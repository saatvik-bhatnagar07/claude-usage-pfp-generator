from character_sheet import (
    compute_score,
    compute_tier,
    compute_class,
    compute_secondary_class,
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
    """10 claude msgs + 2 commits + 100 lines = 10 + 4 + 1 = 15.0."""
    stats = {"claudeMessages": 10, "gitCommits": 2, "gitLinesChanged": 100}
    assert compute_score(stats) == 15.0


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
    expected = 1.0 + 2.0 + 0.01 + 2.0 + 2.0 + 1.5 + 0.3 + 0.5
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
    stats = {
        "claudeMessages": 20,   # 20.0
        "gitCommits": 10,       # 20.0
        "prsOpened": 10,        # 20.0
        "terminalCommands": 67, # 20.1
        "ideMinutes": 40,       # 20.0
    }
    assert compute_class(stats) == "Warrior"


# ---------------------------------------------------------------------------
# compute_secondary_class
# ---------------------------------------------------------------------------

def test_secondary_class_none_when_all_zero():
    """No non-zero non-primary categories -> None."""
    assert compute_secondary_class({}, "Scholar") is None


def test_secondary_class_none_when_only_primary_nonzero():
    """Only the primary category has score -> no valid secondary."""
    stats = {"ideMinutes": 500}
    assert compute_secondary_class(stats, "Scholar") is None


def test_secondary_class_returns_only_eligible():
    """When only one other category is non-zero, always returns that class."""
    stats = {"ideMinutes": 500, "claudeMessages": 100}
    result = compute_secondary_class(stats, "Scholar")
    assert result == "Mage"


def test_secondary_class_never_returns_primary():
    """Secondary class is never the same as the primary."""
    stats = {
        "ideMinutes": 500, "claudeMessages": 100,
        "gitCommits": 5, "terminalCommands": 50,
    }
    for _ in range(30):
        result = compute_secondary_class(stats, "Scholar")
        assert result != "Scholar"


def test_secondary_class_only_from_nonzero_categories():
    """Zero-score categories are never returned as secondary."""
    # git and github are zero; only Mage and Rogue are eligible besides Scholar
    stats = {"ideMinutes": 500, "claudeMessages": 100, "terminalCommands": 50}
    valid = {"Mage", "Rogue"}
    for _ in range(30):
        result = compute_secondary_class(stats, "Scholar")
        assert result in valid


# ---------------------------------------------------------------------------
# build_character_sheet
# ---------------------------------------------------------------------------

def test_build_character_sheet_keys():
    """build_character_sheet returns all expected keys including secondaryClass."""
    stats = {"claudeMessages": 50}
    sheet = build_character_sheet(stats)
    assert set(sheet.keys()) == {"tier", "className", "secondaryClass", "activityScore", "stats"}


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
    stats = {"gitLinesChanged": 3}  # 3 * 0.01 = 0.03
    sheet = build_character_sheet(stats)
    assert sheet["activityScore"] == 0.0
    assert isinstance(sheet["activityScore"], float)


def test_build_character_sheet_legendary():
    """High stats produce Legendary tier."""
    stats = {"prsOpened": 65}  # 65 * 2.0 = 130
    sheet = build_character_sheet(stats)
    assert sheet["tier"] == "Legendary"
    assert sheet["activityScore"] == 130.0
