# Blackout — Godot client

This is the graphical client for the Blackout MUD. It talks to Evennia's
`godotwebsocket` contrib port (`4008`, set in
`blackout/server/conf/settings.py`).

Plan, phases and design decisions:
[docs/old/2026-08-25-ENG-0006-godot-option-a-plan.md](../docs/old/2026-08-25-ENG-0006-godot-option-a-plan.md),
with the decision it implements in
[docs/old/2026-08-25-ENG-0005-godot-vs-webclient.md](../docs/old/2026-08-25-ENG-0005-godot-vs-webclient.md).

> This file used to link `docs/2026-08-08-ENG-0005-godot-client-plan.md`, but
> nobody ever wrote that doc. `git log --all --diff-filter=A` confirms it.
> ENG-0005 is now the decision record, and ENG-0006 is the plan.

**This project renders through Compatibility (OpenGL 3.3 / WebGL 2.0), not
Forward+.** The web export cannot use Forward+ at all. The web platform does
not support Forward+ or Mobile, and Godot has no WebGPU backend as of 4.7.
Thus, the desktop build and the editor use the renderer that the browser will
actually use. The setting is `renderer/rendering_method="gl_compatibility"`,
under `[rendering]`. The key is *not* `rendering_method`, because the section
header already supplies the `rendering/` prefix.

There is no `rendering_method.web` override, and none is necessary. See
ENG-0006 §4.

> **Do not put explanation in `project.godot`.** The file said all of the above
> in `;` comments for about an hour. Then one opening of the editor rewrote the
> file and stripped every comment, as the file's own header warns. Values are
> fine there. The reasons must live here.

**Status: the client consumes every statefeed channel in
`SUBSCRIBABLE_CHANNELS`.** The layout has a tabbed game log on the left, the 3D
world and a tabbed control pane on the right, and vitals bars and a minimap
over the world. The world pane draws these things:

- The tile grids of each map, and the links between them
- Room-kind colors, and real tile art on the maps that have any
- A marker on the tile where you stand, and the NPCs and items on it
- A white flash on anything that you hit, and your aura ring.

The mesh ladder below draws everything on the tile. It uses a fetched model
where there is art, and the silhouette of the family where there is not.

| Input | Does |
|---|---|
| **Hover** | Lights whatever a click would take — the entity, else the tile |
| **Left-click a tile** | Walks there. Closes any open menu first — the server's menus stand aside for a walk, an exit or a click on a thing |
| **Left-click an entity** | Sends the entity's `interact` command, verbatim — `attack mutant raider`, `bank`, `craft`, `talk`, `cut`. On another tile, walks there first: `goto (4,7) then cut rusty pole` |
| **Left-click a player** | Nothing — an empty `interact`, which the server decides and this pane does not |
| **Drag an inventory cell** | Swap, equip or unequip — whichever the server named |
| **Right-click an inventory cell** | The item's own actions, as the server listed them |
| **Click a minimap cell** | Walks there. The same `tile_action` lookup the 3D pane makes |
| **Combat tab** | Your weapon, combat level, attack speed, and a button per style — OSRS's Combat Options |
| **Click a style** | Sends the row's `combatoptions <style>`. The highlight moves when the server republishes, not on the click |
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
| **Middle-drag** | Orbit the camera. It was right-drag until 09/10/2026, when the right button became Choose Option |
| **Right-click the world** | Choose Option: every verb the server said a thing affords, at the cursor |
| **Wheel** | Zoom |

## Nothing in the two tab strips takes the keyboard

**Focus IS the mode in this client.** The console grabs the input on ready, and
`_unhandled_key_input` runs only when the input does *not* have focus. Thus,
anything that silently takes focus turns the next letter of the player into a
movement command. For that reason, the two `TabContainer`s and their two
internal `TabBar`s are `FOCUS_NONE`: a filter on the log does not leave the
input. `Ctrl+Tab` exists precisely because they are `FOCUS_NONE`.

## Two modes, and why there have to be two

The retired webclient bound sixteen movement keys and could afford to. Its
input was one DOM element among many, and focus left it constantly, so
`hotkeys.js` only asked "is the player typing?" Here, the text input owns the
keyboard. The console grabs it on ready, and nothing takes it away. Thus, the
same question would answer "yes" forever, and every movement key would be dead
code.

So the mode is explicit. **Escape** leaves the input, and the map takes the
keyboard. **Enter** gives it back. The placeholder of the input says which mode
is current. That last part is not decoration. A text field that silently
refuses letters looks the same as a client that hung.

## Where meshes come from

One ladder, and [MeshResolver] is the only thing that knows the order:

```
asset has art?    -- yes -->  the fetched model      tier 1
	   | no
family has art?   -- yes -->  the family's model     tier 2
	   | no
family has parts? -- yes -->  the family's shape     tier 3
	   | no
							  the generic block      tier 4
```

The server already sends this as one lookup. `serialize_entity` calls `asset`
and `family` "the two tiers of one lookup". Thus, the client resolves and does
not decide. Nothing outside `world/meshes/` knows what a weapon looks like.

**Tier 2 is the one tier that is not per-entity**, and it exists because an
asset key is sometimes the wrong grain. The asset key of a corpse is the key of
the NPC that left it. Art aimed at keys would thus need one packed model for
each creature in the game before any body stopped being a gray box. What every
corpse has in common is its family, which the server already sends.

`FamilyShapes.MODELS` is that table: one family, one asset key. The table
belongs to the CLIENT, in the same way as the tier 3 shapes. `corpse_skeleton`
is an art filename, and the server must never learn it.

Know this when you handle `refreshed`: the signal names an asset key, and an
entity that tier 2 redraws does not carry that key. Ask
`MeshResolver.redraws_for()`, and do not compare keys. A direct comparison was
correct while there was one model tier. It silently stopped being correct when
there were two tiers.

**Two named methods, not a flag.** `resolve_entity()` always returns something,
because an unmodeled item must still be visible and clickable.
`resolve_scenery()` returns art or nothing, because a tile with no prop must
stay a plain slab. A generic block on every tile would be scenery that nobody
asked for. The browser client encoded the same policy as "remember to call
`hasModel()` before `resolve()`", and people forget a rule like that.

**The resolver normalizes everything into a unit box**, tier 1 included, so each
caller applies one scale of its own. This is not cosmetic. The packed sword's
own bounds are 0.33 x **9.80** x 1.02, and with no normalization it stands ten
tiles tall.

**Art sharpens in. It never blocks.** Every resolve answers immediately from the
family shape, and `refreshed` fires if a model arrives later. A room full of
unmodeled content is fully playable, and that is what lets content ship ahead
of art.

**The client fetches every model and draws it one time out of sight, behind the
veil.** On the web, the browser compiles a shader the first time something
draws with it, and the compile freezes the window. A measurement on 09/13/2026
in a Chromium WebGL 2 export: today's twenty models cost **13.5 s** of frozen
frames for one draw each. Six compiles of 1–5 s made most of that time. If the
first draw came at first sight, the freeze came when a corpse dropped or an NPC
walked in.

`MeshResolver.prefetch_all()` asks for every manifest key the first time the
veil goes up. It asks at the veil and not at startup, because the login form is
not a screen to freeze while a player types a password. `ShaderWarmer` is a
tiny `SubViewport` that shares the `World3D` of the world pane. It draws each
arrival for three frames, 20,000 units below the map and past the far plane of
the world camera. A model that waits for its draw counts as in flight, so the
veil waits for the compiles too. Instanced terrain is its own variant, so the
warmer also draws each model as a one-instance `MultiMesh`.

> **A compiled shader lives only as long as a material of its exact variant.**
> Godot frees the shader with its last user, and Godot frees a copy with its
> entity. Thus, `ModelLoader._prepare_materials` makes the materials of each
> PROTOTYPE the same variant as its copies. The prototypes live all session and
> keep the warmed shaders alive. The procedural palette has no prototype, so the
> warmer keeps one hidden block for it.

