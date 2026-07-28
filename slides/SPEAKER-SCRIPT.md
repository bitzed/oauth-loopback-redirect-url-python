# How to Use PKCE OAuth — Speaker Script

Companion to `deck.md` (29 slides). Slide numbers match the rendered deck.

**Format:** ~35 minutes of talking, ~10 minutes of live demo, questions at the end.
**Setup before you start:** terminal at ~18pt in the repo directory, a browser
window already signed in to Zoom, and a Marketplace app with
`http://127.0.0.1/callback` **and** `http://127.0.0.1:3000/callback` both
registered, so you can demo either path without editing anything live.

Timing guide:

| Part | Slides | Minutes |
|---|---|---|
| Opening | 1–2 | 2 |
| 1 · The use case | 3–7 | 8 |
| 2 · The sequence | 8–12 | 10 |
| 3 · The code | 13–20 | 12 |
| 4 · The demo | 21–29 | 13 |

---

## Slide 1 — Title

Good morning. This session is about one specific problem, and it has one
specific answer.

The problem: OAuth was designed assuming your application can keep a secret.
Most of the OAuth documentation you have read assumes there is a `client_secret`
sitting safely on a server you control. But a huge amount of software does not
work that way. Command-line tools, desktop applications, mobile apps — they all
run on somebody else's computer.

So today we answer: how does an application that cannot keep a secret prove to
Zoom that it is who it claims to be? The answer is PKCE, and by the end of this
session you will have run the whole flow yourself, in Python, with no libraries.

> Transition: Here is the shape of the next forty minutes.

---

## Slide 2 — What We Will Do

Four parts.

First, the use case — which applications actually need this, so you can tell
whether yours is one of them. Second, the sequence: we will walk all sixteen
steps of the flow, twice, because seeing it once is never enough. Third, the
code — a single Python file, standard library only, that you can read end to end.
Fourth, the demo: I run it, we read the log together, and then I deliberately
break it four different ways, because the errors are where you will actually
spend your time.

One thing to set expectations: this is a working sample, not a framework. The
point is that you can read every line.

> Transition: Part one. Who needs PKCE?

---

## Slide 3 — Part 1 divider

---

## Slide 4 — One Question Decides Everything

Everything on this slide follows from a single question: can your application
keep a secret?

Not "should it". Can it. This is a question about deployment, not about
discipline.

If the answer is no — if your code ships to the user's machine as a binary, a
script, an app bundle, or JavaScript in a browser — then you are a **public
client**. Look at the left side: desktop applications, CLI tools, mobile apps,
single-page apps. In every one of those cases the user has the bytes. They can
run `strings` on your binary. They can open devtools. They can decompile the
APK. Any secret you embed is not a secret; it is a delay.

For those clients, PKCE is not an enhancement. It is the mechanism that replaces
the secret.

On the right: server-side web applications and backend services. Those run on
hardware you control, so a secret in an environment variable or a vault really is
a secret. Note that even here PKCE is still advised — the current direction of
the specifications, OAuth 2.1, recommends PKCE for every client, confidential
ones included. It costs you almost nothing and closes a real attack.

For the rest of today we live in the bottom band: a CLI tool running on your own
machine.

> Transition: Let us be precise about what "no secret" means at the protocol level.

---

## Slide 5 — Public Client: No Secret Exists

This table is worth internalising because it removes a whole class of confusion.

People often assume that a public client has a secret and is just careless with
it. That is wrong. In a properly configured Zoom app with *Use Public Client
OAuth* enabled, there is no secret issued at all. There is nothing to leak.

Look at the last row — that is the row that matters. At the token endpoint, a
confidential client authenticates with `client_secret`. A public client
authenticates with `code_verifier`. Same slot in the protocol, completely
different mechanism. One is a long-lived shared credential. The other is a
one-time value your app invented eleven seconds ago.

> Transition: So if there is no secret, what actually stops an attacker?

---

## Slide 6 — So What Proves It Is Your App?

Here is the attack, in one sentence: if all you need to redeem an authorization
code is the code plus the `client_id`, and the `client_id` is public by
definition, then whoever steals the code wins.

