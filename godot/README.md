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

**Status: every state-feed channel in `SUBSCRIBABLE_CHANNELS` is consumed.** A tabbed game log on the
left, the 3D world and a tabbed control panel on the right, vitals bars and a
minimap over the world. The world pane draws tile grids per map, the
links between them, room-kind colours, real tile art on the maps that have
any, a marker on the room you are standing in, the NPCs and items in it, a
white flash on anything you land a hit on, and your aura ring. Everything in the room is drawn from the mesh ladder below —
a fetched model where there is art, its family's silhouette where there is not.

| Input | Does |
|---|---|
| **Hover** | Lights whatever a click would take — the entity, else the tile |
| **Left-click a tile** | Walks there, if it is adjacent and has an exit |
| **Left-click an entity** | Sends the entity's `interact` command, verbatim — `attack mutant raider`, `bank`, `craft`, `talk`, `cut` |
| **Left-click a player** | Nothing — an empty `interact`, which the server decides and this pane does not |
| **Drag an inventory cell** | Swap, equip or unequip — whichever the server named |
| **Right-click an inventory cell** | The item's own actions, as the server listed them |
| **Click a minimap cell** | Walks there. The same `tile_action` lookup the 3D pane makes |
| **Character tab** | The sheet — whatever panels `char_summary` sent |
| **Skills tab** | The roster as a grid, banded by category, with a bar per skill |
| **Click a skill** | Its sheet: XP, progress and everything it unlocks. Where that lands is an Options setting |
| **Quests tab** | What you have taken, and how far through it you are |
| **Options tab** | Text size, interface scale, which panes are drawn, where skill detail goes. Saved between runs |
| **Up / Down in the input** | Walks the command history; a half-typed draft is kept |
| **Escape in the input** | Hands the keyboard to the map — see "Two modes" below |
| **WASDQEZC / hjklyubn** | Walk, while the map has the keyboard |
| **Enter, in move mode** | Hands the keyboard back to the input |
| **Click a chat tab** | Filters the log to what that tab claims. A dot means lines landed there while you were elsewhere |
| **3D button** | Hides the 3D world. Persists. The inventory has its own toggle in Options — one switch for both meant giving up the bag to stop the diorama |
| **Drag a divider** | Resizes, and it is remembered. Both offsets were a literal 300 in the scene until 08/28/2026 |
| **Ctrl+F** | Find in the log. Enter steps, Escape closes |
| **Help tab** | Client help — gestures and keys, not the game's `help` |
| **Right-drag** | Orbit the camera |
| **Wheel** | Zoom |

## Nothing in the two tab strips takes the keyboard

**Focus IS the mode in this client.** The console grabs the input on ready and
`_unhandled_key_input` only runs when the input does *not* have it, so anything
that silently takes focus turns the player's next letter into a movement
command. Both `TabContainer`s and both their internal `TabBar`s are
`FOCUS_NONE` for that reason — filtering a log is not leaving the input — and
`Ctrl+Tab` exists precisely because they are.

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

> **The avatar faces the way it walked, and the yaw is on the FIGURE.** Ported
> from `blackout3d.js`'s `yawTowards`. `WorldView.yaw_towards` is
> `atan2(dx, -dy)`, which puts **+Z** — the way both a served `.glb` character
> and the procedural figure are authored to face — along the step, with the Z
> term negated because grid Y grows northward and world Z does not. Two rules
> come with it: only a step to a NEIGHBOURING tile turns anything, since a
> teleport has no direction in it and a relayout replays a zero-length move; and
> the yaw is kept on `WorldView` rather than read back off the node, because
> `_redraw_avatar` frees and rebuilds that node whenever `char_avatar` names a
> new asset or its art lands, and a figure that snapped back to north the moment
> its model arrived would read as the model being wrong. It is written to the
> avatar and never to the marker — the marker's frame is what the ring offset
> and the camera rig are expressed in, and turning it would swing both.

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

## The ground is art on top of the slab, not instead of it

