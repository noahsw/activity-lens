import os
import json
from datetime import datetime
from PIL import Image
import pytesseract
import re

# Paths
CACHE_DIR = os.path.expanduser('~/Library/Caches/activity-lens')
input_dir = os.path.join(CACHE_DIR, 'screen-captures')
output_json = os.path.join(CACHE_DIR, 'screen_captures_ocr.json')

# Load existing JSON data
if not os.path.exists(output_json):
    print(f"JSON file {output_json} not found. Nothing to process.")
    exit()

try:
    with open(output_json, 'r', encoding='utf-8') as f:
        existing_data = json.load(f)
except (json.JSONDecodeError, FileNotFoundError) as e:
    print(f"Error reading JSON file: {e}")
    exit()

# Find entries that don't have screen_text_filename (haven't been OCR'd yet)
entries_to_process = []
for entry in existing_data:
    if 'screen_capture_filename' in entry and 'screen_text_filename' not in entry:
        entries_to_process.append(entry)

if not entries_to_process:
    print("No new entries to process with OCR.")
    exit()

print(f"Found {len(entries_to_process)} entries to process with OCR")

# Process each entry that needs OCR
for idx, entry in enumerate(entries_to_process, 1):
    filename = entry['screen_capture_filename']
    print(f"Processing {idx}/{len(entries_to_process)}: {filename}")
    
    filepath = os.path.join(input_dir, filename)
    
    # Check if the PNG file actually exists
    if not os.path.exists(filepath):
        print(f"Warning: PNG file {filename} not found, skipping...")
        continue
    
    try:
        # OCR extraction
        image = Image.open(filepath)
        full_text = pytesseract.image_to_string(image)
        
        # Create text filename by replacing .png with .txt
        text_filename = filename.replace('.png', '.txt')
        text_filepath = os.path.join(input_dir, text_filename)
        
        # Save OCR text to separate .txt file
        with open(text_filepath, 'w', encoding='utf-8') as tf:
            tf.write(full_text.strip())
        
        print(f"OCR text saved to: {text_filename}")
        
        # Update the existing entry with the text filename
        entry['screen_text_filename'] = text_filename
        
        # Save the updated JSON after each successful operation
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        
        print(f"Progress saved to {output_json}")
        
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        continue

print(f"OCR extraction complete. Results saved to {output_json}") 