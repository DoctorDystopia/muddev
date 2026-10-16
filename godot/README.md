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
`SUBSCRIBABLE_CHANNELS`.** The layout has a tabbed game log on the left and the
3D world on the right. The tabbed control panel hangs in a box over the bottom
right corner of the world, and vitals bars and a minimap sit over the world
too. The world pane draws these things:

- The tile grids of each map, and the links between them
- Room-kind colors, and real tile art on the maps that have any
- Your figure, which walks between tiles, and a mark on the tile the server
  has you on while it does
- The NPCs and items on each tile, which walk the same way
- A white flash on anything that you hit, and your aura ring
- A hitsplat over each figure that a swing reaches, with a larger amber one
  for a max hit.

The mesh ladder below draws everything on the tile. It uses a fetched model
where there is art, and the silhouette of the family where there is not.

| Input | Does |
|---|---|
| **Hover** | Lights whatever a click would take — the entity, else the tile |
| **Left-click a tile** | Walks there. Closes any open menu first — the server's menus stand aside for a walk, an exit or a click on a thing |
| **Left-click an entity** | Sends the entity's `interact` command, verbatim — `attack mutant raider`, `bank`, `craft`, `talk`, `cut`. On another tile, walks there first: `goto (4,7) then cut rusty pole` |
| **Left-click a player** | Nothing — an empty `interact`, which the server decides and this pane does not |
| **Drag an inventory cell** | Swaps two carried squares. The one command this client composes, because a drag knows two endpoints |
| **Left-click an inventory cell** | The server's first action on that row: `Equip` on a wearable, `Deposit` or `Sell` while a pop-up is open |
| **Right-click an inventory cell** | The item's own actions, as the server listed them |
| **Equipment tab** | The paper doll, in OSRS's Worn Equipment shape. A left click unequips, because that is the server's first action on a worn row |
| **Edit layout** in Options | Opens the layout editor. Drag a frame to move a HUD element, and drag a grip to size it. Click a frame to hide, fade or scale the element. Save and load layouts by name. `Done` or Esc closes it. Remembered |
| **Drag a pop-up grip** | Resizes the pop-up. It has a grip on each edge and each corner. Remembered |
| **Click a minimap cell** | Walks there. The same `tile_action` lookup the 3D pane makes |
| **Mouse wheel on the minimap**, or its `-` and `+` | Zooms the minimap. Remembered |
| **`Run` on the minimap**, or **R** in move mode | Turns run on or off. The button shows what the server says. Run moves two tiles each tick |
| **"Show the walk path on the maps" in Options** | Shows or hides the walk path on both maps. Remembered |
| **`Map` on the minimap** | Opens the world map. Drag to pan, wheel to zoom, `Up` and `Down` for the plane, Esc to close |
| **Combat tab** | Your weapon, combat level, attack speed, and a button per style — OSRS's Combat Options |
| **Click a style** | Sends the row's `combatoptions <style>`. The highlight moves when the server republishes, not on the click |
| **Character tab** | The sheet — whatever panels `char_summary` sent |
| **Skills tab** | The roster as a grid, banded by category, with a bar per skill |
| **Click a skill** | Its sheet: XP, progress and everything it unlocks. Where that lands is an Options setting |
| **Quests tab** | What you have taken, and how far through it you are |
| **Options tab** | Text size, interface scale, which panes are drawn, where skill detail goes, whether figures slide between tiles. Saved between runs. The Game half asks the server: the text map, and which parts of the room a step prints |
| **Up / Down in the input** | Walks the command history; a half-typed draft is kept |
| **Escape in the input** | Hands the keyboard to the map — see "Two modes" below |
| **WASDQEZC / hjklyubn** | Walk while held, while the map has the keyboard. One tile each tick, two with run on. W and D together walk northeast |
| **"WASD follows the camera" in Options** | W walks where the camera looks, not to the north. Off by default. Remembered |
| **Enter, in move mode** | Hands the keyboard back to the input |
| **Click a chat button** | The buttons sit under the input: All, Game, Combat, Local, Private, Channel. A click shows only the lines of that tab. A dot means that lines landed there while you were elsewhere |
| **Right-click a chat button** | "Set chat mode" for each mode whose lines the tab shows, and "Show in All". Both are remembered |
| **Click the chat mode** | The name in front of the input, `Nick [Public]:`. A menu of every mode. In a chat mode, the client adds the prefix of the mode to each typed line. A line that starts with `/` goes out as a command in every mode |
| **3D button** | Hides the 3D world. Persists. The inventory has its own toggle in Options — one switch for both meant giving up the bag to stop the diorama |
| **Drag the divider** | Resizes the log against the world, and it is remembered. Both offsets were a literal 300 in the scene until 08/28/2026 |
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

The hint follows login and focus, in `_refresh_input_hint`. Before login it is
the `connect` line. After login it names Escape while the player types, and it
names the movement keys while the map has the keyboard.

## A held key walks at the speed of a click

Since 09/29/2026 the server moves every step on the tick
(`blackout/systems/gameplay/movement/walk.py`). A held key and a click thus
move at one speed: one tile each tick, or two tiles with run on. The first
step waits for the next tick, as in OSRS.

A direction command is ONE tick of movement. A held key must thus reach the
server at least one time each tick. `HeldMovement` sends the direction when
the key goes down. The console sends it again every half tick while the key
stays down (`HELD_RESEND_TICKS`). The server makes a new walk from the current
tile on each command, so the sends never stack.

Three rules follow:

- **The client sends no "stop".** When the player lets go, the sends stop,
  and the walker moves at most one tick more. A tap is one tick of movement.
  A lost key-up event thus cannot make a walk that never ends.
- **A loss of focus forgets the held keys.** A key that goes up while the
  input has the keyboard never reaches `_unhandled_key_input`. The same is
  true for a window that loses focus. The console clears `HeldMovement` on
  both.
- **Two held keys make one direction.** `MovementKeys.combined` adds the steps
  of the held keys, and each axis keeps its sign. W and D walk northeast. Two
  keys that cancel (W and S) give the newest key.

**The keys can follow the camera.** With "WASD follows the camera" on in
Options, W walks where the camera looks. `MovementKeys.steered` turns the key
direction by `WorldView.camera_forward()`, and it snaps the result to the
nearest of the eight directions. The console reads the camera again on each
send, so a held key follows a turn of the camera within half a tick. The
server still gets a plain direction word. The box is off by default
(`ClientSettings.camera_relative_keys`), so W is north, as the website says.

The start angle of the camera (`YAW_START`, 0.40 rad) is 23 degrees west of
north. That is past the 22.5 degree line, so with the box on, W at the start
angle walks northwest.

**Run.** The `Run` button in the top-left corner of the minimap and the R key
send `RUN_TOGGLE_COMMAND`. The server sends `running` on `blackout_walk`, and
the button shows that value. A press puts the button back to the server value
until the feed answers. The button is not on the strip, which stays at three
buttons (Nick, 09/28/2026).

**A click on the next tile sends `goto (x,y)`,** not a direction word. With run
on, a direction word moves two tiles. A `goto` of one tile moves one tile.

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

**The look files come first, and the tables are the fallback** (ENG-0011,
steps L4 to L6, 10/13/2026). Three looks of the mesh ladder are data files
that the figure workbench writes:

| File | Holds | Reader | Fallback |
|---|---|---|---|
| `blackout/assets/figure/palette.json` | Each named color, each color role, and each finish | `FigurePalette` | `MeshPalette.COLORS` and `MeshPalette.FINISHES` |
| `world/look/families.json` | The parts of each family with no art, and the model of a family | `FamilyLooks`, through `FamilyShapes` | `FamilyShapes.SHAPES` and `MODELS` |
| `world/look/presentation.json` | The offset, the turn, and the scale of each served model | `ModelPresentation`, through `ModelRegistry` | `ModelRegistry.PRESENTATION` |

A key with no row draws as before the file existed. Thus, a missing file
breaks nothing, and new content never needs a client edit. The Python guard
in `test_client_constants.py` checks that each key names a server family or
a model record.

`MeshBuilder` draws each part with the active palette,
`FigurePalette.active`. The color of a part is a color role or a named
color. The `roles` table gives the role its named color, and the named
color gives its color and its finish. A part with no finish takes the
finish of its named color. The figure workbench puts the palette of its
store there, so a change on the Colors tab reaches each family shape at one
time. With no active palette, each name comes from `MeshPalette`. The game
sets no active palette yet, because it does not read the figure set yet.

A family row of `families.json` is a worn look with one bone, `root`. The
part editor of the figure workbench edits it as it edits a worn look.
`FamilyLooks.builder_parts` gives `MeshBuilder` the flat list, with the
place of each part in its shapes. A row of `presentation.json` holds the
turn in degrees, because the author types it. `ModelPresentation.entry_of`
gives the registry its radians.

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
> 1. **A move turns the figure if `StepAnimator` slides it.** The two read one
>    limit, `StepAnimator.SNAP_STEPS`. A run moves two tiles in each tick, and
>    the figure turns on each of them. A longer jump snaps and keeps the yaw,
>    because a teleport has no direction in it. A relayout replays a
>    zero-length move, and it keeps the yaw too. Until 10/05/2026 only a step
>    to a neighboring tile turned the figure, and a runner never turned.
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
> skinning out in the model pipeline (`blackout/assets/pipeline`).** These models carry skinning
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

## The ground is the tile world

Since DESIGN-0011 Phase 5 (09/25/2026), the 3D pane draws the chunks of the
tile world. Since Phase 4b (09/25/2026), the tile world is the only world.
`MapPalette`, the `blackout_map` channel, and `room_kind` are gone.

| Part | Where | What it does |
|---|---|---|
| The chunk channel | server `events.emit_tile_chunks` | Sends each chunk of the 3 x 3 block around the player, on every plane, one time for each session. The plane of the player goes first. A resync sends the block again |
| The model | `world/world_state.gd` | Keeps one `ChunkSet` for each plane, and frees a chunk outside the block. The server forgets the same chunks. `chunks` is the set of the plane of the player |
| The ground | `world/terrain/terrain_view.gd` | One mesh for each chunk of each plane, from `ChunkMeshBuilder`, the class of the editor. It builds one chunk each frame, the chunk under the player first |
| The water | `world/terrain/water_mesh_builder.gd` | A flat surface on each water tile, at the height of its highest corner. The editor draws it with the same class |
| The walls | `world/terrain/wall_mesh_builder.gd`, `wall_palette.gd` | A thin slab on each tile edge with a wall flag, inside its own tile, on the ground of that edge. The wall style of the tile gives its colour and its height. A plain primitive until the walls get art. The editor draws it with the same class |
| The scenery | `TerrainView._place_scenery` | The model that `OBJECT_KIND_SCENERY` names for a chunk object, on the centre of its tile. The server names the model in `world/object_kinds.py`. The transition pad is the first. No art, no model |
| The primitives | `world/terrain/prop_mesh_builder.gd` | A ladder, a flight of stairs, a hatch, or the newel posts at the top of a flight, as plain boxes, for a scenery key in `SCENERY_PRIMITIVES`. The rotation of the object turns it. At rotation 0 the front faces north. A flight rises over the run of its kind, in front of its tile. The editor draws it with the same class |
| The height | `WorldState.ground_y` | The drawn ground at the centre of a tile. The avatar, each entity, the marks, and the aura stand on it |
| The pick | `WorldView._cell_under` | `TerrainPicking.ray_hit` on the height grid. No collision shape |
| The area look | `WorldView._place_marker` | The area of the tile under the player, from its chunk, goes to `AreaEnvironment` |

Four rules:

1. **One coordinate rule.** Tile (x, y) has its centre at (x, h, -y). The
   mesh, the height read, and the pick use it. A figure thus stands on the
   drawn ground, and a click lands on the tile under the cursor.
2. **The chunk payload is the chunk file.** The server sends the JSON of the
   canonical text, and `ChunkFile.from_dict` reads it. A refused chunk is a
   parity bug between the two readers, and `WorldState.last_chunk_error`
   keeps the reason.
3. **A far tile walks by the server template.** A near tile keeps the action
   that `room_info` names. A far walkable tile sends `TILE_WALK_TEMPLATE`
   with its coordinates. A chunk has 4,096 tiles, so the server spells the
   command one time and the client fills in the tile. The chunk flags say
   which tile is walkable. They are server facts.
4. **No position is a guess.** `ground_y` gives null for a tile whose chunk
   has not landed. A figure there waits, and it stands when `chunks_changed`
   brings the ground.

A hover mark shows on the tile under the cursor when a click there acts. It
is the true tile square in `WorldView.COLOR_HOVER`.

### Planes (DESIGN-0011 Phase 7b)

The Z of the room of the player gives its plane: `tile_world` is plane 0, and
`tile_world_p<p>` is plane p. `WorldState.plane_of_z` is the twin of the
Python `planes.plane_of_z`, from the same generated names.

- **Each plane draws at its own heights.** A plane-1 chunk stores absolute
  corner heights, so no offset applies.
- **A void tile has no floor.** `ChunkMeshBuilder` draws no triangle on a
  tile of the floor type `void`, so the plane below shows through. The
  minimap draws it clear.
- **Hide roofs.** Options has a "Hide roofs" box, on by default
  (`ClientSettings.hide_roofs`). On, it hides every plane above the plane of
  the player while the player is under a roof: some plane above has a floor
  that is not void on the tile of the player (DESIGN-0013 decision 4). A
  player outside a house sees its roof. `TerrainView.under_roof` owns the
  rule.
- **A roof is never a cliff.** A roof floor type (`TILE_ROOF_FLOOR_TYPES`)
  never takes the cliff colour, so a steep roof keeps its own colour.
- **The reads of the player read the plane of the player.** The ground
  height, the pick, the minimap, and `tile_action` read `WorldState.chunks`.
  An entity stands on the ground of the plane in its own Z.

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

## A figure walks between tiles, and its true tile stays marked

The server moves a character in whole tiles on each tick: one tile, or two
tiles with run on. The tick engine moves every walker at `TICK_SECONDS`.
Before 09/20/2026, the client drew each step as a jump. That reads as teleporting, not
as walking.

`StepAnimator` slides the figure instead. One animator belongs to each figure.
The world pane holds the observer's, and `EntityPool` holds one for each NPC
and item. Thus, the player and the raider that chases them move by one set of
rules.

**The animation is a look, so the player can switch it off.** The checkbox is
in Options, under Movement. `ClientSettings.smooth_movement` keeps the choice
between runs. The server sends the same messages either way, and the client
asks for nothing more.

**The tick comes from the server.** `clientexport.py` writes `TICK_SECONDS`
into `blackout_constants.gd`. The client paces the walk from it. Never type
`0.6` into GDScript.

### Three rules keep the slide honest

**A crossing takes longer than a tick.** `StepAnimator.WALK_TICKS` is 1.2, so
one tile takes 0.72 s at a 0.6 s tick. That looks wrong and it is the fix for
the jitter.

Cross a tile in exactly one tick and the figure arrives before the next step
can be announced. A message cannot arrive before the event that caused it. The
figure then stands still until that message lands, on every step, for whatever
the network and the tick grid add. A player reads the stop and start as
snapping. Crossing a little slower leaves the figure still moving when the
next step lands.

