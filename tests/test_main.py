import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

# Stub heavy dependencies so main.py can be imported without torch/diffusers
for mod_name in ("torch", "diffusers", "diffusers.utils", "PIL", "PIL.Image"):
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

from main import _escape_applescript, _notify


def test_escape_applescript_quotes():
    assert _escape_applescript('say "hello"') == 'say \\"hello\\"'


def test_escape_applescript_backslashes():
    assert _escape_applescript("C:\\path\\to") == "C:\\\\path\\\\to"


def test_escape_applescript_both():
    assert _escape_applescript('"a\\b"') == '\\"a\\\\b\\"'


def test_escape_applescript_plain():
    assert _escape_applescript("no special chars") == "no special chars"


@patch("main.subprocess.run")
def test_notify_escapes_strings(mock_run):
    _notify('Title "with" quotes', 'Message with "quotes" and \\backslash')
    script = mock_run.call_args[0][0][2]  # osascript -e <script>
    assert '\\"' in script
    assert "\\\\" in script
    assert script.startswith('display notification "')
    assert 'with title "' in script
