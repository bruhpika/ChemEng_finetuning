"""
Core Gemini API caller with batching, retry, rate-limiting, and checkpoint/resume.

Processes KB chunks in configurable batch sizes, calls Gemini to generate
Q&A pairs, and saves progress incrementally.
"""

import json
import os
import re
import time

import google.generativeai as genai

from synthetic_qa.config import (
    API_KEYS,
    BATCH_SIZE,
    CHECKPOINT_FILE,
    COOL_DOWN_BATCHES,
    COOL_DOWN_SLEEP,
    MAX_RETRIES,
    MAX_RETRY_BACKOFF,
    MODEL_NAME,
    PROGRESS_FILE,
    QA_PER_CHUNK_TARGET,
    RETRY_WAIT,
    SLEEP_BETWEEN_CALLS,
    log,
)
from synthetic_qa.kb_loader import chunk_to_context_string
from synthetic_qa.prompt_templates import build_generation_prompt, build_targeted_prompt

# ── API STATE ────────────────────────────────────────────────────────────────
_current_key_idx = 0
_model: genai.GenerativeModel | None = None
# Tracks which keys have hit their quota in the current rotation cycle.
# Cleared after a successful call so recovery is detected automatically.
_exhausted_keys: set[int] = set()


def _init_model() -> genai.GenerativeModel:
    """Initialize or return the cached Gemini model instance."""
    global _model
    if _model is None:
        if not API_KEYS:
            raise RuntimeError("No API keys available. Cannot initialize Gemini model.")
        genai.configure(api_key=API_KEYS[_current_key_idx])
        _model = genai.GenerativeModel(MODEL_NAME)
        log.info(
            f"Initialized Gemini model: {MODEL_NAME} "
            f"(key {_current_key_idx + 1}/{len(API_KEYS)})"
        )
    return _model


def _rotate_key() -> bool:
    """
    Cycle to the next available (non-exhausted) API key.

    Wraps around from the last key back to key 0 (full cycle).
    Returns True if a non-exhausted key was found, False if ALL keys
    are currently exhausted (caller should back off and wait).
    """
    global _current_key_idx, _model, _exhausted_keys

    # Mark current key as exhausted
    _exhausted_keys.add(_current_key_idx)

    if len(_exhausted_keys) >= len(API_KEYS):
        # Every key has hit its quota — signal the caller to back off
        log.warning(
            f"All {len(API_KEYS)} API key(s) are rate-limited. "
            "Will wait before retrying."
        )
        return False

    # Advance cyclically, skipping exhausted keys
    for _ in range(len(API_KEYS)):
        _current_key_idx = (_current_key_idx + 1) % len(API_KEYS)
        if _current_key_idx not in _exhausted_keys:
            log.warning(
                f"Rotating to API key {_current_key_idx + 1}/{len(API_KEYS)} "
                f"({len(_exhausted_keys)} exhausted so far)"
            )
            genai.configure(api_key=API_KEYS[_current_key_idx])
            _model = genai.GenerativeModel(MODEL_NAME)
            return True

    # Should never reach here, but guard anyway
    return False


def _reset_exhausted_keys() -> None:
    """Clear the exhausted-key set after a successful call or a timed backoff."""
    global _exhausted_keys
    if _exhausted_keys:
        log.info("Resetting exhausted-key tracker — all keys are available again.")
    _exhausted_keys = set()


def _restart_from_first_key() -> None:
    """Reset the active key to index 0 after a full-cycle backoff."""
    global _current_key_idx, _model
    _current_key_idx = 0
    genai.configure(api_key=API_KEYS[_current_key_idx])
    _model = genai.GenerativeModel(MODEL_NAME)
    log.info(f"Restarted from key 1/{len(API_KEYS)} after backoff.")


# ── JSON PARSING ─────────────────────────────────────────────────────────────


def _parse_gemini_json(text: str) -> list[dict] | None:
    """
    Robust JSON extraction from Gemini response.

    Handles markdown fences, extra commentary, and nested brackets.
    Same proven approach from the Track B agent.
    """
    text = text.strip()

    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Find outermost array boundaries
    start = text.find("[")
    end = text.rfind("]")

    if start == -1 or end == -1 or end <= start:
        log.error("No JSON array found in Gemini response")
        log.debug(f"Response preview: {text[:200]}")
        return None

    candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, list):
            return parsed
        log.error(f"Parsed JSON is not a list: {type(parsed)}")
        return None
    except json.JSONDecodeError as e:
        log.error(f"JSON decode failed: {e}")
        log.debug(f"Candidate preview: {candidate[:300]}")
        return None