And codes are stealable. On a shared machine, a malicious process can register
the same custom URI scheme as your app, or sit on a loopback port and wait. This
is called the authorization code interception attack, and it is the specific
reason PKCE exists.

PKCE's answer is elegant. Instead of shipping one secret with the application,
the application invents a new secret for every single authorization request.

Look at the two lines at the bottom. The `code_verifier` is a random string
between 43 and 128 characters. It never leaves the process during the first half
of the flow. What does leave is the `code_challenge` — the SHA-256 of the
verifier, base64url encoded.

And this is the whole trick, so let me say it slowly: **the challenge goes up
with the request, and the verifier goes up with the redemption.** Zoom stores the
challenge when it issues the code. Later, when someone tries to redeem that code,
they must present a verifier that hashes to the stored challenge. SHA-256 is
one-way, so seeing the challenge does not help you produce the verifier.

An attacker who intercepts the code has the code and nothing else. They cannot
redeem it.

One clarification that always comes up: PKCE does not encrypt anything. There is
no encryption here. It is a proof of possession built on a one-way hash.

> Transition: Now, where does that authorization code actually get delivered?

---

## Slide 7 — Why the Redirect Goes to Your Own Machine

OAuth delivers the authorization code by redirecting a browser to your
`redirect_uri`. For a web application that is easy — you have a public HTTPS
endpoint.

A CLI tool has no public endpoint. So we do something that sounds strange the
first time you hear it: the application starts a tiny web server on the user's
own machine, and points the redirect URI at that. This is specified in RFC 8252,
OAuth 2.0 for Native Apps, and it is called loopback interface redirection.

Follow the numbers. Five, first, at the bottom left: `main.py` starts a throwaway
HTTP server bound to `127.0.0.1`. One: it opens the system browser at Zoom's
authorize endpoint. Two: the browser loads the consent screen — and note that we
use the *system* browser deliberately, because that is where the user's Zoom
session already lives, and because the user can see the real URL in the address
bar. Three: after the user approves, Zoom sends a 302 pointing back at
`127.0.0.1`. Four: the browser follows it and hits our little server, which
captures the code.

Then step six, in red, and this one matters: the token exchange does not involve
the browser at all. Our process talks to Zoom directly over HTTPS. Only the
authorization code travels through the browser. The verifier and the token never
do.

Two properties worth calling out. The dashed box is your machine — nothing in
there is reachable from the internet, which is exactly why this is safe. And the
server is bound to `127.0.0.1`, not `0.0.0.0`. If you bind to `0.0.0.0` you have
just published your OAuth callback to the local network. Do not do that.

> Transition: Let us now walk the whole thing, step by step.

---

## Slide 8 — Part 2 divider

Sixteen steps, split into two halves. First half: getting the code. Second half:
turning it into a token.

---

## Slide 9 — Half One: Getting the Code

Four lanes. Our process, the loopback listener, the system browser, and Zoom's
authorize endpoint.

Step one: we generate the verifier, hash it into a challenge, and generate a
`state` value. All in memory, nothing on the network yet.

Steps two and three, and this ordering is not cosmetic: we bind the listener
*before* we know the port, and then we ask the operating system what port it gave
us. We asked for port zero, which means "you pick". It came back with 54929. Next
run it will be a different number.

Step four: we build the authorize URL. This carries the `client_id`, the
`redirect_uri` — which we could only construct after step three — the
`code_challenge`, the method `S256`, and the `state`. Then we open the browser.

Steps five and six: the browser hits Zoom, the user sees a consent screen and
clicks Allow. Note that for a secret-less public client the consent screen is
always shown. There is no silent path.

Step seven: Zoom responds with a 302 back to our loopback address, with the code
and state on the query string.

Step eight: the browser follows the redirect and hits our listener. We now have
the code.

Read the blue bar at the bottom before we move on. At this point the challenge
has been sent, and the verifier has not left the process. That asymmetry is the
entire security property.

> Transition: Second half. Now we spend the code.

---

## Slide 10 — Half Two: Redeeming the Code

Step nine: the listener hands the captured parameters back to our main flow.