The cost is a trail. The figure runs about a fifth of a tile behind just
before each step, and a little over one tile just after it. The trail IS the
buffer that absorbs the irregular arrivals, and the true tile mark is what
repays it.

**A crossing takes the same TIME, whatever distance it covers.** The speed is
set when the step lands, and it is held until the next one. This is what
bounds the trail. A speed recomputed each frame from the distance that is left
is an exponential: it halves the gap forever and never closes it, so a figure
that fell behind stays behind.

**A move longer than `SNAP_STEPS` is not a walk.** `SNAP_STEPS` is three. A
teleport, a resync, and an island that arrives late all SNAP.

Three and not one, because `CHANNEL_ROOM_INFO` is in `COALESCABLE_CHANNELS`.
Two steps that land in one tick reach the client as ONE message that names a
tile two squares away. That is a real walk the player took, announced late.
The threshold was 1.5 until 09/21/2026, and it drew that walk as a teleport
several times each minute. Since 09/29/2026 a run makes the case common: each
tick of a run moves two tiles in one message.

A run that turns a corner (north, then east) is drawn as one straight line
across the corner. The client does not know the middle tile of the run.

The honest cost is that a teleport of three tiles or fewer is drawn as a slide
of under a second, through whatever stands between the two tiles. A
map-crossing jump still snaps.

**The move is measured from the last TARGET, never from the drawn position.**
The figure trails during a walk, so a drawn-to-new measurement reads an
ordinary step as more than two tiles. Then every step snaps and the animation
does nothing at all.

### The figure turns, and it does not spin

`_turn_avatar` names the direction. `WorldView._process` turns the figure to
it at `TURN_SPEED`, and a reversal takes about a quarter of a second.

The turn was instant until 09/21/2026. An instant quarter turn at the head of
every step is a snap, and no amount of smoothing on the POSITION hides it.

### A step re-aims the ring, it does not rebuild it

`EntityPool.replace_positions` runs on every step the observer takes. It used
to free and build every mesh and every label in the room. That is a frame
several milliseconds longer, one time for each step, and the eye reads it as
the whole scene stuttering.

`_reaim` does the same work with one lookup and one aim for each entity. It
refuses, and leaves the rebuild to do the job, when the set of drawable
entities changed as well. An island that arrives is that case.

`test_entity_pool` asserts node IDENTITY across a step, because a rebuild
frees the node and puts a new one in its place.

### The true tile is always marked

While a figure is between two squares, it does not stand where the server has
it. And the server's square is the only one a command resolves against. That
gap is what the animation costs. The client pays it back at once.

`TrueTileMark` draws a square outline on the server's tile. The outline stays
for exactly as long as the figure is away from that tile. It goes out when the
figure arrives, because the figure then marks the tile itself.

The model is the OSRS game square, and the true tile indicator its players use:
<https://oldschool.runescape.wiki/w/Game_square>.

**The mark is not separately switchable, and that is deliberate.** It repays
what the animation costs. A player who kept the animation and dropped the mark
would choose to know less than the server says. With the animation off there is
nothing to repay, and the client draws no mark.

Your own square is teal, and everyone else's is amber. The one square a player
must find in a fight is their own. A screen of identical outlines is what hides
it.

### Who draws what

| Node | Holds |
|---|---|
| `Marker` | YOUR true tile. It snaps, because it IS the server's tile. The aura ring is placed from it |
| `Avatar` | What your figure hangs off. It slides towards the marker, and the camera rig follows IT |
| `Entities` | Every other figure, each with its own animator |

The pane draws every other true tile as one MultiMesh. `EntityPool` names the
tiles that need one, through `true_tiles_changed`. It sends that signal only
when the set changes. It groups by TILE and not by entity, because two
identical outlines on one square are z-fighting, not emphasis.

**The pool keeps its animators beside the nodes, not inside them.** `_rebuild`
frees every node and builds each one again: on an entity that arrives, on art
that lands, and on a relayout. A walk must live through all three. Thus, the
record of where a figure is drawn has the entity id for its key.

**The camera follows the avatar, not the marker.** It also closes its gap with
`1 - e^(-k dt)` rather than with `min(k dt, 1)`. The two agree only at a steady
frame rate. The old form snapped below 8 frames each second and tightened above
it. Thus, the camera lagged differently on two machines that watched one walk.

**The minimap needs no change.** It draws from `WorldState`, which holds the
server's tile and nothing else.

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
another tile of your Z in the server's `ENTITY_APPROACH_TEMPLATE`:
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
- **The pane sends a command for an entity on another Z verbatim.**
  `goto (X,Y)` reads its numbers on the Z where you are. On the tile world
  every entity has the same Z, so this is a guard, not a case.
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

The view addresses cells by INDEX. It allocates them, and where an index sits
in the 3D grid is the business of `item_stage.gd` alone. If two cells claimed
one rectangle, they would quietly draw one object in two slots. For that
reason, a test asserts that every cell owns a different region. **The bag and
the doll are two panes with a stage each**, so neither pane has to know how
many cells the other made.

The stage updates `WHEN_VISIBLE`, so text-only mode really does stop paying for
it.

> **`own_world_3d` must be true, and it defaults to false.** A SubViewport left
> at the default SHARES the `World3D` of its parent. Thus, the item meshes land
> in the same 3D world as the game: forty swords and rocks in a neat grid that
> floats in the sky over the map. Also, the stage's `WorldEnvironment` paints
> the game's sky black. The two bugs happened on the first run. Nothing else
> about the viewport hints at it, so `test_inventory_view` asserts that the two
> worlds differ and does not trust a comment.

## The player places every HUD element

Until 09/21/2026 the panel was the bottom half of a `VSplitContainer`, under
the world pane. Until 09/22/2026 the game log was the left half of an
`HSplitContainer`. Each pixel that a split gave to a pane was a pixel that the
world did not get. Until 09/29/2026 each dock hung from a fixed bottom corner
(`PanelDock`), and the minimap, the vitals and the XP drops had fixed offsets
in `console.tscn`. The player could size the two docks and nothing else.

Now the player moves, sizes, hides, fades and scales six HUD elements in the
layout editor. The "Edit layout" button in Options opens it. `Done` and Esc
close it.

| Key | Element | Control | Can hide | Fades |
|---|---|---|---|---|
| `log` | Game log | `%ConsoleDock/Box` | No, it holds the input | The background |
| `panel` | Control panel | `%PanelDock/Box` | No, it holds Options | The background |
| `minimap` | Minimap | `%Minimap` | Yes | The whole element |
| `xp` | XP drops | `%XpHud` | Yes | The whole element |
| `vitals` | Vitals | `%WorldVitals` | Yes | The whole element |
| `hover` | Hover text | the world `HoverBar` | Yes | The whole element |

Five files share the work. Each one has one job:

| File | Owns |
|---|---|
| `world/hud_layout.gd` | The rules: the anchor of a drop, the position from an anchor, the clamp, the snap, and the check of a saved entry. Static, and it knows no node |
| `scenes/layout/hud_elements.gd` | The table: the key of each element and where it ships |
| `scenes/layout/hud_slot.gd` | One row of that table, with its control |
| `scenes/layout/hud_arranger.gd` | The one owner of where each element sits. It places every element on each pane resize and each layout change |
| `scenes/layout/layout_editor.gd` | The mode: a frame over each element, the grips, the snap, the bar, and the presets |

**A new HUD element is one row in `HudElements.ROWS` and one control** in
`Console._build_layout`. The arranger and the editor name no element. Never
change a key after it ships: the saved layout of each player uses the key.

**An element keeps its distance from its nearest corner.** A drop stores an
anchor and an offset, not a position. The anchor comes from the third of the
pane that holds the centre of the element: left, centre or right, and top,
centre or bottom. Thus a minimap that the player moved to the top right stays
at the top right, the same distance from the corner, in any window. The player
never sets an anchor by hand.

**The arranger is the one owner of "the element is on the screen".** Its pass
runs on every resize of the window and on every layout change. It clamps each
element into the pane, and it never makes an element smaller than its
content. A `TabContainer` reports the widest minimum of its tabs, so the
content usually sets the floor of the panel. A layout that a wide window saved
comes back into a narrow one here.

**The layout is locked outside the editor.** No grip hangs on a dock during
play, so a drag in the world never moves a box. The editor covers the whole
console and takes each click and each key while it is open. A movement key
thus never walks the player behind it. It is the last child of the console,
so its grips draw over every element, and the docks no longer need to keep
clear of each other.

**A drag snaps.** An edge snaps to the pane edge one margin in, to the edge of
another element, or one gap beside it. The centre snaps to the centre of the
pane. Shift stops the snap. No line puts two edges flush: that line is less
than the snap distance from the gap line, and the drag would jump between
them. A drag also does not snap to an element that follows other elements,
such as the shipped hover bar. Its edge moves with the dragged edge, so the
snap pulled the log back 2 pixels on each mouse step, and the log jittered.

**Three facts decide whether an element is drawn.** The player hides it in
the editor. A setting in Options turns it off: the 3D world takes the minimap,
the vitals, the XP drops and the hover text with it. The console calls that a
gate (`HudArranger.set_gate`). The two stay apart, so the minimap comes back
where the player put it when the world comes back. A hidden element keeps a
faint frame in the editor, so the player can find it and show it again.

**A dock fades its background, not its text.** The log and the panel fade
through `self_modulate` on their box. A clear log is still a log that the
player can read. Every other element fades whole, with a floor of 20%, because
Hide does the job of 0%.

**A scale keeps the anchored corner.** The element scale multiplies the global
interface scale of Options. A panel at the bottom right grows up and to the
left.

**Presets are layouts by name.** The editor bar saves the current layout under
a name, loads it, and deletes it. `ClientSettings` keeps up to 20. "Reset to
defaults" in Options resets the layout and keeps the presets. "Reset all" in
the editor does the same.

**The arranger writes the layout, and reads it only when told.** A drag writes
through `ClientSettings.set_layout` after 0.4 seconds. The arranger reads the
layout again only on `ClientSettings.layout_replaced`: a load, a reset, or a
preset. A pane that follows the setting it writes is how a slider in Options
came to collapse the pane it sat in.

**The dock sizes of an older build move into the layout.** Before 09/29/2026
`client.cfg` kept `panel_size` and `console_size`. The first load takes each
one as the size of its element, and the dock keeps its shipped corner.

**The shipped size follows the pane.** Before the first edit, a dock takes its
row size or its share of the room, whichever is smaller. A fixed size that
suits a 1920 x 1080 window covered the minimap in a 1280 x 720 window.
`smoke_console` checks that no two shipped elements overlap at five window
sizes, from 1280 x 720 to 2560 x 1440. That check found two old overlaps on
09/29/2026: the XP drops ended under the minimap, and the panel covered the
bottom of the minimap in the two smallest windows.

**The pop-up is not a HUD element.** The server opens and closes it, so the
editor would have no box to show most of the time. The player moves and sizes
it where it is, and it keeps its own grips.

**The first-run UI scale comes from the screen.** The console gives
`ClientSettings` the scale for the screen DPI: 144 DPI gives 1.5. A browser
gives 96 times its device pixel ratio. A scale in the file wins, and Reset
goes back to the scale of the screen.

**The log dock is a sibling of the world pane, not a child.** The loading veil
must be the last child of the world pane, and it covers that pane only. The
log thus stays readable while the world loads, as the old text column did.

**With the 3D world off, the log fills the space beside the panel.**
`HudArranger.fill_beside` gives the log the full height, and the width on the
wider side of the panel. The editor shows no grips on the log then. The saved
layout does not change, and the log returns to it when the world comes back.

**The world pane is never hidden, and the panel dock is the reason.**
`show_world` turns off the 3D view and the HUD elements over it, not the pane
itself. The panel holds Options, so a hidden pane would be a setting that
hides the screen that you change it on.

**The panel dock draws over the pop-up and under the right-click menu.** That order
is the pop-up's own rule and not a layout detail: a pop-up draws no copy of the
bag, because the inventory pane IS the bag. A bank that covered the bag would
put every Deposit action on it out of reach.

**It is not a `Window`.** `PanelView` says why the three floating windows went
in 08/2026: a web export is one canvas, so a Window is an embedded subwindow
that cannot leave the game area. Each HUD element is an ordinary `Control`
over the world pane, and so are the veil and the right-click menu.

## The paper doll is the client's picture of the server's slots

The doll was a flat row of twelve squares under the carried grid until
09/21/2026. It is `EquipmentView` now, in a tab of its own, in the shape of
OSRS's Worn Equipment tab.

**`DollLayout` owns that shape, and the server must never learn it.** The
server says which wield locations exist and in what order to READ them
(`SLOT_DISPLAY_ORDER`, which arrives as the `equip_slots` frame list). It does
not say that the head goes above the chest.

The asymmetry is the same one that `AreaLook.LOOKS` documents:

- **A square that names no wield location is a bug.** The server never sends a
  frame for it, so the doll draws a hole that the player can never fill.
  `test_client_constants.py` fails on it.
- **A wield location that the table forgets is fine.** It lands in a strip
  under the doll. Thus, a slot added to the enum reaches the pane with no
  client edit.

**Twelve frames go into eleven OSRS squares.** OSRS has one weapon square and
one shield square. Blackout has three hand slots, because `two_hands` is a slot
of its own. So the two-hander gets a row of its own across the width, and the
pane draws that row only while the slot is occupied. The pane asks whether the
slot holds anything, never what kind of thing it holds. An empty two-hand frame
is a square that cannot be filled while a one-hander is worn, and a permanent
dead square in the middle of a doll reads as a bug.

> **A tab strip costs one gesture.** The bag and the doll were one pane, so a
> drag from a carried square to a worn frame was an `equip`, and the reverse
> was an `unequip`. Neither endpoint can see the other now. **The left click
> replaced both**, and it costs nothing: the server puts `Equip` first on a
> carried wearable and `Unequip` first on a worn row, so one click does what
> the drag did. `EquipmentView` connects no `dropped` signal, and
> `inventory_view.gd` keeps only the swap. A branch put back in either file
> would compose a verb for a gesture that no player can make, which is how a
> verb table gets into a client.

## A pop-up is item grids, and every slot carries its commands

The server opens a pop-up over the world pane on `char_popup`: the bank
(`bank`), a shop (`trade`), and a crafting facility (`craft`). The model is the
OSRS bank, shop and smithing interfaces: a left click on a slot sends its first
action, and a right click lists all of its actions.

```
char_popup -> {open, key, title, status, grids: [...], quantity: [...],
			   actions: [...], text, choices: [...], input, timers,
			   close_command}
```

Each grid is `{key, title, slots_total, items}`, and each item row has the
shape of a `char_items_list` row. A row also carries `detail` (one short line
under the name, for example a price or a skill level), `info` (more lines for
the tooltip), and `enabled`. A slot with `enabled` false is dim, and a click
still sends, so the server can say why the action fails. A buff card row also
carries `rarity`, the key of its rarity. [RarityPalette] gives the colour of
the border and the detail line: green, blue, purple, orange. `actions` is the row
of buttons under the grids, for what the pop-up affords as a whole: stop a
craft, collect a cure.

