import pyautogui
from datetime import datetime
import time
import os
import Quartz.CoreGraphics as CG
import subprocess
import json

# -----------------------------------------------------------------------------
# AppleScript-based visible text extraction (works without Accessibility bridge)
# -----------------------------------------------------------------------------


def grab_visible_text():
    """Return visible text from the front-most window.

    • If the frontmost app is a browser (Arc, Chrome, Safari, etc.) run
      JavaScript `document.body.innerText` to get full page text.
    • Otherwise fall back to getting every static-text value via System Events.
    """
    try:
        # Which application is frontmost?
        app_name = subprocess.check_output(
            ['osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true']
        ).decode().strip()

        browser_scripts = {
            'Arc': 'tell application "Arc" to tell front window\'s active tab to execute javascript "document.body.innerText"',
            'Google Chrome': 'tell application "Google Chrome" to tell active tab of front window to execute javascript "document.body.innerText"',
            'Safari': 'tell application "Safari" to do JavaScript "document.body.innerText" in current tab of front window',
            'Brave Browser': 'tell application "Brave Browser" to tell active tab of front window to execute javascript "document.body.innerText"',
            'Microsoft Edge': 'tell application "Microsoft Edge" to tell active tab of front window to execute javascript "document.body.innerText"',
        }

        if app_name in browser_scripts:
            raw = subprocess.check_output(['osascript', '-e', browser_scripts[app_name]]).decode('utf-8', errors='ignore')
            return raw.strip()

        # Fallback: generic static-text extraction via Accessibility/System Events
        static_text_script = (
            'tell application "System Events" to tell (first application process whose frontmost is true) '
            'to get value of every static text of windows'
        )
        raw = subprocess.check_output(['osascript', '-e', static_text_script]).decode('utf-8', errors='ignore')
        return raw.replace(', ', '\n').strip()

    except subprocess.CalledProcessError as e:
        print(f"Error in grab_visible_text: {e}")
        return ""

def get_window_title():
    """Return the window title.

    • If the frontmost app is a browser, use JavaScript `document.title`.
    • Otherwise return the window name via System Events.
    """
    try:
        app_name = subprocess.check_output([
            'osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true'
        ]).decode().strip()

        browser_title_scripts = {
            'Arc': 'tell application "Arc" to tell front window\'s active tab to execute javascript "document.title"',
            'Google Chrome': 'tell application "Google Chrome" to tell active tab of front window to execute javascript "document.title"',
            'Safari': 'tell application "Safari" to do JavaScript "document.title" in current tab of front window',
            'Brave Browser': 'tell application "Brave Browser" to tell active tab of front window to execute javascript "document.title"',
            'Microsoft Edge': 'tell application "Microsoft Edge" to tell active tab of front window to execute javascript "document.title"',
        }

        if app_name in browser_title_scripts:
            title = subprocess.check_output(['osascript', '-e', browser_title_scripts[app_name]]).decode().strip()
            return title

        title = subprocess.check_output([
            'osascript',
            '-e', 'tell application "System Events" to tell (first application process whose frontmost is true) to get name of front window'
        ]).decode().strip()
        return title
    except Exception:
        return ""

def get_focused_window_rect():
    CGWindowListCopyWindowInfo = getattr(CG, 'CGWindowListCopyWindowInfo')
    kCGWindowListOptionOnScreenOnly = getattr(CG, 'kCGWindowListOptionOnScreenOnly')
    kCGNullWindowID = getattr(CG, 'kCGNullWindowID')
    windows = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
    # Find the frontmost, non-desktop, non-hidden window
    for w in windows:
        if w.get('kCGWindowLayer', 0) == 0 and w.get('kCGWindowOwnerName') and w.get('kCGWindowBounds'):
            bounds = w['kCGWindowBounds']
            return bounds
    return None

def get_active_app_name():
    try:
        app_name = subprocess.check_output(
            ['osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true']
        ).decode().strip()
    except Exception:
        app_name = "UnknownApp"
    # Sanitize app name for filename
    safe_app_name = "".join(c if c.isalnum() else "_" for c in app_name)
    print("Active app name:", safe_app_name)
    return safe_app_name

def write_text_json(app_name, timestamp, text, window_title="", output_json="screen_captures_ocr.json"):
    # Write a JSON entry in the same format as ocr_extract.py
    entry = {
        'filename': f'{app_name}_focused_window_{timestamp}.txt',
        'app_name': app_name,
        'timestamp': datetime.strptime(timestamp, "%Y%m%d_%H%M%S").isoformat(),
        'window_title': window_title,
        'text_lines': text.splitlines(),
        'text_full': text
    }
    # Append to or create the JSON file
    if os.path.exists(output_json):
        with open(output_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = []
    data.append(entry)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Text extracted and saved to {output_json}")

def capture_focused_window():
    """
    Tries to extract visible text from the AXTree. If unsuccessful, captures a screenshot of the currently focused window and saves it as PNG.
    """
    try:
        app_name = get_active_app_name()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        text = grab_visible_text()
        window_title = get_window_title()
        if text.strip():
            write_text_json(app_name, timestamp, text, window_title)
            return
        # Fallback to screenshot
        bounds = get_focused_window_rect()
        if not bounds:
            print("No active window found or cannot get window geometry.")
            return
        screenshot = pyautogui.screenshot(region=(
            int(bounds['X']), int(bounds['Y']), int(bounds['Width']), int(bounds['Height'])
        ))
        output_dir = "screen-captures"
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"{app_name}_focused_window_{timestamp}.png")
        screenshot.save(filename)
        print(f"Screenshot saved as: {filename}")
    except Exception as e:
        print(f"Error capturing screenshot or extracting text: {e}")

def capture_focused_window_continuous(interval=5):
    """
    Continuously captures screenshots or text of the focused window every specified interval.
    Args:
        interval (int): Time interval between captures in seconds (default: 5)
    """
    print(f"Starting continuous capture every {interval} seconds...")
    print("Press Ctrl+C to stop")
    try:
        while True:
            capture_focused_window()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nCapture stopped by user")

if __name__ == "__main__":
    # For single capture
    # capture_focused_window()
    # For continuous capture (uncomment the line below)
    capture_focused_window_continuous()
