# ENG-0005 — Godot as the 3D renderer: what it would cost, and what it would buy

**Status:** superseded by a decision. **Option A was chosen on 08/25/2026**,
against this document's recommendation of Option B. The implementation plan is
[ENG-0006](2026-08-25-ENG-0006-godot-option-a-plan.md); the costs raised here
are carried forward as its risk register. This document is kept as the record of
what was weighed.
**Date:** 08/25/2026
**Scope:** `systems/statefeed/`, `web/static/webclient/js/`, `godot/` on
`godot-client-prototype`, the Cloudflare pipeline to `game.playblackout.io`, and
the `playblackout-site` repo.
**Related:** [ENG-0004](old/2026-08-23-ENG-0004-webclient-architecture.md),
[INFRA-0001](old/2026-08-21-INFRA-0001-public-hosting.md),
[DESIGN-0002](2026-08-15-DESIGN-0002-3d-inventory.md)

> **Dangling reference, resolved.** `godot/README.md` and `project.godot` on
> `godot-client-prototype` both link
> `docs/2026-08-08-ENG-0005-godot-client-plan.md`. That file has never existed
> on any ref — checked with `git log --all --diff-filter=A`. This document takes
> the ENG-0005 slot so both links resolve to something real.

---

## Summary

**The question as posed — "switch entirely to Godot for 3D while Evennia keeps
the statefeed" — is already answered by the architecture. That is exactly what
the statefeed was built for, and a Godot client has been running against it,
unmodified, since 08/11/2026.** The server needs zero work. The interesting
question is not whether it *can* be done, but what happens to the **web**
version — and there the answer is much less comfortable.

Three findings drive everything below.

1. **The server side is already renderer-agnostic and costs nothing to keep
   that way.** `systems/statefeed/` is 4,415 lines of source and 4,045 of test
   that know nothing about three.js. The Godot contrib subclasses Evennia's
   browser websocket and overrides **exactly one method** — `send_text`, to
   convert ANSI to BBCode. `send_default`, which carries the entire state feed,
   is inherited unchanged. Switching renderers is not a server migration.

2. **Godot's web export cannot use the renderer the prototype is built on, and
   that removes most of the reason to switch on the web.** Godot 4 targets
   **WebGL 2.0 through the Compatibility renderer only**; Forward+/Mobile are
   unsupported on the web platform, and WebGPU — the prerequisite — is still not
   implemented as of 4.7. `godot/project.godot` is configured `Forward Plus`
   with a `d3d12` driver, so **the prototype as it stands is not web-exportable
   at all**. A web Godot client would draw through the same WebGL2 three.js
   already uses, at ~25–40 MB of WASM instead of 1.27 MB of vendored three.js.

3. **A MUD is a text application with a diorama attached, and Godot's web export
   is a canvas.** Today the text pane is DOM: selectable, `Ctrl+F`-able,
   system-clipboard-pasteable, screen-reader-legible, browser-zoomable. Godot on
   the web is one `<canvas>` — none of that survives. This is the cost that is
   genuinely hard to buy back, and it is worse for this genre than for almost
   any other.

**Recommendation: do not move the web client to Godot. Promote Godot to a
first-class *native desktop* client instead, and keep the browser on three.js.**
The statefeed already supports both, and ENG-0004's generated-constants work has
made the marginal cost of a second client roughly "a row in a punctuation table"
rather than a second copy of every fact. The web is where Godot is weakest and
where the current client is strongest; native is the reverse. §7 sets out the
three options and what each actually commits to.

---

## 1. What exists today, measured

### 1.1 The server boundary — `systems/statefeed/`

| | Lines |
|---|---:|
| Source | 4,415 |
| Tests | 4,045 |

Twelve subscribable channels, named in the **GMCP vocabulary** on purpose
(`room_info` → `Room.Info`, `char_items_list` → `Char.Items.List`), with
game-specific ones namespaced `blackout_*`. The consequence is that Mudlet and
MUSHclient get the same data for free, and so does anything else that speaks
GMCP — the feed was never designed around a browser.

