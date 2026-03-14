"""Slack OAuth flow for obtaining a user token.

Starts a local HTTPS server (self-signed cert), opens the browser to Slack's
OAuth authorize page, catches the redirect with the authorization code, and
exchanges it for a user token.
"""

import os
import re
import ssl
import subprocess
import tempfile
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests

REDIRECT_URI = "https://127.0.0.1:8338/callback"
USER_SCOPES = "users.profile:write"
SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

# Default Slack app credentials — shared across the team.
# Override via SLACK_CLIENT_ID / SLACK_CLIENT_SECRET env vars if needed.
DEFAULT_CLIENT_ID = ""
DEFAULT_CLIENT_SECRET = ""


def _generate_self_signed_cert(cert_dir: str) -> tuple[str, str]:
    """Generate a self-signed certificate for the local HTTPS server.

    Returns (cert_path, key_path).
    """
    cert_path = os.path.join(cert_dir, "cert.pem")
    key_path = os.path.join(cert_dir, "key.pem")
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key_path, "-out", cert_path,
            "-days", "1", "-nodes",
            "-subj", "/CN=127.0.0.1",
        ],
        capture_output=True,
        check=True,
    )
    return cert_path, key_path


def _build_authorize_url(client_id: str) -> str:
    """Build the Slack OAuth authorize URL."""
    params = {
        "client_id": client_id,
        "user_scope": USER_SCOPES,
        "redirect_uri": REDIRECT_URI,
    }
    return f"{SLACK_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str, client_id: str, client_secret: str) -> str:
    """Exchange an authorization code for a user token via Slack's oauth.v2.access endpoint.

    Returns the user access token string.
    Raises RuntimeError on failure.
    """
    resp = requests.post(
        SLACK_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
    )
    resp.raise_for_status()
    data = resp.json()

    if not data.get("ok"):
        raise RuntimeError(f"Slack token exchange failed: {data.get('error', 'unknown error')}")

    # For user-scope-only apps the token is in authed_user.access_token
    token = data.get("authed_user", {}).get("access_token")
    if not token:
        raise RuntimeError("No user access token in Slack response")

    return token


def save_token_to_env(token: str, env_path: Path | None = None) -> None:
    """Save/update SLACK_USER_TOKEN in the .env file.

    Creates the file if it doesn't exist. Updates the value if the key already exists.
    """
    if env_path is None:
        env_path = Path(__file__).resolve().parent / ".env"

    if env_path.exists():
        content = env_path.read_text()
        # Replace existing SLACK_USER_TOKEN line
        if re.search(r"^SLACK_USER_TOKEN=.*$", content, re.MULTILINE):
            content = re.sub(
                r"^SLACK_USER_TOKEN=.*$",
                f"SLACK_USER_TOKEN={token}",
                content,
                flags=re.MULTILINE,
            )
        else:
            # Append to end
            if not content.endswith("\n"):
                content += "\n"
            content += f"SLACK_USER_TOKEN={token}\n"
        env_path.write_text(content)
    else:
        env_path.write_text(f"SLACK_USER_TOKEN={token}\n")


def _extract_code_from_url(url: str) -> str | None:
    """Extract the authorization code from a callback URL."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    codes = params.get("code")
    return codes[0] if codes else None


def run_oauth_flow(client_id: str, client_secret: str) -> str:
    """Run the full OAuth flow: open browser, authorize, exchange code, save token.

    Two ways to complete the flow:
    1. Automatic: local HTTPS server catches the redirect (requires accepting self-signed cert)
    2. Manual: paste the redirect URL from the browser's address bar

    Returns the user access token.
    """
    auth_code = None
    server_ready = False

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            if "code" in params:
                auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Success!</h1>"
                    b"<p>You can close this tab and return to your terminal.</p>"
                    b"</body></html>"
                )
            else:
                error = params.get("error", ["unknown"])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    f"<html><body><h1>Error</h1><p>{error}</p></body></html>".encode()
                )

        def log_message(self, format, *args):
            pass

    # Try to start HTTPS server in background; fall back to manual entry
    try:
        cert_dir_obj = tempfile.TemporaryDirectory()
        cert_dir = cert_dir_obj.name
        cert_path, key_path = _generate_self_signed_cert(cert_dir)

        server = HTTPServer(("127.0.0.1", 8338), CallbackHandler)
        server.timeout = 120  # 2 minute timeout
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(cert_path, key_path)
        server.socket = ssl_ctx.wrap_socket(server.socket, server_side=True)
        server_ready = True
    except Exception as e:
        print(f"Warning: Could not start HTTPS server ({e})")
        print("You'll need to paste the redirect URL manually.\n")

    authorize_url = _build_authorize_url(client_id)
    print("Opening browser for Slack authorization...")
    print(f"  URL: {authorize_url}\n")
    webbrowser.open(authorize_url)

    if server_ready:
        print("After authorizing, Slack will redirect to https://127.0.0.1:8338/callback")
        print()
        print("Option A — automatic (click through the browser cert warning):")
        print("  Your browser will show a security warning (self-signed cert).")
        print("  Click 'Advanced' → 'Proceed to 127.0.0.1'.")
        print()
        print("Option B — manual (if the cert warning blocks you):")
        print("  Copy the full URL from your browser's address bar and paste it here.")
        print()

        # Run server in a thread so we can also read stdin
        import threading

        def serve_once():
            nonlocal auth_code
            try:
                server.handle_request()
            except ssl.SSLError:
                pass  # Browser rejected cert — user will paste manually
            finally:
                server.server_close()

        server_thread = threading.Thread(target=serve_once, daemon=True)
        server_thread.start()

        # Wait for either automatic callback or manual input
        print("Waiting... (paste the redirect URL here if automatic callback doesn't work)")
        while not auth_code:
            server_thread.join(timeout=0.5)
            if auth_code:
                break
            if not server_thread.is_alive():
                # Server finished without getting a code — ask for manual input
                break

        if not auth_code:
            print("\nAutomatic callback didn't work. Paste the full redirect URL from your browser:")
            url = input("> ").strip()
            auth_code = _extract_code_from_url(url)

        # Clean up
        try:
            cert_dir_obj.cleanup()
        except Exception:
            pass
    else:
        print("After authorizing on Slack, your browser will try to redirect to:")
        print(f"  {REDIRECT_URI}?code=XXXX")
        print("\nThe page won't load, but copy the full URL from the address bar and paste it here:")
        url = input("> ").strip()
        auth_code = _extract_code_from_url(url)

    if not auth_code:
        raise RuntimeError("Did not receive an authorization code from Slack")

    print("Authorization code received. Exchanging for token...")
    token = exchange_code_for_token(auth_code, client_id, client_secret)

    print("Token obtained. Saving to .env file...")
    save_token_to_env(token)

    print("Setup complete! SLACK_USER_TOKEN has been saved to .env")
    return token
