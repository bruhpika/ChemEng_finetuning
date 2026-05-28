"""
Central configuration for the Synthetic Q&A Generation pipeline.

All constants, file paths, API settings, and thresholds are defined here.
"""

import os
import logging

# ── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("synthetic_qa")

# ── PROJECT ROOT ─────────────────────────────────────────────────────────────
# This file lives at synthetic_qa/config.py → project root is one level up
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── API KEY LOADING ──────────────────────────────────────────────────────────
# Follows the same pattern as Track A/B agents:
#   1. Check GEMINI_API_KEY / GOOGLE_API_KEY env vars
#   2. Read from gemini_api_key.txt (primary) or api.txt (fallback)
#   Format in file: "API KEY: <key>" (one per line for multiple keys)


def load_api_keys() -> list[str]:
    """Load Gemini API keys from environment and key files."""
    keys: list[str] = []

    # Env vars
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(var)
        if val and val not in keys:
            keys.append(val)

    # Key files (primary → fallback)
    key_files = [
        os.path.join(PROJECT_ROOT, "gemini_api_key.txt"),
        os.path.join(PROJECT_ROOT, "api.txt"),
    ]
    for key_path in key_files:
        if os.path.exists(key_path):
            try:
                with open(key_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if "API KEY:" in line:
                            key = line.split(":")[-1].strip()
                            if key and key not in keys:
                                keys.append(key)
                        elif line and not line.startswith("#") and len(line) > 20:
                            # Also accept bare key lines (no "API KEY:" prefix)
                            if line not in keys:
                                keys.append(line)
            except Exception as e:
                log.warning(f"Failed to read key file {key_path}: {e}")

    if not keys:
        log.error(
            "No API keys found. Set GEMINI_API_KEY env var or create "
            "gemini_api_key.txt with format 'API KEY: <key>'"
        )

    return keys


API_KEYS = load_api_keys()

# ── GEMINI MODEL ─────────────────────────────────────────────────────────────
MODEL_NAME = "gemini-2.5-flash"

# ── INPUT PATHS (Knowledge Base chunks) ──────────────────────────────────────
KB_FILES = [
    # Track A (processed/merged)
    os.path.join(
        PROJECT_ROOT,
        "data",
        "processed",
        "blackboard",
        "knowledge",
        "chunks_DWSIM.json",
    ),
    os.path.join(
        PROJECT_ROOT,
        "data",
        "processed",
        "blackboard",
        "knowledge",
        "chunks_MATLAB.json",
    ),
    os.path.join(
        PROJECT_ROOT,
        "data",
        "processed",
        "blackboard",
        "knowledge",
        "chunks__Part_1.json",
    ),
    os.path.join(
        PROJECT_ROOT,
        "data",
        "processed",
        "blackboard",
        "knowledge",
        "chunks__Part_2.json",
    ),
    os.path.join(
        PROJECT_ROOT,
        "data",
        "processed",
        "blackboard",
        "knowledge",
        "chunks__Part_3.json",
    ),
    os.path.join(
        PROJECT_ROOT,
        "data",
        "processed",
        "blackboard",
        "knowledge",
        "chunks__Part_4.json",
    ),
    # Track B (processed)
    os.path.join(
        PROJECT_ROOT,
        "data",
        "processed",
        "track_b",
        "chunks_DWSIM.json",
    ),
    os.path.join(
        PROJECT_ROOT,
        "data",
        "processed",
        "track_b",
        "chunks_MATLAB.json",
    ),
]

# ── OUTPUT PATHS ─────────────────────────────────────────────────────────────
OUTPUT_JSONL = os.path.join(PROJECT_ROOT, "finetune_dataset.jsonl")
CHECKPOINT_FILE = os.path.join(MODULE_DIR, "checkpoint.json")
PROGRESS_FILE = os.path.join(MODULE_DIR, "progress.md")
STATS_FILE = os.path.join(MODULE_DIR, "generation_stats.json")

# ── RATE LIMITING ────────────────────────────────────────────────────────────
SLEEP_BETWEEN_CALLS = 3  # seconds between Gemini calls
RETRY_WAIT = 30  # initial wait on 429/500
MAX_RETRIES = 5  # max retries per API call
MAX_RETRY_BACKOFF = 300  # cap backoff at 5 minutes
COOL_DOWN_BATCHES = 10  # every N batches, take a longer break
COOL_DOWN_SLEEP = 30  # seconds for the cool-down pause

# ── BATCH PROCESSING ────────────────────────────────────────────────────────
BATCH_SIZE = 5  # chunks per Gemini call (smaller = higher quality)
QA_PER_CHUNK_TARGET = 8  # target Q&A pairs per chunk (5-10 range)

# ── CATEGORY TARGETS ────────────────────────────────────────────────────────
CATEGORIES = ["how_to", "troubleshooting", "parameter_config", "conceptual"]
MIN_PER_CATEGORY = 500  # PRD requirement: ≥500 per category

# ── QUALITY THRESHOLDS ───────────────────────────────────────────────────────
MIN_OUTPUT_LENGTH = 50  # chars — reject short/empty outputs
MIN_INSTRUCTION_LENGTH = 20  # chars — reject vague instructions
MIN_INPUT_LENGTH = 0  # input can be empty (some questions are self-contained)
