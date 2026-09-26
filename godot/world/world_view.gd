class_name WorldView
extends Node3D
## The 3D world pane: the ground of the tile world, and who stands on it.
##
## **The tile world only.** DESIGN-0011 Phase 5 (09/25/2026) replaced the
## xyzgrid islands with the chunks of the tile world. [TerrainView] draws one
## mesh for each chunk that [WorldState] holds. Nick chose to drop the island
## renderer at once. Thus, a player on an xyzgrid map sees no ground here until
## Phase 4b moves every player.
##
## **One coordinate rule.** Tile (x, y) has its centre at (x, h, -y), where h
## is the height of the drawn ground there ([method WorldState.ground_y]). Grid
## Y grows to the north, and north is -Z. [ChunkMeshBuilder] and
## [TerrainPicking] use the same rule, so a figure stands on the drawn ground
## and a click lands on the tile under the cursor.

## Every name the SERVER owns, generated from
## blackout/systems/interface/statefeed/constants.py by systems/interface/statefeed/clientexport.py.
##
## Preloaded rather than autoloaded: the generated file declares no `extends
## Node`, and a Godot autoload must. Do not retype a channel name here -- the
## dead "Pole clearing" room-kind key reached this file by exactly that route
## and rendered a fallback hue in both clients until 08/23/2026.
const Const := preload("res://autoload/blackout_constants.gd")

## Emitted when the player right-clicks something that affords anything.
##
## `options` are `{command, label, target}` dictionaries in the server's own
## order; `at` is where to open the box, in this viewport's coordinates. The
## pane raises the question and something else draws it -- [ChooseOption] is a
## sibling Control over the world pane, not a child of this Node3D, so the 3D
## scene stays 3D and the menu can be tested without a camera.
signal options_requested(options: Array, at: Vector2)

## Emitted when what a left click would act on changes, with the text that
## names it: "Attack Mutant Raider / 1 more option", "North", or "" for nothing.
## The console shows it in a [HoverBar] over the pane, for the reason
## [signal options_requested] gives for the menu: this Node3D draws no Controls.
signal hover_text_changed(text: String)

## Added to the hover text when the right-click menu has more than the default.
## OSRS prints the same count, so a player knows a right click has more.
const MORE_OPTIONS_TEXT := " / %d more options"
const ONE_MORE_OPTION_TEXT := " / 1 more option"

const AURA_EVENT_DEACTIVATE := "deactivate"
const AURA_EVENT_PULSE := "pulse"
const AURA_RING_THICKNESS := 0.06
const AURA_PULSE_SECONDS := 0.4
const AURA_ALPHA := 0.55
const AURA_PULSE_ALPHA := 1.0

## How near the cursor an entity has to be, in pixels, to be what you clicked.
const PICK_REACH_PIXELS := 24.0

## How much of a tile YOU fill, and how far above its face you stand.
##
## Matches EntityPool's ENTITY_SCALE deliberately. The browser learned this the
## hard way with two different lifts -- 0.22 for entities and 0.42 for the local
## marker -- which was correct only while the marker was a cone half a tile tall,
## and read as hovering over people the moment it was not. There is no lift
## constant at all now: the avatar rests on the tile by measurement, exactly as
## everything standing beside it does.
const AVATAR_SCALE := EntityPool.ENTITY_SCALE

## The colour of the mark on the tile under the cursor. A client fact: the
## server says what a click does, and this only shows where it lands.
const COLOR_HOVER := Color(1.0, 1.0, 1.0)

## One tile, in world units. The same as [constant ChunkMeshBuilder.TILE_SIZE].
const TILE_SIZE := ChunkMeshBuilder.TILE_SIZE
const STEP := TILE_SIZE


## The ground. See [TerrainView].
@onready var _terrain: TerrainView = $Terrain

## YOUR TRUE TILE: the square the server has you standing on.
##
## It was a placeholder box until 09/20/2026 and the avatar hung off it. It is
## now the mark itself, drawn only while [member _animator] has the figure away
## from it — see [TrueTileMark]. The node stays the anchor whatever it draws:
## the aura ring is placed from it, and every route that moves the observer
## moves this first.
@onready var _marker: MeshInstance3D = $Marker

## What the avatar actually hangs off, and the node the camera rig follows.
##
## SEPARATE from the marker, and that separation is the whole animation. The
## marker snaps to the server's tile because it IS the server's tile; this
## slides towards it, so the figure walks and the fact stays put. With the
## animation off the two are in the same place on every frame, which is exactly
## the client's behaviour before this node existed.
@onready var _avatar_root: Node3D = $Avatar

@onready var _entities: EntityPool = $Entities
@onready var _aura: MeshInstance3D = $Aura
@onready var _camera: Camera3D = $Camera/SpringArm3D/Camera3D

## The fog and the light of the area that the player stands in. This pane
## tells it the area on each placement. See [AreaEnvironment].
@onready var _area_environment: AreaEnvironment = $Environment

## The world model. GIVEN by the console since 08/28/2026, not built here:
## the minimap draws the same map, and one payload must not be reassembled
## twice. See [method bind_world].
var _state := WorldState.new()

