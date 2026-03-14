"""Generates image prompts from RPG character sheets.

Primary: Gemini 2.5 Flash generates an evocative pixel art scene prompt.
Fallback: Template-based prompt using class aesthetics if Gemini is unavailable.
"""

import random

from google import genai
from google.genai import types

SYSTEM_PROMPT = (
    "You are a pixel art scene designer for retro RPG profile pictures.\n\n"
    "Given a developer's daily \"character sheet\" (RPG class, power tier, and activity stats), "
    "write a single image generation prompt for a retro 16-bit pixel art portrait.\n\n"
    "Rules:\n"
    "- Maximum 60 words (CLIP token limit)\n"
    "- Must be retro 16-bit pixel art style with dark background and visible pixels\n"
    "- Ground the visual in the RPG class aesthetic\n"
    "- Reflect the power tier in visual intensity and complexity\n"
    "- No text or UI elements in the image\n"
    "- Output ONLY the prompt, nothing else"
)

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


def _build_gemini_prompt(sheet: dict) -> str:
    """Build the user prompt string for Gemini from the character sheet."""
    class_name = sheet["className"]
    tier = sheet["tier"]
    score = sheet["activityScore"]

    # Top 3 stats by value
    stats = sheet.get("stats", {})
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:3]
    top_stats = ", ".join(f"{k}={v}" for k, v in sorted_stats)

    return (
        f"Class: {class_name}\n"
        f"Tier: {tier}\n"
        f"Activity score: {score}/200\n"
        f"Top stats: {top_stats}"
    )


def _fallback_prompt(sheet: dict) -> str:
    """Template-based RPG prompt using CLASS_AESTHETICS and TIER_INTENSITY."""
    class_name = sheet["className"]
    tier = sheet["tier"]
    aesthetic = random.choice(CLASS_AESTHETICS.get(class_name, CLASS_AESTHETICS["Warrior"]))
    intensity = random.choice(TIER_INTENSITY.get(tier, TIER_INTENSITY["Adventurer"]))

    return (
        f"retro 16-bit pixel art, {intensity} RPG {class_name} character, "
        f"{aesthetic}, dark background, large visible pixels, retro gaming aesthetic"
    )


def generate_prompt(sheet: dict, api_key: str | None = None) -> str:
    """Generate an image prompt from a character sheet.

    Uses Gemini 2.5 Flash if an api_key is provided, otherwise falls back
    to a template-based prompt.
    """
    if not api_key:
        return _fallback_prompt(sheet)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=_build_gemini_prompt(sheet),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=150,
                temperature=0.9,
            ),
        )
        if not response.text:
            return _fallback_prompt(sheet)
        return response.text
    except Exception:
        return _fallback_prompt(sheet)
