from datetime import datetime
import time
import os
import Quartz.CoreGraphics as CG
import subprocess
import json
from PIL import Image
import argparse

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
CACHE_DIR = os.path.expanduser('~/Library/Caches/activity-lens')

def get_date_paths():
    """Get the current date and return paths with date appended."""
    current_date = datetime.now().strftime('%Y%m%d')
    screen_dir = os.path.join(CACHE_DIR, f'screen-captures-{current_date}')
    json_path = os.path.join(CACHE_DIR, f'screen_captures_ocr-{current_date}.json')
    return screen_dir, json_path

# Get current date-based paths
SCREEN_DIR, JSON_PATH = get_date_paths()
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
metadata_only_apps = ['FaceTime', 'Teams', 'Discord']

# App-specific cropping configurations (left%, top%, right%, bottom% crop)
# These are applied after the initial window capture
app_cropping = {
    'Slack': (27, 0, 0, 0),      # Crop 15% from left (sidebar)
    'Microsoft_Outlook': (40, 10, 0, 0),
    'zoom_us': (0, 0, 0, 10),
    'ChatGPT': (14, 0, 0, 0),
}



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





def get_display_id_for_window(bounds):
    """Determine which display contains the window and return its ID."""
    window_center_x = bounds['X'] + bounds['Width'] // 2
    window_center_y = bounds['Y'] + bounds['Height'] // 2
    
    # print(f"  Window center: ({window_center_x}, {window_center_y})")
    
    # Get main display bounds
    main_display = CG.CGMainDisplayID()
    main_bounds = CG.CGDisplayBounds(main_display)
    main_x, main_y = int(main_bounds.origin.x), int(main_bounds.origin.y)
    main_width, main_height = int(main_bounds.size.width), int(main_bounds.size.height)
    
    # print(f"  Main display bounds: {main_x}, {main_y}, {main_width}x{main_height}")
    
    # Check if window is on main display
    if (main_x <= window_center_x <= main_x + main_width and 
        main_y <= window_center_y <= main_y + main_height):
        # print(f"  Window is on main display (ID: 1)")
        return 1
    
    # Window is on secondary display
    # print(f"  Window is on secondary display (ID: 2)")
    return 2

def calculate_cropped_bounds(original_bounds, app_name):
    """Calculate the cropped bounds based on app-specific cropping percentages."""
    if app_name not in app_cropping:
        return original_bounds
    
    left_crop_pct, top_crop_pct, right_crop_pct, bottom_crop_pct = app_cropping[app_name]
    
    # Calculate crop pixels based on percentages
    left_crop_pixels = int(original_bounds['Width'] * left_crop_pct / 100)
    top_crop_pixels = int(original_bounds['Height'] * top_crop_pct / 100)
    right_crop_pixels = int(original_bounds['Width'] * right_crop_pct / 100)
    bottom_crop_pixels = int(original_bounds['Height'] * bottom_crop_pct / 100)
    
    # Calculate new bounds
    new_x = original_bounds['X'] + left_crop_pixels
    new_y = original_bounds['Y'] + top_crop_pixels
    new_width = original_bounds['Width'] - left_crop_pixels - right_crop_pixels
    new_height = original_bounds['Height'] - top_crop_pixels - bottom_crop_pixels
    
    # Validate dimensions
    if new_width <= 0 or new_height <= 0:
        print(f"  ⚠️  Cropping would result in invalid dimensions, using original bounds")
        return original_bounds
    
    cropped_bounds = {
        'X': new_x,
        'Y': new_y,
        'Width': new_width,
        'Height': new_height
    }
    
    print(f"  Original bounds: {original_bounds['X']}, {original_bounds['Y']}, {original_bounds['Width']}x{original_bounds['Height']}")
    print(f"  Cropping: left={left_crop_pct}%, top={top_crop_pct}%, right={right_crop_pct}%, bottom={bottom_crop_pct}%")
    print(f"  Cropped bounds: {cropped_bounds['X']}, {cropped_bounds['Y']}, {cropped_bounds['Width']}x{cropped_bounds['Height']}")
    
    return cropped_bounds

