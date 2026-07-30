# Zoom OAuth — Loopback Redirect URI + PKCE (Python)

A **minimal, dependency-free** proof-of-concept for Zoom's
[**"Using a loopback redirect URI"**](https://developers.zoom.us/docs/integrations/oauth/)
flow — the [RFC 8252](https://datatracker.ietf.org/doc/html/rfc8252) pattern for
native / desktop / CLI apps that can't expose a public HTTPS callback.

One file. Python 3. **Standard library only** — no `pip install`, no venv.

This is the Python port of the Node.js version:
[oauth-loopback-redirect-url-test](https://github.com/bitzed/oauth-loopback-redirect-url-test).

---

## What is a loopback redirect URI?

Instead of registering a public `https://…/callback` endpoint, a native app:

1. Starts a **temporary local HTTP server** bound to the loopback interface
   (`127.0.0.1`).
2. Builds the redirect URI from that address, e.g. `http://127.0.0.1:3000/callback`.
3. Opens the **system browser** to Zoom's authorize endpoint.
4. Captures the `code` when the browser is redirected back to the local server.
5. Exchanges the code for tokens using **PKCE** (no client secret).
6. **Shuts the listener down immediately.**

```
  main.py                          System browser                 Zoom
     │                                   │                          │
     ├─ 1. PKCE verifier + challenge     │                          │
     ├─ 2. bind 127.0.0.1:PORT ──────┐   │                          │
     ├─ 3. open authorize URL ───────┼──▶│──── /oauth/authorize ───▶│
     │                               │   │◀─── consent screen ──────┤
     │   4. ?code=…&state=…  ◀───────┴───┤◀─── 302 to 127.0.0.1 ────┤
     ├─ 5. validate state                │                          │
     ├─ 6. POST /oauth/token ────────────┼─────────────────────────▶│
     │      client_id + code_verifier    │      (no client secret)  │
     │◀─────────────────────────────── access_token ────────────────┤
```

---

## How to test

1. Create a **General app** at <https://marketplace.zoom.us/>.
2. **App Credentials → toggle `Use Public Client OAuth` ON** → copy the
   **Public Client ID** (a public client needs no secret).
3. **OAuth Allow List** → add `http://127.0.0.1:3000/callback`.
4. Create `.env` (`cp .env.example .env`) and fill it in:

   ```dotenv
   PUBLIC_CLIENT_ID=your_public_client_id
   LOOPBACK_PORT=3000
   ```

5. Run it:

   ```bash
   python3 main.py
   ```

6. The system browser opens Zoom's consent screen. Click **Allow** — the terminal
   prints the authorize parameters and, after the redirect, the `access_token`.

> `LOOPBACK_PORT` must match the port in the registered redirect URI exactly.
> Set it to `0` for an OS-assigned ephemeral port (RFC 8252), but then the
> registered URI must be accepted without a fixed port.

## License

MIT