Step ten, in orange, before anything else: does the returned `state` match the
one we generated? If not, we abort. We do not attempt the token exchange. We will
come back to why this check is separate from PKCE in two slides.

Step eleven: close the listener. Immediately. It has done its one job. Leaving a
local HTTP server running is a needless open door.

Step twelve: the token request. Look at what is in the body — grant type, code,
`client_id`, `redirect_uri`, `code_verifier`. And look at the red line: no
`client_secret`, and no `Authorization` header. If you have written a
confidential-client integration before, this is the part your fingers will get
wrong. There is no Basic auth here.

One detail people trip on: the `redirect_uri` in this request must be identical
to the one from step four. It is not used to redirect anything. It is used as an
integrity check.

Step thirteen, the red box — this is the moment the whole talk has been building
towards. Zoom takes the `code_verifier` we just sent, hashes it with SHA-256, and
compares it against the challenge it stored back at step four. Match, and we get
tokens. No match, and we get nothing.

Steps fourteen through sixteen: we receive the access token, and we call
`/v2/users/me` to prove it actually works. Always end an OAuth implementation
with a real API call. A token you have not used is a token you have not tested.

And now the bar at the bottom pays off. Remember the attacker from slide six, who
intercepted the code at step eight. They never had the verifier. Step thirteen
rejects them. That is PKCE.

> Transition: Two implementation details that cost people entire afternoons.

---

## Slide 11 — Two Rules That Cost People Hours

Two rules. Both boring. Both will bite you.

Rule one: use `127.0.0.1`, never `localhost`. `localhost` is a hostname, which
means it goes through name resolution. It may resolve to IPv4 or to IPv6
depending on the machine, which means the redirect can arrive somewhere your
listener is not. It can also be redirected through a hosts file. RFC 8252
section 8.3 recommends the numeric IP literal for exactly these reasons, and Zoom
rejects `localhost` outright in the OAuth Allow List.

Related, and easy to miss: `127.0.0.1` and `::1` are matched as *different
hosts*. They are both loopback, but they are not interchangeable. Pick one
family, register it, and use it consistently at runtime.

Rule two: bind first, then browse. The tempting alternative is to find a free
port, close the socket, build your URL, and bind again later. That is a race — in
between, something else can take the port. Bind to port zero, read the assigned
port off the socket, and only then construct the redirect URI. As the bar says:
the redirect URI cannot exist until the socket does.

> Transition: One more conceptual point, because this confusion is almost universal.

---

## Slide 12 — `state` Is Not PKCE

I want to head this off, because I have seen people remove `state` after adding
PKCE, thinking it is now redundant. It is not.

They defend against different attacks and they are checked by different parties.

`state` protects against CSRF. The attack is that someone tricks *your* session
into consuming *their* authorization code, so you end up connected to the
attacker's account. `state` is a value you generate and you verify. Zoom just
echoes it back.

PKCE protects against code interception. The attack is that someone steals *your*
code and uses it themselves. The verification happens on Zoom's side, not yours.

Different attacks, different directions, different verifiers. Use both, every
time. It is four lines of code together.

> Transition: Enough theory. Let us read the actual implementation.

---

## Slide 13 — Part 3 divider

One file. Python 3.9 or newer. Standard library only.

---

## Slide 14 — No Dependencies. None.

These are all the imports in the file.

I want to be clear that this is not a stunt. There is a real pedagogical reason:
when you use an OAuth library, the library makes all the interesting decisions
for you, and you learn nothing about the protocol. Here, `secrets` gives us the
cryptographic random source, `hashlib` gives us SHA-256, `http.server` gives us
the listener, and `urllib` makes the HTTP calls. That is the entire protocol
surface.

Practically, it also means there is nothing to install. You clone and you run. No
virtual environment, no lockfile, no version conflicts in the room during a
workshop.

For production you would very likely use a maintained library. But read this
first, so that you know what the library is doing.

> Transition: Step one — the verifier.

---

## Slide 15 — Step 1 — Generate the Verifier

Six lines, and there are three things I want you to notice.

