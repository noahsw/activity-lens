tell application "Safari"
	set pageTitle to do JavaScript "document.title" in current tab of front window
	set pageText to do JavaScript "document.body.innerText" in current tab of front window
end tell

return pageTitle & "|||" & pageText 