**Hover changes a color, never a shader.** `emission_enabled` is part of the key
that a `BaseMaterial3D` builds its shader from. Hover used to flip it both
ways, so every hover-on AND every hover-off caused a compile, because Godot
frees the variant that the material just left. **Every material is glow-ready
from birth**: emission is on, at whatever value the model authored (black at
zero for nearly all of them).

`MeshGlow` owns the rule. `MeshPalette` and `ModelLoader` both call
`MeshGlow.prepare`, and hover writes only color and energy. A measurement on
the same export: a toggle cost ~52 ms for each hover on a primitive, and ~1.9 s
on the first hover of a model. A write to the uniforms never cost anything
measurable. `test_entity_pool` asserts that no hover changes the flag.

**A new family is one entry in `family_shapes.gd`**: `SHAPES` for a procedural
shape, `MODELS` for a packed model that stands in for the whole family. The
keys of the two tables are the generated constants, not string literals. Thus,
a family renamed on the server breaks the file loudly. It does not silently
draw every weapon as a box.

> **On the web, the page's own origin must serve the art.** `wss://` is exempt
> from CORS. An HTTP fetch for a `.glb` is not, and
> `game.playblackout.io/static/webclient/models/` serves no
> `Access-Control-Allow-Origin` (measured 08/26/2026). Thus, for a release web
> build, `ServerEndpoint.asset_origin` prefixes **the page's own origin**, read
> from `location.origin` through `JavaScriptBridge`. The origin is the same, so
> there is no preflight.
>
> **Do not use a relative path.** `HTTPRequest` parses the URL itself and
> refuses a URL with no scheme. On 08/27/2026, that made a release client draw
> every entity as a family shape, while the art sat correctly deployed beside
> it. **The deploy must put the model tree at the same path.** Refer to
> `deploy/webexport/README.md`.

> **`STATEFEED_ENTITY_RADIUS` is 10, not 0**: a 21x21 neighborhood of 441
> tiles. Thus, the statefeed names a great deal that the text channel does not,
> and the pool places every entity from its own `coords`. This file once claimed
> that the radius was 0, and the client ringed everything around the observer.
> That stacked the whole neighborhood onto one tile, exactly as the docstring of
> `serialize_entity` warned. The bug was invisible only while every entity was
> an identical small sphere.
>
> The pool draws an entity whose map has not arrived nowhere, never somewhere
> wrong.

> **You are the occupant that the statefeed never mentions.**
> `emit_room_contents` leaves the observer out of their own `room_players` list.
> Thus, the statefeed describes the one tile that is never empty as one thing
> short. The ring sized itself from that count, so a lone item dropped at your
> feet came out at radius 0: dead center, exactly where the pane draws you.
>
> The pane now tells the pool which tile is yours (`EntityPool.stand`). You take
> slot 0 of its ring, and `observer_slot_changed` gives back the offset for the
> avatar. The **marker itself never moves off center**. The camera rig follows
> it by NodePath, and the aura ring is anchored to it, so only the figure that
> hangs on it shifts.

> **The avatar faces the way it walked, and the yaw is on the FIGURE.** The code
> comes from `yawTowards` in `blackout3d.js`. `WorldView.yaw_towards` is
> `atan2(dx, -dy)`. It puts **+Z** along the step. +Z is the way that a served
> `.glb` character and the procedural figure both face as authored. The code
> negates the Z term, because grid Y grows northward and world Z does not.
>
> Two rules come with it:
>
> 1. **Only a step to a NEIGHBORING tile turns anything.** A teleport has no
>    direction in it, and a relayout replays a zero-length move.
> 2. **`WorldView` keeps the yaw. The code does not read it back from the
>    node.** `_redraw_avatar` frees and rebuilds that node whenever
>    `char_avatar` names a new asset or its art lands. A figure that snapped
>    back to north when its model arrived would look like a wrong model.
>
> The yaw goes to the avatar and never to the marker. The ring offset and the
> camera rig use the frame of the marker, and a turn of the marker would swing
> the two.

> **A rigged model's `mesh.get_aabb()` is its BIND POSE, not what renders.**
> Until 08/27/2026, `player_character` carried a Spider-Man placeholder. Its
> meshes measured 0.74 x **0.17** x 1.00, flat as if it lay down, but its
> skeleton was 1.04 tall. A normalize by the mesh box alone made it about six
> times too big, and it floated. `bounds_of` merges in the rest bones of the
> skeleton. That merge is a floor on the real extent, not the whole extent.
>
> The base character that replaced the placeholder does not reproduce the bug,
> because its bind pose is the pose. But **do not read the merge as dead code**:
> nothing about a file shows which kind it is. **The proper fix is to bake the
> skinning out in `assets/pack_model.py`.** These models carry skinning
> attributes for zero animations, so the rig is dead weight that also breaks
> measurement.

> **The character is a T-POSE, so it is fractionally WIDER than it is tall.**
> The outstretched arms measure 1.859, and the height measures 1.820. Thus, the
> normalize divides by the arm span, and the figure stands 0.979 of a unit, not
> 1.000. Two percent is not worth a correction. But "the longest axis is the
> height" stopped being true for characters, and the smoke test says so in its
> assertion: it measures uprightness against DEPTH, not width.

> **An export can be wrong about itself, and nothing downstream can tell.** The
> body of the eye arrives at albedo alpha 0 with `alphaMode: BLEND`: an
> invisible shell around a floating eyeball. It loads cleanly and reports no
> error. The only symptom is a person who says that it looks wrong. For that
> reason, `opaque` is a hand-written entry in `ModelRegistry.PRESENTATION`, and
> that table must stay in step with `blackout_models.js`.

> **Nothing floats at a fixed height.** Every tier centers what it produces on
> the origin by a different amount. Thus, the code lifts each node by its own
> measured bottom. The single `ENTITY_LIFT` constant that this replaced could
> only ever be right for one shape.

> **A rotated part's BOX is not its shape**, and everything rests on the bottom
> of that number. `bounds_of` used to transform each `mesh.get_aabb()`. That
> measures the rotated box, not the geometry inside it, and a box has corners
> that its contents do not have. The rock of the gathering node tilts by
> (0.5, 0.3, 0.2) radians. Thus, its box reached **0.164 lower than any vertex
> in it**, and the whole node floated a twelfth of a tile above the ground
> (measured 08/27/2026).
>
> The code now reads static meshes vertex by vertex. Skinned meshes keep the
> box, because their vertices describe a pose that nobody renders.

> **Headless prints `Parameter "material" is null` when freeing a fetched
> model.** It comes from `servers/rendering/dummy/`, which only exists under
> `--headless`, and does not happen in a real renderer. Noise, not a leak.

## The ground is art on top of the slab, not instead of it

Since 08/28/2026, a map can be **surfaced**: every one of its tiles gets a real
tile mesh on top of the colored slab that it used to be.
`MapPalette.TILE_MODELS` is the table. Its keys are map names, and its values
are asset keys:

- `oasis` gets a sand tile with a water pool.
- `oasis_outskirts` gets open sand.
- `trade town sector 1` gets nothing, and thus keeps the plain slab.

**A layer, not a replacement, and the slab is the reason.** The slab carries the
room-kind color, and hover writes through the slab. Hover writes an instance
color, and these tiles are one MultiMesh, so there is no material for each tile
to tint. A replacement of the slab would have cost the two. `TERRAIN_SCALE` is
under 1, so a rim of the slab shows around every tile, and the two facts stay
visible.