**The pop-up draws no copy of the bag.** The inventory pane is the bag. While
a pop-up is open, the server puts its verb FIRST on each bag row: Deposit for
the vault, Sell for a shop. Thus, a left click in the pane deposits or sells,
as in OSRS. A shop also sends the row's price as `detail`, and the bag cell
shows it in the tooltip. The pane follows the pop-up, because the server sends
`char_items_list` again when a pop-up opens, closes, or changes its quantity
mode.

**A timed station has a side panel.** `timers` is `{title, total, slots}`, and
each slot is `{name, ready, remaining, duration}` in seconds. `TimerPanel`
draws a bar for each slot, and an empty row for each free slot up to `total`.
It counts `remaining` down between snapshots, so the bar moves. At zero it
says "Finishing...", not "Ready": `ready` is the server's word. The server
marks the pop-up stale at the deadline, and that snapshot says `ready`. The
curing chamber is the first station. A second timed station needs only a
`timer_report` on its server-side handler.

**A grid can have tabs, a search box, and a drag.** The bank vault sends all
three (10/08/2026). A grid that sends them carries four more fields:

| Field | Holds |
|---|---|
| `tabs` | One `{index, label, title, asset, family, active, drop_key, actions}` for each tab button, the "+" last |
| `view` | The tab that the player views. `0` is the main tab |
| `searchable` | `true` shows the search box |
| `drag` | `{onto_slot, onto_tab}`: the command template for a drop on a slot or on a tab |

Each vault row also carries `tab`, `drag_key` and `placeholder`.
`PopupState.row_groups` decides which rows show. A search shows each match in
every tab. A tab other than `0` shows its own rows. The main tab shows every
row, in one block for each tab, with a line between two blocks.

The rules that keep the client out of the game:

- **A tab button draws what the server sent.** A tab with an `asset` shows that
  mesh, and a tab with no asset shows its `label`. A named tab sends no asset.
  `PopupTabButton` thus never asks what a tab is.
- **A drop fills a server template.** `PopupState.drop_command` puts the
  `drag_key` of the dragged slot at `DRAG_SOURCE_TOKEN` and the key of the
  target at `DRAG_TARGET_TOKEN`. These are the tokens of the inventory swap.
- **A left click on a vault slot fires on the release.** A click that fired on
  the press would withdraw the item that the player meant to drag.
- **The search text belongs to the client.** A snapshot keeps it, so a
  withdraw from a search result does not clear the search. The filter needs no
  round trip for each key press.
- **A rename is a text action.** `input.kind` is `ACTION_INPUT_KIND_TEXT`, and
  `TextPrompt` asks for the text. `TextPrompt.perform` reads both prompt kinds,
  so a slot and a tab button send a prompted action the same way.

**The player moves and sizes the box.** A drag on the title bar moves it. A
drag on any edge or any corner sizes it, and the edges that the grip does not
name stay where they are. The grid fits its columns to the new width. The box
stays inside the pane, also when the pane changes size.

**The grips of the pop-up draw over the docks.** The control panel draws over
the pop-up on purpose, and until 09/22/2026 it covered the only grip of the
pop-up, in the bottom-right corner. Each grip is now a `top_level` Control.
Godot draws a top-level item after all other items, and the GUI picks it
first. `ResizeGrips` makes the grips for the pop-up and for both docks.

**The first box opens between the docks.** The console gives the pop-up the
gap between the log dock and the control panel. When the gap is at least
`MIN_GAP_WIDTH` wide, the first box opens centred in it. It is never larger
than `DEFAULT_MAX_SIZE`. In a narrower gap, it opens centred in the pane.

The server orders the actions of a row, and
it puts the active quantity mode first. Thus, "Withdraw 5" is what a left click
means after the player picks 5, and the client never learns what 5 is.

**The client sends only what the server named.** A vault slot carries
`withdraw rusty metal dust 5`, the same line that a telnet player types at the
terminal. The X entries are prompted actions, the shape that the inventory's
Deposit X already uses. `ServerAction` reads that shape and `AmountPrompt`
asks for the amount, so the two panes share one rule and one box.

The box is built per prompt and freed on close, so the size the player drags it
to lives in `ClientSettings.amount_size`. It is read when the box CLOSES, one
write for one box. One size serves every verb, because Deposit X, Withdraw X,
Sell X and the pop-up's X button all draw the same box with a different title.
Zero means "wrap the contents", which is the first-run look.

**It is a Control over the pane, not a `Window`.** On the web, a `Window` is a
subwindow that cannot move beside the game, the lesson that `SummaryView`
records. `PopupView` is a full-pane Control, as `ChooseOption` is. While it
shows, it takes every click on the pane, so a click beside the box does not
walk the player.

**It closes when the server says so.** The close button and Escape send
`close_command`. The box goes away when the closed snapshot arrives. The
server also closes it when the player walks away from the terminal.

**A rebuild keeps the scroll.** Every snapshot rebuilds every slot, as the
inventory does. A withdraw sends a snapshot, so each grid keeps its scroll
position through a rebuild of the same pop-up.

**The box keeps the rect the player dragged, between runs.** A drag on the
title bar moves the box and a drag on a grip sizes it.
`ClientSettings.popup_rect` keeps both. Until 09/21/2026 the rect lived in the
view and died with the client, so a player who moved the bank off their
minimap moved it again on every run.

Three rules hold that together:

- **`PopupView._place_box` stays the one owner of "the box is on screen".** It
  clamps a rect into the pane on every open, every drag and every resize of
  the pane. Thus the saved rect is plain pixels, and a box saved by a wide
  window comes back inside a narrow one.
- **The rect is read the first time the box is placed, not at bind time.** The
  console binds every pane BEFORE it loads the file.
- **The write is debounced by 0.4 s, and the view writes the CLAMPED rect.**
  `gui_input` fires for each frame of a drag, and each setter writes the file.
  This is the rule the two dividers already follow.

Reset in Options forgets the rect. The box moves home on the next run, not at
the click: `bind_settings` does not follow `changed`, because a rect pushed
back in on every change loses a drag made inside the write delay.

**The quantity mode is server state.** The 1 / 5 / 10 / X / All buttons send
`popup quantity <n|all>`. The button lights only when the next snapshot says
so, the rule that the Combat tab follows.

A new pop-up is one Python file under
`blackout/systems/interface/popups/popup_defs/`, and no client edit.

**An EvMenu node uses the same channel.** It has no grids. It has three other
fields:

- `text`: the node as escaped BBCode, from the parser that the log uses.
- `choices`: `[{key, label, command}]`, in the order of the node.
- `input`: `{label}` when the node reads typed text, else `{}`.

> **The field is `choices`, never `options`.** The statefeed sends a payload
> as the keyword arguments of `msg()`, and Evennia reserves `options` for
> protocol flags. The socket removes it before the message leaves. Until
> 09/18/2026 the field had that name, and every menu pop-up showed its text
> with no buttons. `test_emit.py` now refuses any payload field of that name.

The view draws the text with the `ChatLog` variation of the log. Thus, a menu
table lines up as it does in the log. The text and the choice buttons share
one scroll, so a long node scrolls down to its choices. A button sends the
choice key. The box sends the typed line. A number key picks the choice with
that key. The node text does not also go into the log. If the box had the
keyboard when it hides, `keyboard_released` gives the keyboard back to the
game input.

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
`blackout_chunk` can still be on its way, `room_info` might not yet name the tile
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

A device with a saved login logs in again by itself after a drop. See the
next section.

## A saved login logs in by itself

The login form has a **Remember me on this device** box, ticked by default.
With the box ticked, a login by password sends `remember` once the body
exists. The server answers with a login token on `CH_LOGIN_TOKEN`, and
`SavedLogin` keeps it in `user://login.cfg`. At the next start, the form sends
`resume <name> <token>` when the server confirms the subscription. The player
is in with no password typed.

**The device keeps a token, never the password.** On the web, `user://` is
IndexedDB, and any script on the page origin can read it. A stolen token
opens one account until one of these things happens:

- The token goes 30 days with no use.
- The password changes.
- The player types `forget` on that device, or `forget all` on any device.

The server keeps only the SHA-256 digest of each token
(`blackout/systems/core/login_tokens/store.py`).

**The file is not `client.cfg`.** A player can share `client.cfg` to show a
layout, and a key to the account must not go with it.

Four rules keep the auto-login safe:

| Rule | Why |
|---|---|
| One `resume` for each socket | A reload of the server confirms the subscription again. A refused token must not loop |
| No `resume` with a body | A reload of a logged-in server is not a new login |
| A clean close (code 1000) stops the auto-login | `quit` and a boot both close with 1000. A client that logged straight back in would make both useless. Connect with an empty password sends `resume` again |
| The server decides when a token is bad | `forget` and a refused `resume` both send an empty token. The client clears its copy and asks for the password |

**The echo is off before login.** The Portal echoes each typed line back
when `LOCALECHO` is on. Before 10/05/2026, `ServerSession.at_sync` turned it on
for every session, so the log printed `connect <name> <password>` as typed.
Now `at_sync` turns the echo on only for a logged-in session, and
`ServerSession.at_login` turns it on at login. The `resume` line and its
token thus never reach the log.

The **Forget saved login** button removes the token from this device only. The
server copy stays good until it expires or the player types `forget all`.

## The terrain editor writes chunk files, not scenes

DESIGN-0011 section 6.3. The terrain editor is an editor plugin in
`addons/blackout_terrain/`. `project.godot` enables it. The web export excludes
the directory (`exclude_filter` in `export_presets.cfg`), so a player never
downloads it.

To use it:

1. Open `res://addons/blackout_terrain/terrain_editor.tscn`.
2. Select the `TerrainWorld` node. The Terrain panel opens on the right.
3. In the block strip, set the centre chunk and the plane. Click **Load**.
   The four pan buttons move the block one chunk. **Go to tile** loads the
   block of a tile and puts the beacon on it.
4. On the **Paint** tab, click a tool, or press its number key. Drag with
   the left button. Shift lowers with the Raise brush, clears the flags with
   the Flags brush, and picks the floor or the area under the mouse with
   those two brushes. The hint line at the bottom of the 3D view names the
   tool, its values, and the keys.
5. Click **Check world** on the **World** tab. Fix each finding.
6. Press Ctrl+S, or click **Save** in the file strip. The button counts
   the changed chunks. The plugin writes each changed chunk to
   `blackout/world/chunks/`.
7. Stop the server, run `scripts/sync_tile_objects.py --apply` from
   `blackout/`, and start the server. The World tab names each chunk file
   that changed since the last sync.

Three strips sit above the tabs:

| Strip | Holds |
|---|---|
| File | **Save (N changed)**, **Revert** (reads the chunk files again, after a question that counts the unsaved chunks), **Open workbench** or **Open world**, and in the workbench **Clear workbench** |
| Block | The centre chunk, **Load**, the four pan buttons, the plane, **Go to tile**, and **Walls down (V)** |
| Paint values | The **Floor**, the **Area**, and the **Wall** style that the tools of the Paint tab and of the Build tab write. One list for each, so a pick from either tab lands here. **(keep)** leaves the floor or the area of each tile: the Room and the Place tool use it, and the Floor brush and the Area brush paint nothing with it. **New** beside each list opens the Tables tab on its table |

The panel has six tabs:

| Tab | Holds |
|---|---|
| Paint | The tool row, and the options of the current tool only: the radius, the brush shape, the strength, the flags, the object kind and rotation, the sign text, the noise, and **Protect structures** |
| Build | The structure tools (DESIGN-0013): Wall line, Room, Doorway, Level above, Ladder, Stairs, Roof, Wall style, Decor, Select tiles, and Place, with the options of the current tool only. See "The Build tab" below |
| Objects | The selected object with its **Kind**, **Rotation**, and **Sign text** fields (a change applies at once), **Turn**, **Turn back**, **Delete**, and **Follow link**. A filter, and a list of every object in the block. A click on a row selects it, and the Paint tool stays. **Show decor** off keeps the decor out of the list |
| World | The **Block** report (the load errors and the seam faults, kept until the next load), the marks to show with a legend, how the planes above show, **Check world** and its findings, and the state of the tile sync |
| Look | The colour of each floor type, the cliff, the water, and each prop, the colour and the height of each wall style, the fog and the light of each area with **Preview the area light**, and the colours of the editor marks. See "The Look tab" below |
| Tables | The rows of the areas, the floor types, the wall styles, and the decor kinds: **New row**, **Save row**, **Rename row**, **Remove row**, and **Read files again**. See "The Tables tab" below |

The **Shape** of the Paint brush is a circle or a square. The side of a
square is twice the radius, and its edges lie on the tile edges. An odd side
centres on the tile under the mouse, and an even side on the nearest corner.
The ring shows the tiles of the square. The Ramp has no shape, because it
reads the radius as the half of its width.

The **Pick object** tool of the Paint tab picks an object on a click. A
second click on the same tile picks the next object there. A drag moves the
selected object to another tile. A tall magenta beacon marks the selection,
or the tile of a finding.

**Follow link** loads the block where the selected object leads: the target
of a transition, or the same tile one plane up or down for a climb. A click
on a finding loads its block and plane in the same way. With unsaved chunks,
a move to another block asks first: the move saves the chunks and drops the
undo history.

The keys of the 3D view work on every tab. Page Up and Page Down change the
plane. V toggles "Walls down". The bracket keys step the radius of the Paint
brush, or the pitch and the brush of the Build tools. The number keys 1 to 9
and 0 pick a tool of the tab that shows. Esc drops a drag, a half-made ramp,
and the selection.

The rules that the editor keeps:

- **The scene holds no terrain.** Every mesh is made at load and has no owner.
  The chunk files are the only store.
- **The block is 4 x 4 chunks.** The centre chunk is the south-west chunk of
  the middle four. A brush writes a shared corner to every chunk
  that stores it, so a seam behaves like any other place. The outer edge of the
  block shows red, and no brush writes it: its corners also belong to chunks
  that are not loaded.
- **What the author sees is what the player sees.** The ground comes from
  `world/terrain/chunk_mesh_builder.gd`, and Phase 5 draws the client with the
  same class. The flag, area, and object marks are the editor's own.
- **The lists come from the server.** The floor types, the areas, and the
  object kinds are rows under `blackout/world/`, exported to
  `blackout_constants.gd`. A new row needs no edit here.
- **One stroke is one undo entry.** `TerrainEdit` keeps the first value of each
  changed corner or tile. A Build gesture is one entry too, over every plane
  that it writes.
- **The block holds every plane** (DESIGN-0013 Phase S0). `TerrainWorld` keeps
  one `ChunkSet` for each plane, and an edit keys on (plane, tile). A change of
  the plane reads no file, saves nothing, and keeps the undo history.
- **A file that does not read stays out of the block.** The editor never draws
  a blank chunk in its place, so a save cannot overwrite it.
- **The noise seed is not in the chunk file.** The file stores the baked
  integer heights, because the server cannot run Godot's noise. The seed, the
  frequency, and the amplitude persist in `terrain_editor.cfg`, beside the
  plugin, so every author gets the same noise.
