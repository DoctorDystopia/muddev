class_name PropMeshBuilder
extends RefCounted
## The primitive scenery of one chunk: a plain shape on the tile of each
## object whose scenery key is a primitive.
##
## The server names the scenery of each object kind
## ([method TileTables.scenery_of]). A key in
## [code]SCENERY_PRIMITIVES[/code] has no model record yet, so this class
## draws it: a ladder, a flight of stairs, a hatch, or a decor shape. When
## the art arrives,
## the key leaves that list, and [TerrainView] stands the model. This class
## then draws nothing for it, with no edit here (Nick, 09/27/2026).
##
## The client ([TerrainView]) and the terrain editor ([TerrainWorld]) both draw
## the primitives through this class, as they both draw the walls through
## [WallMeshBuilder]. Thus, what an author sees is what a player sees.
##
## ## The rotation
##
## The rotation of the object turns the shape in quarter turns, clockwise
## from above, as [method TerrainView._stand] turns a model. At rotation 0,
## the front of a shape faces north.
##
## - A ladder stands at the back edge of its tile. A climber stands in front
##   of it.
## - A flight of stairs rises toward the front, over the tiles in front of
##   its tile. The run of its kind gives the tiles
##   ([method TileTables.climb_run]). The bottom step is at the front edge of
##   its tile. A climber stands on that tile, at the foot of the flight.
## - The top of a flight is two newel posts at the back edge of its tile,
##   one at each side of the flight below.
## - A hatch has its handle on the front edge.
## - A crate, a table, and a lamp post are decor (DESIGN-0013 Phase S4). A
##   crate and a table stand on the centre of the tile. A table is wider
##   than it is deep. The arm of a lamp post reaches toward the front.
## - An oil lamp and a torch are decor too (10/18/2026). The oil lamp is a
##   small lamp with a glass chimney, on the ground of its tile. A tile
##   holds one decor, so the nudge of its look puts it on a table beside
##   it. The torch is a metal pole with a cup and a flame on top. The glass
##   and the flame glow with the light of their rows.
##
## ## A new primitive
##
## A primitive of the server with no shape here draws a plain post, so new
## content needs no client edit. A shape here that the server does not name
## is a bug. `test_prop_mesh.gd` checks both lists.
##
## ## The lamp light (10/18/2026)
##
## The lamps that reach the chunk bake into each vertex, as on the ground
## ([TileLights]). The lamp of a lamp post glows with the light of its row
## ([LightLook]), so the bulb shows the colour that it gives off.

const _Const := preload("res://autoload/blackout_constants.gd")

## Every primitive that this class draws with its own shape.
const SHAPES := [_Const.SCENERY_LADDER, _Const.SCENERY_STAIRS,
	_Const.SCENERY_HATCH, _Const.SCENERY_STAIRS_TOP, _Const.SCENERY_CRATE,
	_Const.SCENERY_TABLE, _Const.SCENERY_LAMP_POST, _Const.SCENERY_OIL_LAMP,
	_Const.SCENERY_TORCH]

## How high a ladder and a flight of stairs rise: one plane. The terrain
## editor starts a new plane 32 height steps up (TerrainWorld.NEW_PLANE_RISE),
## and a height step is 1/16 of a unit.
const CLIMB_HEIGHT := 2.0

## How far the base of a shape sinks into the ground, so no gap shows on a
## slope.
const SINK := 0.05

## The ladder: the distance between its rails, the thickness of a rail and a
## rung, the gap between two rungs, and how far behind the tile centre it
## stands.
const LADDER_WIDTH := 0.5
const RAIL_SIZE := 0.06
const RUNG_SIZE := 0.04
const RUNG_GAP := 0.28
const LADDER_BACK := 0.38

## The stairs: the steps on each tile of the run, and the width of a step. A
## stairs primitive on a kind with no run draws a flight of one tile.
const STEPS_PER_TILE := 4
const STAIRS_WIDTH := 0.8
const FLIGHT_MIN := 1