First, `secrets.token_bytes`, not the `random` module. `secrets` is backed by the
operating system's cryptographically secure generator. `random` is a Mersenne
Twister — perfectly good for simulations, completely unsuitable here, because its
output is predictable from previous output. This is a common and serious mistake.

Second, 32 random bytes base64url-encoded gives us 43 characters, which is
exactly the minimum length the specification allows. That is not a coincidence;
it is 256 bits of entropy.

Third — and this one causes real debugging pain — `rstrip("=")`. The base64url
encoding used by PKCE is *unpadded*. If you leave the `=` padding on, your
challenge string does not match what the server computes, and you get an opaque
failure at the token endpoint with no useful message. Strip the padding, on both
the verifier and the challenge.

The challenge itself is three operations: encode the verifier as ASCII, SHA-256
it, base64url encode the digest. That is the whole `S256` transform.

> Transition: Step two — the listener, and the ordering rule from earlier, in code.

---

## Slide 16 — Step 2 — Bind First, Derive Second

This is rule two made concrete.

We construct the server, which binds the socket. Then — and only then — we read
`server_address[1]`, which is the port the operating system actually assigned. If
we passed zero, that number is a surprise to us, and it will be different next
time.

Then we build the redirect URI from that real port.

One small detail worth stealing: the `host_for_uri` line. If the host contains a
colon it is IPv6, and IPv6 literals must be wrapped in square brackets inside a
URI — `http://[::1]:54929/callback`. Forget the brackets and your URL is
unparseable. Three lines up, that same colon test picks the socket address
family. Handling IPv6 is about four lines total, so there is no reason to skip it.

> Transition: Step three — receiving the redirect.

---

## Slide 17 — Step 3 — Catch Exactly One Request

This is the smallest useful HTTP handler you can write.

Parse the path. If it is not the path we expect, return 404 and stop.

That 404 branch is not defensive boilerplate — it is load-bearing. Browsers
request `/favicon.ico` unprompted. Without this check, a favicon request looks
like a callback with no `code` and no `state`, and your flow fails with a
confusing error before the real redirect ever arrives. I have watched people lose
half an hour to this.

If the path does match, we pull the query parameters into a dictionary, return a
small "you can close this tab" page to the browser — always give the user
something human, otherwise they stare at a blank tab wondering if it worked — and
store the result on the server object where the main flow can pick it up.

Note what is *not* here: no validation, no token exchange, no business logic. The
handler's only job is to capture and hand off. Keeping the HTTP handler dumb makes
the security-relevant code linear and easy to audit.

> Transition: Step four — the authorize URL.

---

## Slide 18 — Step 4 — Build the Authorize URL

Six parameters, and I have annotated the two that matter.

`code_challenge` is the hash, not the verifier. If you send the verifier here you
have defeated the entire mechanism, and — this is the dangerous part — the flow
will still work. Nothing will fail. You will simply have no protection. Reviewers
should look at this line specifically.

`code_challenge_method` is `S256`. The specification also defines `plain`, where
the challenge equals the verifier. Never use it. It exists for constrained
devices that genuinely cannot compute SHA-256, and that is not you.

Two more things. There is no `scope` parameter — Zoom uses the scopes configured
in your app's build flow, which is a Zoom-specific behaviour worth knowing, since
most providers expect `scope` here.

And use `urlencode`. Do not build this string by hand. The `redirect_uri` value
contains a colon and slashes, all of which must be percent-encoded when nested
inside another URL. Hand-rolled string concatenation is the single most common
source of "invalid redirect" errors that turn out to have nothing to do with your
registration.

> Transition: Step five — the two things that happen when the code comes back.

---

## Slide 19 — Step 5 — Validate, Then Redeem

Two blocks, in this order, and the order is the point.

First: compare `state`. If it does not match, abort. Do not log the code, do not
retry, do not attempt the exchange. Just stop. Two lines.

Then the token request. Look at the dictionary. `redirect_uri` — with the comment
— must be byte-identical to what we sent at step four; it is an integrity check,
not a routing instruction. And `code_verifier` is where our secret finally goes
on the wire, over TLS, directly to Zoom.

