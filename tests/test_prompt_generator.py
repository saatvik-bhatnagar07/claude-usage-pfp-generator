from unittest.mock import MagicMock, patch

from prompt_generator import _build_gemini_prompt, _fallback_prompt, generate_prompt


# ---------------------------------------------------------------------------
# _build_gemini_prompt
# ---------------------------------------------------------------------------

def test_build_gemini_prompt_contains_class_and_tier():
    """Gemini prompt includes class, tier, and score."""
    sheet = {
        "className": "Mage",
        "tier": "Champion",
        "activityScore": 95,
        "stats": {
            "claudeMessages": 80,
            "gitCommits": 5,
            "ideMinutes": 30,
            "terminalCommands": 2,
        },
    }
    result = _build_gemini_prompt(sheet)
    assert "Mage" in result
    assert "Champion" in result
    assert "95" in result


# ---------------------------------------------------------------------------
# _fallback_prompt
# ---------------------------------------------------------------------------

def test_fallback_prompt_contains_class_and_tier():
    """Fallback prompt contains pixel art keywords and class aesthetics."""
    sheet = {
        "className": "Blacksmith",
        "tier": "Legendary",
        "activityScore": 150,
        "stats": {},
    }
    result = _fallback_prompt(sheet)
    assert "pixel art" in result
    assert "Blacksmith" in result.lower() or "forge" in result.lower()
    assert len(result.split()) <= 60


# ---------------------------------------------------------------------------
# generate_prompt
# ---------------------------------------------------------------------------

@patch("prompt_generator.genai")
def test_generate_prompt_uses_gemini(mock_genai):
    """generate_prompt calls Gemini when api_key is provided."""
    mock_response = MagicMock()
    mock_response.text = "a beautiful pixel art mage with cosmic energy"
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client

    sheet = {
        "className": "Mage",
        "tier": "Champion",
        "activityScore": 95,
        "stats": {"claudeMessages": 80},
    }
    result = generate_prompt(sheet, api_key="fake-key")

    mock_client.models.generate_content.assert_called_once()
    assert result == "a beautiful pixel art mage with cosmic energy"


@patch("prompt_generator.genai")
def test_generate_prompt_falls_back_on_gemini_error(mock_genai):
    """generate_prompt falls back to template when Gemini raises an exception."""
    mock_genai.Client.side_effect = Exception("API unavailable")

    sheet = {
        "className": "Rogue",
        "tier": "Adventurer",
        "activityScore": 50,
        "stats": {"terminalCommands": 100},
    }
    result = generate_prompt(sheet, api_key="fake-key")

    assert "pixel art" in result
    assert len(result.split()) <= 60


def test_generate_prompt_falls_back_when_no_api_key():
    """generate_prompt returns a fallback prompt when no api_key is given."""
    sheet = {
        "className": "Scholar",
        "tier": "Apprentice",
        "activityScore": 20,
        "stats": {"ideMinutes": 40},
    }
    result = generate_prompt(sheet, api_key=None)

    assert "pixel art" in result
