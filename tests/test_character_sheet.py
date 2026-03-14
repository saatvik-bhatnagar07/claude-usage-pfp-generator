from character_sheet import (
    compute_score,
    compute_tier,
    compute_class,
    build_character_sheet,
)


# ---------------------------------------------------------------------------
# compute_score
# ---------------------------------------------------------------------------

def test_score_zero_stats():
    """Zero stats produce a score of 0."""
    stats = {k: 0 for k in [
        "claudeMessages", "gitCommits", "gitLinesChanged",
        "prsOpened", "prsMerged", "reviewsDone",
        "terminalCommands", "ideMinutes",
    ]}
    assert compute_score(stats) == 0.0


def test_score_empty_dict():
    """An empty dict also yields 0 (missing keys treated as 0)."""
    assert compute_score({}) == 0.0


def test_score_known_calculation():
    """10 claude msgs + 2 commits + 100 lines = 10 + 10 + 5 = 25.0."""
    stats = {"claudeMessages": 10, "gitCommits": 2, "gitLinesChanged": 100}
    assert compute_score(stats) == 25.0


def test_score_all_fields():
    """Verify the full weighted sum with every field populated."""
    stats = {
        "claudeMessages": 1,
        "gitCommits": 1,
        "gitLinesChanged": 1,
        "prsOpened": 1,
        "prsMerged": 1,
        "reviewsDone": 1,
        "terminalCommands": 1,
        "ideMinutes": 1,
    }
    expected = 1.0 + 5.0 + 0.05 + 10.0 + 10.0 + 8.0 + 0.3 + 0.5
    assert abs(compute_score(stats) - expected) < 1e-9


# ---------------------------------------------------------------------------
# compute_tier
# ---------------------------------------------------------------------------

def test_tier_zero():
    assert compute_tier(0) == "Apprentice"


def test_tier_30_boundary():
    assert compute_tier(30) == "Apprentice"


def test_tier_31():
    assert compute_tier(31) == "Adventurer"


def test_tier_70_boundary():
    assert compute_tier(70) == "Adventurer"


def test_tier_71():
    assert compute_tier(71) == "Champion"


def test_tier_120_boundary():
    assert compute_tier(120) == "Champion"


def test_tier_121():
    assert compute_tier(121) == "Legendary"


def test_tier_very_high():
    assert compute_tier(9999) == "Legendary"


# ---------------------------------------------------------------------------
# compute_class
# ---------------------------------------------------------------------------

def test_class_mage():
    """Dominant claude messages -> Mage."""
    stats = {"claudeMessages": 100}
    assert compute_class(stats) == "Mage"


def test_class_blacksmith():
    """Dominant git activity -> Blacksmith."""
    stats = {"gitCommits": 20, "gitLinesChanged": 500}
    assert compute_class(stats) == "Blacksmith"


def test_class_paladin():
    """Dominant GitHub activity -> Paladin."""
    stats = {"prsOpened": 10, "prsMerged": 10, "reviewsDone": 10}
    assert compute_class(stats) == "Paladin"


def test_class_rogue():
    """Dominant terminal usage -> Rogue."""
    stats = {"terminalCommands": 500}
    assert compute_class(stats) == "Rogue"


def test_class_scholar():
    """Dominant IDE time -> Scholar."""
    stats = {"ideMinutes": 500}
    assert compute_class(stats) == "Scholar"


def test_class_warrior_all_zeros():
    """All zeros -> Warrior."""
    stats = {k: 0 for k in [
        "claudeMessages", "gitCommits", "gitLinesChanged",
        "prsOpened", "prsMerged", "reviewsDone",
        "terminalCommands", "ideMinutes",
    ]}
    assert compute_class(stats) == "Warrior"


def test_class_warrior_empty():
    """Empty dict -> Warrior."""
    assert compute_class({}) == "Warrior"


def test_class_warrior_balanced():
    """Roughly equal contributions across categories -> Warrior."""
    # Each category contributes ~20% of total
    stats = {
        "claudeMessages": 20,   # 20.0
        "gitCommits": 4,        # 20.0
        "prsOpened": 2,         # 20.0
        "terminalCommands": 67, # 20.1
        "ideMinutes": 40,       # 20.0
    }
    assert compute_class(stats) == "Warrior"


# ---------------------------------------------------------------------------
# build_character_sheet
# ---------------------------------------------------------------------------

def test_build_character_sheet_keys():
    """build_character_sheet returns all expected keys."""
    stats = {"claudeMessages": 50}
    sheet = build_character_sheet(stats)
    assert set(sheet.keys()) == {"tier", "className", "activityScore", "stats"}


def test_build_character_sheet_values():
    """build_character_sheet returns coherent values."""
    stats = {"claudeMessages": 50}
    sheet = build_character_sheet(stats)
    assert sheet["activityScore"] == 50.0
    assert sheet["tier"] == "Adventurer"
    assert sheet["className"] == "Mage"
    assert sheet["stats"] is stats


def test_build_character_sheet_rounding():
    """activityScore is rounded to 1 decimal place."""
    stats = {"gitLinesChanged": 3}  # 3 * 0.05 = 0.15
    sheet = build_character_sheet(stats)
    assert sheet["activityScore"] == 0.1 or sheet["activityScore"] == 0.2
    # Python rounds 0.15 -> 0.1 (banker's rounding), but either is fine
    assert isinstance(sheet["activityScore"], float)


def test_build_character_sheet_legendary():
    """High stats produce Legendary tier."""
    stats = {"prsOpened": 13}  # 130
    sheet = build_character_sheet(stats)
    assert sheet["tier"] == "Legendary"
    assert sheet["activityScore"] == 130.0
