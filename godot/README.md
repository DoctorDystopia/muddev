# Blackout — Godot client

Graphical client for the Blackout MUD. Talks to Evennia's `godotwebsocket`
contrib port (`4008`, set in `blackout/server/conf/settings.py`).

Plan, phases and design decisions:
[docs/old/2026-08-25-ENG-0006-godot-option-a-plan.md](../docs/old/2026-08-25-ENG-0006-godot-option-a-plan.md),
with the decision it implements in
[docs/old/2026-08-25-ENG-0005-godot-vs-webclient.md](../docs/old/2026-08-25-ENG-0005-godot-vs-webclient.md).

> This used to link `docs/2026-08-08-ENG-0005-godot-client-plan.md`, which was
> never written — checked with `git log --all --diff-filter=A`. ENG-0005 is now
> the decision record and ENG-0006 the plan.

**This project renders through Compatibility (OpenGL 3.3 / WebGL 2.0), not
Forward+.** The web export cannot use Forward+ at all — Forward+ and Mobile are
unsupported on the web platform and Godot has no WebGPU backend as of 4.7 — so
the desktop build and the editor are held to the renderer the browser will
actually use. `renderer/rendering_method="gl_compatibility"`, under
`[rendering]`; the key is *not* `rendering_method`, because the section header
already supplies the `rendering/` prefix. There is no `rendering_method.web`
override and none is needed. See ENG-0006 §4.

> **Do not put explanation in `project.godot`.** It said all of the above in
> `;` comments for about an hour, and opening the editor once rewrote the file
> and stripped every one of them — which the file's own header warns it will
> do. Setting values there is fine; the reasons have to live here.

**Status: all twelve state-feed channels consumed.** Text game on the left, the
3D world and the inventory on the right, a vitals strip above the log and a
character sheet behind a button. The world pane draws tile grids per map, the
links between them, room-kind colours, a marker on the room you are standing
in, the NPCs and items in it, a white flash on anything you land a hit on, and
your aura ring. Everything in the room is drawn from the mesh ladder below —
a fetched model where there is art, its family's silhouette where there is not.

| Input | Does |
|---|---|
| **Hover** | Lights whatever a click would take — the entity, else the tile |
| **Left-click a tile** | Walks there, if it is adjacent and has an exit |
| **Left-click an entity** | Sends the entity's `interact` command, verbatim — `attack mutant raider`, `bank`, `craft`, `talk`, `cut` |
| **Left-click a player** | Nothing — an empty `interact`, which the server decides and this pane does not |
| **Drag an inventory cell** | Swap, equip or unequip — whichever the server named |
| **Right-click an inventory cell** | The item's own actions, as the server listed them |
| **Character button** | Opens the sheet — whatever panels `char_summary` sent |
| **Options button** | Text size and interface scale, saved between runs |
| **Up / Down in the input** | Walks the command history; a half-typed draft is kept |
| **Escape in the input** | Hands the keyboard to the map — see "Two modes" below |
| **WASDQEZC / hjklyubn** | Walk, while the map has the keyboard |
| **Enter, in move mode** | Hands the keyboard back to the input |
| **3D button** | Hides both 3D panes. Text-only, and it persists |
| **Ctrl+F** | Find in the log. Enter steps, Escape closes |
| **? button** | Client help — gestures and keys, not the game's `help` |
| **Right-drag** | Orbit the camera |
| **Wheel** | Zoom |

## Two modes, and why there have to be two

The webclient binds sixteen movement keys and can afford to, because its input
is one DOM element among many and focus leaves it constantly — `hotkeys.js`
just asks "is the player typing?" Here the text input owns the keyboard: the
console grabs it on ready and nothing takes it away, so the same question would
answer "yes" forever and every movement key would be dead code.

So the mode is explicit. **Escape** leaves the input and the map takes the
keyboard; **Enter** gives it back; the input's placeholder says which mode is
current. That last part is not decoration — a text field that has silently
stopped accepting letters is indistinguishable from a client that has hung.

## Where meshes come from

One ladder, and [MeshResolver] is the only thing that knows the order:

```
asset has art?    -- yes -->  the fetched model      tier 1
       | no
family has parts? -- yes -->  the family's shape     tier 2
	   | no
							  the generic block      tier 3
```

