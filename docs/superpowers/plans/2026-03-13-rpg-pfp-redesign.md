# RPG-Themed Meaningful PFP Redesign — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the chaotic encoding pipeline with a meaningful RPG character system where daily dev stats drive class/tier selection, and Gemini 2.5 Flash generates evocative pixel art prompts.

**Architecture:** Five stat sources (Claude, Git, GitHub PRs, Terminal, JetBrains IDE) feed into a character sheet (tier + class), which Gemini 2.5 Flash converts into a tight image prompt for SDXL Turbo. Template fallback if Gemini is unavailable.

**Tech Stack:** Python 3.13, google-genai (Gemini SDK), subprocess (git/gh CLI), existing SDXL Turbo pipeline

**Spec:** `docs/superpowers/specs/2026-03-13-rpg-pfp-redesign.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `stats_collector.py` (new) | Collects stats from all 5 sources, returns unified stats dict |
| `character_sheet.py` (new) | Maps stats → activity score → tier + class |
| `prompt_generator.py` (new) | Gemini 2.5 Flash prompt generation + template fallback |
| `main.py` (modify) | Rewire pipeline: stats_collector → character_sheet → prompt_generator → image → slack |
| `requirements.txt` (modify) | Add `google-genai` |
| `.env.example` (modify) | Add `GEMINI_API_KEY` |
| `tests/test_stats_collector.py` (new) | Tests for each stat source with mocked I/O |
| `tests/test_character_sheet.py` (new) | Tests for tier/class calculation |
| `tests/test_prompt_generator.py` (new) | Tests for Gemini integration + fallback |

**Removed after migration:** `encoder.py`, `pools.py`, `tests/test_encoder.py`

---

## Chunk 1: Stats Collector

### Task 1: Stats Collector — Claude Stats

**Files:**
- Create: `stats_collector.py`
- Create: `tests/test_stats_collector.py`

- [ ] **Step 1: Write the failing test for Claude stats**

```python
# tests/test_stats_collector.py
import json
import os
import tempfile
from datetime import date, datetime, timedelta

from stats_collector import collect_claude_stats


def _ts(date_str, hour=12):
    """Helper to create a millisecond timestamp from a date string."""
    dt = datetime.fromisoformat(f"{date_str}T{hour:02d}:00:00")
    return int(dt.timestamp() * 1000)


def _write_history(path, entries):
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def test_collect_claude_stats_today():
    today = date.today().isoformat()
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        _write_history(path, [
            {"timestamp": _ts(today, 10), "sessionId": "s1"},
            {"timestamp": _ts(today, 11), "sessionId": "s1"},
            {"timestamp": _ts(today, 14), "sessionId": "s2"},
        ])
        result = collect_claude_stats(path)
        assert result["claudeMessages"] == 3
        assert result["claudeSessions"] == 2
    finally:
        os.unlink(path)


