#!/usr/bin/env python3
"""
Screen Capture Analysis
- OCR processing for extracted text
- Summarization using Ollama API
- Progress tracking and caching
"""

import os
import json
import time
from datetime import datetime, timedelta
from PIL import Image
import pytesseract
import requests

# Paths
CACHE_DIR = os.path.expanduser('~/Library/Caches/activity-lens')
input_dir = os.path.join(CACHE_DIR, 'screen-captures')
output_json = os.path.join(CACHE_DIR, 'screen_captures_ocr.json')
prompt_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'summarize_screen_text_prompt.txt')
summary_cache_file = os.path.join(CACHE_DIR, 'summary_cache.json')

# Global variable for existing data (will be loaded in main function)
existing_data = []

# Load summary cache
def load_summary_cache():
    try:
        with open(summary_cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Create empty cache file if it doesn't exist
        try:
            # Ensure cache directory exists
            os.makedirs(os.path.dirname(summary_cache_file), exist_ok=True)
            # Create empty cache file
            with open(summary_cache_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            print(f"Created new summary cache file: {summary_cache_file}")
            return {}
        except Exception as e:
            print(f"Warning: Could not create summary cache file: {e}")
            return {}
    except json.JSONDecodeError as e:
        print(f"Warning: Corrupted summary cache file, starting fresh: {e}")
        # Backup the corrupted file
        import shutil
        backup_file = summary_cache_file + '.backup'
        try:
            shutil.copy2(summary_cache_file, backup_file)
            print(f"Backed up corrupted cache to: {backup_file}")
        except:
            pass
        return {}

def save_summary_cache(cache):
    """Save summary cache to file."""
    try:
        # Ensure cache directory exists
        os.makedirs(os.path.dirname(summary_cache_file), exist_ok=True)
        with open(summary_cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Could not save summary cache: {e}")

def get_content_hash(text_content):
    """Generate a hash of the text content for caching."""
    import hashlib
    return hashlib.md5(text_content.encode('utf-8')).hexdigest()

def summarize_with_ollama(text_content, app_name="", window_title="", model_to_use=None):
    """Summarize text using Ollama API with caching."""
    # Load cache
    summary_cache = load_summary_cache()
    
    # Check cache first
    content_hash = get_content_hash(text_content)
    if content_hash in summary_cache:
        print(f"  Using cached summary for {content_hash[:8]}...")
        return summary_cache[content_hash]
    
    # Load prompt template
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_template = f.read().strip()
    except FileNotFoundError:
        prompt_template = "Summarize this text in 1-2 sentences: {text}"
    
    # Construct the full prompt with context
    context_info = f"Application: {app_name}"
    if window_title:
        context_info += f"\nWindow Title: {window_title}"
    
    prompt = f"{prompt_template}:\n\n{context_info}\n\nScreen Contents:\n{text_content}"
    
    try:
        # Use the model passed in (checked once at startup)
        if not model_to_use:
            print("  No model available, skipping summarization")
            return None
        
        # Call Ollama API
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': model_to_use,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'num_ctx': 8192 * 2,  # Use 16k context window
                    'num_predict': 100,
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
            print(f"  Ollama API error: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"  Error calling Ollama: {e}")
        return None

def main():
    """Main execution function."""
    global existing_data
    
    # Load existing JSON data
    try:
        with open(output_json, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        print(f"Loaded {len(existing_data)} existing entries from {output_json}")
    except FileNotFoundError:
        existing_data = []
        print(f"No existing data found, starting fresh")
    
    # Load summary cache
    summary_cache = load_summary_cache()
    print(f"Loaded summary cache with {len(summary_cache)} entries")
    
    # Find entries that need processing
    entries_to_process = []
    for entry in existing_data:
        needs_ocr = 'screen_capture_filename' in entry and 'screen_text_filename' not in entry
        needs_summary = 'screen_text_filename' in entry and 'activity_summary' not in entry
        
        if needs_ocr or needs_summary:
            entries_to_process.append((entry, needs_ocr, needs_summary))
    
    if not entries_to_process:
        print("No entries need processing.")
        return
    
    print(f"Found {len(entries_to_process)} entries to process")
    
    # Estimate processing time
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
        print(f"  Needs OCR: {needs_ocr} | Needs Summary: {needs_summary}")
        
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
                # Load and optimize image for OCR
                image = Image.open(filepath)
                
                # Convert to grayscale for better OCR
                if image.mode != 'L':
                    image = image.convert('L')
                
                # Use pytesseract with optimized settings for maximum accuracy
                full_text = pytesseract.image_to_string(
                    image, 
                    config='--psm 6 --oem 3 --dpi 600'
                )
                
                print(f"  OCR completed: {len(full_text)} characters extracted")
                
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
        
        # Re-evaluate if summarization is needed (in case OCR just created the text file)
        if not needs_summary and 'screen_text_filename' in entry and 'summary' not in entry:
            needs_summary = True
            print(f"  Updated: Now needs summarization (OCR created text file)")
        
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
                    entry['activity_summary'] = summary
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

if __name__ == '__main__':
    main() 