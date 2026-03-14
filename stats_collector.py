"""Unified stats collection from multiple developer activity sources.

Collects daily activity metrics from:
  1. Claude Code (history.jsonl) — delegates to stats_reader.py
  2. Git repos (commits, lines changed)
  3. GitHub PRs/reviews (gh CLI)
  4. Terminal commands (zsh_history)
  5. JetBrains IDE (log files)

Each source fails independently — missing tools or files return zeroed metrics.
"""

import glob
import os
import re
import subprocess
from datetime import date
from pathlib import Path

from stats_reader import read_stats


def collect_claude_stats(history_path: str | None = None) -> dict:
    """Collect today's Claude Code usage stats.

    Delegates to stats_reader.read_stats() and remaps keys to the
    unified schema.
    """
    result = read_stats(history_path)
    return {
        "claudeMessages": result["messageCount"],
        "claudeSessions": result["sessionCount"],
    }


def collect_git_stats(base_dir: str | None = None) -> dict:
    """Collect today's git commit and line-change stats across local repos.

    Scans for .git directories under base_dir (default ~/src/work) up to
    depth 3 and aggregates commits and lines changed by the local user.
    """
    if base_dir is None:
        base_dir = str(Path.home() / "src" / "work")

    today = date.today().isoformat()
    total_commits = 0
    total_lines = 0

    git_dirs = glob.glob(os.path.join(base_dir, "**", ".git"), recursive=True)

    for g in git_dirs:
        # Depth filter: only repos within 3 levels of base_dir
        relative = os.path.dirname(g)[len(base_dir) :].strip(os.sep)
        if relative and relative.count(os.sep) >= 3:
            continue

        repo_dir = os.path.dirname(g)

        try:
            email_result = subprocess.run(
                ["git", "config", "user.email"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            email = email_result.stdout.strip()
            if not email:
                continue

            # Count commits
            log_result = subprocess.run(
                [
                    "git",
                    "log",
                    f"--after={today}T00:00:00",
                    f"--author={email}",
                    "--format=oneline",
                ],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            commits = len(
                [line for line in log_result.stdout.strip().split("\n") if line]
            )
            total_commits += commits

            # Count lines changed
            stat_result = subprocess.run(
                [
                    "git",
                    "log",
                    f"--after={today}T00:00:00",
                    f"--author={email}",
                    "--shortstat",
                    "--format=",
                ],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            for line in stat_result.stdout.strip().split("\n"):
                insertions = re.search(r"(\d+) insertion", line)
                deletions = re.search(r"(\d+) deletion", line)
                if insertions:
                    total_lines += int(insertions.group(1))
                if deletions:
                    total_lines += int(deletions.group(1))

        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return {
        "gitCommits": total_commits,
        "gitLinesChanged": total_lines,
    }


def collect_github_stats() -> dict:
    """Collect today's GitHub PR and review stats via the gh CLI."""
    today = date.today().isoformat()
    results = {"prsOpened": 0, "prsMerged": 0, "reviewsDone": 0}

    queries = [
        ("prsOpened", ["gh", "search", "prs", "--author=@me",
                       f"--created={today}", "--json", "url", "-q", ".[].url"]),
        ("prsMerged", ["gh", "search", "prs", "--author=@me",
                       f"--merged={today}", "--json", "url", "-q", ".[].url"]),
        ("reviewsDone", ["gh", "search", "prs", "--reviewed-by=@me",
                         f"--updated={today}", "--json", "url", "-q", ".[].url"]),
    ]

    for key, cmd in queries:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                lines = [l for l in result.stdout.strip().split("\n") if l]
                results[key] = len(lines)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return results


def collect_terminal_stats(history_path: str | None = None) -> dict:
    """Count today's terminal commands from zsh extended history.

    Parses lines in the format: `: <timestamp>:<duration>;<command>`
    """
    if history_path is None:
        history_path = str(Path.home() / ".zsh_history")

    today = date.today().isoformat()
    count = 0

    try:
        with open(history_path, "rb") as f:
            for raw_line in f:
                line = raw_line.decode("utf-8", errors="replace")
                match = re.match(r"^: (\d+):\d+;", line)
                if match:
                    ts = int(match.group(1))
                    entry_date = date.fromtimestamp(ts).isoformat()
                    if entry_date == today:
                        count += 1
    except FileNotFoundError:
        pass

    return {"terminalCommands": count}


def collect_ide_stats(logs_base: str | None = None) -> dict:
    """Count distinct active minutes in JetBrains IDE logs for today.

    Scans idea.log and pycharm.log files under the JetBrains logs directory
    and counts unique HH:MM timestamps on lines starting with today's date.
    """
    if logs_base is None:
        logs_base = str(Path.home() / "Library" / "Logs" / "JetBrains")

    today = date.today().isoformat()
    minutes = set()

    for log_name in ("idea.log", "pycharm.log"):
        for log_path in glob.glob(os.path.join(logs_base, "*", log_name)):
            try:
                with open(log_path) as f:
                    for line in f:
                        if line.startswith(today):
                            match = re.match(
                                r"\d{4}-\d{2}-\d{2} (\d{2}:\d{2})", line
                            )
                            if match:
                                minutes.add(match.group(1))
            except (FileNotFoundError, PermissionError):
                continue

    return {"ideMinutes": len(minutes)}


def collect_all_stats() -> dict:
    """Collect all daily stats into a single dict.

    Each collector runs independently — if one fails, its keys get
    zeroed defaults and the rest still report.
    """
    today = date.today().isoformat()
    stats = {"date": today}

    collectors = [
        (collect_claude_stats, {"claudeMessages": 0, "claudeSessions": 0}),
        (collect_git_stats, {"gitCommits": 0, "gitLinesChanged": 0}),
        (collect_github_stats, {"prsOpened": 0, "prsMerged": 0, "reviewsDone": 0}),
        (collect_terminal_stats, {"terminalCommands": 0}),
        (collect_ide_stats, {"ideMinutes": 0}),
    ]

    for collector, defaults in collectors:
        try:
            stats.update(collector())
        except Exception:
            stats.update(defaults)

    return stats