The server already sends this as one lookup — `serialize_entity` calls `asset`
and `family` "the two tiers of one lookup" — so the client resolves rather than
decides. Nothing outside `world/meshes/` knows what a weapon looks like.

**Two named methods, not a flag.** `resolve_entity()` always returns something,
because an unmodelled item still has to be visible and clickable.
`resolve_scenery()` returns art or nothing, because a tile with no prop must
stay a plain slab — a generic block on every tile would be scenery nobody asked
for. The browser encodes that same policy as "remember to call `hasModel()`
before `resolve()`", which is a rule that gets forgotten.

**Everything is normalised into a unit box**, tier 1 included, so each caller
applies one scale of its own. This is not cosmetic: the packed sword's own
bounds are 0.33 x **9.80** x 1.02, and unnormalised it stands ten tiles tall.

**Art sharpens in; it never blocks.** Every resolve answers immediately from the
family shape, and `refreshed` fires if a model arrives later. A room full of
unmodelled content is fully playable, which is what lets content ship ahead of
art.

**Adding a family is one entry in `family_shapes.gd`.** Its keys are the
generated constants, not string literals — a family renamed server-side breaks
the file loudly instead of silently drawing every weapon as a box.

> **On the web, art must be served from the page's own origin.** `wss://` is
> exempt from CORS; an HTTP fetch for a `.glb` is not, and
> `game.playblackout.io/static/webclient/models/` serves no
> `Access-Control-Allow-Origin` (measured 08/26/2026). `ServerEndpoint.asset_origin`
> therefore prefixes **the page's own origin** for a release web build, read off
> `location.origin` through `JavaScriptBridge`. Same origin, no preflight.
> **Not a relative path**: `HTTPRequest` parses the URL itself and refuses one
> with no scheme, which is how a release client came to draw every entity as a
> family shape while the art sat correctly deployed beside it (08/27/2026).
> **The deploy has to put the model tree at the same path** — see
> `deploy/webexport/README.md`.

> **`STATEFEED_ENTITY_RADIUS` is 10, not 0** — a 21x21 neighbourhood, 441
> rooms. So the feed names a great deal the text channel does not, and every
> entity is placed from its own `coords`. This file claimed the radius was 0 and
> ringed everything around the observer, which stacked the whole neighbourhood
> onto one tile — exactly what `serialize_entity`'s docstring warned would
> happen. It was invisible only while every entity was an identical small
> sphere. An entity whose map has not arrived is drawn nowhere, never somewhere
> wrong.

> **You are the occupant the feed never mentions.** `emit_room_contents` leaves
> the observer out of their own `room_players` list, so the one tile that is
> never empty is described as holding one fewer thing than it does. The ring
> sized itself from that count, and a lone item dropped at your feet came out at
> radius 0 — dead centre, which is exactly where the pane draws you. The pane
> now tells the pool which tile is yours (`EntityPool.stand`), you take slot 0
> of its ring, and `observer_slot_changed` hands back the offset to draw the
> avatar at. The **marker itself never moves off centre**: the camera rig
> follows it by NodePath and the aura ring is anchored to it, so only the figure
> hanging on it shifts.

> **A rigged model's `mesh.get_aabb()` is its BIND POSE, not what renders.**
> The Spider-Man placeholder `player_character` carried until 08/27/2026
> measured 0.74 x **0.17** x 1.00 by its meshes — flat, as if lying down — while
> its skeleton spanned 1.04 tall. Normalising by the mesh box alone made it
> about six times too big and left it floating. `bounds_of` merges in the
> skeleton's rest bones, which is a floor on the real extent rather than the
> whole of it. The base character that replaced it does not reproduce the bug —
> its bind pose is the pose — so **do not read the merge as dead code**: nothing
> about a file announces which kind it is. **The proper fix is baking the
> skinning out in `assets/pack_model.py`** — these models carry skinning
> attributes for zero animations, so the rig is dead weight that also breaks
> measurement.

> **The character is a T-POSE, so it is fractionally WIDER than it is tall.**
> 1.859 of outstretched arms against 1.820 of height, which means the normalise
> divides by the arm span and the figure stands 0.979 of a unit rather than
> 1.000. Two percent is not worth correcting, but "the longest axis is the
> height" stopped being true for characters and the smoke test says so in the
> assertion it makes — uprightness is measured against DEPTH, not width.