Since 08/28/2026 a map can be **surfaced**: every one of its tiles gets a real
tile mesh laid on the coloured slab it used to be. `MapPalette.TILE_MODELS` is
the table, keyed by map name, valued by asset key — `oasis` gets a sand tile
with a water pool, `oasis_outskirts` gets open sand, and `trade town sector 1`
gets nothing and therefore keeps the plain slab.

**A layer, not a replacement, and the slab is why.** The slab is what carries
the room-kind colour and what hover is written through — hover writes an
instance colour, and these tiles are one MultiMesh, so there is no per-tile
material to tint. Replacing the slab would have cost both. `TERRAIN_SCALE` is
under 1 so a rim of it shows around every tile, and the two facts stay visible.

**A surfaced map colours fewer kinds, on purpose.** `MapPalette.kind_colour`
hashes an unlisted room kind to a stable hue, which is exactly right on a bare
map and exactly wrong under art: "Oasis" hashes to magenta, and magenta is then
the frame around every square metre of desert. `kind_tint` is the same table
without the fallback — an authored kind keeps its colour, everything else falls
to the neutral a kindless tile already used. `MapPalette.tile_colour` is the
chooser between them, and which one applies is a property of the ISLAND rather
than of the tile.

**Both map panes ask that question, so neither owns it.**
`MapPalette.is_surfaced(z, meshes)` does, and it is asked of the console's
shared resolver — the minimap is bound to it for this and nothing else, since
nothing on a minimap is a mesh. The question put to it is **"could this key ever
produce art"**, not "has it arrived", and the difference is one round trip that
matters both ways:

- "Has it arrived" makes an island come up in hashed hues and then change colour
  a second later. A whole map recolouring after it is already on screen reads as
  a bug; coming up neutral and having the art fade in on top does not.
- "Is it configured" would keep the neutral palette on a map whose art is never
  coming — a failed deploy, a model tree the export forgot — and there the
  hashed hues are the only thing left telling a bank from a clearing.

`may_have_art` is false before the manifest lands and false again for a key that
failed, so both panes fall back together and neither flickers. The minimap
redraws on `manifest_ready` for that reason: without it a surfaced map would
draw once in the bare palette and stay there for the session.

**The minimap is better for it independently**, which is worth saying because
otherwise this reads as consistency for its own sake. A field of hashed hues is
a field in which the bank does not stand out; neutral ground with four coloured
landmarks on it is what a minimap is for.

> **A terrain tile has to be a unit SQUARE, and the normalise cannot check
> that.** `_normalise` divides by the model's longest axis, which is right for a
> sword and an assumption for a tileset: `block_a` in the desert set is a 2x2
> tile with a rock lip hanging 0.28 past its south edge, so its longest axis is
> 2.28 and it normalises to a footprint of **0.877** — a visible gap between
> every pair of tiles in the world, from a model that loaded perfectly and is
> exactly one unit on the axis it was measured by. `smoke_model_load` measures
> the footprint of every terrain tile in `TILE_MODELS` for that reason. Prefer
> the flat `center_*` tiles, which are square to the millimetre.

> **A flat tile needs `TERRAIN_LIFT`.** `tile_oasis_outskirts` is a single plane
> and measures 0.000 thick, and a plane resting exactly on the face it covers is
> coplanar with it — z-fighting, not a picture. Everything else in the pane rests
> on the face by measurement and needs no epsilon, because everything else has
> volume.

> **The tileset's materials declare `alphaMode: BLEND` and are not
> transparent.** Blender writes BLEND for any material carrying an RGBA image,
> used or not; the packed palette's alpha is 255 everywhere. Harmless on a prop,
> not on the ground — a transparent floor is the thing every entity, prop and
> marker in the pane sorts against. Both tile keys carry `opaque` in
> `ModelRegistry.PRESENTATION`, and `test_map_terrain` asserts every terrain key
> does.