**A surfaced map colors fewer kinds, on purpose.** `MapPalette.kind_colour`
hashes an unlisted room kind to a stable hue. That is exactly right on a bare
map and exactly wrong under art: "Oasis" hashes to magenta, and magenta then
frames every square meter of desert. `kind_tint` is the same table with no
fallback. An authored kind keeps its color, and everything else falls to the
neutral color that a kindless tile already used. `MapPalette.tile_colour`
chooses between them, and the choice is a property of the ISLAND, not of the
tile.

**The two map panes ask that question, so neither pane owns it.**
`MapPalette.is_surfaced(z, meshes)` owns it, and the console's shared resolver
answers it. The minimap binds to that resolver for this question only, because
nothing on a minimap is a mesh. The question is **"could this key ever produce
art"**, not "has it arrived". The difference is one round trip, and it matters
in the two directions:

- "Has it arrived" makes an island come up in hashed hues and then change color
  a second later. A whole map that changes color after it is on screen looks
  like a bug. A map that comes up neutral, while the art fades in on top, does
  not.
- "Is it configured" would keep the neutral palette on a map whose art never
  comes, for example after a failed deploy or with a model tree that the export
  forgot. There, the hashed hues are the only thing left that tells a bank from
  a clearing.

`may_have_art` is false before the manifest lands, and false again for a key
that failed. Thus, the two panes fall back together, and neither flickers. For
that reason, the minimap redraws on `manifest_ready`. Without it, a surfaced map
would draw one time in the bare palette and stay that way for the session.

**The minimap is better for it on its own merits.** This matters, because
otherwise the change reads as consistency for its own sake. In a field of
hashed hues, the bank does not stand out. A minimap exists to show neutral
ground with four colored landmarks on it.

> **A terrain tile must be a unit SQUARE, and the normalize cannot check
> that.** `_normalise` divides by the longest axis of the model. That is right
> for a sword and an assumption for a tileset. `block_a` in the desert set is a
> 2x2 tile with a rock lip 0.28 past its south edge. Thus, its longest axis is
> 2.28, and it normalizes to a footprint of **0.877**. That leaves a visible
> gap between every pair of tiles in the world, from a model that loaded
> perfectly and is exactly one unit on the axis that the code measured.
>
> For that reason, `smoke_model_load` measures the footprint of every terrain
> tile in `TILE_MODELS`. Prefer the flat `center_*` tiles, which are square to
> the millimeter.

> **A flat tile needs `TERRAIN_LIFT`.** `tile_oasis_outskirts` is a single plane
> and measures 0.000 thick. A plane that rests exactly on the face it covers is
> coplanar with that face, and the result is z-fighting, not a picture.
> Everything else in the pane rests on the face by measurement and needs no
> epsilon, because everything else has volume.

> **The materials of the tileset declare `alphaMode: BLEND` and are not
> transparent.** Blender writes BLEND for any material with an RGBA image, used
> or not. The alpha of the packed palette is 255 everywhere. That is harmless
> on a prop, but not on the ground. A transparent floor is what every entity,
> prop, and marker in the pane sorts against. The two tile keys carry `opaque`
> in `ModelRegistry.PRESENTATION`, and `test_map_terrain` asserts that every
> terrain key does.

> **The retired browser pane had no terrain layer.** Thus, there was nothing to
> keep in step with `blackout_models.js` there. The parity rule above applied
> to a model that the two panes drew, and neither pane drew a tile that the
> other did not. The served manifest still names the tile keys in every case.

## The entity pool holds one entry per id

Nothing in the wire protocol promises that the server announces an entity one
time, and nothing can:

- `room_players` is a whole list, sent on arrival and on resync.
- `room_add_player` is a delta.
- The server computes `room_players_delta` against its snapshot of what this
  client holds.

An entity that arrived by one route can legitimately come again by another. For
example, `room_add_player` announces an NPC that respawns on your tile. Then the
`added` half of the next delta names it again, because the server took that
snapshot before the NPC existed.

`EntityPool` appended both times, so it drew the thing two times, in two slots
of the ring of the tile. That bug had a long tail. `remove` took only the first
match, so when the server deleted the entity, the second copy stayed there
permanently, and a player could still click it. A tile showed two corpses after
someone butchered one, and a click on the survivor sent a command about an
object that no longer existed.

The fix is an INVARIANT, not a rule about who may send what: at most one entry
for each id, whatever arrives. A later announcement REPLACES an earlier one,
because the later one is fresher. A re-sent entity can move, take damage, or
gain an action between the two sends. `remove` drops every copy, not only the
first. Together, these rules also make a resync idempotent, and idempotence is
the property that resync exists for.

## An entity may carry text, and it is not a sign's field

`serialize_entity` sends an optional `label` and `label_kind` beside the
`asset`/`family` pair. A signpost is the first thing to use them, and on
purpose not the last. A nameplate, a shop's name, and a builder's note over a
broken tile are the same fact about different entities. Thus, the pool draws
floating text in one place and gets every future case with no edit here.

`EntityPool._attach_label` hangs a `Label3D` from the node when the field is
present. When the field is absent, it returns immediately. Nearly every entity
in the world has no label, and for that reason the server omits the two fields
and does not send them empty.

Three things about it are load-bearing:

- **The pool attaches it AFTER `_rest_offset`.** The two read the node's
  bounds. A label attached first counts as part of the mesh, and it lifts its
  entity off the ground by the height of its own text. Nothing else would show
  the bug: the sign still draws, still reads, and simply floats.
- **The pool divides the entity scale back out.** A child inherits
  `ENTITY_SCALE`, so a label left alone draws at half size, and smaller again
  on the day that someone tunes that constant. The size of text is a
  readability decision, not a function of the size of the thing under it.
- **The color table belongs to the client, and needs no guard test.** The
  server owns which kinds exist. `LABEL_KIND_COLORS` owns what they look like.
  Its keys are generated constants, so a kind renamed on the server is a parse
  error, not a row that colors nothing. `FamilyShapes.MODELS` makes the same
  argument for a check of only its values. A kind that this client does not
  know falls to `COLOR_LABEL_FALLBACK` and still reads.

The cap belongs to the server: 64 characters over 3 lines, enforced in
`systems/interface/statefeed/labels.py`. The reason is that `label` rides the
biggest payload that the statefeed sends.

## Three kinds of words, three colours

`label_kind` arrives beside every `label`, and the client's `LABEL_KIND_COLORS`
turns it into a color. The three kinds that the server names today are not
decoration:

| kind | who wrote it | drawn |
|---|---|---|
| `sign` | a map module | warm paper |
| `marker` | whoever is building the game | synthetic magenta |
| `graffiti` | a player, with a spray can | aerosol green |

A player must tell the second row from the first, and the third row from the
other two. If a builder's note looked like signage, the first player who walked
past it would read it as worldbuilding. A scrawl that reads `BANK: EAST` is a
lie that a signpost could not tell. If two of these kinds draw in the same
color, that is a bug, and the pairwise check in `test_entity_pool.gd` exists to
catch it.

## Right click asks; left click still acts

One thing in the world can be several things to you at the same time. You can
butcher a mutant raider corpse where it lies, or you can take it with you. A
left click can only ever mean one of those actions.

`serialize_entity` sends the two: `interact` is the primary verb, and `actions`
is the whole list, `{command, label}` for each row. **`actions` is present only
when there is more than one action.** Otherwise, it would be a second copy of a
string already on the row, one for each entity, on `room_players`, the largest
payload that the statefeed sends. Thus, the single-verb fallback in
`WorldView.options_for()` is the COMMON path, not a legacy one.

A left click sends `interact`, exactly as before. A right click opens
`ChooseOption`, modeled on the OSRS box of the same name: the header, one row
for each option in the server's order, and `Cancel` last. A right click on bare
ground offers the tile's own action instead.