> **An export can be wrong about itself, and nothing downstream can tell.** The
> eye's body arrives at albedo alpha 0 against `alphaMode: BLEND` — an invisible
> shell around a floating eyeball. It loads cleanly and reports no error. The
> only symptom is a person saying it looks wrong, which is why `opaque` is a
> hand-written entry in `ModelRegistry.PRESENTATION` and why that table has to
> stay in step with `blackout_models.js`.

> **Nothing floats at a fixed height.** Every tier centres what it produces on
> the origin by a different amount, so each node is lifted by its own measured
> bottom. The single `ENTITY_LIFT` constant this replaced could only ever be
> right for one shape.

> **A rotated part's BOX is not its shape**, and everything rests on the bottom
> of that number. `bounds_of` used to transform each `mesh.get_aabb()`, which
> measures the rotated box rather than the geometry inside it — and a box has
> corners its contents do not. The gathering node's rock is tilted by
> (0.5, 0.3, 0.2) radians, so its box reached **0.164 lower than any vertex in
> it** and the whole node was lifted a twelfth of a tile clear of the ground
> (measured 08/27/2026). Static meshes are now read vertex by vertex; skinned
> ones keep the box, because their vertices describe a pose nobody renders.

> **Headless prints `Parameter "material" is null` when freeing a fetched
> model.** It comes from `servers/rendering/dummy/`, which only exists under
> `--headless`, and does not happen in a real renderer. Noise, not a leak.

## The inventory draws in 3D without giving up drag and drop

The browser gives the inventory a whole second three.js scene, camera and
renderer, and hit-tests meshes to work out what was clicked. Here the cells stay
`Control`s — so Godot's own drag and drop keeps working, which is the single
largest thing the engine buys on this screen — and `ItemStage` supplies each
cell nothing but a picture.

**One viewport, not one per cell.** The obvious build is a `SubViewport` per
cell: with 32 carried slots and a dozen worn frames that is forty-odd render
targets for forty thumbnails a centimetre across. Instead every item is laid out
on a grid in one 3D scene under one orthographic camera, and each cell shows its
own rectangle of the result through an `AtlasTexture`. One target, one camera,
one pass — and the slow spin costs the same whether one item is on screen or
forty.

Cells are addressed by INDEX: the view allocates them (carried first, then
worn), and where an index sits in the 3D grid is `item_stage.gd`'s business
alone. Two cells claiming one rectangle would quietly draw one object in two
slots, which is why a test asserts every cell owns a different region.

The stage updates `WHEN_VISIBLE`, so text-only mode really does stop paying for
it.

> **`own_world_3d` must be true, and it defaults to false.** A SubViewport left
> at the default SHARES its parent's `World3D`, so the item meshes land in the
> same 3D world the game is drawn in — forty swords and rocks in a neat grid,
> floating in the sky over the map — and the stage's `WorldEnvironment` repaints
> the game's sky black. Both happened on the first run. Nothing else about the
> viewport hints at it, which is why `test_inventory_view` asserts the two
> worlds differ rather than trusting a comment.

## Reconnecting

The socket redials itself on a drop: one second, then two, four, eight, capped
at thirty, forever. A close the client *asked for* is never redialled, which is
what the `requested` flag on `Evennia.closed` is for.

**A reconnect does not restore the session.** A websocket close ends the Evennia
Session, so the new socket lands on the connection screen and the player logs in
again — exactly what the webclient does. `CharState.reset()` is what makes that
coherent: it clears the character, so the HUD stops claiming 87/100 beside a
dead socket and the login form comes back. The form's visibility is a *function*
of whether a body exists rather than a one-way dismissal, which keeps "am I
puppeted" to a single owner.

## Running

Start the game server first — the client connects on load and reports the
failure in the feed pane if nothing is listening.

**Which server it reaches is decided by the BUILD, not by a constant somebody
has to remember to flip.** `ServerEndpoint` keys off `OS.is_debug_build()`: the
editor and a debug export reach `ws://127.0.0.1:4008`, a release export reaches
`wss://game.playblackout.io/godot`. Verified by wrapping `WebSocket` in a real
release web export and watching which URL it dialled.

