import os
import json
from datetime import datetime, timedelta
from PIL import Image
import pytesseract
import re
import requests
import time
import hashlib

# Paths
CACHE_DIR = os.path.expanduser('~/Library/Caches/activity-lens')
input_dir = os.path.join(CACHE_DIR, 'screen-captures')
output_json = os.path.join(CACHE_DIR, 'screen_captures_ocr.json')
prompt_file = os.path.join(os.path.dirname(__file__), 'summarize_prompt.txt')
summary_cache_file = os.path.join(CACHE_DIR, 'summary_cache.json')

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

# Load summary cache
def load_summary_cache():
    """Load the summary cache from file."""
    if os.path.exists(summary_cache_file):
        try:
            with open(summary_cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}

def save_summary_cache(cache):
    """Save the summary cache to file."""
    try:
        with open(summary_cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Could not save summary cache: {e}")

def get_content_hash(text_content):
    """Generate a hash for the text content."""
    return hashlib.md5(text_content.encode('utf-8')).hexdigest()

# Load the cache
summary_cache = load_summary_cache()
print(f"Loaded summary cache with {len(summary_cache)} entries")

# Function to call Ollama for summarization
def summarize_with_ollama(text_content, app_name="", window_title=""):
    """Call Ollama API to summarize the given text."""
    # Check cache first
    content_hash = get_content_hash(text_content)
    if content_hash in summary_cache:
        print(f"  Using cached summary (hash: {content_hash[:8]}...)")
        return summary_cache[content_hash]
    
    try:
        # Load the prompt template
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_template = f.read().strip()
        
        # Construct the full prompt with context
        context_info = f"Application: {app_name}"
        if window_title:
            context_info += f"\nWindow Title: {window_title}"
        
        full_prompt = f"{prompt_template}:\n\n{context_info}\n\nScreen Contents:\n{text_content}"
        
        # Call Ollama API
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'llama3.2',  # You can change this to your preferred model
                'prompt': full_prompt,
                'stream': False,
                'options': {
                    'num_ctx': 8192 * 2,  # Use 16k context window (more reasonable)
                    'num_predict': 100, # Limit output length
                    'temperature': 0
                }
            },
            timeout=60  # Increase timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            summary = result.get('response', '').strip()
            
            # Cache the result
            summary_cache[content_hash] = summary
            save_summary_cache(summary_cache)
            
            return summary
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

# Estimate processing time (rough estimates: OCR ~5s, summarization ~10s per entry)
estimated_ocr_time = sum(1 for _, needs_ocr, _ in entries_to_process if needs_ocr) * 5
estimated_summary_time = sum(1 for _, _, needs_summary in entries_to_process if needs_summary) * 10
total_estimated_seconds = estimated_ocr_time + estimated_summary_time

if total_estimated_seconds > 0:
    estimated_time = timedelta(seconds=total_estimated_seconds)
    print(f"Estimated processing time: {estimated_time}")
    print(f"  - OCR operations: {sum(1 for _, needs_ocr, _ in entries_to_process if needs_ocr)} entries (~{timedelta(seconds=estimated_ocr_time)})")
    print(f"  - Summarization operations: {sum(1 for _, _, needs_summary in entries_to_process if needs_summary)} entries (~{timedelta(seconds=estimated_summary_time)})")

start_time = time.time()

# Process each entry completely (OCR + summarization in one pass)
for idx, (entry, needs_ocr, needs_summary) in enumerate(entries_to_process, 1):
    # Get the appropriate filename for display
    display_filename = entry.get('screen_capture_filename', entry.get('screen_text_filename', 'Unknown'))
    print(f"\nProcessing {idx}/{len(entries_to_process)}: {display_filename}")
    
    # Step 1: OCR if needed
    if needs_ocr:
        print("  Step 1: Running OCR...")
        filename = entry['screen_capture_filename']
        
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
            summary = summarize_with_ollama(text_content, entry.get('app_name', ''), entry.get('window_title', ''))
            
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
    
    # Show progress and time remaining
    elapsed_time = time.time() - start_time
    avg_time_per_entry = elapsed_time / idx
    remaining_entries = len(entries_to_process) - idx
    estimated_remaining = timedelta(seconds=int(avg_time_per_entry * remaining_entries))
    
    print(f"  Progress: {idx}/{len(entries_to_process)} entries processed")
    print(f"  Elapsed time: {timedelta(seconds=int(elapsed_time))}")
    print(f"  Estimated time remaining: {estimated_remaining}")

print(f"\nAnalysis complete! Total time: {timedelta(seconds=int(time.time() - start_time))}") 