> **The camera moved to the middle button to make room.** Until 09/10/2026,
> `OrbitCamera` turned on a right-drag. If "turn the camera" and "ask what this
> is" share one button, nothing makes it feel right. A menu that opens on the
> press appears at the start of every turn. A menu that opens on the release
> appears at the end of every turn, unless a pixel threshold separates a click
> from a drag. A threshold is a number that is wrong for somebody.
>
> Orbit is now a MIDDLE-drag. The menu opens on the right PRESS, with no
> arbitration at all. `test_choose_option` reads `orbit_camera.gd` to assert
> that the right button stays free.

**There is still no verb table in this client.** The command of every row is a
string that the server composed and that this pane sends verbatim. The WORDING
of every row is the `label` sent beside it. The server capitalizes it, exactly
as `INVENTORY_ACTION_EQUIP` is `("Equip", "equip {slot}")`, so the two menus on
this screen cannot spell their rows differently. The client decides only the
JOINING: `"Butcher"` plus the entity's own name makes `Butcher Mutant Raider
corpse`. The label never names the target, because the row already knows it,
and a third copy of that string would count against the payload ceiling.

That division is why a corpse that gets a Brain Farming yield gets a row here
with no edit in either file. `world_view.gd` documents what the *other*
arrangement cost the two clients that tried it.

> **The box is a sibling of the world pane, not a child of the `Node3D`.** It
> lives in `WorldPane` beside `Minimap` and `LoadingVeil`. Thus, the 3D scene
> stays 3D, and the menu is a plain `Control` that `test_choose_option` drives
> with no camera, no pool, and no connection. `WorldView` raises
> `options_requested`, and `console.gd` connects it. The pane asks the question,
> and something else draws the answer.

> **While it is open, the menu owns the clicks of the pane.** `ChooseOption` is
> a full-rect transparent `Control` with the box inside it. That backdrop is the
> whole reason that a player can close the menu at all. Under it sits a
> `SubViewportContainer`, which forwards every mouse event from the GUI into the
> 3D pane. Thus, a menu that covered only its own rows never saw the click that
> should close it. Until 09/11/2026, a right click left a box over the world for
> good, and the click that should have closed it *walked the player instead*.
>
> The menu reads the mouse in `_gui_input`, where the GUI picks the backdrop.
> `_unhandled_input` keeps only Escape, which the GUI does not pick by position.
> A headless run has no GUI picking at all, and that is exactly how this bug
> shipped. Thus, `test_choose_option` asserts the structure and the source. It
> does not push a click and believe the result.

**A multi-yield node lists its cuts.** A right click on a mutant raider corpse
first offers `Butcher Mutant Raider corpse`: the best cut that your level
allows, which is also what a left click sends. Then it offers one row for each
cut: `Butcher chuck from Mutant Raider corpse`, `Butcher filet from …`.
`gathering_verbs` on the server builds the rows from `GATHERABLE_REGISTRY`.
Each row sends `butcher <node> = <cut>`, a line that a telnet player could type.
Nothing here knows that a corpse has cuts.

## Something on a far tile is walked to, then acted on

The statefeed names entities across a radius of tiles, so the pole that you
click is often not on your tile. Sent verbatim, `cut rusty pole` could only
fail. The verb of a node lives in the node's own cmdset, and `attack` and `get`
search the tile where you stand.

So `WorldView.approach_command()` wraps any command aimed at an entity on
another tile of your island in the server's `ENTITY_APPROACH_TEMPLATE`:
`goto (4,7) then cut rusty pole`. The server's `goto` walks the route on the
tick. It types the follow-up for you **only if the walk ends on the tile that
it started towards**. An interrupt node, a new click elsewhere, or a manual
detour that strands you drops the follow-up. A left click and every Choose
Option row go through the same wrap. A wrapped row keeps its verb as its label,
so the menu does not read "Goto" on every line.

- **The template is generated, not typed.** The separator has one owner in
  `statefeed/constants.py`, and `test_movement_cmds` parses the template back
  into its two halves.
- **It is not a field on the entity row.** The tile where you stand changes
  every step and the row does not, so a command stored on each entity would be
  stale after one move. The server owns the spelling. This pane owns the two
  tiles.
- **The pane sends a command for an entity on another island verbatim.**
  `goto (X,Y)` reads its numbers on the map where you are, and there the same
  numbers name a different tile.
- **The walk does not chase a moving NPC.** The walk goes to where the NPC
  stood at the click. If the NPC left, the follow-up says so, as the typed
  command would.

## The inventory draws in 3D without giving up drag and drop

The retired webclient gave the inventory a whole second three.js scene, camera,
and renderer, and hit-tested meshes to find what the player clicked. Here, the
cells stay `Control`s. Thus, Godot's own drag and drop keeps its function, and
that is the single largest thing that the engine gives this screen. `ItemStage`
supplies each cell only a picture.

**One viewport, not one for each cell.** The obvious build is a `SubViewport`
for each cell. With 32 carried slots and a dozen worn frames, that is about
forty render targets for forty thumbnails a centimeter across. Instead, the
stage puts every item on a grid in one 3D scene, under one orthographic camera.
Each cell shows its own rectangle of the result through an `AtlasTexture`. The
result is one target, one camera, and one pass, and the slow spin costs the
same for one item on screen or forty.

The view addresses cells by INDEX. It allocates them (carried first, then
worn), and where an index sits in the 3D grid is the business of
`item_stage.gd` alone. If two cells claimed one rectangle, they would quietly
draw one object in two slots. For that reason, a test asserts that every cell
owns a different region.

The stage updates `WHEN_VISIBLE`, so text-only mode really does stop paying for
it.

> **`own_world_3d` must be true, and it defaults to false.** A SubViewport left
> at the default SHARES the `World3D` of its parent. Thus, the item meshes land
> in the same 3D world as the game: forty swords and rocks in a neat grid that
> floats in the sky over the map. Also, the stage's `WorldEnvironment` paints
> the game's sky black. The two bugs happened on the first run. Nothing else
> about the viewport hints at it, so `test_inventory_view` asserts that the two
> worlds differ and does not trust a comment.

## Three screens cover the way in, and they hand off in order

A login is not an arrival. Until 08/29/2026, the client behaved as if it were.

| Screen | Covers | Ends when |
|---|---|---|
| Godot's boot splash | the ENGINE loading | the first frame is drawn |
| [LoginView] | no character yet | `char_vitals` lands — a body exists |
| [LoadingVeil] | a body, but no world yet | the map is whole and the art has gone quiet |

The third screen was missing. `LoginView` closes itself the moment vitals
arrive. The server sends vitals only for a PUPPETED character, so vitals are the
honest signal that a body exists. But a body is not a world. At that moment,
`blackout_map` can still come in chunks, `room_info` might not yet name the tile
where you stand, and the client holds no `.glb` yet. For one to three seconds,
the player saw a pane that was empty, then half-built, then right. **Every
click in that time was a real command about a world that the player could not
see.**

Godot's own splash cannot cover this, because it is gone before the socket
opens.

### Four facts, and the phase is whichever is missing first

	a body      char_vitals landed          CharState.has_vitals
	a place     room_info named a map       WorldState.current_z
	a map       every chunk of it arrived   Level.is_complete()
	the art     nothing fetched, unwarmed   MeshResolver.in_flight_count()
				or awaiting the manifest

Today, they do complete in that order. Nothing in `SessionReadiness` assumes
it. The code tests each fact independently. Thus, if a server sends them in a
different order, the veil reports the truth, not a stale label.
`test_session_readiness` asserts exactly that, with a complete map that arrives
before the room that names it.

> **An empty in-flight set is not a finished one.** The client fetches models
> lazily, when something draws them, so the set legitimately empties between
> batches. The map completes, the terrain layer asks for its tiles, and a moment
> later the entity layer asks for the NPCs on those tiles. If the veil lifted on
> the first zero, it would show a room with nobody in it. `SETTLE_SECONDS` is
> how long the quiet must hold, and it is the single most load-bearing constant
> here.
>
> Since 09/13/2026, the veil also starts a prefetch of every model (see "Where
> meshes come from"), and the count covers all of it:
>
> - Fetches in the air
> - Models that `ShaderWarmer` did not draw yet
> - The manifest itself, while it did not land yet.
>
> Without the last item, a veil raised before the manifest arrived would read
> zero and lift on a prefetch that did not start. On the web, this puts the
> compiles (13.5 s measured for today's art) under the veil, inside
> `CEILING_SECONDS`. Nobody measured whether the browser's own program cache
> shortens that time on a second visit.

**The rule is static and takes every input as an argument.** `phase_for()` is
the whole decision, and a test can call it with no socket, no timer, and no
frame. `ReconnectPolicy` makes the same split. The node around it is only a
stopwatch and four reads.

> **It POLLS, and that is not laziness.** Three of the four facts announce
> themselves. The fourth does not. A model that goes INTO flight emits nothing,
> because a draw calls `ModelLoader.request`, and a signal there would chatter
> on every entity rebuild. A readiness model bound only to the existing signals
> learns when art finished, but never when more art started. That is precisely
> the case that it must not miss, because that case is what a premature "ready"
> looks like.
>
> So the node reads all four facts on a tick, and the tick runs only while the
> veil is up.

### It covers the world pane, not the window

This is the main design decision, and the reason that it is not the
full-screen loading screen that it sounds like.

A full-window veil would hide the game log, which is the one thing that IS
working. The greeting, the MOTD, and any error that explains why the rest is
slow all land there. If the veil covered the log, an informative wait would
become a blank one, and a player who could already play the text game would
lose it.

What the veil gives is **the click**. The tile grid and the minimap both send
real commands, and both live under `%WorldPane`. A `PanelContainer` that fills
that pane with the default `MOUSE_FILTER_STOP` eats the misclick. The input, the
log, and its tabs stay live all the time.

If you hide the 3D pane (Options → 3D), the veil hides with it, correctly and
with no code. A player in text-only mode waits for nothing.

> **Sibling order is draw order.** The veil must be the LAST child of
> `%WorldPane`. If it is authored anywhere earlier, it still exists, still
> resolves by unique name, and still reports the right phase. But it draws under
> an opaque `SubViewportContainer`, so nobody ever sees the screen that it
> should show. `smoke_console` asserts the ordering, because nothing else can.

### Nobody is ever trapped behind it

There are three independent exits, because every other way out of this screen
needs something to arrive:

- **The gate opens.** This is the normal case, and it takes less than a second
  on a warm cache.
- **`CEILING_SECONDS` (30) expires.** This is a ceiling, not a timeout. Nothing
  is canceled, and nothing reports a failure. The code checks it BEFORE the
  missing-fact branches. Otherwise, a session that never gets a map would
  report `MAPPING` forever, and the code would never reach the ceiling.
- **The player clicks "Enter anyway."** The button appears after
  `SKIP_OFFER_SECONDS` (6), late enough that a normal login never sees it. The
  choice is one-way within a session: a player who chose to go in early does
  not get the question again on the next tile. A dropped socket clears the
  choice, because that is a new session.

### The mark

`ui/blackout_mark.png` is the sigil. It is the veil's centerpiece, the window
icon (`config/icon`), and the boot splash (`boot_splash/image`, over
`boot_splash/bg_color` #07080b, the same `--color-void` that the website uses).
One file serves all three.

The reasons live here, not in `project.godot`, for the reason that the top of
this file gives: one opening of the editor rewrites that file and strips every
comment in it.

## Reconnecting

The socket redials itself on a drop: after one second, then two, four, and
eight, with a cap at thirty, forever. The client never redials a close that it
*asked for*, and the `requested` flag on `Evennia.closed` is for that case.

**A reconnect does not restore the session.** A websocket close ends the Evennia
Session. Thus, the new socket lands on the connection screen, and the player
logs in again. Evennia's own browser webclient always did the same.
`CharState.reset()` makes that coherent. It clears the character, so the HUD
stops showing 87/100 beside a dead socket, and the login form comes back. The
visibility of the form is a *function* of whether a body exists, not a one-way
dismissal, and that keeps "am I puppeted" to a single owner.

## Running

Start the game server first. The client connects on load, and if nothing
listens, it reports the failure in the feed pane.

**The BUILD decides which server the client reaches, not a constant that
somebody must remember to flip.** `ServerEndpoint` reads `OS.is_debug_build()`.
The editor and a debug export reach `ws://127.0.0.1:4008`. A release export
reaches `wss://game.playblackout.io/godot`. A test confirmed this: a wrapper
around `WebSocket` in a real release web export showed which URL it dialed.