# ── CHECKPOINT MANAGEMENT ────────────────────────────────────────────────────


def load_checkpoint() -> dict:
    """Load checkpoint state (processed chunk IDs and accumulated pairs)."""
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            log.warning(f"Corrupt checkpoint file, starting fresh: {e}")
    return {"processed_ids": [], "total_pairs": 0, "api_calls": 0}


def save_checkpoint(state: dict) -> None:
    """Save checkpoint state to disk."""
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ── PROGRESS TRACKER ─────────────────────────────────────────────────────────


def update_progress(
    total_chunks: int,
    processed: int,
    pairs_generated: int,
    api_calls: int,
    category_counts: dict[str, int],
    current_batch: int | None = None,
    status: str = "Running",
) -> None:
    """Write live progress to progress.md for monitoring."""
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        f.write("# Synthetic Q&A Generation — Progress Tracker\n\n")
        f.write(f"**Last Updated:** {time.ctime()}\n")
        f.write(f"**Status:** {status}\n\n")

        f.write("## Statistics\n\n")
        f.write(f"- **Total KB Chunks:** `{total_chunks}`\n")
        f.write(f"- **Chunks Processed:** `{processed}` / `{total_chunks}` ({processed * 100 // max(total_chunks, 1)}%)\n")
        f.write(f"- **Q&A Pairs Generated:** `{pairs_generated}`\n")
        f.write(f"- **Gemini API Calls:** `{api_calls}`\n")
        f.write(f"- **Avg Pairs/Chunk:** `{pairs_generated / max(processed, 1):.1f}`\n\n")

        if current_batch is not None:
            total_batches = (total_chunks + BATCH_SIZE - 1) // BATCH_SIZE
            f.write(f"- **Current Batch:** `{current_batch}` / `{total_batches}`\n\n")

        f.write("## Category Distribution\n\n")
        f.write("| Category | Count | Target |\n")
        f.write("|----------|-------|--------|\n")
        for cat in ["how_to", "troubleshooting", "parameter_config", "conceptual"]:
            count = category_counts.get(cat, 0)
            status_emoji = "✅" if count >= 500 else "⚠️"
            f.write(f"| {cat} | {count} | 500 {status_emoji} |\n")
        f.write(f"| **Total** | **{sum(category_counts.values())}** | **2000+** |\n\n")

        f.write("## API Key Status\n\n")
        f.write(f"- **Total Keys Loaded:** `{len(API_KEYS)}`\n")
        f.write(f"- **Current Key Index:** `{_current_key_idx + 1}` / `{len(API_KEYS)}`\n")
        exhausted = len(_exhausted_keys)
        available = len(API_KEYS) - exhausted
        f.write(f"- **Keys Available:** `{available}` / **Exhausted this cycle:** `{exhausted}`\n")
        f.write(f"- **Model:** `{MODEL_NAME}`\n")


# ── CORE API CALL ────────────────────────────────────────────────────────────


