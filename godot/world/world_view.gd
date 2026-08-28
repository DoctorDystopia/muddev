class_name WorldView
extends Node3D
## The 3D world pane: tile grids, the links between them, and where you stand.
##
## Layout and colour rules are ported from the browser pane
## (web/static/webclient/js/plugins/blackout3d.js) rather than re-derived. Two
## of them are load-bearing and not obvious:
##
## **Z is a map NAME, not an elevation.** Maps are disconnected islands laid out
## along world X. Their relative placement cannot be computed from the data, so
## it is authored in Z_LAYOUT_ORDER; a map not listed still appears, after the
## named ones.
##
## **Room kinds not in the colour table are hashed to a stable hue.** A new room
## type is visually distinct with no edit here, and is the same colour every
## session and for every player.

## Every name the SERVER owns, generated from
## blackout/systems/statefeed/constants.py by systems/statefeed/clientexport.py.
##
## Preloaded rather than autoloaded: the generated file declares no `extends
## Node`, and a Godot autoload must. Do not retype a channel name here -- the
## dead "Pole clearing" room-kind key reached this file by exactly that route
## and rendered a fallback hue in both clients until 08/23/2026.
const Const := preload("res://autoload/blackout_constants.gd")

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

## How much of a tile a prop drawn ON that tile covers.
##
## Bigger than an entity on purpose: a prop is part of the ground rather than
## something standing on it, and the transition pad reads as a pad only when it
## reaches the tile's edges.
const TILE_PROP_SCALE := 0.9

## How much brighter a hovered tile is drawn. A multiplier on its own room-kind
## colour, so every kind lifts by the same amount and none needs its own entry.
const HOVER_LIFT := 1.5

const TILE_SIZE := 1.0
const TILE_GAP := 0.18
const TILE_HEIGHT := 0.16
const STEP := TILE_SIZE + TILE_GAP
const Z_LEVEL_GAP := 4.0
const LINK_WIDTH := 0.10
const LINK_HEIGHT := 0.04

const Z_LAYOUT_ORDER := ["oasis", "oasis_outskirts", "trade town sector 1"]

const COLOR_TILE_DEFAULT := Color("2b3a4a")
const COLOR_LINK := Color("2e4256")

## Saturation and lightness the browser pane gives a hash-coloured room kind.
## Named in ITS colour space -- HSL -- rather than pre-converted, so the pair
## can be compared against blackout3d.js's `setHSL(hue, 0.42, 0.42)` by eye.
const KIND_HSL_SATURATION := 0.42
const KIND_HSL_LIGHTNESS := 0.42

## Must colour the SAME set of room kinds as blackout3d.js, key for key --
## ClientRoomKindTests asserts it in both directions. A key naming no map
## prototype is dead configuration; a room kind with no key here is fine and
## hashes to a stable hue.
const ROOM_KIND_COLORS := {
	"Bank": Color("4488ff"),
	"Foundry Furnace Facility": Color("dd4422"),
	"Metalsmith Anvil Facility": Color("aaaaaa"),
	# Two clearings, not one, and they are told apart by what they yield:
	# oasis grows rusty poles, oasis_outskirts grows metal ones. Coloured for
	# the material rather than for the tile, so the map reads as a gradient
	# from scrap to stock as the player moves out.
	#
	# This said "Pole clearing" until 08/25/2026 -- a key no map has ever
	# declared, copied here from the browser pane before that pane was fixed.
	# Both real clearings rendered the hash colour and nothing errored.
	"Rusty pole clearing": Color("cc6633"),
	"Metal pole clearing": Color("8899a6"),
	"Shopkeeper": Color("ddcc44"),
	"Mutant Raider Tile": Color("8fbf00"),
	"Big Mutant Tile": Color("bf3f00"),
	# Not a prototype key like the rest: the server synthesises this one for a
	# node that spawns no room. It is the way OFF the map, so it is coloured
	# whether or not the teleporter model is there to stand on it.
	#
	# A LITERAL, though Const.ROOM_KIND_TRANSITION holds the same string and
	# blackout_models.js imports it. ClientRoomKindTests reads both clients as
	# TEXT -- that is what lets one test cover two languages without importing
	# either -- so a key written as a constant reference is invisible to it and
	# reads as "this client colours nothing here". blackout3d.js spells it
	# literally for the same reason. Making the scraper resolve constant
	# references would let both use Const; until then the literal is what keeps
	# the guard honest.
	"map_transition": Color("35e0c0"),
}

