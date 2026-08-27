# Serving the Godot web export

The client binary is served from **Cloudflare, beside the marketing site** — not
from Evennia. Only the websocket crosses the tunnel.

Three reasons, in order:

- Django is a poor static host, and 4001 is behind the tunnel, so every byte of
  a ~38 MB download would cross `cloudflared`.
- `evennia reload` happens constantly. Serving the client from the game origin
  means a reload can interrupt a player's **download**, not just their session.
- The CDN is already there and already serves `playblackout.io`.

The consequence, stated because it is the kind of thing discovered at 2am: the
page origin and the socket origin are **different hosts by design**. That is
fine for a WebSocket — `wss://` is not subject to CORS — and it is why
`ServerEndpoint.PRODUCTION_URL` names `game.playblackout.io` explicitly rather
than deriving it from `location`.

---

## The model tree must be deployed BESIDE the client

**`wss://` is exempt from CORS. An HTTP fetch for a `.glb` is not**, and that is
the one place the "different origins are fine" reasoning above does not reach.
The Godot client fetches its art at runtime rather than bundling it (ENG-0006
R11), so those are ordinary cross-origin requests when the page and the art sit
on different hosts.

Measured 08/26/2026:

```
$ curl -D - -H "Origin: https://playblackout.io" \
    https://game.playblackout.io/static/webclient/models/manifest.json
HTTP/1.1 200 OK
Content-Type: application/json
```

No `Access-Control-Allow-Origin`. A web client served from the CDN and fetching
art from the game origin would therefore be refused by the browser, and every
entity in the game would silently fall back to its procedural family shape —
a degradation with no error a player could report.

So `ServerEndpoint.asset_origin()` returns **`""`** for a release web build: the
request goes out relative to the page and never crosses an origin at all.

**What that requires of this deploy:** whatever serves `index.html` must also
serve the model tree at the path the client asks for, which is
`ModelRegistry.MODEL_ROOT` — `/static/webclient/models/`, manifest included.
Copy `blackout/web/static/webclient/models/` into the site's `dist/` under that
path when publishing the export.

The alternative — adding CORS headers to Evennia's static serving — was rejected
for the same two reasons §4.2 gives above: every byte would cross `cloudflared`,
and an `evennia reload` could interrupt an art fetch.

---

## Build

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot --export-release "Web" <out>/index.html
```

The `Web` preset is committed in `godot/export_presets.cfg`. Its one load-bearing
setting is `variant/thread_support=false`: single-threaded needs no
`SharedArrayBuffer`, therefore no cross-origin isolation, therefore no COOP/COEP
headers anywhere in this file. **Measured**, not assumed — the export boots with
`crossOriginIsolated: false` and `SharedArrayBuffer` undefined.

A release export (not debug) is what makes the client connect to production:
`ServerEndpoint` keys off `OS.is_debug_build()`, so there is no constant to
remember to flip.

Expect roughly:

| | |
|---|---|
| Raw | ~38 MiB, of which ~99% is `index.wasm` |
| Brotli | ~6.7 MiB |

## Deploy

The export is **not committed** — to this repo or to `playblackout-site`. It is
a build artifact of a known size, it changes wholesale on every build, and a
40 MB binary in git history is permanent.

Copy the built files into the site's `public/` (so Astro passes them through to
`dist/`) under a `play/` directory, then deploy the site as usual. The client
then lives at `https://playblackout.io/play/`.

## `_headers`

Cloudflare's static asset serving reads a `_headers` file. `headers.template`
beside this README is the block to include.

**Do not add COOP/COEP.** They are only needed for a threaded export, this one
is single-threaded, and adding them would additionally break any embedded
third-party content on the site for no gain.

The cache policy is deliberately modest. Godot's web export does **not**
content-hash its filenames — every build produces `index.wasm` again — so a long
`immutable` cache would serve a stale engine to returning players after a
deploy. Revalidation plus Cloudflare's ETag is the right trade until the
filenames carry a hash.

## What still has to be true on the game side

- `deploy/cloudflared/config.yml` carries the `^/godot` rule, **above** the
  catch-all. Rules evaluate top to bottom and a websocket rule below the
  catch-all gets handed HTML instead of a socket upgrade.
- Port 4008 stays bound to `127.0.0.1`. `cloudflared` runs on the same machine
  and dials localhost, so loopback is reachable by the tunnel and by nothing
  else. It does **not** need widening to `0.0.0.0`.
- The Portal must have been restarted since `server/conf/godot_websocket.py`
  landed — `PORTAL_SERVICES_PLUGIN_MODULES` is read at Portal start, and
  `evennia reload` restarts the Server only. `evennia reboot` does both.

**Author:** Nick Hobar
**Date:** 08/25/2026
