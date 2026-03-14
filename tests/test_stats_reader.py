import json
import os
import tempfile
from datetime import date, datetime, timedelta

from stats_reader import read_stats


def _ts(date_str, hour=12):
    """Helper to create a millisecond timestamp from a date string."""
    dt = datetime.fromisoformat(f"{date_str}T{hour:02d}:00:00")
    return int(dt.timestamp() * 1000)


def _write_history(path, entries):
    """Helper to write a history.jsonl file."""
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def test_reads_today_stats():
    today = date.today().isoformat()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        _write_history(path, [
            {"timestamp": _ts(today, 10), "sessionId": "s1", "display": "msg1"},
            {"timestamp": _ts(today, 11), "sessionId": "s1", "display": "msg2"},
            {"timestamp": _ts(today, 14), "sessionId": "s2", "display": "msg3"},
        ])
        stats = read_stats(path)
        assert stats["date"] == today
        assert stats["messageCount"] == 3
        assert stats["sessionCount"] == 2
    finally:
        os.unlink(path)


def test_falls_back_to_yesterday():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        _write_history(path, [
            {"timestamp": _ts(yesterday), "sessionId": "s1", "display": "msg1"},
            {"timestamp": _ts(yesterday), "sessionId": "s1", "display": "msg2"},
        ])
        stats = read_stats(path)
        assert stats["date"] == yesterday
        assert stats["messageCount"] == 2
    finally:
        os.unlink(path)


def test_falls_back_to_zeroed_when_no_data():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        _write_history(path, [])
        stats = read_stats(path)
        assert stats["date"] == date.today().isoformat()
        assert stats["messageCount"] == 0
        assert stats["sessionCount"] == 0
    finally:
        os.unlink(path)
