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

So `ServerEndpoint.asset_origin()` prefixes **the page's own origin**, read off
`location.origin` through `JavaScriptBridge`, for a release web build: the fetch
is same-origin and there is nothing for a preflight to refuse.

It returned **`""`** until 08/27/2026, on the reasoning that an empty origin
makes a root-relative path the browser resolves against the page. That is right
about CORS and wrong about `HTTPRequest`, which is not the browser's fetch — it
parses the URL itself and refuses one with no scheme:

```
ERROR: Error parsing URL: '/static/webclient/models/manifest.json'
   at: _parse_url (scene/main/http_request.cpp:61)
WARNING: ModelLoader: manifest request refused: error 31
```

The manifest never arrived, so `has_model` answered false for every asset key
and **every entity in the game drew its family shape** — which is indistinguish-
able from art that was never packed, and was read as a broken model file for a
day. `test_server_endpoint.gd` now asserts that whatever origin is chosen, the
URL built from it can actually be dialled.

**What that requires of this deploy:** whatever serves `index.html` must also
serve the model tree at the path the client asks for, which is
`ModelRegistry.MODEL_ROOT` — `/static/webclient/models/`, manifest included.
`publish.sh` uploads both trees to the same bucket for exactly this reason, and
`worker/index.ts` claims both prefixes on the site's own hostname.

The alternative — adding CORS headers to Evennia's static serving — was rejected
for the same two reasons §4.2 gives above: every byte would cross `cloudflared`,
and an `evennia reload` could interrupt an art fetch.

---

## Build

Export into `build/` beside this README — gitignored, and the one place
`publish.sh` looks:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot --export-release "Web" deploy/webexport/build/index.html
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

**The export is not a static asset and cannot become one.** Cloudflare caps an
individual static asset at **25 MiB**, on the Free plan and the Paid plan alike;
`index.wasm` is **37.7 MiB**. `wrangler deploy` does not warn, it refuses:

```
X [ERROR] Asset too large.
  Cloudflare Workers supports assets with sizes of up to 25 MiB. We found a
  file .../dist/client/index.wasm with a size of 37.7 MiB.
```

Nothing on the game side reaches that number either — `index.pck` is 205 KB of
the export, so the weight is the Godot engine, not the game.

So the client and the model tree live in the **`playblackout-assets` R2 bucket**
and are served by `playblackout-site/worker/index.ts`. Two steps, in this order:

```bash
./deploy/webexport/publish.sh          # --dry-run lists the keys first
```

```bash
cd ../playblackout-site && npx wrangler deploy
```

**It is a bash script and was a PowerShell one until 08/27/2026.** The shell in
front of this repo is git bash, this machine has no `pwsh`, and what stood here
was a `powershell -ExecutionPolicy Bypass -File` incantation explaining how to
run a PowerShell script from a shell that is not PowerShell. One script for the
shell that exists beats two that can drift.

The one Windows-specific thing left in it is `cygpath`: `wrangler` is a native
Windows binary and cannot open a POSIX path, so `--file` is translated on the way
in. On a real POSIX box there is nothing to translate and the path passes
through, which is the same shape `scripts/clean_and_reload_all_maps.sh` already
uses for the virtualenv.

The bucket is the origin and the site deploy is the router, so a publish with no
deploy leaves the old client live, while a deploy with no publish 404s `/play`.
**Publish first.**

### Why a worker and not a bucket subdomain

An R2 custom domain binds a **whole hostname** — `cdn.playblackout.io` is what
it offers, and that is a different origin from the page. Everything in §2 above
then comes back: the `.glb` fetches cross an origin, R2 needs CORS headers, and
`asset_origin()` returning `""` stops being true. A worker binding is the only
arrangement that puts a bucket at a **path** on the site's own hostname.

Keys mirror URLs exactly — `client/index.wasm` in the bucket is
`/client/index.wasm` on the site — which is the whole of the routing rule.

## Response headers

**The worker owns them**, in its `CONTENT_TYPES` table and `CACHE_CONTROL`
constant. There is no `_headers` file: a `_headers` block applies to static
assets, and none of these are static assets any more. `headers.template` used to
live here and was deleted for that reason — it also still said `/play/`, which
collides with the site's own `/play` marketing page.

Two decisions carried over into the worker rather than lost with it:

**No COOP/COEP.** They are only needed for a threaded export, this one is
single-threaded, and adding them would additionally break any embedded
third-party content on the site for no gain.

**No `immutable`.** Godot's web export does not content-hash its filenames —
every build produces `index.wasm` again — so a long cache would serve a stale
engine to returning players after a deploy. `must-revalidate` plus R2's ETag
makes the repeat visit a 304 with no body, which is the same win without the
staleness.

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