## The newel posts at the top of a flight: the side and the height of a
## post.
const NEWEL_SIZE := 0.1
const NEWEL_HEIGHT := 0.9

## The hatch: the side of the door, the width and the height of the frame,
## how far the door sits over the ground, and the size of the handle.
const HATCH_SIZE := 0.7
const FRAME_WIDTH := 0.06
const FRAME_HEIGHT := 0.08
const HATCH_LIFT := 0.03
const HANDLE_SIZE := 0.08

## The crate: the side of the box, and the height of its lid. The lid is a
## little wider than the box.
const CRATE_SIZE := 0.6
const CRATE_LID_HEIGHT := 0.06
const CRATE_LID_LIP := 0.02

## The table. The top has a width across the front, a depth, a height, and
## a thickness. Each leg has a side, and it stands in from the edge of the
## top by the inset.
const TABLE_WIDTH := 0.9
const TABLE_DEPTH := 0.6
const TABLE_HEIGHT := 0.5
const TABLE_TOP := 0.05
const TABLE_LEG := 0.06
const TABLE_LEG_INSET := 0.05

## The lamp post. The pole has a side and a height. The arm has a length and
## a thickness. The lamp hangs under the end of the arm. The lamp and the
## base each have a side and a height.
const LAMP_POLE_SIZE := 0.08
const LAMP_HEIGHT := 1.8
const LAMP_ARM := 0.35
const LAMP_ARM_SIZE := 0.05
const LAMP_SIZE := 0.16
const LAMP_LAMP_HEIGHT := 0.1
const LAMP_BASE_SIZE := 0.2
const LAMP_BASE_HEIGHT := 0.06

## The oil lamp. The base has a side and a height. The reservoir sits on
## it, with a side and a height. The glass chimney stands on the
## reservoir, with a side and a height. The whole is small, for a table.
const OIL_LAMP_BASE_SIZE := 0.16
const OIL_LAMP_BASE_HEIGHT := 0.03
const OIL_LAMP_BODY_SIZE := 0.12
const OIL_LAMP_BODY_HEIGHT := 0.1
const OIL_LAMP_GLASS_SIZE := 0.08
const OIL_LAMP_GLASS_HEIGHT := 0.18

## The torch. The pole has a side and a height. The cup sits on the pole,
## with a side and a height. The flame rises out of the cup, with a side
## and a height.
const TORCH_POLE_SIZE := 0.05
const TORCH_HEIGHT := 1.2
const TORCH_CUP_SIZE := 0.14
const TORCH_CUP_HEIGHT := 0.1
const TORCH_FLAME_SIZE := 0.08
const TORCH_FLAME_HEIGHT := 0.16

## The post of a primitive with no shape here: its side and its height.
const POST_SIZE := 0.15
const POST_HEIGHT := 1.0


## The arrays of the mesh under construction. A class, not a Dictionary: a
## packed array read out of a Dictionary is a copy.
class _Surface:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()
	var lamp := PackedFloat32Array()


## Where one shape stands. The origin is the ground point of the tile
## centre, with the nudge of its look. The basis is the turn of its object,
## with the tilt and the scale of its look. The run is that of its kind.
## The lights are the lamps that reach the tile, and the glow is the light
## that the shape itself gives off: black for every shape but a lamp.
class _Place:
	var origin: Vector3
	var basis: Basis
	var run := 0
	var lights: Array = []
	var glow := Color.BLACK

	## The direction of a local normal under the basis, with the scale
	## taken out.
	func normal(local: Vector3) -> Vector3:
		return (basis * local).normalized()


## The primitive mesh of one chunk. A chunk with no primitive gives a mesh
## with no surface. `lights` is the lamps that reach the chunk, from
## [method TileLights.collect].
static func build(chunk: ChunkFile, lights: Array = []) -> ArrayMesh:
	var out := _Surface.new()
	var buckets := TileLights.bucket(chunk, lights)

	for thing: Dictionary in chunk.objects:
		var shape := primitive_of(thing["kind"])

		if shape.is_empty():
			continue

		var place := _place(chunk, thing)

		place.lights = buckets.get(thing["y"] * _Const.CHUNK_SIZE + thing["x"], [])
		place.glow = _glow_of(shape)
		_add_shape(shape, place, out)

	var mesh := ArrayMesh.new()

	TerrainMaterial.add_surface(mesh,
		TerrainMaterial.arrays_of(out.vertices, out.normals, out.colors, out.lamp))

	return mesh


