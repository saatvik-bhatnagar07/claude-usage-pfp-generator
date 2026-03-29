"""Maps developer activity stats to an RPG character sheet.

Computes an activity score from weighted stats, assigns a power tier,
and determines a character class based on the dominant activity source.
"""

import random

WEIGHTS = {
    "claudeMessages": 1.0,
    "gitCommits": 2.0,
    "gitLinesChanged": 0.01,
    "prsOpened": 2.0,
    "prsMerged": 2.0,
    "reviewsDone": 1.5,
    "terminalCommands": 0.3,
    "ideMinutes": 0.5,
}

TIERS = [
    (30, "Apprentice"),
    (70, "Adventurer"),
    (120, "Champion"),
]

CATEGORIES = {
    "claude": (["claudeMessages"], "Mage"),
    "git": (["gitCommits", "gitLinesChanged"], "Blacksmith"),
    "github": (["prsOpened", "prsMerged", "reviewsDone"], "Paladin"),
    "terminal": (["terminalCommands"], "Rogue"),
    "ide": (["ideMinutes"], "Scholar"),
}


def compute_score(stats: dict) -> float:
    """Return the weighted activity score for the given stats."""
    return sum(stats.get(k, 0) * w for k, w in WEIGHTS.items())


def compute_tier(score: float) -> str:
    """Map a numeric score to a power-tier label."""
    for threshold, tier in TIERS:
        if score <= threshold:
            return tier
    return "Legendary"


def compute_class(stats: dict) -> str:
    """Determine RPG class from the dominant activity category."""
    total = compute_score(stats)
    if total == 0:
        return "Warrior"

    best_score = 0.0
    best_class = "Warrior"
    for _cat, (keys, class_name) in CATEGORIES.items():
        cat_score = sum(stats.get(k, 0) * WEIGHTS[k] for k in keys)
        if cat_score > best_score:
            best_score = cat_score
            best_class = class_name

    if best_score / total <= 0.4:
        return "Warrior"
    return best_class


def compute_secondary_class(stats: dict, primary_class: str) -> str | None:
    """Pick a secondary class via weighted random from non-primary, non-zero categories.

    Categories with a score of zero are excluded. The remaining candidates
    are sampled proportionally to their weighted scores, so more active
    categories appear as secondary more often without being guaranteed.
    Returns None when no eligible secondary exists.
    """
    candidates = []
    weights = []
    for _cat, (keys, class_name) in CATEGORIES.items():
        if class_name == primary_class:
            continue
        # Note: when primary_class is "Warrior", it is not in CATEGORIES so no
        # candidate is ever suppressed here — all non-zero categories are eligible.
        score = sum(stats.get(k, 0) * WEIGHTS[k] for k in keys)
        if score > 0:
            candidates.append(class_name)
            weights.append(score)

    if not candidates:
        return None

    total = sum(weights)
    r = random.random() * total
    cumulative = 0.0
    for cls, w in zip(candidates, weights):
        cumulative += w
        if r <= cumulative:
            return cls
    # Safety fallback: unreachable in practice because random.random() is in
    # [0.0, 1.0) so r < total, meaning the loop above always returns before here.
    return candidates[-1]


def build_character_sheet(stats: dict) -> dict:
    """Build a complete character sheet from raw activity stats."""
    score = compute_score(stats)
    primary = compute_class(stats)
    return {
        "tier": compute_tier(score),
        "className": primary,
        "secondaryClass": compute_secondary_class(stats, primary),
        "activityScore": round(score, 1),
        "stats": stats,
    }