## Where every mesh in the pane comes from. OWNED BY THE CONSOLE and bound in,
## not built here: the inventory draws meshes too now, and two resolvers would
## mean two model caches, two fetches of the same `.glb`, and a sword that
## arrives in the room before it arrives in the bag.
var _meshes: MeshResolver

## YOUR avatar, standing on the marker tile.
##
## A child of the marker rather than a replacement for it: the marker is what
## the camera rig follows by NodePath and what every placement routine moves, so
## it stays the anchor and this is what the anchor wears.
var _avatar: Node3D

## Where on the marker tile the avatar stands, handed over by [EntityPool].
##
## The marker itself never moves off the tile's centre — it is what the camera
## rig follows by NodePath and what the aura ring is anchored to, and both would
## slide off the tile with it. Only the figure hanging on it shifts, into the
## slot the ring left for it, so a dropped item is beside you rather than inside
## you and a crowded tile reads as several people rather than one.
var _avatar_offset := Vector3.ZERO

## How fast the avatar turns to face a new direction, in radians per second.
##
## It turned INSTANTLY until 09/21/2026, and an instant quarter turn at the
## start of every step is a snap however smoothly the figure then slides. A
## reversal takes about a quarter of a second at this rate, which is under half
## a tick -- so the figure is facing the right way for most of the step it is
## taking, and the turn still reads as a turn.
const TURN_SPEED := 12.0

## Which way the avatar is turning TO, and which way it is drawn, in radians
## about Y.
##
## Two values for the same reason the position has two: the server's step names
## a direction at once, and the figure takes a moment to turn to it. They are
## equal whenever the avatar is not mid-turn, which is nearly always.
##
## Held here rather than read back off the node, because [method _redraw_avatar]
## frees and rebuilds that node every time `char_avatar` names a different asset
## or art lands for the one it already named — and a player who walked north
## before their model arrived should still be facing north after it does.
var _avatar_yaw := 0.0
var _avatar_yaw_drawn := 0.0

## The tile the avatar was last placed on, and which island it was on.
##
## An empty z means no step has been watched yet, which is the state on login
## and after a resync. A first sighting names no direction, so the avatar keeps
## the yaw it has rather than snapping round to face north.
var _facing_cell := Vector2i.ZERO
var _facing_z := ""

## The observer's own state, bound by the console. Read for `asset` and
## `family` and nothing else.
##
## Bound rather than ingested here. [CharState] already owns char_avatar, and a
## second reader parsing the same channel would be the third module to own one
## fact -- which is exactly how the android's dialogue came to print
## `talk:tester: 0/True` at players.
var _char: CharState

## The square on the tile under the cursor. It shows only on a tile that a
## click acts on.
var _hover_mark: MeshInstance3D

## The last text sent on [signal hover_text_changed]. Kept so a mouse move
## inside one tile emits nothing.
var _hover_text := ""

## Where YOU are drawn, as against where the server says you are.
##
## One per figure is the rule, and the observer's is held here while every
## other figure's lives in [EntityPool] — so the player and the raider chasing
## them move by one set of maths and neither can be smoother than the other.
##
## Paced by the SERVER's tick, which arrives in the generated constants.
## `goto` steps one tile per tick, so a walk drawn at any other speed either
## arrives early and waits or falls behind and keeps falling.
var _animator := StepAnimator.new(STEP, Const.TICK_SECONDS)

## Everyone else's true tile, as one MultiMesh of the same square.
##
## A MultiMesh rather than a node each: a fight in a busy room puts a mark
## under several entities at once, and they are one square drawn in several
## places. Built here rather than in the pool for the reason the pool draws no
## observer — a mark is ground, the ground is this pane's, and the pool is
## given a tile origin rather than the maths that produced it.
var _entity_marks: MultiMeshInstance3D

## What the player chose about how movement is drawn. Bound by the console,
## which owns it. Null until then, and the animation runs until told otherwise.
var _settings: ClientSettings


func _ready() -> void:
	_build_true_tile_marks()
	_build_hover_mark()

	# A new figure rises out of the fog of the area, so the pool must know the
	# fog colour. See [method EntityPool.set_fade_color].
	_area_environment.look_changed.connect(_on_area_look)

	Evennia.channel_received.connect(_on_channel)


func _on_area_look(look: Dictionary) -> void:
	_entities.set_fade_color(look["fog_color"])


## Give both true tile marks the one square they draw.
##
## The observer's is written onto the marker node, which already exists and is
## already in the right place. Everyone else's is a MultiMesh with no instances
## in it yet — [method _on_entity_marks] fills it the first time somebody
## starts moving, and empties it again when they stop.
##
## Two materials from one builder, because the two differ in colour and must
## not differ in anything else. Each gets its OWN material rather than sharing
## one: a shared resource is a colour written by whichever pane drew last.
func _build_true_tile_marks() -> void:
	var square := TrueTileMark.build_mesh(TILE_SIZE)

	_marker.mesh = square
	_marker.material_override = TrueTileMark.build_material(
		TrueTileMark.COLOR_OBSERVER)
	_marker.visible = false

	_entity_marks = _instance_of(_new_multimesh(square, 0, false))
	_entity_marks.material_override = TrueTileMark.build_material(
		TrueTileMark.COLOR_ENTITY)

	add_child(_entity_marks)


