# ENG-0006 — Option A: Godot as the only client. Implementation plan.

**Status:** **Phases 0–1 DONE**; **Phase 4 export pipeline proven** (08/25/2026).
Phases 2, 3, 5 not started.
**Date:** 08/25/2026
**Decision:** Option A from [ENG-0005](2026-08-25-ENG-0005-godot-vs-webclient.md),
taken 08/25/2026. Godot becomes the only client. The Evennia webclient's 3D and
text panes are retired once Godot reaches the parity bar in §6.
**Related:** [ENG-0005](2026-08-25-ENG-0005-godot-vs-webclient.md),
[ENG-0004](old/2026-08-23-ENG-0004-webclient-architecture.md),
[INFRA-0001](old/2026-08-21-INFRA-0001-public-hosting.md)

> ENG-0005 recommended Option B. Option A was chosen anyway, deliberately, and
> this plan implements it in full. The costs ENG-0005 raised are not restated as
> objections here — they are carried forward as §7's risk register, with an
> owner and a mitigation each, which is what they should have been all along
> once the decision was made.

---

## 1. What Option A commits to

**One client. One socket. One renderer.**

The Godot client becomes the only way to play. `game.playblackout.io` serves a
Godot web export; the desktop build is the same project exported natively. The
Evennia webclient (`/webclient`, all six Blackout JS files, three.js, and the
GoldenLayout panes) is deleted **after** cutover, not before.

Three things Option A explicitly does **not** touch:

- **The Evennia website stays.** `game.playblackout.io` also serves Django's
  admin and the account pages. Only the *webclient* is retired.
- **`systems/statefeed/` does not change.** Verified: the contrib overrides
  exactly one method. The feed is already renderer-agnostic.
- **`MULTISESSION_MODE` does not change.** This is a genuine advantage of A over
  the hybrid: one client means one socket per player, so the default `0` is
  correct and stays. The blocker ENG-0005 §4.2 identified applies only to
  Option C.

---

## 2. Ground truth — two corrections found while merging

Both contradict what the existing docs claim. Both change the plan.

### 2.1 `godot/autoload/blackout_constants.gd` is NOT committed

ENG-0004 Phase 1 item 8 says "✅ Committed
`web/static/webclient/js/generated/blackout_constants.js` **and**
`godot/autoload/blackout_constants.gd`". Checked:

```
git cat-file -e origin/main:godot/autoload/blackout_constants.gd
  -> NOT TRACKED on origin/main
```

The JS half is committed. **The GDScript half exists only as an untracked
working file.** So the "it's already generated and waiting for you" story in
ENG-0005 §1.3 is half true: the renderer works and the file is on disk, but a
fresh clone gets nothing, and CI has never seen it. Phase 0 fixes this, and it
is the single cheapest item in this plan.

### 2.2 The statefeed carries no colour codes — verified, and this is load-bearing

`systems/banking/messages.py` warns that a colour code baked into a message
would reach a Godot client as a literal `|r`. The concern is real but it is a
warning, not a report: grepped `systems/statefeed/*.py` for `ANSIString`,
`parse_ansi`, `strip_ansi` and `systems/summary/*.py` for `|w`/`|c`/`|y`/`|r`/
`|g`/`|n` — **no hits**.

This matters more under Option A than it did before. The contrib overrides
`send_text` only. **Structured channel payloads never pass through
`parse_to_bbcode`** — they go out via the inherited `send_default` as raw JSON.
So any colour code that ever lands in a payload arrives in Godot as literal
text, and there is no conversion layer that would catch it.

Today that invariant holds by accident of discipline. Phase 2 makes it a test.

---

## 3. Phase 0 — land the merge, stop the drift — **DONE 08/25/2026, `6847080`**

### 0.1 The merge — **DONE, staged, not committed**

Two `add/add` conflicts, both resolved in favour of `main`:

| File | HEAD (branch) | Resolution |
|---|---|---|
| `web/static/webclient/js/plugins/blackout3d.js` | Pre-Phase-3 "mirror, not a controller" version, no click control | **main** — verified byte-identical to `origin/main` |
| `web/static/webclient/js/vendor/README.md` | UMD-era doc, "do not upgrade past r159" | **main** — the ESM doc |

