# Claude Usage PFP Generator — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a unique techno pixel art PFP from daily Claude Code usage stats via Gemini AI and upload it to Slack.

**Architecture:** Pipeline of small modules: stats reader → chaotic encoder → Gemini image generator → Slack uploader. Each module is a single file with one responsibility, orchestrated by `main.py`.

**Tech Stack:** Python 3, google-genai, requests, python-dotenv, Pillow

**Spec:** `docs/superpowers/specs/2026-03-12-pfp-generator-design.md`

---

## Chunk 1: Project Setup + Core Pipeline (stats → encoding → prompt)

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create requirements.txt**

```
google-genai
requests
python-dotenv
Pillow
```

- [ ] **Step 2: Create .env.example**

```
GEMINI_API_KEY=your-google-ai-studio-api-key
SLACK_USER_TOKEN=xoxp-your-slack-user-token
# Optional: override default stats path
# CLAUDE_STATS_PATH=~/.claude/stats-cache.json
```

- [ ] **Step 3: Create .gitignore**

```
.env
output/
__pycache__/
*.pyc
venv/
.superpowers/
```

- [ ] **Step 4: Create virtualenv and install deps**

```bash
cd /Users/saatvik/src/work/claude-usage-pfp-generator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 5: Create output directory**

```bash
mkdir -p output
```

---

### Task 2: Stats Reader

**Files:**
- Create: `stats_reader.py`
- Create: `tests/test_stats_reader.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_stats_reader.py
import json
import os
import tempfile
from datetime import date, timedelta

from stats_reader import read_stats


def _write_stats(path, daily_activity, daily_model_tokens):
    """Helper to write a stats-cache.json file."""
    data = {
        "version": 2,
        "dailyActivity": daily_activity,
        "dailyModelTokens": daily_model_tokens,
    }
    with open(path, "w") as f:
        json.dump(data, f)


def test_reads_today_stats():
    today = date.today().isoformat()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name
    try:
        _write_stats(
            path,
            [{"date": today, "messageCount": 100, "sessionCount": 3, "toolCallCount": 25}],
            [{"date": today, "tokensByModel": {"claude-opus-4-6": 5000}}],
        )
        stats = read_stats(path)
        assert stats["date"] == today
        assert stats["messageCount"] == 100
        assert stats["sessionCount"] == 3
        assert stats["toolCallCount"] == 25
        assert stats["tokensByModel"] == {"claude-opus-4-6": 5000}
    finally:
        os.unlink(path)


def test_falls_back_to_yesterday():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name
    try:
        _write_stats(
            path,
            [{"date": yesterday, "messageCount": 50, "sessionCount": 2, "toolCallCount": 10}],
            [{"date": yesterday, "tokensByModel": {"claude-opus-4-6": 2000}}],
        )
        stats = read_stats(path)
        assert stats["date"] == yesterday
        assert stats["messageCount"] == 50
    finally:
        os.unlink(path)


def test_falls_back_to_date_only_when_no_data():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name
    try:
        _write_stats(path, [], [])
        stats = read_stats(path)
        assert stats["date"] == date.today().isoformat()
        assert stats["messageCount"] == 0
        assert stats["sessionCount"] == 0
        assert stats["toolCallCount"] == 0
        assert stats["tokensByModel"] == {}
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/saatvik/src/work/claude-usage-pfp-generator
source venv/bin/activate
python -m pytest tests/test_stats_reader.py -v
```

Expected: FAIL — `stats_reader` module not found.

- [ ] **Step 3: Implement stats_reader.py**

```python
# stats_reader.py
"""Reads Claude Code CLI usage stats from stats-cache.json.

Extracts today's daily activity and token data. Falls back to yesterday
if today has no entry, or returns zeroed stats if no data exists at all.
"""

import json
from datetime import date, timedelta
from pathlib import Path