- **Every other choice is in the session file**, outside the repo:
  `user://blackout_terrain_session.cfg`. The tool, the Build options, the
  paint values, the marks to show, and the colours of the editor marks live
  there. Thus a session leaves no modified file in git.
- **A new chunk above the ground starts from the chunk below.** Its heights
  are those below plus 32 height steps (two tiles). Every tile is `void` and
  Blocked, and the areas are those below. A floor paint on a void tile clears
  Blocked, and a `void` paint sets it. Until an edit, a new chunk follows the
  ground under it. The planes below show dim. The planes above show hidden,
  dim, or solid, as the World tab says.
- **A move of the block clears the undo history.** The move saves the old
  block first. Thus, an undo after the move would write into a chunk that is
  not loaded. `TerrainWorld.replay_edit` also refuses an edit of another
  block. With unsaved chunks, the plugin asks before the move, and the
  status names the files that the move saved.
- **A chunk file that does not write shows first in the status box**, in
  capitals, and it stays unsaved. The Output panel alone is easy to miss.
- **Ctrl+S reaches the last edited world.** Godot gives the plugin no world
  while another node is selected, for example the sun. The plugin keeps the
  last one, so the save and the close prompt still see its unsaved chunks.
- **Check world runs the rules of the server.** `terrain_checks.gd` is the
  twin of `blackout/world/tile_checks.py`. Each transition and each climb
  lands on an open tile. Each object stands on a walkable tile. Each void
  tile is Blocked and carries no wall. The world has one respawn point. The
  check reads the files on disk, with the unsaved block in place. The two
  twins check one fixture world against one `expected.json`.
- **A note warns and fails no test.** `unreachable` gives one note for each
  pocket of walkable tiles that no walk from the respawn point reaches. The
  findings list shows a note in blue. `step_grid.gd` holds the GDScript twin
  of the server step rule, and the pockets of the fixture test it.
- **A wall meets the floor above it.** Where the same tile of the plane above
  has a floor, the wall top takes the corner heights of that tile.
  `WallMeshBuilder` draws it this way in the client and in the editor.

### The Build tab

DESIGN-0013 section 6.7. A structure is tile grid facts, not a scene: wall
flags, floor types, a plane above, and a climb pair. The tools write those
facts, so the server reads nothing new. `structure_tools.gd`,
`room_fill.gd`, and `roof_shapes.gd` hold the rules.
`test_structure_tools.tscn` and `test_roof_shapes.tscn` test them.

The tab shows the options of the current tool only. The hint line names
the state of the rest.

| Tool | Gesture | Shift |
|---|---|---|
| Wall line | Drag along tile edges, on one axis | Remove the walls under the line |
| Room | Drag a rectangle: the levelled ground, the floor, the area, and walls on the inner edges of the border | Remove the walls in the rectangle |
| Doorway | Click a wall edge. The wall goes from both sides | Put the wall back |
| Level above | Click inside a closed room, or drag a rectangle. The plane above gets a floor, flat at the highest corner plus 32 steps | Set the tiles back to void and Blocked |
| Ladder | Click a tile. The ladder goes straight up: the climb goes on this plane and its twin on the same tile of the plane above. A void landing gets a floor. A tile with the pair refuses a second pair. R and Shift+R turn the next one | Remove the pair |
| Stairs | Click the tile at the foot. The flight rises over the 3 tiles in front of the foot. Its twin goes on the plane above, on the tile past the top step. The steps get Blocked, and the plane above gets a void stairwell over them. A void landing gets a floor. R and Shift+R turn the next one | Remove the pair, and open the steps again. The stairwell stays void |
| Roof | Click inside a closed rectangle room, or drag a rectangle. The plane above gets the roof floor type, Blocked, and the corner heights of the roof shape over the room and its overhang | Set the roof tiles back to void and Blocked |
| Wall style | Drag the brush ring over walls. Each tile with a wall bit under the ring takes the wall style | Paint the default style, `plain` |
| Decor | Click a tile, again and again. The decor of the options goes on the tile at the next turn. R and Shift+R turn the next one | Remove the decor on the tile |
| Select tiles | Drag a rectangle, or click inside a room. Ctrl adds to the tile selection | Take tiles out of the tile selection |
| Place | Click to write a copy of the template of the options. R turns it, F mirrors it | none. Alt and a click replace the objects on its tiles |

Alt and a click take the floor, the area, and the wall style of a tile into
the paint values strip. On a tile with decor, they also take its kind and
its turn. Esc cancels a drag. "Walls down" in the block strip, or V, draws
each wall low, so the author sees into a room.

**Ladders and stairs** (Nick, 10/16/2026). A ladder goes straight up. A
flight of stairs goes up over tiles. A walker stands on the tile at the
foot and types `climb up`, and lands past the top step on the plane above.
`climb down` on that tile goes back to the foot. The run of the climb kind
gives the tiles of the flight (`STAIRS_RUN`, 3). The rotation of the
object gives the way. Both objects of a flight carry the same rotation. The
mark of the Stairs tool covers the foot, the steps, and the landing. A
flight that leaves the loaded block refuses, and the hint line says to turn
it. The session file keeps the tool by name, so a new tool can go anywhere
in the row.

In the game, a click on a ladder, on the foot, or on any step walks to the
climb and climbs it. The server sends that action for each tile of each
climb near the player. The steps are Blocked, so no walk command fits
them. The pick meets each step at its drawn height
(`PropMeshBuilder.pick_tops`). Thus a click on a high step picks that step,
not the ground past it. A wall beside the steps rises to the plane above,
and a wall on a stairwell tile is legal. `ClimbRule`
(`world/terrain/climb_rule.gd`) owns the landing, the steps, and the
stairwell for the client, the editor, and the checks.

**Wall styles.** A wall style is the look of the walls of one tile:
`plain`, `concrete`, `brick`, and so on (DESIGN-0013 section 6.4). The rows
are in `blackout/world/tables/wall_styles.json`, and the Tables tab edits
them. The colour and the height of each
style are the client's own, in `world/look/terrain_palette.json`, with
`world/terrain/wall_palette.gd` as the fallback. The Look tab edits them.
`plain` starts 0.75 units tall, and `rubble` is a low ruin wall. A style
with no row anywhere draws in the colour and at the height of `plain`, so a
new style needs no client edit.

The Wall line and the Room put the wall style of the options on each tile
that gets a wall bit. The Wall style brush paints the style on the walls
under its ring, and the bracket keys step its radius. A removal keeps the
style of a tile: a style with no wall bit is legal, and nothing draws it.
A chunk with a style other than `plain` saves as format 2. Every other chunk
stays format 1, so its file does not change.

**The Roof tool.** A roof is the ground of the plane above (DESIGN-0013
section 6.2). The options are the shape (Flat, Shed, Gable, Hip, Pyramid),
the pitch (1 to 16 height steps for each tile), the overhang (0 to 2
tiles), and the roof floor type. R and Shift+R turn the ridge of a gable or
the low edge of a shed. The bracket keys step the pitch. The roof meets the
walls at 32 steps above the highest corner of the room, and the overhang
hangs one pitch lower for each tile. The walls rise to meet the roof, so a
gable end fills itself.

While the mouse is down, the outline shows the roof: a lattice at the roof
heights. A green outline builds on release. A red outline is a refusal, and
the hint line names the reason, for example a floor on the plane above. To
roof a house with a level above, edit the plane of that level. The planes
above are hidden by default, so a note on the hint line tells the author
where the roof went.

**The Decor tool.** Decor is scenery and nothing more: a crate, a table, a
lamp post (DESIGN-0013 section 6.5). The kinds are the rows of the `decor`
category in `blackout/world/object_kinds.py`. A tile holds one decor. A
click on a tile with decor replaces it, so a second click after R turns it.
The mark under the mouse shows the edge that the front of the next decor
faces. A void tile takes no decor. A Blocked tile takes decor, and the
content check does not refuse it. A Blocked tile under a table stops a walk
through it. Decor pins no tile room, and the tile sync stands nothing up
for it. Until a model record takes the key, `PropMeshBuilder` draws a
plain shape.

**Select, Move, and Delete.** The Select tiles tool of the Build tab holds
a tile selection, not an object. With "Select every plane" on, a gesture takes the
edited plane and each plane above it. A click inside a room then takes the
room, its level, and its roof with the overhang. The keys:

| Key | Does |
|---|---|
| Delete | Takes the walls, the wall styles, and the objects off each tile. A ground tile keeps its floor. A tile of a plane above goes back to void and Blocked |
| Ctrl+C | Copies the tile selection to the clipboard |
| Ctrl+V | Starts the Place tool with the clipboard |
| M | Starts the Place tool with the tile selection. The click clears the old tiles and writes the new ones, in one undo entry. The move keeps its planes. A pick of another tool ends it |
| Esc | Drops the drag, else the tile selection |

**Templates and the Place tool.** A template is a saved structure in
`blackout/world/structures/<key>.json` (DESIGN-0013 section 6.6).
`blackout/world/structures/README.md` gives the format. Type a key and
click "Save as template". A key that a template has asks first: the old
file goes. The Place tool then lists it, after the row of the clipboard. A copy is plain facts in the chunk files,
and nothing links it to its template.

The outline of the Place tool follows the mouse, centred on it. Green
places. Amber places with a warning: the levelling moves a corner more than
one plane rise, or the blend ring reaches another structure. Red refuses:
an object on a covered tile (Alt replaces it), a floor on a covered tile of
a plane above, the locked edge of the block, or the top plane. The hint
line names the reason. The copy levels its ground to the "Level to" rule,
and the blend ring moves the corners around it part of the way to that
base. A copy from the list keeps the tool on, so one click places each
stall of a market row. `structure_template.gd`, `structure_place.gd`,
`tile_selection.gd`, and `template_input.gd` hold the rules, and
`test_structure_template.tscn` tests them.

**Protect structures.** With this box on the Paint tab, under each sculpt
tool, a sculpt, a ramp, and a noise fill skip each corner of a tile with a
wall or with a floor above it. The author then shapes the hills around a
town, and the floors stay flat.

**The structure workbench.** Open
`res://addons/blackout_terrain/structure_workbench.tscn`, or click "Open
workbench" in the file strip (DESIGN-0013 Phase S6). It is the
terrain editor on scratch chunk files in `user://structure_workbench`,
outside the repo. The ground starts flat and blank. Every tool works as in
the world. Build a structure, select it, and save it as a template. The
template goes to `blackout/world/structures/` as from the world, and no
chunk of the world changes. To change a template, place it in the
workbench, edit the copy, and save it again with the same key.

- "Check world" in the workbench leaves out `respawn_count` and
  `unreachable`. A scratch world holds no respawn point.
- "Clear workbench" deletes the scratch chunk files after a question that
  counts them, and the ground is blank again. The templates stay. The
  button refuses the world chunk files.
- "Open world" goes back. With unsaved chunks, it asks to save them first.

The hint line at the bottom of the 3D view names the tool, its gesture, each
modifier, and each toggle, on every tab. A size readout follows the cursor
during a drag. After each gesture, the live check runs the cheap rules on
the changed tiles. The hint line names the first finding, and the findings
list of the World tab says that its rows can be old.

### The Look tab

Since 10/13/2026 the look of the terrain is data, not code. Each table of
the client keeps its old values as the fallback, and a JSON file under
`world/look/` is the design:

| File | Holds | Fallback |
|---|---|---|
| `terrain_palette.json` | The colour of each floor type, the cliff, the water, and each prop. The colour and the height of each wall style, in height steps. The wall top lighten | `world/terrain/floor_palette.gd`, `wall_palette.gd` |
| `area_looks.json` | The nine fields of the fog and the light of each area | `world/area_look.gd` |

`world/look/look_file.gd` reads and writes them, with a cache, so a mesh
build pays for no file read. A key with no row draws as before the file
existed. Thus a new floor type, wall style, or area needs no edit anywhere
on the client, and a missing file breaks nothing. The Python guard
(`LookFileTests` in `test_client_constants.py`) fails on a key that names
no server fact.

The Look tab edits the two files. Each picker and each field writes the
file a short moment after the last change of a drag, and the block draws
again, so the author sees the colour on the ground. "Preview the area
light" applies the fog and the light of the chosen area to the sun and the
environment of the editor scene, through the same routine that the game
uses (`AreaLook.apply_to`). The preview writes into the sky and the sun of
the scene. Thus, the plugin ends it before each save (`_apply_changes`), and
starts it again on the next frame. A save with the preview on stored the
look as the sky of the scene until 10/14/2026. "Reset colours" and "Reset
area" take the rows out of the file after a question.

The colours of the editor marks are the last section of the tab: the
Blocked and water tiles, the walls, the borders, the brush ring, the Build
outlines, the beacon, the ghost planes, and the marker of each object
category. A player never sees them, so they are no look file. They are the
author's, in the session file, and "Reset marks" gives the defaults back.

### The Tables tab

Since 10/14/2026 the areas, the floor types, the wall styles, and the decor
kinds are table files under `blackout/world/tables/`. That directory has a
README with the format and the steps. The Tables tab edits the four files.
Nick chose JSON tables, a New button for the four tables, and a rename and
a removal too.

| Button | Does |
|---|---|
| **New row** | Adds the fields as a new row at the end of the table. The key must be new and a legal chunk file name, and each text needs a word. A decor kind needs a scenery: a primitive or a served model |
| **Save row** | Writes the fields to the selected row. The key stays |
| **Rename row** | Gives the selected row the key of the Key field. It asks first and counts the files. It saves the unsaved chunks. Then it writes the new key into each file that names the old key: the chunk files, the templates, the look rows, and the fallback rows. The block then reads again |
| **Remove row** | Takes out the selected row when no chunk file, unsaved chunk, or template uses it. Its look rows and fallback rows go too |
| **Read files again** | Reads the table files again, after an edit outside Godot |

Some rows stay. The first row of the areas, the floor types, and the wall
styles is the default of a new chunk. A rename of it is legal, and a
removal is not. `void` and `plain` keep their keys, because the client and the chunk
file format name them. The last roof floor type stays a roof for the Roof
tool.

The class `TableEdits` owns these rules. The class `SourceTable` changes a
row of a fallback table of the client, for example `AreaLook.LOOKS`. The
Python guard fails on a client key that names nothing.

After each change, every list of the dock reads the tables again. The
block draws again. Then the class `ClientExport` runs the client export and
the check fixture builder on a thread. The status box gives the result. The
server reads a new row after a restart.

**Two sources.** The class `TileTables` (`world/terrain/tile_tables.gd`) is
the one GDScript reader of the four tables. In the editor it reads the
table files. Thus, a new row shows at once, with no export and no reload.
The game reads the generated constants, because it must read what its
server reads. For example, the world map sends a floor type as its index in
`TILE_FLOOR_TYPES`. Thus, deploy the client again after a change of a
table. The test `test_tile_tables.tscn` tests the reader, the rules, and
the form, on copies under `user://`.

"Block outside" sets Blocked on the ring of tiles around a room, for a
dungeon. A ring tile with a wall bit is part of another room, and it stays
open.
- **The links show where an object leads.** A transition draws an arc to its
  target, or a stub toward a target outside the block. A climb draws a post
  up or down. The targets and the ways come from
  `blackout/world/object_kinds.py`, through the generated constants. A new
  sign or transition is still one row there (Nick, 09/26/2026).
