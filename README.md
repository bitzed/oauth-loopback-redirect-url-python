> ⚠️ The following sample application is a personal, open-source project shared by the app creator and not an officially supported Zoom Communications, Inc. sample application. Zoom Communications, Inc., its employees and affiliates are not responsible for the use and maintenance of this application. Please use this sample application for inspiration, exploration and experimentation at your own risk and enjoyment. You may reach out to the app creator and broader Zoom Developer community on https://devforum.zoom.us/ for technical discussion and assistance, but understand there is no service level agreement support for this application. Thank you and happy coding!

> ⚠️ このサンプルのアプリケーションは、Zoom Communications, Inc.の公式にサポートされているものではなく、アプリ作成者が個人的に公開しているオープンソースプロジェクトです。Zoom Communications, Inc.とその従業員、および関連会社は、本アプリケーションの使用や保守について責任を負いません。このサンプルアプリケーションは、あくまでもインスピレーション、探求、実験のためのものとして、ご自身の責任と楽しみの範囲でご活用ください。技術的な議論やサポートが必要な場合は、アプリ作成者やZoom開発者コミュニティ（ https://devforum.zoom.us/ ）にご連絡いただけますが、このアプリケーションにはサービスレベル契約に基づくサポートがないことをご理解ください。

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
