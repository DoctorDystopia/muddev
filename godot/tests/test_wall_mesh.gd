extends Node
## Unit tests for WallMeshBuilder: a slab stands on each tile edge with a
## wall flag, inside its own tile, on the ground of that edge.
##
##     godot --headless --path godot res://tests/test_wall_mesh.tscn
##
## Exits 0 when every case passes, 1 on the first failure.

const _Const := preload("res://autoload/blackout_constants.gd")

## The faces of one slab: two sides, two ends, and the top. Two triangles each.
const _TRIANGLES_PER_WALL := 5 * 2

## The tolerance of a position compare, in world units.
const _NEAR := 0.001

var _failures := 0


func _ready() -> void:
	_a_chunk_with_no_wall_has_no_surface()
	_each_wall_bit_gives_one_slab()
	_a_slab_stands_inside_its_own_tile()
	_a_slab_stands_on_the_ground_of_its_edge()
	_every_face_points_out_of_its_slab()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: wall_mesh")
	get_tree().quit(0)


# ─── Cases ───────────────────────────────────────────────────────────────────

func _a_chunk_with_no_wall_has_no_surface() -> void:
	var chunk := ChunkFile.blank(0, 0)

	chunk.flags[3] = _Const.TILE_FLAG_BLOCKED | _Const.TILE_FLAG_WATER

	_expect(WallMeshBuilder.build(chunk).get_surface_count() == 0,
		"blocked and water flags draw no wall")


func _each_wall_bit_gives_one_slab() -> void:
	var chunk := ChunkFile.blank(0, 0)

	chunk.flags[0] = _Const.TILE_FLAG_WALL_NORTH | _Const.TILE_FLAG_WALL_WEST
	chunk.flags[70] = _Const.TILE_FLAG_WALL_EAST
	chunk.flags[140] = _Const.TILE_FLAG_WALL_SOUTH | _Const.TILE_FLAG_BLOCKED

	var vertices := _vertices(chunk)

	_expect(WallMeshBuilder.wall_count(chunk) == 4, "four wall bits count four walls")
	_expect(vertices.size() == 4 * _TRIANGLES_PER_WALL * 3,
		"and give four slabs of five faces")


func _a_slab_stands_inside_its_own_tile() -> void:
	# Tile (5, 5) has a north wall. The tile above has a south wall on the
	# same edge. The two slabs must not overlap.
	var chunk := ChunkFile.blank(0, 0)
	var size: int = _Const.CHUNK_SIZE

	chunk.flags[5 * size + 5] = _Const.TILE_FLAG_WALL_NORTH

	var edge_z := -5.5 * ChunkMeshBuilder.TILE_SIZE
	var outside := 0

	for vertex: Vector3 in _vertices(chunk):
		var across := vertex.x >= 4.5 - _NEAR and vertex.x <= 5.5 + _NEAR
		var deep := vertex.z >= edge_z - _NEAR \
			and vertex.z <= edge_z + WallMeshBuilder.THICKNESS + _NEAR

		if not (across and deep):
			outside += 1

	_expect(outside == 0, "a north wall stays on its edge, inside its own tile")


func _a_slab_stands_on_the_ground_of_its_edge() -> void:
	# Raise the north-east corner of tile (2, 2). The east end of its north
	# wall stands higher than the west end.
	var chunk := ChunkFile.blank(0, 0)
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE

	chunk.heights[3 * side + 3] = 8
	chunk.flags[2 * _Const.CHUNK_SIZE + 2] = _Const.TILE_FLAG_WALL_NORTH

	var low_west := INF
	var low_east := INF

	for vertex: Vector3 in _vertices(chunk):
		if vertex.x < 2.0 - 0.25:
			low_west = minf(low_west, vertex.y)
		elif vertex.x > 2.0 + 0.25:
			low_east = minf(low_east, vertex.y)

	var sink := -WallMeshBuilder.SINK
	var raised := 8 * ChunkMeshBuilder.HEIGHT_STEP - WallMeshBuilder.SINK

	_expect(is_equal_approx(low_west, sink), "the west end sinks into flat ground")
	_expect(is_equal_approx(low_east, raised), "the east end follows the raised corner")


func _every_face_points_out_of_its_slab() -> void:
	var chunk := ChunkFile.blank(0, 0)
	var size: int = _Const.CHUNK_SIZE

	chunk.flags[7 * size + 7] = _Const.TILE_FLAG_WALL_EAST

	var vertices := _vertices(chunk)
	var core := Vector3.ZERO

	for vertex: Vector3 in vertices:
		core += vertex

	core /= vertices.size()

	var outward := 0

	for start: int in range(0, vertices.size(), 3):
		var a := vertices[start]
		var normal := (vertices[start + 2] - a).cross(vertices[start + 1] - a)
		var middle := (a + vertices[start + 1] + vertices[start + 2]) / 3.0

		if normal.dot(middle - core) > 0.0:
			outward += 1

	_expect(outward == vertices.size() / 3, "every face of a slab points out")


# ─── Private helpers ─────────────────────────────────────────────────────────

func _vertices(chunk: ChunkFile) -> PackedVector3Array:
	var mesh := WallMeshBuilder.build(chunk)

	if mesh.get_surface_count() == 0:
		return PackedVector3Array()

	return mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