Point either at somewhere else with `--server=<url>` on the command line, or
`?server=<url>` in the page's query string on the web. Only `ws://` and `wss://`
are accepted — an override naming `http://` would fail in a way that looks
exactly like the server being down.

```bash
cd blackout && ../evenv/Scripts/evennia.exe start
```

Then open `godot/` in Godot 4.7 and press F5, or run it headless. Godot is not
on PATH on this machine; the 4.7.1 build lives in an extracted folder that is
itself named `...exe`, so the binary path repeats:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --path godot
```

Log in through the form at the top of the text column, or by typing the same
thing into the input field — they send the identical line:

```
connect <name> <password>
```

The form exists for the password field, which can be masked where a shared
command line cannot be, and for the **Paste** button on web builds. See rule 6
below.

The client does **not** subscribe when the socket opens — that is a race it
loses whenever the Server is still starting. It waits for the server to
announce an empty subscription set at `ServerSession.at_sync`, and answers
that. The same message is what lets it recover from an `evennia reload`, which
wipes the Session ndb subscriptions live on without dropping the socket.

The world snapshot arrives when you puppet a character, pushed by
`Character.at_post_puppet`.

To see the recovery for yourself: with the client connected, run
`evennia reload`, and the feed pane logs `server has no subscription for us;
subscribing` followed by a fresh `subscribed: ...`.

## Tests

All eighteen are headless and exit non-zero on failure. Fifteen need nothing
running; the three `smoke_*` scenes need an Evennia, and none needs an account.

> **After adding a `class_name`, run `--headless --path godot --import` once
> before running anything headless.** Global class names live in
> `.godot/global_script_class_cache.cfg`, which is rebuilt by an editor scan and
> is gitignored. A plain `--headless` run does not rebuild it, so a brand-new
> `class_name` fails as `Identifier "..." not declared in the current scope` —
> which reads like a typo and is not one. A fresh clone needs this too.

`test_world_state.tscn` needs **nothing running** — its payloads are hand-built
in the shape Godot's JSON parser produces:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_world_state.tscn
```

`test_char_state.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_char_state.tscn
```

`test_model_registry.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_model_registry.tscn
```

`test_inventory_state.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_inventory_state.tscn
```

`test_inventory_view.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_inventory_view.tscn
```

`test_summary_state.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_summary_state.tscn
```

`test_login_view.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_login_view.tscn
```

`test_command_history.tscn`, `test_client_settings.tscn`,
`test_scrollback_find.tscn`, `test_server_endpoint.tscn`,
`test_movement_keys.tscn` and `test_reconnect_policy.tscn` need nothing
running either:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_command_history.tscn
```

`smoke_reconnect.tscn` needs a running Evennia but no account. It proves the
one thing `test_reconnect_policy` cannot: that `Evennia.open()` is callable a
second time. A `WebSocketPeer` at STATE_CLOSED is a used object, so the client
builds a fresh peer per open — a change that looks obviously correct and can
only be confirmed against a real server.

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/smoke_reconnect.tscn
```

