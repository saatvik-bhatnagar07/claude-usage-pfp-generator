from prompt_generator import generate_prompt


def test_generate_prompt_contains_class_and_pixel_art():
    sheet = {
        "className": "Blacksmith",
        "tier": "Legendary",
        "activityScore": 150,
        "stats": {},
    }
    result = generate_prompt(sheet)
    assert "pixel art" in result
    assert "Blacksmith" in result
    assert len(result.split()) <= 60


def test_generate_prompt_all_classes():
    for class_name in ["Mage", "Blacksmith", "Paladin", "Rogue", "Scholar", "Warrior"]:
        sheet = {"className": class_name, "tier": "Adventurer", "activityScore": 50, "stats": {}}
        result = generate_prompt(sheet)
        assert class_name in result
        assert "pixel art" in result


def test_generate_prompt_all_tiers():
    for tier in ["Apprentice", "Adventurer", "Champion", "Legendary"]:
        sheet = {"className": "Warrior", "tier": tier, "activityScore": 50, "stats": {}}
        result = generate_prompt(sheet)
        assert "pixel art" in result


def test_generate_prompt_unknown_class_falls_back_to_warrior():
    sheet = {"className": "Unknown", "tier": "Adventurer", "activityScore": 50, "stats": {}}
    result = generate_prompt(sheet)
    assert "pixel art" in result
