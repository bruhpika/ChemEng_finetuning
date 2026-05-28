# Synthetic Q&A Generation Pipeline

Generates `{instruction, input, output}` finetuning pairs from the ChemE-LLM Knowledge Base using Gemini API.

## Setup

1. **API Key**: Ensure your Gemini API key is in `gemini_api_key.txt` at the project root:
   ```
   API KEY: your_gemini_api_key_here
   ```

2. **Dependencies**: The pipeline uses `google-generativeai` (already in your venv).

## Usage

```bash
cd ChemEng_finetuning-main
source .venv/bin/activate

# Validate KB without API calls
python -m synthetic_qa.pipeline --dry-run

# Test with 5 chunks (makes ~1 API call)
python -m synthetic_qa.pipeline --max-chunks 5 --skip-balance

# Full run (processes all 766+ chunks)
python -m synthetic_qa.pipeline

# Resume interrupted run
python -m synthetic_qa.pipeline --resume

# Start completely fresh
python -m synthetic_qa.pipeline --no-resume --clear-checkpoint
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--dry-run` | off | Load KB, validate, skip API calls |
| `--max-chunks N` | all | Limit chunks processed (testing) |
| `--batch-size N` | 5 | Chunks per Gemini API call |
| `--skip-balance` | off | Skip category balancing pass |
| `--no-resume` | off | Ignore checkpoint, start fresh |
| `--clear-checkpoint` | off | Delete checkpoint file |
| `--target-per-category N` | 500 | Min pairs per category |

## Pipeline Steps

1. **Load KB** — Merges Track A + Track B chunks, filters flagged entries, deduplicates
2. **Generate** — Batched Gemini calls with retry, rate-limiting, checkpoint/resume
3. **Filter** — Removes empty, short, duplicate, off-topic, and self-referential pairs
4. **Balance** — Checks category distribution; generates targeted extras if any category < 500
5. **Output** — Writes `finetune_dataset.jsonl` at project root

## Output Format

```jsonl
{"instruction": "...", "input": "...", "output": "...", "category": "how_to", "software": "DWSIM", "source_chunk_id": "..."}
{"instruction": "...", "input": "...", "output": "...", "category": "troubleshooting", "software": "MATLAB", "source_chunk_id": "..."}
```

## Q&A Categories

| Category | Description | Source Fields |
|----------|-------------|---------------|
| `how_to` | Step-by-step procedures | steps, ui_paths |
| `troubleshooting` | Error diagnosis + fixes | errors, fixes |
| `parameter_config` | Parameter values/units | params, ui_paths |
| `conceptual` | Theory + comparisons | theory, topic |

## Monitoring

- **Live progress**: `synthetic_qa/progress.md` (updates after each batch)
- **Checkpoint**: `synthetic_qa/checkpoint.json` (for resume)
- **Final stats**: `synthetic_qa/generation_stats.json`

## Architecture

```
synthetic_qa/
├── config.py              # Constants, paths, API key loading
├── kb_loader.py           # Merge + filter + rank KB chunks
├── prompt_templates.py    # Gemini prompts with few-shot examples
├── generator.py           # Batched API caller with retry/checkpoint
├── quality_filter.py      # Multi-stage quality filtering
├── category_balancer.py   # Category distribution + targeted generation
├── pipeline.py            # Main orchestrator + CLI
└── README.md              # This file
```