## Build the square that marks the tile under the cursor. The same mesh as the
## true tile marks, in its own colour, so the three read as one family.
func _build_hover_mark() -> void:
	_hover_mark = MeshInstance3D.new()
	_hover_mark.name = "HoverMark"
	_hover_mark.mesh = TrueTileMark.build_mesh(TILE_SIZE)
	_hover_mark.material_override = TrueTileMark.build_material(COLOR_HOVER)
	_hover_mark.visible = false

	add_child(_hover_mark)


## Slide the avatar towards the tile the server put it on, and show or hide the
## mark for that tile.
##
## The ONLY per-frame work this pane does. Everything else redraws on a feed
## message, and this could not: an animation is a function of time, and the
## server sends nothing between two steps.
func _process(delta: float) -> void:
	_animator.advance(delta)
	_avatar_yaw_drawn = rotate_toward(
		_avatar_yaw_drawn, _avatar_yaw, TURN_SPEED * delta)
	_draw_avatar()


## Put the avatar where the animator currently has it, and show the mark for
## your true tile while the two are apart.
##
## Called from [method _process] and from both places that move the animator
## WITHOUT waiting for a frame. That second group is the point of having a
## routine at all: with the animation off, a step lands the figure on its new
## tile immediately, and drawing that a frame later would put the avatar behind
## its own marker -- the lag this file exists to remove. [EntityPool] writes
## its nodes at the same points, for the same reason.
func _draw_avatar() -> void:
	_avatar_root.position = _animator.drawn()
	_marker.visible = _animator.is_travelling()

	# Null until char_avatar has been answered, and on tier 1 until the .glb
	# has landed. _redraw_avatar applies the drawn yaw when the figure arrives.
	if _avatar != null:
		_avatar.rotation.y = _avatar_yaw_drawn


## Give the pane its mesh source. Called by the console, which owns it.
##
## Not done in _ready, because a child's _ready runs BEFORE its parent's -- so
## at that point the console has not built the resolver yet and this pane would
## bind null.
func bind_meshes(resolver: MeshResolver) -> void:
	_meshes = resolver
	_entities.bind(_meshes, _locate_coords, STEP)
	_entities.observer_slot_changed.connect(_on_observer_slot)
	_entities.true_tiles_changed.connect(_on_entity_marks)
	_meshes.refreshed.connect(_on_art_arrived)

	# In THIS pane's world, because a shader is compiled for the lighting it is
	# drawn under, and this is the lighting every model will be drawn under.
	var warmer := ShaderWarmer.new()

	add_child(warmer)
	_meshes.bind_warmer(warmer)

	# Something stands on the marker from the first frame, before char_avatar
	# has said which asset you are. The generic character figure is the right
	# placeholder: it is what every OTHER player in the room is drawn as, so you
	# look like a person immediately and sharpen into your own model later.
	_redraw_avatar()


## Take the world model. Called by the console, which owns it.
##
## Not done in _ready for the reason bind_meshes gives: a child's _ready runs
## before its parent's, so the console has not built anything yet.
func bind_world(state: WorldState) -> void:
	_state = state
	_state.room_changed.connect(_place_marker)

	# A chunk that lands after the room gives the ground its height. The marker
	# and every figure then stand again, on the drawn ground.
	_state.chunks_changed.connect(_place_marker)

	# Whatever has already landed. The console binds after the socket is open,
	# so a chunk that arrived during the handshake is not lost.
	_terrain.bind(_state)
	_place_marker()


## Take the player's own preferences. Called by the console, which owns them.
##
## Only one is read here, and it decides whether a figure slides between tiles
## or appears on each. Applied to the pool as well as to the avatar from this
## one place, because a client that animated the player and not the raider
## beside them would be worse than one that animated neither.
func bind_settings(settings: ClientSettings) -> void:
	_settings = settings
	_settings.changed.connect(_apply_settings)
	_apply_settings()


func _apply_settings() -> void:
	var animated: bool = _settings.smooth_movement

	_animator.set_animated(animated)
	_entities.set_animated(animated)

	# On the frame the player ticked the box, not the one after it. The
	# checkbox is in a pane beside the world, so the change is watched as it is
	# made -- and a figure that took a frame to land would be a flicker the
	# player caused and cannot explain.
	_draw_avatar()


## Follow the observer's own state. Called by the console, which owns it.
func bind_char(state: CharState) -> void:
	_char = state
	_char.changed.connect(_redraw_avatar)
	_redraw_avatar()


## Draw whoever you currently are, on the node that slides between tiles.
##
## Hung off [member _avatar_root] and not off the marker. The marker is where
## the SERVER has you; this is where you are DRAWN, and telling the two apart
## is what lets the walk be animated without the client ever claiming to be
## somewhere the server does not have you.
func _redraw_avatar() -> void:
	if _meshes == null:
		return

	if _avatar != null:
		_avatar.queue_free()

	var asset := "" if _char == null else _char.asset
	var family := Const.FAMILY_CHARACTER

	if _char != null and not _char.family.is_empty():
		family = _char.family

	_avatar = _meshes.resolve_entity(asset, family)
	_avatar.scale = Vector3.ONE * AVATAR_SCALE
	# Rests on the tile by measurement, like everything standing beside it, and
	# stands in the ring slot the pool reserved -- which is the middle of the
	# tile whenever nothing is sharing it.
	var bounds := ModelLoader.bounds_of(_avatar)
	_avatar.position = _avatar_offset + Vector3(
		0.0, -bounds.position.y * AVATAR_SCALE, 0.0)
	# Re-applied rather than left at zero: this runs whenever the asset changes
	# or its art finally lands, and both are things that happen mid-walk. A
	# figure that snapped back to facing north the moment its model arrived
	# would read as the model being wrong rather than as the yaw being lost.
	#
	# The DRAWN yaw, not the one being turned to: a model that lands in the
	# middle of a turn should carry on turning, not finish it instantly.
	_avatar.rotation.y = _avatar_yaw_drawn
	_avatar_root.add_child(_avatar)