> **The browser pane has no terrain layer**, so there is nothing to keep in step
> with `blackout_models.js` here — the parity rule above applies to a model both
> panes draw, and neither pane draws a tile the other does not. The served
> manifest names the tile keys; the browser simply never asks for them.

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

All thirty are headless and exit non-zero on failure. Twenty-seven need
nothing running; three of the four `smoke_*` scenes need an Evennia, and none
needs an account. `smoke_console` is the exception: it builds `console.tscn` for real and
needs nothing, because the socket it opens is expected to fail.

Two of them guard the SCENE rather than a model, which is the gap everything
else leaves:

| | Catches |
|---|---|
| `smoke_console` | A `%UniqueName` that no longer resolves, a node whose type changed, a theme that came unattached. Every other test builds its subject in code, so a scene edit is invisible to all of them |
| `test_theme` | A `theme_type_variation` a script names and `ui/blackout_theme.tres` does not declare. The control silently falls back to the default style, which reads as a styling mistake rather than a typo |

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

`test_world_view.tscn` needs nothing running either — `yaw_towards` is static,
and every case is a pair of grid cells:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_world_view.tscn
```

`test_map_terrain.tscn` needs nothing running either — which map is surfaced
with what is a table, and the space the terrain is placed in is measured
against a hand-built model:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_map_terrain.tscn
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

`test_skills_state.tscn` and `test_skills_view.tscn` need nothing running
either. The view test asserts the two things a screenshot would not catch: that
every command leaving the pane is one the server named, and that each of the
three detail modes asks for exactly what it shows.

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_skills_view.tscn
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

## Skills left the character sheet

Until 08/28/2026 the roster was a **band on the dossier** — one panel under
`systems/summary/panel_defs/`, arriving in `char_summary` beside vitals,
holdings and the rest. The Character tab drew it because it draws every panel
it is sent, and `score` printed it as a wrapped run of `Cutting 30  Brawn 12`.

It moved because a grid could not be built from it without breaking the rule
the dossier is built on. [SummaryState] **iterates panels and never names
one** — that is what lets a band added on the server appear here with no client
edit — and a skills screen would have had to reach into that payload and pull
one key out by name. The first client to do that makes the contract a
suggestion.

So the band left. `score` no longer carries skills, `profile` no longer carries
them either, and the roster ships on a channel of its own:

```
char_skills -> {skills: [...], categories: [...],
				total_level, total_xp, max_level, closest}
