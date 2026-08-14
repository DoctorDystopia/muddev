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

const CH_MAP := "blackout_map"
const CH_ROOM_INFO := "room_info"
const CH_ROOM_PLAYERS := "room_players"
const CH_PLAYER_ADD := "room_add_player"
const CH_PLAYER_REMOVE := "room_remove_player"
const CH_COMBAT := "blackout_combat"
const CH_AURA := "blackout_aura"

const AURA_EVENT_DEACTIVATE := "deactivate"
const AURA_EVENT_PULSE := "pulse"
const AURA_RING_THICKNESS := 0.06
const AURA_PULSE_SECONDS := 0.4
const AURA_ALPHA := 0.55
const AURA_PULSE_ALPHA := 1.0

## How near the cursor an entity has to be, in pixels, to be what you clicked.
const PICK_REACH_PIXELS := 24.0

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

const ROOM_KIND_COLORS := {
	"Bank": Color("4488ff"),
	"Foundry Furnace Facility": Color("dd4422"),
	"Metalsmith Anvil Facility": Color("aaaaaa"),
	"Pole clearing": Color("cc6633"),
	"Shopkeeper": Color("ddcc44"),
	"Mutant Raider Tile": Color("8fbf00"),
	"Big Mutant Tile": Color("bf3f00"),
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


func _ready() -> void:
	_tile_material = _vertex_coloured()
	_link_material = _vertex_coloured()
	Evennia.channel_received.connect(_on_channel)


func _on_channel(channel: String, payload: Dictionary) -> void:
	match channel:
		CH_MAP:
			var completed := _state.ingest_map_chunk(payload)

			if not completed.is_empty():
				_relayout()

		CH_ROOM_INFO:
			_state.ingest_room_info(payload)
			_place_marker()

		CH_ROOM_PLAYERS:
			_entities.replace_all(payload.get("entities", []))

		CH_PLAYER_ADD:
			_entities.add(payload.get("entity", {}))

		CH_PLAYER_REMOVE:
			_entities.remove(int(payload.get("entity_id", 0)))

		CH_COMBAT:
			if payload.get("hit", false):
				_entities.flash(int(payload.get("target_id", 0)))

		CH_AURA:
			_on_aura(payload)


# ─── Clicking ────────────────────────────────────────────────────────────────

func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return

	var click := event as InputEventMouseButton

	if click.button_index == MOUSE_BUTTON_LEFT and click.pressed:
		_act_on(click.position)


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
	var target := str(entity.get("name", ""))

	if target.is_empty():
		return

	match str(entity.get("kind", "")):
		"npc":
			Evennia.command("attack %s" % target)
		"item":
			Evennia.command("get %s" % target)
		"gatherable":
			# Harvested where it stands, never pocketed -- a node carries
			# `get:false()`, so offering `get` here proposes the one thing the
			# object refuses.
			#
			# Every gathering node in the game today is a cutting node. When a
			# second verb appears, the server should name it in the payload
			# rather than this file growing a table of them: the verb belongs
			# with GATHERABLE_REGISTRY, not with the renderer.
			Evennia.command("cut %s" % target)

	# A `character` is another player, and deliberately falls through to
	# nothing. Everything else here is recoverable; opening combat on a person
	# because of a stray click is not the sort of thing a misclick should be
	# able to do.


func _walk_towards(cell: Vector2i) -> void:
	var direction := WorldState.direction_for(cell - _state.current_cell)

	if direction.is_empty():
		return

	# Refused rather than sent: the server would only answer "you cannot go
	# that way", and the exits it already told us about are enough to know.
	if not _state.current_exits.has(direction):
		return

	Evennia.command(direction)


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

	island.add_child(_build_tiles(level, offset))

	if not level.links.is_empty():
		island.add_child(_build_links(level, offset))


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
	if not _offsets.has(_state.current_z):
		# The room arrived before its map did. The marker stays where it was
		# until _relayout calls back here with the island in place.
		return

	var base := _tile_position(_state.current_cell, _offsets[_state.current_z])
	var top := base + Vector3(0.0, TILE_HEIGHT * 0.5, 0.0)

	_marker.position = top + Vector3(0.0, (_marker.mesh as BoxMesh).size.y * 0.5, 0.0)
	_entities.set_anchor(top)
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
