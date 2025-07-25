-- AppleScript to extract the visible conversation and channel name from the
-- main Slack window and return it as a JSON object.
-- Final, highly optimized, and robust version for DMs and Channels.

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
	-- Start the timer
	set startTime to current date
	
	-- Initialize variables with default values
	set channelName to "unknown"
	set chatText to ""
	
	tell application "Slack"
		activate
		delay 0.1 -- Minimal delay for maximum speed.
	end tell
	
	tell application "System Events"
		tell process "Slack"
			-- Get the window name to extract the channel name.
			try
				set windowName to name of front window
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
				-- New High-Speed Strategy: Find a unique landmark (the message composer)
				-- and use it to locate the message list. This is extremely fast.
				set messageList to missing value
				
				-- Attempt 1 (Fastest & Most Reliable):
				try
					-- The message composer text area is a reliable, unique landmark.
					set messageComposer to first text area of window 1 whose description starts with "Message to"
					
					-- The message list is usually a sibling of the composer's container. We go up two levels.
					set parentContainer to container of container of messageComposer
					
					-- Now, find the list within that container.
					set messageList to (first list of parentContainer whose description contains "direct message" or description contains "channel")
				on error
					-- If the fast method fails, fall back to the original full window scan.
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
				end try
				
				if messageList is missing value then
					error "Could not find the main message list after trying all known methods."
				end if
				
				-- Use the reliable recursive function to extract text.
				set chatText to my extractTextFrom(messageList)
				
			on error errMsg
				-- If all approaches fail, provide a clear error.
				set chatText to "Error: Could not extract text. The script failed with the following error: " & errMsg
			end try
		end tell
	end tell
	
	-- Stop the timer and calculate the duration
	set endTime to current date
	set duration to endTime - startTime
	
	-- Escape the extracted text to ensure it's valid inside a JSON string.
	set escapedChannel to my escapeForJSON(channelName)
	set escapedChat to my escapeForJSON(chatText)
	
	-- Construct the final JSON string.
	set jsonString to "{\"channel\": \"" & escapedChannel & "\", \"conversation\": \"" & escapedChat & "\", \"execution_time_seconds\": " & duration & "}"
	
	-- Return the JSON string as the script's result.
	return jsonString
	
on error errMsg number errNum
	-- If a major, unhandled error occurs, return it in JSON format for consistent output.
	set errorJSON to "{\"error\": \"An AppleScript error occurred: " & my escapeForJSON(errMsg) & " (Error " & errNum & ")\"}"
	return errorJSON
end try