def read_stats(stats_path: str = None) -> dict:
    """Read and return today's usage stats from the Claude stats cache.

    Returns a dict with keys: date, messageCount, sessionCount,
    toolCallCount, tokensByModel.
    """
    if stats_path is None:
        stats_path = str(Path.home() / ".claude" / "stats-cache.json")

    with open(stats_path) as f:
        data = json.load(f)

    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # Build lookup dicts keyed by date
    activity_by_date = {e["date"]: e for e in data.get("dailyActivity", [])}
    tokens_by_date = {e["date"]: e for e in data.get("dailyModelTokens", [])}

    # Try today, then yesterday, then return zeroed stats
    for target_date in [today, yesterday]:
        if target_date in activity_by_date:
            activity = activity_by_date[target_date]
            tokens_entry = tokens_by_date.get(target_date, {})
            return {
                "date": target_date,
                "messageCount": activity.get("messageCount", 0),
                "sessionCount": activity.get("sessionCount", 0),
                "toolCallCount": activity.get("toolCallCount", 0),
                "tokensByModel": tokens_entry.get("tokensByModel", {}),
            }

    # No data at all — return zeroed stats with today's date
    return {
        "date": today,
        "messageCount": 0,
        "sessionCount": 0,
        "toolCallCount": 0,
        "tokensByModel": {},
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_stats_reader.py -v
```

Expected: 3 PASSED.

---

### Task 3: Descriptor Pools

**Files:**
- Create: `pools.py`

- [ ] **Step 1: Create pools.py**

```python
# pools.py
"""Curated descriptor pools for the chaotic encoding pipeline.

Each pool contains 16 entries. The encoder picks one entry per pool
using a chaotic float index. More entries = more visual variety.

These pools define the "visual vocabulary" — every generated PFP
is a combination of one pick from each pool.
"""

COLORS = [
    "neon cyan", "electric magenta", "acid green", "deep violet",
    "burnt orange", "plasma pink", "chrome silver", "laser red",
    "toxic yellow", "midnight blue", "holographic white", "blood crimson",
    "UV purple", "radioactive green", "molten gold", "ice blue",
]

PATTERNS = [
    "fractal circuits", "data streams", "waveforms", "crystalline lattice",
    "neural mesh", "interference patterns", "topographic lines", "voronoi cells",
    "recursive spirals", "broken grids", "signal noise", "matrix rain",
    "circuit traces", "frequency spectrum", "quantum field", "binary cascade",
]

MOODS = [
    "dystopian", "ethereal", "aggressive", "serene",
    "chaotic", "hypnotic", "industrial", "alien",
    "minimalist", "explosive", "haunting", "volatile",
    "transcendent", "corrupted", "pristine", "ominous",
]

TEXTURES = [
    "scanlines", "noise grain", "chrome reflection", "holographic",
    "matte", "CRT glow", "dithered", "wireframe",
    "embossed", "static", "frosted glass", "liquid metal",
    "pixel mosaic", "etched", "glitch artifacts", "vapor trail",
]

COMPOSITIONS = [
    "centered mandala", "diagonal split", "radial burst", "layered depth",
    "tiled grid", "asymmetric cluster", "concentric rings", "scattered fragments",
    "vortex", "corner anchor", "floating islands", "stacked panels",
    "spiral arm", "shattered mirror", "horizon line", "nested frames",
]

ACCENTS = [
    "floating glyphs", "binary rain", "pulse rings", "particle swarm",
    "geometric shards", "data nodes", "frequency bars", "hex fragments",
    "laser beams", "quantum dots", "orbiting sparks", "scan sweeps",
    "constellation lines", "energy arcs", "dot matrix", "static bursts",
]
```

No tests needed — this is purely data.

---

### Task 4: Chaotic Encoder

**Files:**
- Create: `encoder.py`
- Create: `tests/test_encoder.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_encoder.py
from encoder import encode_stats, build_prompt


def test_encode_deterministic():
    """Same input always produces the same descriptors."""
    stats = {
        "date": "2026-03-12",
        "messageCount": 1907,
        "sessionCount": 9,
        "toolCallCount": 214,
        "tokensByModel": {"claude-opus-4-6": 45000},
    }
    result1 = encode_stats(stats)
    result2 = encode_stats(stats)
    assert result1 == result2


def test_encode_avalanche():
    """Changing one stat by 1 should produce different descriptors.

    SHA-256 guarantees ~50% of bits flip for any input change.
    Since the hash completely changes, the logistic map seed changes,
    and the chaotic expansion diverges. We assert the overall result
    is different — the exact number of changed fields depends on
    which pool indices the new floats land in.
    """
    stats_a = {
        "date": "2026-03-12",
        "messageCount": 1907,
        "sessionCount": 9,
        "toolCallCount": 214,
        "tokensByModel": {"claude-opus-4-6": 45000},
    }
    stats_b = {
        "date": "2026-03-12",
        "messageCount": 1908,  # +1 message
        "sessionCount": 9,
        "toolCallCount": 214,
        "tokensByModel": {"claude-opus-4-6": 45000},
    }
    result_a = encode_stats(stats_a)
    result_b = encode_stats(stats_b)
    assert result_a != result_b, "Expected different descriptors for +1 message change"


def test_encode_returns_all_fields():
    stats = {
        "date": "2026-03-12",
        "messageCount": 100,
        "sessionCount": 2,
        "toolCallCount": 10,
        "tokensByModel": {},
    }
    result = encode_stats(stats)
    expected_keys = {
        "primary_color", "secondary_color", "pattern",
        "mood", "texture", "composition", "accent",
    }
    assert set(result.keys()) == expected_keys


def test_encode_zero_stats():
    """Zeroed stats with just a date should still produce valid descriptors."""
    stats = {
        "date": "2026-03-12",
        "messageCount": 0,
        "sessionCount": 0,
        "toolCallCount": 0,
        "tokensByModel": {},
    }
    result = encode_stats(stats)
    assert all(isinstance(v, str) and len(v) > 0 for v in result.values())


def test_build_prompt():
    """build_prompt returns a non-empty string containing the descriptors."""
    descriptors = {
        "primary_color": "neon cyan",
        "secondary_color": "deep violet",
        "pattern": "fractal circuits",
        "mood": "dystopian",
        "texture": "scanlines",
        "composition": "centered mandala",
        "accent": "floating glyphs",
    }
    prompt = build_prompt(descriptors)
    assert "neon cyan" in prompt
    assert "pixel art" in prompt.lower()
    assert "techno" in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_encoder.py -v
```

Expected: FAIL — `encoder` module not found.

- [ ] **Step 3: Implement encoder.py**

```python
# encoder.py
"""Chaotic encoding pipeline: usage stats → image prompt descriptors.

The pipeline has three stages, designed so that even tiny changes in
usage stats produce completely different visual outputs (avalanche effect).

  ┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
  │  Stats dict  │──▶  │  SHA-256 hash     │──▶  │  Logistic map    │──▶ descriptors
  │  (5 fields)  │     │  (avalanche)      │     │  (chaotic expand)│
  └─────────────┘     └──────────────────┘     └──────────────────┘

Stage 1: Serialize stats into a canonical string → SHA-256 hash.
         The hash guarantees that changing even 1 message flips ~50% of bits.

Stage 2: Convert hash bytes into a seed → iterate a logistic map (r=3.99).
         The logistic map is a chaotic system: nearby seeds produce wildly
         divergent sequences. Each iteration gives us one float in (0, 1).

Stage 3: Each float indexes into a curated pool of visual descriptors.
         float 0.73 + pool of 16 items → index 11 → "circuit traces"
"""

import hashlib
import json

import pools


# ---------------------------------------------------------------------------
# Stage 1: Stats → SHA-256 hash
# ---------------------------------------------------------------------------

def _stats_to_hash(stats: dict) -> bytes:
    """Serialize stats deterministically and return the SHA-256 digest.

    The canonical string format is:
        "{date}|{messageCount}|{sessionCount}|{toolCallCount}|{tokens_json}"

    tokens_json uses sorted keys so that {"a": 1, "b": 2} and {"b": 2, "a": 1}
    produce the same hash.
    """
    tokens_json = json.dumps(stats.get("tokensByModel", {}), sort_keys=True)
    canonical = (
        f"{stats['date']}|"
        f"{stats['messageCount']}|"
        f"{stats['sessionCount']}|"
        f"{stats['toolCallCount']}|"
        f"{tokens_json}"
    )
    return hashlib.sha256(canonical.encode()).digest()


# ---------------------------------------------------------------------------
# Stage 2: Hash → chaotic float sequence (logistic map)
# ---------------------------------------------------------------------------

def _logistic_map(digest: bytes, n: int) -> list[float]:
    """Expand a SHA-256 digest into n chaotic floats via the logistic map.

    1. Take the first 8 bytes of the digest as an integer.
    2. Normalize to a seed in [0.1, 0.9] — avoids the fixed points at
       0.0 and 1.0 where the logistic map collapses to zero.
    3. Iterate x_{n+1} = r * x_n * (1 - x_n) with r=3.99 (fully chaotic regime).

    At r=3.99 the map is ergodic and sensitive to initial conditions:
    seeds differing by 1e-15 will diverge within ~50 iterations.
    """
    # Convert first 8 bytes to a float seed in [0.1, 0.9]
    raw = int.from_bytes(digest[:8], "big")
    seed = 0.1 + 0.8 * (raw / (2**64 - 1))

    R = 3.99  # Chaotic regime (r > 3.57 is chaotic, 3.99 ≈ maximum chaos)
    x = seed
    values = []
    for _ in range(n):
        x = R * x * (1 - x)
        values.append(x)
    return values


# ---------------------------------------------------------------------------
# Stage 3: Floats → prompt descriptors
# ---------------------------------------------------------------------------

def _pick(pool: list[str], value: float) -> str:
    """Map a float in (0, 1) to a pool entry.

    index = floor(value * len(pool))
    Clamped to valid range as a safety measure.
    """
    index = min(int(value * len(pool)), len(pool) - 1)
    return pool[index]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# The mapping of chaotic sequence positions to descriptor fields.
# Position 0 → primary_color, position 1 → secondary_color, etc.
# This order is arbitrary but fixed — changing it changes all outputs.
DESCRIPTOR_FIELDS = [
    ("primary_color",   pools.COLORS),
    ("secondary_color", pools.COLORS),
    ("pattern",         pools.PATTERNS),
    ("mood",            pools.MOODS),
    ("texture",         pools.TEXTURES),
    ("composition",     pools.COMPOSITIONS),
    ("accent",          pools.ACCENTS),
]


def encode_stats(stats: dict) -> dict:
    """Full pipeline: stats dict → descriptor dict.

    Returns a dict like:
        {
            "primary_color": "neon cyan",
            "secondary_color": "deep violet",
            "pattern": "fractal circuits",
            "mood": "dystopian",
            "texture": "scanlines",
            "composition": "centered mandala",
            "accent": "floating glyphs",
        }
    """
    # Stage 1: hash the stats
    digest = _stats_to_hash(stats)

    # Stage 2: expand hash into N chaotic floats
    chaotic_values = _logistic_map(digest, len(DESCRIPTOR_FIELDS))

    # Stage 3: map each float to a pool entry
    return {
        name: _pick(pool, chaotic_values[i])
        for i, (name, pool) in enumerate(DESCRIPTOR_FIELDS)
    }


def build_prompt(descriptors: dict) -> str:
    """Assemble the Gemini prompt from descriptor values."""
    return (
        f"Generate a pixel art profile picture in a techno aesthetic. "
        f"Style: {descriptors['mood']} {descriptors['texture']}. "
        f"Primary color: {descriptors['primary_color']}. "
        f"Secondary color: {descriptors['secondary_color']}. "
        f"Pattern: {descriptors['pattern']}. "
        f"Composition: {descriptors['composition']}. "
        f"Accent: {descriptors['accent']}. "
        f"Dark background, abstract, no text, no faces, no watermarks."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_encoder.py -v
```

Expected: 5 PASSED.

---

## Chunk 2: Image Generation + Slack Upload + Main

### Task 5: Image Generator (Gemini)

**Files:**
- Create: `image_generator.py`
- Create: `tests/test_image_generator.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_image_generator.py
from unittest.mock import patch, MagicMock, ANY
from PIL import Image
import io

from image_generator import generate_image


def test_generate_image_returns_resized_png():
    """generate_image should call Gemini and return 1024x1024 PNG bytes."""
    # Create a fake 512x512 image as if Gemini returned it
    fake_img = Image.new("RGB", (512, 512), color=(255, 0, 128))
    buf = io.BytesIO()
    fake_img.save(buf, format="PNG")
    fake_image_bytes = buf.getvalue()

    # Mock the Gemini client
    mock_part = MagicMock()
    mock_part.inline_data.data = fake_image_bytes
    mock_part.text = None

    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [mock_part]

    with patch("image_generator.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        result = generate_image("test prompt", api_key="fake-key")

    # Verify Gemini was called with the prompt
    mock_client.models.generate_content.assert_called_once_with(
        model=ANY,
        contents="test prompt",
        config=ANY,
    )

    # Verify result is 1024x1024 PNG
    img = Image.open(io.BytesIO(result))
    assert img.size == (1024, 1024)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_image_generator.py -v
```

Expected: FAIL — `image_generator` module not found.

- [ ] **Step 3: Look up current Gemini image generation API**

Before implementing, check the current google-genai SDK docs to confirm the correct model ID and API call pattern for image generation. The model ID changes frequently.

```bash
# Check installed SDK version and available models
source venv/bin/activate
python -c "import google.genai; help(google.genai.Client)" 2>/dev/null | head -40
```

Also check context7 docs or Google AI Studio documentation for the current image generation model ID.

- [ ] **Step 4: Implement image_generator.py**

```python
# image_generator.py
"""Generates a techno pixel art image via Gemini's image generation API.

Sends the assembled prompt to Gemini, receives an image back,
and resizes it to exactly 1024x1024 for Slack compatibility.
"""

import io

from google import genai
from google.genai import types
from PIL import Image


# The model ID for Gemini image generation on the free tier.
# This changes frequently — update if the API returns a "model not found" error.
# Check https://ai.google.dev/gemini-api/docs/models for current models.
IMAGE_MODEL = "gemini-2.0-flash-exp-image-generation"


def generate_image(prompt: str, api_key: str) -> bytes:
    """Send prompt to Gemini and return resized 1024x1024 PNG bytes.

    Args:
        prompt: The assembled image generation prompt.
        api_key: Google AI Studio API key.

    Returns:
        PNG image bytes, resized to 1024x1024.

    Raises:
        RuntimeError: If Gemini returns no image in the response.
    """
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )

    # Extract image bytes from response
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            raw_bytes = part.inline_data.data
            return _resize_to_square(raw_bytes, 1024)

    raise RuntimeError("Gemini response contained no image data")


def _resize_to_square(image_bytes: bytes, size: int) -> bytes:
    """Resize an image to an exact square, preserving aspect ratio with cropping."""
    img = Image.open(io.BytesIO(image_bytes))

    # Center-crop to square if not already
    w, h = img.size
    if w != h:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))

    # Resize to target
    img = img.resize((size, size), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_image_generator.py -v
```

Expected: 1 PASSED.

---

### Task 6: Slack Uploader

**Files:**
- Create: `slack_uploader.py`
- Create: `tests/test_slack_uploader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_slack_uploader.py
from unittest.mock import patch, MagicMock

from slack_uploader import upload_profile_photo


def test_upload_calls_slack_api():
    """upload_profile_photo should POST to users.setPhoto with the image."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}

    with patch("slack_uploader.requests.post", return_value=mock_response) as mock_post:
        upload_profile_photo(b"fake-png-bytes", token="xoxp-fake-token")

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "users.setPhoto" in call_args[0][0]
    assert call_args[1]["headers"]["Authorization"] == "Bearer xoxp-fake-token"


def test_upload_raises_on_slack_error():
    """Should raise RuntimeError if Slack returns ok=false."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": False, "error": "invalid_auth"}

    with patch("slack_uploader.requests.post", return_value=mock_response):
        try:
            upload_profile_photo(b"fake-png-bytes", token="xoxp-fake-token")
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "invalid_auth" in str(e)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_slack_uploader.py -v
```

Expected: FAIL — `slack_uploader` module not found.

- [ ] **Step 3: Implement slack_uploader.py**

```python
# slack_uploader.py
"""Uploads an image as the user's Slack profile photo.

Uses the users.setPhoto API endpoint. Requires a user token (xoxp-)
with the users.profile:write scope.
"""

