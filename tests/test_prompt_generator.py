from unittest.mock import patch

from prompt_generator import _stat_seed, generate_prompt


def _sheet(class_name, tier, stats, secondary=None):
    return {
        "className": class_name,
        "tier": tier,
        "activityScore": 50,
        "stats": stats,
        "secondaryClass": secondary,
    }


def test_generate_prompt_contains_class_and_pixel_art():
    sheet = _sheet("Blacksmith", "Legendary", {})
    result = generate_prompt(sheet)
    assert "pixel art" in result
    assert "Blacksmith" in result
    assert len(result.split()) <= 80


def test_generate_prompt_all_classes():
    for class_name in ["Mage", "Blacksmith", "Paladin", "Rogue", "Scholar", "Warrior"]:
        result = generate_prompt(_sheet(class_name, "Adventurer", {}))
        assert class_name in result
        assert "pixel art" in result


def test_generate_prompt_all_tiers():
    for tier in ["Apprentice", "Adventurer", "Champion", "Legendary"]:
        result = generate_prompt(_sheet("Warrior", tier, {}))
        assert "pixel art" in result


def test_generate_prompt_unknown_class_falls_back_to_warrior():
    result = generate_prompt(_sheet("Unknown", "Adventurer", {}))
    assert "pixel art" in result


def test_generate_prompt_includes_secondary_when_present():
    """Secondary class name and 'hints of' phrase appear in the prompt."""
    sheet = _sheet("Scholar", "Legendary", {"ideMinutes": 400, "claudeMessages": 100}, secondary="Mage")
    result = generate_prompt(sheet)
    assert "hints of Mage" in result


def test_generate_prompt_no_secondary_phrase_when_none():
    """'hints of' does not appear when secondaryClass is None."""
    sheet = _sheet("Scholar", "Legendary", {"ideMinutes": 400}, secondary=None)
    result = generate_prompt(sheet)
    assert "hints of" not in result


def test_stat_seed_is_deterministic():
    """Same stats always produce the same seed."""
    stats = {"ideMinutes": 400, "claudeMessages": 100}
    assert _stat_seed(stats) == _stat_seed(stats)


def test_stat_seed_differs_for_different_stats():
    """Different stat values produce different seeds."""
    stats_a = {"ideMinutes": 400}
    stats_b = {"ideMinutes": 999}
    assert _stat_seed(stats_a) != _stat_seed(stats_b)


def test_generate_prompt_primary_is_deterministic():
    """Same stats always produce the same primary aesthetic and intensity.

    Only the module-level random.choice (scene + secondary) is patched to a
    fixed value. The stat-seeded Random instance is unaffected, so this test
    genuinely verifies that the seeded path is deterministic.
    """
    stats = {"ideMinutes": 400}
    sheet = _sheet("Scholar", "Legendary", stats, secondary=None)
    with patch("prompt_generator.random.choice", return_value="at dusk with long shadows"):
        p1 = generate_prompt(sheet)
        p2 = generate_prompt(sheet)
    assert p1 == p2


def test_generate_prompt_scene_varies_across_runs():
    """Scene modifier uses module-level random so produces variety across runs."""
    sheet = _sheet("Scholar", "Legendary", {"ideMinutes": 400}, secondary=None)
    results = {generate_prompt(sheet) for _ in range(40)}
    assert len(results) > 1
