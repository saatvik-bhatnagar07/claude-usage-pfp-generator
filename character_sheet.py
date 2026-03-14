"""Maps developer activity stats to an RPG character sheet.

Computes an activity score from weighted stats, assigns a power tier,
and determines a character class based on the dominant activity source.
"""

WEIGHTS = {
    "claudeMessages": 1.0,
    "gitCommits": 5.0,
    "gitLinesChanged": 0.05,
    "prsOpened": 10.0,
    "prsMerged": 10.0,
    "reviewsDone": 8.0,
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


def build_character_sheet(stats: dict) -> dict:
    """Build a complete character sheet from raw activity stats."""
    score = compute_score(stats)
    return {
        "tier": compute_tier(score),
        "className": compute_class(stats),
        "activityScore": round(score, 1),
        "stats": stats,
    }