## Take the slot [EntityPool] left for the observer in their tile's ring.
##
## Written straight onto the avatar rather than through a redraw: the mesh is
## unchanged, only where it stands is, and rebuilding it would throw away a
## fetched model and re-resolve it on every step the player takes.
##
## The avatar can be null here -- the pool rebuilds the moment room_players
## lands, which is before char_avatar has said who you are -- so the offset is
## kept and applied by [method _redraw_avatar] when the figure does arrive.
func _on_observer_slot(offset: Vector3) -> void:
	_avatar_offset = offset

	if _avatar == null:
		return

	_avatar.position.x = offset.x
	_avatar.position.z = offset.z


## Mark the true tile of everybody the pool currently has between tiles.
##
## `origins` are tile positions this pane handed the pool in the first place,
## through `_locate_coords`, so nothing here re-derives where a tile is. The
## list arrives only when the SET changes -- when somebody starts or stops
## moving -- rather than every frame, which is what makes a MultiMesh rebuild
## affordable at all.
##
## One mark per TILE and not per entity. Two raiders walking onto one square
## are two identical coplanar outlines, which is z-fighting rather than
## emphasis; the pool groups them before it sends the list.
func _on_entity_marks(origins: Array) -> void:
	var multi := _entity_marks.multimesh

	multi.instance_count = origins.size()

	for index: int in origins.size():
		# Already the tile's TOP face: `_locate_coords` lifts by half the slab,
		# which is what every entity is placed from. The square's own clearance
		# above that face is TrueTileMark.LIFT, baked into the mesh.
		var origin: Vector3 = origins[index]

		multi.set_instance_transform(
			index, Transform3D(Basis.IDENTITY, origin))


## Draw the avatar again when its art lands. The ground uses no model art, so
## nothing else here waits for a model.
func _on_art_arrived(asset_key: String) -> void:
	if _char != null and _char.asset == asset_key:
		_redraw_avatar()


func _on_channel(channel: String, payload: Dictionary) -> void:
	# CH_TILE_CHUNK and CH_ROOM_INFO are not here on purpose. The console puts
	# them into the shared WorldState, and this pane draws on its signals. A
	# second read here would parse each chunk two times. It would also run
	# BEFORE the console, because a child connects to Evennia in its own
	# _ready, and the _ready of a child runs first.
	match channel:
		Const.CH_ROOM_PLAYERS:
			_entities.replace_all(payload.get("entities", []))

		Const.CH_ROOM_PLAYERS_DELTA:
			_entities.apply_delta(payload.get("added", []),
					payload.get("removed", []))

		Const.CH_PLAYER_ADD:
			_entities.add(payload.get("entity", {}))

		Const.CH_PLAYER_REMOVE:
			_entities.remove(int(payload.get("entity_id", 0)))

		Const.CH_COMBAT:
			if payload.get("hit", false):
				_entities.flash(int(payload.get("target_id", 0)))

		Const.CH_AURA:
			_on_aura(payload)


# ─── Clicking ────────────────────────────────────────────────────────────────

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_hover_at((event as InputEventMouseMotion).position)
		return

	if not (event is InputEventMouseButton):
		return

	var click := event as InputEventMouseButton

	if click.button_index == MOUSE_BUTTON_LEFT and click.pressed:
		_act_on(click.position)
		return

	# Right click ASKS instead of acting. Left click still performs the
	# default, which is the first option the server listed -- so nothing about
	# the existing one-verb flow changes, and the menu is purely additional.
	#
	# On the PRESS, with no gesture arbitration, because the right button is
	# the menu's alone: OrbitCamera turns the camera on a MIDDLE drag, moved
	# there on 09/10/2026 for exactly this. Sharing one button between the two
	# needs a click-versus-drag threshold, and a threshold is a number that is
	# wrong for somebody.
	if click.button_index == MOUSE_BUTTON_RIGHT and click.pressed:
		_offer_options(click.position)


## Where an entity's `coords` put it in the world, or null if not placeable yet.
##
## Handed to [EntityPool] as a callable, so the placement maths has one owner:
## this pane already decides where a tile is, and a second copy in the pool
## would be free to disagree with the tiles actually drawn.
##
## Null and not a fallback position. A figure off the tile world, or on a
## chunk that has not landed, has no honest place. A guess once put the whole
## neighbourhood on the tile of the observer.
##
## The position is ON the drawn ground: its height comes from
## [method WorldState.ground_y], the same triangles that [ChunkMeshBuilder]
## draws.
func _locate_coords(coords: Array) -> Variant:
	if coords.size() < 3 or str(coords[2]) != Const.TILE_WORLD_Z:
		return null

	# Every number in a parsed payload is a float. This converts it where it
	# reads it, like every other coordinate in this client.
	var cell := Vector2i(int(coords[0]), int(coords[1]))

	return _ground_point(cell)


