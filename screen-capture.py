import pyautogui
from datetime import datetime
import time
import os
import Quartz.CoreGraphics as CG
import subprocess
import json

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
CACHE_DIR = os.path.expanduser('~/Library/Caches/activity-lens')
SCREEN_DIR = os.path.join(CACHE_DIR, 'screen-captures')
JSON_PATH   = os.path.join(CACHE_DIR, 'screen_captures_ocr.json')
os.makedirs(SCREEN_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# Helper to append a metadata block to the master JSON file
# -----------------------------------------------------------------------------


def append_metadata(entry: dict):
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as jf:
            data = json.load(jf)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []                          # start fresh if file missing or invalid

    data.append(entry)
    with open(JSON_PATH, 'w', encoding='utf-8') as jf:
        json.dump(data, jf, indent=2, ensure_ascii=False)

# Common browsers and their AppleScript JS execution commands
browser_scripts = {
    'Arc': 'tell application "Arc" to tell front window\'s active tab to execute javascript "document.body.innerText"',
    'Google Chrome': 'tell application "Google Chrome" to tell active tab of front window to execute javascript "document.body.innerText"',
    'Safari': 'tell application "Safari" to do JavaScript "document.body.innerText" in current tab of front window',
    'Brave Browser': 'tell application "Brave Browser" to tell active tab of front window to execute javascript "document.body.innerText"',
    'Microsoft Edge': 'tell application "Microsoft Edge" to tell active tab of front window to execute javascript "document.body.innerText"',
}

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

        if app_name in browser_scripts:
            raw = subprocess.check_output(['osascript', '-e', browser_scripts[app_name]]).decode('utf-8', errors='ignore')
            return raw.strip()

        # Fallback: generic static-text extraction via Accessibility/System Events
        static_text_script = (
            'tell application "System Events" to tell (first application process whose frontmost is true) '
            'to get value of every static text of windows'
        )
        raw = subprocess.check_output(['osascript', '-e', static_text_script]).decode('utf-8', errors='ignore')
        return raw.replace(', ', '\n').replace(', ', '\n').replace('\n', '\n').replace('\\n', '\n').strip()

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

def get_active_app_names():
    """Return raw app name and sanitized version."""
    try:
        raw_name = subprocess.check_output([
            'osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true'
        ]).decode().strip()
    except Exception:
        raw_name = "UnknownApp"
    safe_name = "".join(c if c.isalnum() else "_" for c in raw_name)
    print("Active app name:", safe_name)
    return raw_name, safe_name

def write_text_entry(app_name, timestamp, text, window_title="", output_json=JSON_PATH):
    """Save text to a .txt file and write a metadata entry to JSON."""
    # Create human-readable filename: "YYYYMMDD HHMMSS - AppName.txt"
    ts_readable = f"{timestamp[:8]} {timestamp[9:] if '_' in timestamp else timestamp[8:]}"
    txt_filename = f"{ts_readable} - {app_name}.txt"
    txt_path = os.path.join(SCREEN_DIR, txt_filename)

    # Skip writing empty files
    if text.strip():
        with open(txt_path, 'w', encoding='utf-8') as tf:
            tf.write(text)
        fname = txt_filename
    else:
        fname = None  # indicate no file was written

    # Build JSON metadata entry (no text_full to keep JSON small)
    entry = {
        'filename': fname,
        'app_name': app_name,
        'timestamp': datetime.strptime(timestamp, "%Y%m%d_%H%M%S").isoformat(),
        'window_title': window_title
    }
    append_metadata(entry)
    print(f"Text extracted and saved to {output_json}")

def capture_focused_window():
    """
    Tries to extract visible text from the AXTree. If unsuccessful, captures a screenshot of the currently focused window and saves it as PNG.
    """
    try:
        raw_app_name, app_name = get_active_app_names()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        window_title, text = ("", "")
        if app_name in browser_scripts:
            text = grab_visible_text()
            window_title = get_window_title()
        elif app_name == "Slack":
            window_title, text = slack_get_title_and_messages()
        elif app_name == "zoom_us":
            # Just record focus time; no file written
            metadata = {
                'filename': None,
                'app_name': app_name,
                'timestamp': datetime.strptime(timestamp, "%Y%m%d_%H%M%S").isoformat(),
                'window_title': "Zoom Meeting"
            }
            append_metadata(metadata)
            return
        else:
            text = grab_visible_text()
            window_title = get_window_title()

        if text.strip():
            write_text_entry(app_name, timestamp, text, window_title)
            return
        # If extracted text length is insignificantly small, treat as no text
        if len(text.strip()) < 10:
            text = ""
        if not text:
            # Fallback to screenshot
            bounds = get_focused_window_rect()
            if not bounds:
                print("No active window found or cannot get window geometry.")
                return
            screenshot = pyautogui.screenshot(region=(
                int(bounds['X']), int(bounds['Y']), int(bounds['Width']), int(bounds['Height'])
            ))
            ts_readable = f"{timestamp[:8]} {timestamp[9:] if '_' in timestamp else timestamp[8:]}"
            filename = os.path.join(SCREEN_DIR, f"{ts_readable} - {app_name}.png")
            screenshot.save(filename)
            print(f"Screenshot saved as: {filename}")
            # Write metadata to JSON for PNG capture
            entry = {
                'filename': os.path.basename(filename),
                'app_name': app_name,
                'timestamp': datetime.strptime(timestamp, "%Y%m%d_%H%M%S").isoformat(),
                'window_title': window_title
            }
            append_metadata(entry)
            return
        # Otherwise text existed and was logged above
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

# ------------------------------------------------------------------
# Slack-specific AppleScript helpers
# ------------------------------------------------------------------
def slack_get_title_and_messages() -> tuple[str, str]:
    """
    Returns (window_title, message_text) for the front-most Slack window.
    If anything fails, returns ("", "").
    """
    script_path = os.path.join(os.path.dirname(__file__), 'slack_script.scpt')
    try:
        raw = subprocess.check_output(
            ['osascript', script_path]
        ).decode('utf-8', errors='ignore').strip()
        
        # Parse the JSON response
        data = json.loads(raw)
        
        if 'error' in data:
            print(f"Slack AppleScript error: {data['error']}")
            return "", ""
        
        channel = data.get('channel', '')
        conversation = data.get('conversation', '')
        
        print(f"Slack channel: {channel}")
        print(f"Slack conversation length: {len(conversation)} chars")
        return channel, conversation
        
    except json.JSONDecodeError as e:
        print(f"Slack AppleScript returned invalid JSON: {e}")
        return "", ""
    except Exception as e:
        print(f"Slack AppleScript failed: {e}")
        return "", ""

if __name__ == "__main__":
    # For single capture
    # capture_focused_window()
    # For continuous capture (uncomment the line below)
    capture_focused_window_continuous()
