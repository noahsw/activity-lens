import pyautogui
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



def get_display_info():
    """Get information about all displays."""
    try:
        # Get the main display first
        main_display = CG.CGMainDisplayID()
        main_bounds = CG.CGDisplayBounds(main_display)
        
        displays = [{
            'id': main_display,
            'bounds': main_bounds,
            'x': int(main_bounds.origin.x),
            'y': int(main_bounds.origin.y),
            'width': int(main_bounds.size.width),
            'height': int(main_bounds.size.height)
        }]
        print(f"  Main display: {displays[0]}")
        
        # Try to get additional displays using a different approach
        # For now, we'll use a simple heuristic based on the window coordinates
        # If the window is beyond the main display bounds, we'll create a virtual second display
        
        return displays
    except Exception as e:
        print(f"  ❌ Error getting display info: {e}")
        # Fallback: assume main display is at (0,0) with pyautogui size
        main_width, main_height = pyautogui.size()
        return [{'id': 0, 'x': 0, 'y': 0, 'width': main_width, 'height': main_height}]

def get_display_for_window(window_bounds, displays):
    """Determine which display contains the window."""
    window_x, window_y = window_bounds['X'], window_bounds['Y']
    window_center_x = window_x + window_bounds['Width'] // 2
    window_center_y = window_y + window_bounds['Height'] // 2
    
    print(f"  Window center: ({window_center_x}, {window_center_y})")
    
    # Check if window is on the main display
    main_display = displays[0]
    display_x, display_y = main_display['x'], main_display['y']
    display_width, display_height = main_display['width'], main_display['height']
    
    print(f"  Main display bounds: {display_x}, {display_y}, {display_width}x{display_height}")
    
    # Check if window center is within main display bounds
    if (display_x <= window_center_x <= display_x + display_width and 
        display_y <= window_center_y <= display_y + display_height):
        print(f"  Window is on main display: {main_display}")
        return main_display
    
    # Window appears to be on a secondary display
    print(f"  Window appears to be on secondary display")
    
    # Let's try a different approach - use pyautogui to get the actual screen size
    # and see if the window coordinates make sense relative to that
    try:
        pyautogui_width, pyautogui_height = pyautogui.size()
        print(f"  PyAutoGUI screen size: {pyautogui_width}x{pyautogui_height}")
        
        # If the window coordinates are within pyautogui bounds, it might actually be on main display
        if (0 <= window_center_x <= pyautogui_width and 0 <= window_center_y <= pyautogui_height):
            print(f"  Window is within pyautogui bounds - treating as main display")
            return main_display
    except Exception as e:
        print(f"  Error getting pyautogui size: {e}")
    
    # If we get here, assume it's a secondary display
    # Create a virtual secondary display entry
    secondary_display = {
        'id': 1,  # Virtual ID
        'x': display_width,  # Position to the right of main display
        'y': 0,
        'width': 1920,  # Assume standard width
        'height': 1080,  # Assume standard height
        'is_secondary': True
    }
    
    print(f"  Created virtual secondary display: {secondary_display}")
    return secondary_display

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

