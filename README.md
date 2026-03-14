# Claude Usage PFP Generator

Generates a unique pixel art profile picture every day from your Claude Code CLI usage stats using SDXL Turbo (runs locally, no API key needed), then uploads it as your Slack profile photo.

## How It Works

1. **Read stats** — Parses `~/.claude/history.jsonl` to count today's messages and sessions.
2. **Encode** — Serializes the stats into a canonical string and hashes it with SHA-256. The hash feeds a logistic map (r=3.99, fully chaotic regime) that expands it into a sequence of floats. Thanks to the avalanche effect, changing even a single message flips ~50% of the hash bits, which the chaotic map amplifies into a completely different float sequence.
3. **Generate** — Each float indexes into curated descriptor pools (style, form, palette, effect, composition) to build a prompt. SDXL Turbo generates a 512x512 image in 4 steps, resized to 1024x1024 for Slack.
4. **Upload** — Sets the generated image as your Slack profile photo via the `users.setPhoto` API.

## Setup

### Prerequisites

- Python 3.10+
- macOS (Apple Silicon recommended for MPS acceleration)
- ~6.5 GB disk space for the SDXL Turbo model (downloaded on first run)

### Installation

```bash
git clone https://github.com/your-username/claude-usage-pfp-generator.git
cd claude-usage-pfp-generator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Slack App Setup

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App** > **From scratch**.
2. Name it (e.g. "PFP Generator") and pick your workspace.
3. Navigate to **OAuth & Permissions** > **User Token Scopes** and add `users.profile:write`.
4. Under **Basic Information**, copy the **Client ID** and **Client Secret**.
5. In **OAuth & Permissions**, add `http://localhost:8338/callback` as a redirect URL.
6. Copy the example env file and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set `SLACK_CLIENT_ID` and `SLACK_CLIENT_SECRET`.
7. Run the OAuth flow to get your user token:
   ```bash
   python main.py --setup
   ```

### Usage

```bash
# Full pipeline: generate image + upload to Slack
python main.py

# Generate only, save to output/ directory (no Slack upload)
python main.py --dry-run

# Authenticate with Slack (OAuth flow)
python main.py --setup
```

Generated images are always saved to `output/pfp-YYYY-MM-DD.png` regardless of mode.

## Scheduling (macOS launchd)

To run the generator automatically every day, set up a launchd job.

Create (or verify) the plist at `~/Library/LaunchAgents/com.saatvik.pfp-generator.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.saatvik.pfp-generator</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/saatvik/src/work/claude-usage-pfp-generator/venv/bin/python</string>
        <string>/Users/saatvik/src/work/claude-usage-pfp-generator/main.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/saatvik/src/work/claude-usage-pfp-generator</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>10</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/saatvik/src/work/claude-usage-pfp-generator/output/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/saatvik/src/work/claude-usage-pfp-generator/output/launchd.log</string>
</dict>
</plist>
```

This runs the generator at 10:30 AM daily. If your Mac was asleep at that time, launchd will run it as soon as the machine wakes up.

### Commands

```bash
# Load (start scheduling)
launchctl load ~/Library/LaunchAgents/com.saatvik.pfp-generator.plist

# Unload (stop scheduling)
launchctl unload ~/Library/LaunchAgents/com.saatvik.pfp-generator.plist

# Run immediately (test)
launchctl start com.saatvik.pfp-generator

# Check status
launchctl list | grep pfp-generator

# Watch logs
tail -f output/launchd.log
```

## Project Structure

```
main.py              — Entry point; orchestrates the full pipeline
stats_reader.py      — Reads Claude usage stats from ~/.claude/history.jsonl
encoder.py           — SHA-256 + logistic map chaotic encoding pipeline
pools.py             — Curated descriptor pools (styles, palettes, effects, etc.)
image_generator.py   — SDXL Turbo image generation via HuggingFace diffusers
slack_uploader.py    — Uploads image as Slack profile photo
requirements.txt     — Python dependencies
.env.example         — Template for environment variables
output/              — Generated images and launchd logs
```