## The light that a shape gives off: the glow of its row in [LightLook], or
## black for a shape with no light.
static func _glow_of(shape: String) -> Color:
	var row := LightLook.light_of(shape)

	if not LightLook.is_lit(row):
		return Color.BLACK

	return LightLook.glow_of(row)


## The primitive of an object kind, or "" when its scenery is a model or it
## has none.
static func primitive_of(kind: String) -> String:
	var key: String = TileTables.scenery_of(kind)

	if key in _Const.SCENERY_PRIMITIVES:
		return key

	return ""


## The top of each step tile of each flight on `chunks`, as world tile to
## world height, for [method TerrainPicking.ray_hit]. The top of a tile is
## the top of its highest step. The client picks with it, so a click on a
## high step picks the tile of that step. The server gives that tile the
## climb.
static func pick_tops(chunks: ChunkSet) -> Dictionary:
	var tops := {}

	for coord: Vector2i in chunks.chunk_coords():
		var chunk := chunks.get_chunk(coord)

		for thing: Dictionary in chunk.objects:
			if primitive_of(thing["kind"]) == _Const.SCENERY_STAIRS:
				_add_flight_tops(chunk, thing, tops)

	return tops


static func _add_flight_tops(chunk: ChunkFile, thing: Dictionary, tops: Dictionary) -> void:
	var place := _place(chunk, thing)
	var run := maxi(place.run, FLIGHT_MIN)
	var foot := Vector2i(chunk.cx, chunk.cy) * _Const.CHUNK_SIZE \
		+ Vector2i(thing["x"], thing["y"])
	var ahead := ClimbRule.facing(thing["rotation"])

	for index: int in range(1, run + 1):
		var tile := foot + ahead * index
		var top := place.origin.y + CLIMB_HEIGHT * index / run

		tops[tile] = maxf(tops.get(tile, top), top)


## How many objects of one chunk draw a primitive. For a test.
static func prop_count(chunk: ChunkFile) -> int:
	var count := 0

	for thing: Dictionary in chunk.objects:
		if not primitive_of(thing["kind"]).is_empty():
			count += 1

	return count


static func _place(chunk: ChunkFile, thing: Dictionary) -> _Place:
	var lx: int = thing["x"]
	var ly: int = thing["y"]
	var world_x := chunk.cx * _Const.CHUNK_SIZE + lx
	var world_y := chunk.cy * _Const.CHUNK_SIZE + ly
	var ground := ChunkMeshBuilder.surface_height(chunk, lx + 0.5, ly + 0.5) \
		* ChunkMeshBuilder.HEIGHT_STEP
	var place := _Place.new()
	var look: Dictionary = thing.get("look", {})

	# A shape faces -Z as built, so it turns by -rotation. The tilt of the
	# look rides on that turn. The scale of the look sizes the shape about
	# the ground point (10/16/2026).
	var turn := ObjectLook.turn_of(look) + Vector3(0.0, -int(thing["rotation"]) * PI * 0.5, 0.0)

	place.origin = Vector3(world_x * ChunkMeshBuilder.TILE_SIZE, ground,
		-world_y * ChunkMeshBuilder.TILE_SIZE) + ObjectLook.offset_of(look)
	place.basis = Basis.from_euler(turn).scaled(Vector3.ONE * ObjectLook.scale_of(look))
	place.run = TileTables.climb_run(thing["kind"])

	return place