- **The tile sync stamp.** `sync_tile_objects.py --apply` writes
  `blackout/server/tile_sync_state.json`, a digest of each chunk file. The
  World tab compares the files with it. Git ignores the stamp, because it
  describes the dev database.

The brushes follow the workflow of Low Poly Terrain Builder (MIT). None of its
code is here: its Delaunay mesh cannot give a floor colour to one tile or put a
wall on a tile edge.

## The figure workbench writes figure files, not scenes

DESIGN-0014. The figure workbench is an editor plugin in
`addons/blackout_figure/`, a sibling of the terrain editor. `project.godot`
enables it, and the web export excludes the directory. It makes the rigs and
the bodies of the figures. Phase W1 (10/12/2026) built the Rig tab and the
Body tab. Phase W2 (10/12/2026) built the clips and the Clips tab. Phase W3
(10/12/2026) built the Gear tab, the outfit bar, and the slot shapes. The
bodies and the slot shapes have the low-poly look since 10/12/2026
(DESIGN-0014 section 16). Phase W4 (10/12/2026) built the model parts, the
reference body, the hide list, the fit of a body type, and the figure set.
Phase W5 (10/13/2026) built the palette, the Colors tab, the tiers, and the
stance table. Phase W6 (10/13/2026) built the checks, the Check tab, the
budget line, the kit parts, and the list of the NPC defs. It also gave the
author more tools: the other side of a part, a copy of a part, the rotation
of a socket, the regions of a rig, and a new name for a color. The plan of
DESIGN-0014 has no phase left. The game does not draw a figure yet. The
look layer of ENG-0011 (10/13/2026) added the finishes of the palette, the
Families tab, and the presentation fields of the Gear tab.

To use it:

1. Open `res://addons/blackout_figure/figure_workbench.tscn`, or click
   **Open workbench** on the Figure dock.
2. Select the `FigureWorkbench` node. A mannequin of each body type stands
   on the floor.
3. Click a part in the 3D view. Move it with the Godot tools: W moves, E
   turns, and R scales. The hint line at the bottom of the 3D view names
   the selected part, its look, its bone, and the body type.
4. On the **Rig** tab, select a bone and change its position. The mark on
   the bone is a node: W moves it in the 3D view, and the move goes into
   the rig of that stand. The mirror box applies to the fields only. On
   the **Body** tab, change a part and its shape list.
5. On the **Clips** tab, select a clip. Click **Play** in the play bar
   above the tabs. Each body type plays the same clip, on every tab.
   **Show a held item in each hand** shows if a clip puts an item through
   the body.
6. Press Ctrl+S, or click **Save** in the top strip. The plugin writes
   each changed file to `blackout/assets/figure/`.

The top strip is the first row of the dock. **Save** says how many files
are unsaved, for example "Save (3 changed)". **Revert** reads each figure
file again. It asks first, and the question names each unsaved file. With
no unsaved file, it asks nothing. The terrain editor has the same strip.

Each button says a verb and an object. The full sentence is in its
tooltip. A button that cannot apply is off, and its tooltip gives the
reason: a button that needs a row, the socket rotation of a bone of the
body, or a build that runs now.

The **Body** tab and the **Gear** tab fold their sections: Look, Colors,
Hides, Model, Kit, and Parts. Parts starts open. The session file keeps
the state of each fold.

To give an item a worn look:

1. On the **Gear** tab, pick the row of the item. Each body type then wears
   the item. An item with no worn look shows the slot shape of its slot.
   The text field above the list keeps the rows with the typed text, with
   no regard to the case.
2. Click **New look**. The item gets a copy of the slot shape of its slot
   as its own look.
3. Change the parts, the shape list, and the colors, as on the Body tab. A
   click on the item in the 3D view selects its part.
4. Use the **outfit bar** above the tabs to put an item in each other slot.
   Look for a part that goes through another part.
5. Press Ctrl+S. The look is `blackout/assets/figure/looks/<item key>.json`.

**Copy look** gives the row the parts and the colors of another look. A tier
is a legal source. The list names it "key (a tier of base)", and the copy
takes the look that the tier draws. **Only the rows with no worn look**
lists the items that still show a slot shape.

To give an item a model from a modeler (Phase W4):

1. Select the body type that you model over. Use the outfit bar to dress
   the figure in each item that the new part must fit over.
2. On the **Body** tab, click **Export reference body**, and save the
   `.glb` file.
3. Open the file in a modeler. Model the part where it sits on the body: a
   helm over the head, a chainbody over the torso and the arms. Do not move
   the body. Keep the feet at the origin, +Y up, and the face to +Z.
4. Make one object for each bone that the item must follow. A chainbody is a
   torso object and two arm objects. Give each material the name of a color
   role: `metal`, `trim`, `cloth`.
5. Export only the new objects, as one `.glb` file.
6. On the **Gear** tab, pick the row of the item. Type the author of the
   file, and click **Import model**. The model pipeline builds the model
   on a thread. The status box says "Building ..." until it ends, and the
   button is off. The editor stays usable.
7. Look at the parts in the part editor. Each object is one part, on the
   bone with the name of the object, or on the nearest bone. Change a bone
   there if it is wrong. The part stays where it is.
8. Tick each region that the item covers in **Regions that the look hides on
   each other look**. A chainbody hides `torso` and `arms`.
9. Select the other body type, and click **Fit from bone lengths**. Play
   each clip, and look at each body type.
10. Press Ctrl+S.

The import writes four things in the game directory: the source
`assets/sources/blackout_<key>/`, the model record
`assets/models/<family>/<key>.toml`, the served `.glb`, and
`assets/build.lock.json`. An undo takes the parts out of the look. It does
not remove those files. `blackout/assets/README.md` has the rules of the
command.

The import refuses a key that another model has. An item key can be an alias
in the record of another model, as `rusty_scrap_arrow` is. Take the key out
of that record first. Or type another key in the model field, and the item
keeps its old model in the inventory.

**Parts from model** does step 7 for a model that the served tree has
already. It also reads the served tree again after a build
in a terminal.

To change the fit of one part on one body type:

1. Select the body type on the dock, and select the part.
2. Tick **Own place on this body type (the fit)**. The part does not move.
3. Move the part with the Godot tools on the stand of that body type, or
   change the place fields. The other body type keeps its place.

To make a tier of an item (Phase W5):

1. Give one item of the set its worn look, as above. The slot shape of the
   slot can be that look also.
2. On the **Gear** tab, pick the row of the next tier.
3. Select the look with the parts in the list below **Copy the parts and
   the colors of this look**.
4. Click **Make tier**. The row then draws the parts of that look. Its file
   holds a `base` and no part.
5. Pick a color for a color role in the color table. A `*` marks each role
   with a color of its own. The first choice of a list gives the role the
   color of the base again.
6. Press Ctrl+S.

The color table of a look has one row for each color role that the look can
give a color to: the roles of its shapes, and the material names of its
model. On a look with no base, the first choice of a list is the color of
the palette. Each list shows a mark in the color of each row.

A tier can be the base of another tier. To change a part of a tier, select
the row of the look that has the parts, or move the part in the 3D view.
The change shows on each tier. A look stays while a tier names it as its
base.

To change a color of each look that names it (Phase W5):

1. On the **Colors** tab, pick the named color in the list. The line below
   the finish names each look and each color role that has it.
2. Click the color bar, and pick a color. Each stand shows the change. One
   drag is one undo entry.
3. Select a finish in the list. A shape with a finish of its own keeps it.
4. Press Ctrl+S. The file is `blackout/assets/figure/palette.json`.

The table **Colors of the character on the stands** gives a color role one
named color over each look: a skin color, a hair color. It changes no
figure file.

The **Finishes** section of the Colors tab lists each finish of the palette
(ENG-0011, step L4). A finish is a metalness and a roughness. Pick one to
change its two numbers in the spin boxes. **New finish** adds one with the
name in the field. **Remove finish** refuses while a named color has the
finish. The matte finish stays, because a color with no finish has it. A
finish that the file does not have comes from `MeshPalette.FINISHES`, so an
old palette file reads.

To change the shape of a family with no art (ENG-0011, step L5):

1. On the **Families** tab, pick the family. The list has each item family
   of the server, each family of `families.json`, and each family of
   `FamilyShapes.SHAPES`. A row says where its shape comes from: the file,
   the table, or nothing. The family shows on the stand at the right of the
   figures, as the game draws it.
2. A family with no row has a note. Click **New shape from the fallback**.
   The family gets a row with the parts that it draws now.
3. Change the parts and the shape list in the part editor below, as on the
   Body tab. A family shape has one bone, `root`, and no fit. The stand
   draws each change at once.
4. Type an asset key in the model field and click **Set model** to give the
   whole family a served model. An empty field takes the model out.

**Remove shape** takes the row out, and the family draws its table again.
The file is `world/look/families.json`, a look file of the client. It
writes on each change, as the Look tab of the terrain editor writes. Save
and Revert concern the figure files only. Each change is one undo entry.

To change how the game shows a served model (ENG-0011, step L6):

1. On the **Gear** tab, pick the row of the item. The row needs a served
   model: the model that its look names, or a model with the key of the
   row. The model shows on the stand at the right, with its presentation.
2. Open the **Model** fold. Change the offset, the turn in degrees, or the
   scale. The stand draws each change at once. One drag is one undo entry.

The file is `world/look/presentation.json`. It writes on each change. A
model with no row draws as `ModelRegistry.PRESENTATION` says.

To give a tool type a stance (Phase W5):

1. Use the outfit bar to put the item in the hand of the figure. The stance
   list of the **Clips** tab goes to the tool type of that item.
2. Pick a clip for each action whose clip differs from the default clip
   set. The first choice of a list is the clip of the default clip set.
3. Click **Play** on a row to see the clip of that action on each stand.
4. Press Ctrl+S. The file is `world/figure/stances.json`.

To give a stance an action that the table does not have, type the name of
the action below the stance table. Select a clip in the clip list, and
click **Add action**.

To check the figure files (Phase W6):

1. On the **Check** tab, click **Check the figure files**. One check of the
   files of 10/13/2026 takes 0.2 seconds.
2. Read the list. A finding is a fault. A note is no fault: an item with no
   worn look gives a note, because its slot shape draws.
3. Click a row. The dock shows the file of the finding in its tab, with the
   part, the bone, or the clip selected.
4. Correct the fault, and click **Check the figure files** again.

The **Budgets** fields below the list set four limits: the triangles of a
worn look of each slot, the triangles of a body, and the triangles and the
draws of a dressed figure. The slot table gives one slot its own number.
The line below the body type list is the budget line. It gives the draws
and the triangles of the dressed figure against the budget, and it says
when one is over. The budgets are an option of the workbench, in
`figure_editor.cfg`. They are no figure file.

The check also runs by itself, half a second after the last change of a
file. The list of the Check tab thus never goes stale. The status box
keeps the status of the change.

To make a kit part: a hair shape, a head, a beard (Phase W6):

1. On the **Body** tab, select the bone in the list above **Add a part on
   this bone**. Use `head_top` for a hair shape.
2. Type a key and a kit group below **Kit of the figure on the stands**, for
   example `hair_short` and `hair`.
3. Click **New kit part**. Each stand wears the kit part, and the part
   editor shows it. It starts with one prism, and it hides the region of
   its bone.
4. Change the parts and the shape list, as for a body. Tick each region of
   the body that the kit part takes the place of.
5. Press Ctrl+S. The file is `blackout/assets/figure/looks/<key>.json`,
   with a `kit` key.

**The part editor shows** goes back to the body. **Kit of the figure on the
stands** picks the kit part of each kit group, or the body as it is. It
changes no file.

To make the two sides of a figure the same (Phase W6):

1. Change one part, for example `sleeve_l`.
2. Select it, and click **Mirror part**. The part `sleeve_r` then is the
   mirror picture, on the bone of the other side.
3. On the **Rig** tab, tick **Move the bone of the other side also** before
   you change a position. The bone of the other side follows.

**Copy part** and **Copy shape** make a second one at the same place.

To change the grip of a hand socket (Phase W6):

1. On the **Rig** tab, select the socket: `hand_r` or `hand_l`.
2. Change the three rotation fields. A held item has its length along +Y of
   the socket.
3. Do the same on the other body type, if it must have the same grip.

Only a socket takes a rotation. Each body type shares the rest rotation of
each bone of the body, so one clip moves each of them.

To change a region of a rig (Phase W6):

1. On the **Rig** tab, type the name of a new region, and click **Add
   region**.
2. Select a bone, and pick its region in the list. A new part on that bone
   starts in that region.
3. To remove a region, select a bone of it, and click **Remove region**. A
   region that a look names stays.

To give a named color a new name (Phase W6): on the **Colors** tab, select
the color, type the new name, and click **Rename color**. The palette and
each look that names the color change in one undo entry.

To dress the figure as an NPC def (Phase W6): pick the NPC def in the list
below **Take each item off**. The list has each `NpcDef` with an `outfit`.
The server owns the outfit, so the workbench only shows it. To give an NPC
an outfit, add `outfit={WieldLocation.HEAD: "<item key>"}` to its `NpcDef`,
and run `python scripts/export_client_constants.py` in `blackout/`.

To add a clip from a source that has a clip list:

1. On the **Clips** tab, select the clip list. Click **List source clips**.
   The import step runs on a thread, and the list of the clips of the
   source fills. It writes no clip file. Then select the clip of the
   source.
2. Type the name of the clip in the game, and tick the loop box for a clip
   such as a walk.
3. Click **Put clip in list**, then **Build the clips**. The question names
   each clip file that the build writes over. The build runs on a thread,
   and one build takes about 3 seconds for each clip list.
4. Press Ctrl+S to save the clip list.