The rule that makes a renderer swap cheap is the one CLAUDE.md states as **"the
server names; the client draws."** `serialize_entity` sends
`interact: "attack mutant raider"`. `tile_actions` sends `{command, kind}` per
tile. `serialize_inventory` sends whole commands. **A client that wants to act
sends a string a telnet player could have typed.** There is no privileged
channel. A second renderer inherits every lock, cooldown and permission with
nothing to re-audit — and both existing clients independently document that they
act only this way (`Evennia.command()` in GDScript, `["text", [cmd], {}]` in JS).

### 1.2 The browser client — `web/static/webclient/js/`

4,833 authored lines plus 1.27 MB of vendored three.js r159 (ESM).

| File | Lines |
|---|---:|
| `plugins/blackout3d.js` | 1,921 |
| `plugins/blackout_inventory.js` | 1,376 |
| `blackout_meshes.js` | 864 |
| `shell/pane.js` | 263 |
| `blackout_models.js` | 142 |
| `blackout_channels.js` | 79 |
| `plugins/hotkeys.js` | 68 |
| `generated/blackout_constants.js` | 66 |

**This layer finished a four-phase rebuild two days ago**
([ENG-0004](old/2026-08-23-ENG-0004-webclient-architecture.md), all phases marked
DONE on 08/23/2026). It is now ES modules behind one entry point, with a shared
pane shell, generated constants, server-declared tile affordances, and a
`node --test` suite that needs no dependencies. **It has never been in better
shape than it is right now.** That is not an argument against changing it, but
any comparison that treats the JS layer as the legacy mess it was a week ago is
comparing against a state that no longer exists.

### 1.3 The Godot client — `godot-client-prototype`

1,394 authored lines of GDScript (1,091 client, 303 test).

| File | Lines | Owns |
|---|---:|---|
| `world/world_view.gd` | 486 | Tiles, links, islands, marker, colours |
| `tests/test_world_state.gd` | 233 | Headless, needs nothing running |
| `world/entity_pool.gd` | 193 | Room occupants, hit flash |
| `world/world_state.gd` | 125 | Chunk reassembly, the float boundary |
| `autoload/evennia.gd` | 119 | The socket. The only wire-format knower |
| `scenes/console.gd` | 89 | Shell, input, subscription handshake |
| `world/orbit_camera.gd` | 79 | `SpringArm3D` follow rig |
| `tests/smoke_handshake.gd` | 70 | Live handshake against a running server |

It is good work — genuinely so. Two headless tests that exit non-zero. It
reimplements the JS string hash and a closed-form HSL→HSV specifically so the
two clients cannot disagree about colour. Its README records four hard-won rules
(`get_string_from_utf8()` not `_ascii`; every parsed number is a `float`; act
only through `Evennia.command()`; the monospace font is load-bearing).

**It is also stale and incomplete.** Two numbers matter:

- **79 commits behind `main`**, last touched **08/14/2026** — eleven days.
- **7 of 12 channels handled.** It consumes `blackout_map`, `room_info`,
  `room_players`, `room_add_player`, `room_remove_player`, `blackout_combat`,
  `blackout_aura`. It does not consume `char_avatar`, `char_vitals`,
  `char_status`, `char_summary`, or `char_items_list`.

That last omission is the whole 3D inventory / paper-doll feature — **1,376
lines** on the JS side, plus its share of the 864-line mesh resolver. It does not
exist in Godot in any form.

The staleness has already produced concrete drift beyond line count:

- `world_view.gd` still hand-types seven channel names as
  `const CH_MAP := "blackout_map"` etc. **`godot/autoload/blackout_constants.gd`
  on `main` already generates every one of those**, with identical names — the
  ENG-0004 Phase 1 work deliberately rendered the GDScript half *before* the
  branch landed, so the merge is a delete-and-repoint rather than a third
  hand-typed copy. That is the good case, and it is waiting.
- The branch predates **Phase 2 (server-declared tile affordances)**. So
  `world_state.gd` still carries `direction_for()` — the grid-delta →
  direction-name table that Phase 2 *deleted from JS as a bug source*, because
  it cannot express a one-way exit, a diagonal link, or a map whose geometry and
  direction names disagree. The Godot client is currently running the design
  that was replaced for cause.
