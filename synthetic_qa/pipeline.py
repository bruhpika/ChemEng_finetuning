"""
Main pipeline orchestrator for Synthetic Q&A Generation.

Entry point: python -m synthetic_qa.pipeline [options]

Pipeline steps:
  1. Load KB (merge Track A + Track B)
  2. Initial Generation Pass (Gemini API)
  3. Quality Filter
  4. Category Balance Check (+ targeted generation if needed)
  5. Final JSONL Output
"""

import argparse
import json
import os
import sys
import time

from synthetic_qa.category_balancer import balance_dataset, print_distribution_report
from synthetic_qa.config import (
    BATCH_SIZE,
    CATEGORIES,
    CHECKPOINT_FILE,
    MIN_PER_CATEGORY,
    OUTPUT_JSONL,
    STATS_FILE,
    log,
)
from synthetic_qa.generator import generate_from_chunks, update_progress
from synthetic_qa.kb_loader import load_kb
from synthetic_qa.quality_filter import filter_pairs


def write_jsonl(pairs: list[dict], output_path: str) -> None:
    """
    Write Q&A pairs to JSONL format (one JSON object per line).

    The output contains the SFT-standard fields: instruction, input, output.
    Metadata fields (category, software, source_chunk_id) are preserved
    for analysis but can be stripped before finetuning.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for pair in pairs:
            # Ensure clean output
            record = {
                "instruction": pair.get("instruction", ""),
                "input": pair.get("input", ""),
                "output": pair.get("output", ""),
                # Metadata (keep for traceability, strip before training if desired)
                "category": pair.get("category", "unknown"),
                "software": pair.get("software", "unknown"),
                "source_chunk_id": pair.get("source_chunk_id", ""),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    log.info(f"Wrote {len(pairs)} pairs to {output_path}")


def save_stats(
    total_chunks: int,
    total_pairs_raw: int,
    total_pairs_filtered: int,
    total_pairs_final: int,
    filter_stats: dict,
    category_distribution: dict,
    duration_seconds: float,
) -> None:
    """Save generation statistics to a JSON file."""
    stats = {
        "timestamp": time.ctime(),
        "kb_chunks": total_chunks,
        "pairs_raw": total_pairs_raw,
        "pairs_after_filter": total_pairs_filtered,
        "pairs_final": total_pairs_final,
        "filter_stats": filter_stats,
        "category_distribution": category_distribution,
        "duration_seconds": round(duration_seconds, 1),
        "pairs_per_minute": round(total_pairs_final / max(duration_seconds / 60, 0.1), 1),
    }
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    log.info(f"Stats saved to {STATS_FILE}")


def run_pipeline(
    resume: bool = True,
    dry_run: bool = False,
    batch_size: int = BATCH_SIZE,
    max_chunks: int | None = None,
    target_per_category: int = MIN_PER_CATEGORY,
    skip_balance: bool = False,
) -> None:
    """
    Run the full Synthetic Q&A Generation pipeline.

    Args:
        resume: Resume from checkpoint if available
        dry_run: Load KB and validate, but skip API calls
        batch_size: Chunks per Gemini call
        max_chunks: Limit chunks processed (for testing)
        target_per_category: Minimum pairs per category
        skip_balance: Skip the category balancing pass
    """
    start_time = time.time()

    log.info("=" * 60)
    log.info("SYNTHETIC Q&A GENERATION PIPELINE")
    log.info("=" * 60)
    log.info(f"  Resume: {resume}")
    log.info(f"  Dry run: {dry_run}")
    log.info(f"  Batch size: {batch_size}")
    log.info(f"  Max chunks: {max_chunks or 'all'}")
    log.info(f"  Target per category: {target_per_category}")
    log.info("")

    # ── Step 1: Load Knowledge Base ──────────────────────────────────────
    log.info("Step 1: Loading Knowledge Base...")
    chunks = load_kb()

    if not chunks:
        log.error("No chunks loaded. Cannot proceed.")
        sys.exit(1)

    if dry_run:
        log.info("=" * 60)
        log.info("DRY RUN COMPLETE — KB loaded and validated.")
        log.info(f"Would process {len(chunks)} chunks in ~{(len(chunks) + batch_size - 1) // batch_size} batches.")
        log.info(f"Estimated API calls: ~{(len(chunks) + batch_size - 1) // batch_size}")
        log.info(f"Estimated Q&A pairs: ~{len(chunks) * 7} (at ~7 pairs/chunk)")
        log.info("=" * 60)
        return

    # ── Step 2: Initial Generation Pass ──────────────────────────────────
    log.info("")
    log.info("Step 2: Generating Q&A pairs from KB chunks...")
    raw_pairs = generate_from_chunks(
        chunks=chunks,
        batch_size=batch_size,
        resume=resume,
        max_chunks=max_chunks,
    )

    if not raw_pairs:
        log.error("No pairs generated. Check API key and Gemini access.")
        sys.exit(1)

    total_raw = len(raw_pairs)
    log.info(f"Raw pairs generated: {total_raw}")

    # ── Step 3: Quality Filter ───────────────────────────────────────────
    log.info("")
    log.info("Step 3: Applying quality filters...")
    filtered_pairs, filter_stats = filter_pairs(raw_pairs)
    total_filtered = len(filtered_pairs)

    # ── Step 4: Category Balance ─────────────────────────────────────────
    if not skip_balance:
        log.info("")
        log.info("Step 4: Checking category balance...")
        final_pairs = balance_dataset(filtered_pairs, chunks)
    else:
        log.info("")
        log.info("Step 4: Skipping category balance (--skip-balance)")
        final_pairs = filtered_pairs

    # Apply quality filter again on any new pairs from balancing
    if len(final_pairs) > total_filtered:
        log.info("Re-filtering after balance pass...")
        final_pairs, _ = filter_pairs(final_pairs)

    total_final = len(final_pairs)

    # ── Step 5: Write JSONL Output ───────────────────────────────────────
    log.info("")
    log.info("Step 5: Writing final JSONL output...")
    write_jsonl(final_pairs, OUTPUT_JSONL)

    # Print report
    report = print_distribution_report(final_pairs)

    # Save stats
    from collections import Counter
    cat_dist = dict(Counter(p.get("category", "unknown") for p in final_pairs))

    duration = time.time() - start_time
    save_stats(
        total_chunks=len(chunks),
        total_pairs_raw=total_raw,
        total_pairs_filtered=total_filtered,
        total_pairs_final=total_final,
        filter_stats=filter_stats,
        category_distribution=cat_dist,
        duration_seconds=duration,
    )

    # Update final progress
    update_progress(
        total_chunks=len(chunks),
        processed=len(chunks),
        pairs_generated=total_final,
        api_calls=0,  # already tracked in generator
        category_counts=cat_dist,
        status="Complete ✅",
    )

    # Summary
    log.info("")
    log.info("=" * 60)
    log.info("PIPELINE COMPLETE")
    log.info("=" * 60)
    log.info(f"  KB Chunks: {len(chunks)}")
    log.info(f"  Raw pairs: {total_raw}")
    log.info(f"  After filter: {total_filtered}")
    log.info(f"  Final output: {total_final}")
    log.info(f"  Output file: {OUTPUT_JSONL}")
    log.info(f"  Duration: {duration:.0f}s ({duration / 60:.1f} min)")
    log.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Synthetic Q&A Generation Pipeline for ChemE-LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m synthetic_qa.pipeline                     # Full run with resume
  python -m synthetic_qa.pipeline --dry-run            # Validate KB only
  python -m synthetic_qa.pipeline --max-chunks 5       # Test with 5 chunks
  python -m synthetic_qa.pipeline --no-resume          # Start fresh
  python -m synthetic_qa.pipeline --batch-size 3       # Smaller batches
  python -m synthetic_qa.pipeline --skip-balance       # Skip category balancing
        """,
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Resume from checkpoint (default: True)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        default=False,
        help="Start fresh, ignoring any checkpoint",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Load KB and validate without making API calls",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Chunks per Gemini API call (default: {BATCH_SIZE})",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Limit total chunks processed (for testing)",
    )
    parser.add_argument(
        "--target-per-category",
        type=int,
        default=MIN_PER_CATEGORY,
        help=f"Minimum pairs per category (default: {MIN_PER_CATEGORY})",
    )
    parser.add_argument(
        "--skip-balance",
        action="store_true",
        default=False,
        help="Skip the category balancing pass",
    )
    parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        default=False,
        help="Delete checkpoint file and start fresh",
    )

    args = parser.parse_args()

    # Handle checkpoint clearing
    if args.clear_checkpoint:
        if os.path.exists(CHECKPOINT_FILE):
            os.remove(CHECKPOINT_FILE)
            log.info("Checkpoint cleared.")

    resume = not args.no_resume

    run_pipeline(
        resume=resume,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        max_chunks=args.max_chunks,
        target_per_category=args.target_per_category,
        skip_balance=args.skip_balance,
    )


if __name__ == "__main__":
    main()