## The point on the drawn ground at the centre of a tile, or null when its
## chunk is not loaded.
func _ground_point(cell: Vector2i) -> Variant:
	var height: Variant = _state.ground_y(cell)

	if height == null:
		return null

	return Vector3(cell.x * STEP, float(height), -cell.y * STEP)


# ─── Hover ───────────────────────────────────────────────────────────────────

## Light up whatever a click would act on.
##
## Answers the question the pane could not answer before: entities are a few
## pixels across and picked by CURSOR DISTANCE rather than by a raycast, so
## without feedback a player has no way to know which of two adjacent raiders
## they are about to attack. The rule is deliberately the same one [method
## _act_on] uses -- entity first, then tile -- so what lights up is exactly what
## a click would take.
func _hover_at(screen_point: Vector2) -> void:
	var entity_id := _entities.pick(_camera, screen_point, PICK_REACH_PIXELS)

	if entity_id != 0:
		_clear_tile_hover()

		# An entity the server gave no `interact` STOPS the search rather than
		# falling through to the tile beneath it, which is what _act_on does
		# too -- so nothing lights and nothing happens. Falling through would
		# mean a cursor aimed at another player lights the ground under them
		# and a click walks you there.
		var entity := _entities.entity(entity_id)
		var affords := _interaction(entity)

		_entities.hover(entity_id if not affords.is_empty() else 0)
		_set_hover_text(entity_hover_text(entity))
		return

	var cell := _cell_under(screen_point)

	_entities.hover(0)
	_hover_tile(cell)
	_set_hover_text(tile_hover_text(_state.tile_action(cell)))


## Put out every hover: the lit entity, the lit tile, and the text.
##
## The console calls this when the mouse leaves the pane. The pane gets no
## mouse motion after that, so without this call the last tile stays lit and
## the bar keeps naming a thing the mouse is not on.
func clear_hover() -> void:
	_entities.hover(0)
	_clear_tile_hover()
	_set_hover_text("")


## The hover text for one entity: its default action as the right-click menu
## words it, and a count of the other rows.
##
## Static and public so a test can assert the wording with no scene. The words
## come from [method ChooseOption.row_text], so the bar and the menu cannot name
## one action two ways. An entity that affords nothing, such as another player,
## gives its name alone. A click does nothing there, but the name is still news.
static func entity_hover_text(entity: Dictionary) -> String:
	var options := options_for(entity)

	if options.is_empty():
		return str(entity.get("name", ""))

	var text := ChooseOption.row_text(options[0])
	var more := options.size() - 1

	if more == 1:
		return text + ONE_MORE_OPTION_TEXT

	if more > 1:
		return text + MORE_OPTIONS_TEXT % more

	return text


## The hover text for one tile action: "North", "Goto (4,3)", or "" when the
## server named no action for the tile. The same row the right-click menu shows.
static func tile_hover_text(tile: Dictionary) -> String:
	var command := str(tile.get("command", ""))

	if command.is_empty():
		return ""

	return ChooseOption.row_text({"command": command, "label": "", "target": ""})


func _set_hover_text(text: String) -> void:
	if text == _hover_text:
		return

	_hover_text = text
	hover_text_changed.emit(text)


## Mark the tile under the cursor, if a click there acts.
##
## The mark lies on the drawn ground, like the true tile marks. A tile that
## affords nothing gets no mark, so the mark means "a click does something".
func _hover_tile(cell: Vector2i) -> void:
	var action := _state.tile_action(cell)
	var point: Variant = _ground_point(cell)

	if action.is_empty() or point == null:
		_clear_tile_hover()
		return

	_hover_mark.position = point
	_hover_mark.visible = true


func _clear_tile_hover() -> void:
	_hover_mark.visible = false


## Turn one click into one command a telnet player could have typed.
##
## That constraint is the whole of Phase 3: there is no privileged client
## channel, so every lock, cooldown and permission still applies with nothing
## to re-audit. Clicking a tile sends `north`. It does not send a position.
func _act_on(screen_point: Vector2) -> void:
	var entity_id := _entities.pick(_camera, screen_point, PICK_REACH_PIXELS)

	if entity_id != 0:
		_act_on_entity(_entities.entity(entity_id))
		return

	_walk_towards(_cell_under(screen_point))


func _act_on_entity(entity: Dictionary) -> void:
	var command := approach_command(_interaction(entity), entity,
		_state.current_cell, _state.current_z, walks_there(entity))

	if command.is_empty():
		return

	Evennia.command(command)