To point either build somewhere else, use `--server=<url>` on the command line,
or `?server=<url>` in the page's query string on the web. The client accepts
only `ws://` and `wss://`. An override that names `http://` would fail in a way
that looks exactly like a server that is down.

```bash
cd blackout && ../evenv/Scripts/evennia.exe start
```

Then open `godot/` in Godot 4.7 and press F5, or run it headless. Godot is not
on PATH on this machine. The 4.7.1 build lives in an extracted folder that has
the name `...exe` itself, so the binary path repeats:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --path godot
```

Log in through the form at the top of the text column, or type the same thing
into the input field. The two send the identical line:

```
connect <name> <password>
```

The form exists for two reasons. It can mask the password field, which a
shared command line cannot do, and it has the **Paste** button on web builds.
See rule 6 below.

The client does **not** subscribe when the socket opens. That is a race that it
loses whenever the Server is still starting. It waits until the server
announces an empty subscription set at `ServerSession.at_sync`, and then it
answers. The same message lets it recover from an `evennia reload`, which wipes
the Session ndb where the subscriptions live but does not drop the socket.

`Character.at_post_puppet` pushes the world snapshot when you puppet a
character.

To see the recovery for yourself, run `evennia reload` while the client is
connected. The feed pane logs `server has no subscription for us;
subscribing`, and then a fresh `subscribed: ...`.

## Tests

All forty-one tests are headless and exit non-zero on failure. Thirty-eight
need nothing running. Three of the four `smoke_*` scenes need an Evennia, and
none needs an account. `smoke_console` is the exception: it builds
`console.tscn` for real and needs nothing, because the test expects its socket
to fail.

Two of them guard the SCENE, not a model, and that is the gap that every other
test leaves:

| | Catches |
|---|---|
| `smoke_console` | A `%UniqueName` that no longer resolves, a node whose type changed, a theme that came unattached. Every other test builds its subject in code, so a scene edit is invisible to all of them |
| `test_theme` | A `theme_type_variation` a script names and `ui/blackout_theme.tres` does not declare. The control silently falls back to the default style, which reads as a styling mistake rather than a typo |

> **After you add a `class_name`, run `--headless --path godot --import` one
> time before you run anything headless.** Global class names live in
> `.godot/global_script_class_cache.cfg`, which an editor scan rebuilds and git
> ignores. A plain `--headless` run does not rebuild it. Thus, a brand-new
> `class_name` fails as `Identifier "..." not declared in the current scope`.
> That reads like a typo, but it is not one. A fresh clone needs this step too.

`test_world_state.tscn` needs **nothing running**. Its payloads are hand-built
in the shape that Godot's JSON parser produces:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_world_state.tscn
```

`test_choose_option.tscn` needs nothing running. The payloads are hand-built in
the shape that `serialize_entity` produces, floats included. The menu is a
plain `Control`, driven with no camera and no pool:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_choose_option.tscn
```

It covers the two things that go silently wrong:

- Every row emits the server's string byte for byte, and `Cancel` emits
  nothing at all.
- `options_for` falls back to `interact` when `actions` is absent. That is
  nearly every entity in the world, because the server omits the list for the
  one-verb case.

`test_world_view.tscn` needs nothing running either. `yaw_towards` is static,
and every case is a pair of grid cells:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_world_view.tscn
```

