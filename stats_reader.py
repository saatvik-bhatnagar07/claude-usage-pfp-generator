"""Reads Claude Code CLI usage stats from history.jsonl.

Counts today's messages and sessions from the conversation history.
Falls back to yesterday if today has no entries, or returns zeroed
stats if no data exists at all.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path


def read_stats(stats_path: str = None) -> dict:
    """Read and return today's usage stats from the Claude history log.

    Reads ~/.claude/history.jsonl (one JSON object per line) and counts
    messages and unique sessions for today (or yesterday as fallback).

    Returns a dict with keys: date, messageCount, sessionCount.
    """
    if stats_path is None:
        stats_path = str(Path.home() / ".claude" / "history.jsonl")

    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # Count messages and sessions per date
    counts = {}  # date_str -> {"messages": int, "sessions": set}

    try:
        with open(stats_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                ts = entry.get("timestamp", 0)
                if not ts:
                    continue
                date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                if date_str not in (today, yesterday):
                    continue

                if date_str not in counts:
                    counts[date_str] = {"messages": 0, "sessions": set()}
                counts[date_str]["messages"] += 1
                session_id = entry.get("sessionId", "")
                if session_id:
                    counts[date_str]["sessions"].add(session_id)
    except FileNotFoundError:
        pass

    # Try today, then yesterday, then return zeroed stats
    for target_date in [today, yesterday]:
        if target_date in counts and counts[target_date]["messages"] > 0:
            c = counts[target_date]
            return {
                "date": target_date,
                "messageCount": c["messages"],
                "sessionCount": len(c["sessions"]),
            }

    # No data at all
    return {
        "date": today,
        "messageCount": 0,
        "sessionCount": 0,
    }
