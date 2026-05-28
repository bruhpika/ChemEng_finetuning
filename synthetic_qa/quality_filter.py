"""
Quality filter for generated Q&A pairs.

Applies multiple filtering passes to remove low-quality, duplicate,
off-topic, and self-referential pairs.
"""

import re
from collections import Counter

from synthetic_qa.config import MIN_INPUT_LENGTH, MIN_INSTRUCTION_LENGTH, MIN_OUTPUT_LENGTH, log


# Patterns that indicate self-referential or evasive answers
REJECT_PATTERNS = [
    r"as an ai",
    r"i cannot",
    r"i don'?t have access",
    r"i'?m not able to",
    r"i am unable to",
    r"based on the (chunk|provided|context)",
    r"according to the (chunk|provided|context)",
    r"the chunk (mentions|states|describes)",
    r"from the provided (data|text|content)",
    r"this (chunk|passage|text) (discusses|covers)",
]

# Technical terms that should appear in valid ChemE Q&A pairs
CHEME_KEYWORDS = {
    "DWSIM": [
        "dwsim", "simulation", "flowsheet", "stream", "property", "component",
        "thermodynamic", "flash", "distillation", "column", "separator", "mixer",
        "heater", "cooler", "pump", "compressor", "reactor", "valve",
        "temperature", "pressure", "flow", "experiment", "phase", "equilibrium",
        "convergence", "solver", "unit operation", "material stream",
    ],
    "MATLAB": [
        "matlab", "simulink", "function", "script", "plot", "matrix", "array",
        "ode", "solver", "pid", "controller", "transfer function", "bode",
        "command", "variable", "workspace", "toolbox", "block", "model",
        "simulation", "parameter", "equation", "numerical", "code",
    ],
}


def filter_pairs(pairs: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """
    Apply all quality filters to generated Q&A pairs.

    Returns:
        (filtered_pairs, rejection_stats)
    """
    stats: dict[str, int] = {
        "input_total": len(pairs),
        "rejected_empty_instruction": 0,
        "rejected_empty_output": 0,
        "rejected_short_instruction": 0,
        "rejected_short_output": 0,
        "rejected_self_referential": 0,
        "rejected_off_topic": 0,
        "rejected_duplicate": 0,
        "passed": 0,
    }

    filtered: list[dict] = []
    seen_instructions: set[str] = set()

    for pair in pairs:
        if not isinstance(pair, dict):
            continue

        instruction = str(pair.get("instruction", "")).strip()
        input_text = str(pair.get("input", "")).strip()
        output = str(pair.get("output", "")).strip()

        # ── Empty field check ────────────────────────────────────────────
        if not instruction:
            stats["rejected_empty_instruction"] += 1
            continue

        if not output:
            stats["rejected_empty_output"] += 1
            continue

        # ── Length check ─────────────────────────────────────────────────
        if len(instruction) < MIN_INSTRUCTION_LENGTH:
            stats["rejected_short_instruction"] += 1
            continue

        if len(output) < MIN_OUTPUT_LENGTH:
            stats["rejected_short_output"] += 1
            continue

        # ── Self-referential check ───────────────────────────────────────
        combined_text = f"{instruction} {output}".lower()
        is_self_ref = False
        for pattern in REJECT_PATTERNS:
            if re.search(pattern, combined_text):
                is_self_ref = True
                break
        if is_self_ref:
            stats["rejected_self_referential"] += 1
            continue

        # ── Off-topic detection ──────────────────────────────────────────
        software = pair.get("software", "")
        if software:
            keywords = CHEME_KEYWORDS.get(software, [])
            if keywords:
                output_lower = output.lower()
                has_relevant_term = any(kw in output_lower for kw in keywords)
                if not has_relevant_term:
                    stats["rejected_off_topic"] += 1
                    continue

        # ── Deduplication (exact match on instruction) ───────────────────
        instruction_normalized = instruction.lower().strip()
        if instruction_normalized in seen_instructions:
            stats["rejected_duplicate"] += 1
            continue
        seen_instructions.add(instruction_normalized)

        # ── Pair passed all filters ──────────────────────────────────────
        # Clean up the pair
        pair["instruction"] = instruction
        pair["input"] = input_text
        pair["output"] = output

        filtered.append(pair)
        stats["passed"] += 1

    # Log summary
    log.info(
        f"Quality filter: {stats['input_total']} input → {stats['passed']} passed "
        f"({stats['passed'] * 100 // max(stats['input_total'], 1)}% pass rate)"
    )

    rejection_details = {
        k: v for k, v in stats.items()
        if k.startswith("rejected_") and v > 0
    }
    if rejection_details:
        log.info(f"  Rejections: {rejection_details}")

    return filtered, stats