- ENG-0004 records that the dead `"Pole clearing"` room-kind key **had already
  been copied into `world_view.gd`**. A second client did not expose the bug; it
  inherited it. `test_client_constants.py` now guards both clients by reading
  their sources as text, which is the mitigation — but the incident is the honest
  baseline for what "maintain two clients" costs.

---

## 2. Why the swap is architecturally cheap

Worth stating precisely, because it is the strongest thing in this analysis and
it cuts *both* ways — it is equally an argument for keeping the JS client.

`evennia/contrib/base_systems/godotwebsocket/webclient.py` is 80 lines. It
subclasses `webclient.WebSocketClient` and overrides `send_text` to run text
through `parse_to_bbcode`. That is the entire Godot-specific server surface.
Everything else — `send_default`, which serialises every outputfunc as
`[name, args, kwargs]` and is what carries all twelve state-feed channels — is
inherited untouched.

The settings cost is three lines, already present in
`blackout/server/conf/settings.py`:

```python
PORTAL_SERVICES_PLUGIN_MODULES.append('evennia.contrib.base_systems.godotwebsocket.webclient')
GODOT_CLIENT_WEBSOCKET_PORT = 4008
GODOT_CLIENT_WEBSOCKET_CLIENT_INTERFACE = "127.0.0.1"
```

So: **Evennia does not care.** Both clients are pure consumers of the same frames
on two ports. The renderer is genuinely a leaf. Nothing in `systems/`,
`typeclasses/`, `world/` or `commands/` would change under any option here.

**The one thing the contrib costs is a fork in the text pipeline.** Port 4002
gets ANSI→HTML; port 4008 gets ANSI→BBCode. `systems/banking/messages.py`
already carries a comment about exactly this — a colour code baked into a message
string reaches a Godot client as a literal `|r`. That constraint exists today and
is being honoured; it just gets more load-bearing if Godot becomes primary.

---

## 3. The web version — the crux

This is where "switch entirely to Godot" stops being a renderer choice and
becomes a product decision.

### 3.1 Godot's web export cannot use the renderer the prototype is built on

Godot 4 supports **WebGL 2.0 via the Compatibility rendering method only**.
Forward+ and Mobile are not supported on the web platform because they are
designed around modern low-level graphics APIs, and Godot does not yet implement
WebGPU, which is the prerequisite. This is still true in 4.7 — WebGPU is baseline
in browsers now, but Godot has not caught up.

`godot/project.godot` on the branch:

```
config/features=PackedStringArray("4.7", "Forward Plus")
rendering_device/driver.windows="d3d12"
```

**The prototype is not web-exportable as configured.** Making it so means
committing the project to Compatibility — which is then also the renderer you
develop the desktop client in, unless you accept two visual targets.

The practical consequence: **on the web, Godot draws through the same WebGL2
three.js already draws through.** The "better renderer" argument for switching is
a *native desktop* argument. It does not transfer to the browser.

### 3.2 Payload and boot

| | Today (three.js) | Godot web export |
|---|---|---|
| Renderer payload | 1.27 MB vendored ESM, cached | ~25–40 MB WASM (~5 MB Brotli, ~10 MB gzip) |
| Time to *text* | Immediate — DOM renders, socket opens | After the WASM module boots |
| Time to 3D | Pane opens on demand, from Options | Same boot |
| Failure mode | 3D pane missing, game fully playable | Blank canvas, nothing playable |

The last row matters most and is easy to miss. **The 3D panes are non-essential
by design** — ENG-0004 says so explicitly, and it is why headless-browser
rendering tests were rejected. A player on a locked-down machine, an old GPU, or
a blocked WebGL context loses the diorama and keeps the game. Under an all-Godot
web client the renderer *is* the client: there is no degraded mode, because the
text pane is inside the canvas.

### 3.3 Cross-origin isolation

Godot's multi-threaded web export needs `SharedArrayBuffer`, which needs
cross-origin isolation:

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