import requests


def upload_profile_photo(image_bytes: bytes, token: str) -> None:
    """Upload image bytes as the authenticated user's Slack profile photo.

    Args:
        image_bytes: PNG image data.
        token: Slack user token (xoxp-...) with users.profile:write scope.

    Raises:
        RuntimeError: If Slack API returns an error.
    """
    response = requests.post(
        "https://slack.com/api/users.setPhoto",
        headers={"Authorization": f"Bearer {token}"},
        files={"image": ("pfp.png", image_bytes, "image/png")},
    )

    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_slack_uploader.py -v
```

Expected: 2 PASSED.

---

### Task 7: Main Entrypoint

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implement main.py**

```python
# main.py
"""Claude Usage PFP Generator — main entry point.

Orchestrates the pipeline:
  1. Read today's Claude Code usage stats
  2. Encode stats into visual descriptors via chaotic pipeline
  3. Generate pixel art image via Gemini
  4. Upload as Slack profile photo

Usage:
  python main.py           # Generate and upload
  python main.py --dry-run # Generate only, save locally, skip Slack upload
"""

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the script's directory (works in cron too)
_script_dir = Path(__file__).resolve().parent
load_dotenv(_script_dir / ".env")

from stats_reader import read_stats
from encoder import encode_stats, build_prompt
from image_generator import generate_image
from slack_uploader import upload_profile_photo


