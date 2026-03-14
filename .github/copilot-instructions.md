# Vocab App - Workspace Instructions

## Project Overview

**Vocab App** is a TOEIC vocabulary enrichment tool that transforms a simple list of English words into comprehensive language learning data. The main script (`scripts/toiec_enrich.py`) uses an LLM (via OpenAI-compatible API) to automatically generate:

- Grammatical type (noun, verb, adjective, etc.)
- French translations
- 3 realistic example sentences in English + French translations

**Target Audience**: TOEIC exam preparation; vocabulary focused on business, travel, and daily life contexts.

**Technology Stack**:
- Python 3.7+
- OpenAI-compatible API client (openai library)
- LM Studio (or compatible LLM endpoint)
- ThreadPoolExecutor for parallel processing
- CSV-based data storage

---

## Key Files and Their Purpose

| File/Directory | Purpose |
|---|---|
| `scripts/toiec_enrich.py` | Main script: reads CSV, calls LLM, enriches words, writes output |
| `data/words.csv` | Input data: columns `mot`, `section`, `type` with TOEIC vocabulary |
| `data/toeic_enriched.csv` | Output data: enriched words with translations and examples (auto-generated) |

### CSV Schemas

**Input (words.csv)**:
```
id,mot,section,type
1,advantage,A,noun
2,anxious,A,adjective
...
```

**Output (toeic_enriched.csv)**:
```
id,mot,section,type,translation_fr,example_1_en,example_1_fr,example_2_en,example_2_fr,example_3_en,example_3_fr
1,advantage,A,noun,avantage,...
```

---

## Core Architecture and Data Flow

```
words.csv → Load & Validate → Check Resume Status → ThreadPool Workers
                                                           ↓
                                    (For each word) Call LLM → Parse JSON → Write CSV
                                                           ↓
                                    ← Immediate flush to prevent data loss
                                                           ↓
                                           toeic_enriched.csv
```

**Key Design Principles**:
1. **Resilience**: 3-retry logic with exponential backoff on API failures
2. **Data Integrity**: Immediate CSV flush after each word to enable safe resumption
3. **Graceful Degradation**: Fallback values ("unknown" type, empty fields) to never fully crash
4. **Parallel Processing**: ThreadPoolExecutor with configurable worker count (default 4)
5. **Resume Capability**: Can continue from last processed word if interrupted

---

## Build/Run Commands

### Basic Execution
```bash
# From workspace root
python scripts/toiec_enrich.py

# From scripts directory
cd scripts
python toiec_enrich.py
```

### With Custom Parameters
```bash
python scripts/toiec_enrich.py \
    --input data/words.csv \
    --output data/toeic_enriched.csv \
    --base-url http://localhost:1234/v1 \
    --model openai/gpt-oss-20b \
    --workers 4 \
    --limit 10 \
    --resume
```

### CLI Arguments Reference

| Argument | Default | Purpose |
|----------|---------|---------|
| `--input` | `../data/words.csv` | Input CSV file path |
| `--output` | `../data/toeic_enriched.csv` | Output enriched CSV file path |
| `--base-url` | `http://localhost:1234/v1` | LM Studio API endpoint |
| `--model` | `openai/gpt-oss-20b` | Model name for the API |
| `--api-key` | `"0"` | API key (default works for LM Studio) |
| `--workers` | `4` | Number of parallel threads |
| `--limit` | `None` | Process only N words (for testing) |
| `--resume` | `False` | Continue from last processed word |

**Common Use Cases**:
- **Testing with 10 words**: `python scripts/toiec_enrich.py --limit 10`
- **Resume after interruption**: `python scripts/toiec_enrich.py --resume`
- **Custom API endpoint**: `python scripts/toiec_enrich.py --base-url http://api.example.com/v1 --model custom-model`

---

## Development Patterns and Conventions

### Error Handling Pattern
- Always maintain the 3-retry loop in `call_llm()` for transient failures
- Use `time.sleep()` with exponential backoff between retries
- Return fallback values instead of raising exceptions to ensure completion

### Data Processing Pattern
- Keep word processing stateless and independent (enables parallelization)
- Validate JSON structure before consuming (check for required keys)
- Validate example count (must have exactly 3 examples)

### CSV I/O Pattern
- Use `csv.DictWriter` for typed, header-based writing
- Call `flush()` immediately after each row write (critical for resume)
- Use `newline=''` parameter in file open (Python CSV requirement)

### Progress Feedback
- Use emoji indicators in console output: `✅` (success), `❌` (failure), `🔍` (processing)
- Include word counter and runtime info for user feedback
- Print one line per word for easy scanning

### Code Style
- Code contains French comments (accessible to francophone contributors)
- Use f-strings for formatting
- Type hints for function signatures (optional but preferred)
- Clear function docstrings explaining purpose and return values

---

## Common Development Tasks

### Add a New Output Column

1. **Update `process_row()` return dict** to include new field
2. **Update CSV fieldnames** in `main()` DictWriter initialization
3. **Update system prompt** if new data comes from LLM
4. **Validate JSON structure** if new data is LLM-sourced

### Modify LLM Behavior

Edit `SYSTEM_PROMPT` constant:
- Current: Instructs LLM to be a linguist specialist
- Must return JSON with specific structure
- Can adjust tone, language focus, or output format

### Test with Subset of Data

```bash
python scripts/toiec_enrich.py --limit 5
```

### Resume a Failed Run

```bash
python scripts/toiec_enrich.py --resume
```

### Change Worker Count for Performance

```bash
python scripts/toiec_enrich.py --workers 8
```

(Tune based on API rate limits and system resources)

---

## Dependencies and Environment Setup

### Python Requirements
- Python 3.7+ (uses f-strings, type hints)
- `openai` library (OpenAI-compatible API client)

### Installation

```bash
# Create and activate environment
conda create -n vocab-app python=3.10
conda activate vocab-app

# Install dependencies
pip install openai
```

### External Service
- **LM Studio** (or compatible OpenAI-compatible API) running on `http://localhost:1234/v1`
- Default model: `openai/gpt-oss-20b` (can be substituted)
- **Note**: Ensure LM Studio is running before executing the script

---

## Tips for AI Agents

### When Making Bug Fixes
- Preserve the 3-retry pattern in `call_llm()`
- Maintain immediate CSV flush to enable resume functionality
- Always validate JSON structure before parsing

### When Adding Features
- Extend `process_row()` for new column types
- Add CLI arguments to `argparse.ArgumentParser` for new options
- Ensure thread-safety in write operations (currently safe due to serial CSV writes after thread resolution)

### When Optimizing Performance
- Worker count is tunable via `--workers` flag
- Current bottleneck is API latency (not disk I/O)
- Consider batch API calls if LLM backend supports them

### When Troubleshooting
- Check LM Studio is running on configured `--base-url`
- Verify input CSV has required columns: `mot`, `section`, `type`
- Use `--limit` to test with small subsets first
- Check console output for `❌` indicators showing which words failed
- Resume mode skips already-processed words (check output CSV for existing rows)

---

## Project Structure
```
Vocab_app/
├── .github/
│   └── copilot-instructions.md  (this file)
├── data/
│   ├── words.csv                (input vocabulary)
│   └── toeic_enriched.csv       (generated output)
└── scripts/
    └── toiec_enrich.py          (main enrichment script)
```

---

## Contact / Maintenance Notes

- **Language**: The project supports French-speaking contributors (code comments in French)
- **Scope**: Currently focused on TOEIC vocabulary; extensible to other exam formats
- **Status**: Production-ready with robust error handling and resume capability
- **Next Improvements**: (Add any planned features, performance optimizations, or known limitations here)
