tell application "Brave Browser"
	tell active tab of front window
		set pageTitle to execute javascript "document.title"
		set pageText to execute javascript "document.body.innerText"
	end tell
end tell

return pageTitle & "|||" & pageText 