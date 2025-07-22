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

ocr_results = []

image_files = [f for f in sorted(os.listdir(input_dir)) if f.lower().endswith('.png')]
total = len(image_files)

for idx, filename in enumerate(image_files, 1):
    print(f"Processing {idx}/{total}: {filename}")
    filepath = os.path.join(input_dir, filename)
    app_name = filename.split('_focused_window_')[0]
    # Extract timestamp from filename using regex
    match = re.search(r'(\d{8})[_]?(\d{6})', filename)
    if match:
        timestamp_str = match.group(1) + match.group(2)
        try:
            timestamp = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
            timestamp_iso = timestamp.isoformat()
        except Exception:
            timestamp_iso = None
    else:
        timestamp_iso = None
    # OCR extraction
    image = Image.open(filepath)
    ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    # Structure: list of lines, each line is a list of words
    lines = {}
    for i, text in enumerate(ocr_data['text']):
        if text.strip():
            line_num = ocr_data['line_num'][i]
            if line_num not in lines:
                lines[line_num] = []
            lines[line_num].append(text)
    structured_text = [' '.join(lines[k]) for k in sorted(lines.keys())]
    ocr_results.append({
        'filename': filename,
        'app_name': app_name,
        'timestamp': timestamp_iso,
        'window_title': None,
        'text_full': '\n'.join(structured_text)
    })

with open(output_json, 'w', encoding='utf-8') as f:
    json.dump(ocr_results, f, indent=2, ensure_ascii=False)

print(f"OCR extraction complete. Results saved to {output_json}") 