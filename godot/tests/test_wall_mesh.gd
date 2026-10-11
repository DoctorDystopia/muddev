extends Node
## Unit tests for WallMeshBuilder: a slab stands on each tile edge with a
## wall flag, inside its own tile, on the ground of that edge. Its top meets
## the floor of the plane above.
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
	_a_wall_under_a_floor_meets_it()
	_a_wall_under_void_keeps_its_height()
	_walls_down_draws_low()
	_each_style_draws_at_its_own_height()
	_a_style_colours_its_walls()
	_an_unknown_style_draws_as_the_default()
	_a_style_with_no_wall_bit_draws_nothing()

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


## DESIGN-0013 section 6.3. The tile above has a floor: each top corner takes
## the corner height of the plane above, and a raised corner gives a slope.
func _a_wall_under_a_floor_meets_it() -> void:
	var size: int = _Const.CHUNK_SIZE
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE
	var chunk := ChunkFile.blank(0, 0)
	var above := TerrainWorld.upper_chunk(chunk, 1)

	chunk.flags[2 * size + 2] = _Const.TILE_FLAG_WALL_NORTH
	above.floor_names.append("concrete")
	above.floors[2 * size + 2] = 1
	above.heights[3 * side + 3] = 40

	var top_west := -INF
	var top_east := -INF

	for vertex: Vector3 in _vertices_of(WallMeshBuilder.build(chunk, above)):
		if vertex.x < 2.0 - 0.25:
			top_west = maxf(top_west, vertex.y)
		elif vertex.x > 2.0 + 0.25:
			top_east = maxf(top_east, vertex.y)

	var rise := TerrainWorld.NEW_PLANE_RISE * ChunkMeshBuilder.HEIGHT_STEP

	_expect(is_equal_approx(top_west, rise), "the west top meets the floor above")
	_expect(is_equal_approx(top_east, 40 * ChunkMeshBuilder.HEIGHT_STEP),
		"the east top meets the raised corner above")


func _a_wall_under_void_keeps_its_height() -> void:
	var chunk := ChunkFile.blank(0, 0)
	var above := TerrainWorld.upper_chunk(chunk, 1)

	chunk.flags[0] = _Const.TILE_FLAG_WALL_SOUTH

	_expect(is_equal_approx(_top(WallMeshBuilder.build(chunk, above)),
		WallMeshBuilder.height_of(_Const.TILE_DEFAULT_WALL_STYLE)),
		"a void tile above leaves the height of the wall style")


func _walls_down_draws_low() -> void:
	var chunk := ChunkFile.blank(0, 0)
	var above := TerrainWorld.upper_chunk(chunk, 1)

	chunk.flags[0] = _Const.TILE_FLAG_WALL_SOUTH
	above.floor_names.append("concrete")
	above.floors.fill(1)

	_expect(is_equal_approx(_top(WallMeshBuilder.build(chunk, null, true)),
		WallMeshBuilder.DOWN_HEIGHT), "walls down draws at the low height")
	_expect(is_equal_approx(_top(WallMeshBuilder.build(chunk, above, true)),
		WallMeshBuilder.DOWN_HEIGHT), "walls down stays low under a floor")


## DESIGN-0013 section 6.4. Each tile has a wall style. The style gives the
## height with nothing above, and the colour of the walls of its tile.
func _each_style_draws_at_its_own_height() -> void:
	for style: String in _Const.TILE_WALL_STYLES:
		var chunk := _styled_chunk(style)
		var steps: int = _Const.TILE_WALL_STYLE_HEIGHTS[style]

		_expect(is_equal_approx(_top(WallMeshBuilder.build(chunk)),
			steps * ChunkMeshBuilder.HEIGHT_STEP),
			"a %s wall stands %d height steps tall" % [style, steps])


func _a_style_colours_its_walls() -> void:
	var colors := {}

	for style: String in _Const.TILE_WALL_STYLES:
		var mesh := WallMeshBuilder.build(_styled_chunk(style))
		var found: PackedColorArray = mesh.surface_get_arrays(0)[Mesh.ARRAY_COLOR]
		var side := WallPalette.side_color(style)
		var near := absf(found[0].r - side.r) <= side.r * FloorPalette.FACET_SHADE + _NEAR

		_expect(near, "a %s wall has the %s colour" % [style, style])
		colors[side.to_html()] = true

	_expect(colors.size() > 1, "two wall styles can differ in colour")


func _an_unknown_style_draws_as_the_default() -> void:
	var chunk := _styled_chunk("no_such_style")
	var default_style: String = _Const.TILE_DEFAULT_WALL_STYLE

	_expect(is_equal_approx(_top(WallMeshBuilder.build(chunk)),
		WallMeshBuilder.height_of(default_style)),
		"an unknown style has the height of the default style")
	_expect(WallPalette.side_color("no_such_style") == WallPalette.side_color(default_style),
		"and its colour")


func _a_style_with_no_wall_bit_draws_nothing() -> void:
	var chunk := _styled_chunk("brick")

	chunk.flags[0] = 0

	_expect(WallMeshBuilder.build(chunk).get_surface_count() == 0,
		"a wall style on a tile with no wall bit draws nothing")


# ─── Private helpers ─────────────────────────────────────────────────────────

func _vertices(chunk: ChunkFile) -> PackedVector3Array:
	return _vertices_of(WallMeshBuilder.build(chunk))


## A flat chunk with one south wall on tile 0, in `style`.
static func _styled_chunk(style: String) -> ChunkFile:
	var chunk := ChunkFile.blank(0, 0)

	chunk.flags[0] = _Const.TILE_FLAG_WALL_SOUTH
	chunk.wall_names.append(style)
	chunk.walls[0] = 1

	return chunk


static func _vertices_of(mesh: ArrayMesh) -> PackedVector3Array:
	if mesh.get_surface_count() == 0:
		return PackedVector3Array()

	return mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]


## The highest point of a mesh.
static func _top(mesh: ArrayMesh) -> float:
	var top := -INF

	for vertex: Vector3 in _vertices_of(mesh):
		top = maxf(top, vertex.y)

	return top


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
