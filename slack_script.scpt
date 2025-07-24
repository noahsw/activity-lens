-- AppleScript to extract the visible conversation and channel name from the
-- main Slack window and return it as a JSON object.
-- Final version based on UI hierarchy analysis.

-- Helper function to escape characters for JSON compatibility.
on escapeForJSON(theText)
	set originalDelimiters to AppleScript's text item delimiters
	
	-- Escape backslashes
	set AppleScript's text item delimiters to "\\"
	set textItems to text items of theText
	set AppleScript's text item delimiters to "\\\\"
	set theText to textItems as string
	
	-- Escape double quotes
	set AppleScript's text item delimiters to "\""
	set textItems to text items of theText
	set AppleScript's text item delimiters to "\\\""
	set theText to textItems as string
	
	-- Replace newlines with the \n character
	set AppleScript's text item delimiters to "
"
	set textItems to text items of theText
	set AppleScript's text item delimiters to "\\n"
	set theText to textItems as string
	
	-- Restore original delimiters
	set AppleScript's text item delimiters to originalDelimiters
	return theText
end escapeForJSON

-- Recursive function to extract all static text values from a given UI element.
on extractTextFrom(uiElement)
	set collectedText to ""
	tell application "System Events"
		try
			-- Check if the current element itself contains the text we want.
			if class of uiElement is static text then
				set elementValue to value of uiElement
				if elementValue is not missing value and elementValue is not "" then
					set collectedText to collectedText & elementValue & "
"
				end if
			end if
			
			-- Recursively search inside any container elements for more text.
			set elementClass to class of uiElement
			if elementClass is group or elementClass is row or elementClass is UI element or elementClass is list then
				repeat with childElement in (every UI element of uiElement)
					set collectedText to collectedText & my extractTextFrom(childElement)
				end repeat
			end if
			
		on error
			-- Ignore errors on individual elements (like buttons that have no value).
		end try
	end tell
	return collectedText
end extractTextFrom

-- Main script logic
try
	-- Initialize variables with default values
	set channelName to "unknown"
	set chatText to ""
	
	tell application "Slack"
		activate
		delay 1 -- Give Slack a moment to become the frontmost application and render UI.
	end tell
	
	tell application "System Events"
		tell process "Slack"
			-- Get the window name to extract the channel name.
			try
				set windowName to name of front window
				-- Assumes window title format: "#channel-name - Workspace" or "User Name - Workspace"
				set originalDelimiters to AppleScript's text item delimiters
				set AppleScript's text item delimiters to " - "
				set channelName to the first text item of windowName
				set AppleScript's text item delimiters to originalDelimiters
			on error
				set channelName to "Error: Could not get channel name."
			end try
			
			-- Get the visible conversation text from the main scroll area.
			set chatText to ""
			try
				-- New strategy: Search the entire window for the list element.
				-- This can be slow, but is very robust against changes in nesting.
				set messageList to missing value
				set allElements to entire contents of window 1
				
				repeat with anElement in allElements
					try
						if class of anElement is list then
							set listDesc to description of anElement
							if listDesc contains "direct message" or listDesc contains "channel" then
								set messageList to anElement
								exit repeat
							end if
						end if
					end try
				end repeat
				
				if messageList is missing value then
					error "Could not find the main message list element after scanning the entire window."
				end if
				
				-- Once the list is found, recursively extract all text from it.
				set chatText to my extractTextFrom(messageList)
				
			on error errMsg
				-- If the targeted approach fails, provide a clear error.
				set chatText to "Error: Could not extract text. The script failed with the following error: " & errMsg
			end try
		end tell
	end tell
	
	-- Escape the extracted text to ensure it's valid inside a JSON string.
	set escapedChannel to my escapeForJSON(channelName)
	set escapedChat to my escapeForJSON(chatText)
	
	-- Construct the final JSON string
	set jsonString to "{\"channel\": \"" & escapedChannel & "\", \"conversation\": \"" & escapedChat & "\"}"
	
	-- Return the JSON string as the script's result.
	return jsonString
	
on error errMsg number errNum
	-- If a major, unhandled error occurs, return it in JSON format for consistent output.
	set errorJSON to "{\"error\": \"An AppleScript error occurred: " & my escapeForJSON(errMsg) & " (Error " & errNum & ")\"}"
	return errorJSON
end try
