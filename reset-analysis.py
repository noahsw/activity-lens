#!/usr/bin/env python3
"""
Reset script for screen capture analysis data.
Removes specified fields from screen_captures_ocr.json to allow reprocessing.
"""

import os
import json
import argparse
from pathlib import Path

# Paths
CACHE_DIR = os.path.expanduser('~/Library/Caches/activity-lens')

def get_date_paths():
    """Get the current date and return paths with date appended."""
    from datetime import datetime
    current_date = datetime.now().strftime('%Y%m%d')
    output_json = os.path.join(CACHE_DIR, f'screen_captures_ocr-{current_date}.json')
    input_dir = os.path.join(CACHE_DIR, f'screen-captures-{current_date}')
    return output_json, input_dir

# Get current date-based paths
output_json, input_dir = get_date_paths()

def load_json():
    """Load the JSON file or create empty list if it doesn't exist."""
    if not os.path.exists(output_json):
        print(f"JSON file {output_json} not found. Nothing to reset.")
        return []
    
    try:
        with open(output_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, IsADirectoryError) as e:
        print(f"Error reading JSON file: {e}")
        return []

def save_json(data):
    """Save data to JSON file."""
    try:
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Updated JSON saved to {output_json}")
        return True
    except Exception as e:
        print(f"Error saving JSON file: {e}")
        return False

def remove_summary_fields(data):
    """Remove 'activity_summary' field from all entries."""
    count = 0
    for entry in data:
        if 'activity_summary' in entry:
            del entry['activity_summary']
            count += 1
    
    print(f"Removed 'activity_summary' field from {count} entries")
    return count

def remove_text_filename_fields(data):
    """Remove 'screen_text_filename' field from entries that have 'screen_capture_filename'."""
    count = 0
    for entry in data:
        if 'screen_text_filename' in entry and 'screen_capture_filename' in entry:
            del entry['screen_text_filename']
            count += 1
    
    print(f"Removed 'screen_text_filename' field from {count} entries")
    return count

def remove_text_files(data):
    """Remove .txt files that correspond to entries with screen_text_filename."""
    # input_dir is now defined globally with date
    count = 0
    
    for entry in data:
        if 'screen_text_filename' in entry:
            text_filepath = os.path.join(input_dir, entry['screen_text_filename'])
            if os.path.exists(text_filepath):
                try:
                    os.remove(text_filepath)
                    count += 1
                    print(f"Removed text file: {entry['screen_text_filename']}")
                except Exception as e:
                    print(f"Error removing {entry['screen_text_filename']}: {e}")
    
    print(f"Removed {count} text files")
    return count

def main():
    parser = argparse.ArgumentParser(
        description='Reset screen capture analysis data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python reset-analysis.py --summary                    # Remove summary fields
  python reset-analysis.py --text-filename              # Remove screen_text_filename fields
  python reset-analysis.py --text-files                 # Remove .txt files
  python reset-analysis.py --all                        # Remove all analysis data
  python reset-analysis.py --summary --text-filename    # Remove both fields
        """
    )
    
    parser.add_argument('--summary', action='store_true',
                       help='Remove "activity_summary" field from all entries')
    parser.add_argument('--text-filename', action='store_true',
                       help='Remove "screen_text_filename" field from entries')
    parser.add_argument('--text-files', action='store_true',
                       help='Remove .txt files from screen-captures directory')
    parser.add_argument('--all', action='store_true',
                       help='Remove all analysis data (summary, text_filename, and text files)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be removed without actually doing it')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompt (use with caution)')
    
    args = parser.parse_args()
    
    # If no arguments provided, show help
    if not any([args.summary, args.text_filename, args.text_files, args.all]):
        parser.print_help()
        return
    
    # Load the JSON data
    data = load_json()
    if not data:
        return
    
    print(f"Loaded {len(data)} entries from {output_json}")
    
    # Track what would be removed
    summary_count = 0
    text_filename_count = 0
    text_files_count = 0
    
    if args.all or args.summary:
        summary_count = sum(1 for entry in data if 'activity_summary' in entry)
    
    if args.all or args.text_filename:
        text_filename_count = sum(1 for entry in data if 'screen_text_filename' in entry and 'screen_capture_filename' in entry)
    
    if args.all or args.text_files:
        input_dir = os.path.join(CACHE_DIR, 'screen-captures')
        text_files_count = sum(1 for entry in data if 'screen_text_filename' in entry and 
                              os.path.exists(os.path.join(input_dir, entry['screen_text_filename'])))
    
    # Show what would be removed
    print(f"\nWould remove:")
    if summary_count > 0:
        print(f"  - {summary_count} summary fields")
    if text_filename_count > 0:
        print(f"  - {text_filename_count} screen_text_filename fields")
    if text_files_count > 0:
        print(f"  - {text_files_count} text files")
    
    if summary_count == 0 and text_filename_count == 0 and text_files_count == 0:
        print("  Nothing to remove!")
        return
    
    # Confirm action
    if not args.dry_run and not args.force:
        response = input("\nProceed? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("Operation cancelled.")
            return
    
    # Perform the removals
    if args.dry_run:
        print("\nDRY RUN - No changes made")
        return
    
    print("\nPerforming removals...")
    
    if args.all or args.summary:
        remove_summary_fields(data)
    
    if args.all or args.text_filename:
        remove_text_filename_fields(data)
    
    if args.all or args.text_files:
        remove_text_files(data)
    
    # Save the updated JSON
    if args.all or args.summary or args.text_filename:
        if save_json(data):
            print("Reset completed successfully!")
        else:
            print("Reset completed but failed to save JSON file!")

if __name__ == "__main__":
    main() 