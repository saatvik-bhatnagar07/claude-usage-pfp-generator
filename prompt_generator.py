"""Generates image prompts from RPG character sheets.

Primary: Gemini 2.5 Flash generates an evocative pixel art scene prompt.
Fallback: Template-based prompt using class aesthetics if Gemini is unavailable.
"""

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
    "Mage": "arcane crystal orbs and cosmic energy swirls, ethereal glow, deep purple and cyan",
    "Blacksmith": "blazing forge with molten metal and anvil sparks, fiery orange and steel gray",
    "Paladin": "golden shield radiating holy light, structured stonework, gold and white",
    "Rogue": "shadowy figure with electric edges and smoke trails, dark teal and crimson",
    "Scholar": "ancient floating tomes with glowing runes, candlelight amber and deep blue",
    "Warrior": "bold geometric armor with sword and shield, classic red and silver",
}

TIER_INTENSITY = {
    "Apprentice": "simple and muted,",
    "Adventurer": "moderate detail,",
    "Champion": "rich and dynamic,",
    "Legendary": "epic and intensely detailed,",
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
    aesthetic = CLASS_AESTHETICS.get(class_name, CLASS_AESTHETICS["Warrior"])
    intensity = TIER_INTENSITY.get(tier, TIER_INTENSITY["Adventurer"])

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