Now look at the `Request` construction and notice what is missing. Content type
is form-urlencoded, and that is the only header. No `Authorization`. No secret
anywhere.

If you are porting a confidential-client integration to PKCE, this is the diff:
delete the Basic auth header, add `code_verifier`. That is genuinely it.

> Transition: Last piece of code — proving it worked.

---

## Slide 20 — Step 6 — Prove the Token Works

The top block is unremarkable and that is the point — once you have an access
token, this is an ordinary bearer-token API call.

I included the bottom block because it is the most valuable four lines in the
file. When `urllib` raises an `HTTPError`, the exception object is also a
readable file object, and the body is where Zoom explains what you did wrong. If
you only print `err.code`, you get "HTTP 400" and you learn nothing. If you print
the body, you get the actual reason and error number.

Please copy this pattern. It is the difference between debugging this in five
minutes and debugging it over an afternoon. I will show you exactly this in a
moment when I break things on purpose.

> Transition: Let us run it.

---

## Slide 21 — Part 4 divider

Register, run, read, break.

---

## Slide 22 — Marketplace Setup — Four Things

Four things in the Marketplace, and then we run.

Create a General app. In App Credentials, turn on *Use Public Client OAuth* — that
is the toggle that makes your app a public client and makes it eligible for a
loopback redirect. In the OAuth Allow List, add `http://127.0.0.1/callback`. And
add the `user:read:user` scope so our `/users/me` call has permission.

The one thing that catches almost everybody is on the bar at the bottom. Once you
enable public client OAuth you get a **Public Client ID**, and it is a different
value from the Client ID sitting above it. If you copy the wrong one you get
`invalid_client` from the token endpoint, and nothing about that message tells you
which field you got wrong.

> Transition: Everything is registered. Let us run it.

---

## Slide 23 — Run It

**[LIVE DEMO — switch to the terminal]**

Clone, change directory, run. There is no install step between those lines, and
that is not a simplification I made for the slide.

Show it: `git clone`, `cd`, then `python3 main.py --client-id …`.

The browser opens. Point at the address bar and note that this is the real
`zoom.us` domain — this is why we use the system browser rather than an embedded
webview: the user can verify who they are giving access to.

Click Allow. Switch back to the terminal.

*Fallback if the network or the app misbehaves: the log output on the next slide
is a real captured run, so narrate that instead and continue.*

---

## Slide 24 — Watch the Whole Flow

Walk down the log with the audience. Everything we drew on the sequence diagrams
is here, in order.

PKCE generated — 43-character verifier, `S256`. Listener bound, and there is our
ephemeral port, 54929, with the redirect URI derived from it. The authorize URL.
Then the callback arrives with the code and state. The listener closes — notice
that this happens *before* the token call, not after. State validated. The token
POST. Tokens back, with a one-hour expiry. And finally the profile call.

The whole flow is about four seconds of machine time, and almost all of the
elapsed time is you clicking Allow.

> Transition: Three details in that log deserve a second look.

---

## Slide 25 — Three Things to Notice

Three things.

The port is different every single run. I ran this twice: 54929, then 54931.
Nothing is cached, and nothing should be — RFC 8252 asks for a fresh port each
attempt, and reusing a known port is exactly what makes a port squatting attack
easier.

The listener closes before the token exchange, not after. The window in which
there is an HTTP server running on your machine is measured in milliseconds.

And the access token is logged as `eyJzdi…(1089 chars)`. You can see its shape,
its prefix, and its length, which is everything you need for debugging, and none
of what you need to impersonate the user. Build that redaction in from the first
line of code, because a token that reaches a log file has reached your log
aggregator, your terminal scrollback, and possibly a screenshot in a bug report.

> Transition: Now the more useful half of the demo. Let us break it.

---

## Slide 26 — Now Break It On Purpose

**[LIVE DEMO — run at least the first two]**

Four failures, and every one of them is somebody's future debugging session.

Pass `--host localhost` and the guard in `main()` stops us before any network
call, with an explanation. Failing early with a good message beats failing at the
consent screen with a bad one.

