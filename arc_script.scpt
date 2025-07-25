tell application "Arc"
	tell front window's active tab
		set pageTitle to execute javascript "document.title"
		set pageText to execute javascript "document.body.innerText"
	end tell
end tell

return pageTitle & "|||" & pageText 