`test_map_terrain.tscn` needs nothing running either. A table says which map
gets which surface, and the test measures the space of the terrain against a
hand-built model:

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
either. The view test asserts two things that a screenshot would not catch.
Every command that leaves the pane is one that the server named. Each of the
three detail modes asks for exactly what it shows.

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_skills_view.tscn
```

`test_xp_tracker_state.tscn` and `test_xp_hud_view.tscn` need nothing running
either. The tracker's clock is a Callable that the test moves by hand, so the
test measures an hour of XP per hour in milliseconds. The view test proves that
the HUD is hidden before an award, and that no control in it takes the mouse.

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_xp_hud_view.tscn
```

`test_combat_options_state.tscn` and `test_combat_options_view.tscn` need
nothing running either. The view test asserts that every command that leaves
the tab is the one that its row carried, and that a click alone never moves the
highlight:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_combat_options_view.tscn
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

`test_sound_cues.tscn` needs nothing running either. A headless run uses the
dummy audio driver, so the test plays every cue for real with no speaker
attached:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/test_sound_cues.tscn
```

`smoke_reconnect.tscn` needs a running Evennia but no account. It proves the
one thing that `test_reconnect_policy` cannot: `Evennia.open()` is callable a
second time. A `WebSocketPeer` at STATE_CLOSED is a used object, so the client
builds a fresh peer for each open. That change looks obviously correct, but
only a real server can confirm it.

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/smoke_reconnect.tscn
```

`smoke_handshake.tscn` needs a running Evennia but no account. The server
answers `blackout_subscribe` on an unauthenticated session:

```bash
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" --headless --path godot res://tests/smoke_handshake.tscn
```

## Skills left the character sheet

Until 08/28/2026, the roster was a **panel on the dossier**: one panel under
`systems/interface/summary/panel_defs/`, in `char_summary` beside vitals,
holdings, and the rest. The Character tab drew it, because the tab draws every
panel that it gets, and `score` printed it as a wrapped run of
`Cutting 30  Brawn 12`.

It moved because nobody could build a grid from it without a break in the rule
that the dossier depends on. [SummaryState] **iterates panels and never names
one**. That is what lets a panel added on the server appear here with no client
edit. A skills screen would need to reach into that payload and read one key by
name. The first client to do that makes the contract a suggestion.

So the panel left. `score` no longer carries skills, `profile` no longer
carries them, and the roster ships on a channel of its own:

```
char_skills -> {skills: [...], categories: [...],
				total_level, total_xp, max_level, closest}
```

**Each row is complete**, and that decision shapes this pane. A row carries the
level, the XP curve, *and the whole unlock ladder*: every recipe, gathering
node, item, and ability that the skill opens, with the level that each needs.
The ladder is static (what a recipe requires does not depend on who asks), so
it could be a second request. But it ships in the snapshot, so a click on a
skill is **instant, with no round trip**, for a few kilobytes across the entire
roster.

`current_xp` / `needed_xp` are the progress into the current level and the
threshold of that level. `total_xp` is cumulative. The two ship under names
that say which they are, because a derivation of one from the other is exactly
the mistake that once rendered a `1154 / 152` bar on the server's own screen.

### The grid is grouped by the server's order, coloured by the client's

Rows arrive sorted by `(category, name)`, and `categories` arrives beside them.
Thus, the bands and their contents need no ordering table here, and the text
screens and this grid agree with no statement from either. The client owns
three columns, a bar for each cell, and `world/skill_palette.gd`.

That palette is **guarded, not generated**, on the same asymmetry as
`ROOM_KIND_COLORS`. A category named there that no skill declares is a bug, and
`test_client_constants.py` fails on it. A category with no entry draws the
fallback and costs nothing. The guard caught its own first dead key on the run
that introduced it: `General`, which is `BaseSkill`'s default and which no
shipped skill uses.

### Where a clicked skill's answer goes is a setting

There are three modes, in Options. The default is both:

| Mode | Sends | Shows |
|---|---|---|
| **Pane and log** | `skills <key>` | The sheet in the pane, and the server's text sheet in the log |
| **In the pane** | nothing | The sheet in the pane |
| **In the game log** | `skills <key>` | The server's text sheet in the log |

**`In the pane` sends nothing, and it must.** The client cannot ask the server
about a skill quietly. The command that renders the sheet renders it *into the
log*, and that is what the mode exists to prevent. So the setting is not "where
is the answer shown" but "which answer does the client ask for", and each mode
asks for exactly what it will show. The cost is that pane mode draws from the
last snapshot, and that is why the rows are complete.

The two text answers come from one renderer,
`systems/gameplay/progression/skills/detail.py`. Until this change, the
renderer was inline in the EvMenu, so a player could see what a skill unlocked
only from inside a menu. Three readers now share it: the menu node,
`skills <skill>`, and this channel. The sheet renders *from* the structured
form, not from a second set of handler reads. Thus, the grid and the text
cannot describe a skill differently.

### The open sheet survives a rebuild

`char_skills` republishes whenever XP or a level moves (at most one time each
tick), on resync, and whenever the player types `skills`. This pane rebuilds
wholesale on each one, so the selected key outlives the rebuild. Without that,
the sheet would close itself every time the skill on screen earned XP, and that
is exactly when a player looks at it. The kept key also makes the sheet update
live.

One consequence: this pane frees its children with `queue_free`, where
[InventoryView] and [QuestsView] use `free`. Those views rebuild from a
*model's* signal, and nothing that they destroy is mid-emit. This pane also
rebuilds from a *cell's* signal, because a click on a skill destroys the cell
that the player clicked. A `free` there tears down an object while its signal
still emits.

## The Combat tab lights what the server says, not what was clicked

The tab is modeled on OSRS's Combat Options: the weapon and combat level at the
top, and one button for each style under them. Auto-retaliate and the special
attack bar are absent, because Blackout has neither.

```
char_combat -> {weapon_name, armed, combat_level,
				attack_speed_ticks, attack_speed_seconds, styles: [...]}
```

Each style row carries its boosts and XP skills as data, and the whole
`combatoptions <style>` line that picks it.
`systems/gameplay/combat/style_options.py` builds the two, and the
`combatoptions` EvMenu also renders from that module. Thus, the tab and the
menu cannot describe a style differently. `detail.py` makes the same
arrangement for skills.

**A click sends, and changes nothing else.** The button goes straight back to
what the last snapshot said. The highlight moves only when `set_combat_style`
republishes `char_combat`. An optimistic highlight could show a style that the
server refused (for example, if the player unequipped the weapon between the
click and the command), and nothing would correct it. A click on the style that
is already active sends nothing, because the only answer is "already using it".

**Bare hands show one disabled button.** The unarmed table declares four
styles. But there is no object to store a choice on, and combat always resolves
`punch`, so the server sends that row with an empty command. Three more buttons
would change nothing.

`attack_speed_seconds` ships beside the ticks, because the tick length belongs
to the server and is not exported. A division by a copy of 0.6 here would be a
second owner of that fact.

The channel republishes on a style switch, on any equipment change (which
covers a mid-fight `wield`), on a level change (combat level), on the bare
`combatoptions` command, and on resync.

## The quest log is numbers, not sentences

`char_quests` sends each objective as `{key, description, current, required,
counted, done}`, not as the rendered `[x] Rats culled 3/5` that the telnet
screen prints. Thus, this pane can draw a progress bar, gray out what is done,
and show the two kinds of objective differently. A client that got the sentence
could only print it.

`required` is **1 for a one-shot objective**, not absent, so the bar needs no
branch for the two kinds. `counted` decides whether the reading beside it is a
fraction or a tickbox.