@onready var _islands: Node3D = $Islands
@onready var _marker: MeshInstance3D = $Marker
@onready var _entities: EntityPool = $Entities
@onready var _aura: MeshInstance3D = $Aura
@onready var _camera: Camera3D = $Camera/SpringArm3D/Camera3D

var _state := WorldState.new()
var _offsets: Dictionary = {}      # z -> world X offset of that island
var _tile_material: StandardMaterial3D
var _link_material: StandardMaterial3D

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

## The observer's own state, bound by the console. Read for `asset` and
## `family` and nothing else.
##
## Bound rather than ingested here. [CharState] already owns char_avatar, and a
## second reader parsing the same channel would be the third module to own one
## fact -- which is exactly how the android's dialogue came to print
## `talk:tester: 0/True` at players.
var _char: CharState

## z -> the MultiMesh drawing that island's tiles, kept so one instance's colour
## can be written for hover. Cleared and refilled by _relayout.
var _tile_meshes: Dictionary = {}

## Which tile is currently lit, and on which island. Empty z means none.
var _hover_z := ""
var _hover_cell := Vector2i.ZERO


func _ready() -> void:
	_tile_material = _vertex_coloured()
	_link_material = _vertex_coloured()

	Evennia.channel_received.connect(_on_channel)


## Give the pane its mesh source. Called by the console, which owns it.
##
## Not done in _ready, because a child's _ready runs BEFORE its parent's -- so
## at that point the console has not built the resolver yet and this pane would
## bind null.
func bind_meshes(resolver: MeshResolver) -> void:
	_meshes = resolver
	_entities.bind(_meshes, _locate_coords)
	_meshes.refreshed.connect(_on_art_arrived)

	# Something stands on the marker from the first frame, before char_avatar
	# has said which asset you are. The generic character figure is the right
	# placeholder: it is what every OTHER player in the room is drawn as, so you
	# look like a person immediately and sharpen into your own model later.
	_redraw_avatar()


## Follow the observer's own state. Called by the console, which owns it.
func bind_char(state: CharState) -> void:
	_char = state
	_char.changed.connect(_redraw_avatar)
	_redraw_avatar()


## Draw whoever you currently are on the marker tile.
##
## The marker's own box mesh is hidden the moment there is a figure to replace
## it — it was never meant to be a character, only a stand-in for one.
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
	# Rests on the tile by measurement, like everything standing beside it.
	var bounds := ModelLoader.bounds_of(_avatar)
	_avatar.position = Vector3(0.0, -bounds.position.y * AVATAR_SCALE, 0.0)
	_marker.add_child(_avatar)

	# The BOX goes, not the node. `visible = false` would take the avatar with
	# it -- visibility is inherited in Godot -- and the marker itself has to
	# stay: it is what the camera rig follows by NodePath and what
	# _place_marker moves.
	_marker.mesh = null


## Redraw when art lands for something this pane is drawing.
##
## Two callers in one, because both are "the fallback is on screen and the real
## thing has just arrived". The relayout terminates rather than looping: the
## rebuild asks resolve_scenery again, which now answers from the cache and
## starts no second fetch.
func _on_art_arrived(asset_key: String) -> void:
	if _char != null and _char.asset == asset_key:
		_redraw_avatar()

	if _any_tile_is_kind(asset_key):
		_relayout()


## Whether any island holds a tile of this room kind.
##
## Asked before relaying out, so art arriving for something not on screen -- an
## item fetched for the room, a model the inventory wanted -- does not rebuild
## every island for nothing.
func _any_tile_is_kind(kind: String) -> bool:
	for z: String in _state.levels:
		var level: WorldState.Level = _state.levels[z]

		if level.kinds.has(kind):
			return true

	return false


func _on_channel(channel: String, payload: Dictionary) -> void:
	match channel:
		Const.CH_MAP:
			var completed := _state.ingest_map_chunk(payload)

			if not completed.is_empty():
				_relayout()

		Const.CH_ROOM_INFO:
			_state.ingest_room_info(payload)
			_place_marker()

		Const.CH_ROOM_PLAYERS:
			_entities.replace_all(payload.get("entities", []))

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


