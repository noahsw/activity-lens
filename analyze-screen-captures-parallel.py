#!/usr/bin/env python3
"""
Parallel Screen Capture Analysis
- OCR processing runs in parallel across multiple cores
- Summarization runs with limited concurrency to avoid API overload
"""

import os
import json
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from PIL import Image
import pytesseract
import multiprocessing

# Try to import psutil, but make it optional
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available, memory monitoring disabled")

# Paths
CACHE_DIR = os.path.expanduser('~/Library/Caches/activity-lens')
input_dir = os.path.join(CACHE_DIR, 'screen-captures')
output_json = os.path.join(CACHE_DIR, 'screen_captures_ocr.json')
prompt_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'summarize_screen_text_prompt.txt')
summary_cache_file = os.path.join(CACHE_DIR, 'summary_cache.json')

# Configuration - Adaptive based on system capabilities
MAX_OCR_WORKERS = min(4, multiprocessing.cpu_count())
MAX_SUMMARY_WORKERS = min(2, max(1, MAX_OCR_WORKERS // 2))
BATCH_SIZE = 10  # Process in smaller batches to reduce memory pressure
SUMMARY_SEMAPHORE = threading.Semaphore(MAX_SUMMARY_WORKERS)  # Control summarization concurrency
SAVE_LOCK = threading.Lock()  # Prevent concurrent file saves

# Progress tracking
progress_lock = threading.Lock()
ocr_completed = 0
summary_completed = 0
start_time = None

# Load existing JSON data
try:
    with open(output_json, 'r', encoding='utf-8') as f:
        existing_data = json.load(f)
    print(f"Loaded {len(existing_data)} existing entries from {output_json}")
except FileNotFoundError:
    existing_data = []
    print(f"No existing data found, starting fresh")

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
    """Thread-safe function to save summary cache."""
    with SAVE_LOCK:
        try:
            # Ensure cache directory exists
            os.makedirs(os.path.dirname(summary_cache_file), exist_ok=True)
            with open(summary_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save summary cache: {e}")

def save_progress_safe(data):
    """Thread-safe function to save progress to JSON file."""
    with SAVE_LOCK:
        try:
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"  Warning: Could not save progress: {e}")
            return False

def check_memory_usage():
    """Check current memory usage and warn if too high."""
    if not PSUTIL_AVAILABLE:
        return True  # Skip memory checks if psutil not available
    
    try:
        memory = psutil.virtual_memory()
        if memory.percent > 95:  # Only stop at 95% (much more reasonable)
            print(f"⚠️  Very high memory usage: {memory.percent:.1f}%")
            return False
        elif memory.percent > 85:
            print(f"⚠️  High memory usage: {memory.percent:.1f}%")
        elif memory.percent > 75:
            print(f"⚠️  Elevated memory usage: {memory.percent:.1f}%")
        return True
    except Exception:
        return True  # Continue if we can't check memory

def log_progress(phase, completed, total, start_time):
    """Log progress with rate and ETA calculations."""
    if start_time is None:
        return
    
    elapsed = time.time() - start_time
    if elapsed > 0:
        rate = completed / elapsed
        eta = (total - completed) / rate if rate > 0 else 0
        print(f"  {phase}: {completed}/{total} ({rate:.1f}/s, ETA: {timedelta(seconds=int(eta))})")

def process_with_retry(func, *args, max_retries=3):
    """Execute function with retry logic and exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func(*args)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            wait_time = 1 * (2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
            print(f"  Retry {attempt + 1}/{max_retries} in {wait_time}s: {e}")
            time.sleep(wait_time)

def get_content_hash(text_content):
    """Generate a hash of the text content for caching."""
    import hashlib
    return hashlib.md5(text_content.encode('utf-8')).hexdigest()

def check_ollama_status():
    """Check if Ollama is running and what models are available."""
    try:
        import requests
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            available_models = [model['name'] for model in models]
            print(f"Available Ollama models: {available_models}")
            return available_models
        else:
            print(f"Ollama API error: {response.status_code}")
            return []
    except Exception as e:
        print(f"Ollama not running or not accessible: {e}")
        return []

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
    
    # Construct the full prompt with context (like original)
    context_info = f"Application: {app_name}"
    if window_title:
        context_info += f"\nWindow Title: {window_title}"
    
    prompt = f"{prompt_template}:\n\n{context_info}\n\nScreen Contents:\n{text_content}"
    
    try:
        import requests
        
        # Use the model passed in (checked once at startup)
        if not model_to_use:
            print("  No model available, skipping summarization")
            return None
        
        # Call Ollama API with optimized settings
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': model_to_use,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'num_ctx': 8192 * 2,  # Use 16k context window
                    'num_predict': 100,   # Limit output length
                    'temperature': 0      # Deterministic output
                }
            },
            timeout=60  # Increased timeout for longer prompts
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

def process_ocr(entry):
    """Process OCR for a single entry - can run in parallel."""
    global ocr_completed
    
    filename = entry['screen_capture_filename']
    filepath = os.path.join(input_dir, filename)
    
    # Check if the PNG file actually exists
    if not os.path.exists(filepath):
        print(f"  Warning: PNG file {filename} not found, skipping...")
        return entry, False
    
    try:
        # Check memory usage before processing
        if not check_memory_usage():
            print(f"  Skipping {filename} due to high memory usage")
            return entry, False
        
        # Load and optimize image for OCR with retry logic
        def load_and_process_image():
            image = Image.open(filepath)
            if image.mode != 'L':
                image = image.convert('L')
            return image
        
        image = process_with_retry(load_and_process_image)
        
        # Use pytesseract with optimized settings for maximum accuracy
        def perform_ocr():
            return pytesseract.image_to_string(
                image, 
                config='--psm 6 --oem 3 --dpi 600'
            )
        
        full_text = process_with_retry(perform_ocr)
        
        print(f"  OCR completed for {filename}: {len(full_text)} characters extracted")
        
        # Create text filename by replacing .png with .txt
        text_filename = filename.replace('.png', '.txt')
        text_filepath = os.path.join(input_dir, text_filename)
        
        # Save OCR text to separate .txt file
        with open(text_filepath, 'w', encoding='utf-8') as tf:
            tf.write(full_text.strip())
        
        print(f"  OCR text saved to: {text_filename}")
        
        # Update the entry with the text filename
        entry['screen_text_filename'] = text_filename
        
        # Update progress counter
        with progress_lock:
            global ocr_completed
            ocr_completed += 1
        
        return entry, True
        
    except Exception as e:
        print(f"  Error during OCR for {filename}: {e}")
        return entry, False

def process_summarization(entry, model_to_use=None):
    """Process summarization for a single entry - limited concurrency."""
    global summary_completed
    
    with SUMMARY_SEMAPHORE:  # Limit concurrent summarization requests
        text_filename = entry['screen_text_filename']
        text_filepath = os.path.join(input_dir, text_filename)
        
        # Check if the text file actually exists
        if not os.path.exists(text_filepath):
            print(f"  Warning: Text file {text_filename} not found, skipping...")
            return entry, False
        
        try:
            # Check memory usage before processing
            if not check_memory_usage():
                print(f"  Skipping {text_filename} due to high memory usage")
                return entry, False
            
            # Read the text content with retry logic
            def read_text_file():
                with open(text_filepath, 'r', encoding='utf-8') as tf:
                    return tf.read().strip()
            
            text_content = process_with_retry(read_text_file)
            
            if not text_content:
                print(f"  Warning: Text file {text_filename} is empty, skipping...")
                return entry, False
            
            # Check if text is too long for model context
            if len(text_content) > 15000:  # Conservative limit for 16k context
                print(f"  Warning: Text too long ({len(text_content)} chars), truncating for {text_filename}")
                text_content = text_content[:15000]
            
            # Get summary from Ollama with retry logic
            def get_summary():
                return summarize_with_ollama(text_content, entry.get('app_name', ''), entry.get('window_title', ''), model_to_use)
            
            summary = process_with_retry(get_summary)
            
            if summary:
                print(f"  Summary for {text_filename}: {summary}")
                
                # Update the entry with the summary
                entry['summary'] = summary
                
                # Update progress counter
                with progress_lock:
                    global summary_completed
                    summary_completed += 1
                
                return entry, True
            else:
                print(f"  Failed to get summary for {text_filename}")
                return entry, False
            
        except Exception as e:
            print(f"  Error during summarization for {text_filename}: {e}")
            return entry, False

# Find entries that need processing
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

# Count operations for time estimation
ocr_entries = [(entry, needs_ocr, needs_summary) for entry, needs_ocr, needs_summary in entries_to_process if needs_ocr]
summary_entries = [(entry, needs_ocr, needs_summary) for entry, needs_ocr, needs_summary in entries_to_process if needs_summary]

print(f"  - OCR operations: {len(ocr_entries)} entries")
print(f"  - Summarization operations: {len(summary_entries)} entries")
print(f"  - OCR workers: {MAX_OCR_WORKERS} (adaptive based on {multiprocessing.cpu_count()} CPU cores)")
print(f"  - Summary workers: {MAX_SUMMARY_WORKERS}")
print(f"  - Batch size: {BATCH_SIZE}")

# Check system resources
print(f"\nSystem check:")
if PSUTIL_AVAILABLE:
    memory = psutil.virtual_memory()
    print(f"  Memory: {memory.percent:.1f}% used ({memory.available / (1024**3):.1f} GB available)")
else:
    print(f"  Memory: Monitoring disabled (psutil not available)")
cpu_count = multiprocessing.cpu_count()
print(f"  CPU cores: {cpu_count}")

# Check Ollama availability and select model once at startup
selected_model = None
if summary_entries:
    print(f"\nChecking Ollama availability...")
    available_models = check_ollama_status()
    if not available_models:
        print("⚠️  Ollama not available - summarization will be skipped")
        print("   To enable summarization:")
        print("   1. Install Ollama: https://ollama.ai")
        print("   2. Pull a model: ollama pull llama3.2:3b")
        print("   3. Start Ollama: ollama serve")
    else:
        # Try to find a suitable model
        preferred_models = ['llama3.2:3b', 'llama3.2', 'llama3', 'llama2', 'mistral']
        for preferred in preferred_models:
            if any(preferred in model for model in available_models):
                selected_model = preferred
                break
        
        if not selected_model:
            selected_model = available_models[0]  # Use first available model
        
        print(f"✓ Selected Ollama model: {selected_model}")
        ollama_available = True
else:
    ollama_available = False

start_time = time.time()

# Phase 1: Parallel OCR processing
if ocr_entries:
    print(f"\n=== Phase 1: Parallel OCR Processing ===")
    
    # Process in batches to manage memory
    for batch_start in range(0, len(ocr_entries), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(ocr_entries))
        batch = ocr_entries[batch_start:batch_end]
        
        print(f"\nProcessing OCR batch {batch_start//BATCH_SIZE + 1}/{(len(ocr_entries) + BATCH_SIZE - 1)//BATCH_SIZE}")
        print(f"  Batch size: {len(batch)} entries")
        
        # Check memory before starting batch
        if not check_memory_usage():
            print("  ⚠️  High memory usage, waiting before continuing...")
            time.sleep(5)
        
        with ThreadPoolExecutor(max_workers=MAX_OCR_WORKERS) as executor:
            # Submit OCR tasks for this batch
            future_to_entry = {}
            for entry_tuple in batch:
                entry, needs_ocr, needs_summary = entry_tuple
                future = executor.submit(process_ocr, entry)
                future_to_entry[future] = entry_tuple
            
            # Process completed OCR tasks
            for future in as_completed(future_to_entry):
                entry_tuple = future_to_entry[future]
                original_entry = entry_tuple[0]  # Get just the entry from the tuple
                
                try:
                    updated_entry, success = future.result()
                    
                    # Update the entry in the main list
                    for i, main_entry in enumerate(existing_data):
                        if main_entry.get('screen_capture_filename') == updated_entry.get('screen_capture_filename'):
                            existing_data[i] = updated_entry
                            break
                    
                    if success:
                        print(f"  ✓ OCR completed for {updated_entry.get('screen_capture_filename')}")
                    else:
                        print(f"  ✗ OCR failed for {updated_entry.get('screen_capture_filename')}")
                    
                    # Save progress after each OCR completion (thread-safe)
                    save_progress_safe(existing_data)
                    
                    # Log progress
                    log_progress("OCR", ocr_completed, len(ocr_entries), start_time)
                        
                except Exception as e:
                    print(f"  ✗ OCR exception for {original_entry.get('screen_capture_filename')}: {e}")
        
        # Small delay between batches to allow memory cleanup
        if batch_end < len(ocr_entries):
            time.sleep(1)

# Phase 2: Limited parallel summarization
if summary_entries and ollama_available:
    print(f"\n=== Phase 2: Limited Parallel Summarization ===")
    
    # Process in batches to manage memory and API load
    for batch_start in range(0, len(summary_entries), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(summary_entries))
        batch = summary_entries[batch_start:batch_end]
        
        print(f"\nProcessing Summary batch {batch_start//BATCH_SIZE + 1}/{(len(summary_entries) + BATCH_SIZE - 1)//BATCH_SIZE}")
        print(f"  Batch size: {len(batch)} entries")
        
        # Check memory before starting batch
        if not check_memory_usage():
            print("  ⚠️  High memory usage, waiting before continuing...")
            time.sleep(5)
        
        with ThreadPoolExecutor(max_workers=MAX_SUMMARY_WORKERS) as executor:
            # Submit summarization tasks for this batch
            future_to_entry = {}
            for entry_tuple in batch:
                entry, needs_ocr, needs_summary = entry_tuple
                future = executor.submit(process_summarization, entry, selected_model)
                future_to_entry[future] = entry_tuple
            
            # Process completed summarization tasks
            for future in as_completed(future_to_entry):
                entry_tuple = future_to_entry[future]
                original_entry = entry_tuple[0]  # Get just the entry from the tuple
                
                try:
                    updated_entry, success = future.result()
                    
                    # Update the entry in the main list
                    for i, main_entry in enumerate(existing_data):
                        if main_entry.get('screen_text_filename') == updated_entry.get('screen_text_filename'):
                            existing_data[i] = updated_entry
                            break
                    
                    if success:
                        print(f"  ✓ Summary completed for {updated_entry.get('screen_text_filename')}")
                    else:
                        print(f"  ✗ Summary failed for {updated_entry.get('screen_text_filename')}")
                    
                    # Save progress after each summary completion (thread-safe)
                    save_progress_safe(existing_data)
                    
                    # Log progress
                    log_progress("Summary", summary_completed, len(summary_entries), start_time)
                        
                except Exception as e:
                    print(f"  ✗ Summary exception for {original_entry.get('screen_text_filename')}: {e}")
        
        # Small delay between batches to allow memory cleanup and reduce API load
        if batch_end < len(summary_entries):
            time.sleep(2)

# Save final results
try:
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Results saved to {output_json}")
except Exception as e:
    print(f"\n✗ Error saving results: {e}")

total_time = time.time() - start_time
print(f"\n=== Analysis Complete ===")
print(f"Total time: {timedelta(seconds=int(total_time))}")
print(f"Average time per entry: {total_time/len(entries_to_process):.2f}s")
print(f"OCR completed: {ocr_completed}/{len(ocr_entries) if ocr_entries else 0}")
print(f"Summaries completed: {summary_completed}/{len(summary_entries) if summary_entries else 0}")

# Final system check
if PSUTIL_AVAILABLE:
    final_memory = psutil.virtual_memory()
    print(f"Final memory usage: {final_memory.percent:.1f}%")
else:
    print("Final memory usage: Monitoring disabled") 