## Gather everything a right click could mean here, and raise it.
##
## Entity first, then the tile beneath -- the same order [method _act_on] and
## [method _hover_at] use, so the menu opens on exactly what a left click would
## have acted on. An entity that affords nothing STOPS the search rather than
## falling through to the ground under it, for the reason _hover_at gives: a
## menu offering to walk to the tile another player is standing on is not what
## the player was asking about.
func _offer_options(screen_point: Vector2) -> void:
	var entity_id := _entities.pick(_camera, screen_point, PICK_REACH_PIXELS)

	if entity_id != 0:
		var entity := _entities.entity(entity_id)
		var options := approach_options(options_for(entity), entity,
			_state.current_cell, _state.current_z)

		if not options.is_empty():
			options_requested.emit(options, screen_point)

		return

	var tile := _state.tile_action(_cell_under(screen_point))
	var command := str(tile.get("command", ""))

	if command.is_empty():
		return

	# A tile action carries no `label` -- it is `{command, kind}` and always
	# has been -- so the label is left EMPTY rather than filled with a copy of
	# the command. Empty is what ChooseOption.row_text's fallback is for, and
	# it is the honest answer: the server named no wording for this, so the
	# client derives one instead of pretending it was told.
	#
	# The row then reads as the verb: "North", "Goto (4,3)". Giving tiles a
	# server-sent label is a one-field change on `tile_actions` if the wording
	# ever needs to be better than the command.
	options_requested.emit(
		[{"command": command, "label": "", "target": ""}], screen_point)


## Every verb the server said this entity affords, richest form first.
##
## Static and public so a test can assert the fallback without a scene, a
## camera or a pool.
##
## `actions` is the list; `interact` is its head, sent separately so that a
## client reading only the single verb keeps working. Reading the list when it
## is there and falling back to the single verb when it is not is what lets
## this pane sit in front of a server of either vintage -- and the server omits
## `actions` entirely for the one-verb case, which is nearly every entity in
## the world, so the fallback is the COMMON path rather than a legacy one.
##
## Deduplicates on the command rather than on the label, because two rows that
## send the same string are one option however they are worded, and a menu that
## lists it twice looks broken.
static func options_for(entity: Dictionary) -> Array:
	var target := str(entity.get("name", ""))
	var rows: Array = []
	var seen := {}

	for raw: Variant in entity.get("actions", []):
		if typeof(raw) != TYPE_DICTIONARY:
			continue

		var action := raw as Dictionary
		var command := str(action.get("command", "")).strip_edges()

		if command.is_empty() or seen.has(command):
			continue

		seen[command] = true
		rows.append({
			"command": command,
			"label": str(action.get("label", "")),
			"target": target,
			"approach": walks_there(action),
		})

	if not rows.is_empty():
		return rows

	var single := _interaction(entity)

	if single.is_empty():
		return []

	# The fallback row's answer comes off the ENTITY, which is where the
	# server mirrors the primary verb's -- the same place `interact` itself
	# comes from.
	return [{
		"command": single,
		"label": "",
		"target": target,
		"approach": walks_there(entity),
	}]


## The whole command the server said this entity affords, or "".
##
## THERE IS DELIBERATELY NO VERB TABLE HERE. `serialize_entity` names the
## command in full -- "craft", "bank", "talk", "attack mutant raider" -- and
## this pane sends it verbatim, which is the standing instruction in CLAUDE.md
## and the reason `interact_command` exists on the server at all.
##
## This file kept a `kind`-to-verb match until 08/27/2026 -- the third writing
## of that table across the two clients, and the third one to be wrong. It knew
## three kinds, `npc`, `item` and `gatherable`, and so:
##
##   a Bank, a Foundry Furnace and an Anvil are `station`, which the match did
##       not name at all, so clicking any of them silently did NOTHING;
##   a Shopkeeper is `npc`, so clicking one sent `attack` at the man selling
##       you things -- confidently, and with the wrong verb rather than none;
##   a gathering node was sent `cut <name>`, when its verb takes no target at
##       all because the node carries the cmdset.
##
## Every one of those was already correct in the payload. The pane simply was
## not reading it.
##
## An empty answer means the entity affords nothing -- another player, or
## anything the server has not given a verb -- and the pane leaves it unlit and
## unclickable.
static func _interaction(entity: Dictionary) -> String:
	return str(entity.get("interact", ""))


## Whether a click on this has to WALK there before the command can act.
##
## `source` is either an entity row or one of its `actions` rows: the server
## mirrors the primary verb's answer onto the entity beside `interact`, so the
## same key answers for both.
##
## TRUE IS THE DEFAULT AND THE COMMON CASE. `cut`, `talk`, `bank` and `get` all
## act where the player stands, and the server sends the key only to say
## otherwise. So a payload from a server that has never heard of the field
## keeps the behaviour this pane has always had.
##
## The one verb that answers false today is `attack`, and the reason is the
## reason this field exists rather than a client-side reach check: how far a
## weapon carries is a rule, it changes with what the player holds, and a bow
## reaching seven tiles made the wrap walk an archer onto the raider it was
## already able to shoot. `CmdAttack` walks by itself when it has to.
static func walks_there(source: Dictionary) -> bool:
	return bool(source.get("approach", true))


