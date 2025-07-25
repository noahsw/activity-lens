README

# Focused Window Screenshot Script (macOS)

## Setup Instructions

1. **Create and activate a virtual environment:**
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

3. **Install Tesseract OCR (required for OCR extraction):**
   ```sh
   brew install tesseract
   ```

## When changing buckets.yml
  ```sh
  python build-centroids.py
  ```


## Run the Script

- To capture the focused window every 5 seconds:
  ```sh
  python screen-capture.py
  ```

- To capture a single screenshot (edit the script to uncomment the relevant line):
  ```sh
  python screen-capture.py
  ```

# Activity Lens OCR & Classification

## Requirements
- Python 3.11.x (required for macOS accessibility APIs; see .python-version)
- Install dependencies:
  ```sh
  pip install -r requirements.txt
  ```
- Ensure you have Tesseract OCR installed on your system for pytesseract to work.

## Usage

### 1. Extract OCR from Screenshots
Extract text from all PNG screenshots in the `screen-captures/` directory and save the results to `screen_captures_ocr.json`:

  ```sh
  python ocr_extract.py
  ```

This will create or overwrite `screen_captures_ocr.json` with OCR results for each image, including filename, app name, timestamp, and extracted text.

### 2. Classify OCR Entries
Classify each entry in the OCR JSON using the precomputed centroids and FAISS index:

  ```sh
  python classify_ocr_json.py
  ```

- This script loads `screen_captures_ocr.json`.
- Uses `bucket_ids.npy` and `bucket_index.faiss` for classification.
- Adds a `classification` field to each entry based on sentence embedding similarity.
- **Updates the original `screen_captures_ocr.json` file inline** (no new file is created).
- If an entry does not meet the similarity threshold, it will be marked as `"unclassified"`.

---

For questions or issues, please refer to the code comments or open an issue.

from Quartz import AXUIElementCreateApplication, AXUIElementCopyAttributeValue, kAXRoleAttribute, kAXChildrenAttribute, kAXValueAttribute