static func _add_shape(shape: String, place: _Place, out: _Surface) -> void:
	if shape == _Const.SCENERY_LADDER:
		_add_ladder(place, out)
	elif shape == _Const.SCENERY_STAIRS:
		_add_stairs(place, out)
	elif shape == _Const.SCENERY_HATCH:
		_add_hatch(place, out)
	elif shape == _Const.SCENERY_STAIRS_TOP:
		_add_stairs_top(place, out)
	elif shape == _Const.SCENERY_CRATE:
		_add_crate(place, out)
	elif shape == _Const.SCENERY_TABLE:
		_add_table(place, out)
	elif shape == _Const.SCENERY_LAMP_POST:
		_add_lamp_post(place, out)
	elif shape == _Const.SCENERY_OIL_LAMP:
		_add_oil_lamp(place, out)
	elif shape == _Const.SCENERY_TORCH:
		_add_torch(place, out)
	else:
		var half := POST_SIZE * 0.5

		_add_box(place, Vector3(-half, -SINK, -half), Vector3(half, POST_HEIGHT, half),
			WallPalette.side_color(_Const.TILE_DEFAULT_WALL_STYLE), out)


# ─── The shapes ─────────────────────────────────────────────────────────────
# Each shape is boxes in the local frame of its tile: x to the east, y up, and
# -z to the front, before the turn.

## Two rails and a rung every [constant RUNG_GAP], at the back of the tile.
static func _add_ladder(place: _Place, out: _Surface) -> void:
	var half_rail := RAIL_SIZE * 0.5
	var back := LADDER_BACK
	var color := FloorPalette.prop("ladder")

	for side: float in [-1.0, 1.0]:
		var x := side * LADDER_WIDTH * 0.5

		_add_box(place, Vector3(x - half_rail, -SINK, back - half_rail),
			Vector3(x + half_rail, CLIMB_HEIGHT, back + half_rail), color, out)

	var half_rung := RUNG_SIZE * 0.5
	var half_width := LADDER_WIDTH * 0.5
	var height := RUNG_GAP

	while height < CLIMB_HEIGHT:
		_add_box(place, Vector3(-half_width, height - half_rung, back - half_rung),
			Vector3(half_width, height + half_rung, back + half_rung), color, out)
		height += RUNG_GAP


## [constant STEPS_PER_TILE] solid steps for each tile of the run, from the
## front edge of the tile out. The top step is one plane up.
static func _add_stairs(place: _Place, out: _Surface) -> void:
	var count := maxi(place.run, FLIGHT_MIN) * STEPS_PER_TILE
	var depth := ChunkMeshBuilder.TILE_SIZE / STEPS_PER_TILE
	var rise := CLIMB_HEIGHT / count
	var half_width := STAIRS_WIDTH * 0.5
	var front := -ChunkMeshBuilder.TILE_SIZE * 0.5

	for step: int in count:
		var near := front - step * depth

		_add_box(place, Vector3(-half_width, -SINK, near - depth),
			Vector3(half_width, (step + 1) * rise, near),
			FloorPalette.prop("stairs"), out)


## Two newel posts at the back edge of the tile, one at each side of the
## flight that rises to it from behind.
static func _add_stairs_top(place: _Place, out: _Surface) -> void:
	var half := NEWEL_SIZE * 0.5
	var back := ChunkMeshBuilder.TILE_SIZE * 0.5 - half
	var color := FloorPalette.prop("stairs")

	for side: float in [-1.0, 1.0]:
		var x := side * (STAIRS_WIDTH * 0.5 + half)

		_add_box(place, Vector3(x - half, -SINK, back - half),
			Vector3(x + half, NEWEL_HEIGHT, back + half), color, out)