def capture_window_high_res(bounds):
    """
    Capture a window at high resolution using Core Graphics directly.
    This handles Retina displays properly by using physical coordinates.
    """
    try:
        # Get the main display ID
        main_display = CG.CGMainDisplayID()
        
        if main_display == 0:
            raise Exception("No main display available")
            
        # Convert logical coordinates to physical coordinates
        x = int(bounds['X'])
        y = int(bounds['Y'])
        width = int(bounds['Width'])
        height = int(bounds['Height'])
        
        # Validate dimensions
        if width <= 0 or height <= 0:
            raise Exception(f"Invalid dimensions: {width}x{height}")
        
        # For now, use a simpler approach that's more stable
        # Capture the entire display and let PIL handle the cropping
        full_display_image = CG.CGDisplayCreateImage(main_display)
        if full_display_image is None:
            raise Exception("Could not capture display image")
        
        # Get the full display dimensions
        full_width = CG.CGImageGetWidth(full_display_image)
        full_height = CG.CGImageGetHeight(full_display_image)
        
        # Get image properties
        bytes_per_row = CG.CGImageGetBytesPerRow(full_display_image)
        data_provider = CG.CGImageGetDataProvider(full_display_image)
        
        # Copy the image data
        data = CG.CGDataProviderCopyData(data_provider)
        if data is None:
            CG.CGImageRelease(full_display_image)
            raise Exception("Could not copy image data")
        
        try:
            # Create PIL Image from raw data
            full_image = Image.frombytes('RGBA', (full_width, full_height), data, 'raw', 'BGRA', bytes_per_row)
        except Exception as e:
            # Try with different pixel format
            try:
                full_image = Image.frombytes('RGB', (full_width, full_height), data, 'raw', 'BGR', bytes_per_row)
            except Exception as e2:
                CG.CGImageRelease(full_display_image)
                raise Exception(f"Failed to create PIL image: {e}")
        
        # Clean up Core Graphics resources immediately
        CG.CGImageRelease(full_display_image)
        
        # Crop the image using PIL (more stable than Core Graphics cropping)
        cropped_image = full_image.crop((x, y, x + width, y + height))
        
        return cropped_image
        
    except Exception as e:
        print(f"  High-res capture failed: {e}")
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
            
            # Get display information and determine which display the window is on
            print("  Getting display information...")
            displays = get_display_info()
            target_display = get_display_for_window(bounds, displays)
            
            # For now, let's try a simpler approach that prioritizes cropping
            # If the window appears to be on a secondary display, let's try to capture it
            # using the original coordinates but with bounds checking
            
            # Get the original window coordinates
            window_x = int(bounds['X'])
            window_y = int(bounds['Y'])
            window_width = int(bounds['Width'])
            window_height = int(bounds['Height'])
            
            print(f"  Original window coordinates: {window_x}, {window_y}, {window_width}x{window_height}")
            
            # Get the main display size for bounds checking
            main_width, main_height = pyautogui.size()
            print(f"  Main display size: {main_width}x{main_height}")
            
            # Check if the window is within the main display bounds
            if (0 <= window_x < main_width and 0 <= window_y < main_height and 
                window_x + window_width <= main_width and window_y + window_height <= main_height):
                print(f"  Window is within main display bounds - capturing normally")
                # Window is fully within main display, use normal capture
                target_display = displays[0]  # Force to main display
            else:
                print(f"  Window extends beyond main display bounds")
                # Check if this is a secondary display case
                if target_display.get('is_secondary', False):
                    print(f"  This appears to be a secondary display - will handle separately")
                    # Don't adjust coordinates yet, let the secondary display logic handle it
                else:
                    # Window extends beyond main display but not secondary, try to clip
                    if window_x < 0:
                        window_width += window_x  # Reduce width by the amount that goes off the left
                        window_x = 0
                    if window_y < 0:
                        window_height += window_y  # Reduce height by the amount that goes off the top
                        window_y = 0
                    if window_x + window_width > main_width:
                        window_width = main_width - window_x  # Clip to display width
                    if window_y + window_height > main_height:
                        window_height = main_height - window_y  # Clip to display height
                    
                    print(f"  Adjusted window region: {window_x}, {window_y}, {window_width}x{window_height}")
                    
                    # Final validation only for non-secondary displays
                    if window_width <= 0 or window_height <= 0:
                        print(f"  ❌ Window is completely outside display bounds")
                        return
            
            # Check if we're dealing with a secondary display
            if target_display.get('is_secondary', False):
                print(f"  ⚠️  Window is on secondary display")
                print(f"  Attempting to capture the specific window region...")
                
                # Try to capture the specific window region directly
                try:
                    # Use the original coordinates but try to capture the region
                    # This might work if pyautogui can handle coordinates beyond the main display
                    print(f"  Attempting direct region capture: ({window_x}, {window_y}, {window_width}, {window_height})")
                    image = pyautogui.screenshot(region=(window_x, window_y, window_width, window_height))
                    print(f"  Direct capture successful: {image.size}")
                except Exception as e:
                    print(f"  Direct capture failed: {e}")
                    print(f"  Falling back to main display capture with cropping...")
                    
                    # Fallback: capture the main display and apply cropping
                    full_screen = pyautogui.screenshot()
                    print(f"  Main display captured: {full_screen.size}")
                    
                    # Use the main display dimensions for cropping
                    main_width, main_height = pyautogui.size()
                    image = full_screen.crop((0, 0, main_width, main_height))
                    print(f"  Main display region: {image.size} (will apply cropping)")
            else:
                # Window is on the main display - use normal pyautogui capture
                if args and args.fast:
                    # Fast mode: Direct region capture (logical resolution, faster)
                    print(f"  Fast mode: Capturing region directly...")
                    image = pyautogui.screenshot(region=(window_x, window_y, window_width, window_height))
                    print(f"  Fast capture: {image.size} (logical resolution)")
                else:
                    # Quality mode: Full screen capture + crop (Retina resolution, slower)
                    print(f"  Quality mode: Capturing full screen at Retina resolution...")
                    full_screen = pyautogui.screenshot()
                    print(f"  Full screen captured: {full_screen.size}")
                    
                    # Scale the coordinates to physical coordinates for cropping
                    scale_factor = 2  # Retina scale factor
                    x = window_x * scale_factor
                    y = window_y * scale_factor
                    width = window_width * scale_factor
                    height = window_height * scale_factor
                    
                    print(f"  Scale factor: {scale_factor}")
                    print(f"  Physical crop coordinates: ({x}, {y}, {x + width}, {y + height})")
                    
                    # Ensure coordinates are within bounds
                    full_width, full_height = full_screen.size
                    x = max(0, min(x, full_width - 1))
                    y = max(0, min(y, full_height - 1))
                    width = min(width, full_width - x)
                    height = min(height, full_height - y)
                    
                    # Crop the region from the full Retina capture
                    image = full_screen.crop((x, y, x + width, y + height))
                    print(f"  Cropped region: {image.size} (Retina resolution)")
            
            # App-specific cropping (e.g., remove sidebars from chat apps)
            # Use same case sensitivity as other app lists
            if app_name in app_cropping and not args.no_crop:
                left_crop_pct, top_crop_pct, right_crop_pct, bottom_crop_pct = app_cropping[app_name]
                print(f"  {app_name} window detected, applying app-specific cropping...")
                
                # Calculate crop pixels based on percentages
                left_crop_pixels = int(image.size[0] * left_crop_pct / 100)
                top_crop_pixels = int(image.size[1] * top_crop_pct / 100)
                right_crop_pixels = int(image.size[0] * right_crop_pct / 100)
                bottom_crop_pixels = int(image.size[1] * bottom_crop_pct / 100)
                
                # Apply cropping
                new_left = left_crop_pixels  # Start from this many pixels from left edge
                new_top = top_crop_pixels    # Start from this many pixels from top edge
                new_right = image.size[0] - right_crop_pixels  # End this many pixels from right edge
                new_bottom = image.size[1] - bottom_crop_pixels  # End this many pixels from bottom edge
                
                print(f"  Original size: {image.size}")
                print(f"  Cropping: left={left_crop_pct}%, top={top_crop_pct}%, right={right_crop_pct}%, bottom={bottom_crop_pct}%")
                print(f"  Crop pixels: left={left_crop_pixels}, top={top_crop_pixels}, right={right_crop_pixels}, bottom={bottom_crop_pixels}")
                
                if new_right > new_left and new_bottom > new_top:
                    image = image.crop((new_left, new_top, new_right, new_bottom))
                    print(f"  Cropped to: {image.size}, mode: {image.mode}")
                else:
                    print(f"  Warning: Invalid crop dimensions, keeping original size")
            
            # Simple optimization: convert to grayscale for better OCR
            try:
                if image.mode != 'L':
                    image = image.convert('L')
            except Exception as convert_error:
                print(f"  Warning: Failed to convert to grayscale: {convert_error}")
                # Continue with original image mode
            
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
