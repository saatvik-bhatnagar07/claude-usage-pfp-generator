"""Uploads an image as the user's Slack profile photo.

Uses the users.setPhoto API endpoint. Requires a user token (xoxp-)
with the users.profile:write scope.
"""

import requests


def upload_profile_photo(image_bytes: bytes, token: str) -> None:
    """Upload image bytes as the authenticated user's Slack profile photo.

    Args:
        image_bytes: PNG image data.
        token: Slack user token (xoxp-...) with users.profile:write scope.

    Raises:
        RuntimeError: If Slack API returns an error.
    """
    response = requests.post(
        "https://slack.com/api/users.setPhoto",
        headers={"Authorization": f"Bearer {token}"},
        files={"image": ("pfp.png", image_bytes, "image/png")},
    )

    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")
