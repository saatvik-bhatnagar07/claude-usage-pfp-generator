# Prompt Variety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generated images visually distinct day-to-day even when tier and primary class stay the same, by adding a weighted-random secondary class and a stat-seeded deterministic primary aesthetic.

**Architecture:** `character_sheet.py` gains a `compute_secondary_class` function that does a weighted random draw from non-primary, non-zero-score categories. `prompt_generator.py` uses a stat-derived seed for the primary aesthetic (deterministic per day's stats) and module-level `random` for the secondary element and scene modifier (fresh each run).

**Tech Stack:** Python stdlib only — `hashlib` for stat seed, `random.Random` for seeded draws, `random.choice` for novel draws.

---

### Task 1: Add secondary class to character sheet

**Files:**
- Modify: `character_sheet.py`
- Modify: `tests/test_character_sheet.py`

- [ ] **Step 1: Write failing tests for `compute_secondary_class`**

Add to `tests/test_character_sheet.py` (and update the existing `test_build_character_sheet_keys`):

```python
from character_sheet import (
    compute_score,
    compute_tier,
    compute_class,
    compute_secondary_class,
    build_character_sheet,
)


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


def test_build_character_sheet_keys():
    """build_character_sheet returns all expected keys including secondaryClass."""
    stats = {"claudeMessages": 50}
    sheet = build_character_sheet(stats)
    assert set(sheet.keys()) == {"tier", "className", "secondaryClass", "activityScore", "stats"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/saatvik/src/work/claude-usage-pfp-generator && \
  source venv/bin/activate && \
  python -m pytest tests/test_character_sheet.py::test_secondary_class_none_when_all_zero \
    tests/test_character_sheet.py::test_build_character_sheet_keys -v
```

Expected: FAIL — `ImportError: cannot import name 'compute_secondary_class'`

- [ ] **Step 3: Implement `compute_secondary_class` and update `build_character_sheet`**

Replace `character_sheet.py` entirely:

```python
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
```

- [ ] **Step 4: Run all character sheet tests**

```bash
cd /Users/saatvik/src/work/claude-usage-pfp-generator && \
  source venv/bin/activate && \
  python -m pytest tests/test_character_sheet.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/saatvik/src/work/claude-usage-pfp-generator && \
  git add character_sheet.py tests/test_character_sheet.py && \
  git commit -m "feat: add weighted-random secondary class to character sheet"
```

---

### Task 2: Stat-seeded primary + random secondary and scene in prompt generator

**Files:**
- Modify: `prompt_generator.py`
- Modify: `tests/test_prompt_generator.py`

- [ ] **Step 1: Write failing tests**

Replace `tests/test_prompt_generator.py` with:

```python
from unittest.mock import patch

from prompt_generator import generate_prompt


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


def test_generate_prompt_primary_is_deterministic():
    """Same stats always produce the same primary aesthetic and intensity.

    The scene modifier (module-level random.choice) is patched to a fixed value
    so only the stat-seeded parts contribute to variation — confirming they don't.
    """
    stats = {"ideMinutes": 400}
    sheet = _sheet("Scholar", "Legendary", stats, secondary=None)
    with patch("prompt_generator.random") as mock_rng:
        mock_rng.choice.return_value = "at dusk with long shadows"
        p1 = generate_prompt(sheet)
        p2 = generate_prompt(sheet)
    assert p1 == p2


def test_generate_prompt_scene_varies_across_runs():
    """Scene modifier uses module-level random so produces variety across runs."""
    sheet = _sheet("Scholar", "Legendary", {"ideMinutes": 400}, secondary=None)
    results = {generate_prompt(sheet) for _ in range(40)}
    assert len(results) > 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/saatvik/src/work/claude-usage-pfp-generator && \
  source venv/bin/activate && \
  python -m pytest tests/test_prompt_generator.py -v
```

Expected: `test_generate_prompt_includes_secondary_when_present` and `test_generate_prompt_primary_is_deterministic` FAIL.

- [ ] **Step 3: Implement updated `prompt_generator.py`**

Replace `prompt_generator.py` entirely:

```python
"""Generates image prompts from RPG character sheets using template-based aesthetics."""

import hashlib
import random
from random import Random

CLASS_AESTHETICS = {
    "Mage": [
        "arcane crystal orbs and cosmic energy swirls, ethereal glow, deep purple and cyan",
        "swirling astral vortex with enchanted staves, mystic nebula aura, violet and teal",
        "floating spell glyphs orbiting a hooded figure, crackling arcane lightning, indigo and silver",
        "crystalline mana shards erupting with starfire, shimmering aurora, deep blue and magenta",
        "ancient grimoire unleashing spectral flames, moonlit arcane circle, midnight purple and gold",
    ],
    "Blacksmith": [
        "blazing forge with molten metal and anvil sparks, fiery orange and steel gray",
        "glowing crucible pouring liquid steel, ember-lit workshop, copper and charcoal",
        "massive war hammer striking red-hot iron on an anvil, shower of sparks, amber and gunmetal",
        "enchanted blade cooling in oil with rising steam, furnace glow, burnt sienna and iron",
        "bellows feeding a roaring forge fire, chains and molten rivets, flame red and dark bronze",
    ],
    "Paladin": [
        "golden shield radiating holy light, structured stonework, gold and white",
        "luminous sword raised beneath a cathedral rose window, divine radiance, ivory and amber",
        "armored sentinel with wings of light, marble pillars and holy banners, pearl and gold",
        "blessed warhammer glowing with sacred runes, stained glass halo, silver and celestial blue",
        "knight kneeling in prayer with a radiant aura, sunlit temple, warm gold and platinum",
    ],
    "Rogue": [
        "shadowy figure with electric edges and smoke trails, dark teal and crimson",
        "twin daggers glinting in moonlight, rooftop silhouette, midnight blue and scarlet",
        "cloaked assassin vanishing into pixelated shadows, poison vials, emerald green and black",
        "lockpicks and scattered coins on a dimly lit table, flickering torchlight, dark purple and bronze",
        "hooded figure perched on a gargoyle in rain, neon city glow below, steel gray and electric violet",
    ],
    "Scholar": [
        "ancient floating tomes with glowing runes, candlelight amber and deep blue",
        "towering library with enchanted scrolls and astrolabe, warm lamplight, mahogany and gold",
        "alchemist table with bubbling potions and star charts, quill writing by itself, sepia and emerald",
        "crystal ball revealing constellations, stacked manuscripts, midnight blue and warm amber",
        "sage meditating among floating geometric theorems, soft lantern glow, parchment cream and navy",
    ],
    "Warrior": [
        "bold geometric armor with sword and shield, classic red and silver",
        "battle-scarred champion raising a war axe, tattered banner flying, crimson and iron",
        "dual-wielding warrior in spiked plate armor, arena dust clouds, blood red and dark steel",
        "shield wall formation with crossed spears, war drums and fire, bronze and deep maroon",
        "legendary greatsword planted in cracked earth, storm clouds gathering, gunmetal and ember orange",
    ],
}

TIER_INTENSITY = {
    "Apprentice": [
        "simple and muted,",
        "soft and understated,",
        "faintly glowing, low detail,",
        "humble and subdued,",
        "dim and sparse,",
    ],
    "Adventurer": [
        "moderate detail,",
        "crisp and balanced,",
        "steady and well-defined,",
        "clear with emerging complexity,",
        "polished with mild flourishes,",
    ],
    "Champion": [
        "rich and dynamic,",
        "vibrant with intricate detail,",
        "bold and layered,",
        "striking with elaborate patterns,",
        "powerful and finely crafted,",
    ],
    "Legendary": [
        "epic and intensely detailed,",
        "overwhelmingly radiant, maximum detail,",
        "transcendent and awe-inspiring,",
        "mythic grandeur with extreme intricacy,",
        "blinding brilliance, godlike presence,",
    ],
}

SCENE_MODIFIERS = [
    "at dusk with long shadows",
    "under a full moon",
    "in the golden hour light",
    "during a thunderstorm",
    "bathed in dawn light",
    "in a misty atmosphere",
    "under starlit skies",
    "in foggy conditions",
    "at high noon with harsh light",
    "under aurora borealis",
]


def _stat_seed(stats: dict) -> int:
    """Derive a deterministic integer seed from today's stat values."""
    from character_sheet import WEIGHTS
    key = "|".join(
        f"{k}={int(stats.get(k, 0))}"
        for k in sorted(WEIGHTS.keys())
    )
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % (2 ** 32)


def generate_prompt(sheet: dict) -> str:
    """Generate a template-based image prompt from a character sheet.

    Primary aesthetic and tier intensity are stat-seeded (deterministic per
    day's stats). Secondary class element and scene modifier are drawn fresh
    from module-level random on every call, ensuring novelty across runs.
    """
    class_name = sheet["className"]
    tier = sheet["tier"]
    secondary = sheet.get("secondaryClass")
    stats = sheet["stats"]

    # Deterministic picks — same stats always produce the same base prompt
    rng = Random(_stat_seed(stats))
    aesthetic = rng.choice(CLASS_AESTHETICS.get(class_name, CLASS_AESTHETICS["Warrior"]))
    intensity = rng.choice(TIER_INTENSITY.get(tier, TIER_INTENSITY["Adventurer"]))

    # Novel picks — fresh each run
    scene = random.choice(SCENE_MODIFIERS)

    if secondary:
        sec_element = random.choice(CLASS_AESTHETICS.get(secondary, CLASS_AESTHETICS["Warrior"]))
        return (
            f"retro 16-bit pixel art, {intensity} RPG {class_name} character, "
            f"{aesthetic}, with hints of {secondary}: {sec_element}, "
            f"{scene}, dark background, large visible pixels, retro gaming aesthetic"
        )
    return (
        f"retro 16-bit pixel art, {intensity} RPG {class_name} character, "
        f"{aesthetic}, {scene}, dark background, large visible pixels, retro gaming aesthetic"
    )
```

- [ ] **Step 4: Run all prompt generator tests**

```bash
cd /Users/saatvik/src/work/claude-usage-pfp-generator && \
  source venv/bin/activate && \
  python -m pytest tests/test_prompt_generator.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/saatvik/src/work/claude-usage-pfp-generator && \
  source venv/bin/activate && \
  python -m pytest -v
```

Expected: All tests PASS.

- [ ] **Step 6: Smoke test end-to-end**

```bash
cd /Users/saatvik/src/work/claude-usage-pfp-generator && \
  source venv/bin/activate && \
  python main.py --dry-run
```

Expected output includes lines like:
```
  Class: Scholar
  Tier: Legendary
  Score: ...
  Prompt: retro 16-bit pixel art, ... RPG Scholar character, ..., with hints of Mage: ..., at dusk with long shadows, dark background, large visible pixels, retro gaming aesthetic
```
(Secondary class and scene modifier will vary per run.)

- [ ] **Step 7: Commit**

```bash
cd /Users/saatvik/src/work/claude-usage-pfp-generator && \
  git add prompt_generator.py tests/test_prompt_generator.py && \
  git commit -m "feat: stat-seeded primary aesthetic, random secondary class and scene modifier"
```
