class_name PropMeshBuilder
extends RefCounted
## The primitive scenery of one chunk: a plain shape on the tile of each
## object whose scenery key is a primitive.
##
## The server names the scenery of each object kind
## ([code]OBJECT_KIND_SCENERY[/code]). A key in
## [code]SCENERY_PRIMITIVES[/code] has no model record yet, so this class
## draws it: a ladder, a flight of stairs, or a hatch. When the art arrives,
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
## - A flight of stairs rises toward the front. The bottom step is at the back
##   edge.
## - A hatch has its handle on the front edge.
##
## ## A new primitive
##
## A primitive of the server with no shape here draws a plain post, so new
## content needs no client edit. A shape here that the server does not name
## is a bug. `test_prop_mesh.gd` checks both lists.

const _Const := preload("res://autoload/blackout_constants.gd")

## Every primitive that this class draws with its own shape.
const SHAPES := [_Const.SCENERY_LADDER, _Const.SCENERY_STAIRS,
	_Const.SCENERY_HATCH]

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

## The stairs: the number of steps, and the width of a step.
const STEP_COUNT := 8
const STAIRS_WIDTH := 0.8

## The hatch: the side of the door, the width and the height of the frame,
## how far the door sits over the ground, and the size of the handle.
const HATCH_SIZE := 0.7
const FRAME_WIDTH := 0.06
const FRAME_HEIGHT := 0.08
const HATCH_LIFT := 0.03
const HANDLE_SIZE := 0.08

## The post of a primitive with no shape here: its side and its height.
const POST_SIZE := 0.15
const POST_HEIGHT := 1.0


## The arrays of the mesh under construction. A class, not a Dictionary: a
## packed array read out of a Dictionary is a copy.
class _Surface:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()


## Where one shape stands: the ground point of the tile centre, and the turn
## of its object.
class _Place:
	var origin: Vector3
	var basis: Basis


## The primitive mesh of one chunk. A chunk with no primitive gives a mesh
## with no surface.
static func build(chunk: ChunkFile) -> ArrayMesh:
	var out := _Surface.new()

	for thing: Dictionary in chunk.objects:
		var shape := primitive_of(thing["kind"])

		if not shape.is_empty():
			_add_shape(shape, _place(chunk, thing), out)

	var mesh := ArrayMesh.new()

	if out.vertices.is_empty():
		return mesh

	var arrays := []

	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = out.vertices
	arrays[Mesh.ARRAY_NORMAL] = out.normals
	arrays[Mesh.ARRAY_COLOR] = out.colors
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)

	return mesh


## The primitive of an object kind, or "" when its scenery is a model or it
## has none.
static func primitive_of(kind: String) -> String:
	var key: String = _Const.OBJECT_KIND_SCENERY.get(kind, "")

	if key in _Const.SCENERY_PRIMITIVES:
		return key

	return ""


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

	place.origin = Vector3(world_x * ChunkMeshBuilder.TILE_SIZE, ground,
		-world_y * ChunkMeshBuilder.TILE_SIZE)
	place.basis = Basis(Vector3.UP, -int(thing["rotation"]) * PI * 0.5)

	return place


static func _add_shape(shape: String, place: _Place, out: _Surface) -> void:
	if shape == _Const.SCENERY_LADDER:
		_add_ladder(place, out)
	elif shape == _Const.SCENERY_STAIRS:
		_add_stairs(place, out)
	elif shape == _Const.SCENERY_HATCH:
		_add_hatch(place, out)
	else:
		var half := POST_SIZE * 0.5

		_add_box(place, Vector3(-half, -SINK, -half), Vector3(half, POST_HEIGHT, half),
			FloorPalette.WALL_COLOR, out)


# ─── The shapes ─────────────────────────────────────────────────────────────
# Each shape is boxes in the local frame of its tile: x to the east, y up, and
# -z to the front, before the turn.

## Two rails and a rung every [constant RUNG_GAP], at the back of the tile.
static func _add_ladder(place: _Place, out: _Surface) -> void:
	var half_rail := RAIL_SIZE * 0.5
	var back := LADDER_BACK
	var color := FloorPalette.LADDER_COLOR

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


## [constant STEP_COUNT] solid steps from the back edge to the front edge.
static func _add_stairs(place: _Place, out: _Surface) -> void:
	var depth := ChunkMeshBuilder.TILE_SIZE / STEP_COUNT
	var rise := CLIMB_HEIGHT / STEP_COUNT
	var half_width := STAIRS_WIDTH * 0.5
	var back := ChunkMeshBuilder.TILE_SIZE * 0.5

	for step: int in STEP_COUNT:
		var near := back - step * depth

		_add_box(place, Vector3(-half_width, -SINK, near - depth),
			Vector3(half_width, (step + 1) * rise, near),
			FloorPalette.STAIRS_COLOR, out)


## A dark door in a frame, with a handle on the front edge.
static func _add_hatch(place: _Place, out: _Surface) -> void:
	var half := HATCH_SIZE * 0.5
	var inner := half - FRAME_WIDTH
	var frame := FloorPalette.HATCH_FRAME_COLOR

	_add_box(place, Vector3(-inner, -SINK, -inner), Vector3(inner, HATCH_LIFT, inner),
		FloorPalette.HATCH_COLOR, out)
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


# ─── Boxes ──────────────────────────────────────────────────────────────────

## Add the six faces of a box from `low` to `high`, local corners before the
## turn. The top face is lighter, so the shape reads from above.
static func _add_box(place: _Place, low: Vector3, high: Vector3, color: Color,
		out: _Surface) -> void:
	var corners: Array[Vector3] = []

	for index: int in 8:
		var local := Vector3(high.x if index & 1 else low.x,
			high.y if index & 2 else low.y, high.z if index & 4 else low.z)

		corners.append(place.origin + place.basis * local)

	var top := color.lightened(FloorPalette.PROP_TOP_LIGHTEN)

	# Each face: its four corner indexes in ring order, and its local normal.
	_add_quad(corners, [0, 1, 3, 2], place.basis * Vector3.FORWARD, color, out)
	_add_quad(corners, [4, 5, 7, 6], place.basis * Vector3.BACK, color, out)
	_add_quad(corners, [0, 2, 6, 4], place.basis * Vector3.LEFT, color, out)
	_add_quad(corners, [1, 3, 7, 5], place.basis * Vector3.RIGHT, color, out)
	_add_quad(corners, [0, 1, 5, 4], Vector3.DOWN, color, out)
	_add_quad(corners, [2, 3, 7, 6], Vector3.UP, top, out)


## Add a quad as two triangles, each with its front along `outward`. As in
## [ChunkMeshBuilder], (c - a) x (b - a) points out of the front.
static func _add_quad(corners: Array[Vector3], ring: Array, outward: Vector3,
		color: Color, out: _Surface) -> void:
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
