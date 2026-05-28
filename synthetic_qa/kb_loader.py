"""
Knowledge Base Loader.

Merges all Track A + Track B chunk files into a unified list,
filters out flagged/incomplete chunks, deduplicates, and ranks
by content richness for priority processing.
"""

import json
import os
from collections import Counter

from synthetic_qa.config import KB_FILES, log


def _content_richness(chunk: dict) -> int:
    """
    Score a chunk's content richness for processing priority.

    Higher score = more fields populated = more Q&A categories possible.
    Weights reflect which fields enable which Q&A categories:
      - steps/ui_paths   → how_to
      - errors/fixes     → troubleshooting
      - params           → parameter_config
      - theory           → conceptual
    """
    score = 0

    steps = chunk.get("steps", [])
    if isinstance(steps, list) and len(steps) > 0:
        score += 3  # Steps are the most valuable for how-to

    ui_paths = chunk.get("ui_paths", [])
    if isinstance(ui_paths, list) and len(ui_paths) > 0:
        score += 2

    errors = chunk.get("errors", [])
    if isinstance(errors, list) and len(errors) > 0:
        score += 3  # Errors are rare and valuable for troubleshooting

    fixes = chunk.get("fixes", [])
    if isinstance(fixes, list) and len(fixes) > 0:
        score += 2

    params = chunk.get("params", {})
    if isinstance(params, dict) and len(params) > 0:
        score += 2
    elif isinstance(params, list) and len(params) > 0:
        # Some chunks have params as list (Track B quirk)
        score += 2

    theory = chunk.get("theory", "")
    if isinstance(theory, str) and len(theory.strip()) > 20:
        score += 2

    topic = chunk.get("topic", "")
    if isinstance(topic, str) and len(topic.strip()) > 5:
        score += 1

    return score


def load_kb() -> list[dict]:
    """
    Load, merge, filter, deduplicate, and rank all KB chunks.

    Returns a list of chunk dicts sorted by content richness (descending).
    Each chunk is guaranteed to have a 'chunk_id' and 'software' field.
    """
    all_chunks: list[dict] = []
    files_loaded = 0
    files_missing = 0

    for filepath in KB_FILES:
        if not os.path.exists(filepath):
            log.warning(f"KB file not found, skipping: {filepath}")
            files_missing += 1
            continue

        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                all_chunks.extend(data)
            elif isinstance(data, dict):
                # Single chunk (like the Part files)
                all_chunks.append(data)
            else:
                log.warning(f"Unexpected data type in {filepath}: {type(data)}")
                continue

            files_loaded += 1
            count = len(data) if isinstance(data, list) else 1
            log.info(f"Loaded {count} chunks from {os.path.basename(filepath)}")

        except (json.JSONDecodeError, Exception) as e:
            log.error(f"Failed to load {filepath}: {e}")
            files_missing += 1

    log.info(f"Files loaded: {files_loaded} | Files missing: {files_missing}")
    log.info(f"Raw chunks before filtering: {len(all_chunks)}")

    # ── Filter out flagged chunks ────────────────────────────────────────
    filtered: list[dict] = []
    removed_incomplete = 0
    removed_parse_error = 0
    removed_no_id = 0

    for chunk in all_chunks:
        flag = chunk.get("flag", "")

        if flag == "INCOMPLETE":
            removed_incomplete += 1
            continue

        if flag == "PARSE_ERROR":
            removed_parse_error += 1
            continue

        # Must have a chunk_id and software
        if not chunk.get("chunk_id"):
            removed_no_id += 1
            continue

        if not chunk.get("software"):
            removed_no_id += 1
            continue

        filtered.append(chunk)

    log.info(
        f"Filtered: removed {removed_incomplete} INCOMPLETE, "
        f"{removed_parse_error} PARSE_ERROR, {removed_no_id} missing ID/software"
    )

    # ── Deduplicate by chunk_id ──────────────────────────────────────────
    seen_ids: set[str] = set()
    deduped: list[dict] = []
    dups = 0

    for chunk in filtered:
        cid = chunk["chunk_id"]
        if cid in seen_ids:
            dups += 1
            continue
        seen_ids.add(cid)
        deduped.append(chunk)

    if dups > 0:
        log.info(f"Deduplicated: removed {dups} duplicate chunk_ids")

    # ── Enrich with content richness score and sort ──────────────────────
    for chunk in deduped:
        chunk["_richness"] = _content_richness(chunk)

    deduped.sort(key=lambda c: c["_richness"], reverse=True)

    # ── Log distribution ─────────────────────────────────────────────────
    software_counts = Counter(c.get("software", "unknown") for c in deduped)
    source_counts = Counter(c.get("source_type", "unknown") for c in deduped)
    richness_buckets = Counter(
        "high" if c["_richness"] >= 8 else "medium" if c["_richness"] >= 4 else "low"
        for c in deduped
    )

    log.info(f"Final KB: {len(deduped)} chunks")
    log.info(f"  By software: {dict(software_counts)}")
    log.info(f"  By source: {dict(source_counts)}")
    log.info(f"  By richness: {dict(richness_buckets)}")

    return deduped


def chunk_to_context_string(chunk: dict) -> str:
    """
    Serialize a chunk into a readable context string for inclusion
    in a Gemini prompt. Omits empty fields for token efficiency.
    """
    parts: list[str] = []
    parts.append(f"Topic: {chunk.get('topic', 'N/A')}")
    parts.append(f"Software: {chunk.get('software', 'N/A')}")
    parts.append(f"Source Type: {chunk.get('source_type', 'N/A')}")

    steps = chunk.get("steps", [])
    if steps:
        steps_str = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(steps))
        parts.append(f"Steps:\n{steps_str}")

    params = chunk.get("params", {})
    if params:
        if isinstance(params, dict):
            params_str = "\n".join(f"  - {k}: {v}" for k, v in params.items())
        elif isinstance(params, list):
            params_str = "\n".join(f"  - {p}" for p in params)
        else:
            params_str = str(params)
        parts.append(f"Parameters:\n{params_str}")

    ui_paths = chunk.get("ui_paths", [])
    if ui_paths:
        ui_str = "\n".join(f"  - {p}" for p in ui_paths)
        parts.append(f"UI Paths:\n{ui_str}")

    errors = chunk.get("errors", [])
    if errors:
        err_str = "\n".join(f"  - {e}" for e in errors)
        parts.append(f"Common Errors:\n{err_str}")

    fixes = chunk.get("fixes", [])
    if fixes:
        fix_str = "\n".join(f"  - {fix}" for fix in fixes)
        parts.append(f"Fixes:\n{fix_str}")

    theory = chunk.get("theory", "")
    if theory and len(theory.strip()) > 10:
        parts.append(f"Theory/Explanation: {theory}")

    return "\n".join(parts)
