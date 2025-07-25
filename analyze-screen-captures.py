import os
import json
from datetime import datetime
from PIL import Image
import pytesseract
import re
import requests

# Paths
CACHE_DIR = os.path.expanduser('~/Library/Caches/activity-lens')
input_dir = os.path.join(CACHE_DIR, 'screen-captures')
output_json = os.path.join(CACHE_DIR, 'screen_captures_ocr.json')
prompt_file = os.path.join(os.path.dirname(__file__), 'summarize_prompt.txt')

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

# Function to call Ollama for summarization
def summarize_with_ollama(text_content):
    """Call Ollama API to summarize the given text."""
    try:
        # Load the prompt template
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_template = f.read().strip()
        
        # Construct the full prompt
        full_prompt = f"{prompt_template}:\n\n{text_content}"
        
        # Call Ollama API
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'llama3.2',  # You can change this to your preferred model
                'prompt': full_prompt,
                'stream': False
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', '').strip()
        else:
            print(f"Ollama API error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return None

# Find entries that need processing (either OCR, summarization, or both)
entries_to_process = []
for entry in existing_data:
    needs_ocr = 'screen_capture_filename' in entry and 'screen_text_filename' not in entry
    needs_summary = 'screen_text_filename' in entry and 'summary' not in entry
    
    if needs_ocr or needs_summary:
        entries_to_process.append((entry, needs_ocr, needs_summary))

if not entries_to_process:
    print("No entries need processing.")
    exit()

print(f"Found {len(entries_to_process)} entries to process")

# Process each entry completely (OCR + summarization in one pass)
for idx, (entry, needs_ocr, needs_summary) in enumerate(entries_to_process, 1):
    filename = entry['screen_capture_filename']
    print(f"\nProcessing {idx}/{len(entries_to_process)}: {filename}")
    
    # Step 1: OCR if needed
    if needs_ocr:
        print("  Step 1: Running OCR...")
        filepath = os.path.join(input_dir, filename)
        
        # Check if the PNG file actually exists
        if not os.path.exists(filepath):
            print(f"  Warning: PNG file {filename} not found, skipping...")
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
            
            print(f"  OCR text saved to: {text_filename}")
            
            # Update the existing entry with the text filename
            entry['screen_text_filename'] = text_filename
            
        except Exception as e:
            print(f"  Error during OCR: {e}")
            continue
    
    # Step 2: Summarization if needed
    if needs_summary:
        print("  Step 2: Running summarization...")
        text_filename = entry['screen_text_filename']
        text_filepath = os.path.join(input_dir, text_filename)
        
        # Check if the text file actually exists
        if not os.path.exists(text_filepath):
            print(f"  Warning: Text file {text_filename} not found, skipping...")
            continue
        
        try:
            # Read the text content
            with open(text_filepath, 'r', encoding='utf-8') as tf:
                text_content = tf.read().strip()
            
            if not text_content:
                print(f"  Warning: Text file {text_filename} is empty, skipping...")
                continue
            
            # Get summary from Ollama
            summary = summarize_with_ollama(text_content)
            
            if summary:
                print(f"  Summary: {summary}")
                
                # Update the existing entry with the summary
                entry['summary'] = summary
            else:
                print(f"  Failed to get summary for {text_filename}")
                continue
            
        except Exception as e:
            print(f"  Error during summarization: {e}")
            continue
    
    # Save progress after each complete file processing
    try:
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        print(f"  Progress saved to {output_json}")
    except Exception as e:
        print(f"  Error saving progress: {e}")

print("\nAnalysis complete!") 