## Where an entity's `coords` put it in the world, or null if not placeable yet.
##
## Handed to [EntityPool] as a callable, so the placement maths has one owner:
## this pane already decides where a tile is, and a second copy in the pool
## would be free to disagree with the tiles actually drawn.
##
## Null and not a fallback position. `STATEFEED_ENTITY_RADIUS` is 10, so the
## feed names entities across a 441-room neighbourhood, and any island that has
## not arrived yet has no honest place to put them. Guessing put the whole
## neighbourhood on the observer's own tile, which is the bug this replaced.
func _locate_coords(coords: Array) -> Variant:
	if coords.size() < 3:
		return null

	var z := str(coords[2])

	if not _offsets.has(z):
		return null

	# Every number in a parsed payload is a float; converted here, at the point
	# of use, like every other coordinate in this client.
	var cell := Vector2i(int(coords[0]), int(coords[1]))
	var base := _tile_position(cell, _offsets[z])

	return base + Vector3(0.0, TILE_HEIGHT * 0.5, 0.0)


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
		var affords := _interaction(_entities.entity(entity_id))

		_entities.hover(entity_id if not affords.is_empty() else 0)
		return

	_entities.hover(0)
	_hover_tile(_cell_under(screen_point))


## Brighten one tile, and put the last one back.
##
## Written through the MultiMesh's instance colour rather than by tinting a
## material: the tiles of one island are ONE mesh drawn many times, so there is
## no per-tile material to write to. That is also why the previous tile has to be
## restored by hand from the room kind -- nothing else remembers what it was.
func _hover_tile(cell: Vector2i) -> void:
	if cell == _hover_cell and _state.current_z == _hover_z:
		return

	_clear_tile_hover()

	var multi: MultiMesh = _tile_meshes.get(_state.current_z)

	if multi == null:
		return

	var level: WorldState.Level = _state.levels.get(_state.current_z)
	var index := -1 if level == null else level.cells.find(cell)

	if index < 0:
		return

	multi.set_instance_color(index, kind_colour(level.kinds[index]) * HOVER_LIFT)
	_hover_cell = cell
	_hover_z = _state.current_z


func _clear_tile_hover() -> void:
	if _hover_z.is_empty():
		return

	var multi: MultiMesh = _tile_meshes.get(_hover_z)
	var level: WorldState.Level = _state.levels.get(_hover_z)

	if multi != null and level != null:
		var index := level.cells.find(_hover_cell)

		if index >= 0:
			multi.set_instance_color(index, kind_colour(level.kinds[index]))

	_hover_z = ""
	_hover_cell = Vector2i.ZERO


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
	var command := _interaction(entity)

	if command.is_empty():
		return

	Evennia.command(command)


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
## Intersects the ray with the plane the tile tops lie in rather than
## raycasting against physics, because these tiles are MultiMesh instances and
## have no bodies to hit. Falls back to the observer's own cell on a miss --
## the delta is then zero, which produces no direction and therefore no move.
func _cell_under(screen_point: Vector2) -> Vector2i:
	var origin := _camera.project_ray_origin(screen_point)
	var direction := _camera.project_ray_normal(screen_point)
	var hit: Variant = Plane(Vector3.UP, TILE_HEIGHT * 0.5).intersects_ray(origin, direction)

	if hit == null:
		return _state.current_cell

	var offset: float = _offsets.get(_state.current_z, 0.0)
	var point: Vector3 = hit

	return Vector2i(roundi((point.x - offset) / STEP), roundi(-point.z / STEP))


# ─── Layout ──────────────────────────────────────────────────────────────────

## Redraw every island, packing them left to right.
##
## Every island is rebuilt rather than only the one that just completed,
## because an island's offset depends on the widths of the ones before it and a
## map can arrive in any order. This runs once per completed map -- on login and
## on resync -- so rebuilding three MultiMeshes is not worth avoiding.
func _relayout() -> void:
	for child: Node in _islands.get_children():
		# Detached before freeing: queue_free leaves the node in the tree until
		# the end of the frame, and the replacement island carries the same
		# name, which Godot would silently rename to avoid the collision.
		_islands.remove_child(child)
		child.queue_free()

	# The MultiMeshes just freed are the ones hover writes through, so the
	# bookkeeping goes with them. A stale entry here would be a write to a
	# freed resource on the next mouse move.
	_tile_meshes.clear()
	_hover_z = ""
	_offsets.clear()

	var cursor := 0.0

	for z: String in _ordered_levels():
		var level: WorldState.Level = _state.levels[z]

		_offsets[z] = cursor
		_draw_level(z, level, cursor)
		cursor += _level_width(level) * STEP + Z_LEVEL_GAP

	_place_marker()


