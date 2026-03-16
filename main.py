"""Claude Usage PFP Generator — main entry point.

Orchestrates the RPG-themed pipeline:
  1. Collect daily developer activity stats (Claude, Git, GitHub, Terminal, IDE)
  2. Build an RPG character sheet (tier + class) from the stats
  3. Generate an image prompt via Gemini 2.5 Flash
  4. Generate pixel art image via SDXL Turbo
  5. Upload as Slack profile photo

Usage:
  python main.py           # Generate and upload
  python main.py --dry-run # Generate only, save locally, skip Slack upload
  python main.py --setup   # Run Slack OAuth flow to obtain a user token
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the script's directory (works in launchd too)
_script_dir = Path(__file__).resolve().parent
load_dotenv(_script_dir / ".env")

from stats_collector import collect_all_stats
from character_sheet import build_character_sheet
from prompt_generator import generate_prompt
from image_generator import generate_image
from slack_uploader import upload_profile_photo


def _escape_applescript(s: str) -> str:
    """Escape a string for safe embedding in AppleScript double-quoted literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _notify(title: str, message: str, image_path: str | None = None) -> None:
    """Send a macOS notification and optionally open the image in Preview."""
    safe_title = _escape_applescript(title)
    safe_message = _escape_applescript(message)
    script = f'display notification "{safe_message}" with title "{safe_title}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)

    if image_path:
        subprocess.Popen(["open", "-a", "Preview", image_path])


def main():
    parser = argparse.ArgumentParser(description="Generate and upload a daily RPG PFP")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't upload to Slack")
    parser.add_argument("--setup", action="store_true", help="Run Slack OAuth setup to obtain a user token")
    args = parser.parse_args()

    # --setup: run OAuth flow and exit
    if args.setup:
        from slack_auth import run_oauth_flow, DEFAULT_CLIENT_ID, DEFAULT_CLIENT_SECRET
        client_id = os.environ.get("SLACK_CLIENT_ID", DEFAULT_CLIENT_ID)
        client_secret = os.environ.get("SLACK_CLIENT_SECRET", DEFAULT_CLIENT_SECRET)
        if client_id == "PASTE_YOUR_CLIENT_ID_HERE" or client_secret == "PASTE_YOUR_CLIENT_SECRET_HERE":
            print(
                "Error: Slack app credentials not configured.\n"
                "Set DEFAULT_CLIENT_ID/DEFAULT_CLIENT_SECRET in slack_auth.py,\n"
                "or set SLACK_CLIENT_ID/SLACK_CLIENT_SECRET in your .env file.",
                file=sys.stderr,
            )
            sys.exit(1)
        run_oauth_flow(client_id, client_secret)
        sys.exit(0)

    # Check required env vars
    slack_token = os.environ.get("SLACK_USER_TOKEN")

    if not slack_token and not args.dry_run:
        print("Error: SLACK_USER_TOKEN not set (use --dry-run to skip upload)", file=sys.stderr)
        sys.exit(1)

    # 1. Collect stats
    print("Collecting developer activity stats...")
    stats = collect_all_stats()
    print(f"  Date: {stats['date']}")
    print(f"  Claude: {stats['claudeMessages']} msgs, {stats['claudeSessions']} sessions")
    print(f"  Git: {stats['gitCommits']} commits, {stats['gitLinesChanged']} lines")
    print(f"  GitHub: {stats['prsOpened']} opened, {stats['prsMerged']} merged, {stats['reviewsDone']} reviews")
    print(f"  Terminal: {stats['terminalCommands']} commands")
    print(f"  IDE: {stats['ideMinutes']} active minutes")

    # 2. Build character sheet
    print("\nBuilding character sheet...")
    sheet = build_character_sheet(stats)
    print(f"  Class: {sheet['className']}")
    print(f"  Tier: {sheet['tier']}")
    print(f"  Score: {sheet['activityScore']}")

    # 3. Generate prompt
    print("\nGenerating image prompt...")
    prompt = generate_prompt(sheet)
    print(f"  Prompt: {prompt}")

    # 4. Generate image
    print("\nGenerating image via SDXL Turbo...")
    try:
        image_bytes = generate_image(prompt)
    except Exception as e:
        print(f"Error: Image generation failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Save locally
    output_dir = _script_dir / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"pfp-{stats['date']}.png"
    output_path.write_bytes(image_bytes)
    print(f"Saved to {output_path}")

    # 5. Upload to Slack
    if args.dry_run:
        print("Dry run — skipping Slack upload")
        _notify(
            "PFP Generated (dry run)",
            f"{sheet['tier']} {sheet['className']} | Score: {sheet['activityScore']}",
            image_path=str(output_path),
        )
    else:
        print("Uploading to Slack...")
        try:
            upload_profile_photo(image_bytes, token=slack_token)
            print("Done! Profile photo updated.")
            _notify(
                "Slack PFP Updated",
                f"{sheet['tier']} {sheet['className']} | Score: {sheet['activityScore']}",
                image_path=str(output_path),
            )
        except Exception as e:
            print(f"Error: Slack upload failed: {e}", file=sys.stderr)
            _notify("PFP Generator Failed", f"Slack upload error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