## The command that acts on `entity` from where the observer stands, or "".
##
## An entity on the observer's own tile gets `command` verbatim, exactly as
## before. One on a DIFFERENT tile of the same island gets it wrapped in the
## server's [constant Const.ENTITY_APPROACH_TEMPLATE] -- `goto (4,7) then cut
## rusty pole` -- so the click walks there and acts on arrival. Sent verbatim it
## could only fail: a gathering node's verb lives in the node's own cmdset, and
## `attack` and `get` search the room the player is in.
##
## THE TEMPLATE IS THE SERVER'S; only the two tiles are this pane's, and it
## already holds both. The wrap cannot ride on the entity row instead, because
## which tile the observer stands on changes every step and the row does not.
##
## An entity on ANOTHER island is sent verbatim too, and that is not a rule
## about maps: the server reads the template's (X,Y) on the map the player is
## standing on, so the same numbers there name a different room entirely.
## Wrapping it would walk the player somewhere they never clicked.
##
## Static and public so a test can pin every branch with hand-built payloads.
static func approach_command(command: String, entity: Dictionary,
		here: Vector2i, here_z: String, walks := true) -> String:
	if command.is_empty():
		return ""

	# A command that closes its own distance is sent from wherever the player
	# is standing. See [method walks_there].
	if not walks:
		return command

	var coords: Variant = entity.get("coords", [])

	if typeof(coords) != TYPE_ARRAY or coords.size() < 3:
		return command

	# Floats off the wire, converted at the point of use like every other
	# coordinate in this client.
	var cell := Vector2i(int(coords[0]), int(coords[1]))

	if cell == here or str(coords[2]) != here_z:
		return command

	# {command} LAST, so a command that happened to contain "{x}" is carried
	# as written rather than having a coordinate substituted into it.
	return Const.ENTITY_APPROACH_TEMPLATE \
		.replace("{x}", str(cell.x)) \
		.replace("{y}", str(cell.y)) \
		.replace("{command}", command)


## [method options_for]'s rows, each command passed through
## [method approach_command].
##
## A row whose command gets wrapped keeps its VERB as its label. A row the
## server sent no label for is worded by [method ChooseOption.row_text] from
## the command's first word -- which, once wrapped, is `goto`, and every far
## entity's menu would then read "Goto Rusty Pole" on every row.
static func approach_options(options: Array, entity: Dictionary,
		here: Vector2i, here_z: String) -> Array:
	var rows: Array = []

	for option: Dictionary in options:
		var command := str(option.get("command", ""))
		var label := str(option.get("label", ""))
		var sent := approach_command(command, entity, here, here_z,
			walks_there(option))

		if sent != command and label.is_empty():
			label = command.split(" ")[0]

		rows.append({
			"command": sent,
			"label": label,
			"target": option.get("target", ""),
		})

	return rows


## Send whatever the server said this tile affords.
##
## This used to compute a direction from the grid delta and check it against
## `current_exits`. Both of those are rules about the MAP, and the server owns
## the map -- see WorldState.tile_action for what that cost. Nothing here
## decides anything any more: it forwards a command the server already named,
## or it does nothing.
##
## NOT YET PORTED: the browser pane tracks an auto-walk in flight, so clicking
## your own tile mid-walk sends `cancel_action` instead of `look`. This client
## does not track a walk, so `current_cancel_action` is stored and unused and
## a mid-walk click on your own tile looks. Harmless, and deliberately left for
## whoever adds walk tracking rather than half-built here.
func _walk_towards(cell: Vector2i) -> void:
	var action := _state.tile_action(cell)
	var command := str(action.get("command", ""))

	if command.is_empty():
		return

	Evennia.command(command)


## Which tile a screen point lands on.
##
## A ray march on the drawn ground ([TerrainPicking]), not a flat plane: a
## plane misses the tile under the cursor on a hill (DESIGN-0011 section 6.6).
## The march reads the height grid, so the ground needs no collision shape. A
## miss gives the tile of the observer, and a click there looks.
func _cell_under(screen_point: Vector2) -> Vector2i:
	var origin := _camera.project_ray_origin(screen_point)
	var direction := _camera.project_ray_normal(screen_point)
	var hit: Variant = TerrainPicking.ray_hit(_state.chunks, origin, direction)

	if hit == null:
		return _state.current_cell

	return ChunkSet.tile_at(TerrainPicking.tile_point(hit))


func _place_marker() -> void:
	# The area comes first, before the pool builds a node. A figure that
	# arrives with this room then tints in from the fog of the new area. The
	# area is the one of the tile under the player, from its chunk. A tile whose
	# chunk has not landed keeps the area that it had.
	var area := _state.area_at(_state.current_cell)

	if not area.is_empty():
		_area_environment.set_area(area)

	# BEFORE the early return. Each figure stands from its own coords. Thus, a
	# figure on a chunk that is here shows before the chunk under the observer
	# arrives.
	#
	# stand() only RECORDS the tile of the observer. The next line acts on it.
	# The pool also rebuilds when an entity arrives or art lands. Each rebuild
	# must size the ring the same way.
	_entities.stand(_observer_coords())
	_entities.replace_positions()

	# BEFORE the early return as well. The coords alone say which way the last
	# step went, so a room that arrives before its chunk still records the step.
	_turn_avatar()

	var top: Variant = _ground_point(_state.current_cell)

	if top == null:
		# The room arrived before its chunk. The marker stays where it was
		# until chunks_changed calls back here with the ground in place.
		return

	# ON the drawn ground. The avatar rests itself on this point, so the
	# offset belongs to the figure, not to the anchor.
	_marker.position = top
	_aura.position = top

	# The marker is the truth and has already moved. This asks the figure to
	# walk there. A step slides; a teleport, a resync and an island arriving
	# late all snap, because StepAnimator refuses to draw a path for a move
	# longer than one step -- the same rule yaw_towards applies to facing.
	_animator.aim(top)

	_draw_avatar()


