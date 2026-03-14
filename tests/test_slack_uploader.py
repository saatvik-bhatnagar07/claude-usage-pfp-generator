from unittest.mock import patch, MagicMock

from slack_uploader import upload_profile_photo


def test_upload_calls_slack_api():
    """upload_profile_photo should POST to users.setPhoto with the image."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}

    with patch("slack_uploader.requests.post", return_value=mock_response) as mock_post:
        upload_profile_photo(b"fake-png-bytes", token="xoxp-fake-token")

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "users.setPhoto" in call_args[0][0]
    assert call_args[1]["headers"]["Authorization"] == "Bearer xoxp-fake-token"


def test_upload_raises_on_slack_error():
    """Should raise RuntimeError if Slack returns ok=false."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": False, "error": "invalid_auth"}

    with patch("slack_uploader.requests.post", return_value=mock_response):
        try:
            upload_profile_photo(b"fake-png-bytes", token="xoxp-fake-token")
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "invalid_auth" in str(e)