Both files are ones Option A eventually deletes, so the resolution is bookkeeping
rather than a design choice — but it must be `main`'s version, because the web
client has to keep working for players right up to cutover.

Verified after resolution: no conflict markers, nothing unmerged, `node --test`
in `web/jstests/` passes **13/13**.

```bash
git commit --no-edit
```

### 0.2 Commit the generated GDScript constants — §2.1 — ✅

```bash
python blackout/scripts/export_client_constants.py --check
```

`--check` writes nothing and exits non-zero on a stale file. If it passes, the
untracked file is current and just needs adding. If it fails, re-run without
`--check` first.

```bash
git add godot/autoload/blackout_constants.gd
```

Then correct ENG-0004 Phase 1 item 8, which currently claims this was done.

### 0.3 Repoint `world_view.gd` at the generated constants — ✅

Delete the seven hand-typed names at `world/world_view.gd:18-24`
(`CH_MAP`, `CH_ROOM_INFO`, `CH_ROOM_PLAYERS`, `CH_PLAYER_ADD`,
`CH_PLAYER_REMOVE`, `CH_COMBAT`, `CH_AURA`) and read them from the
`BlackoutConstants` autoload instead. Every one is already generated under an
identical name.

Same for `scenes/console.gd:17` — `_CH_SUBSCRIBED` is generated as
`CH_SUBSCRIBED`.

**This is the fix for the failure that has already happened once**: the dead
`"Pole clearing"` room-kind key propagated *into* `world_view.gd` and rendered a
fallback hue in both clients. Under Option A there is no second client to
cross-check against, so generation stops being a nicety and becomes the only
guard.

### 0.4 Adopt `tile_actions`, delete `direction_for()` — ✅

`world_state.gd:direction_for()` is the grid-delta → direction-name table that
ENG-0004 Phase 2 deleted from the JS client **for cause**: it cannot express a
one-way exit, a diagonal link, or a map whose geometry and direction names
disagree. The branch predates that work and is still running the replaced
design.

The server-side contract already exists and is already tested (23 Python tests,
`systems/statefeed/tests/test_tile_actions.py`):

- `blackout_map` nodes carry `action` — the `goto (X,Y)` for that node.
- `room_info` carries `tile_actions` — the observer's tile and everything one
  real exit away, as `{command, kind}`.

Port `getTileAction`'s two-lookups-and-a-comparison shape from the JS pane. Keep
the distinction the JS comment records and that was nearly lost once: **absent**
means fall through to the node's `goto`; **empty command** means the server says
no. Diagonals are deliberately absent.