```

**Each row is complete**, which is the decision that shapes this pane. It
carries the level, the XP curve *and the whole unlock ladder* — every recipe,
gathering node, item and ability that skill opens, with the level each needs.
The ladder is static (what a recipe requires does not depend on who is asking),
so it could have been a second request; shipping it in the snapshot is what
makes clicking a skill **instant, with no round trip**, for a few kilobytes
across the entire roster.

`current_xp` / `needed_xp` are progress into the current level and that level's
own threshold; `total_xp` is cumulative. Both ship, under names that say which
they are, because deriving one from the other is exactly the mistake that once
rendered a `1154 / 152` bar on the server's own screen.

### The grid is grouped by the server's order, coloured by the client's

Rows arrive sorted by `(category, name)` and `categories` arrives beside them,
so the bands and their contents need no ordering table here — the text screens
and this grid agree without either of them saying so. What is the client's is
three columns, a bar per cell, and `world/skill_palette.gd`.

That palette is **guarded rather than generated**, the same asymmetry
`ROOM_KIND_COLORS` sits on: a category named there that no skill declares is a
bug and `test_client_constants.py` fails on it, while a category with no entry
draws the fallback and costs nothing. It caught its own first dead key on the
run that introduced it — `General`, which is `BaseSkill`'s default and which no
shipped skill uses.

### Where a clicked skill's answer goes is a setting

Three modes, in Options, defaulting to both:

| Mode | Sends | Shows |
|---|---|---|
| **Pane and log** | `skills <key>` | The sheet in the pane, and the server's text sheet in the log |
| **In the pane** | nothing | The sheet in the pane |
| **In the game log** | `skills <key>` | The server's text sheet in the log |

**`In the pane` sends nothing, and it has to.** The server cannot be asked
about a skill quietly — the command that renders the sheet renders it *into the
log*, which is the thing that mode exists to avoid. So the setting is not
"where is the answer shown" but "which answer is asked for", and each mode asks
for exactly what it will show. The cost is that pane mode draws from the last
snapshot, which is why the rows are complete.

Both text answers come from one renderer,
`systems/progression/skills/detail.py`. It was inline in the EvMenu until this
change, which meant the only way to see what a skill unlocked was to be inside
a menu; three readers now share it — the menu node, `skills <skill>`, and this
channel — and the sheet is rendered *from* the structured form rather than from
a second set of handler reads, so the grid and the text cannot describe a skill
differently.

### The open sheet survives a rebuild

`char_skills` republishes whenever a level moves, on resync, and whenever the
player types `skills`, and this pane rebuilds wholesale on each — so the
selected key outlives the rebuild. Without that, the sheet would throw itself
away the moment the skill being read levelled, which is the moment a player is
most likely to be looking at it. It is also what makes the sheet update live.

One consequence worth naming: this pane frees its children with `queue_free`
where [InventoryView] and [QuestsView] use `free`. Those rebuild from a
*model's* signal and nothing they destroy is mid-emit; this one also rebuilds
from a *cell's* signal — clicking a skill destroys the cell that was clicked —
and freeing there tears down an object while its signal is still emitting.

## The quest log is numbers, not sentences

`char_quests` sends each objective as `{key, description, current, required,
counted, done}` rather than as the rendered `[x] Rats culled 3/5` the telnet
screen prints — so this pane can draw a progress bar, grey out what is done,
and show the two kinds of objective differently. A client given the sentence
could only print it.

`required` is **1 for a one-shot objective** rather than absent, so the bar
needs no branch for the two kinds; `counted` is what decides whether the
reading beside it is a fraction or a tickbox.

The payload is built entirely through `QuestHandler`'s public read API — see
`systems/statefeed/quests.py`. Nothing outside that handler reads
`db.active_quests`, and this would have been the fourth module to try.

## The minimap is drawn from the feed, not from the text map

`blackout_map` already carries every node with its `room_kind` and every link;
`room_info` carries where you are standing and what each near tile affords.
[WorldState] reassembles both, and **the console owns that model** — the 3D
pane built its own until 08/28/2026, and two panes drawing one chunked payload
would have meant reassembling it twice and, on a resync, two reassemblies
briefly disagreeing about which tiles exist.

It is bound to the console's **resolver** as well, and for one question only:
whether the map it is drawing has ground art, which decides which of the two
colour palettes it uses. See "The ground is art on top of the slab" above — the
short of it is that the pane a minimap sits on top of must not be colouring the
same map a different way.

So the minimap is a second VIEW, and it gets three things routing the ASCII
print to a pane would not have given:

- it scales with `content_scale_factor`, where a monospace block cannot;
- it is clickable, through the same `WorldState.tile_action` the 3D pane uses,
  so click-to-walk works with **no new server contract**;
- the server can stop sending the ASCII map to this client altogether.

That last one is the point. `XYZRoom.return_appearance` msg'd the map on every
`look`, and `look` runs on every room change — so on a 95-node map the text
pane's dominant content was a picture already being drawn beside it. A Godot
session is now answered `False` by `GridTile._wants_ascii_map`, and every other
protocol is unaffected.

**The player decides, and the way they decide is `automap`.** The client-based
answer is only a DEFAULT: `automap on` / `automap off` overrides it
permanently, `automap` reports which way it is set and whether that was chosen
or inherited, and `help automap` explains it — which is how a telnet player
finds it at all. The Options tab carries the same three as buttons, because a
player of this client has never seen the text map and would otherwise have no
reason to imagine it exists. They are BUTTONS and not a checkbox on purpose:
the setting is the server's, so a checkbox here would be claiming to know a
state only the server can report.

## The log is tabbed, and the server never names a tab

Every line of game text may carry a routing tag in its outputfunc kwargs --
`caller.msg((line, {"type": "combat"}))` on the server arrives here as
`{"type": "combat"}`. The vocabulary is `MESSAGE_TYPES` in
`blackout/systems/statefeed/constants.py`, generated into
`autoload/blackout_constants.gd` as `MSG_*` like every other server-owned name.

**The server says what a line IS. The client says which tab shows it.** There is
no server fact naming a tab and there must not be one; `ChatTabs.DEFAULT_TABS`
is the whole table and adding a tab is one row in it.

Three consequences, each of which reads as a bug until you know it:

- **A type no tab claims is not lost.** It appears in `All`, which is the tab
  the client opens on. A message type added on the server tomorrow shows up
  there with no edit in this project -- the same degradation an item with no art
  gets from the mesh ladder.
- **An untagged line is normal.** Evennia's EvMenu nodes, `page`, and much of
  its error prose carry no tag at all. `ChatTabs.tabs_for("")` reads that as
  `general` rather than dropping it, and the default is applied HERE rather than
  on the server, so "nobody has tagged this yet" stays distinguishable from
  "this line is genuinely general".
- **Half the tags are Evennia's own.** `say`, `whisper`, `pose`, `look`, `help`
  and `examine` are tagged by the engine, not by Blackout, and the vocabulary
  copies its spelling rather than inventing a parallel one. `whisper`, not
  `tell`, for that reason.

**One RichTextLabel per tab, appended to.** Godot's own docs say a
console-sized log stutters when `text` is reassigned, because that reparses
every line of BBCode, and prescribe `append_text` plus `threaded`. A design that
re-rendered the buffer on tab switch would do the expensive thing on the most
frequent interaction -- and would lose each tab's scroll position, which is the
difference between a tab strip and an annoying one. Each log is capped at
`ChatView.MAX_LINES` by `remove_paragraph(0)`; there is no max-lines property.

`Ctrl+F` follows the visible tab. The console rebinds the find bar on
`active_log_changed`, because a find that spanned tabs would scroll one the
player cannot see and count matches in logs they are not reading.

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
| `world/quest_state.gd` | Your quest log. Knows no quest key and must not learn any. |
| `scenes/quests/quests_view.gd` | The quest tab: a bar per objective, drawn from numbers rather than prose. |
| `world/map_palette.gd` | Room-kind colours, island order, and which map is surfaced with which terrain. Read by BOTH map panes; guarded from Python by path. |
| `scenes/minimap/minimap_view.gd` | The map drawn small over the world pane. Clickable, and from the feed rather than the ASCII print. |
| `scenes/panel/panel_view.gd` | The control-panel tab strip. Tabs are addressed by title, never by index. |
| `scenes/vitals/vitals_bars.gd` | Your resources as bars. One control, two homes. |
| `world/chat_tabs.gd` | Which tab a line belongs in, and which tabs have unread lines. Holds no text. |
| `scenes/chat/chat_view.gd` | The tab strip and one RichTextLabel per tab. Appends; never re-renders. |
| `world/client_settings.gd` | Font size, UI scale, which panes are shown and where the dividers sit, via ConfigFile under `user://`. |
| `ui/blackout_theme.tres` | Every margin, separation, font size and label colour. Assigned once on the console root and inherited. |
| `world/server_endpoint.gd` | Which server this build talks to. Debug reaches localhost, release reaches production. |
| `world/scrollback_find.gd` | Which matches exist and which one you are on. Pure. |
| `scenes/find/find_bar.gd` | Ctrl+F over the log. Scrolls via `get_character_line`. |
| `scenes/help/help_view.gd` | What the CLIENT does. The game's own `help` covers the rest. |
| `scenes/options/options_view.gd` | The sliders and the pane toggles. Writes through the settings object, applies nothing. |
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
