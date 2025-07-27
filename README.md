# Activity Lens (macOS)

Activity-Lens ingests screenshots, window titles, and OCR text, then:
1. Classifies every event into customizable activity buckets (coding, email, browsing, shopping…).
2. Aggregates time spent in each bucket with human-friendly charts & CSV exports.
3. Generates daily narratives (“You spent 2 h 17 m coding in Cursor, 45 m shopping on Amazon…”).
4. Runs locally — no data leaves your machine unless you choose to sync.
5. Extensible via Python plug-ins: add new data sources (e.g., browser history) or analytics.

## Setup Instructions

**Prerequisites:**
- Python 3.11 (recommended) - other versions may work but 3.11 is tested
- Homebrew (for installing Tesseract and Ollama)

1. **Create and activate a virtual environment:**
   ```sh
   python3.11 -m venv venv
   source venv/bin/activate
   ```

2. **Install Python dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

3. **Install Tesseract OCR (required for OCR extraction):**
   ```sh
   brew install tesseract
   ```

4. **Install Ollama (required for text summarization):**
   ```sh
   brew install ollama
   ```


## Usage

1. **Capture the focused window every 5 seconds:**
  ```sh
  python screen-capture.py
  ```

2. **Analyze screen captures (OCR + Summarization):**
  In one Terminal:
  ```sh
  ollama serve
  ```

  In another Terminal:
  ```sh
  python analyze-screen-captures.py
  ```

3. **Paste the output of screen_captures_ocr.json into ChatGPT o3 and ask it to summarize my computer activity.**


## Reset Options

The `reset-analysis.py` script allows you to selectively remove analysis data to reprocess specific parts of the pipeline:

### `--text-filename` vs `--text-files`:

**`--text-filename`**
- **Removes the JSON field**: Deletes the `"screen_text_filename"` field from entries in the JSON file
- **Keeps the actual files**: The `.txt` files remain in the `screen-captures` directory
- **Purpose**: Allows you to re-run OCR on entries that already have text files

**`--text-files`** 
- **Removes the actual files**: Deletes the `.txt` files from the `screen-captures` directory
- **Keeps the JSON field**: The `"screen_text_filename"` field remains in the JSON
- **Purpose**: Frees up disk space by removing the text files

### Usage Examples:

```bash
# Remove only summary fields
python reset-analysis.py --summary

# Remove only text filename fields (keeps .txt files)
python reset-analysis.py --text-filename

# Remove only .txt files (keeps JSON fields)
python reset-analysis.py --text-files

# Remove all analysis data
python reset-analysis.py --all

# See what would be removed without doing it
python reset-analysis.py --all --dry-run

# Remove both summary and text filename fields
python reset-analysis.py --summary --text-filename
```

---

For questions or issues, please refer to the code comments or open an issue.