import base64
import hashlib
import json
import os
import secrets
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "127.0.0.1"
CALLBACK_PATH = "/callback"
AUTHORIZE_URL = "https://zoom.us/oauth/authorize"
TOKEN_URL = "https://zoom.us/oauth/token"
# Enter "http://127.0.0.1:3000/callback" in your Zoom App's "Redirect URL for OAuth" field.

def load_env(path=".env"):
    for line in open(path):
        key, _, value = line.strip().partition("=")
        os.environ.setdefault(key, value)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Authorization received. You can close this tab.")

    def log_message(self, *_):
        pass


def main():
    load_env()
    client_id = os.environ["PUBLIC_CLIENT_ID"]
    port = int(os.environ.get("LOOPBACK_PORT") or 0)

    # 1. PKCE (RFC 7636) + state.
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    state = secrets.token_urlsafe(16)

    # 2. Listener FIRST — the redirect URI cannot exist until the socket does.
    server = HTTPServer((HOST, port), Handler)
    redirect_uri = f"http://{HOST}:{server.server_address[1]}{CALLBACK_PATH}"

    # 3. Send the user to Zoom, in their real browser.
    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    print("Generating Authorize URL from:")
    for key, value in auth_params.items():
        print(f"  {key}: {value}")
    authorize_url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(auth_params)
    webbrowser.open(authorize_url)

    # 4. Block until the browser hits the listener.
    server.handle_request()
    server.server_close()
    params = server.params

    # 5. Validate state BEFORE spending the code.
    assert params.get("state") == state, "state mismatch"

    # 6. Redeem the code for tokens (public client: no client secret).
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": params["code"],
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    tokens = json.loads(urllib.request.urlopen(req).read())

    print("access_token:", tokens["access_token"])


if __name__ == "__main__":
    main()