def call_gemini(prompt: str) -> list[dict] | None:
    """
    Make a single Gemini API call with retry and rate-limiting.

    Returns a list of parsed Q&A pair dicts, or None on failure.
    """
    model = _init_model()
    wait = RETRY_WAIT

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = model.generate_content(prompt)

            if not response.text:
                log.warning(f"Empty response from Gemini (attempt {attempt})")
                if attempt < MAX_RETRIES:
                    time.sleep(wait)
                    continue
                return None

            pairs = _parse_gemini_json(response.text)
            if pairs is None:
                log.warning(f"Failed to parse JSON (attempt {attempt})")
                if attempt < MAX_RETRIES:
                    time.sleep(wait)
                    continue
                return None

            # Successful call — clear exhausted tracker so all keys are
            # eligible again (they may have refilled quota since last hit).
            _reset_exhausted_keys()
            return pairs

        except Exception as e:
            error_str = str(e).lower()

            # Rate limit — cycle through keys before falling back to a timed wait
            if "429" in error_str or "resource exhausted" in error_str:
                log.warning(f"Rate limited on key {_current_key_idx + 1} (attempt {attempt}): {e}")
                if _rotate_key():
                    # Successfully switched to a fresh key — retry immediately
                    # (don't burn a retry count on a key-rotation switch)
                    model = _init_model()
                    continue
                # All keys exhausted — wait then reset the tracker for next cycle
                log.info(
                    f"Full key cycle exhausted. Backing off {wait}s before "
                    "retrying from key 1..."
                )
                time.sleep(wait)
                wait = min(wait * 2, MAX_RETRY_BACKOFF)
                _reset_exhausted_keys()
                # Restart from key index 0 after backoff
                _restart_from_first_key()
                model = _model
                continue

            # Server error — retry with backoff
            if "500" in error_str or "503" in error_str:
                log.warning(f"Server error (attempt {attempt}): {e}")
                time.sleep(wait)
                wait = min(wait * 2, MAX_RETRY_BACKOFF)
                continue

            # Other errors — log and give up
            log.error(f"Gemini call failed (attempt {attempt}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(wait)
                continue
            return None

    return None


# ── BATCH GENERATION ─────────────────────────────────────────────────────────


def generate_from_chunks(
    chunks: list[dict],
    batch_size: int = BATCH_SIZE,
    resume: bool = True,
    max_chunks: int | None = None,
    category_emphasis: dict[str, int] | None = None,
) -> list[dict]:
    """
    Process KB chunks in batches, generating Q&A pairs via Gemini.

    Args:
        chunks: List of KB chunk dicts (from kb_loader.load_kb)
        batch_size: Number of chunks per Gemini call
        resume: Whether to resume from checkpoint
        max_chunks: Limit total chunks processed (for testing)
        category_emphasis: Optional category → extra pairs needed

    Returns:
        List of all generated Q&A pair dicts.
    """
    # Load checkpoint if resuming
    checkpoint = load_checkpoint() if resume else {"processed_ids": [], "total_pairs": 0, "api_calls": 0}
    processed_ids = set(checkpoint["processed_ids"])

    # Filter out already-processed chunks
    remaining = [c for c in chunks if c["chunk_id"] not in processed_ids]
    if max_chunks is not None:
        remaining = remaining[:max_chunks]

    total_to_process = len(remaining)
    log.info(
        f"Generation: {total_to_process} chunks to process "
        f"({len(processed_ids)} already done, {len(chunks)} total)"
    )

    if total_to_process == 0:
        log.info("Nothing to process — all chunks already done.")
        return []

    # Track categories
    all_pairs: list[dict] = []
    category_counts: dict[str, int] = {"how_to": 0, "troubleshooting": 0, "parameter_config": 0, "conceptual": 0}
    api_calls = checkpoint["api_calls"]
    chunks_done = len(processed_ids)

    # Process in batches
    total_batches = (total_to_process + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, total_to_process)
        batch = remaining[batch_start:batch_end]

        batch_num = batch_idx + 1
        log.info(f"Batch {batch_num}/{total_batches} — {len(batch)} chunks")

        # Build context string from batch chunks
        context_parts = []
        chunk_ids = []
        for chunk in batch:
            cid = chunk["chunk_id"]
            chunk_ids.append(cid)
            ctx = chunk_to_context_string(chunk)
            context_parts.append(f"--- Chunk ID: {cid} ---\n{ctx}")

        full_context = "\n\n".join(context_parts)

        # Build prompt
        prompt = build_generation_prompt(full_context, chunk_ids, category_emphasis)

        # Call Gemini
        pairs = call_gemini(prompt)
        api_calls += 1

        if pairs is None:
            log.warning(f"Batch {batch_num} failed — no pairs generated")
        else:
            # Validate and count
            valid_pairs = []
            for pair in pairs:
                if not isinstance(pair, dict):
                    continue
                # Ensure required fields exist
                if not pair.get("instruction") or not pair.get("output"):
                    continue
                # Default empty input
                if "input" not in pair:
                    pair["input"] = ""
                # Validate category
                cat = pair.get("category", "")
                if cat not in category_counts:
                    cat = "conceptual"  # fallback
                    pair["category"] = cat
                category_counts[cat] = category_counts.get(cat, 0) + 1
                valid_pairs.append(pair)

            all_pairs.extend(valid_pairs)
            log.info(f"  → Generated {len(valid_pairs)} valid pairs (batch total: {len(all_pairs)})")

        # Update checkpoint
        for chunk in batch:
            processed_ids.add(chunk["chunk_id"])
        chunks_done += len(batch)

        save_checkpoint({
            "processed_ids": list(processed_ids),
            "total_pairs": len(all_pairs),
            "api_calls": api_calls,
        })

        # Update progress
        update_progress(
            total_chunks=len(chunks),
            processed=chunks_done,
            pairs_generated=len(all_pairs),
            api_calls=api_calls,
            category_counts=category_counts,
            current_batch=batch_num,
        )

        # Rate limiting
        time.sleep(SLEEP_BETWEEN_CALLS)

        # Cool-down pause
        if batch_num > 0 and batch_num % COOL_DOWN_BATCHES == 0:
            log.info(f"Cool-down pause ({COOL_DOWN_SLEEP}s) after {batch_num} batches...")
            time.sleep(COOL_DOWN_SLEEP)

    log.info(
        f"Generation complete: {len(all_pairs)} pairs from {chunks_done} chunks "
        f"in {api_calls} API calls"
    )
    log.info(f"Category distribution: {category_counts}")

    return all_pairs


def generate_targeted(
    chunks: list[dict],
    target_category: str,
    pairs_needed: int,
    batch_size: int = BATCH_SIZE,
) -> list[dict]:
    """
    Run a targeted generation pass for a specific underrepresented category.

    Selects the most relevant chunks for the target category and generates
    only that category's Q&A pairs.
    """
    log.info(f"Targeted generation: {pairs_needed} '{target_category}' pairs needed")

    # Select chunks most relevant to this category
    category_field_map = {
        "how_to": lambda c: bool(c.get("steps")),
        "troubleshooting": lambda c: bool(c.get("errors")) or bool(c.get("fixes")),
        "parameter_config": lambda c: bool(c.get("params")),
        "conceptual": lambda c: bool(c.get("theory") and len(str(c.get("theory", ""))) > 30),
    }

    selector = category_field_map.get(target_category, lambda c: True)
    relevant_chunks = [c for c in chunks if selector(c)]

    if not relevant_chunks:
        log.warning(f"No relevant chunks found for category '{target_category}'")
        return []

    # Limit to what we need (estimate ~3 pairs per chunk for targeted)
    chunks_needed = min(len(relevant_chunks), (pairs_needed // 3) + 5)
    selected = relevant_chunks[:chunks_needed]

    log.info(f"Selected {len(selected)} chunks for targeted '{target_category}' generation")

    all_pairs: list[dict] = []
    total_batches = (len(selected) + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, len(selected))
        batch = selected[batch_start:batch_end]

        context_parts = []
        chunk_ids = []
        for chunk in batch:
            cid = chunk["chunk_id"]
            chunk_ids.append(cid)
            ctx = chunk_to_context_string(chunk)
            context_parts.append(f"--- Chunk ID: {cid} ---\n{ctx}")

        full_context = "\n\n".join(context_parts)

        # Calculate pairs per batch
        batch_pairs_target = min(
            pairs_needed - len(all_pairs),
            len(batch) * 3,
        )
        if batch_pairs_target <= 0:
            break

        prompt = build_targeted_prompt(full_context, chunk_ids, target_category, batch_pairs_target)

        pairs = call_gemini(prompt)
        if pairs:
            valid = [
                p for p in pairs
                if isinstance(p, dict) and p.get("instruction") and p.get("output")
            ]
            # Force correct category
            for p in valid:
                p["category"] = target_category
                if "input" not in p:
                    p["input"] = ""
            all_pairs.extend(valid)
            log.info(f"  Targeted batch {batch_idx + 1}/{total_batches}: {len(valid)} pairs")

        if len(all_pairs) >= pairs_needed:
            break

        time.sleep(SLEEP_BETWEEN_CALLS)

    log.info(f"Targeted generation done: {len(all_pairs)} '{target_category}' pairs")
    return all_pairs