def main():
    parser = argparse.ArgumentParser(description="Generate and upload a daily PFP")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't upload to Slack")
    args = parser.parse_args()

    # Check required env vars
    gemini_key = os.environ.get("GEMINI_API_KEY")
    slack_token = os.environ.get("SLACK_USER_TOKEN")
    stats_path = os.environ.get("CLAUDE_STATS_PATH")

    if not gemini_key:
        print("Error: GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not slack_token and not args.dry_run:
        print("Error: SLACK_USER_TOKEN not set (use --dry-run to skip upload)", file=sys.stderr)
        sys.exit(1)

    # 1. Read stats
    print("Reading Claude usage stats...")
    stats = read_stats(stats_path)
    print(f"  Date: {stats['date']}")
    print(f"  Messages: {stats['messageCount']}, Sessions: {stats['sessionCount']}, Tool calls: {stats['toolCallCount']}")

    # 2. Encode → prompt
    print("Encoding stats into visual descriptors...")
    descriptors = encode_stats(stats)
    for key, value in descriptors.items():
        print(f"  {key}: {value}")

    prompt = build_prompt(descriptors)
    print(f"\nPrompt: {prompt}\n")

    # 3. Generate image
    print("Generating image via Gemini...")
    try:
        image_bytes = generate_image(prompt, api_key=gemini_key)
    except Exception as e:
        print(f"Error: Gemini image generation failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Save locally
    output_dir = _script_dir / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"pfp-{stats['date']}.png"
    output_path.write_bytes(image_bytes)
    print(f"Saved to {output_path}")

    # 4. Upload to Slack
    if args.dry_run:
        print("Dry run — skipping Slack upload")
    else:
        print("Uploading to Slack...")
        try:
            upload_profile_photo(image_bytes, token=slack_token)
            print("Done! Profile photo updated.")
        except Exception as e:
            # Image is already saved locally — log but don't crash
            print(f"Error: Slack upload failed: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASSED.

- [ ] **Step 3: Manual dry-run test**

```bash
# Set just the Gemini key for a dry run
export GEMINI_API_KEY="your-key-here"
python main.py --dry-run
```

Expected: Prints stats, descriptors, prompt, generates an image, saves to `output/pfp-{date}.png`, skips Slack upload.

- [ ] **Step 4: Verify the generated image**

Open `output/pfp-{date}.png` and confirm it's a 1024x1024 techno pixel art image.

---

### Task 8: End-to-end test with Slack upload

- [ ] **Step 1: Set up .env with real credentials**

Copy `.env.example` to `.env` and fill in real `GEMINI_API_KEY` and `SLACK_USER_TOKEN`.

- [ ] **Step 2: Run full pipeline**

```bash
python main.py
```

Expected: Image generated, saved, and Slack profile photo updated.

- [ ] **Step 3: Verify on Slack**

Check your Slack profile to confirm the new PFP is showing.

---

### Task 9: Set up cron job

- [ ] **Step 1: Add cron entry**

```bash
crontab -e
```

Add:
```
0 0 * * * cd /Users/saatvik/src/work/claude-usage-pfp-generator && /Users/saatvik/src/work/claude-usage-pfp-generator/venv/bin/python main.py >> /Users/saatvik/src/work/claude-usage-pfp-generator/output/cron.log 2>&1
```

- [ ] **Step 2: Verify cron is registered**

```bash
crontab -l
```

Expected: Shows the entry above.