## A dark door in a frame, with a handle on the front edge.
static func _add_hatch(place: _Place, out: _Surface) -> void:
	var half := HATCH_SIZE * 0.5
	var inner := half - FRAME_WIDTH
	var frame := FloorPalette.prop("hatch_frame")

	_add_box(place, Vector3(-inner, -SINK, -inner), Vector3(inner, HATCH_LIFT, inner),
		FloorPalette.prop("hatch"), out)
	_add_box(place, Vector3(-half, -SINK, -half), Vector3(half, FRAME_HEIGHT, -inner),
		frame, out)
	_add_box(place, Vector3(-half, -SINK, inner), Vector3(half, FRAME_HEIGHT, half),
		frame, out)
	_add_box(place, Vector3(-half, -SINK, -inner), Vector3(-inner, FRAME_HEIGHT, inner),
		frame, out)
	_add_box(place, Vector3(inner, -SINK, -inner), Vector3(half, FRAME_HEIGHT, inner),
		frame, out)

	var handle := HANDLE_SIZE * 0.5
	var front := -inner + HANDLE_SIZE

	_add_box(place, Vector3(-handle, HATCH_LIFT, front - handle),
		Vector3(handle, HATCH_LIFT + HANDLE_SIZE, front + handle), frame, out)


## A box with a lid a little wider than the box.
static func _add_crate(place: _Place, out: _Surface) -> void:
	var half := CRATE_SIZE * 0.5
	var body := CRATE_SIZE - CRATE_LID_HEIGHT
	var lid := half + CRATE_LID_LIP

	_add_box(place, Vector3(-half, -SINK, -half), Vector3(half, body, half),
		FloorPalette.prop("crate"), out)
	_add_box(place, Vector3(-lid, body, -lid), Vector3(lid, CRATE_SIZE, lid),
		FloorPalette.prop("crate_lid"), out)


## A flat top on four legs, wider across the front than deep.
static func _add_table(place: _Place, out: _Surface) -> void:
	var half_x := TABLE_WIDTH * 0.5
	var half_z := TABLE_DEPTH * 0.5
	var under := TABLE_HEIGHT - TABLE_TOP
	var color := FloorPalette.prop("table")

	_add_box(place, Vector3(-half_x, under, -half_z), Vector3(half_x, TABLE_HEIGHT, half_z),
		color, out)

	var leg_x := half_x - TABLE_LEG_INSET - TABLE_LEG
	var leg_z := half_z - TABLE_LEG_INSET - TABLE_LEG

	for x: float in [-leg_x - TABLE_LEG, leg_x]:
		for z: float in [-leg_z - TABLE_LEG, leg_z]:
			_add_box(place, Vector3(x, -SINK, z), Vector3(x + TABLE_LEG, under, z + TABLE_LEG),
				color, out)


## A pole on a base, with an arm toward the front and a lamp under its end.
static func _add_lamp_post(place: _Place, out: _Surface) -> void:
	var pole := LAMP_POLE_SIZE * 0.5
	var base := LAMP_BASE_SIZE * 0.5
	var arm := LAMP_ARM_SIZE * 0.5
	var lamp := LAMP_SIZE * 0.5
	var color := FloorPalette.prop("lamp_post")
	var arm_low := LAMP_HEIGHT - LAMP_ARM_SIZE

	_add_box(place, Vector3(-base, -SINK, -base), Vector3(base, LAMP_BASE_HEIGHT, base),
		color, out)
	_add_box(place, Vector3(-pole, -SINK, -pole), Vector3(pole, LAMP_HEIGHT, pole),
		color, out)
	_add_box(place, Vector3(-arm, arm_low, -LAMP_ARM - lamp), Vector3(arm, LAMP_HEIGHT, -pole),
		color, out)
	_add_box(place, Vector3(-lamp, arm_low - LAMP_LAMP_HEIGHT, -LAMP_ARM - lamp),
		Vector3(lamp, arm_low, -LAMP_ARM + lamp), FloorPalette.prop("lamp"), out,
		place.glow)


