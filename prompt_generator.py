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