`systems/interface/statefeed/quests.py` builds the payload entirely through the
public read API of `QuestHandler`. Nothing outside that handler reads
`db.active_quests`, and this pane would have been the fourth module to try.

## The minimap is drawn from the feed, not from the text map

`blackout_map` already carries every node with its `room_kind`, and every link.
`room_info` carries the tile where you stand and what each near tile affords.
[WorldState] reassembles the two, and **the console owns that model**. Until
08/28/2026, the 3D pane built its own. If two panes drew one chunked payload,
the client would reassemble it two times. On a resync, the two reassemblies
would briefly disagree about which tiles exist.

The minimap also binds to the console's **resolver**, for one question only:
does the map that it draws have ground art? The answer decides which of the two
color palettes it uses. See "The ground is art on top of the slab" above. In
short, the pane under a minimap must not color the same map in a different
way.

So the minimap is a second VIEW. It gets three things that the ASCII print in a
pane would not give:

- It scales with `content_scale_factor`, and a monospace block cannot.
- It is clickable, through the same `WorldState.tile_action` that the 3D pane
  uses, so click-to-walk works with **no new server contract**.
- The server can send no ASCII map to this client at all.

That last item is the point. `XYZRoom.return_appearance` msg'd the map on every
`look`, and `look` runs on every move to a new tile. Thus, on a 95-node map,
the dominant content of the text pane was a picture that the client already
drew beside it. `GridTile._wants_ascii_map` now answers `False` for a Godot
session, and every other protocol stays the same.

**The player decides, with `automap`.** The answer based on the client is only
a DEFAULT:

- `automap on` / `automap off` overrides it permanently.
- `automap` reports the current setting, and whether the player chose it or
  inherited it.
- `help automap` explains it, and that is how a telnet player finds it at all.

The Options tab carries the same three as buttons. A player of this client
never saw the text map, and without the buttons would have no reason to think
that it exists. They are BUTTONS, not a checkbox, on purpose. The setting
belongs to the server, so a checkbox here would claim to know a state that only
the server can report.

The same row style carries **`toggle craft confirm`** as a single Toggle
button. The server offers only a toggle for it (no on, no off, no query), so
the pane offers exactly that. The log's "Crafting confirmation turned ON/OFF."
is the answer. The command lives on the character
(`commands/crafting_cmds.py`), not on the workbench, so the button works on any
tile.

## The log is tabbed, and the server never names a tab

Every line of game text can carry a routing tag in its outputfunc kwargs.
`caller.msg((line, {"type": "combat"}))` on the server arrives here as
`{"type": "combat"}`. The vocabulary is `MESSAGE_TYPES` in
`blackout/systems/interface/statefeed/constants.py`. The export generates it
into `autoload/blackout_constants.gd` as `MSG_*`, like every other name that
the server owns.

**The server says what a line IS. The client says which tab shows it.** No
server fact names a tab, and none must. `ChatTabs.DEFAULT_TABS` is the whole
table, and a new tab is one row in it.

Three consequences follow, and each looks like a bug until you know it:

- **A type that no tab claims is not lost.** It appears in `All`, the tab that
  the client opens on. A message type added on the server tomorrow shows there
  with no edit in this project. An item with no art gets the same degradation
  from the mesh ladder.
- **An untagged line is normal.** Evennia's EvMenu nodes, `page`, and much of
  its error prose carry no tag at all. `ChatTabs.tabs_for("")` reads that as
  `general` and does not drop it. The client applies that default HERE, not on
  the server. Thus, "nobody tagged this yet" stays distinguishable from "this
  line is really general".
- **Half the tags are Evennia's own.** The engine, not Blackout, tags `say`,
  `whisper`, `pose`, `look`, `help`, and `examine`. The vocabulary copies the
  engine's spelling and does not invent a parallel one. For that reason, the
  tag is `whisper`, not `tell`.

**One RichTextLabel for each tab, and the client appends to it.** Godot's own
docs say that a console-sized log stutters when code reassigns `text`, because
that reparses every line of BBCode. The docs prescribe `append_text` plus
`threaded`. A design that rendered the buffer again on a tab switch would do
the expensive thing on the most frequent interaction. It would also lose the
scroll position of each tab, and that is the difference between a tab strip and
an annoying one. `remove_paragraph(0)` caps each log at `ChatView.MAX_LINES`,
because there is no max-lines property.

`Ctrl+F` follows the visible tab. The console rebinds the find bar on
`active_log_changed`. A find across tabs would scroll a tab that the player
cannot see, and count matches in logs that the player does not read.

## XP drops ride an event; the session is the client's

The HUD sits just left of the minimap, right-aligned against it, where OSRS
keeps its XP counter. It draws only after the player earns something. It shows
these parts:

- A strip that reads `session 12,345 xp   3,420 xp/hr`
- A segmented bar for the skill just trained (`strike 42 → 43 · 1,120 to go`)
- A `level up // strike 43` line that fades
- XP per hour for each skill, when Options asks for it.

Each award rises into the bottom of that column as one row, `+25 Butchery
+5 Cutting`, colored by skill category from [SkillPalette].

**Every award arrives on `blackout_xp`, one message for each action.**
`xp_awards.grant_xp` sends it. That function is the one seam that every
player-facing award on the server passes through. The message carries the
progress of each skill, read after the award landed. It does not come from
`char_skills`, because the server marks that roster stale on an award and
builds it one time after the last award. Two awards on one tick would come here
as one blurred change, a reactor turn late.

`blackout_xp` is an event channel like `blackout_combat`, and for the same
reason, nothing coalesces it.

**The session is the client's reading, not a server fact.** `XpTrackerState`
starts a clock at the first award and ends it at `reset()`: a dropped socket,
or Options → Reset session. The client sends totals and rates nowhere, the same
way that RuneLite's tracker is a plugin and not a game feature. A rate reads
`--` for its first 30 seconds. One swing two seconds into a fight is tens of
thousands an hour, and a player would quote that number.

**The level-up line hangs off `SkillsState.levelled`**, the signal that the
jingle already uses. It does not compare levels on the award. "A level rose"
has one owner.

**Nothing in the HUD takes a click.** It sits over the tiles, and
`test_xp_hud_view` walks every control in it to prove that the mouse passes
through.

## Sound is the client's, and a cue hangs off a fact

`world/sound_cues.gd` is the whole table: a cue NAME (`SoundCues.LEVEL_UP`)
mapped to a clip under `audio/sfx/`. Callers ask for the moment, never the
file, so a clip swap is one line, and no caller moves. The server names no
sound and must not start. Which clip a level-up plays is a look, on the same
side of the line as a mesh or a color.

**A cue hangs off state, never off a line of prose.** The level-up cue is
`SkillsState.levelled`, which compares each `char_skills` roster with the one
before it. The server does print `[LEVEL_UP] ...` at the same moment. A match
on that string would work until its first copy edit, and then stop with no
error. The comparison needs no server change, because `char_skills`
republishes only on a level change, a resync, or the `skills` command, and the
last two compare equal. A redial stays quiet, because `SkillsState.reset`
empties the roster that the next one is compared against.

A cue with no state behind it, such as a miss or a failed craft, needs a
structured server event, not a pattern over the log. That event is a constant
in `statefeed/constants.py`, regenerated into `blackout_constants.gd`.

**Every clip plays on the `SFX` bus** declared in `default_bus_layout.tres`.
An audio player that names a bus that does not exist plays on Master with no
warning. For that reason, `test_sound_cues` checks the bus by name.

**The Options slider sets that bus, and nothing else does.** It writes
`ClientSettings.sfx_volume`, LINEAR from 0.0 to 1.0, because a slider in
decibels crowds every audible change into its last quarter. The console's
`_apply_settings` gives the value to `SoundCues.apply_volume`, the one place
that knows that a decibel exists. Zero mutes the bus, and the code does not
write `linear_to_db(0.0)`, which is negative infinity. The ceiling is 1.0, the
level that the clips were mixed at. More volume is the job of the operating
system's slider, and it is not a reason to clip.