Change the path so it no longer matches what is registered, and you get `4709
redirect uri mismatch`. Only some parts of a redirect URI are flexible; the path
is matched exactly.

Use the wrong client id and the token endpoint says `invalid_client`. This is
where the error-body printing from slide 20 earns its keep — without it you just
see "HTTP 400".

And pin `--port 3000` when only the unported URI is registered, and you get
`Invalid redirect … (4700)`. Which brings us neatly to the last real topic.

---

## Slide 27 — The Ephemeral Port Caveat

Here is a genuine tension in this design, and I would rather you hear it from me
than discover it at two in the morning.

RFC 8252 wants a fresh OS-assigned port on every run. But you register your
redirect URI in advance, and you cannot register a port number you will not know
until runtime.

The specification's resolution is that the authorization server should ignore the
port when matching a loopback redirect URI, and match only the scheme, host, and
path.

The practical caveat: **support for that varies between providers, so verify it
against yours before you design around it.** Do not assume it works and do not
assume it does not. Write the two-line test, register a portless URI, run with an
ephemeral port, and see what comes back. That is precisely why this sample exposes
`--port`: with `0` you exercise the real RFC 8252 path, and with a fixed number
you exercise exact matching as a fallback. Same code, one flag, and you get an
answer in a minute.

If port relaxation does not work for your provider, the fallback is a registered
fixed port. It is less elegant, it is not really RFC 8252, and it works. Just
know which one you are relying on, deliberately.

Test this on day one of your integration, because the answer decides your whole
registration strategy.

> Transition: Let us close with what to take away.

---

## Slide 28 — Checklist to Take Home

Eight things. Four about the protocol, four about the runtime.

Protocol: PKCE with `S256`, always. Validate `state`, every time. `127.0.0.1`,
never `localhost`. Bind before you build the URI.

Runtime: bind to loopback only, never `0.0.0.0`. Close the listener the instant
you have the code. Fresh port per attempt. Never log a token.

If you remember only one sentence from the whole session, make it this one: the
challenge goes up with the request, the verifier goes up with the redemption.
Everything else follows from that.

The repository is on the slide. It is about three hundred lines with comments,
and it runs on a clean machine with nothing but Python installed. Clone it this
afternoon and get a token — the concepts land differently once you have watched
your own port number appear in the log.

---

## Slide 29 — Thank You

Both RFCs are short and readable — 7636 in particular is worth a genuine read,
not just a skim; it is about fifteen pages and it explains its own threat model
better than any blog post will.

Questions.

---

## Anticipated questions

**Is PKCE only for public clients?**
No. It started that way, but current guidance recommends it for confidential
clients too. It closes code interception regardless of whether you also have a
secret.

**Can I use PKCE with a client secret at the same time?**
Yes, and for a confidential client that is the recommended combination. Send the
secret as usual and add the PKCE parameters.

**Why not use a fixed port and skip all this?**
You can, and it is a legitimate fallback — see slide 27. The costs are that the
port might be occupied, and that a known fixed port is easier for a hostile local
process to squat on before you bind it.

**Why not an embedded webview instead of the system browser?**
Two reasons. The user cannot verify the URL, so they cannot tell a real consent
screen from a fake one. And you do not get their existing session, so you force
a fresh login. RFC 8252 recommends against embedded user agents for exactly these
reasons.

**What about the refresh token?**
It comes back in the same token response. Refresh works the same as any other
OAuth client, except that a public client again sends no secret — just
`grant_type=refresh_token`, the refresh token, and the `client_id`.

**Is `http://` here a problem, given it is not HTTPS?**
No, and this is the one place where plain HTTP is correct. The traffic never
leaves the machine — it goes from the browser to a socket on the loopback
interface. There is no network path to intercept. TLS on `127.0.0.1` would mean
shipping a certificate and private key inside your application, which is strictly
worse.

**Does this work over SSH or in a container?**
Partly. The listener works fine, but there is no browser to open. Use
`--no-browser`, copy the URL to a machine that has a browser, and make sure the
loopback port is reachable from wherever that browser runs — which usually means
port forwarding. It is a real constraint of the loopback pattern.