**This is avoidable.** Since 4.3, single-threaded export is the default and
preferred method and needs no such headers; it costs performance and
multithreading. For this workload — a low-poly tile diorama driven by a 0.6 s
server tick — single-threaded is almost certainly fine, and it also avoids the
documented Apple-device problems, which reportedly disappear under single-threaded
export.

So COOP/COEP is a footnote rather than a blocker. Noted because it is the first
thing every Godot-web writeup leads with, and for this project it is the wrong
thing to worry about.

### 3.4 What the canvas takes away — the real cost

A MUD is a text application. Everything in this column is free today because the
text pane is DOM, and none of it survives a canvas:

| | DOM text pane (today) | Godot canvas |
|---|---|---|
| Select / copy game output | Native | Must be reimplemented in `RichTextLabel` |
| **Paste into the input** | Native | **Broken** — Godot's web export keeps its own clipboard, not the system's; `OS.get_clipboard()` stays empty unless the copy originated in-game. Worse inside an iframe. |
| `Ctrl+F` on scrollback | Browser | Gone; build your own |
| Screen reader | Real DOM | Godot's AccessKit work (4.5+) targets **native platform accessibility APIs** — UIA on Windows. Web platform support is not established. |
| Browser zoom / reflow | Native | Canvas scales; text does not reflow |
| Right-click, links, browser history | Native | Gone |
| Font choice via the existing `font.js` plugin | Works | Reimplement |

Paste alone is a serious regression for a MUD: `connect <name> <password>` from a
password manager is the *first thing a new player does*, and the `/play` page on
`playblackout-site` literally instructs them to type it. Breaking paste at the
login prompt is a conversion problem, not an ergonomics one.

This is also why the prototype's README rule 4 — "the output pane's monospace
font is load-bearing" — is a preview of the general shape. Every text affordance
the browser gives away has to be rebuilt by hand inside the canvas, and each one
is small until you count them.

### 3.5 Browser support

Safari has several WebGL 2.0 issues other browsers do not, and Chromium or
Firefox are the recommended targets. Native mobile builds substantially
outperform web ones. For a game whose only public entry point is a browser link
on a marketing site, "recommend Chrome" is a real narrowing.

---

## 4. The pipeline to `game.playblackout.io`

Current shape, from [INFRA-0001](old/2026-08-21-INFRA-0001-public-hosting.md):

```
playblackout.io        Astro static → Cloudflare Workers assets   (playblackout-site)
game.playblackout.io   Cloudflare Tunnel → this machine           (muddev)
                         path ^/ws  →  ws://localhost:4002   (webclient socket)
                         catch-all  →  http://localhost:4001 (Evennia webserver)
```

The connection sits behind **three NAT layers** with no route to an inbound port,
so `cloudflared` dialling outbound is not a preference — it is the only option.
That constrains every deployment idea below.

### 4.1 What an all-Godot web client would need

1. **A `wss://` route to 4008.** Already flagged as open work in INFRA-0001 §6:
   port 4008 is bound to `127.0.0.1` with no ingress rule. Adding one is a third
   `ingress:` block above the catch-all, plus flipping
   `GODOT_CLIENT_WEBSOCKET_CLIENT_INTERFACE`. The **ordering rule holds** — any
   websocket rule must precede the catch-all or the client is handed HTML.
2. **Somewhere to serve ~30 MB of WASM.** Two choices, and the second is better:
   - Evennia's Django webserver on 4001, through the tunnel. Simple, but it puts
     a 30 MB static payload on the same origin that `evennia reload` restarts
     constantly, and Django is a poor static host.
   - **Cloudflare, beside the marketing site.** `wrangler.jsonc` already serves
     `./dist` as static assets, and a `_headers` file covers COOP/COEP and the
     `application/wasm` MIME type if ever needed. This is the right answer: the
     game binary comes off the CDN, and only the websocket crosses the tunnel. It
     also means a game-server restart no longer takes the client download with it.