## The observer's own tile, in the shape an entity carries its coords.
##
## Built here rather than in [EntityPool] so the pool compares two keys spelled
## by one routine. [WorldState] holds x and y as a Vector2i and z as the map
## name, which is the same triple `serialize_entity` sends, only already parsed.
func _observer_coords() -> Array:
	return [_state.current_cell.x, _state.current_cell.y, _state.current_z]


# ─── Facing ──────────────────────────────────────────────────────────────────

## Which way to turn a figure stepping from `from` to `to`, or `keep` when the
## move names no direction worth facing.
##
## `atan2(dx, dz)`, not the `atan2(dz, dx)` a maths text would write. This is
## the rotation that puts **+Z** along the direction of travel, and +Z is the
## way both tiers of character are authored to face — the served `.glb` and the
## procedural figure alike.
##
## The Z term is NEGATED because grid Y grows northward while world Z grows
## southward: the same flip [method _ground_point] makes, and the reason a step
## north answers PI rather than 0. Getting this wrong is silent — the figure
## simply walks backwards — so `test_world_view` pins all eight compass steps.
##
## Only a step to a NEIGHBOURING tile turns anything. A teleport is not a walk
## and has no direction in it, so a longer jump keeps the yaw rather than facing
## wherever the destination happens to lie; so does arriving where you already
## were, which is what a relayout and a resync each replay.
static func yaw_towards(from: Vector2i, to: Vector2i, keep: float) -> float:
	var delta := to - from

	if delta == Vector2i.ZERO or absi(delta.x) > 1 or absi(delta.y) > 1:
		return keep

	return atan2(float(delta.x), float(-delta.y))


## Face the way the last step went.
##
## Called from [method _place_marker] rather than from the `room_changed`
## handler, so every path that moves the marker turns the figure with it — and
## the paths that move it without a step (a relayout, an island arriving late)
## hand [method yaw_towards] a zero-length move, which keeps the yaw.
##
## A change of island is not a step either. The two z values are compared before
## the cells are, because cell (4,2) on the oasis and cell (4,2) in the wastes
## are not neighbours however close their coordinates read.
func _turn_avatar() -> void:
	if _facing_z == _state.current_z:
		_avatar_yaw = yaw_towards(_facing_cell, _state.current_cell, _avatar_yaw)

	_facing_cell = _state.current_cell
	_facing_z = _state.current_z

	# Nothing is written to the node here. This names the direction, and
	# [method _process] turns the figure towards it over TURN_SPEED -- an
	# instant quarter turn at the head of every step was a snap that no amount
	# of smoothing on the POSITION could hide.


# ─── Aura ────────────────────────────────────────────────────────────────────

## Draw the aura footprint.
##
## The ring is built from `radius` on activate and torn down on deactivate,
## NOT from the pulses. That is the server's own instruction -- see the comment
## beside emit_aura's activate call in systems/gameplay/combat/auras/aura_handler.py --
## and the reason is that a ring rebuilt per pulse would flicker on the pulse
## cadence.
##
## `tiles` therefore goes unread. It carries the same footprint the radius
## already describes, enumerated, and enumerating it here would buy a second
## MultiMesh and a second thing to keep in step with the ring.
##
## This is the only channel that names ground the observer is not standing on.
## It is sent to the aura's OWNER alone, because the text game does not show
## anyone else a player's aura radius either.
func _on_aura(payload: Dictionary) -> void:
	var event := str(payload.get("event", ""))

	if event == AURA_EVENT_PULSE:
		_pulse_aura()
		return

	var radius := int(payload.get("radius", 0))

	if event == AURA_EVENT_DEACTIVATE or radius <= 0:
		_aura.visible = false
		return

	var ring := TorusMesh.new()

	ring.inner_radius = maxf(float(radius) * STEP - AURA_RING_THICKNESS, 0.01)
	ring.outer_radius = float(radius) * STEP + AURA_RING_THICKNESS

	_aura.mesh = ring
	_aura.visible = true


func _pulse_aura() -> void:
	if not _aura.visible:
		return

	var material: StandardMaterial3D = _aura.material_override

	material.albedo_color.a = AURA_PULSE_ALPHA

	var tween := create_tween()

	tween.tween_property(material, "albedo_color:a", AURA_ALPHA, AURA_PULSE_SECONDS)


# ─── Private helpers ─────────────────────────────────────────────────────────

## A MultiMesh of one mesh, `count` times. `use_colors` gives each instance
## its own colour.
func _new_multimesh(mesh: Mesh, count: int, use_colors := true) -> MultiMesh:
	var multi := MultiMesh.new()

	multi.transform_format = MultiMesh.TRANSFORM_3D
	multi.use_colors = use_colors
	multi.mesh = mesh
	multi.instance_count = count

	return multi


func _instance_of(multi: MultiMesh) -> MultiMeshInstance3D:
	var node := MultiMeshInstance3D.new()

	node.multimesh = multi

	return node
