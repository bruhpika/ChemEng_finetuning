"""
Category balancer for the Q&A dataset.

After initial generation, checks if any category is underrepresented
(below MIN_PER_CATEGORY) and triggers targeted generation passes
to fill the gaps.
"""

from collections import Counter

from synthetic_qa.config import CATEGORIES, MIN_PER_CATEGORY, log
from synthetic_qa.generator import generate_targeted


def get_category_distribution(pairs: list[dict]) -> dict[str, int]:
    """Count pairs per category."""
    counts = Counter(p.get("category", "unknown") for p in pairs)
    # Ensure all expected categories appear
    return {cat: counts.get(cat, 0) for cat in CATEGORIES}


def check_balance(pairs: list[dict]) -> dict[str, int]:
    """
    Check which categories are below the minimum threshold.

    Returns a dict of category → deficit (how many more pairs needed).
    Empty dict means all categories are balanced.
    """
    distribution = get_category_distribution(pairs)
    deficits: dict[str, int] = {}

    for cat in CATEGORIES:
        count = distribution.get(cat, 0)
        if count < MIN_PER_CATEGORY:
            deficits[cat] = MIN_PER_CATEGORY - count

    if deficits:
        log.info(f"Category deficits detected: {deficits}")
    else:
        log.info("All categories meet minimum threshold ✓")

    return deficits


def balance_dataset(
    pairs: list[dict],
    chunks: list[dict],
) -> list[dict]:
    """
    Balance the dataset by generating additional pairs for underrepresented categories.

    Args:
        pairs: Current list of Q&A pairs
        chunks: Full KB chunk list (for targeted generation)

    Returns:
        Extended list of pairs with balanced categories.
    """
    deficits = check_balance(pairs)

    if not deficits:
        return pairs

    all_new_pairs: list[dict] = []

    for category, needed in deficits.items():
        log.info(f"Balancing '{category}': need {needed} more pairs")

        new_pairs = generate_targeted(
            chunks=chunks,
            target_category=category,
            pairs_needed=needed,
        )

        if new_pairs:
            all_new_pairs.extend(new_pairs)
            log.info(f"  Added {len(new_pairs)} '{category}' pairs")
        else:
            log.warning(f"  Failed to generate additional '{category}' pairs")

    combined = pairs + all_new_pairs
    final_dist = get_category_distribution(combined)
    log.info(f"Final category distribution: {final_dist}")
    log.info(f"Total pairs after balancing: {len(combined)}")

    return combined


def print_distribution_report(pairs: list[dict]) -> str:
    """Generate a human-readable distribution report."""
    dist = get_category_distribution(pairs)
    total = sum(dist.values())

    lines = [
        "=" * 50,
        "CATEGORY DISTRIBUTION REPORT",
        "=" * 50,
    ]

    for cat in CATEGORIES:
        count = dist.get(cat, 0)
        pct = count * 100 // max(total, 1)
        bar = "█" * (pct // 2)
        status = "✅" if count >= MIN_PER_CATEGORY else "⚠️"
        lines.append(f"  {cat:<20s} {count:>5d} ({pct:>2d}%) {bar} {status}")

    lines.append(f"  {'TOTAL':<20s} {total:>5d}")
    lines.append("=" * 50)

    # Software breakdown
    software_dist = Counter(p.get("software", "unknown") for p in pairs)
    lines.append("\nBy Software:")
    for sw, count in software_dist.most_common():
        lines.append(f"  {sw:<20s} {count:>5d}")

    report = "\n".join(lines)
    log.info("\n" + report)
    return report
