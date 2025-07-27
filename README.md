# Activity Lens (macOS)

Activity-Lens ingests screenshots, window titles, and OCR text, then:
1. Classifies every event into customizable activity buckets (coding, email, browsing, shopping…).
2. Aggregates time spent in each bucket with human-friendly charts & CSV exports.
3. Generates daily narratives (“You spent 2 h 17 m coding in Cursor, 45 m shopping on Amazon…”).
4. Runs locally — no data leaves your machine unless you choose to sync.
5. Extensible via Python plug-ins: add new data sources (e.g., browser history) or analytics.

## Setup Instructions

**Prerequisites:**
- Python 3.12 (recommended) - other versions may work but 3.12 is tested
- Homebrew (for installing Tesseract and Ollama)

1. **Create and activate a virtual environment:**
   ```sh
   /opt/homebrew/opt/python@3.12/bin/python3.12 -m venv venv
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

3. **Analyze your activity patterns and get AI outsourcing suggestions:**
   ```sh
   python prepare_activity_analysis.py
   ```
   This will:
   - Load your activity data and analysis prompt
   - Format it for LLM analysis
   - Copy everything to your clipboard
   - Provide instructions for pasting into ChatGPT, Claude, or other LLMs
   - Get insights on time usage and AI outsourcing opportunities


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

## Activity Analysis & AI Outsourcing

### **Automated Activity Analysis**
The `prepare_activity_analysis.py` script provides a streamlined way to analyze your computer activity patterns and identify AI outsourcing opportunities:

**What it does:**
- 📊 **Loads your activity data** from screen captures and summaries
- 📝 **Applies analysis prompt** designed for productivity insights
- 📋 **Formats for LLM consumption** with clean, structured data
- 🎯 **Copies to clipboard** for easy pasting into any LLM
- 📈 **Provides data summary** including token estimates

**Sample output:**
```
🔍 Preparing Activity Analysis for LLM
==================================================
📝 Loading analysis prompt...
📊 Loading activity data...
   Found 85 activity entries
📋 Formatting data...
📋 Copying to clipboard...
✅ Successfully copied to clipboard!

🎯 Next Steps:
1. Open your favorite LLM (ChatGPT, Claude, etc.)
2. Paste the content (Cmd+V on Mac, Ctrl+V on Windows)
3. Ask the LLM to analyze your activity patterns
4. Get insights on time usage and AI outsourcing opportunities!

📊 Data Summary:
   - Total entries: 85
   - Total characters: 14,150
   - Estimated tokens: 3,537 (rough estimate)
```

**Analysis includes:**
- ⏰ **Time tracking** - How much time spent on each activity
- 🎯 **Theme identification** - Grouping activities into meaningful categories
- 🤖 **AI outsourcing suggestions** - Low-ROI activities that could be automated
- 📈 **Productivity insights** - Patterns and optimization opportunities

### **Customizing Analysis**
You can modify the analysis prompt in `analyze_activity_prompt.txt` to focus on specific aspects:
- Time management patterns
- Focus vs. distraction analysis
- Project-specific productivity
- Work-life balance insights

---

For questions or issues, please refer to the code comments or open an issue.