func _ordered_levels() -> Array:
	var named: Array = []
	var rest: Array = []

	for z: String in _state.levels:
		if Z_LAYOUT_ORDER.has(z):
			named.append(z)
		else:
			rest.append(z)

	named.sort_custom(
		func(a: String, b: String) -> bool:
			return Z_LAYOUT_ORDER.find(a) < Z_LAYOUT_ORDER.find(b)
	)

	return named + rest


func _level_width(level: WorldState.Level) -> float:
	var widest := 0

	for cell: Vector2i in level.cells:
		widest = maxi(widest, cell.x)

	return float(widest + 1)


# ─── Drawing ─────────────────────────────────────────────────────────────────

func _draw_level(z: String, level: WorldState.Level, offset: float) -> void:
	var island := Node3D.new()

	island.name = z
	_islands.add_child(island)

	var tiles := _build_tiles(level, offset)

	island.add_child(tiles)
	_tile_meshes[z] = tiles.multimesh

	if not level.links.is_empty():
		island.add_child(_build_links(level, offset))

	island.add_child(_build_props(level, offset))


## Stand a model on every tile whose room kind has one.
##
## Deliberately NOT the entity path. An entity always gets a mesh, because
## something nobody has modelled still has to be visible and clickable. A prop
## is scenery: a tile whose kind has no art stays a plain coloured slab, which
## is what every tile in the game was before this. [MeshResolver.resolve_scenery]
## is that policy, in its name.
##
## The KEY IS THE ROOM KIND. `mapexport` names a transition node
## "map_transition", the served manifest lists a `.glb` under that name, and
## nothing in between has to be edited to give another room kind a prop.
func _build_props(level: WorldState.Level, offset: float) -> Node3D:
	var props := Node3D.new()

	props.name = "Props"

	for index: int in level.cells.size():
		var prop := _meshes.resolve_scenery(level.kinds[index])

		if prop == null:
			continue

		var base := _tile_position(level.cells[index], offset)

		prop.scale = Vector3.ONE * TILE_PROP_SCALE
		props.add_child(prop)

		# Rest it ON the tile rather than through it. A normalised model fills
		# the unit box on its LONGEST axis only -- the transition pad is far
		# flatter than it is wide -- so half the prop's height is not half its
		# scale, and the scaled copy has to be measured.
		var bounds := ModelLoader.bounds_of(prop)
		var top := base.y + (TILE_HEIGHT * 0.5)

		prop.position = Vector3(base.x, top - (bounds.position.y * TILE_PROP_SCALE),
			base.z)

	return props


func _build_tiles(level: WorldState.Level, offset: float) -> MultiMeshInstance3D:
	var box := BoxMesh.new()

	box.size = Vector3(TILE_SIZE, TILE_HEIGHT, TILE_SIZE)
	box.material = _tile_material

	var multi := _new_multimesh(box, level.cells.size())

	for index: int in level.cells.size():
		var origin := _tile_position(level.cells[index], offset)

		multi.set_instance_transform(index, Transform3D(Basis.IDENTITY, origin))
		multi.set_instance_color(index, kind_colour(level.kinds[index]))

	return _instance_of(multi)


func _build_links(level: WorldState.Level, offset: float) -> MultiMeshInstance3D:
	var box := BoxMesh.new()

	box.size = Vector3.ONE
	box.material = _link_material

	var multi := _new_multimesh(box, level.links.size())

	for index: int in level.links.size():
		var pair: Array = level.links[index]
		var from := _tile_position(pair[0], offset)
		var to := _tile_position(pair[1], offset)

		multi.set_instance_transform(index, link_transform(from, to))
		multi.set_instance_color(index, COLOR_LINK)

	return _instance_of(multi)


## Place a unit box so it spans from one tile centre to another.
##
## Static and public because this is the only real geometry in the file and it
## fails SILENTLY when it is wrong -- the first version used Basis.scaled and
## drew every east-west link as a long bar running north-south. Nothing errors;
## you just get a wrong picture. tests/test_world_state.tscn covers it.
static func link_transform(from: Vector3, to: Vector3) -> Transform3D:
	var span := to - from

	# scaled_local, NOT scaled. Basis.scaled multiplies the basis ROWS, which
	# applies the scale along the PARENT axes -- so `span.length()` would
	# stretch global Z no matter which way the link actually runs. scaled_local
	# multiplies the columns, which is the link's own frame.
	#
	# -Z of a looking_at basis points along the span, so scaling local Z by the
	# full length makes the box reach exactly from one centre to the other when
	# placed at the midpoint.
	var basis := Basis.looking_at(span, Vector3.UP).scaled_local(
		Vector3(LINK_WIDTH, LINK_HEIGHT, span.length())
	)
	var origin := from.lerp(to, 0.5) + Vector3(0.0, TILE_HEIGHT * 0.5, 0.0)

	return Transform3D(basis, origin)