def capture_window_screencapture(bounds, app_name, output_path):
    """Capture window using screencapture with real-time cropping."""
    try:
        # Apply app-specific cropping if configured
        # Handle case where args might be None (e.g., in tests)
        if args is None or not args.no_crop:
            bounds = calculate_cropped_bounds(bounds, app_name)
        
        # Determine display ID
        display_id = get_display_id_for_window(bounds)
        
        # Build optimized screencapture command
        cmd = [
            'screencapture',
            '-D', str(display_id),
            '-R', f'{bounds["X"]},{bounds["Y"]},{bounds["Width"]},{bounds["Height"]}',
            '-x',  # No sound
            '-o',  # No window shadows (faster, cleaner)
            '-a',  # No attached windows (cleaner capture)
            output_path
        ]
        
        print(f"  Running screencapture: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and os.path.exists(output_path):
            # Get image info for logging
            try:
                image = Image.open(output_path)
                file_size_kb = os.path.getsize(output_path) / 1024
                print(f"  ✅ Screencapture successful: {image.size} | File size: {file_size_kb:.1f} KB")
                return True
            except Exception as e:
                print(f"  ⚠️  Screencapture completed but couldn't verify image: {e}")
                return True
        else:
            print(f"  ❌ Screencapture failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"  ❌ Screencapture error: {e}")
        return False

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
            
            print(f"  Window bounds: {bounds['X']}, {bounds['Y']}, {bounds['Width']}x{bounds['Height']}")
            
            # Use unified screencapture approach with real-time cropping
            ts_readable = f"{timestamp[:8]} {timestamp[9:] if '_' in timestamp else timestamp[8:]}"
            filename = os.path.join(SCREEN_DIR, f"{ts_readable} - {app_name}.png")
            
            # Capture using screencapture with real-time cropping
            if capture_window_screencapture(bounds, app_name, filename):
                # Write metadata to JSON for PNG capture
                entry = {
                    'screen_capture_filename': os.path.basename(filename),
                    'app_name': app_name,
                    'timestamp': datetime.strptime(timestamp, "%Y%m%d_%H%M%S").isoformat(),
                    'window_title': window_title
                }
                append_metadata(entry)
                print(f"Screenshot saved as: {filename}")
            else:
                print(f"Failed to capture screenshot for {app_name}")
                # Fall back to just recording metadata without screenshot
                entry = {
                    'app_name': app_name,
                    'timestamp': datetime.strptime(timestamp, "%Y%m%d_%H%M%S").isoformat(),
                    'window_title': window_title
                }
                append_metadata(entry)
            return
        # Otherwise text existed and was logged above
    except Exception as e:
        print(f"Error capturing screenshot or extracting text: {e}")

def capture_focused_window_continuous(interval=15):
    """
    Continuously captures screenshots or text of the focused window every specified interval.
    Args:
        interval (int): Time interval between captures in seconds (default: 15)
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

# Global variable for command line arguments
args = None

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Capture screen content for activity tracking')
    parser.add_argument('--single', action='store_true', 
                       help='Capture a single screenshot and exit (for testing)')
    parser.add_argument('--interval', type=int, default=15,
                       help='Interval between captures in seconds (default: 15)')
    parser.add_argument('--no-crop', action='store_true',
                       help='Disable app-specific cropping for testing')
    parser.add_argument('--fast', action='store_true',
                       help='Use faster capture mode (logical resolution, not Retina)')
    
    args = parser.parse_args()
    
    if args.single:
        print("📸 Single capture mode - capturing one screenshot and exiting...")
        capture_focused_window()
        print("✅ Single capture completed")
    else:
        # Continuous capture mode
        capture_focused_window_continuous(args.interval)