`smoke_handshake.tscn` needs a running Evennia but no account —
`blackout_subscribe` is answered on an unauthenticated session:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/smoke_handshake.tscn
```

## Layout

| File | Owns |
|---|---|
| `autoload/evennia.gd` | The socket. The only place that knows the `[name, args, kwargs]` wire format. |
| `scenes/console.tscn` `.gd` | The shell: output, input, and the subscription handshake. |
| `scenes/world.tscn` | The 3D scene: environment, light, islands, marker, camera rig. |
| `world/world_state.gd` | The world model. Chunk reassembly and the float boundary. |
| `world/char_state.gd` | YOUR model: entity id, hp, in_combat, skill levels. |
| `world/model_registry.gd` | Which assets have art (fetched) and how each is oriented (not). |
| `world/meshes/mesh_palette.gd` | Colours and finishes. One owner for both. |
| `world/meshes/family_shapes.gd` | What each family looks like, as data. One entry per family. |
| `world/meshes/mesh_builder.gd` | Part data to a Node3D. Knows no family names. |
| `world/meshes/model_loader.gd` | The only file that knows HTTP and glTF exist. |
| `world/meshes/mesh_resolver.gd` | The mesh ladder. The only thing panes call. |
| `world/inventory_state.gd` | Carried grid and worn slots. |
| `scenes/inventory/inventory_view.gd` | Draws the grid and the paper doll; turns a gesture into a command. |
| `scenes/inventory/slot_cell.gd` | One frame. Drag/drop is Godot's engine API, not hand-rolled. |
| `scenes/inventory/item_stage.gd` | Every item in 3D, into ONE render target. Cells read sub-rects of it. |
| `world/summary_state.gd` | The dossier. Knows no panel names and must not learn any. |
| `scenes/summary/summary_view.gd` | The sheet, a native `Window`. Iterates panels, never enumerates them. |
| `scenes/login/login_view.gd` | Name, password, connect/create. Hides itself when vitals arrive. |
| `world/command_history.gd` | The up-arrow. Pure rules, no widget. |
| `world/movement_keys.gd` | Which key means which direction. Knows nothing about focus. |
| `world/reconnect_policy.gd` | How long to wait before redialling. Pure schedule, no clock. |
| `world/client_settings.gd` | Font size and UI scale, via ConfigFile under `user://`. |
| `world/server_endpoint.gd` | Which server this build talks to. Debug reaches localhost, release reaches production. |
| `world/scrollback_find.gd` | Which matches exist and which one you are on. Pure. |
| `scenes/find/find_bar.gd` | Ctrl+F over the log. Scrolls via `get_character_line`. |
| `scenes/help/help_view.gd` | What the CLIENT does. The game's own `help` covers the rest. |
| `scenes/options/options_view.gd` | The two sliders. Writes through the settings object, applies nothing. |
| `scenes/hud.tscn` `.gd` | Draws char_state above the text pane. Presentation only. |
| `world/world_view.gd` | Drawing tiles, links, islands and the marker. Owns the browser-parity hash and colours. |
| `world/entity_pool.gd` | Everything the feed can see, each on its own tile. Hit flash and hover. |
| `world/orbit_camera.gd` | The `SpringArm3D` follow rig. |

Four rules worth not rediscovering:

1. **Decode with `get_string_from_utf8()`.** The contrib's own README example
   uses `get_string_from_ascii()`, which mangles the box-drawing that the
   dossier and every section rule in the game are built from.
2. **Every number in a parsed payload is a float.** `JSON.parse_string` returns
   `{"x": 3.0, "num": 19863.0}` — always. A dictionary keyed on that will not
   match a key written as `3`, and nothing raises. `WorldState` converts at the
   point of use; do the same rather than coercing whole payloads, because the
   first genuinely fractional field the server grows would be corrupted
   silently.
3. **The client acts only through `Evennia.command()`**, which sends the same
   `text` a telnet player types. Clicking a tile sends `north` — never a
   position. There is no privileged client channel, so every lock, cooldown and
   permission keeps working with nothing to re-audit. It also does not decide
   WHICH command: `serialize_entity` names the whole thing in `interact` and
   the pane forwards it. Clicking another player does nothing because the
   server sends an empty `interact` for one — every other misclick is
   recoverable, and opening combat on a person is not — and the pane learns
   that rather than knowing it.
4. **The output pane's monospace font is load-bearing**, not cosmetic. Godot's
   default theme font is proportional and the game draws ASCII art constantly.
6. **On the web, Ctrl+V into a LineEdit may not paste, and the failure is
   silent.** Godot's export listens for the DOM `paste` event, but its
   `clipboard_get` reads `navigator.clipboard.readText()` -- the
   permission-gated path -- and swallows a rejection in an empty `catch`, so a
   refused read looks exactly like an empty clipboard. Without user activation
   that read is refused in both engines, and Firefox does not support the
   `clipboard-read` permission at all, so there is nothing to grant once. The
   login form's **Paste button** is the floor: a click IS user activation, so
   the read that fails from a keystroke succeeds from a button. Desktop is
   unaffected -- Ctrl+V is native there.
5. **Anything both panes draw must match.** The two get put side by side on the
   same character, so a difference has to mean a bug. That is why
   `WorldView.stable_hash` reimplements the JS string hash instead of calling
   Godot's, and why the HSL-to-HSV conversion beside it is closed-form rather
   than matched by eye. Both have test vectors computed from the JS directly.