func _place_marker() -> void:
	# BEFORE the early return. Entities are placed from their own coords now, so
	# the ones standing on islands that HAVE arrived are drawable even while the
	# observer's own map is still in flight -- and tying their placement to the
	# marker's would hold all of them back for one missing island.
	_entities.replace_positions()

	if not _offsets.has(_state.current_z):
		# The room arrived before its map did. The marker stays where it was
		# until _relayout calls back here with the island in place.
		return

	var base := _tile_position(_state.current_cell, _offsets[_state.current_z])
	var top := base + Vector3(0.0, TILE_HEIGHT * 0.5, 0.0)

	# Sits ON the tile's top face. It used to be lifted by half the box's height,
	# which stopped being meaningful when the box was replaced by a figure --
	# and would have crashed reading `.size.y` off a mesh that is now null. The
	# avatar rests itself on the face instead, so the offset belongs to the
	# thing being drawn rather than to the anchor.
	_marker.position = top
	_aura.position = top


# ─── Aura ────────────────────────────────────────────────────────────────────

## Draw the aura footprint.
##
## The ring is built from `radius` on activate and torn down on deactivate,
## NOT from the pulses. That is the server's own instruction -- see the comment
## beside emit_aura's activate call in systems/combat/auras/aura_handler.py --
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

func _tile_position(cell: Vector2i, offset: float) -> Vector3:
	# Grid Y grows northward; Godot's -Z is away from a default camera, so the
	# island reads the same way round as the text map does.
	return Vector3(offset + cell.x * STEP, 0.0, -cell.y * STEP)


## The colour a room kind is drawn in.
##
## Static and public so the browser-parity claim above it can actually be
## tested. Anything not in the table gets a stable hue, so a room type added to
## the game is visually distinct with no edit here.
static func kind_colour(kind: String) -> Color:
	if kind.is_empty():
		return COLOR_TILE_DEFAULT

	if ROOM_KIND_COLORS.has(kind):
		return ROOM_KIND_COLORS[kind]

	var hue := float(stable_hash(kind) % 360) / 360.0

	# Godot has no from_hsl, and HSV is not HSL -- feeding the browser's
	# saturation and lightness straight into from_hsv would give a different
	# colour for the same hue. This is the closed-form conversion, not a
	# match by eye.
	var value := KIND_HSL_LIGHTNESS + KIND_HSL_SATURATION * minf(
		KIND_HSL_LIGHTNESS, 1.0 - KIND_HSL_LIGHTNESS
	)

	if value <= 0.0:
		return Color.BLACK

	return Color.from_hsv(hue, 2.0 * (1.0 - KIND_HSL_LIGHTNESS / value), value)


## The browser pane's string hash, reproduced bit for bit.
##
## NOT Godot's `hash()`. Most of Blackout's room kinds are not in the colour
## table above -- "Oasis", "Oasis Outskirts", "Trade Town Sector 1" -- so this
## number is what colours most of the world, and the two panes are routinely
## put side by side on the same character. Different hashes would mean two
## differently coloured deserts and no way to tell a rendering bug from a
## rendering difference.
##
## This is JS's classic 31-multiply (`(h << 5) - h + c`) with ToInt32 applied
## every iteration, which is what `hashString` in blackout3d.js implements. The
## mask reproduces that truncation; the fold at the end reproduces JS's SIGNED
## result, which its Math.abs is applied to.
static func stable_hash(text: String) -> int:
	var value := 0

	for code: int in text.to_utf8_buffer():
		value = ((value << 5) - value + code) & 0xFFFFFFFF

	if value >= 0x80000000:
		value -= 0x100000000

	return absi(value)


func _new_multimesh(mesh: Mesh, count: int) -> MultiMesh:
	var multi := MultiMesh.new()

	multi.transform_format = MultiMesh.TRANSFORM_3D
	multi.use_colors = true
	multi.mesh = mesh
	multi.instance_count = count

	return multi


func _instance_of(multi: MultiMesh) -> MultiMeshInstance3D:
	var node := MultiMeshInstance3D.new()

	node.multimesh = multi

	return node


func _vertex_coloured() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()

	# Without this the per-instance colours set above are simply ignored and
	# every tile renders white.
	material.vertex_color_use_as_albedo = true

	return material
