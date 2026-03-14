import json
import os
import tempfile
import time
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from stats_collector import (
    collect_all_stats,
    collect_claude_stats,
    collect_git_stats,
    collect_github_stats,
    collect_ide_stats,
    collect_terminal_stats,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(date_str, hour=12):
    """Create a millisecond timestamp from a date string."""
    dt = datetime.fromisoformat(f"{date_str}T{hour:02d}:00:00")
    return int(dt.timestamp() * 1000)


def _write_history(path, entries):
    """Write a history.jsonl file."""
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Task 1 — Claude stats
# ---------------------------------------------------------------------------

def test_collect_claude_stats_today():
    today = date.today().isoformat()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        _write_history(path, [
            {"timestamp": _ts(today, 10), "sessionId": "s1", "display": "m1"},
            {"timestamp": _ts(today, 11), "sessionId": "s1", "display": "m2"},
            {"timestamp": _ts(today, 14), "sessionId": "s2", "display": "m3"},
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


# ---------------------------------------------------------------------------
# Task 2 — Git stats
# ---------------------------------------------------------------------------

def _make_subprocess_result(stdout="", returncode=0):
    r = MagicMock()
    r.stdout = stdout
    r.returncode = returncode
    return r


def test_collect_git_stats_counts_commits_and_lines():
    today = date.today().isoformat()

    with tempfile.TemporaryDirectory() as base:
        # Create a fake .git directory
        repo = os.path.join(base, "myrepo")
        os.makedirs(os.path.join(repo, ".git"))

        def fake_run(cmd, **kwargs):
            if "user.email" in cmd:
                return _make_subprocess_result("dev@example.com\n")
            if "--format=oneline" in cmd:
                return _make_subprocess_result("abc123 commit one\ndef456 commit two\n")
            if "--shortstat" in cmd:
                return _make_subprocess_result(
                    " 3 files changed, 50 insertions(+), 10 deletions(-)\n"
                    " 1 file changed, 5 insertions(+)\n"
                )
            return _make_subprocess_result()

        with patch("stats_collector.subprocess.run", side_effect=fake_run):
            result = collect_git_stats(base)

        assert result["gitCommits"] == 2
        assert result["gitLinesChanged"] == 65  # 50+10+5


def test_collect_git_stats_skips_deep_repos():
    with tempfile.TemporaryDirectory() as base:
        # depth 4 — should be skipped
        deep = os.path.join(base, "a", "b", "c", "d")
        os.makedirs(os.path.join(deep, ".git"))

        with patch("stats_collector.subprocess.run") as mock_run:
            result = collect_git_stats(base)

        mock_run.assert_not_called()
        assert result["gitCommits"] == 0


def test_collect_git_stats_handles_timeout():
    import subprocess as real_subprocess

    with tempfile.TemporaryDirectory() as base:
        os.makedirs(os.path.join(base, "repo", ".git"))

        with patch(
            "stats_collector.subprocess.run",
            side_effect=real_subprocess.TimeoutExpired("git", 10),
        ):
            result = collect_git_stats(base)

        assert result["gitCommits"] == 0
        assert result["gitLinesChanged"] == 0


def test_collect_git_stats_no_git_dirs():
    with tempfile.TemporaryDirectory() as base:
        result = collect_git_stats(base)
        assert result["gitCommits"] == 0
        assert result["gitLinesChanged"] == 0


# ---------------------------------------------------------------------------
# Task 3 — GitHub stats
# ---------------------------------------------------------------------------

def test_collect_github_stats_counts_prs():
    def fake_run(cmd, **kwargs):
        if "--created" in " ".join(cmd):
            return _make_subprocess_result(
                "https://github.com/org/repo/pull/1\n"
                "https://github.com/org/repo/pull/2\n"
            )
        if "--merged" in " ".join(cmd):
            return _make_subprocess_result(
                "https://github.com/org/repo/pull/1\n"
            )
        if "--reviewed-by" in " ".join(cmd):
            return _make_subprocess_result(
                "https://github.com/org/repo/pull/3\n"
                "https://github.com/org/repo/pull/4\n"
                "https://github.com/org/repo/pull/5\n"
            )
        return _make_subprocess_result()

    with patch("stats_collector.subprocess.run", side_effect=fake_run):
        result = collect_github_stats()

    assert result["prsOpened"] == 2
    assert result["prsMerged"] == 1
    assert result["reviewsDone"] == 3


def test_collect_github_stats_gh_not_installed():
    with patch(
        "stats_collector.subprocess.run",
        side_effect=FileNotFoundError,
    ):
        result = collect_github_stats()

    assert result["prsOpened"] == 0
    assert result["prsMerged"] == 0
    assert result["reviewsDone"] == 0


def test_collect_github_stats_gh_failure():
    with patch(
        "stats_collector.subprocess.run",
        return_value=_make_subprocess_result("", returncode=1),
    ):
        result = collect_github_stats()

    assert result["prsOpened"] == 0
    assert result["prsMerged"] == 0
    assert result["reviewsDone"] == 0


# ---------------------------------------------------------------------------
# Task 4 — Terminal stats
# ---------------------------------------------------------------------------

def test_collect_terminal_stats_counts_today():
    today = date.today()
    now_ts = int(time.mktime(today.timetuple()) + 3600)  # today + 1h
    old_ts = now_ts - 86400 * 30  # 30 days ago

    content = (
        f": {now_ts}:0;ls -la\n"
        f": {now_ts + 60}:0;cd /tmp\n"
        f": {old_ts}:0;echo old\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="wb", suffix="_history", delete=False
    ) as f:
        f.write(content.encode("utf-8"))
        path = f.name

    try:
        result = collect_terminal_stats(path)
        assert result["terminalCommands"] == 2
    finally:
        os.unlink(path)


def test_collect_terminal_stats_missing_file():
    result = collect_terminal_stats("/nonexistent/history")
    assert result["terminalCommands"] == 0


def test_collect_terminal_stats_handles_binary_garbage():
    today = date.today()
    now_ts = int(time.mktime(today.timetuple()) + 3600)

    content = (
        b": " + str(now_ts).encode() + b":0;echo hi\n"
        b"\x80\x81\x82 garbage line\n"
        b": " + str(now_ts + 60).encode() + b":0;pwd\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="wb", suffix="_history", delete=False
    ) as f:
        f.write(content)
        path = f.name

    try:
        result = collect_terminal_stats(path)
        assert result["terminalCommands"] == 2
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Task 5 — JetBrains IDE stats
# ---------------------------------------------------------------------------

def test_collect_ide_stats_counts_distinct_minutes():
    today = date.today().isoformat()

    with tempfile.TemporaryDirectory() as logs_base:
        product_dir = os.path.join(logs_base, "IntelliJIdea2025.1")
        os.makedirs(product_dir)

        log_path = os.path.join(product_dir, "idea.log")
        with open(log_path, "w") as f:
            f.write(
                f"{today} 10:05:12,345 [  Thread-1] INFO - some.Class\n"
                f"{today} 10:05:45,678 [  Thread-2] INFO - other.Class\n"
                f"{today} 10:06:01,000 [  Thread-1] INFO - another.Class\n"
                f"{today} 11:30:00,000 [  Thread-3] INFO - yet.Another\n"
                f"2020-01-01 09:00:00,000 [  Thread-1] INFO - old entry\n"
            )

        result = collect_ide_stats(logs_base)

    # 10:05, 10:06, 11:30 = 3 distinct minutes
    assert result["ideMinutes"] == 3


def test_collect_ide_stats_no_logs_dir():
    result = collect_ide_stats("/nonexistent/JetBrains")
    assert result["ideMinutes"] == 0


def test_collect_ide_stats_multiple_products():
    today = date.today().isoformat()

    with tempfile.TemporaryDirectory() as logs_base:
        for product, log_name in [
            ("IntelliJIdea2025.1", "idea.log"),
            ("PyCharm2025.1", "pycharm.log"),
        ]:
            d = os.path.join(logs_base, product)
            os.makedirs(d)
            with open(os.path.join(d, log_name), "w") as f:
                f.write(f"{today} 10:00:00,000 [  Thread-1] INFO - x\n")
                f.write(f"{today} 10:01:00,000 [  Thread-1] INFO - y\n")

        result = collect_ide_stats(logs_base)

    # 10:00 and 10:01 from both files = 2 distinct minutes
    assert result["ideMinutes"] == 2


# ---------------------------------------------------------------------------
# Task 6 — Unified collect_all_stats
# ---------------------------------------------------------------------------

def test_collect_all_stats_merges_all_sources():
    today = date.today().isoformat()

    with patch("stats_collector.collect_claude_stats",
               return_value={"claudeMessages": 5, "claudeSessions": 2}), \
         patch("stats_collector.collect_git_stats",
               return_value={"gitCommits": 3, "gitLinesChanged": 100}), \
         patch("stats_collector.collect_github_stats",
               return_value={"prsOpened": 1, "prsMerged": 0, "reviewsDone": 2}), \
         patch("stats_collector.collect_terminal_stats",
               return_value={"terminalCommands": 42}), \
         patch("stats_collector.collect_ide_stats",
               return_value={"ideMinutes": 120}):
        result = collect_all_stats()

    assert result["date"] == today
    assert result["claudeMessages"] == 5
    assert result["claudeSessions"] == 2
    assert result["gitCommits"] == 3
    assert result["gitLinesChanged"] == 100
    assert result["prsOpened"] == 1
    assert result["prsMerged"] == 0
    assert result["reviewsDone"] == 2
    assert result["terminalCommands"] == 42
    assert result["ideMinutes"] == 120


def test_collect_all_stats_handles_partial_failure():
    today = date.today().isoformat()

    with patch("stats_collector.collect_claude_stats",
               side_effect=RuntimeError("boom")), \
         patch("stats_collector.collect_git_stats",
               return_value={"gitCommits": 7, "gitLinesChanged": 200}), \
         patch("stats_collector.collect_github_stats",
               side_effect=RuntimeError("gh broken")), \
         patch("stats_collector.collect_terminal_stats",
               return_value={"terminalCommands": 10}), \
         patch("stats_collector.collect_ide_stats",
               side_effect=RuntimeError("no logs")):
        result = collect_all_stats()

    assert result["date"] == today
    # Failed collectors get zeros
    assert result["claudeMessages"] == 0
    assert result["claudeSessions"] == 0
    assert result["prsOpened"] == 0
    assert result["prsMerged"] == 0
    assert result["reviewsDone"] == 0
    assert result["ideMinutes"] == 0
    # Successful collectors kept their values
    assert result["gitCommits"] == 7
    assert result["gitLinesChanged"] == 200
    assert result["terminalCommands"] == 10