def test_collect_claude_stats_missing_file():
    result = collect_claude_stats("/nonexistent/path.jsonl")
    assert result["claudeMessages"] == 0
    assert result["claudeSessions"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_stats_collector.py::test_collect_claude_stats_today tests/test_stats_collector.py::test_collect_claude_stats_missing_file -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'stats_collector'` or `ImportError`

- [ ] **Step 3: Implement collect_claude_stats**

```python
# stats_collector.py
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
from datetime import date, datetime, timedelta
from pathlib import Path

from stats_reader import read_stats


def collect_claude_stats(history_path: str | None = None) -> dict:
    """Count today's Claude Code messages and sessions from history.jsonl.

    Delegates to stats_reader.read_stats and remaps keys.
    Falls back to yesterday if today has no entries.
    """
    result = read_stats(history_path)
    return {
        "claudeMessages": result["messageCount"],
        "claudeSessions": result["sessionCount"],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_stats_collector.py -v`
Expected: 2 PASSED

---

### Task 2: Stats Collector — Git Stats

**Files:**
- Modify: `stats_collector.py`
- Modify: `tests/test_stats_collector.py`

- [ ] **Step 1: Write the failing test for git stats**

Add to `tests/test_stats_collector.py`:

```python
from unittest.mock import patch, MagicMock
from stats_collector import collect_git_stats


def test_collect_git_stats_counts_commits_and_lines():
    """Mock subprocess to simulate git log and git diff output."""
    log_output = "abc1234 feat: add feature\ndef5678 fix: bug fix\n"
    diff_output = " 2 files changed, 45 insertions(+), 12 deletions(-)\n"

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        if "log" in cmd:
            result.stdout = log_output
        elif "diff" in cmd:
            result.stdout = diff_output
        return result

    with patch("stats_collector.subprocess.run", side_effect=mock_run):
        with patch("stats_collector.glob.glob", return_value=["/fake/repo/.git"]):
            result = collect_git_stats("/fake/base")
    assert result["gitCommits"] == 2
    assert result["gitLinesChanged"] == 57  # 45 + 12


def test_collect_git_stats_no_repos():
    with patch("stats_collector.glob.glob", return_value=[]):
        result = collect_git_stats("/empty/dir")
    assert result["gitCommits"] == 0
    assert result["gitLinesChanged"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_stats_collector.py::test_collect_git_stats_counts_commits_and_lines tests/test_stats_collector.py::test_collect_git_stats_no_repos -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement collect_git_stats**

Add to `stats_collector.py`:

```python
def collect_git_stats(base_dir: str | None = None) -> dict:
    """Count today's git commits and lines changed across repos under base_dir.

    Scans for .git directories up to depth 3 under base_dir.
    """
    if base_dir is None:
        base_dir = str(Path.home() / "src" / "work")

    today = date.today().isoformat()

    # Find git repos (max depth 3 under base_dir)
    git_dirs = glob.glob(os.path.join(base_dir, "**", ".git"), recursive=True)
    git_dirs = [
        g for g in git_dirs
        if g.startswith(base_dir) and
        os.path.dirname(g)[len(base_dir):].strip(os.sep).count(os.sep) < 3
    ]

    total_commits = 0
    total_lines = 0

    for git_dir in git_dirs:
        repo_dir = os.path.dirname(git_dir)
        try:
            # Get user email for author filter
            email_result = subprocess.run(
                ["git", "config", "user.email"],
                cwd=repo_dir, capture_output=True, text=True, timeout=5,
            )
            author_email = email_result.stdout.strip()

            # Count commits
            log_result = subprocess.run(
                ["git", "log", f"--after={today}T00:00:00",
                 f"--author={author_email}", "--format=oneline"],
                cwd=repo_dir, capture_output=True, text=True, timeout=10,
            )
            if log_result.returncode == 0:
                commits = [l for l in log_result.stdout.strip().split("\n") if l]
                total_commits += len(commits)

            # Lines changed today
            diff_result = subprocess.run(
                ["git", "log", f"--after={today}T00:00:00",
                 f"--author={author_email}", "--shortstat", "--format="],
                cwd=repo_dir, capture_output=True, text=True, timeout=10,
            )
            if diff_result.returncode == 0:
                for line in diff_result.stdout.split("\n"):
                    ins = re.search(r"(\d+) insertion", line)
                    dels = re.search(r"(\d+) deletion", line)
                    if ins:
                        total_lines += int(ins.group(1))
                    if dels:
                        total_lines += int(dels.group(1))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    return {"gitCommits": total_commits, "gitLinesChanged": total_lines}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_stats_collector.py -v`
Expected: 4 PASSED

---

### Task 3: Stats Collector — GitHub PRs/Reviews

**Files:**
- Modify: `stats_collector.py`
- Modify: `tests/test_stats_collector.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_stats_collector.py`:

```python
from stats_collector import collect_github_stats


def test_collect_github_stats_counts_prs_and_reviews():
    call_count = {"n": 0}

    def mock_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        call_count["n"] += 1
        if call_count["n"] == 1:
            # prs opened today
            result.stdout = "http://github.com/repo/pull/1\nhttp://github.com/repo/pull/2\n"
        elif call_count["n"] == 2:
            # prs merged today
            result.stdout = "http://github.com/repo/pull/3\n"
        elif call_count["n"] == 3:
            # reviews done today
            result.stdout = "http://github.com/repo/pull/4\nhttp://github.com/repo/pull/5\n"
        else:
            result.stdout = ""
        return result

    with patch("stats_collector.subprocess.run", side_effect=mock_run):
        result = collect_github_stats()
    assert result["prsOpened"] == 2
    assert result["prsMerged"] == 1
    assert result["reviewsDone"] == 2


def test_collect_github_stats_gh_not_installed():
    with patch("stats_collector.subprocess.run", side_effect=FileNotFoundError):
        result = collect_github_stats()
    assert result["prsOpened"] == 0
    assert result["prsMerged"] == 0
    assert result["reviewsDone"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_stats_collector.py::test_collect_github_stats_counts_prs_and_reviews tests/test_stats_collector.py::test_collect_github_stats_gh_not_installed -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement collect_github_stats**

Add to `stats_collector.py`:

```python
def collect_github_stats() -> dict:
    """Count today's PRs opened, merged, and reviews via the gh CLI.

    Returns zeroed stats if gh is not installed or not authenticated.
    """
    today = date.today().isoformat()
    result = {"prsOpened": 0, "prsMerged": 0, "reviewsDone": 0}

    try:
        # PRs opened today
        opened = subprocess.run(
            ["gh", "search", "prs", "--author=@me",
             "--created", today, "--json", "url", "-q", ".[].url"],
            capture_output=True, text=True, timeout=15,
        )
        if opened.returncode == 0:
            result["prsOpened"] = len([l for l in opened.stdout.strip().split("\n") if l])

        # PRs merged today
        merged = subprocess.run(
            ["gh", "search", "prs", "--author=@me",
             "--merged", today, "--json", "url", "-q", ".[].url"],
            capture_output=True, text=True, timeout=15,
        )
        if merged.returncode == 0:
            result["prsMerged"] = len([l for l in merged.stdout.strip().split("\n") if l])

        # Reviews done today
        reviews = subprocess.run(
            ["gh", "search", "prs", "--reviewed-by=@me",
             "--updated", today, "--json", "url", "-q", ".[].url"],
            capture_output=True, text=True, timeout=15,
        )
        if reviews.returncode == 0:
            result["reviewsDone"] = len([l for l in reviews.stdout.strip().split("\n") if l])

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_stats_collector.py -v`
Expected: 6 PASSED

---

### Task 4: Stats Collector — Terminal History

**Files:**
- Modify: `stats_collector.py`
- Modify: `tests/test_stats_collector.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_stats_collector.py`:

```python
from stats_collector import collect_terminal_stats


def test_collect_terminal_stats_counts_today():
    today_ts = int(datetime.combine(date.today(), datetime.min.time()).timestamp())
    tomorrow_ts = today_ts + 86400

    history_content = (
        f": {today_ts + 100}:0;ls\n"
        f": {today_ts + 200}:0;git status\n"
        f": {today_ts + 300}:0;python main.py\n"
        f": {today_ts - 100}:0;old command\n"  # yesterday
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".history", delete=False) as f:
        f.write(history_content)
        path = f.name
    try:
        result = collect_terminal_stats(path)
        assert result["terminalCommands"] == 3
    finally:
        os.unlink(path)


def test_collect_terminal_stats_missing_file():
    result = collect_terminal_stats("/nonexistent/.zsh_history")
    assert result["terminalCommands"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_stats_collector.py::test_collect_terminal_stats_counts_today tests/test_stats_collector.py::test_collect_terminal_stats_missing_file -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement collect_terminal_stats**

Add to `stats_collector.py`:

```python
def collect_terminal_stats(history_path: str | None = None) -> dict:
    """Count today's commands from zsh extended history.

    Format: ": <timestamp>:<duration>;<command>"
    """
    if history_path is None:
        history_path = str(Path.home() / ".zsh_history")

    today_start = int(datetime.combine(date.today(), datetime.min.time()).timestamp())
    tomorrow_start = today_start + 86400
    count = 0

    try:
        with open(history_path, "rb") as f:
            for raw_line in f:
                try:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                except Exception:
                    continue
                match = re.match(r"^: (\d+):\d+;", line)
                if match:
                    ts = int(match.group(1))
                    if today_start <= ts < tomorrow_start:
                        count += 1
    except FileNotFoundError:
        pass

    return {"terminalCommands": count}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_stats_collector.py -v`
Expected: 8 PASSED

---

### Task 5: Stats Collector — JetBrains IDE

**Files:**
- Modify: `stats_collector.py`
- Modify: `tests/test_stats_collector.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_stats_collector.py`:

```python
from stats_collector import collect_ide_stats


def test_collect_ide_stats_counts_active_minutes():
    today = date.today().isoformat()
    # Simulate log lines at 3 distinct minutes
    log_content = (
        f"{today} 10:05:12,345 [  Thread-1] INFO - some.Class - action\n"
        f"{today} 10:05:45,678 [  Thread-2] INFO - some.Class - action\n"  # same minute
        f"{today} 10:06:12,345 [  Thread-1] INFO - some.Class - action\n"
        f"{today} 10:15:00,000 [  Thread-1] INFO - some.Class - action\n"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = os.path.join(tmpdir, "IntelliJIdea2025.1")
        os.makedirs(log_dir)
        log_path = os.path.join(log_dir, "idea.log")
        with open(log_path, "w") as f:
            f.write(log_content)

        result = collect_ide_stats(tmpdir)
    assert result["ideMinutes"] == 3  # 10:05, 10:06, 10:15


def test_collect_ide_stats_no_logs():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = collect_ide_stats(tmpdir)
    assert result["ideMinutes"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_stats_collector.py::test_collect_ide_stats_counts_active_minutes tests/test_stats_collector.py::test_collect_ide_stats_no_logs -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement collect_ide_stats**

Add to `stats_collector.py`:

```python
def collect_ide_stats(logs_base: str | None = None) -> dict:
    """Estimate active IDE minutes from JetBrains log files.

    Scans idea.log and pycharm.log for today's entries, counts distinct
    minute-windows as "active minutes".
    """
    if logs_base is None:
        logs_base = str(Path.home() / "Library" / "Logs" / "JetBrains")

    today = date.today().isoformat()
    active_minutes = set()

    log_files = (
        glob.glob(os.path.join(logs_base, "*", "idea.log"))
        + glob.glob(os.path.join(logs_base, "*", "pycharm.log"))
    )

    for log_file in log_files:
        try:
            with open(log_file, errors="replace") as f:
                for line in f:
                    # JetBrains log format: "2026-03-13 10:05:12,345 ..."
                    if line.startswith(today):
                        # Extract HH:MM
                        match = re.match(r"\d{4}-\d{2}-\d{2} (\d{2}:\d{2})", line)
                        if match:
                            active_minutes.add(match.group(1))
        except FileNotFoundError:
            continue

    return {"ideMinutes": len(active_minutes)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_stats_collector.py -v`
Expected: 10 PASSED

---

### Task 6: Stats Collector — Unified collect_all_stats

**Files:**
- Modify: `stats_collector.py`
- Modify: `tests/test_stats_collector.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_stats_collector.py`:

```python
from stats_collector import collect_all_stats


def test_collect_all_stats_returns_all_keys():
    with patch("stats_collector.collect_claude_stats", return_value={"claudeMessages": 10, "claudeSessions": 2}):
        with patch("stats_collector.collect_git_stats", return_value={"gitCommits": 3, "gitLinesChanged": 100}):
            with patch("stats_collector.collect_github_stats", return_value={"prsOpened": 1, "prsMerged": 0, "reviewsDone": 2}):
                with patch("stats_collector.collect_terminal_stats", return_value={"terminalCommands": 50}):
                    with patch("stats_collector.collect_ide_stats", return_value={"ideMinutes": 60}):
                        result = collect_all_stats()

    expected_keys = {
        "date", "claudeMessages", "claudeSessions",
        "gitCommits", "gitLinesChanged",
        "prsOpened", "prsMerged", "reviewsDone",
        "terminalCommands", "ideMinutes",
    }
    assert set(result.keys()) == expected_keys
    assert result["claudeMessages"] == 10
    assert result["ideMinutes"] == 60


def test_collect_all_stats_survives_source_failure():
    """If one source throws, others still work."""
    with patch("stats_collector.collect_claude_stats", side_effect=Exception("boom")):
        with patch("stats_collector.collect_git_stats", return_value={"gitCommits": 3, "gitLinesChanged": 100}):
            with patch("stats_collector.collect_github_stats", return_value={"prsOpened": 0, "prsMerged": 0, "reviewsDone": 0}):
                with patch("stats_collector.collect_terminal_stats", return_value={"terminalCommands": 50}):
                    with patch("stats_collector.collect_ide_stats", return_value={"ideMinutes": 60}):
                        result = collect_all_stats()

    assert result["claudeMessages"] == 0
    assert result["gitCommits"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_stats_collector.py::test_collect_all_stats_returns_all_keys tests/test_stats_collector.py::test_collect_all_stats_survives_source_failure -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement collect_all_stats**

Add to `stats_collector.py`:

```python
_DEFAULTS = {
    "claudeMessages": 0, "claudeSessions": 0,
    "gitCommits": 0, "gitLinesChanged": 0,
    "prsOpened": 0, "prsMerged": 0, "reviewsDone": 0,
    "terminalCommands": 0,
    "ideMinutes": 0,
}


def collect_all_stats() -> dict:
    """Collect stats from all sources. Each source fails independently."""
    stats = {"date": date.today().isoformat(), **_DEFAULTS}

    collectors = [
        collect_claude_stats,
        collect_git_stats,
        collect_github_stats,
        collect_terminal_stats,
        collect_ide_stats,
    ]

    for collector in collectors:
        try:
            stats.update(collector())
        except Exception:
            pass  # Source failed — keep defaults for its keys

    return stats
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_stats_collector.py -v`
Expected: 12 PASSED

- [ ] **Step 5: Commit**

```bash
git add stats_collector.py tests/test_stats_collector.py
git commit -m "feat: add unified stats collector with 5 dev activity sources"
```

---

## Chunk 2: Character Sheet

### Task 7: Character Sheet — Scoring and Tier

**Files:**
- Create: `character_sheet.py`
- Create: `tests/test_character_sheet.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_character_sheet.py
from character_sheet import compute_score, compute_tier


def test_compute_score_zero_stats():
    stats = {
        "claudeMessages": 0, "claudeSessions": 0,
        "gitCommits": 0, "gitLinesChanged": 0,
        "prsOpened": 0, "prsMerged": 0, "reviewsDone": 0,
        "terminalCommands": 0, "ideMinutes": 0,
    }
    assert compute_score(stats) == 0.0


def test_compute_score_weighted():
    stats = {
        "claudeMessages": 10, "claudeSessions": 2,
        "gitCommits": 2, "gitLinesChanged": 100,
        "prsOpened": 0, "prsMerged": 0, "reviewsDone": 0,
        "terminalCommands": 0, "ideMinutes": 0,
    }
    # 10*1.0 + 2*5.0 + 100*0.05 = 10 + 10 + 5 = 25
    assert compute_score(stats) == 25.0


def test_tier_apprentice():
    assert compute_tier(15) == "Apprentice"


def test_tier_adventurer():
    assert compute_tier(50) == "Adventurer"


def test_tier_champion():
    assert compute_tier(100) == "Champion"


def test_tier_legendary():
    assert compute_tier(150) == "Legendary"


def test_tier_boundary_values():
    assert compute_tier(0) == "Apprentice"
    assert compute_tier(30) == "Apprentice"
    assert compute_tier(31) == "Adventurer"
    assert compute_tier(70) == "Adventurer"
    assert compute_tier(71) == "Champion"
    assert compute_tier(120) == "Champion"
    assert compute_tier(121) == "Legendary"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_character_sheet.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement scoring and tier**

```python
# character_sheet.py
"""Maps developer activity stats to an RPG character sheet.

Computes an activity score from weighted stats, assigns a power tier,
and determines a character class based on the dominant activity source.
"""

# Weights for each stat — tuned so that a heavy day (~88 Claude messages
# + some git + terminal) lands in the Champion tier (71-120).
WEIGHTS = {
    "claudeMessages": 1.0,
    "gitCommits": 5.0,
    "gitLinesChanged": 0.05,
    "prsOpened": 10.0,
    "prsMerged": 10.0,
    "reviewsDone": 8.0,
    "terminalCommands": 0.3,
    "ideMinutes": 0.5,
}

TIER_THRESHOLDS = [
    (121, "Legendary"),
    (71, "Champion"),
    (31, "Adventurer"),
    (0, "Apprentice"),
]


def compute_score(stats: dict) -> float:
    """Compute the weighted activity score from raw stats."""
    return sum(stats.get(key, 0) * weight for key, weight in WEIGHTS.items())


def compute_tier(score: float) -> str:
    """Map an activity score to a power tier."""
    for threshold, tier in TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "Apprentice"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_character_sheet.py -v`
Expected: 8 PASSED

---

### Task 8: Character Sheet — Class Determination

**Files:**
- Modify: `character_sheet.py`
- Modify: `tests/test_character_sheet.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_character_sheet.py`:

```python
from character_sheet import compute_class, build_character_sheet


def test_class_mage_when_claude_dominates():
    stats = {
        "claudeMessages": 100, "claudeSessions": 10,
        "gitCommits": 0, "gitLinesChanged": 0,
        "prsOpened": 0, "prsMerged": 0, "reviewsDone": 0,
        "terminalCommands": 0, "ideMinutes": 0,
    }
    assert compute_class(stats) == "Mage"


def test_class_blacksmith_when_git_dominates():
    stats = {
        "claudeMessages": 0, "claudeSessions": 0,
        "gitCommits": 20, "gitLinesChanged": 500,
        "prsOpened": 0, "prsMerged": 0, "reviewsDone": 0,
        "terminalCommands": 0, "ideMinutes": 0,
    }
    assert compute_class(stats) == "Blacksmith"


def test_class_paladin_when_prs_dominate():
    stats = {
        "claudeMessages": 0, "claudeSessions": 0,
        "gitCommits": 0, "gitLinesChanged": 0,
        "prsOpened": 5, "prsMerged": 5, "reviewsDone": 10,
        "terminalCommands": 0, "ideMinutes": 0,
    }
    assert compute_class(stats) == "Paladin"


def test_class_rogue_when_terminal_dominates():
    stats = {
        "claudeMessages": 0, "claudeSessions": 0,
        "gitCommits": 0, "gitLinesChanged": 0,
        "prsOpened": 0, "prsMerged": 0, "reviewsDone": 0,
        "terminalCommands": 500, "ideMinutes": 0,
    }
    assert compute_class(stats) == "Rogue"


def test_class_scholar_when_ide_dominates():
    stats = {
        "claudeMessages": 0, "claudeSessions": 0,
        "gitCommits": 0, "gitLinesChanged": 0,
        "prsOpened": 0, "prsMerged": 0, "reviewsDone": 0,
        "terminalCommands": 0, "ideMinutes": 300,
    }
    assert compute_class(stats) == "Scholar"


def test_class_warrior_when_balanced():
    stats = {
        "claudeMessages": 30, "claudeSessions": 5,
        "gitCommits": 5, "gitLinesChanged": 100,
        "prsOpened": 1, "prsMerged": 1, "reviewsDone": 1,
        "terminalCommands": 80, "ideMinutes": 60,
    }
    assert compute_class(stats) == "Warrior"


def test_class_zero_stats():
    stats = {
        "claudeMessages": 0, "claudeSessions": 0,
        "gitCommits": 0, "gitLinesChanged": 0,
        "prsOpened": 0, "prsMerged": 0, "reviewsDone": 0,
        "terminalCommands": 0, "ideMinutes": 0,
    }
    assert compute_class(stats) == "Warrior"


def test_build_character_sheet():
    stats = {
        "date": "2026-03-13",
        "claudeMessages": 88, "claudeSessions": 11,
        "gitCommits": 5, "gitLinesChanged": 200,
        "prsOpened": 1, "prsMerged": 0, "reviewsDone": 0,
        "terminalCommands": 100, "ideMinutes": 60,
    }
    sheet = build_character_sheet(stats)
    assert sheet["tier"] in ("Apprentice", "Adventurer", "Champion", "Legendary")
    assert sheet["className"] in ("Mage", "Blacksmith", "Paladin", "Rogue", "Scholar", "Warrior")
    assert "activityScore" in sheet
    assert sheet["stats"] is stats
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_character_sheet.py::test_class_mage_when_claude_dominates -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement class determination and build_character_sheet**

Add to `character_sheet.py`:

```python
# Categories group stats into activity sources for class determination.
# Each category maps to: (class_name, [stat_keys])
CATEGORIES = {
    "claude": ("Mage", ["claudeMessages"]),
    "git": ("Blacksmith", ["gitCommits", "gitLinesChanged"]),
    "github": ("Paladin", ["prsOpened", "prsMerged", "reviewsDone"]),
    "terminal": ("Rogue", ["terminalCommands"]),
    "ide": ("Scholar", ["ideMinutes"]),
}


def compute_class(stats: dict) -> str:
    """Determine RPG class from which activity category dominates.

    If no category exceeds 40% of total score, returns "Warrior" (balanced).
    """
    total = compute_score(stats)
    if total == 0:
        return "Warrior"

    category_scores = {}
    for cat_name, (class_name, keys) in CATEGORIES.items():
        cat_score = sum(stats.get(k, 0) * WEIGHTS.get(k, 0) for k in keys)
        category_scores[cat_name] = (class_name, cat_score)

    # Find dominant category
    dominant_cat, (dominant_class, dominant_score) = max(
        category_scores.items(), key=lambda x: x[1][1]
    )

    # "Balanced" if no category exceeds 40%
    if dominant_score / total <= 0.4:
        return "Warrior"

    return dominant_class


def build_character_sheet(stats: dict) -> dict:
    """Build a full character sheet from raw stats."""
    score = compute_score(stats)
    return {
        "tier": compute_tier(score),
        "className": compute_class(stats),
        "activityScore": round(score, 1),
        "stats": stats,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_character_sheet.py -v`
Expected: 16 PASSED

- [ ] **Step 5: Commit**

```bash
git add character_sheet.py tests/test_character_sheet.py
git commit -m "feat: add RPG character sheet with tier and class from dev stats"
```

---

## Chunk 3: Prompt Generator (Gemini + Fallback)

### Task 9: Install google-genai

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add google-genai to requirements.txt**

Add `google-genai` to the end of `requirements.txt`.

- [ ] **Step 2: Install the dependency**

Run: `./venv/bin/pip install --index-url https://pypi.org/simple/ google-genai`

- [ ] **Step 3: Verify import works**

Run: `./venv/bin/python -c "from google import genai; print('OK')"`
Expected: `OK`

---

### Task 10: Prompt Generator — Gemini Integration

**Files:**
- Create: `prompt_generator.py`
- Create: `tests/test_prompt_generator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_prompt_generator.py
from unittest.mock import patch, MagicMock
from prompt_generator import generate_prompt, _build_gemini_prompt, _fallback_prompt


def test_build_gemini_prompt_contains_class_and_tier():
    sheet = {
        "tier": "Champion",
        "className": "Mage",
        "activityScore": 95,
        "stats": {
            "claudeMessages": 88, "claudeSessions": 11,
            "gitCommits": 5, "gitLinesChanged": 200,
            "prsOpened": 1, "prsMerged": 0, "reviewsDone": 0,
            "terminalCommands": 100, "ideMinutes": 60,
        },
    }
    prompt = _build_gemini_prompt(sheet)
    assert "Mage" in prompt
    assert "Champion" in prompt
    assert "95" in prompt


def test_fallback_prompt_contains_class_and_tier():
    sheet = {
        "tier": "Legendary",
        "className": "Blacksmith",
        "activityScore": 150,
        "stats": {},
    }
    prompt = _fallback_prompt(sheet)
    assert "pixel art" in prompt.lower()
    assert "blacksmith" in prompt.lower() or "forge" in prompt.lower()
    assert len(prompt.split()) <= 60  # within CLIP 77 token budget


def test_generate_prompt_uses_gemini():
    sheet = {
        "tier": "Champion",
        "className": "Mage",
        "activityScore": 95,
        "stats": {"claudeMessages": 88},
    }
    mock_response = MagicMock()
    mock_response.text = "16-bit pixel art of a champion mage channeling arcane lightning"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("prompt_generator.genai.Client", return_value=mock_client):
        result = generate_prompt(sheet, api_key="fake-key")

    assert "mage" in result.lower()
    mock_client.models.generate_content.assert_called_once()


def test_generate_prompt_falls_back_on_gemini_error():
    sheet = {
        "tier": "Adventurer",
        "className": "Rogue",
        "activityScore": 50,
        "stats": {},
    }
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("API error")

    with patch("prompt_generator.genai.Client", return_value=mock_client):
        result = generate_prompt(sheet, api_key="fake-key")

    assert "pixel art" in result.lower()
    assert len(result.split()) <= 70


def test_generate_prompt_falls_back_when_no_api_key():
    sheet = {
        "tier": "Apprentice",
        "className": "Scholar",
        "activityScore": 15,
        "stats": {},
    }
    result = generate_prompt(sheet, api_key=None)
    assert "pixel art" in result.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_prompt_generator.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement prompt_generator.py**

```python
# prompt_generator.py
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

# Fallback aesthetics per class — used when Gemini is unavailable
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
    """Build the user prompt for Gemini from the character sheet."""
    stats = sheet.get("stats", {})
    # Find top 3 stats by raw value (excluding date)
    stat_items = [(k, v) for k, v in stats.items() if isinstance(v, (int, float)) and v > 0]
    stat_items.sort(key=lambda x: x[1], reverse=True)
    top_stats = ", ".join(f"{k}: {v}" for k, v in stat_items[:3]) or "minimal activity"

    return (
        f"Character Sheet:\n"
        f"- Class: {sheet['className']}\n"
        f"- Tier: {sheet['tier']}\n"
        f"- Activity Score: {sheet['activityScore']}/200\n"
        f"- Top stats: {top_stats}\n\n"
        f"Write the image prompt."
    )


def _fallback_prompt(sheet: dict) -> str:
    """Template-based fallback prompt when Gemini is unavailable."""
    class_name = sheet.get("className", "Warrior")
    tier = sheet.get("tier", "Apprentice")
    aesthetic = CLASS_AESTHETICS.get(class_name, CLASS_AESTHETICS["Warrior"])
    intensity = TIER_INTENSITY.get(tier, TIER_INTENSITY["Apprentice"])

    return (
        f"retro 16-bit pixel art, {intensity} "
        f"RPG {class_name.lower()} character, "
        f"{aesthetic}, "
        f"dark background, large visible pixels, retro gaming aesthetic"
    )


def generate_prompt(sheet: dict, api_key: str | None = None) -> str:
    """Generate an image prompt from a character sheet.

    Uses Gemini 2.5 Flash if api_key is provided, otherwise falls back to template.
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
        prompt = response.text.strip()
        if prompt:
            return prompt
    except Exception:
        pass

    return _fallback_prompt(sheet)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_prompt_generator.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add prompt_generator.py tests/test_prompt_generator.py requirements.txt
git commit -m "feat: add Gemini 2.5 Flash prompt generator with template fallback"
```

---

## Chunk 4: Pipeline Rewire + Cleanup

### Task 11: Update .env.example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Update .env.example**

Replace contents with:

```
GEMINI_API_KEY=your-gemini-api-key

SLACK_USER_TOKEN=xoxp-your-slack-user-token

# Slack OAuth app credentials (needed for --setup)
SLACK_CLIENT_ID=your-slack-client-id
SLACK_CLIENT_SECRET=your-slack-client-secret

# Optional: override default paths
# CLAUDE_STATS_PATH=~/.claude/history.jsonl
# GIT_REPOS_DIR=~/src/work
```

---

### Task 12: Rewire main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Rewrite main.py pipeline**

Replace the full `main.py` with:

```python
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


def _notify(title: str, message: str, image_path: str | None = None) -> None:
    """Send a macOS notification and optionally open the image in Preview."""
    script = f'display notification "{message}" with title "{title}"'
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
    gemini_key = os.environ.get("GEMINI_API_KEY")

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
    if not gemini_key:
        print("  (No GEMINI_API_KEY — using template fallback)")
    prompt = generate_prompt(sheet, api_key=gemini_key)
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
```

- [ ] **Step 2: Run the full test suite**

Run: `./venv/bin/python -m pytest tests/ -v`
Expected: All new tests pass. Old tests for encoder will fail (expected — we'll remove them next).

---

### Task 13: Remove old encoder pipeline

**Files:**
- Delete: `encoder.py`
- Delete: `pools.py`
- Delete: `tests/test_encoder.py`

- [ ] **Step 1: Delete the old files**

```bash
rm encoder.py pools.py tests/test_encoder.py
```

- [ ] **Step 2: Run the full test suite**

Run: `./venv/bin/python -m pytest tests/ -v`
Expected: ALL tests pass (no more encoder imports)

- [ ] **Step 3: Commit the full pipeline rewire**

```bash
git add main.py .env.example
git add -A  # picks up deletions
git commit -m "feat: rewire pipeline to RPG character system with Gemini prompt generation

Replaces chaotic encoding with meaningful stat-to-archetype mapping.
Removes encoder.py and pools.py in favor of character_sheet.py and prompt_generator.py."
```

---

### Task 14: End-to-end dry run test

- [ ] **Step 1: Add GEMINI_API_KEY to .env**

Make sure your `.env` file has `GEMINI_API_KEY=<your-key>`.

- [ ] **Step 2: Run dry-run**

Run: `./venv/bin/python main.py --dry-run`

Expected output:
- Stats from all 5 sources printed
- Character sheet with class + tier
- Gemini-generated prompt
- Image saved to `output/pfp-2026-03-13.png`
- macOS notification with image preview

- [ ] **Step 3: Verify the image looks like the described character**

Open `output/pfp-2026-03-13.png` and check it matches the RPG theme.