3. **The 45 s websocket keepalive already covers it.** INFRA-0001 §5.2 documents
   Cloudflare's ~100 s edge idle timeout — not configurable below Enterprise —
   and the fix is server-side pings from `server/conf/websocket.py`. That fix is
   transport-level and the doc already states it covers the Godot client. **No new
   work.** A genuine pre-paid cost, and worth crediting.

### 4.2 The finding that kills the naive hybrid

The obvious compromise — keep the DOM text pane, swap only the 3D panes for an
embedded Godot canvas — requires the page to hold **two websockets**: 4002 for
text, 4008 for the canvas. In Evennia, each websocket is a separate **Session**.

`MULTISESSION_MODE` is **not set** in `blackout/server/conf/settings.py`, so it is
Evennia's default of **0 — one session per account; a new connection disconnects
the old one.**

**As configured, the hybrid does not work. The Godot pane connecting would kick
the text client, or vice versa.** It is not a subtle bug; it is immediate and
total.

It is *fixable* — `MULTISESSION_MODE = 1` (many sessions, one puppet, output to
all) is the mode this shape wants, and the per-session subscription handshake the
prototype README describes is already per-`Session` `ndb`. But it is a change to
account-level semantics affecting every player and every login path, made in
service of a rendering decision. It should be a deliberate choice, not a discovery
made three days into an integration.

### 4.3 What a *native* Godot client would need

Nearly nothing, which is the point.

- Native TCP/websocket from a desktop binary is **not subject to the browser's
  mixed-content or same-origin rules**, and Cloudflare Tunnel carries the
  websocket fine.
- It sidesteps INFRA-0001 §6's standing complaint that **telnet cannot be
  exposed** — Mudlet and TinTin++ need a TCP proxy on a cheap VPS that does not
  exist yet. A native Godot client is a "real client" for the players who want
  one, over a transport that already works.
- Distribution is the new cost: a binary to build, sign and host per platform.
  Unsigned executables on Windows and macOS are a meaningful install-funnel loss,
  and code signing is an annual expense.

---

## 5. Pros and cons — all-Godot for 3D, browser included

### Pros

| | |
|---|---|
| **Server cost is zero** | The contrib overrides one method. No change in `systems/`, `world/`, `typeclasses/` or `commands/`. |
| **One renderer, not two** | Today's real risk is two clients drifting — and it has already happened once (the dead room-kind key propagated *into* Godot). One client cannot drift from itself. |
| **A real engine instead of a hand-rolled one** | Scene tree, animation, physics, particles, audio, a shader language, and an editor with a viewport. `blackout_meshes.js` is 864 lines doing by hand what Godot's importer does on drag-and-drop. |
| **The asset pipeline is already portable** | Art is glTF — `player_character.glb`, `floating_eye.glb`, `rusty_scrap_shortsword.glb`, `map_transition.glb`, with `assets/pack_model.py` producing them. Godot imports `.glb` natively. **No asset migration.** |
| **GDScript over JavaScript** | Typed enough to catch the class of bug ENG-0004 F6 is about; the prototype already uses `-> void`, `Vector2i`, typed arrays. The float-boundary rule in `world_state.gd` is exactly the discipline the JS side has no type system to enforce. |
| **The hard client problems are solved once** | Chunk reassembly, subscription-handshake recovery across `evennia reload`, and the act-only-through-`command()` rule are already written in GDScript and tested headlessly. |
| **Opens native desktop and mobile** | Same codebase exports to Windows/macOS/Linux and Android/iOS. That is the strategic argument, and it is real. |

### Cons

