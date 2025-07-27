#!/usr/bin/env python3
"""
Prepare Activity Analysis for LLM
Reads the activity analysis prompt and screen captures data,
combines them, and copies to clipboard for pasting into ChatGPT/other LLMs.
"""

import os
import json
import pyperclip
from datetime import datetime

# Paths
CACHE_DIR = os.path.expanduser('~/Library/Caches/activity-lens')
json_file = os.path.join(CACHE_DIR, 'screen_captures_ocr.json')
prompt_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analyze_activity_prompt.txt')

def load_prompt():
    """Load the activity analysis prompt."""
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"❌ Error: Prompt file not found: {prompt_file}")
        print("   Make sure analyze_activity_prompt.txt exists in the current directory")
        return None
    except Exception as e:
        print(f"❌ Error reading prompt file: {e}")
        return None

def load_activity_data():
    """Load the screen captures activity data."""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: Activity data file not found: {json_file}")
        print("   Make sure you've run the screen capture analysis first")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Error reading JSON file: {e}")
        return None
    except Exception as e:
        print(f"❌ Error loading activity data: {e}")
        return None

def format_activity_data(data):
    """Format the activity data for LLM analysis."""
    if not data:
        return "No activity data available."
    
    formatted_entries = []
    
    for entry in data:
        # Extract key information
        timestamp = entry.get('timestamp', 'Unknown time')
        app_name = entry.get('app_name', 'Unknown app')
        window_title = entry.get('window_title', '')
        summary = entry.get('summary', '')
        
        # Format the entry
        entry_text = f"Time: {timestamp}\nApp: {app_name}"
        
        if window_title:
            entry_text += f"\nWindow: {window_title}"
        
        if summary:
            entry_text += f"\nActivity: {summary}"
        
        formatted_entries.append(entry_text)
    
    return "\n\n---\n\n".join(formatted_entries)

def copy_to_clipboard(text):
    """Copy text to clipboard and verify it worked."""
    try:
        pyperclip.copy(text)
        
        # Verify the copy worked by reading it back
        clipboard_content = pyperclip.paste()
        
        if clipboard_content == text:
            print("✅ Successfully copied to clipboard!")
            return True
        else:
            print("⚠️  Warning: Clipboard content doesn't match expected text")
            print("   The copy may have been truncated or failed")
            return False
            
    except Exception as e:
        print(f"❌ Error copying to clipboard: {e}")
        print("   You may need to install pyperclip: pip install pyperclip")
        return False

def main():
    """Main function to prepare activity analysis for LLM."""
    
    print("🔍 Preparing Activity Analysis for LLM")
    print("=" * 50)
    
    # Load the prompt
    print("📝 Loading analysis prompt...")
    prompt = load_prompt()
    if not prompt:
        return
    
    # Load activity data
    print("📊 Loading activity data...")
    activity_data = load_activity_data()
    if not activity_data:
        return
    
    print(f"   Found {len(activity_data)} activity entries")
    
    # Format the data
    print("📋 Formatting data...")
    formatted_data = format_activity_data(activity_data)
    
    # Combine prompt and data
    full_text = f"{prompt}\n\n{formatted_data}"
    
    # Show preview
    print(f"\n📄 Preview (first 200 characters):")
    print("-" * 50)
    print(full_text[:200] + "..." if len(full_text) > 200 else full_text)
    print("-" * 50)
    
    # Copy to clipboard
    print(f"\n📋 Copying to clipboard...")
    if copy_to_clipboard(full_text):
        print("\n🎯 Next Steps:")
        print("1. Open your favorite LLM (ChatGPT, Claude, etc.)")
        print("2. Paste the content (Cmd+V on Mac, Ctrl+V on Windows)")
        print("3. Ask the LLM to analyze your activity patterns")
        print("4. Get insights on time usage and AI outsourcing opportunities!")
        
        print(f"\n📊 Data Summary:")
        print(f"   - Total entries: {len(activity_data)}")
        print(f"   - Total characters: {len(full_text):,}")
        print(f"   - Estimated tokens: {len(full_text) // 4:,} (rough estimate)")
        
        # Check if data might be too large for some LLMs
        if len(full_text) > 100000:  # ~100KB
            print(f"\n⚠️  Note: This is a large dataset ({len(full_text):,} characters)")
            print("   Some LLMs may have token limits. Consider:")
            print("   - Using a recent time period only")
            print("   - Breaking into smaller chunks")
            print("   - Using a model with higher token limits (like GPT-4)")
    else:
        print("\n❌ Failed to copy to clipboard")
        print("   You can manually copy the text below:")
        print("=" * 50)
        print(full_text)
        print("=" * 50)

if __name__ == "__main__":
    main() 