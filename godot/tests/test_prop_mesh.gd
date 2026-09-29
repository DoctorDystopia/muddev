extends Node
## Unit tests for PropMeshBuilder: a ladder, a flight of stairs, or a hatch
## stands on the tile of each object whose scenery is a primitive, and the
## rotation of the object turns it.
##
##     godot --headless --path godot res://tests/test_prop_mesh.tscn
##
## Exits 0 when every case passes, 1 on the first failure.

const _Const := preload("res://autoload/blackout_constants.gd")

## The tile of each case, and its world centre.
const _TILE := Vector2i(6, 9)
const _CENTRE := Vector3(6.0, 0.0, -9.0)

## The tolerance of a position compare, in world units.
const _NEAR := 0.001

var _failures := 0


func _ready() -> void:
	_every_shape_names_a_primitive_of_the_server()
	_a_chunk_with_no_primitive_has_no_surface()
	_each_climb_kind_draws_its_primitive()
	_a_ladder_and_stairs_rise_one_plane_and_a_hatch_stays_flat()
	_a_ladder_stands_at_the_back_of_its_turned_tile()
	_stairs_rise_toward_the_front()
	_a_shape_stands_on_the_ground_of_its_tile()
	_every_face_points_along_its_normal()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: prop_mesh")
	get_tree().quit(0)


# ─── Cases ───────────────────────────────────────────────────────────────────

func _every_shape_names_a_primitive_of_the_server() -> void:
	# A client shape that names nothing is a bug. A server primitive with no
	# shape here draws a post, which is fine.
	for shape: String in PropMeshBuilder.SHAPES:
		_expect(shape in _Const.SCENERY_PRIMITIVES,
			"the shape %s is a primitive of the server" % shape)


func _a_chunk_with_no_primitive_has_no_surface() -> void:
	var chunk := ChunkFile.blank(0, 0)

	chunk.objects.append(_thing(_Const.TILE_RESPAWN_KIND, 0))

	_expect(PropMeshBuilder.build(chunk).get_surface_count() == 0,
		"a landmark draws no primitive")
	_expect(PropMeshBuilder.prop_count(chunk) == 0, "and counts none")


func _each_climb_kind_draws_its_primitive() -> void:
	for kind: String in _Const.OBJECT_KIND_CLIMBS:
		var chunk := ChunkFile.blank(0, 0)

		chunk.objects.append(_thing(kind, 0))

		_expect(PropMeshBuilder.prop_count(chunk) == 1
			and PropMeshBuilder.build(chunk).get_surface_count() == 1,
			"the climb %s draws a primitive" % kind)


func _a_ladder_and_stairs_rise_one_plane_and_a_hatch_stays_flat() -> void:
	var ladder := _bounds(_kind_of(_Const.SCENERY_LADDER), 0)
	var stairs := _bounds(_kind_of(_Const.SCENERY_STAIRS), 0)
	var hatch := _bounds(_kind_of(_Const.SCENERY_HATCH), 0)

	_expect(is_equal_approx(ladder.end.y, PropMeshBuilder.CLIMB_HEIGHT),
		"a ladder reaches the plane above")
	_expect(is_equal_approx(stairs.end.y, PropMeshBuilder.CLIMB_HEIGHT),
		"the stairs reach the plane above")
	_expect(hatch.end.y < 0.25, "a hatch stays near the floor")


func _a_ladder_stands_at_the_back_of_its_turned_tile() -> void:
	# The front of rotation 0 faces north (-z). Each quarter turn is clockwise
	# from above: north, east, south, west.
	var kind := _kind_of(_Const.SCENERY_LADDER)
	var backs := [Vector3.BACK, Vector3.LEFT, Vector3.FORWARD, Vector3.RIGHT]

	for rotation: int in _Const.CHUNK_ROTATION_COUNT:
		var middle := _bounds(kind, rotation).get_center() - _CENTRE
		var toward: Vector3 = backs[rotation]

		_expect(Vector2(middle.x, middle.z).dot(Vector2(toward.x, toward.z))
			> PropMeshBuilder.LADDER_BACK * 0.5,
			"at rotation %d the ladder stands at the back of its tile" % rotation)


func _stairs_rise_toward_the_front() -> void:
	var kind := _kind_of(_Const.SCENERY_STAIRS)

	for rotation: int in _Const.CHUNK_ROTATION_COUNT:
		var top := _highest_vertex(kind, rotation) - _CENTRE
		var front := Basis(Vector3.UP, -rotation * PI * 0.5) * Vector3.FORWARD

		_expect(Vector2(top.x, top.z).dot(Vector2(front.x, front.z)) > 0.25,
			"at rotation %d the top step is at the front" % rotation)


func _a_shape_stands_on_the_ground_of_its_tile() -> void:
	var chunk := ChunkFile.blank(0, 0)
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE

	for corner: Vector2i in [_TILE, _TILE + Vector2i.RIGHT, _TILE + Vector2i.DOWN,
			_TILE + Vector2i.ONE]:
		chunk.heights[corner.y * side + corner.x] = 16

	chunk.objects.append(_thing(_kind_of(_Const.SCENERY_HATCH), 0))

	var low := _mesh_bounds(chunk).position.y
	var ground := 16 * ChunkMeshBuilder.HEIGHT_STEP

	_expect(is_equal_approx(low, ground - PropMeshBuilder.SINK),
		"a hatch sinks into the raised ground of its tile")


func _every_face_points_along_its_normal() -> void:
	var chunk := ChunkFile.blank(0, 0)

	chunk.objects.append(_thing(_kind_of(_Const.SCENERY_STAIRS), 1))

	var arrays := PropMeshBuilder.build(chunk).surface_get_arrays(0)
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var along := 0

	for start: int in range(0, vertices.size(), 3):
		var a := vertices[start]
		var normal := (vertices[start + 2] - a).cross(vertices[start + 1] - a)

		if normal.dot(normals[start]) > 0.0:
			along += 1

	_expect(along == vertices.size() / 3, "every triangle fronts along its normal")


# ─── Private helpers ─────────────────────────────────────────────────────────

## The first object kind whose scenery is `primitive`.
func _kind_of(primitive: String) -> String:
	for kind: String in _Const.OBJECT_KIND_SCENERY:
		if _Const.OBJECT_KIND_SCENERY[kind] == primitive:
			return kind

	_expect(false, "some kind shows the primitive %s" % primitive)

	return ""


func _thing(kind: String, rotation: int) -> Dictionary:
	return {"kind": kind, "x": _TILE.x, "y": _TILE.y, "rotation": rotation,
		"text": ""}


## The box around the primitive of one object of `kind` on flat ground.
func _bounds(kind: String, rotation: int) -> AABB:
	var chunk := ChunkFile.blank(0, 0)

	chunk.objects.append(_thing(kind, rotation))

	return _mesh_bounds(chunk)


func _mesh_bounds(chunk: ChunkFile) -> AABB:
	var mesh := PropMeshBuilder.build(chunk)

	if mesh.get_surface_count() == 0:
		return AABB()

	return mesh.get_aabb()


func _highest_vertex(kind: String, rotation: int) -> Vector3:
	var chunk := ChunkFile.blank(0, 0)

	chunk.objects.append(_thing(kind, rotation))

	var vertices: PackedVector3Array = PropMeshBuilder.build(chunk) \
		.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	var top := vertices[0]

	for vertex: Vector3 in vertices:
		if vertex.y > top.y + _NEAR:
			top = vertex

	return top


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