**Browsers refuse audio until the player clicks or types in the page.** A login
does both, so anything cued from a game event plays. A sound on the login
screen itself can fail to play.

### Only the clips in use live in this project

Source packs stay OUTSIDE the repo, for two reasons. The Ovani Sound FX Starter
Pack is at `C:\Users\NickR\Games\Projects\Godot\Assets\`.

- **The license.** Ovani permits use in a game and asks no credit, but forbids
  distribution of the content on its own. A pack committed here is a pack
  published on GitHub. For the same reason, the pack is not under
  `blackout/assets/` beside the model sources: git tracks that directory.
- **The export.** `export_presets.cfg` exports `all_resources`, so every audio
  file that Godot imported ships in the web build. The whole pack is 215 MB,
  against a ~38 MiB client. If someone unzipped it into `godot/`, the next
  export would include it.

To add a sound:

1. Copy the one clip to `audio/sfx/<cue>.wav`.
2. Unless the clip is positional, tick Force → Mono in the Import dock.
3. Add a row to `audio/CREDITS.md`.
4. Add one constant and one `_STREAMS` row in `sound_cues.gd`.

## Layout

| File | Owns |
|---|---|
| `autoload/evennia.gd` | The socket. The only place that knows the `[name, args, kwargs]` wire format. |
| `scenes/console.tscn` `.gd` | The shell: output, input, and the subscription handshake. |
| `scenes/world.tscn` | The 3D scene: environment, light, islands, marker, camera rig. |
| `world/world_state.gd` | The world model. Chunk reassembly and the float boundary. |
| `world/char_state.gd` | YOUR model: entity id, hp, in_combat, skill levels. |
| `world/model_registry.gd` | Which assets have art (fetched) and how each is oriented (not). |
| `world/meshes/mesh_palette.gd` | Colors and finishes. One owner for both. |
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
| `world/reconnect_policy.gd` | How long to wait before redialing. Pure schedule, no clock. |
| `world/quest_state.gd` | Your quest log. Knows no quest key and must not learn any. |
| `scenes/quests/quests_view.gd` | The quest tab: a bar per objective, drawn from numbers rather than prose. |
| `world/xp_tracker_state.gd` | This session's XP awards, totals and rates. The clock is injectable; the session is the client's own. |
| `scenes/xp/xp_hud_view.gd` | XP drops, the session strip and the progress bar over the world. Takes no click. |
| `world/combat_options_state.gd` | Your weapon and its styles. Names no style, and nothing in it is set by a click. |
| `scenes/combat/combat_options_view.gd` | The Combat tab: a button per style, lit by the snapshot rather than the click. |
| `world/map_palette.gd` | Room-kind colors, island order, and which map is surfaced with which terrain. Read by BOTH map panes; guarded from Python by path. |
| `scenes/minimap/minimap_view.gd` | The map drawn small over the world pane. Clickable, and from the feed rather than the ASCII print. |
| `scenes/panel/panel_view.gd` | The control-panel tab strip. Tabs are addressed by title, never by index. |
| `scenes/vitals/vitals_bars.gd` | Your resources as bars. One control, two homes. |
| `world/chat_tabs.gd` | Which tab a line belongs in, and which tabs have unread lines. Holds no text. |
| `scenes/chat/chat_view.gd` | The tab strip and one RichTextLabel per tab. Appends; never re-renders. |
| `world/client_settings.gd` | Font size, UI scale, sound effects volume, which panes are shown and where the dividers sit, via ConfigFile under `user://`. |
| `ui/blackout_theme.tres` | Every margin, separation, font size and label color. Assigned once on the console root and inherited. |
| `world/server_endpoint.gd` | Which server this build talks to. Debug reaches localhost, release reaches production. |
| `world/scrollback_find.gd` | Which matches exist and which one you are on. Pure. |
| `scenes/find/find_bar.gd` | Ctrl+F over the log. Scrolls via `get_character_line`. |
| `scenes/help/help_view.gd` | What the CLIENT does. The game's own `help` covers the rest. |
| `scenes/options/options_view.gd` | The sliders and the pane toggles. Writes through the settings object, applies nothing. |
| `scenes/hud.tscn` `.gd` | Draws char_state above the text pane. Presentation only. |
| `world/world_view.gd` | Drawing tiles, links, islands and the marker. Owns the browser-parity hash and colors. |
| `world/entity_pool.gd` | Everything the statefeed can see, each on its own tile. Hit flash and hover. |
| `world/orbit_camera.gd` | The `SpringArm3D` follow rig. |
| `world/sound_cues.gd` | Which clip each cue plays, on the SFX bus. The server names no sound. |
| `audio/sfx/`, `audio/CREDITS.md` | The clips in use, and where each came from. Source packs live outside the repo. |
| `default_bus_layout.tres` | The audio buses. Every cue plays on `SFX`. |

Rules that nobody needs to find again:

1. **Decode with `get_string_from_utf8()`.** The contrib's own README example
   uses `get_string_from_ascii()`, which mangles the box-drawing characters
   that the dossier and every section rule in the game use.
2. **Every number in a parsed payload is a float.** `JSON.parse_string` always
   returns `{"x": 3.0, "num": 19863.0}`. A dictionary keyed on that will not
   match a key written as `3`, and nothing raises. `WorldState` converts at the
   point of use. Do the same, and do not coerce whole payloads. Otherwise, the
   coercion would silently corrupt the first really fractional field that the
   server adds.
3. **The client acts only through `Evennia.command()`**, which sends the same
   `text` that a telnet player types. A click on a tile sends `north`, never a
   position. There is no privileged client channel, so every lock, cooldown,
   and permission still works, with nothing to audit again. The client also
   does not decide WHICH command: `serialize_entity` names the whole command
   in `interact`, and the pane forwards it. A click on another player does
   nothing, because the server sends an empty `interact` for a player. A player
   can recover from every other misclick, but not from combat opened on a
   person. The pane learns that from the server and does not know it itself.
4. **The output pane's monospace font is load-bearing**, not cosmetic. Godot's
   default theme font is proportional, and the game draws ASCII art
   constantly. **The font is bundled** (`ui/fonts/DejaVuSansMono.ttf`), never
   a `SystemFont`. A Web export has no OS fonts to ask. Thus, until
   09/13/2026, a `SystemFont` that listed Consolas resolved on desktop but fell
   back to the proportional default in the browser. The result was ragged
   EvMenu tables, and `→` drawn as a missing-glyph box. One face on every
   platform also keeps the two clients identical. `tests/test_theme.gd` fails
   on a `SystemFont` in the theme.
5. **The room-kind palette still matches the retired browser pane.** The two
   panes once ran side by side on the same character, so a difference meant a
   bug. For that reason, `MapPalette.stable_hash` reimplements the JS string
   hash of `blackout3d.js` and does not call Godot's. Also, the HSL-to-HSV
   conversion beside it is closed-form, not matched by eye.
   `tests/test_world_state.gd` still checks the two against test vectors
   computed directly from the JS.
6. **On the web, Ctrl+V into a LineEdit can fail to paste, and the failure is
   silent.** Godot's export listens for the DOM `paste` event. But its
   `clipboard_get` reads `navigator.clipboard.readText()`, the permission-gated
   path, and swallows a rejection in an empty `catch`. Thus, a refused read
   looks exactly like an empty clipboard. Without user activation, the two
   engines refuse that read. Firefox does not support the `clipboard-read`
   permission at all, so there is nothing to grant one time. The login form's
   **Paste button** is the floor: a click IS user activation, so the read that
   fails from a keystroke succeeds from a button. Desktop has no problem,
   because Ctrl+V is native there.
