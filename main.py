#!/usr/bin/env python3
"""
Zoom OAuth — loopback redirect URI + PKCE. Minimal PoC, standard library only.

This is the RFC 8252 (OAuth 2.0 for Native Apps) pattern for desktop / CLI apps
that cannot expose a public HTTPS callback:

    1. Generate a PKCE code_verifier + code_challenge (S256) and a state value.
    2. Bind a temporary HTTP server to the loopback interface FIRST, so we can
       read the port the OS actually gave us.
    3. Open the system browser to Zoom's authorize endpoint, passing the
       redirect_uri that points at that local listener.
    4. Capture ?code=…&state=… when the browser is redirected back.
    5. Validate state, then exchange the code for tokens using the code_verifier
       (a public client sends NO client secret).
    6. Shut the listener down immediately, then prove the token works.

Every step is printed so you can watch the flow happen. Secrets are redacted.

    python3 main.py --client-id <PUBLIC_CLIENT_ID>

See README.md for the LOOPBACK_PORT / --port distinction, which is the whole
reason this PoC exists.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── Logging ──────────────────────────────────────────────────────────────────
# A tiny coloured logger. Nothing clever — it just makes the flow readable.

_COLORS = {
    "info": "\033[0m",
    "step": "\033[94m",
    "ok": "\033[92m",
    "warn": "\033[93m",
    "error": "\033[91m",
    "net": "\033[96m",
}
_RESET = "\033[0m"
_USE_COLOR = sys.stdout.isatty()


def log(level: str, message: str, detail: object | None = None) -> None:
    color = _COLORS.get(level, "") if _USE_COLOR else ""
    reset = _RESET if _USE_COLOR else ""
    print(f"{color}{time.strftime('%H:%M:%S')}  {message}{reset}")
    if detail is not None:
        text = detail if isinstance(detail, str) else json.dumps(detail, indent=2)
        for line in text.splitlines():
            print(f"          {line}")
    # Flush explicitly: stdout is block-buffered when piped to a file, and this
    # flow spends minutes blocked on the browser. Buffered logs would be useless.
    sys.stdout.flush()


def redact(value: str | None, keep: int = 6) -> str | None:
    """Show the shape of a secret without leaking it."""
    if not value:
        return value
    return f"{value[:keep]}…({len(value)} chars)"


# ── Step 1: PKCE (RFC 7636) ──────────────────────────────────────────────────


def generate_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) using the S256 method.

    The verifier is a high-entropy random string. The challenge is its SHA-256
    digest, base64url-encoded without padding. Only the challenge travels in the
    authorize request; the verifier is revealed later at the token endpoint,
    which is what makes a stolen authorization code useless to an attacker.
    """
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def generate_state() -> str:
    """Opaque CSRF token echoed back by the authorization server."""
    return base64.urlsafe_b64encode(secrets.token_bytes(16)).decode().rstrip("=")