| File | Holds |
|---|---|
| `blackout/assets/figure/rigs/<body_type>.json` | One rig: the bones, the sockets, the regions, and the slot table |
| `blackout/assets/figure/looks/<key>.json` | One worn look. The key is an item key, a slot for a slot shape, or a body type for a body. A kit part has its own key, and a `kit` group |
| `blackout/assets/figure/clips/<source_id>.json` | One clip list: the clips that the workbench takes from one source of `blackout/assets/sources/` |
| `blackout/assets/figure/palette.json` | The palette: each named color with its color and its finish, and the named color of each color role |
| `world/figure/clips/<clip>.res` | One clip. The file name is the clip name. The game export holds these files |
| `world/figure/stances.json` | The stance table: the default clip set, and the clip set of each tool type |
| `world/figure/figure_palette.gd` | `FigurePalette`: the reader and the writer of the palette, and the color of a color role on a figure |
| `world/figure/figure_stances.gd` | `FigureStances`: the reader and the writer of the stance table, and the clip of one action |
| `world/figure/figure_rig.gd`, `figure_look.gd`, `figure_json.gd` | The readers and the writers. The game and the workbench use the same classes |
| `world/figure/figure_builder.gd` | `FigureBuilder`: one figure from a rig and a list of worn looks |
| `world/figure/figure_clips.gd` | `FigureClips`: the clip library, the player of a figure, and the pose of one moment of a clip |
| `world/figure/figure_outfit.gd` | `FigureOutfit`: the worn looks of a figure for a worn record. It picks the worn look, the slot shape, or the family shape of each item |
| `world/figure/figure_models.gd` | `FigureModels`: the mesh and the place of each node of each figure model. It does not put a model in the unit box |
| `world/figure/figure_set.gd` | `FigureSet`: the reader of the served `figure.json` |
| `blackout/web/static/webclient/models/figure.json` | The figure set: each rig, each worn look, and the palette in one served file. Generated, so never edit it by hand |
| `addons/blackout_figure/figure_reference.gd` | `FigureReference`: the reference body file |
| `addons/blackout_figure/figure_pipeline.gd` | `FigurePipeline`: starts `python -m assets.pipeline` of the game directory |
| `addons/blackout_figure/figure_job.gd` | `FigureJob`: one pipeline run on a thread, polled from `_process` |
| `addons/blackout_figure/play_bar.gd` | `FigurePlayBar`: Play, Pause, Rest pose, the time slider, and the speed, in the top bar of the dock |
| `addons/blackout_figure/figure_editor.cfg` | The budgets: the one option that git tracks |
| `user://blackout_figure_session.cfg` | The session of the dock: the body type, the outfit, the colors and the kit of the character, the author, and the folds. Git tracks none of it |
| `addons/blackout_figure/item_catalog.json` | The item catalog: each item with a slot, each slot, each tool type of the server, and each NPC def with an outfit. Generated, so never edit it by hand |
| `addons/blackout_figure/figure_checks.gd` | `FigureChecks`: the content rules of the figure files, and the budgets |
| `addons/blackout_figure/check_panel.gd` | `FigureCheckPanel`: the Check tab |
| `addons/blackout_figure/figure_shapes.gd` | `FigureShapes`: the part rows of a new body and of each new slot shape. A start for the author, not the design |
| `addons/blackout_figure/edits/` | The edit rules, one script for each file that a rule changes: `FigureRigEdits`, `FigurePartEdits`, `FigureShapeEdits`, `FigureLookEdits`, `FigurePaletteEdits`, and `FigureClipEdits`. Each rule changes a copy of the content and returns the reason for a refusal, or "". `figure_edits.gd` keeps `FigureEdits` as a forwarder, for the tests only |
| `addons/blackout_figure/handlers/` | The handlers of each tab of the dock, one script for each tab, plus `FigureHistory` (the undo seam: one entry for one file, or for several files) and `FigureHandlerContext` (what a handler may reach of the plugin). `figure_plugin.gd` keeps the editor contract only: the dock, the selection, the hint, the save, the jobs, and the refresh of each tab |
| `addons/blackout_figure/` | The plugin, the dock, the store, the edit rules, the catalog reader, the clip build, and the clearance check. The editor only |

The rules that the workbench keeps:

- **The scene holds no figure.** The workbench makes each node of a stand at
  load, and the node has no owner. The figure files are the only store.
- **What the author sees is what the player sees.** The stands come from
  `FigureBuilder`, the class that the game uses.
- **A part is one rigid mesh on one bone.** It has no weights and no skin.
  Its node sits below the `BoneAttachment3D` of its bone.
- **A click selects a part by code.** The editor does not select a node
  with no owner on a click. The plugin finds the part below the mouse with
  `FigurePicking`, and it selects that node. The Godot gizmo then moves it.
- **A refresh keeps each node.** `FigureBuilder.refresh` changes a figure in
  place. The undo entry of a gizmo names the node, so a new node for each
  change would break that entry.
- **The node is the place of a part while a gizmo moves it.**
  `FigureWorkbench.sync_from_nodes` reads each part node each frame, and it
  writes a moved one into its worn look. An undo of the editor moves the
  node back, and the same routine writes the old place. The bone mark of
  the Rig tab goes the same way: a moved mark writes the position of the
  bone on its parent into the rig of its stand.
- **A change from the dock is one undo entry of the plugin.** It gives the
  old or the new content of one file to `FigureWorkbench.put`. A field that
  the author drags makes one entry.
- **The same content gives the same bytes.** `FigureJson` sorts the keys,
  keeps five digits of each number, and writes a count as an integer. A
  parsed JSON number is a float, so a reader that keeps `1.0` for `format`
  changes the file on each save.
- **A file is unsaved only while its text differs from the disk.** An undo
  back to the saved content leaves nothing to save.
- **A file that does not read stays out of the store.** The status box names
  it, and the store refuses new content for its key. A save thus never
  writes over it.
- **A fault does not stop a figure.** A part on a bone that the rig does not
  have draws nothing, and each other part draws.
- **A look hides a region of each other look, not of itself.** The parts of
  a chainbody take the place of the torso that it hides.
- **A check finds what a figure hides.** A fault does not stop a figure, so
  nothing reports it in the 3D view. `FigureChecks.run` has one rule for
  each such fault. `test_figure_checks.tscn` runs it on a fixture with one
  fault for each rule, and on the figure files of the repository.
- **The check of the server names is in two places on purpose.** The item
  catalog gives the workbench each item, each slot, and each tool type. The
  Check tab thus shows a wrong name at once. `test_figure_files.py` owns
  the same rules in the Python suite.
- **A kit part is a worn look with a kit group.** The kit groups are the
  groups that a look names, so no table lists them. `FigureOutfit.looks_for`
  puts the kit of a character after the body. The server names a kit part
  by its key only.
- **A change of one name in several files is one step.**
  `FigureWorkbench.put_many` gives each file its content, and the stands
  then draw one time. With one `put` for each file, a stand draws a name
  that one file does not have yet.
- **Each body type has the same bones and the same rest rotations.** Only the
  positions differ. One clip then moves each body type.
- **A shape of a figure has low counts.** With no `segments` and no `rings`,
  a shape gets the defaults of `FigureLook`. The web export pays for each
  draw and each triangle of a crowd.
- **A figure is made of prisms.** A prism is a tapered block with flat
  faces: `SHAPE_PRISM` of `MeshBuilder`. Each face has one shade, and each
  shape is matte. A body, a blade, and a shield use this one shape.
- **The look file is the design. The table is a start.** `FigureShapes` has
  the part rows of a new body and of each new slot shape. A look file holds
  plain shapes, and the author changes each one on the Body tab or the Gear
  tab. Two buttons write a table again and drop each change of the author:
  **New body**, and **New look** on the row of a slot shape.
- **The default clothes of a body are color roles of the body.** A sleeve is
  in the `torso` region, the hips part is in the `legs` region, and a boot
  is in the `feet` region. A worn look that hides a region thus hides the
  clothes there.
- **The slot shape of a body slot hides its regions.** The `body`, `legs`,
  `feet`, and `head` slot shapes take the place of the body parts below
  them. `FigureShapes.SLOT_HIDES` names the regions.
- **A new rig has wide shoulders and short arms.** `FigureRigEdits.ARM_PLACES`
  gives the place of each arm bone, in place of the humanoid profile.
- **The slot names come from the server.** The slot table of a rig has one
  row for each `WieldLocation` value. `test_figure_files.py` compares the
  two, because GDScript cannot import the enum.
- **One clip is one file.** `FigureClips.library()` reads each file of
  `world/figure/clips/`. No table names a clip.
- **A clip finds its skeleton by a unique name.** Each track has the path
  `%GeneralSkeleton:<bone>`, as the retarget of the Godot editor import
  writes it. `FigureBuilder` makes the figure node the owner of the
  skeleton, and `FigureClips.player_of` puts the player on the figure node.
- **A clip holds a rotation for each bone, and one position: the hips.**
  The hips position is a part of the hips height.
  `FigureRig.motion_scale()` is that height, so one clip puts the hips of
  each body type at the correct height.
- **The clip build bakes each clip to the rig of the figure.** The retarget
  of the editor import renames the bones. A source rig can lack a bone of
  the figure, and a rotation then lands on the wrong parent. The KayKit rig
  has no shoulder, and its arms crossed the chest. `clip_extract.gd` copies
  each turn in the space of the skeleton.
- **The game project never holds a clip source.** The build copies the
  source file into a temporary project in the cache directory of the OS,
  and it starts Godot two times on that project.
- **A build writes over a clip that a clip list names.** To keep a change
  from the Godot animation editor, take the clip out of its clip list.
- **A held item has its length along +Y of the hand socket.** The rest
  rotation of each hand socket is the grip. A blade then points forward
  when the arm hangs, and not down through the leg.
- **A clip must hold an item clear of the body.** `FigureClearance` holds a
  probe in each hand, 0.9 units long, and it measures the gap to each body
  part through the clip. `test_figure_clips.tscn` fails on a clip of the
  repository with a gap below zero.
- **A skeleton outside the scene tree gives an old global pose.** A reader
  of `FigureClips.pose` uses `FigureClips.global_pose`.
- **An item draws from one of three sources, in a fixed order.**
  `FigureOutfit` takes the worn look of the item, then the slot shape of its
  slot, then the family shape of `FamilyShapes`. The game and the workbench
  use that class. Thus, a new item draws with no worn look and no client
  edit.
- **The key of a worn look says what it is.** An item key is the look of an
  item. A slot is a slot shape. A body type is a body. `test_figure_files.py`
  refuses each other key, and it refuses an item with the key of a slot.
- **The server owns the item catalog.** `export_client_constants.py` renders
  `item_catalog.json` from `ITEM_DB` and the slot constants. Run it after a
  change to an `ItemDef` with a `use_slot`. A test fails on a stale file.
- **The outfit is no figure file.** It is the worn record of the workbench.
  A save does not write it, and it makes no undo entry. The dock keeps it in
  the session file.
- **The session is no file of the repository.** The dock keeps the selected
  body type, the outfit, the colors and the kit of the character, the
  author of the last model import, and the fold state of each section in
  `user://blackout_figure_session.cfg`. Git tracks none of it. Only the
  budgets stay in `addons/blackout_figure/figure_editor.cfg`, because a
  budget is a rule that the team shares. A test sets `persist` to false, so
  it writes no file of either kind.
- **A pipeline run never freezes the editor.** The model import, the clip
  build, "List source clips", and the served `figure.json` after a save run
  on a thread (`FigureJob`). The plugin polls the job from `_process`. One
  job runs at a time, and the button that started it is off until it ends.
  Each routine that a job runs stays a plain routine, so a headless test
  calls it with no thread.
- **An empty selection keeps the dock alive.** The plugin selects the
  workbench node again when the selection goes empty. When another node is
  selected, the status box says what to select.
- **An item empties each slot that it clears.** The catalog carries
  `SLOT_CONFLICTS` of the server, so the outfit bar holds only an outfit
  that a character can wear.
- **One part editor serves each worn look.** `FigurePartsPanel` is in the
  Body tab and in the Gear tab. Each handler of the plugin gets the look of
  its tab.
- **One worn look shows on each stand.** A part of it has one node on each
  stand. `sync_from_nodes` finds each moved node before it writes. If not,
  the node that did not move writes its old place back.
- **A label in a grid does not wrap.** A label that wraps has no least
  width, and a `GridContainer` gives it the width of one letter. Use
  `FigureFields.cell_label` there.
- **The file of a figure model is in figure space.** The feet are at the
  origin, +Y is up, and the face is to +Z. `FigureModels` keeps the size and
  the place of each node. `ModelLoader` puts each other model in the unit
  box, and a part must skip that step.
- **One node with a mesh is one part.** `FigurePartEdits.parts_from_model` makes
  the parts. The place of a part on its bone is the place of its node in
  the file, seen from the rest pose of that bone.
- **A look names a model by its asset key, and a node by its name.** It
  holds no path. The manifest gives the file.
- **A shape list draws until its model is in hand.** A part can have the
  two. A part whose model or node is not there draws its shape list.
- **The name of a material is a color role.** A role of the color table of
  the look gets a palette color. Each other surface keeps the material of
  the model. One color role must be one material in the modeler: the glTF
  writer of Godot gives a second material with one name a number.
- **One look serves each body type, and a fit row is the exception.**
  `FigureLook.place_of` gives the place of a part on one body type. A move
  on a stand goes into the fit row when the part has one for that body
  type. If not, it goes into the part.
- **The import uses the rig of the selected body type.** Select the body
  type whose reference body the model was made over. The fit from the bone
  lengths then takes the lengths of the other body type as the start.
- **A save writes the served `figure.json` again.** The plugin runs
  `python -m assets.pipeline figure-set` after a save of a rig or of a worn
  look. The check of the model pipeline fails on a stale file.
- **In the editor, the glTF writer leaves out a node with no owner.** The
  reference body gives each node the root as its owner. No headless test
  runs as the editor, so `test_figure_models.tscn` holds the owner.
- **A drag in the 3D view with no part below it clears the selection.** The
  plugin then selects the `FigureWorkbench` node again, so the dock stays
  alive. A click on no part does the same.
- **An outfit holds no two items that clear each other.**
  `FigureCatalog.valid_outfit` puts each entry in through `wear`, in the
  order of the slots. A saved outfit or an NPC outfit thus cannot hold two
  hands and a main hand. The later slot of the order wins.
- **A color has three names, in a fixed order.** A shape names a color
  role. A look gives the role a named color. The palette gives the named
  color its color and its finish. `FigurePalette.named_for` takes the color
  of the figure, then the color of the look, then the color of the role in
  the palette, then the role itself as a named color.
- **The palette file is the design. `MeshPalette` is the start.** A new
  palette takes each color from `MeshPalette`. A named color that the
  palette does not have still draws with the color of that table, so a
  family shape keeps its colors.
- **A finish belongs to a named color.** A shape with a `finish` key keeps
  that finish. Each other shape, and each surface of a model, has the
  finish of its named color. A new palette is matte.
- **A tier has a base and no part.** `FigureLook.resolved` gives the look
  that a figure draws: the parts and the fit of the last base, the colors
  of the tier over the colors of each base, and each hidden region of each
  base. `FigureOutfit` gives the builder only such looks.
- **A tier can hide more, not less.** A region that a base hides stays
  hidden. Its box on the Gear tab has a tick that the author cannot change.
- **A move of a part of a tier goes into the look with the parts.**
  `FigureWorkbench.parts_owner` names that look. Each tier of it follows.
- **A tier whose base is not there draws no part.** The figure still draws.
  The note of the Gear tab gives the reason, and `test_figure_files.py`
  fails on such a file of the repository.
- **The colors of the character are no figure file.** They go to the
  builder as its `figure_colors`, over the color table of each look. The
  game gives the skin and the hair of a character the same way. The dock
  keeps the table of the workbench in the session file.
- **A stance names only what differs.** `FigureStances.clip_for` takes the
  clip of the stance, then the clip of the default clip set. An action with
  no clip leaves the figure in its rest pose.
- **The first worn item with a stance decides.** `FigureStances.stance_of`
  takes the tool type of each worn item, in the order of the slots. No slot
  name is in GDScript for this rule.
- **The tool types come from the server.** The item catalog carries the
  `tool_type` of each item. `test_figure_files.py` compares each key of the
  stance table with the tool types of the server, and each clip name with
  the clip files.