| | |
|---|---|
| **Forward+ does not export to web** | The renderer-quality argument evaporates in the browser: Compatibility/WebGL2, same as three.js. The prototype's own `project.godot` is not web-exportable as written. |
| **~30 MB of WASM in front of a text game** | Against 1.27 MB of cached three.js. Time-to-first-`look` goes from immediate to a boot. |
| **Text affordances are lost wholesale** | Selection, **system-clipboard paste**, `Ctrl+F`, screen readers, browser zoom. Paste breaking at the `connect` prompt is a first-five-minutes problem. §3.4. |
| **Graceful degradation is gone** | Today a WebGL failure costs the diorama and keeps the game. Under all-Godot the renderer *is* the client. |
| **It discards work that landed two days ago** | ENG-0004's four phases — modules, pane shell, generated constants, tile affordances, `node --test` — all completed 08/23/2026. |
| **Parity is much further away than the branch suggests** | 7/12 channels, no inventory pane at all against 1,376 JS lines, 79 commits behind, and running the pre-Phase-2 tile design that was deleted for cause. |
| **The naive hybrid is blocked** | `MULTISESSION_MODE = 0`. Two sockets means the second login kicks the first. §4.2. |
| **Safari/mobile narrowing** | WebGL2 issues on Safari; native mobile substantially outperforms web. The only public entry point is a browser link. |
| **A second toolchain** | Godot is not on `PATH` on this machine; the README documents a binary path that repeats itself and a `--import` step required before any headless run after adding a `class_name`. CI for GDScript is a thing that would need to exist. |

---

## 6. Where the "one owner per fact" rule lands

Worth its own section because it is the axis CLAUDE.md cares most about, and it
does **not** point cleanly in one direction.

**Two clients is two copies of every client-side fact.** That is the F4 problem
and it has already cost something real.

**But ENG-0004 Phase 1 has largely paid that debt down, and did so with Godot
explicitly in mind.** `systems/statefeed/clientexport.py` renders JavaScript
**and GDScript from one body** — the two differ only in a punctuation table, so a
third client is a row. `godot/autoload/blackout_constants.gd` is committed on
`main` right now, generated, tested against a fresh render, *for a client that
lives on another branch*. The module docstring says why in as many words: so the
branch merges and finds its constants already generated rather than growing a
third hand-typed copy while it waits.

The facts that **cannot** be generated — `ROOM_KIND_COLORS`, `Z_LAYOUT_ORDER`,
which mix a server fact with a client one — are guarded instead, by
`test_client_constants.py`, which reads client sources **as text** and therefore
already covers the Godot client the moment the branch lands.

So the honest reading is: **the marginal cost of a second client is much lower
than it was a week ago, and the infrastructure that lowered it was built
deliberately for this case.** The remaining duplication is presentation and
feature work — meshes, panes, camera — not facts. That is duplication of *effort*,
which is a scheduling problem for a small team, not a correctness problem of the
kind the "one owner" rule exists to prevent.

---

## 7. Options

### Option A — All-Godot, web included

Godot becomes the only client; the browser gets a WASM export; the Evennia
webclient is retired.

- **Buys:** one renderer, one language, native+mobile for free later.
- **Costs:** everything in §3.4 and §5's con column. WebGL2 anyway. ~30 MB boot.
  Paste broken at login. No degraded mode. Discards ENG-0004.
- **Verdict: not recommended.** The web is Godot's weakest target and this
  project's only public entry point.

### Option B — Keep three.js on the web; make Godot a first-class native client — **recommended**

The browser client stays exactly as ENG-0004 left it. Godot is promoted from
prototype to a supported desktop download, over the same statefeed.

- **Buys:** Forward+ where it actually renders (native). A real client for players
  who want one, which also partly answers INFRA-0001 §6's telnet gap. A mobile
  path later. The browser keeps instant boot, DOM text, paste, and graceful
  degradation. Nothing landed on 08/23 is wasted.
- **Costs:** two renderers to feature-build. Binary distribution and signing. The
  `MULTISESSION_MODE` question can be deferred — a native client is a *separate*
  play session, not a second socket for the same page.
- **First moves, cheapest first:**
  1. **Rebase `godot-client-prototype` onto `main` now, before it drifts
     further.** 79 commits and eleven days is the cheapest this will ever be.
  2. **Delete the seven hand-typed `const CH_*` in `world_view.gd` and import
     `blackout_constants.gd`.** Already generated and committed on `main`.
     Removes the whole class of drift that has already bitten once.
  3. **Adopt `tile_actions`** and delete `world_state.direction_for()`. The branch
     is running the design Phase 2 replaced for cause; this is a straight port of
     an already-designed, already-tested contract.
  4. **Write the real client plan** the prototype README has been linking to since
     08/08 — phases, and what "parity" is defined as.
  5. Only then: decide whether `char_items_list` (the inventory pane) is worth
     1,376 lines' worth of GDScript, or whether the native client ships without it.