# ── Step 2: the loopback listener ────────────────────────────────────────────

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Zoom OAuth</title><style>
body{{font-family:system-ui,sans-serif;background:#0b1020;color:#e8ecf4;
display:grid;place-items:center;height:100vh;margin:0}}
.card{{background:#141b34;padding:2rem 2.5rem;border-radius:14px;text-align:center}}
.ok{{color:#4ade80}}.err{{color:#f87171}}p{{color:#9fb0d0}}
</style></head><body><div class="card">{body}
<p>You can close this tab and return to the terminal.</p></div></body></html>"""


class _LoopbackServer(HTTPServer):
    """One-shot HTTP server that stores the captured OAuth query params."""

    allow_reuse_address = False  # surface EADDRINUSE instead of hiding it

    def __init__(self, addr, handler, *, ipv6: bool, expected_path: str):
        if ipv6:
            self.address_family = socket.AF_INET6
        super().__init__(addr, handler)
        self.expected_path = expected_path
        self.result: dict[str, str] | None = None


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 — name fixed by BaseHTTPRequestHandler
        parsed = urllib.parse.urlparse(self.path)
        log("step", f"Loopback received request: GET {self.path}")

        # Browsers also ask for /favicon.ico — ignore anything but our path.
        if parsed.path != self.server.expected_path:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

        if "error" in params:
            body = (
                f'<h1 class="err">Authorization failed</h1>'
                f'<p>{params["error"]}: {params.get("error_description", "")}</p>'
            )
            self._respond(400, body)
        else:
            self._respond(200, '<h1 class="ok">Authorization received &check;</h1>')

        self.server.result = params

    def _respond(self, status: int, body: str) -> None:
        payload = _PAGE.format(body=body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args) -> None:
        """Silence BaseHTTPRequestHandler's own stderr logging — we do our own."""


def start_listener(host: str, path: str, port: int) -> tuple[_LoopbackServer, str]:
    """Bind the listener and return (server, redirect_uri).

    `port=0` asks the OS for a free ephemeral port — the RFC 8252 behaviour.
    A non-zero port pins the listener so the runtime redirect URI can match a
    registered URI exactly, port included.
    """
    ipv6 = ":" in host
    server = _LoopbackServer((host, port), _CallbackHandler, ipv6=ipv6, expected_path=path)

    actual_port = server.server_address[1]
    host_for_uri = f"[{host}]" if ipv6 else host
    redirect_uri = f"http://{host_for_uri}:{actual_port}{path}"

    kind = "ephemeral" if port == 0 else "fixed"
    log("ok", f"Loopback listener bound to {host}:{actual_port} ({kind} port)",
        {"redirect_uri": redirect_uri})
    return server, redirect_uri


def wait_for_redirect(server: _LoopbackServer, timeout_s: float) -> dict[str, str]:
    """Serve requests until the callback arrives, then close immediately."""
    deadline = time.monotonic() + timeout_s
    server.timeout = 1.0  # so handle_request() returns and we can re-check the clock
    try:
        while server.result is None and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
        log("step", "Loopback listener closed")

    if server.result is None:
        raise TimeoutError(f"No redirect received within {timeout_s:.0f}s")
    return server.result


# ── Steps 3, 5, 6: talking to Zoom ───────────────────────────────────────────


def build_authorize_url(authorize_base: str, client_id: str, redirect_uri: str,
                        challenge: str, state: str) -> str:
    """Zoom uses the app's build-flow scopes, so no `scope` param is sent."""
    query = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    })
    return f"{authorize_base}?{query}"


def _post_form(url: str, fields: dict[str, str]) -> dict:
    data = urllib.parse.urlencode(fields).encode("ascii")
    request = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def exchange_token(token_base: str, client_id: str, code: str,
                   redirect_uri: str, verifier: str) -> dict:
    """Trade the authorization code for tokens.

    A PKCE public client sends client_id + code_verifier in the body and has NO
    Authorization header — there is no client secret to send.
    """
    fields = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }
    log("net", f"POST {token_base}", {
        **fields,
        "code": redact(code),
        "code_verifier": redact(verifier),
    })

    tokens = _post_form(token_base, fields)
    log("ok", "Token endpoint responded", {
        "token_type": tokens.get("token_type"),
        "expires_in": tokens.get("expires_in"),
        "scope": tokens.get("scope"),
        "access_token": redact(tokens.get("access_token")),
        "refresh_token": redact(tokens.get("refresh_token")),
    })
    return tokens


def get_me(api_base: str, access_token: str) -> dict:
    """Prove the token works. Needs scope user:read:user (or classic user:read)."""
    endpoint = f"{api_base}/v2/users/me"
    log("net", f"GET {endpoint}", {"authorization": f"Bearer {redact(access_token)}"})

    request = urllib.request.Request(
        endpoint, headers={"Authorization": f"Bearer {access_token}"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        me = json.loads(response.read())

    log("ok", "Fetched /users/me", {
        "id": me.get("id"),
        "display_name": me.get("display_name"),
        "email": me.get("email"),
        "account_id": me.get("account_id"),
    })
    return me


# ── Wiring ───────────────────────────────────────────────────────────────────


def load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader so the PoC stays dependency-free."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def parse_args() -> argparse.Namespace:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Zoom OAuth loopback + PKCE PoC (standard library only).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--client-id", default=os.environ.get("PUBLIC_CLIENT_ID", ""),
                        help="Public Client ID (App Credentials → Use Public Client OAuth)")
    parser.add_argument("--path", default=os.environ.get("REDIRECT_PATH", "/callback"),
                        help="Path portion of the redirect URI")
    parser.add_argument("--host", default=os.environ.get("LOOPBACK_HOST", "127.0.0.1"),
                        help="Numeric loopback literal: 127.0.0.1 or ::1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("LOOPBACK_PORT", "0")),
                        help="0 = OS-assigned ephemeral port (RFC 8252); "
                             "non-zero pins the listener for an exact-match run")
    parser.add_argument("--authorize-base",
                        default=os.environ.get("AUTHORIZE_BASE_URL",
                                               "https://zoom.us/oauth/authorize"))
    parser.add_argument("--token-base",
                        default=os.environ.get("TOKEN_BASE_URL", "https://zoom.us/oauth/token"))
    parser.add_argument("--api-base",
                        default=os.environ.get("API_BASE_URL", "https://api.zoom.us"))
    parser.add_argument("--timeout", type=float, default=300.0,
                        help="Seconds to wait for the browser redirect")
    parser.add_argument("--no-browser", action="store_true",
                        help="Print the authorize URL instead of opening a browser")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.client_id:
        log("error", "No client id. Pass --client-id or set PUBLIC_CLIENT_ID in .env")
        return 2
    if "localhost" in args.host.lower():
        log("error", "Use a numeric loopback literal (127.0.0.1 or ::1), never 'localhost'. "
                     "Zoom rejects localhost, and RFC 8252 §8.3 recommends against it.")
        return 2

    log("info", "──────── Zoom OAuth · loopback + PKCE ────────")

    # 1. PKCE + state.
    verifier, challenge = generate_pkce()
    state = generate_state()
    log("step", "Generated PKCE + state", {
        "code_challenge_method": "S256",
        "code_verifier_len": len(verifier),
        "code_challenge": challenge,
        "state": state,
    })

    # 2. Listener FIRST — we cannot build the redirect URI until we know the port.
    try:
        server, redirect_uri = start_listener(args.host, args.path, args.port)
    except OSError as err:
        log("error", f"Could not bind {args.host}:{args.port} — {err}")
        return 1

    if args.port == 0:
        log("warn", "Ephemeral port mode (RFC 8252). This only succeeds if Zoom really "
                    "ignores the port when matching. Registered URI in the OAuth Allow "
                    f'List: "http://{args.host}{args.path}" (with or without a port).')
    else:
        log("warn", "Fixed port mode — exact-match workaround, NOT RFC 8252. Register "
                    f'this EXACT string in the OAuth Allow List: "{redirect_uri}"')

    # 3. Send the user to Zoom.
    authorize_url = build_authorize_url(
        args.authorize_base, args.client_id, redirect_uri, challenge, state
    )
    log("step", "Authorize URL", authorize_url)
    if args.no_browser:
        log("info", "Open the URL above manually (--no-browser).")
    else:
        webbrowser.open(authorize_url)
        log("info", "Opened the system browser. Waiting for the redirect…")

    # 4. Capture the redirect, then 5. validate state.
    try:
        params = wait_for_redirect(server, args.timeout)
    except TimeoutError as err:
        log("error", str(err))
        return 1

    if "error" in params:
        log("error", f'Authorization error: {params["error"]}',
            params.get("error_description"))
        return 1

    log("step", "Redirect captured", {
        "code": redact(params.get("code")),
        "state": params.get("state"),
    })
    if params.get("state") != state:
        log("error", "State mismatch (possible CSRF) — aborting",
            {"expected": state, "received": params.get("state")})
        return 1
    log("ok", "State parameter validated")

    # 6. Token exchange, then prove the token works.
    try:
        tokens = exchange_token(
            args.token_base, args.client_id, params["code"], redirect_uri, verifier
        )
        get_me(args.api_base, tokens["access_token"])
    except urllib.error.HTTPError as err:
        # The response body is where Zoom explains itself (e.g. 4700 invalid redirect).
        log("error", f"HTTP {err.code} from {err.url}", err.read().decode("utf-8", "replace"))
        return 1
    except urllib.error.URLError as err:
        log("error", f"Network error: {err.reason}")
        return 1

    log("ok", "──────── Flow complete 🎉 ────────")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(130)