- **The stance table is beside the clips, not beside the looks.** It names
  clip files, and the export holds the two. The store of the workbench
  takes its path from the clip directory.
- **The editor runs no static initializer of a script with no `@tool`.**
  `FigureBuilder` had an empty palette in a static variable, and that
  variable was null in the editor. No headless test shows this. Make such a
  value in a routine, or give the script `@tool`, as `FamilyShapes` has.

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
on PATH on this machine. The 4.7.2 build lives in an extracted folder that has
the name `...exe` itself, so the binary path repeats:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --path godot
```

Log in through the form at the top of the game log, or type the same thing
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

All seventy-nine tests are headless and exit non-zero on failure.
Seventy-six need nothing running (counted 10/12/2026). Three of the four `smoke_*` scenes need an Evennia, and
none needs an account. `smoke_console` is the exception: it builds
`console.tscn` for real and needs nothing, because the test expects its socket
to fail.

Two of them guard the SCENE, not a model, and that is the gap that every other
test leaves:

| | Catches |
|---|---|
| `smoke_console` | A `%UniqueName` that no longer resolves, a node whose type changed, a theme that came unattached. Every other test builds its subject in code, so a scene edit is invisible to all of them |
| `test_theme` | A `theme_type_variation` a script names and `ui/blackout_theme.tres` does not declare. The control silently falls back to the default style, which reads as a styling mistake rather than a typo. Also an item that its class does not read, such as `LineEdit/colors/background_color` |
| `test_theme_preview` | A theme type that the Theme editor preview does not show or name. Each type needs a control that the picker can select |

> **After you add a `class_name`, run `--headless --path godot --import` one
> time before you run anything headless.** Global class names live in
> `.godot/global_script_class_cache.cfg`, which an editor scan rebuilds and git
> ignores. A plain `--headless` run does not rebuild it. Thus, a brand-new
> `class_name` fails as `Identifier "..." not declared in the current scope`.
> That reads like a typo, but it is not one. A fresh clone needs this step too.

`test_world_state.tscn` needs **nothing running**. Its payloads are hand-built
in the shape that Godot's JSON parser produces:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_world_state.tscn
```

`test_choose_option.tscn` needs nothing running. The payloads are hand-built in
the shape that `serialize_entity` produces, floats included. The menu is a
plain `Control`, driven with no camera and no pool:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_choose_option.tscn
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
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_world_view.tscn
```

The HUD layout has three scenes, and each needs nothing running.
`test_hud_layout` checks the rules with numbers only. `test_hud_arranger`
checks the placement with plain controls. `test_layout_editor` checks the
drags, the settings bar, the presets, and that no key reaches the console
while the editor is open:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_hud_layout.tscn
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_hud_arranger.tscn
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_layout_editor.tscn
```

The Help pane has one scene, and it needs nothing running. `test_help_view`
sizes the pane from the narrowest dock to 2000 px. At each width, it checks that
no label passes the right edge, that the rows ask for no width, and that the
rows stack when the pane is narrow:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_help_view.tscn
```

The two maps have four scenes, and each needs nothing running.
`test_minimap_view` checks the cell maths at each zoom, the dots, and the
settings. `test_entity_roster` checks the entity model. `test_world_map_state`
decodes hand-built summaries. `test_world_map_view` checks the pan, the zoom,
and the planes:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_minimap_view.tscn
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_entity_roster.tscn
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_world_map_state.tscn
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_world_map_view.tscn
```

`test_step_animator.tscn` needs nothing running either, and no scene and no
clock. Each case gives `advance` the frame time it wants to measure:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_step_animator.tscn
```

Every bug it catches is SILENT. A figure that drifts a tile behind the server,
a teleport drawn as a walk through a wall, and a walk that runs at a different
speed on a different frame rate all look like an animation. Each one makes the
client tell the player something the server did not say.

`test_area_look.tscn` needs nothing running either. It checks the fog and light
table of each area (`AreaLook.LOOKS`), the blend between two areas, and the fog
that moves with the camera arm:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_area_look.tscn
```

`test_chunk_file.tscn` needs nothing running either. It is the GDScript half of
the chunk file parity test. It reads the fixtures in
`blackout/systems/core/tilegrid/tests/fixtures/`, writes each one back byte for
byte, matches the committed digests, and refuses the same bad files as
`test_chunkfile.py`:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_chunk_file.tscn
```

Four tests cover the terrain editor, and none needs anything running.
`test_chunk_mesh.tscn` proves that the mesh builder draws the ground that
`surface_height` reads. `test_terrain_editing.tscn` covers the brushes, the
seams, and undo. `test_terrain_world.tscn` loads and saves a block in a scratch
directory under `user://`, never in `blackout/world/chunks/`. It also covers
the planes of one block. `test_structure_tools.tscn` covers the Build tools
and drives one gesture of each through `BuildInput`. `test_roof_shapes.tscn`
covers the corner heights of each roof shape. `test_structure_template.tscn`
covers the templates, the tile selection, and the Place tool.
`test_structure_workbench.tscn` covers the structure workbench in a scratch
directory, and it never touches a world file:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_terrain_editing.tscn
```

Eight tests cover the figure workbench, and none needs anything running.
`test_figure_rig.tscn` and `test_figure_look.tscn` read each file, write it,
and compare the bytes. They also give each bad file that the readers refuse.
`test_figure_builder.tscn` covers the figure: each part on its bone, the
hide list, and the nodes that a refresh keeps. `test_figure_edits.tscn`
covers the rules of the Rig tab and the Body tab.
`test_figure_workbench.tscn` covers the store, the stands, the pick, and a
part that a gizmo moved. It writes only into a scratch directory under
`user://`, and it reads the figure files of the repository.
`test_figure_dock.tscn` covers the signals of the dock:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_figure_workbench.tscn
```

`test_figure_clips.tscn` covers the clips: the player, the pose of one
moment, the clip list, the clearance check, and the clips of the workbench.
It also reads each clip of the repository. Each one must move only bones of
each rig, and it must hold an item clear of the body.
`test_figure_clip_import.tscn` runs the clip build. It starts Godot again
for each build, so one run takes about 9 seconds. The `T-Pose` clip of the
source must give the rest pose of a figure, and each clip file of the
repository must have the bytes of a new build:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_figure_clip_import.tscn
```

`test_figure_models.tscn` covers Phase W4: the reference body, the parts of
a model, the color roles of a model, the fit of a body type, and the figure
set. A reference body goes out as a file and comes back as a model, and
each part must sit where its author made it. A chainbody model must hide
the torso and the arms on each body type, through each clip of the
repository. It also reads the served `figure.json`, which must hold each
rig and each worn look of the repository:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_figure_models.tscn
```

`test_figure_palette.tscn` covers Phase W5: the palette, the colors of a
figure, and the tiers. Three tiers of one item must draw from one slot shape
and three small files. It also reads the palette of the repository, which
must hold each color that a look names. `test_figure_stances.tscn` covers
the stance table. Each clip that the stance table of the repository names
must be a clip file:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_figure_palette.tscn
```

`test_terrain_view.tscn` covers the ground of the client: one mesh for each
chunk of the model, a mesh built again for a chunk sent again, and no mesh for
a freed chunk. It also covers the walls layer, the props layer, and the
scenery. `test_wall_mesh.tscn` covers the wall slabs. `test_prop_mesh.tscn`
covers the primitives and their rotation.

`test_char_state.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_char_state.tscn
```

`test_model_registry.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_model_registry.tscn
```

`test_model_loader.tscn` needs nothing running. It checks that one read
holds the largest served model, and it checks which failed fetches get a
retry:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_model_loader.tscn
```

`test_inventory_state.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_inventory_state.tscn
```

`test_inventory_view.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_inventory_view.tscn
```

`test_summary_state.tscn` needs nothing running either:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_summary_state.tscn
```

`test_skills_state.tscn` and `test_skills_view.tscn` need nothing running
either. The view test asserts two things that a screenshot would not catch.
Every command that leaves the pane is one that the server named. Each of the
three detail modes asks for exactly what it shows.

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_skills_view.tscn
```

`test_xp_tracker_state.tscn` and `test_xp_hud_view.tscn` need nothing running
either. The tracker's clock is a Callable that the test moves by hand, so the
test measures an hour of XP per hour in milliseconds. The view test proves that
the HUD is hidden before an award, and that no control in it takes the mouse.

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_xp_hud_view.tscn
```

`test_combat_options_state.tscn` and `test_combat_options_view.tscn` need
nothing running either. The view test asserts that every command that leaves
the tab is the one that its row carried, and that a click alone never moves the
highlight:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_combat_options_view.tscn
```

`test_login_view.tscn` and `test_saved_login.tscn` need nothing running
either. Both write only to a scratch file under `user://`:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_login_view.tscn
```

`test_command_history.tscn`, `test_client_settings.tscn`,
`test_scrollback_find.tscn`, `test_server_endpoint.tscn`,
`test_movement_keys.tscn`, `test_held_movement.tscn` and
`test_reconnect_policy.tscn` need nothing running either:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_command_history.tscn
```

`test_sound_cues.tscn` needs nothing running either. A headless run uses the
dummy audio driver, so the test plays every cue for real with no speaker
attached:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_sound_cues.tscn
```

`smoke_reconnect.tscn` needs a running Evennia but no account. It proves the
one thing that `test_reconnect_policy` cannot: `Evennia.open()` is callable a
second time. A `WebSocketPeer` at STATE_CLOSED is a used object, so the client
builds a fresh peer for each open. That change looks obviously correct, but
only a real server can confirm it.

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/smoke_reconnect.tscn
```

`smoke_handshake.tscn` needs a running Evennia but no account. The server
answers `blackout_subscribe` on an unauthenticated session:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/smoke_handshake.tscn
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
`AreaLook.LOOKS`. A category named there that no skill declares is a bug, and
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

Since Phase 5 (09/25/2026), the minimap draws the chunks that [WorldState]
holds for the 3D pane. A walkable tile shows the colour of its floor type,
from `FloorPalette`, the palette of the 3D ground. A blocked tile or a water
tile shows that colour darker. `MapRaster` owns that rule, and the world map
uses it too. **The console owns the model**, so the client parses each chunk
one time for both panes.

Since 09/28/2026, the minimap follows the OSRS minimap:

| Part | What it shows | From |
|---|---|---|
| Zoom | 8 to 40 tiles on each side of the player. The mouse wheel, or the `-` and `+` buttons. The zoom is kept in `ClientSettings.minimap_radius` | `MinimapView.ZOOM_RADII` |
| You | A white square on your tile | `WorldState.current_cell` |
| Map dots | White for another player, yellow for an NPC, red for an item on the ground | `EntityRoster`, `MinimapView.DOT_COLOURS` |
| Map icons | A symbol for a bank, a node, a transition, a ladder | the chunk objects, `MapIcons` |
| Destination marker | A red flag on the goal tile of the walk. A held key shows none | `blackout_walk` |
| Walk path | A line through the tiles still to walk. A box in Options, and no button on the minimap (Nick, 09/28/2026: less clutter) | `blackout_walk`, `ClientSettings.show_walk_path` |
| World map | The `Map` button opens the world map | `WorldMapView` |
| Run | A toggle in the top-left corner of the map square, as the OSRS run orb | `blackout_walk` `running` |

Four rules hold it together:

- **The entity rows have a model now.** `EntityRoster` takes the four entity
  channels from the console. `WorldView` forwards each roster signal to the
  same `EntityPool` call as before, and the minimap reads the rows. The
  handoff debt "the minimap draws no entities" is paid.
- **The server sends the walk.** `blackout_walk` carries the goal, the whole
  path, and the room Z. It goes one time, when the walk starts, and again
  when it ends or breaks. `WorldState` drops each tile of the path as the
  player steps on it or skips it in a run. A typed `goto` shows a marker too, because the server
  sends every walk (Nick, 09/28/2026).
- **The dots stop at 10 tiles.** The feed sends the entities within
  `STATEFEED_ENTITY_RADIUS`. At a wider zoom, no dot shows past that ring. The
  map icons come from the chunks, so they show at every zoom.
- **Each chunk is one image.** The minimap builds an `ImageTexture` for each
  chunk when it arrives, and draws the part that the window covers. It does
  not draw one rect for each tile. The dots redraw on every entity message.

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

**`movetext` chooses what a step prints.** A step prints the room name, the
description, the exits, the Characters line and the You see line. The player
can turn off each part: `movetext exits off`. `movetext` lists the parts, and
`movetext reset` turns all of them on again. The default shows every part.

The choice applies to a step only. A typed `look` always shows the whole room.
`Character._look_on_arrival` gives the hidden parts to the look as a kwarg,
and `GridTile` leaves out each part that the kwarg names.
`systems/interface/ui/move_text.py` owns the parts.

The Options tab has an On and an Off button for each part, and `?` and
`All on` buttons. `MOVE_TEXT_LABELS` in `options_view.gd` holds a server key
and a client label for each row. `test_move_text_client.py` fails on a key that
names no part.

## The world map is every chunk, drawn small

The world map (09/28/2026) follows the OSRS world map. It is a large box over
the world pane, and it shows every chunk of one plane:

- the ground, one pixel for each tile at the closest zoom,
- a map icon for each chunk object,
- the name of each area,
- your tile, the destination marker, and the walk path,
- the tile under the cursor, as `(x, y)`, for a player who types `goto x,y`.

A drag pans, and the mouse wheel zooms around the cursor. `Up` and `Down`
change the plane, `Me` centres on you, and `X` or Esc closes it. **A click
walks nowhere** (Nick, 09/28/2026). A walk across the world can hit the limit
of the A* search, so a click that walked would often fail.

**The server sends a summary, not the chunk file.** The client holds only the
block around the player, so it cannot draw the world by itself. The `worldmap`
command asks for it. The server sends the index on `blackout_world_map`: the
planes, every chunk, and one label for each area. Then it sends one world map
summary for each chunk on `blackout_world_map_chunk`. A summary holds one
character for each tile, so a chunk costs about 4 KB, not 35 KB. The server
sends a summary one time for each session, and `WorldMapState` keeps it.
`blackout/systems/interface/statefeed/worldmap.py` owns the encoding, and
`MapRaster.class_colour` decodes it.

**The button sends the command.** The `Map` button opens the box at once. The
first time, the client holds no world map, so the button also sends
`WORLD_MAP_COMMAND`, the word that the server named. A typed `worldmap` opens
the box when the index arrives. A telnet session gets a text overview of its
plane instead (`blackout/world/tile_world_map.py`).

**It is a sibling box of the world pane.** `console.gd` builds it in code, as
it builds the pop-up. It sits over the docks and under the right-click menu
and the veil. `smoke_console` checks that order.

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

### The chat interface (09/29/2026)

The model is the OSRS chat interface. Nick made four choices:

1. **The buttons sit under the input:** All, Game, Combat, Local, Private,
   Channel. Game takes every line that is not chat or combat, untagged lines
   too. Local is the OSRS Public tab. Nick renamed it, because the default
   Evennia channel is also named Public. `ChatTabs.DEFAULT_TABS` is still the
   whole table.
