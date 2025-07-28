import pyautogui
from datetime import datetime
import time
import os
import Quartz.CoreGraphics as CG
import subprocess
import json
from PIL import Image

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

# List of supported browsers (these will try text extraction first)
browser_apps = ['Arc', 'Google Chrome', 'Safari', 'Brave Browser', 'Microsoft Edge']

# List of apps where text extraction is likely to work well
text_extraction_apps = ['Visual Studio Code', 'Sublime Text', 'Atom', 'TextEdit', 'Notes', 'Mail', 'Calendar', 'Reminders', 'Terminal', 'iTerm2']

# List of apps that should only record metadata (no PNG capture, no text extraction)
metadata_only_apps = ['zoom_us', 'Zoom', 'Zoom.us', 'FaceTime', 'Teams', 'Discord']



# -----------------------------------------------------------------------------
# AppleScript-based visible text extraction (works without Accessibility bridge)
# -----------------------------------------------------------------------------


def grab_browser_content():
    """Return (title, text) from the front-most browser window.
    
    • If the frontmost app is a browser, extracts both title and text content.
    • Otherwise returns empty strings.
    """
    try:
        # Get the frontmost app name
        app_name = subprocess.check_output([
            'osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true'
        ]).decode().strip()
        
        script_path = None
        
        # Map app names to script files
        if app_name == "Arc":
            script_path = os.path.join(os.path.dirname(__file__), 'arc_script.scpt')
        elif app_name == "Google Chrome":
            script_path = os.path.join(os.path.dirname(__file__), 'chrome_script.scpt')
        elif app_name == "Safari":
            script_path = os.path.join(os.path.dirname(__file__), 'safari_script.scpt')
        elif app_name == "Brave Browser":
            script_path = os.path.join(os.path.dirname(__file__), 'brave_script.scpt')
        elif app_name == "Microsoft Edge":
            script_path = os.path.join(os.path.dirname(__file__), 'edge_script.scpt')
        else:
            return "", ""  # Not a supported browser
        
        # Execute the appropriate script
        raw = subprocess.check_output(['osascript', script_path]).decode('utf-8', errors='ignore').strip()
        
        # Split the result on the separator
        if "|||" in raw:
            title, text = raw.split("|||", 1)
            return title.strip(), text.strip()
        else:
            return "", ""
        
    except Exception as e:
        print(f"Browser content extraction failed: {e}")
        return "", ""

def grab_generic_text():
    """Fallback function to get text from non-browser applications."""
    try:
        static_text_script = (
            'tell application "System Events" to tell (first application process whose frontmost is true) '
            'to get value of every static text of windows'
        )
        raw = subprocess.check_output(['osascript', '-e', static_text_script]).decode('utf-8', errors='ignore')
        return raw.replace(', ', '\n').replace(', ', '\n').replace('\n', '\n').replace('\\n', '\n').strip()
    except subprocess.CalledProcessError as e:
        print(f"Error in grab_generic_text: {e}")
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
    """Return raw app name, sanitized version, and window title."""
    try:
        # Get both app name and window title in a single AppleScript call
        # Using a simple separator for better performance
        result = subprocess.check_output([
            'osascript', '-e', 'tell application "System Events" to set frontApp to first application process whose frontmost is true' + '\n' +
                             'set appName to name of frontApp' + '\n' +
                             'try' + '\n' +
                             '  set windowTitle to name of front window of frontApp' + '\n' +
                             'on error' + '\n' +
                             '  set windowTitle to ""' + '\n' +
                             'end try' + '\n' +
                             'return appName & "|||" & windowTitle'
        ]).decode().strip()
        
        # Parse the result using simple string split
        if "|||" in result:
            raw_name, window_title = result.split("|||", 1)
        else:
            raw_name = result
            window_title = ""
            
    except Exception as e:
        print(f"Error getting app info: {e}")
        raw_name = "UnknownApp"
        window_title = ""
    
    safe_name = "".join(c if c.isalnum() else "_" for c in raw_name)
    print("Active app name:", safe_name, "with window title:", window_title)
    return raw_name, safe_name, window_title

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
        'screen_text_filename': fname,
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
        raw_app_name, app_name, window_title = get_active_app_names()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        text = ""
        
        # Check if this app should only record metadata (no PNG, no text)
        # Check both raw name and sanitized name for flexibility
        if raw_app_name in metadata_only_apps or app_name in metadata_only_apps:
            # Just record metadata; no file written
            metadata = {
                'app_name': app_name,
                'timestamp': datetime.strptime(timestamp, "%Y%m%d_%H%M%S").isoformat(),
                'window_title': window_title
            }
            append_metadata(metadata)
            return
        
        # Try text extraction for browsers and apps where it's likely to work
        if raw_app_name in browser_apps:
            window_title, text = grab_browser_content()
        elif raw_app_name in text_extraction_apps:
            text = grab_generic_text()
            # If extracted text length is insignificantly small, treat as no text
            if len(text.strip()) < 10:
                print(f"Warning: Text length is insignificantly small: {len(text.strip())}")
                text = ""
        else:
            # For all other apps, skip text extraction and go straight to PNG
            text = ""

        if text.strip():
            write_text_entry(app_name, timestamp, text, window_title)
            return
        if not text:
            # Fallback to optimized screenshot for OCR
            bounds = get_focused_window_rect()
            if not bounds:
                print("No active window found or cannot get window geometry.")
                return
            
            # Capture high-resolution screenshot
            region = (int(bounds['X']), int(bounds['Y']), int(bounds['Width']), int(bounds['Height']))
            
            # Validate region bounds
            if region[2] <= 0 or region[3] <= 0:
                print(f"Invalid window dimensions: {region}")
                return
            
            # Capture focused window at higher resolution for better OCR
            image = pyautogui.screenshot(region=region)
            
            # Optional: Scale up for even higher quality (uncomment if needed)
            # scale_factor = 2
            # new_size = (image.width * scale_factor, image.height * scale_factor)
            # image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Simple optimization: convert to grayscale for better OCR
            if image.mode != 'L':
                image = image.convert('L')
            
            # Save with optimized settings
            ts_readable = f"{timestamp[:8]} {timestamp[9:] if '_' in timestamp else timestamp[8:]}"
            filename = os.path.join(SCREEN_DIR, f"{ts_readable} - {app_name}.png")
            
            try:
                # Save with maximum quality PNG settings for OCR accuracy
                image.save(filename, 'PNG', optimize=False, compress_level=0)
                
                # Get file size
                file_size_kb = os.path.getsize(filename) / 1024
                
                print(f"Screenshot saved as: {filename}")
                print(f"  Image: {image.size} | Mode: {image.mode} | File size: {file_size_kb:.1f} KB")
            except Exception as save_error:
                print(f"Failed to save screenshot for {app_name}: {save_error}")
                # Fall back to just recording metadata without screenshot
                entry = {
                    'app_name': app_name,
                    'timestamp': datetime.strptime(timestamp, "%Y%m%d_%H%M%S").isoformat(),
                    'window_title': window_title
                }
                append_metadata(entry)
                return
            # Write metadata to JSON for PNG capture
            entry = {
                'screen_capture_filename': os.path.basename(filename),
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
    print("💤 Your Mac can sleep normally - this script won't prevent it")
    try:
        while True:
            capture_focused_window()
            # Use time.sleep which allows the system to sleep
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
