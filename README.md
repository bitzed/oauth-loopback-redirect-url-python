# Zoom OAuth — Loopback Redirect URI + PKCE (Python)

A **minimal, dependency-free** proof-of-concept for Zoom's
[**"Using a loopback redirect URI"**](https://developers.zoom.us/docs/integrations/oauth/)
flow — the [RFC 8252](https://datatracker.ietf.org/doc/html/rfc8252) pattern for
native / desktop / CLI apps that can't expose a public HTTPS callback.

One file. Python 3.9+. **Standard library only** — no `pip install`, no venv, no
`requests`. Every step of the flow prints to the terminal so you can *watch* it
happen.

> **Goal:** understand the mechanics. This is a learning PoC, not production code.

This is the Python port of the Node.js version:
[oauth-loopback-redirect-url-test](https://github.com/bitzed/oauth-loopback-redirect-url-test).

---

## What is a loopback redirect URI?

Instead of registering a public `https://…/callback` endpoint, a native app:

1. Starts a **temporary local HTTP server** bound to the loopback interface on
   an **OS-assigned ephemeral port** (`127.0.0.1:0`).
2. Reads the assigned port and builds the redirect URI, e.g.
   `http://127.0.0.1:52936/callback`.
3. Opens the **system browser** to Zoom's authorize endpoint.
4. Captures the `code` when the browser is redirected back to the local server.
5. Exchanges the code for tokens using **PKCE** (no client secret).
6. **Shuts the listener down immediately.**

```
  main.py                          System browser                 Zoom
     │                                   │                          │
     ├─ 1. PKCE verifier + challenge     │                          │
     ├─ 2. bind 127.0.0.1:0  ────────┐   │                          │
     │      OS assigns :52936        │   │                          │
     ├─ 3. open authorize URL ───────┼──▶│──── /oauth/authorize ───▶│
     │                               │   │                          │
     │                               │   │◀─── consent screen ──────┤
     │                               │   │                          │
     │   4. ?code=…&state=…  ◀───────┴───┤◀─── 302 to 127.0.0.1 ────┤
     ├─ 5. validate state                │                          │
     ├─ 6. POST /oauth/token ────────────┼─────────────────────────▶│
     │      client_id + code_verifier    │      (no client secret)  │
     │◀─────────────────────────────── access_token ────────────────┤
     └─ 7. GET /v2/users/me ─────────────┼─────────────────────────▶│
```

### Key rules (Zoom's implementation)

| Rule | Detail |
|------|--------|
| **PKCE / native only** | Loopback works only for **PKCE-enabled public clients or native apps**. A plain confidential client gets `Invalid redirect: <uri>`. |
| **Only the port is relaxed** | Zoom matches the registered URI but **ignores the port**. Scheme, numeric host, path, query, fragment, and userinfo must match exactly. ⚠️ See [Documented vs. observed](#documented-vs-observed) — this did not hold in testing. |
| **No `localhost`** | Use numeric literals only: `127.0.0.1` (IPv4) or `::1` (IPv6). They are matched as **different hosts**. |
| **Port optional at registration** | Register `http://127.0.0.1/callback` (no port) or with any port. |
| **Server first, then browser** | Bind to port `0`, read the real port, *then* open the browser. |
| **Token exchange has no secret** | PKCE public clients send `client_id` + `code_verifier` in the body — **no `Authorization` header**. |

---

## Documented vs. observed

> **Status: port relaxation could not be reproduced.**
> Tested 2026-07-07 against a **Development** General app with
> *Use Public Client OAuth* **ON** (PKCE public client, no secret), authorize
> endpoint `https://zoom.us/oauth/authorize`.

The documentation states that the port is ignored during redirect-URI matching.
In practice **only an exact match — port included — was accepted**:

| Registered redirect URI | Redirect URI sent at runtime | Result |
|---|---|---|
| `http://127.0.0.1/callback` | `http://127.0.0.1/callback` (exact) | ✅ consent → `?code=…&state=…` |
| `http://127.0.0.1/callback` | `http://127.0.0.1:49999/callback` | ❌ `Invalid redirect: … (4700)` |
| `http://127.0.0.1:3000/callback` | `http://127.0.0.1:3000/callback` (exact) | ✅ consent → `?code=…&state=…` |
| `http://127.0.0.1:3000/callback` | `http://127.0.0.1:49999/callback` | ❌ `Invalid redirect: … (4700)` |

The ✅ rows confirm the client *is* loopback-eligible (a confidential client is
rejected for any `127.0.0.1` redirect), so only the **port-relaxation path** is
not firing.

**Why this matters:** an RFC 8252-compliant client binds to an OS-assigned
ephemeral port on every run, so it cannot know — let alone pre-register — its
port. Without port relaxation the loopback flow collapses back into ordinary
fixed-port registration.

This PoC therefore supports **both** modes via `--port` / `LOOPBACK_PORT`, so you
can flip between them and see the difference live:

| `--port` | Mode | Expectation |
|---|---|---|
| `0` (default) | Ephemeral — the real RFC 8252 flow | Works only if port relaxation is in effect |
| e.g. `3000` | Fixed — exact-match workaround | Works today, but is *not* RFC 8252 |

---

## Prerequisites — Zoom Marketplace app

1. Create a **General app** at <https://marketplace.zoom.us/>.
2. **App Credentials → toggle `Use Public Client OAuth` ON** → copy the
   **Public Client ID**. (A public client needs no secret.)
3. **OAuth Allow List** → add a loopback redirect URI. Which one depends on the
   mode you want to exercise:

   | Mode | Register | Then run with |
   |---|---|---|
   | Ephemeral (RFC 8252) | `http://127.0.0.1/callback` | `--port 0` (default) |
   | Fixed (exact match) | `http://127.0.0.1:3000/callback` | `--port 3000` |

   In fixed mode the registered string must match the runtime redirect URI
   **byte for byte**, port included.
4. **Scopes** → add `user:read:user` (granular) or `user:read` (classic) so the
   final `GET /users/me` call succeeds.

> The consent screen is always shown for secret-less public clients (RFC 6819).

---

## Run it

```bash
git clone https://github.com/bitzed/oauth-loopback-redirect-url-python.git
cd oauth-loopback-redirect-url-python

python3 main.py --client-id YOUR_PUBLIC_CLIENT_ID
```

Or put your values in `.env` (`cp .env.example .env`) and just run
`python3 main.py`.

The system browser opens Zoom's consent screen. Click **Allow**, and the
terminal walks through the rest.

### What you'll see

```
──────── Zoom OAuth · loopback + PKCE ────────
Generated PKCE + state
          { "code_challenge_method": "S256", "code_verifier_len": 43, … }
Loopback listener bound to 127.0.0.1:54929 (ephemeral port)
          { "redirect_uri": "http://127.0.0.1:54929/callback" }
Authorize URL
          https://zoom.us/oauth/authorize?response_type=code&…
Loopback received request: GET /callback?code=…&state=…
Loopback listener closed
State parameter validated
POST https://zoom.us/oauth/token
Token endpoint responded
          { "token_type": "bearer", "expires_in": 3599, "access_token": "eyJzdi…(1089 chars)" }
GET https://api.zoom.us/v2/users/me
Fetched /users/me
          { "display_name": "…", "email": "…", "account_id": "…" }
──────── Flow complete 🎉 ────────
```

---

## Configuration

Every setting has a CLI flag and an environment variable. **CLI flags win.**

| Flag | Env var | Default | Notes |
|------|---------|---------|-------|
| `--client-id` | `PUBLIC_CLIENT_ID` | — | From *Use Public Client OAuth*. |
| `--path` | `REDIRECT_PATH` | `/callback` | Must match the path you registered. |
| `--host` | `LOOPBACK_HOST` | `127.0.0.1` | Numeric literal only. `::1` also works. |
| `--port` | `LOOPBACK_PORT` | `0` | `0` = OS-assigned ephemeral port (RFC 8252). A fixed value pins the listener for an exact-match run. |
| `--authorize-base` | `AUTHORIZE_BASE_URL` | `https://zoom.us/oauth/authorize` | |
| `--token-base` | `TOKEN_BASE_URL` | `https://zoom.us/oauth/token` | |
| `--api-base` | `API_BASE_URL` | `https://api.zoom.us` | |
| `--timeout` | — | `300` | Seconds to wait for the browser redirect. |
| `--no-browser` | — | off | Print the authorize URL instead of opening a browser. Handy over SSH. |

---

## Code tour

`main.py` is one file, ordered the way the flow runs:

| Section | What it does |
|---|---|
| `log()` / `redact()` | Coloured step logging; secrets shown as shape only, never value. |
| `generate_pkce()` | 32 random bytes → base64url `code_verifier`; SHA-256 → `code_challenge` (S256). |
| `generate_state()` | Opaque CSRF token echoed back by Zoom. |
| `_LoopbackServer` / `_CallbackHandler` | One-shot `http.server` that captures `?code&state`, 404s everything else (browsers ask for `/favicon.ico`), and serves a small "you can close this tab" page. |
| `start_listener()` | Binds **first**, then derives the redirect URI from the port the OS actually gave us. Brackets IPv6 hosts. |
| `wait_for_redirect()` | Serves until the callback lands or the timeout expires, then closes the socket immediately. |
| `build_authorize_url()` | Assembles the authorize query. No `scope` param — Zoom uses the app's build-flow scopes. |
| `exchange_token()` | `POST /oauth/token`, form-encoded, `client_id` + `code_verifier`, **no `Authorization` header**. |
| `get_me()` | `GET /v2/users/me` to prove the token works. |
| `main()` | Wires it together and enforces the guards (no `localhost`, state must match). |

---

## Security notes (baked into the code)

- **PKCE always** (`S256`) — prevents authorization-code interception.
- **`state` validated** on every callback — CSRF protection. Mismatch aborts
  before the token exchange.
- **Bind only to loopback** — the listener never binds `0.0.0.0`.
- **Listener closed immediately** after the redirect — minimal exposure window.
- **Fresh ephemeral port per run** — never cached or reused (unless you pin
  `--port` to reproduce an exact-match run).
- **Tokens redacted in logs** — you see their shape, not their value.
- **`allow_reuse_address = False`** — a busy fixed port fails loudly instead of
  silently stealing the socket.

---

## Common issues

| Symptom | Cause / fix |
|---------|-------------|
| `Invalid redirect: <uri>` on the consent page | App isn't PKCE/native, or you used `localhost`, or scheme/host/path don't match the registered URI. |
| `Invalid redirect: … (4700)` with `--port 0` | Port relaxation is not in effect — see [Documented vs. observed](#documented-vs-observed). Pin `--port` to a registered port to get through. |
| `4709 redirect uri mismatch` | Registered path ≠ runtime path. |
| `invalid_client` from `/oauth/token` | Wrong Public Client ID, or the app isn't a public client (*Use Public Client OAuth* is off). |
| `/users/me` returns 4711 / scope error | Add `user:read:user` (or `user:read`) to the app's scopes and re-authorize. |
| `Could not bind … Address already in use` | Only happens with a pinned `--port`. Pick a free port and register the matching URI. With `0` the OS always finds a free one. |
| Browser doesn't open (SSH / headless) | Use `--no-browser` and paste the URL yourself. |

---

## References

- [Zoom OAuth docs](https://developers.zoom.us/docs/integrations/oauth/) — *Using a loopback redirect URI*
- [RFC 8252 — OAuth 2.0 for Native Apps](https://datatracker.ietf.org/doc/html/rfc8252)
- [RFC 7636 — PKCE](https://datatracker.ietf.org/doc/html/rfc7636)
- [OAuth Allow List configuration](https://developers.zoom.us/docs/build-flow/basic-info/oauth-info/)
- [Node.js version of this PoC](https://github.com/bitzed/oauth-loopback-redirect-url-test)

## License

MIT
