# Claude Usage PFP Generator — Design Spec

## Overview

A Python tool that generates a unique techno-flavored pixel art profile picture from daily Claude Code CLI usage stats, using AI image generation (Gemini free tier), and uploads it as the user's Slack profile photo. Runs daily at midnight via cron.

## Data Source

Claude Code stores usage stats at `~/.claude/stats-cache.json`. The file contains:

- `dailyActivity[]` — per-day entries with `date`, `messageCount`, `sessionCount`, `toolCallCount`
- `dailyModelTokens[]` — per-day entries with `date` and `tokensByModel` (model name → token count)

### Input Vector

For a given day, extract:

| Field | Source | Example |
|-------|--------|---------|
| `date` | Entry date string | `"2026-03-12"` |
| `messageCount` | `dailyActivity[].messageCount` | `1907` |
| `sessionCount` | `dailyActivity[].sessionCount` | `9` |
| `toolCallCount` | `dailyActivity[].toolCallCount` | `214` |
| `tokensByModel` | `dailyModelTokens[].tokensByModel` | `{"claude-opus-4-6": 45000}` |

**Fallback behavior:**
- If today has no entry, use yesterday's data.
- If no data at all, use the date string alone as the seed (produces a valid but "idle" image).

## Chaotic Encoding Pipeline

The encoding has an **avalanche effect**: 1 extra message or tool call produces a completely different image prompt. Three stages:

### Stage 1: Canonical String → SHA-256

Serialize the stats into a deterministic string and hash it:

```
input  = "{date}|{messageCount}|{sessionCount}|{toolCallCount}|{tokens_sorted_json}"
digest = SHA-256(input)  # 32 bytes, 256 bits
```

`tokens_sorted_json` is `tokensByModel` serialized with sorted keys for determinism.

SHA-256 provides the avalanche property: flipping one bit in the input flips ~50% of the output bits.

### Stage 2: Hash → Chaotic Expansion (Logistic Map)

Convert the first 8 bytes of the hash to a float seed in [0.1, 0.9] to avoid fixed points:

```
seed = 0.1 + 0.8 * (int.from_bytes(digest[:8], 'big') / (2**64 - 1))
```

This guarantees the seed stays in [0.1, 0.9], avoiding 0.0 and 1.0 where the logistic map collapses to a fixed point.

Run through the logistic map:

```
x_{n+1} = r * x_n * (1 - x_n),  where r = 3.99
```

Iterate N times (one per prompt parameter needed). Each iteration produces a float in (0, 1).

**Why the logistic map at r=3.99:**
- Fully chaotic regime — no periodic orbits
- Sensitive to initial conditions — nearby seeds diverge exponentially
- Deterministic — same seed always produces the same sequence
- Simple to implement and understand

### Stage 3: Floats → Prompt Descriptors

Each float from Stage 2 indexes into a curated pool of visual descriptors:

```
index = floor(float_value * len(pool))
descriptor = pool[index]
```

**The encoding must be well-commented to provide a clear mental model of how each stat maps through the pipeline to a visual parameter.**

#### Descriptor Pools

| Parameter | Pool (examples, not exhaustive) |
|-----------|--------------------------------|
| Primary color | neon cyan, electric magenta, acid green, deep violet, burnt orange, plasma pink, chrome silver, laser red, toxic yellow, midnight blue |
| Secondary color | (same pool, different chaotic iteration) |
| Pattern | fractal circuits, data streams, waveforms, crystalline lattice, neural mesh, interference patterns, topographic lines, voronoi cells, recursive spirals, broken grids |
| Mood | dystopian, ethereal, aggressive, serene, chaotic, hypnotic, industrial, alien, minimalist, explosive |
| Texture | scanlines, noise grain, chrome reflection, holographic, matte, CRT glow, dithered, wireframe, embossed, static |
| Composition | centered mandala, diagonal split, radial burst, layered depth, tiled grid, asymmetric cluster, concentric rings, scattered fragments, vortex, corner anchor |
| Accent element | floating glyphs, binary rain, pulse rings, particle swarm, geometric shards, data nodes, frequency bars, hex fragments, laser beams, quantum dots |

Each pool should have 15-20 entries for sufficient variation.

## Gemini Integration

- **SDK:** `google-genai` Python package
- **Model:** Use the current free-tier image generation model (e.g., `gemini-2.0-flash-exp-image-generation` or `gemini-2.5-flash-preview-image-generation`). Verify against Google AI Studio docs before implementation, as model IDs change frequently.
- **Prompt template:**

```
Generate a pixel art profile picture in a techno aesthetic.
Style: {mood} {texture}.
Primary color: {primary_color}. Secondary color: {secondary_color}.
Pattern: {pattern}.
Composition: {composition}.
Accent: {accent_element}.
Dark background, abstract, no text, no faces, no watermarks.
```

- **Post-processing:** Resize/crop the output to exactly 1024x1024 using Pillow before saving. Gemini does not guarantee output dimensions.
- Save generated image to `output/pfp-{date}.png` for history.

## Slack Upload

- **API:** `users.setPhoto` endpoint (`https://slack.com/api/users.setPhoto`)
- **Auth:** User token with `users.profile:write` scope (stored as `SLACK_USER_TOKEN` env var)
- **Method:** Multipart POST with the image file

Note: This requires a **user token** (starts with `xoxp-`), not a bot token. Bot tokens cannot change user profile photos.

## Configuration

Environment variables (loaded from `.env` file):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | — | Google AI Studio API key |
| `SLACK_USER_TOKEN` | Yes | — | Slack user token with `users.profile:write` |
| `CLAUDE_STATS_PATH` | No | `~/.claude/stats-cache.json` | Override stats file location |

## Project Structure

```
claude-usage-pfp-generator/
├── main.py              # Entry point — orchestrates the pipeline
├── stats_reader.py      # Reads and extracts today's stats from stats-cache.json
├── encoder.py           # SHA-256 + logistic map → prompt descriptors + prompt assembly (well-commented)
├── image_generator.py   # Calls Gemini API, returns image bytes, resizes to 1024x1024
├── slack_uploader.py    # Uploads image to Slack as profile photo
├── pools.py             # Curated descriptor pools (colors, patterns, moods, etc.)
├── requirements.txt     # google-genai, requests, python-dotenv, Pillow
├── .env.example         # Template for env vars
└── output/              # Date-stamped generated PFPs
```

## Scheduling

System cron job running daily at midnight:

```cron
0 0 * * * cd /path/to/claude-usage-pfp-generator && /path/to/venv/bin/python main.py >> /path/to/pfp-generator.log 2>&1
```

Use the virtualenv Python, not system Python — macOS system Python won't have the dependencies. The `.env` is loaded via `python-dotenv` using a path relative to `__file__`, so it works in cron's minimal environment.

The script also works standalone for manual runs and testing:

```bash
python3 main.py           # Generate and upload today's PFP
python3 main.py --dry-run # Generate but don't upload to Slack
```

## Error Handling

- **No stats for today:** Fall back to yesterday, then to date-only seed
- **Gemini API failure:** Log error, exit non-zero (cron will show in mail)
- **Slack upload failure:** Log error, image is still saved locally
- **Missing env vars:** Fail fast with clear error message
