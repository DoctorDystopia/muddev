# Public Hosting: playblackout.io and game.playblackout.io

**Status:** live. Site and game both serving since 08/21/2026.
**Author:** Nick Hobar
**Date:** 08/21/2026

> §6 lists what is still open. §5 records the two problems that shaped the
> design — read it before changing the tunnel or the websocket settings.

Blackout is reachable from the public internet without any port being forwarded.
The marketing site and the game server are deliberately separate systems that
share only a DNS zone.

---

## 1. The split

```
playblackout.io          static site, Cloudflare Worker    (playblackout-site repo)
game.playblackout.io     Evennia, this machine, tunnelled  (muddev repo)
```

They are decoupled on purpose. `evennia reload` happens constantly during
development; a Windows update reboots the machine without asking. Neither should
take the landing page down with it, and a compromise of the public site must not
reach the game database.

The cost is that forum/blog identity and game accounts are separate systems.
That is accepted — community lives on Discord, and MUDs conventionally keep
character accounts distinct from web accounts.

## 2. Why a tunnel and not port forwarding

This connection sits behind **three stacked NAT layers** before reaching public
address space:

| Hop | Address | Owner |
|---|---|---|
| 1 | `10.9.18.1` | local gateway |
| 2 | `192.168.187.1` | building operator |
| 3 | `172.16.254.1` | building operator |
| 4 | `208.185.77.185` | Zayo edge (`er3.den1`) |

Reverse DNS identifies a Zayo dedicated-internet circuit terminating at their
Denver edge — a shared building/MDU circuit, not a residential line. Two of the
three routers belong to other parties. There is no path to an inbound port, and
this also explains the closed admin UI and absent UPnP on `10.9.18.1`.

`cloudflared` dials **outbound** and Cloudflare routes inbound requests back down
that connection, so the NAT depth is irrelevant.

## 3. Routing

`deploy/cloudflared/config.yml` (deployed to `%USERPROFILE%\.cloudflared\`):

| Match | Origin | Serves |
|---|---|---|
| `game.playblackout.io` path `^/ws` | `ws://localhost:4002` | webclient websocket |
| `game.playblackout.io` (catch-all) | `http://localhost:4001` | Evennia webserver |
| anything else | `http_status:404` | — |

Rules evaluate top to bottom. **The websocket rule must stay first**, or the
browser client gets handed HTML instead of a socket upgrade.

## 4. Settings that make it work

In `blackout/server/conf/settings.py`, under the public-hosting banner:

| Setting | Why |
|---|---|
| `ALLOWED_HOSTS` | Evennia ships `["*"]`. Narrowed to the real hostnames. |
| `CSRF_TRUSTED_ORIGINS` | Without it every admin login and form POST 403s. |
| `SECURE_PROXY_SSL_HEADER` | Cloudflare terminates TLS and forwards plain HTTP. Without this Django believes every request is insecure and refuses to set secure cookies — login fails in a way that looks like a bad password. |
| `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` | Safe now that all public traffic is TLS. |
| `WEBSOCKET_CLIENT_URL` | See below. |

`SECRET_KEY` now lives in `server/conf/secret_settings.py` (gitignored). It was
previously Evennia's shipped default — a publicly known string that would let
anyone forge session cookies and password-reset tokens. **Back that file up.**
Losing it invalidates sessions but touches no game data.

## 5. Two problems that shaped this

### 5.1 The webclient dialed `ws://` under HTTPS

`evennia/web/templates/webclient/base.html` falls back to
`"ws://" + location.hostname + ":4002"` when `WEBSOCKET_CLIENT_URL` is unset —
which it is by default. Over HTTPS the browser blocks that as mixed content and
the client silently never connects, with no error a player would understand.

Fixed by stating the URL explicitly:

```python
WEBSOCKET_CLIENT_URL = "wss://game.playblackout.io/ws"
```

No query string — `evennia.js` appends its own session parameters.

### 5.2 Sockets died at ~126s

Silent websockets were closed with an abnormal 1006, no code or reason. Measured
against the live host: three silent sockets died at 125.6s, 126.0s and 126.9s; a
socket pinged every 45s survived. A control socket held directly against
`ws://127.0.0.1:4002` stayed open for a full 30 minutes.

It is the **Cloudflare edge** closing websockets idle for ~100s, and that timer
is not configurable below Enterprise. It is not Evennia (`IDLE_TIMEOUT` is `-1`)
and not fixable from the tunnel: `originRequest.keepAliveTimeout` governs
cloudflared's HTTP pool to the origin, not the edge's websocket idle timer — the
measurements above were taken with it already at 1000s.

The fix has to be traffic. `server/conf/websocket.py` sends a websocket PING
every 45s (`WEBSOCKET_KEEPALIVE_INTERVAL`), which browsers answer automatically.
No client change.

> **Correction, 08/25/2026: it did NOT cover the Godot client.** This paragraph
> used to end "and it covers the Godot client too". It did not.
> `WEBSOCKET_PROTOCOL_CLASS` is read in exactly one place --
> `evennia/server/portal/service.py` -- which builds the MAIN webclient service
> on 4002. The godotwebsocket contrib builds its own service and hardcodes
> `factory.protocol = GodotWebSocketClient`, a subclass of the STOCK
> `WebSocketClient`. So port 4008 had no keepalive at all and would have been
> closed at ~100s idle, exactly as measured above.
>
> Nobody noticed because 4008 has never been exposed through the tunnel (§6),
> so no Godot socket has ever run through the Cloudflare edge. It would have
> failed on the first day it did.
>
> Fixed by `server/conf/godot_websocket.py`, which inherits from both the
> keepalive protocol and the contrib's, and which settings.py now names in
> `PORTAL_SERVICES_PLUGIN_MODULES` instead of the contrib. Guarded by
> `systems/statefeed/tests/test_godot_protocol.py`.

## 6. Still open

- **`www.playblackout.io` and both `.net` hostnames are unreachable.** They need
  Redirect Rules to `https://playblackout.io`.
- **`playblackout-site.nhobar.workers.dev` still serves a duplicate** of the
  site, competing with the real domain in search results. Set
  `"workers_dev": false` in `wrangler.jsonc` — the custom domain is attached, so
  this is now safe to do.
- **Telnet (4000) is not exposed and cannot be.** Cloudflare Tunnel carries raw
  TCP only if the *client* also runs `cloudflared access tcp`, which no ordinary
  player will do. Mudlet/TinTin++ support needs a cheap VPS running a TCP proxy.
  `/play` on the site says so plainly.
- **Godot websocket (4008)** is bound to `127.0.0.1` with no ingress rule.
  Routing it means picking a path prefix the Godot client also sends; verify
  against the contrib first.
- **`REST_API_ENABLED = False`.** Any live server-status widget on the site needs
  it on, plus an SSR adapter on the Astro side.

## 7. Operating it

```bash
cloudflared service install
```

Runs the tunnel as a Windows service so it survives reboots, reading the same
`config.yml`. Install it only after a foreground `cloudflared tunnel run`
succeeds — a broken config fails silently in the background.

The service runs whether or not Evennia is up. **If the game server is stopped,
`game.playblackout.io` returns a Cloudflare 502**, not a connection failure.
That is the tunnel working correctly and the origin being absent.

See `deploy/cloudflared/README.md` for first-time setup.