2. **A right-click on a button** offers "Set chat mode" for each mode whose
   lines the tab shows, and "Show in All". The settings file keeps both.
3. **The server names the chat modes** on `char_chat`. The client names no
   mode except Command.
4. **A typed line goes to the chosen mode.** A line that starts with `/` goes
   out as a command in every mode.

**The server names each mode, and the client names one.** Each row of
`char_chat` is `{key, label, type, prefix}`. The builder is
`blackout/systems/interface/statefeed/chat.py`:

| Mode | Prefix | Type |
|---|---|---|
| Say | `say ` | `say` |
| Yell | `yell ` | `say` |
| Reply | `page/reply ` | `page` |
| One row for each channel that the player listens to and can send to | `@channel <key> = `, from the nick replacement of the channel class | `channel` |

`ChatModes.command_for` adds the typed text to the prefix. The console sends
the result through `Evennia.command`, so a chat line is a line that a telnet
player could type. Every lock and cooldown of the command still applies.
Command, the empty key, sends the line as it is. It is the default, and it is
the one mode that the client owns.

**A mode goes on the tab that shows its type.** The bar asks
`ChatModes.modes_for_types` with the types of the tab. Thus, a new channel
shows under Channel, with no client edit. All shows every mode.

**The server decides who hears a say or a yell** (10/05/2026). A say
reaches each person that the client draws, on the plane of the speaker. A
yell reaches the area of the speaker, on every plane. A yell line has the
`say` type. Thus, the Yell mode and its lines go on the Local tab, with no
client edit. The rules are in `blackout/systems/gameplay/speech/`.

**`page/reply` exists for the Reply mode.** Evennia's `page` reads the first
word as a target when an account has that name. A chat mode that sent
`page <text>` could thus page the wrong account. `page/reply` in
`blackout/commands/comms_cmds.py` sends to the last page partner and reads no
target. The same command tags every page line `page`, so a page reaches the
Private tab.

**The input hint names the mode.** In Command mode the hints are as before.
In a chat mode, the map hint reads "Press Enter to chat in Say", and the
typing hint names the mode and the slash. The console reads the hint again
on each change of `ChatModes`.

**The chosen key outlives the payload.** The settings file loads before the
server sends the modes, and a channel can go away. `ChatModes` keeps the
wanted key and gives Command until a mode with that key exists. Thus, the
login line is never sent as a chat line.

**"Hide from All" draws All again.** A log that only appends cannot remove a
line. `ChatView` keeps the source of each line, capped at `MAX_LINES`, and on
a filter change it draws All again with one `append_text`. A filter change is
rare, so the one full parse costs nothing that a player feels. A tab switch
still draws nothing again.

## XP drops ride an event; the session is the client's

The HUD sits just left of the minimap, right-aligned against it, where OSRS
keeps its XP counter. It draws only after the player earns something. It shows
these parts:

- A strip that reads `session 12,345 xp   3,420 xp/hr`
- A continuous bar for the skill just trained (`strike 42 → 43 · 1,120 to go`).
  It glides to each new value, like the HP bar.
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

## Hitsplats: the server names the max hit

A hitsplat is the damage number over a figure. Each `blackout_combat` payload
gives one hitsplat. The payload goes to the attacker, the target and the room.
Thus, everyone in the fight sees the same hitsplat. `world/hitsplats/` holds
the code.

| Kind | Shows on | Style file |
|---|---|---|
| hit | a swing that connected, 0 included | `styles/hit.tres` |
| max hit | a swing that rolled the top face of its damage die | `styles/max_hit.tres` |
| miss | a swing that missed | `styles/miss.tres` |

**To change the look, edit a style file.** Double-click it in the FileSystem
dock. The Inspector shows four groups: Number, Detail line, Motion and
Placement. Each field has a tooltip. Save, and the next hitsplat uses the new
values. No script changes. `HitsplatStyle` documents each field.

**The server decides which swings are max hits.** `ActionResult.is_max_hit`
compares the ROLL with the top face of the die, before the damage channel. A
weapon with its own die has the top face of that die as its max hit. Thus, a
natural 20 is the max hit of the toy sword. The payload carries `max_hit`
and `max_hit_roll`. The roll is 0 on every other swing, so the client never
learns a max hit that the hit line does not show.

**A bonus or a penalty after the roll gets a detail line.** The number shows
the damage, and the line under it shows `MAX 14 +3 BONUS`. Thus, the player
sees why the number is not the max hit. The hit line in the log says the same
thing: `You hit Raider for [17]! (max hit 14 +3 bonus)`.

**The text keeps one size at every zoom** (`fixed_size`), as OSRS does. The
text stands on its point and grows up, so it never covers its figure. The
gap of the detail line is in font pixels for the same reason.

**A hitsplat stands in the world, not on its figure.** A killed NPC deletes
its figure in the same tick. A hitsplat on that figure would go with it, and
the killing blow is the hitsplat that a player most wants to see.

`test_hitsplat_layer` needs nothing running. It reads no colour, size or time
from a style file, because those are look decisions:

```bash
"/c/Users/NickR/Games/Projects/Godot/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe" --headless --path godot res://tests/test_hitsplat_layer.tscn
```

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

**A moment is that event.** The `blackout_moment` channel sends one moment
name, for example `task_complete`, to the player of the moment. `MomentFeed`
turns each message into its `happened` signal. The `_MOMENT_CUES` table in
`sound_cues.gd` maps the moment to a cue. The server names no clip. A new
moment needs three edits:

1. Add a `MOMENT_*` constant and its `MOMENTS` entry in `statefeed/constants.py`.
2. Add its export row in `clientexport.py`, and run `export_client_constants.py`.
3. Call `events.emit_moment` where the moment occurs.

A sound for it is one more row in `_MOMENT_CUES`. A moment with no row plays
nothing.

The last kill of an Exterminator task is the first moment.
`ExterminatorHandler._complete` sends `task_complete`, and the client plays
`task_complete.wav`.

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
| `scenes/world.tscn` | The 3D scene: environment, light, terrain, marker, camera rig. |
| `world/world_state.gd` | The world model: the chunks of the block, the room, and the float boundary. |
| `world/terrain/terrain_view.gd` | The ground of the tile world: one mesh for each chunk that the model holds, with its water, walls, and scenery. |
| `world/terrain/wall_mesh_builder.gd` | The wall slabs of one chunk. The editor uses it too. |
| `world/terrain/wall_palette.gd` | The colour of each wall style. A style with no row draws in the colour of `plain`. |
| `world/terrain/prop_mesh_builder.gd` | The primitive scenery of one chunk: ladders, stairs, hatches, the tops of flights, and the decor shapes. The editor uses it too. |
| `world/char_state.gd` | YOUR model: entity id, hp, in_combat, skill levels. |
| `world/model_registry.gd` | Which assets have art (fetched) and how each is oriented (not). |
| `world/meshes/mesh_palette.gd` | Colors and finishes. One owner for both. |
| `world/meshes/family_shapes.gd` | What each family looks like, as data. One entry per family. |
| `world/meshes/mesh_builder.gd` | Part data to a Node3D. Knows no family names. |
| `world/meshes/model_loader.gd` | The only file that knows HTTP and glTF exist. |
| `world/meshes/mesh_resolver.gd` | The mesh ladder. The only thing panes call. |
| `world/figure/` | The rig reader, the worn look reader, and `FigureBuilder`. The figure workbench uses them. The game does not draw a figure yet. |
| `world/inventory_state.gd` | Carried grid and worn slots. |
| `scenes/inventory/inventory_view.gd` | Draws the grid and the paper doll; turns a gesture into a command. |
| `scenes/inventory/slot_cell.gd` | One frame. Drag/drop is Godot's engine API, not hand-rolled. |
| `scenes/inventory/stack_count_label.gd` | The stack count in the top-right corner of a slot. Shared by the bag and the pop-up. |
| `scenes/inventory/item_stage.gd` | Every item in 3D, into ONE render target. Cells read sub-rects of it. |
| `scenes/inventory/amount_prompt.gd` | The box that asks for the amount of a prompted action. Shared by the inventory and the pop-up. |
| `world/server_action.gd` | How to read one action the server named: send it whole, or fill in the amount. |
| `world/popup_state.gd` | The pop-up the server holds open. Knows no pop-up, grid or verb. |
| `scenes/popup/popup_view.gd` | The pop-up over the world pane: grids or a menu, the side panel, the quantity row. The player moves and sizes it. |
| `scenes/popup/popup_slot.gd` | One slot. Left click sends the first action, right click lists them all. |
| `scenes/popup/timer_panel.gd` | The side panel of a timed station: one bar for each slot, counted down between snapshots. |
| `world/summary_state.gd` | The dossier. Knows no panel names and must not learn any. |
| `scenes/summary/summary_view.gd` | The sheet, a native `Window`. Iterates panels, never enumerates them. |
| `scenes/login/login_view.gd` | Name, password, connect/create. Hides itself when vitals arrive. |
| `world/command_history.gd` | The up-arrow. Pure rules, no widget. |
| `world/movement_keys.gd` | Which key means which direction. Knows nothing about focus. |
| `world/held_movement.gd` | The movement keys held now, and when to send their direction again. Pure state, no clock. |
| `world/reconnect_policy.gd` | How long to wait before redialing. Pure schedule, no clock. |
| `world/quest_state.gd` | Your quest log. Knows no quest key and must not learn any. |
| `scenes/quests/quests_view.gd` | The quest tab: a bar per objective, drawn from numbers rather than prose. |
| `world/xp_tracker_state.gd` | This session's XP awards, totals and rates. The clock is injectable; the session is the client's own. |
| `scenes/xp/xp_hud_view.gd` | XP drops, the session strip and the progress bar over the world. Takes no click. |
| `world/combat_options_state.gd` | Your weapon and its styles. Names no style, and nothing in it is set by a click. |
| `scenes/combat/combat_options_view.gd` | The Combat tab: a button per style, lit by the snapshot rather than the click. |
| `world/stable_hash.gd` | A string hash that gives the same number on every client. `EntityPool` turns the ring of figures on a tile by it. |
| `scenes/minimap/minimap_view.gd` | The tiles around the player, drawn small over the world pane from the chunks. Clickable. Zoom, map dots, map icons, the destination marker, the walk path, the Run button. |
| `scenes/worldmap/world_map_view.gd` | The world map: every chunk of one plane. Pans, zooms, and changes the plane. Walks nowhere. |
| `world/entity_roster.gd` | The entities near the observer, one row per id. The 3D pane and the minimap draw it. |
| `world/world_map_state.gd` | The world map summaries, as one image and one icon list for each plane. |
| `world/map_raster.gd` | The colour of a tile on both maps, and the images the maps draw the ground from. |
| `world/map_icons.gd` | The symbol of each object category on both maps. |
| `scenes/panel/panel_view.gd` | The control-panel tab strip. Tabs are addressed by title, never by index. Each tab has an icon, and the labels show when they fit. |
| `world/hud_layout.gd` | The rules of the HUD layout: anchors, the clamp, the snap, and the check of a saved entry. Static, and it knows no node. |
| `scenes/layout/hud_elements.gd` | The HUD elements that the player can place, and where each one ships. One row for each. |
| `scenes/layout/hud_slot.gd` | One HUD element: its control and its shipped place. |
| `scenes/layout/hud_arranger.gd` | Places every HUD element from the layout of the player. The one owner of where an element sits. |
| `scenes/layout/layout_editor.gd` | The layout editor: frames, grips, snap, the settings of an element, and presets. |
| `scenes/resize_grips.gd` | The grips on the free edges and corners of a box. Shared by the pop-up and the layout editor. The pop-up raises its grips over every other box. |
| `ui/icons/` | The tab icons, from game-icons.net (CC BY 3.0). `PanelView.TAB_ICONS` names the author of each, and the Credits box shows them. |
| `world/doll_layout.gd` | Where each equipment frame sits on the paper doll. A picture, not a rule; guarded from Python by path. |
| `scenes/equipment/equipment_view.gd` | The paper doll. Draws the frames the server sent, in the shape the table says. |
| `scenes/vitals/vitals_bars.gd` | Your resources as bars. One control, two homes. |
| `world/chat_tabs.gd` | Which tab a line belongs in, which tab is open, which tabs have unread lines, and which tabs are hidden from All. Holds no text. |
| `world/chat_modes.gd` | The chat modes from `char_chat`, the chosen mode, and the line to send for a typed line. |
| `scenes/chat/chat_view.gd` | One RichTextLabel per tab. Appends. Draws All again only when the filter changes. |
| `scenes/chat/chat_bar.gd` | The tab buttons under the input, and the right-click menu of each. |
| `scenes/chat/chat_mode_button.gd` | The chat mode in front of the input, and its menu. |
| `world/client_settings.gd` | Font size, UI scale, sound effects volume, which panes are shown, how big the player made a box, the HUD layout and its presets, via ConfigFile under `user://`. |
| `ui/blackout_theme.tres` | Every margin, separation, font size and label color. Also the red accent: the text box red on the slider bars, check boxes (`ui/icons/check_*.svg`, `radio_*.svg`), the selected tab, scroll bars, pressed buttons, menu hover and `FormHeading` lines. The console root and `gui/theme/custom` both name it: the root reaches the tree, the project setting reaches each Window. See `docs/2026-09-22-ENG-0010-godot-ui-authoring.md`. |
| `ui/theme_preview/` | Two scenes for the scene preview of the Theme editor: `blackout.tscn` shows each type that the theme sets, and `godot.tscn` shows each other type of the default theme. In the Theme editor, click Add Preview, then Add Scene Preview. The picker then selects the type of the clicked sample. A tool script builds the samples from the type lists, so a new variation needs no edit. |
| `world/server_endpoint.gd` | Which server this build talks to. Debug reaches localhost, release reaches production. |
| `world/scrollback_find.gd` | Which matches exist and which one you are on. Pure. |
| `scenes/find/find_bar.gd` | Ctrl+F over the log. Scrolls via `get_character_line`. |
| `scenes/help/help_view.gd` | What the CLIENT does. The game's own `help` covers the rest. Every row wraps at any pane width, and a narrow pane stacks each name over its text. No entry has a line break in a sentence. |
| `scenes/options/options_view.gd` | The sliders and the pane toggles. Writes through the settings object, applies nothing. |
| `scenes/hud.tscn` `.gd` | Draws char_state above the text pane. Presentation only. |
| `world/world_view.gd` | The 3D pane: the terrain node, the marker, the hover mark, the pick, and the avatar on the drawn ground. |
| `world/entity_pool.gd` | Everything the statefeed can see, each on its own tile. Hit flash and hover. |
| `world/hitsplats/` | The hitsplats. `hitsplat_layer.gd` picks a style and draws. `hitsplat_style.gd` and `styles/*.tres` hold the look. |
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
5. **`StableHash.of` still matches the retired browser pane.** The two panes
   once ran side by side on the same character, so a difference meant a bug.
   For that reason, it reimplements the JS string hash of `blackout3d.js` and
   does not call Godot's. `tests/test_world_state.gd` still checks it against
   test vectors computed directly from the JS. The room-kind palette that it
   coloured went with the xyzgrid maps in DESIGN-0011 Phase 4b.
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