## A small base, a reservoir on it, and a glass chimney that glows, on the
## centre of the tile.
static func _add_oil_lamp(place: _Place, out: _Surface) -> void:
	var base := OIL_LAMP_BASE_SIZE * 0.5
	var body := OIL_LAMP_BODY_SIZE * 0.5
	var glass := OIL_LAMP_GLASS_SIZE * 0.5
	var body_top := OIL_LAMP_BASE_HEIGHT + OIL_LAMP_BODY_HEIGHT
	var color := FloorPalette.prop("oil_lamp")

	_add_box(place, Vector3(-base, -SINK, -base), Vector3(base, OIL_LAMP_BASE_HEIGHT, base),
		color, out)
	_add_box(place, Vector3(-body, OIL_LAMP_BASE_HEIGHT, -body), Vector3(body, body_top, body),
		color, out)
	_add_box(place, Vector3(-glass, body_top, -glass),
		Vector3(glass, body_top + OIL_LAMP_GLASS_HEIGHT, glass),
		FloorPalette.prop("oil_lamp_glass"), out, place.glow)


## A metal pole with a cup on top, and a flame that glows out of the cup.
static func _add_torch(place: _Place, out: _Surface) -> void:
	var pole := TORCH_POLE_SIZE * 0.5
	var cup := TORCH_CUP_SIZE * 0.5
	var flame := TORCH_FLAME_SIZE * 0.5
	var cup_low := TORCH_HEIGHT - TORCH_CUP_HEIGHT
	var color := FloorPalette.prop("torch")

	_add_box(place, Vector3(-pole, -SINK, -pole), Vector3(pole, cup_low, pole), color, out)
	_add_box(place, Vector3(-cup, cup_low, -cup), Vector3(cup, TORCH_HEIGHT, cup), color, out)
	_add_box(place, Vector3(-flame, TORCH_HEIGHT, -flame),
		Vector3(flame, TORCH_HEIGHT + TORCH_FLAME_HEIGHT, flame),
		FloorPalette.prop("torch_flame"), out, place.glow)


# ─── Boxes ──────────────────────────────────────────────────────────────────

## Add the six faces of a box from `low` to `high`, local corners before the
## turn. The top face is lighter, so the shape reads from above. `glow` is
## the light that the box itself gives off, for the lamp of a lamp post.
static func _add_box(place: _Place, low: Vector3, high: Vector3, color: Color,
		out: _Surface, glow := Color.BLACK) -> void:
	var corners: Array[Vector3] = []

	for index: int in 8:
		var local := Vector3(high.x if index & 1 else low.x,
			high.y if index & 2 else low.y, high.z if index & 4 else low.z)

		corners.append(place.origin + place.basis * local)

	var top := color.lightened(FloorPalette.PROP_TOP_LIGHTEN)

	# Each face: its four corner indexes in ring order, and its local normal.
	# The top and the bottom turn with the tilt too.
	_add_quad(corners, [0, 1, 3, 2], place.normal(Vector3.FORWARD), color, place, glow, out)
	_add_quad(corners, [4, 5, 7, 6], place.normal(Vector3.BACK), color, place, glow, out)
	_add_quad(corners, [0, 2, 6, 4], place.normal(Vector3.LEFT), color, place, glow, out)
	_add_quad(corners, [1, 3, 7, 5], place.normal(Vector3.RIGHT), color, place, glow, out)
	_add_quad(corners, [0, 1, 5, 4], place.normal(Vector3.DOWN), color, place, glow, out)
	_add_quad(corners, [2, 3, 7, 6], place.normal(Vector3.UP), top, place, glow, out)


## Add a quad as two triangles, each with its front along `outward`. As in
## [ChunkMeshBuilder], (c - a) x (b - a) points out of the front. Each
## corner takes the lamp light of the place at its point, plus `glow`.
static func _add_quad(corners: Array[Vector3], ring: Array, outward: Vector3,
		color: Color, place: _Place, glow: Color, out: _Surface) -> void:
	var a := corners[ring[0]]
	var b := corners[ring[1]]
	var c := corners[ring[2]]
	var d := corners[ring[3]]

	if (c - a).cross(b - a).dot(outward) < 0.0:
		var swap := b

		b = d
		d = swap

	for corner: Vector3 in [a, b, c, a, c, d]:
		out.vertices.append(corner)
		out.normals.append(outward)
		out.colors.append(color)
		TileLights.append(out.lamp, glow + TileLights.lit(corner, outward, place.lights))