### 0.5 Green the branch — ✅

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot --import
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_world_state.tscn
```

The `--import` pass is required after 0.3 touches `class_name` resolution — the
README documents that a missing `global_script_class_cache.cfg` fails as
`Identifier "..." not declared`, which reads like a typo and is not one.

Then the full Python suite, from `blackout/`:

```bash
../evenv/Scripts/evennia.exe test --settings test_settings.py items systems typeclasses commands world
```

**Phase 0 exit bar:** merge committed, constants tracked and imported, tile
actions adopted, both Godot headless tests green, full Python suite green.

---

## 4. Phase 1 — commit the project to a web-capable renderer — **DONE 08/25/2026**

### 1.1 The renderer change

`godot/project.godot` today:

```
config/features=PackedStringArray("4.7", "Forward Plus")
rendering_device/driver.windows="d3d12"
```

Note that `rendering/renderer/rendering_method` is **not set at all** — the
project is on the default (`forward_plus`), and `config/features` is the project
manager's record of that choice, not the setting itself.

Web export forces `gl_compatibility` regardless of what the project asks for,
because Forward+/Mobile are unsupported on the web platform and WebGPU is not
implemented as of 4.7. So the real question is whether desktop *also* moves.

**Recommendation: move everything to `gl_compatibility`.** Under Option A the
web is the primary target; keeping Forward+ on desktop means every visual change
has to be verified twice, against a renderer most players will never see. One
renderer is the whole point of Option A.

```
rendering/renderer/rendering_method="gl_compatibility"
```

> **Resolved 08/25/2026, and the guidance above was wrong to frame it as a
> choice.** There is **no `.web` override, and none is needed**: the official
> renderers page says Compatibility is *"used by default on the web platform"*
> and that Forward+/Mobile are simply unsupported there. The web build renders
> through Compatibility whatever this project asks for.
>
> Godot's general feature-tag mechanism does allow `setting.featuretag`, and
> `web` is a real tag — but the feature-tags page also warns that overrides are
> **not** applied by ordinary setting reads (`get_setting_with_override()` is
> required), so relying on one for a setting the engine consumes at startup
> would have been a guess dressed as a config.
>
> So the setting below does not configure the web build at all. It aligns the
> **editor and desktop** with what web will already do. That is the one-renderer
> outcome Option A wants, reached by a shorter route than expected.

**Verified empirically, not assumed** — the key is
`renderer/rendering_method` under `[rendering]`, because the section header
already supplies the `rendering/` prefix:

```
PS rendering/renderer/rendering_method = gl_compatibility
RS method  = gl_compatibility
RS driver  = opengl3
```

### 1.2 What this costs in already-written code

`world_view.gd` and `entity_pool.gd` were authored and looked at under
Forward+. Compatibility has real differences — no SDFGI, no volumetric fog,
different tonemapping defaults, reduced light counts.

**Measured, 08/25/2026.** The same 6×6 map, marker and coloured room kinds were
rendered offscreen at 1280×720 under both renderers by driving the real
`Evennia.channel_received` signal path, then diffed:

| | |
|---|---|
| Mean luminance | `gl_compatibility` is **94.5%** of `forward_plus` |
| Mean absolute RGB difference | 0.0102 |
| Pixels meaningfully different | 7,600 of 230,400 sampled (**3.3%**) |
| Shader / render errors | **none** |

Geometry, island layout, link bars, the standing marker and every per-kind
colour are identical. The difference is a modest tone shift confined to lit
surfaces — Compatibility reads slightly darker and warmer. Nothing is missing
and nothing failed to compile.

**This is an art-pass item, not a code fix**, and it is the whole of risk R6.
The environment and light in `scenes/world.tscn` were tuned by eye under
Forward+; they should be re-tuned once under Compatibility, and from then on
there is only one renderer to tune for.

✅ Dropped `rendering_device/driver.windows="d3d12"`. It names a
RenderingDevice driver, and Compatibility does not use RenderingDevice — it
goes through the OpenGL backend — so the line was inert the moment the renderer
changed.

**Phase 1 exit bar:** ✅ project runs under `gl_compatibility` on desktop
(confirmed by `RenderingServer.get_current_rendering_method()`, not by reading
the file back); world scene visually diffed against the Forward+ baseline; both
headless tests still green; full Python suite still green.

**Not done here, and it gates Phase 4: the Godot export templates are not
installed.** `%APPDATA%/Godot/export_templates/` exists and is empty, and there
is no `export_presets.cfg` (it is gitignored). No web export can be produced
until the 4.7.1 template pack is installed — roughly 1 GB. That is a download
decision, so it is called out rather than taken.

---

## 5. Phase 2 — statefeed parity: the five missing channels

The prototype consumes 7 of 12. Missing: `char_avatar`, `char_vitals`,
`char_status`, `char_summary`, `char_items_list`.

Payload builders are dataclasses in `systems/statefeed/payloads.py`; each
declares its `channel` and its fields, so the GDScript shape is readable
straight off the Python.

| Channel | Payload | Godot work | Size |
|---|---|---|---|
| `char_vitals` | `payloads.py:173` | HP/resource bars. Rate-capped at 0.5s server-side | Small |
| `char_status` | `payloads.py:183` | Status effects row. Capped 1.0s | Small |
| `char_avatar` | `payloads.py:162` | The player's own asset key | Small |
| `char_summary` | `payloads.py:204` | `panels: dict` — **arbitrary keys by design**; a panel legitimately reports nothing. Do not build a dataclass mirror; iterate | Medium |
| `char_items_list` | `payloads.py:246` | The whole inventory + equipment. **The big one** | Large |

### 2.1 `char_items_list` is the real cost

This is the 3D inventory / paper-doll feature — **1,376 lines** in
`blackout_inventory.js`, plus its share of the 864-line mesh resolver. Nothing
equivalent exists in Godot.

Two things in the payload design make the port easier than the line count
suggests, and both should be honoured rather than re-litigated:

- **It is a snapshot, not a delta**, and `payloads.py:210-235` explains at
  length why — inventory mutation points are many and undisciplined
  (`add_item` merges stacks with a bare `+=` and fires no hook), so a delta
  protocol would rot at the first one anyone forgot. A missed delta on the
  player's own inventory is a phantom item they will click. **Do not "optimise"
  this into deltas in Godot.**
- **`equip_slots` ships the empty frame list** — every wield location in display
  order, occupied or not. Adding a slot to `WieldLocation` must light up a new
  frame with no client edit. Godot must iterate that list, not restate
  `SLOT_DISPLAY_ORDER`.

The `dropAction` gesture logic (`blackout_inventory.js:530`) ports across:
inv→inv is `swap` via `const.INVENTORY_SWAP_TEMPLATE`; the equip/unequip
commands are **named by the server** and looked up via `namedAction`; legality
is a comparison of two server-supplied values (`row.equip_slot` against the
frame's slot), not a client rule. Keep it that way. Port the `pendingMove`
staleness guard too — it fixes a real bug.

### 2.2 The colour-code invariant becomes a test — §2.2

Add to `systems/statefeed/tests/`: assert that no string field in any payload
produced by the serializers contains an Evennia colour code. Derive the payload
set from the `_Payload` subclasses rather than listing them, per CLAUDE.md's
no-census rule.

This is the guard for the failure mode that has no conversion layer:
`send_default` does not run `parse_to_bbcode`, so a colour code in a payload
reaches Godot as literal `|r` with nothing to catch it.

**Phase 2 exit bar:** all 12 channels consumed; inventory and equipment render
and are actable; the colour-code test is in the suite.

---

## 6. Phase 3 — text-client parity, the part Option A actually hinges on

**This is the largest and least-scoped phase, and it is the one that decides
whether Option A ships.** Everything before it is renderer work with a clear
contract. This is replacing a mature client.

`web/templates/webclient/base.html` loads these Evennia plugins today. Each is a
player-visible behaviour that currently exists and that a Godot-only world must
either provide or consciously drop:

| Evennia plugin | What it gives the player | Godot |
|---|---|---|
| `default_in` / `default_out` | Command input, text output | Prototype has both |
| `history` | Up/down command history | **Missing** |
| `dual_input` | The second input line | **Missing** |
| `options` / `options2` | The settings pane | **Missing** |
| `font` | Player-chosen font/size | **Missing** — and the README already flags the monospace font as load-bearing |
| `goldenlayout` + `splithandler` | Dockable, resizable panes | **Missing** — Godot needs its own dock system |
| `clienthelp` / `popups` | In-client help windows | **Missing** |
| `message_routing` | Routing messages to named panes | **Missing** |
| `notifications` | Tab-title badge on new activity | **Missing / N-A** |
| `hotbuttons` | Configurable command buttons | **Missing** |
| `oob` | Out-of-band plumbing | Superseded by `evennia.gd` |

Plus the affordances that are not plugins at all because the browser supplied
them free, and a canvas does not (ENG-0005 §3.4):

- **System-clipboard paste.** Godot web exports keep their own clipboard;
  `OS.get_clipboard()` stays empty unless the copy originated in-game. **This
  breaks `connect <name> <password>` from a password manager, at the login
  prompt, for every new player.** It is the single highest-severity item in this
  plan. Mitigation is a JS interop shim via `JavaScriptBridge` reading the async
  Clipboard API and feeding the focused `LineEdit`; it needs a permissions
  prompt and it needs testing per browser. **Prototype this before Phase 4** —
  if it cannot be made to work, the login flow needs a different design (e.g. a
  DOM overlay for the credential fields only).
- Text selection and copy out of scrollback.
- `Ctrl+F` over scrollback — must be built as an in-client find.
- Screen readers. Godot's AccessKit work targets native platform APIs; web
  support is not established. **Assume this is a regression and record it.**
- Browser zoom / text reflow.

### 3.1 Scope decision required

Not all of the above is worth building. **Make the drop list explicit and write
it into this document** rather than discovering it at cutover. A defensible
minimum bar for parity is: input + history, output with find, font size, a dock
system, help, and clipboard paste. `hotbuttons`, `notifications` and
`dual_input` are reasonable drops.

### 3.2 BBCode escaping — a real injection surface

`parse_to_bbcode` builds BBCode from ANSI, but **`TextTag.__str__` returns its
text raw**. Nothing escapes a literal `[` that was already in the game text.
Godot's `RichTextLabel` then parses it.

Unrecognised tags generally render literally, so `[MODTOOL]` — which the
moderator egg writes on every effect — is probably fine. But recognised ones are
not: an object, player or NPC whose name contains `[b]`, `[color=red]`, `[img]`
or `[url=...]` would inject markup into every player's log that sees it. `[img]`
and `[url]` are the ones that matter.

**Action:** a test that round-trips adversarial names through `parse_to_bbcode`,
plus a decision on where to escape. Escaping in `send_text` on the Blackout side
is wrong (it would double-escape the parser's own output); the right place is
almost certainly sanitising names at creation, or a targeted escape of `[` in
the text *before* `parse_ansi` runs. This needs 30 minutes of reading
`text2bbcode.parse()`'s ordering before choosing.

**Phase 3 exit bar:** the drop list is written down and agreed; clipboard paste
works or has an agreed alternative login flow; the BBCode escaping decision is
made and tested.

---

## 7. Phase 4 — web export and hosting

### 4.1 Export settings — **proven 08/25/2026**

> **BUILT AND BOOTED, 08/25/2026.** Export templates 4.7.1.stable installed
> (1,280,486,955 bytes, byte-exact against the GitHub release asset), a `Web`
> preset created with `variant/thread_support=false`, and the export served
> over plain HTTP with **no COOP/COEP headers at all** and loaded in a browser.

**Single-threaded needs no cross-origin isolation — proven, not inferred.**
Probed in the running page:

```
crossOriginIsolated        : false
sharedArrayBufferAvailable : false
engine booted              : true
```

and the engine's own banner:

```
Godot Engine v4.7.1.stable.official
OpenGL API OpenGL ES 3.0 (WebGL 2.0 ...) - Compatibility - Using Device: WebKit
Build configuration: Emscripten 4.0.20, single-threaded, no GDExtension support
```

So the page is *not* isolated, `SharedArrayBuffer` is *not* available, and Godot
runs anyway, through Compatibility/WebGL2 exactly as §4 predicted. **COOP/COEP
is closed as a non-issue.** It also means the export can be served from any
static host with no header configuration — which is what makes §4.2 easy.

**Real size, measured on this project** (not a community figure):

| | Bytes | |
|---|---:|---|
| Raw total | 39,892,593 | **38.0 MiB** |
| gzip -9 | 10,229,859 | 9.8 MiB |
| brotli -q11 | 7,036,836 | **6.7 MiB** (17.6% of raw) |

ENG-0005's estimate was close. The shape matters more than the total:

| | Bytes | Share |
|---|---:|---:|
| `index.wasm` (engine) | 39,513,091 | **99.0%** |
| `index.pck` (this game) | 44,892 | 0.1% |

**Essentially all of it is engine, and that is a floor, not a ceiling.** The
`.pck` is 44 KB because the Godot project currently contains no art.

**The art is the number to worry about.** 12.0 MiB of `.glb` still has to be
ported from the three.js client:

| Model | Bytes |
|---|---:|
| `player_character.glb` | 10,912,852 |
| `floating_eye.glb` | 1,087,128 |
| `map_transition.glb` | 485,384 |
| `rusty_scrap_shortsword.glb` | 131,628 |

**And the delivery model inverts.** `blackout_models.js` fetches a `.glb` on
demand — a player who never opens the inventory pane never downloads the sword,
and an item with no model costs nothing. Baked into a `.pck`, every byte ships
up front, before the login prompt. glTF with PNG textures also compresses
poorly, so most of that 12 MiB survives Brotli: a naive port takes the download
from ~6.7 MiB to roughly ~18 MiB, and one 10.9 MiB character model is most of
it.

Two mitigations, both to decide in Phase 2 when the art is ported, not later:
- **Keep lazy loading.** Godot can fetch a `.glb` at runtime and `GLTFDocument`
  can parse it from a buffer, preserving the "art never blocks content" rule
  that `blackout_models.js` is built around.
- **Compress the art.** 10.9 MiB for one character is large regardless of
  engine; texture resizing and mesh decimation are worth a pass either way.

**Remaining Phase 4 export settings:**
- Single-threaded confirmed as the right default. `web_nothreads_release.zip`
  is the template variant in use.
- Expect the Apple-device problems to be absent under single-threaded, per the
  4.3 release notes. **Not yet tested on Safari** — R10 stands.

### 4.1a The export preset is gitignored — recorded here so it is reproducible

`godot/.gitignore` excludes `export_presets.cfg` (Godot's default, because the
file can carry signing credentials). This project's has none, but that means a
fresh clone and any CI runner has no preset and cannot export. The working one:

```ini
[preset.0]
name="Web"
platform="Web"
runnable=true
export_filter="all_resources"
script_export_mode=2

[preset.0.options]
variant/extensions_support=false
variant/thread_support=false          # the whole COOP/COEP story
html/canvas_resize_policy=2
html/focus_canvas_on_start=true
progressive_web_app/enabled=false
```

Built with:

```bash
godot --headless --path godot --export-release "Web" <out>/index.html
```

**Decide before Phase 4 proper:** either un-ignore this file (it holds no
secret) or generate it in CI. Leaving it only on one machine is how the build
becomes unreproducible.

### 4.2 Serve the export from Cloudflare, not Django

`playblackout-site/wrangler.jsonc` already serves `./dist` as static assets with
no worker script. Put the export there, beside the marketing site.

Reasons, in order:
- Django is a poor static host and 4001 is behind the tunnel, so every byte of a
  30 MB download would cross `cloudflared`.
- `evennia reload` happens constantly. Serving the client binary from the game
  origin means a reload can interrupt a player's *download*, not just their
  session.
- A `_headers` file covers the `application/wasm` MIME type, and COOP/COEP if
  the single-threaded decision is ever revisited.

This does mean the client and the socket are on different origins. That is fine
for a WebSocket — `wss://` is not subject to CORS — but it must be stated because
it is the kind of thing that gets discovered at 2am.

### 4.3 Expose port 4008

Currently `GODOT_CLIENT_WEBSOCKET_CLIENT_INTERFACE = "127.0.0.1"` with no
ingress rule — INFRA-0001 §6 already flags this as open.

In `deploy/cloudflared/config.yml`, **above the catch-all**:

```yaml
  - hostname: game.playblackout.io
    path: ^/godot
    service: ws://localhost:4008
```

The ordering rule from INFRA-0001 §3 holds and is not optional: rules evaluate
top to bottom, and a websocket rule below the catch-all gets handed HTML instead
of a socket upgrade.

Then `GODOT_CLIENT_WEBSOCKET_CLIENT_INTERFACE = "0.0.0.0"` (or the tunnel's
interface), and `evennia.gd`'s `DEFAULT_HOST`/`DEFAULT_PORT` become a
`wss://game.playblackout.io/godot` URL for web builds.

**Verify the contrib tolerates a path prefix.** It is a plain autobahn
`WebSocketServerFactory` and should ignore the path, but INFRA-0001 §6 explicitly
says "verify against the contrib first", and that advice stands.

### 4.4 What is already paid for

The **45-second websocket keepalive** in `server/conf/websocket.py` covers this
with no new work. Cloudflare's edge closes websockets idle for ~100s and that
timer is not configurable below Enterprise; the fix is server-side pings, it is
transport-level, and INFRA-0001 §5.2 already states it covers the Godot client.
Measured: three silent sockets died at 125.6/126.0/126.9s, a pinged one survived.

**Phase 4 exit bar:** web export loads from Cloudflare, connects over `wss://`,
survives a 5-minute idle, and a real player can create an account and log in.

---

## 8. Phase 5 — cutover and deletion

**Nothing is deleted until Phase 3's bar is met and the export has run in
public alongside the old client for a fortnight.** The web client keeps working
throughout Phases 0–4; that is why Phase 0 resolved the merge conflicts in
favour of `main` rather than dropping the files.

1. Point `/play` on `playblackout-site` at the Godot client. Update the seven
   `steps` in `src/pages/play.astro` — several are webclient-specific ("click
   the small cog top left", "open the 3D client in the Options menu") and will
   be wrong.
2. Remove the webclient template override and the six Blackout JS files, plus
   `vendor/three/` (1.27 MB) and `vendor/goldenlayout.min.js`.
3. **`systems/statefeed/tests/test_client_constants.py` will fail loudly, by
   design.** It scans both `blackout3d.js` (line 67) and
   `godot/world/world_view.gd` (line 68), and carries a **vacuity guard** at
   lines 444-448 that fails if `blackout3d.js` is not where it expects — because
   "every check skips a client it cannot find" is exactly how this test would
   quietly stop testing anything. Deleting the JS client means deliberately
   removing its half of that test, not letting the guard trip.
4. Same for `test_client_assets.py`, which checks vendored files exist *and* are
   referenced by the template.
5. Delete `web/jstests/` and its 13 tests.
6. Retire ENG-0004 with a status line pointing here.

---

## 9. Risk register

| # | Risk | Severity | Mitigation | Phase |
|---|---|---|---|---|
| R1 | **Clipboard paste broken at the login prompt** | **Highest** | `JavaScriptBridge` shim; prototype before Phase 4. Fallback: DOM overlay for credentials | 3 |
| R2 | BBCode injection via names containing `[url=`/`[img]` | High | Adversarial round-trip test; escape before `parse_ansi` | 3 |
| R3 | Text-client parity is under-scoped | High | §6's table; write the drop list down and agree it | 3 |
| R4 | ~30 MB boot in front of a text game | Medium | **Measured: 6.7 MiB Brotli / 38.0 MiB raw, 99% engine.** Cloudflare CDN + Brotli | 4 ✅ |
| R11 | **Art delivery inverts: `.pck` ships all 12 MiB of `.glb` up front, where three.js lazy-loads it** | **High** | Runtime `.glb` fetch via `GLTFDocument`, and compress `player_character.glb` (10.9 MiB alone) | 2 |
| R5 | No graceful degradation — renderer failure is total | Medium | Accepted cost of Option A. Keep a documented telnet-ish fallback path in mind | — |
| R6 | Compatibility renderer changes the look | Medium | Screenshot diff against Forward+ baseline before proceeding | 1 |
| R7 | Screen-reader regression | Medium | Record it explicitly as a known regression; revisit if AccessKit reaches web | 3 |
| R8 | Colour code leaks into a payload — no conversion layer | Medium | The §5.2 test | 2 |
| R9 | Godot not on PATH; `--import` needed before headless runs | Low | Already documented in `godot/README.md`; add to CI | 0 |
| R10 | Safari WebGL2 issues | Low | Test on Safari; document a browser recommendation on `/play`. **Not yet tested** | 4 |

---

## 10. Definition of done

Option A is complete when all of these are true:

- [ ] All 12 statefeed channels consumed by the Godot client
- [ ] Inventory and equipment render, and drag/equip/unequip act
- [ ] A new player can create an account and log in **with a pasted password**
- [ ] Command history, in-client find, font sizing, and a dock system exist
- [ ] The drop list (§6.1) is written down and agreed
- [ ] Web export loads from Cloudflare and connects over `wss://`
- [ ] A socket survives 5 minutes idle through the tunnel
- [ ] Both Godot headless tests run in CI
- [ ] Full Python suite green; the colour-code and BBCode tests exist
- [ ] `/play` describes the Godot client, not the webclient
- [ ] The JS client and its guard tests are removed together, deliberately

---

## 11. Sequencing

Phases 0→1→2 are mechanical and low-risk; 0 is hours, 1 is a day, 2 is where the
inventory work lands. **Phase 3 is the long pole and its two highest risks (R1
clipboard, R2 BBCode) are cheap to spike.** Spike both during Phase 2 rather
than waiting — if clipboard paste cannot be made to work in a web export, that
is a fact worth having before the inventory port is written, because it changes
what the login flow has to look like and it is the one item in this plan that
could genuinely force a rethink.

**Author:** Nick Hobar
**Date:** 08/25/2026