### Option C — Hybrid: DOM text, Godot canvas as the 3D pane

Keep the Evennia webclient shell and swap the three.js panes for an embedded Godot
canvas.

- **Buys:** DOM text *and* Godot rendering in the browser.
- **Costs:** **requires `MULTISESSION_MODE = 1`** (§4.2) — an account-semantics
  change for every player, in service of a rendering decision. Still WebGL2. Still
  ~30 MB. Still an iframe/canvas clipboard boundary between the panes. And it is
  the option with the most moving parts and the least precedent.
- **Verdict: technically possible, and worth knowing it is possible, but the worst
  effort-to-benefit of the three.** Revisit only if Godot ships WebGPU web export,
  which would change §3.1's arithmetic materially.

---

## 8. What would change this analysis

Stated explicitly so the decision can be revisited on evidence rather than
re-argued:

- **Godot ships WebGPU web export.** §3.1 is the single biggest strike against
  Option A, and it is a *current* limitation, not a permanent one. If Forward+
  reaches the browser, Options A and C both get materially stronger.
- **The game stops being text-first.** §3.4's costs are weighted for a MUD. If the
  3D panes become how the game is actually played and the text log becomes a
  sidebar, the canvas trade looks very different.
- **A second developer joins.** Most of Option B's cost is "two clients, one
  person". That is a scheduling constraint, not an architectural one.
- **Mobile becomes a target.** Native Godot mobile beats anything the browser
  client can do, and would push toward making Godot primary.

---

## 9. Appendix — facts checked while writing this

- `MULTISESSION_MODE` is unset in `blackout/server/conf/settings.py`; Evennia's
  default is `0` (`evennia/settings_default.py:761`). Basis for §4.2.
- `godotwebsocket/webclient.py` (installed copy, 80 lines) overrides only
  `send_text`. Basis for §2.
- `godot-client-prototype` is 79 commits behind `main`; last commit 2026-08-14.
  Channel coverage read from the `match` in `world_view.gd:83`.
- `godot/project.godot` declares `Forward Plus` and
  `rendering_device/driver.windows="d3d12"`.
- `godot/autoload/blackout_constants.gd` (66 lines, generated) already declares
  every channel name `world_view.gd` hand-types. **Correction, 08/25/2026:** it
  is **not tracked** — `git cat-file -e origin/main:godot/autoload/blackout_constants.gd`
  fails. ENG-0004 Phase 1 item 8 claims it was committed; only the JavaScript
  half was. §1.3 above and ENG-0004 both overstate this. See
  [ENG-0006](2026-08-25-ENG-0006-godot-option-a-plan.md) §2.1.
- `docs/2026-08-08-ENG-0005-godot-client-plan.md` does not exist on any ref.

**Sources for the Godot web-export claims** (checked 08/25/2026):

- [Exporting for the Web — Godot docs](https://docs.godotengine.org/en/4.7/tutorials/export/exporting_for_web.html)
  — WebGL 2.0 / Compatibility only; Forward+ and Mobile unsupported;
  single-threaded default since 4.3; `application/wasm` MIME and compression
  guidance; Safari WebGL2 caveat.
- [Web Export in 4.3 — Godot Engine](https://godotengine.org/article/progress-report-web-export-in-4-3/)
  — the no-threads backport and why it exists.
- [Deploying Godot 4 HTML exports with cross-origin isolation](https://www.rafa.ee/articles/deploying-godot-4-html-exports/)
  — COOP/COEP header requirements.
- [godotengine/godot#12587](https://github.com/godotengine/godot/issues/12587) and
  [#57382](https://github.com/godotengine/godot/issues/57382) — the web export's
  clipboard is not the system clipboard.
- [Godot 4.5 release notes](https://godotengine.org/releases/4.5/) — AccessKit
  screen-reader support; platform-native accessibility APIs, web not established.

**Author:** Nick Hobar
**Date:** 08/25/2026
