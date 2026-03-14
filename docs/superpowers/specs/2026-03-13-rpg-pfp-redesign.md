# RPG-Themed Meaningful PFP Redesign

## Goal

Transform the PFP generator from producing random abstract images into meaningful RPG character portraits that reflect daily developer activity. Teammates can glance at a PFP and understand the person's work style and intensity that day.

## Architecture

```
┌─────────────┐   ┌─────────────────┐   ┌───────────────┐   ┌────────────┐   ┌────────┐
│ Stats        │──▶│ Character Sheet  │──▶│ Gemini 2.5    │──▶│ SDXL Turbo │──▶│ Slack  │
│ (5 sources)  │   │ (tier + class)   │   │ Flash (prompt) │   │ (image)    │   │ Upload │
└─────────────┘   └─────────────────┘   └───────────────┘   └────────────┘   └────────┘
```

The chaotic encoding pipeline (SHA-256 + logistic map) is replaced with a deterministic stat-to-archetype mapping + LLM-generated prompt for creative variety.

## Stats Collection

### Sources

All stats are for the current day (today so far, falling back to yesterday if today is empty).

**1. Claude Code** (existing)
- Source: `~/.claude/history.jsonl`
- Metrics: messageCount, sessionCount

**2. Git activity**
- Source: all git repos under `~/src/work/` (recursive scan for `.git` dirs, max depth 3)
- Metrics: commitCount, linesChanged (additions + deletions)
- Method: `git log --after="YYYY-MM-DDT00:00:00" --author=$(git config user.email) --format=oneline` for count, `git diff --shortstat` for lines

**3. PRs and Code Reviews**
- Source: GitHub via `gh` CLI
- Metrics: prsOpened, prsMerged, reviewsDone
- Method: `gh search prs --author=@me --created=YYYY-MM-DD`, `gh search prs --reviewed-by=@me --updated=YYYY-MM-DD`
- Graceful fallback: if `gh` is not installed or not authed, these stats are 0

**4. Terminal activity**
- Source: `~/.zsh_history`
- Metrics: commandCount (commands executed today)
- Method: zsh extended history format has timestamps (`: 1710300000:0;command`). Count entries whose timestamp falls within today.

**5. JetBrains IDE**
- Source: `~/Library/Logs/JetBrains/*/idea.log` and `*/pycharm.log` (most recent version dirs)
- Metrics: ideMinutes (approximate active minutes)
- Method: count log entries with today's date, bucket into 1-minute windows, count distinct windows as active minutes
- Graceful fallback: if no JetBrains logs found, ideMinutes is 0

### Stats Output Format

```python
{
    "date": "2026-03-13",
    # Claude
    "claudeMessages": 88,
    "claudeSessions": 11,
    # Git
    "gitCommits": 5,
    "gitLinesChanged": 340,
    # GitHub
    "prsOpened": 1,
    "prsMerged": 2,
    "reviewsDone": 3,
    # Terminal
    "terminalCommands": 150,
    # IDE
    "ideMinutes": 120,
}
```

## Character Sheet

### Tier (overall power level)

Based on a weighted activity score:

```
score = (claudeMessages * 1.0)
      + (gitCommits * 5.0)
      + (gitLinesChanged * 0.05)
      + (prsOpened * 10.0)
      + (prsMerged * 10.0)
      + (reviewsDone * 8.0)
      + (terminalCommands * 0.3)
      + (ideMinutes * 0.5)
```

Tier thresholds (calibrated to user's self-reported heavy day of ~88 Claude messages):

| Score Range | Tier | Visual Energy |
|-------------|------|---------------|
| 0–30 | Apprentice | Simple, muted, calm |
| 31–70 | Adventurer | Moderate detail, warmer palette |
| 71–120 | Champion | Rich, dynamic, vibrant |
| 121+ | Legendary | Intense, rare colors, epic composition |

### Class (dominant work style)

Determined by which stat category contributes the most to the total score:

| Dominant Source | Class | Visual Aesthetic |
|----------------|-------|-----------------|
| Claude (messages) | Mage | Arcane runes, cosmic energy, ethereal glow, crystal orbs |
| Git (commits + lines) | Blacksmith | Forge fire, molten metal, anvil sparks, mechanical gears |
| PRs + Reviews | Paladin | Golden shields, holy light, structured architecture, banners |
| Terminal (commands) | Rogue | Shadowy, fragmented, electric edges, dual daggers, smoke |
| IDE (minutes) | Scholar | Ancient tomes, floating runes, candlelight, ink and quill |
| Balanced (no clear dominant) | Warrior | Bold geometric armor, sword and shield, classic hero stance |

"Balanced" means no single category exceeds 40% of total score.

### Character Sheet Output

```python
{
    "tier": "Champion",
    "className": "Mage",
    "dominantActivity": "claude",
    "activityScore": 95,
    "stats": { ... },  # raw stats dict
}
```

## Prompt Generation (Gemini 2.5 Flash)

### API Setup

- Model: `gemini-2.5-flash`
- API key: `GEMINI_API_KEY` env var (loaded from .env)
- Single API call per run

### System Prompt

```
You are a pixel art scene designer for retro RPG profile pictures.

Given a developer's daily "character sheet" (RPG class, power tier, and activity stats),
write a single image generation prompt for a retro 16-bit pixel art portrait.

Rules:
- Maximum 60 words (CLIP token limit)
- Must be retro 16-bit pixel art style with dark background and visible pixels
- Ground the visual in the RPG class aesthetic
- Reflect the power tier in visual intensity and complexity
- No text or UI elements in the image
- Output ONLY the prompt, nothing else
```

### User Prompt

```
Character Sheet:
- Class: {className}
- Tier: {tier}
- Activity Score: {activityScore}/200
- Top stats: {top 3 stats by contribution}

Write the image prompt.
```

### Fallback

If Gemini fails (network, quota, etc.), fall back to a template-based prompt using the class and tier descriptors (similar to current approach but RPG-themed). The pipeline should never fail just because the LLM is unavailable.

## File Changes

### New files
- `stats_collector.py` — unified stats collection from all 5 sources
- `character_sheet.py` — stats → tier + class mapping
- `prompt_generator.py` — Gemini integration + fallback templates

### Modified files
- `main.py` — rewire pipeline to use new modules
- `requirements.txt` — add `google-genai` (Gemini SDK)
- `.env.example` — add `GEMINI_API_KEY`

### Removed/deprecated
- `encoder.py` — replaced by character_sheet.py + prompt_generator.py
- `pools.py` — replaced by RPG class descriptors in prompt_generator.py

### Unchanged
- `image_generator.py` — still takes a prompt string, generates via SDXL Turbo
- `slack_uploader.py` — unchanged
- `slack_auth.py` — unchanged
- `stats_reader.py` — kept as-is, called by stats_collector.py for Claude stats

## Environment

### New env var
```
GEMINI_API_KEY=your-gemini-api-key
```

### .env.example update
```
GEMINI_API_KEY=your-gemini-api-key
SLACK_USER_TOKEN=xoxp-your-slack-user-token
```

## Error Handling

- Each stat source fails independently (missing gh, no JetBrains, etc.) — returns 0 for that source
- Gemini failure → fall back to template prompt
- SDXL Turbo failure → exit with error (image is required)
- Slack upload failure → notify + exit with error (image already saved locally)

## Testing

- `test_stats_collector.py` — mock file reads and subprocess calls for each source
- `test_character_sheet.py` — tier/class calculation with known inputs
- `test_prompt_generator.py` — mock Gemini API, verify fallback behavior
- Existing tests for image_generator, slack_uploader, slack_auth remain unchanged
