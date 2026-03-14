import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from slack_auth import exchange_code_for_token, save_token_to_env


# --- Token exchange tests ---


def test_exchange_code_returns_token():
    """exchange_code_for_token should return the user access token on success."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ok": True,
        "authed_user": {"access_token": "xoxp-new-token-123"},
    }

    with patch("slack_auth.requests.post", return_value=mock_response) as mock_post:
        token = exchange_code_for_token("test-code", "client-id", "client-secret")

    assert token == "xoxp-new-token-123"
    mock_post.assert_called_once()
    call_data = mock_post.call_args[1]["data"]
    assert call_data["code"] == "test-code"
    assert call_data["client_id"] == "client-id"
    assert call_data["client_secret"] == "client-secret"


def test_exchange_code_raises_on_slack_error():
    """Should raise RuntimeError when Slack returns ok=false."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": False, "error": "invalid_code"}

    with patch("slack_auth.requests.post", return_value=mock_response):
        try:
            exchange_code_for_token("bad-code", "client-id", "client-secret")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "invalid_code" in str(e)


def test_exchange_code_raises_when_no_user_token():
    """Should raise RuntimeError when response has ok=true but no authed_user token."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "authed_user": {}}

    with patch("slack_auth.requests.post", return_value=mock_response):
        try:
            exchange_code_for_token("code", "cid", "csec")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "No user access token" in str(e)


# --- .env writing/updating tests ---


def test_save_token_creates_env_file():
    """save_token_to_env should create a new .env file if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        assert not env_path.exists()

        save_token_to_env("xoxp-brand-new", env_path=env_path)

        assert env_path.exists()
        content = env_path.read_text()
        assert content == "SLACK_USER_TOKEN=xoxp-brand-new\n"


def test_save_token_updates_existing_value():
    """save_token_to_env should replace an existing SLACK_USER_TOKEN line."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.write_text("SOME_VAR=hello\nSLACK_USER_TOKEN=xoxp-old-token\nOTHER=world\n")

        save_token_to_env("xoxp-updated-token", env_path=env_path)

        content = env_path.read_text()
        assert "SLACK_USER_TOKEN=xoxp-updated-token" in content
        assert "xoxp-old-token" not in content
        # Other vars should be preserved
        assert "SOME_VAR=hello" in content
        assert "OTHER=world" in content


def test_save_token_appends_when_key_missing():
    """save_token_to_env should append SLACK_USER_TOKEN if the key is not present."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.write_text("SOME_VAR=hello\n")

        save_token_to_env("xoxp-appended", env_path=env_path)

        content = env_path.read_text()
        assert "SOME_VAR=hello" in content
        assert "SLACK_USER_TOKEN=xoxp-appended" in content


def test_save_token_appends_newline_if_missing():
    """save_token_to_env should add a newline before appending if file doesn't end with one."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        env_path.write_text("SOME_VAR=hello")  # no trailing newline

        save_token_to_env("xoxp-appended", env_path=env_path)

        content = env_path.read_text()
        assert "SOME_VAR=hello\nSLACK_USER_TOKEN=xoxp-appended\n" == content
