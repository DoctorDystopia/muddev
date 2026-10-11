extends Node
## Tests for [ChunkMeshBuilder] and [FloorPalette].
##
##     godot --headless --path godot res://tests/test_chunk_mesh.tscn
##
## Needs nothing running. It proves the rules that the editor and the client
## depend on:
##
## 1. The drawn ground and [method ChunkMeshBuilder.surface_height] agree, on
##    every vertex and on the centre of every triangle.
## 2. Every face points up.
## 3. Only a corner inside a block of unwalkable tiles moves.
## 4. Two neighbour chunks draw the same seam.
## 5. The mesh is the same on every build.
##
## Random heights come from a seeded [RandomNumberGenerator], never the global
## RNG.

const _Const := preload("res://autoload/blackout_constants.gd")

const _SEED := 20260924
const _HEIGHT_SPREAD := 12
const _EPSILON := 0.0001

var _failures := 0


func _ready() -> void:
	_a_flat_chunk_is_flat()
	_the_drawn_ground_is_the_surface_height()
	_every_face_points_up()
	_only_a_corner_inside_an_unwalkable_block_moves()
	_neighbour_chunks_draw_the_same_seam()
	_the_mesh_is_the_same_on_every_build()
	_the_diagonal_keeps_one_raised_corner_in_one_triangle()
	_the_palette_gives_a_stable_colour_to_an_unknown_floor()
	_a_face_steeper_than_the_walk_limit_is_a_cliff()
	_one_raised_corner_makes_one_cliff_face_in_each_tile()
	_a_roof_never_takes_the_cliff_colour()
	_a_void_tile_has_no_triangle()
	_a_chunk_of_void_builds_an_empty_mesh()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: chunk_mesh")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


## A chunk with seeded random heights. Every tile is walkable.
func _hilly_chunk(chunk_x: int, chunk_y: int) -> ChunkFile:
	var chunk := ChunkFile.blank(chunk_x, chunk_y)
	var rng := RandomNumberGenerator.new()

	rng.seed = _SEED

	for index: int in chunk.heights.size():
		chunk.heights[index] = rng.randi_range(0, _HEIGHT_SPREAD)

	return chunk


## The local corner coordinates (u, v) of a world position in `chunk`.
func _local_uv(chunk: ChunkFile, position: Vector3) -> Vector2:
	var size: int = _Const.CHUNK_SIZE
	var u := position.x / ChunkMeshBuilder.TILE_SIZE + 0.5 - chunk.cx * size
	var v := -position.z / ChunkMeshBuilder.TILE_SIZE + 0.5 - chunk.cy * size

	return Vector2(u, v)


func _a_flat_chunk_is_flat() -> void:
	var chunk := ChunkFile.blank(0, 0)
	var arrays := ChunkMeshBuilder.build_arrays(chunk)
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var tiles: int = _Const.CHUNK_SIZE * _Const.CHUNK_SIZE
	var highest := 0.0

	for vertex: Vector3 in vertices:
		highest = maxf(highest, absf(vertex.y))

	_expect(vertices.size() == tiles * 6, "two triangles for each tile")
	_expect(highest == 0.0, "a flat chunk has every vertex at height 0")


func _the_drawn_ground_is_the_surface_height() -> void:
	var chunk := _hilly_chunk(-1, 2)
	var arrays := ChunkMeshBuilder.build_arrays(chunk)
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var worst := 0.0

	for first: int in range(0, vertices.size(), 3):
		var centre := (vertices[first] + vertices[first + 1]
			+ vertices[first + 2]) / 3.0

		for point: Vector3 in [vertices[first], centre]:
			var uv := _local_uv(chunk, point)
			var height := ChunkMeshBuilder.surface_height(chunk, uv.x, uv.y)

			worst = maxf(worst, absf(height * ChunkMeshBuilder.HEIGHT_STEP - point.y))

	_expect(worst < _EPSILON,
		"every vertex and triangle centre is on the surface, worst %f" % worst)


func _every_face_points_up() -> void:
	var chunk := _hilly_chunk(0, 0)
	var arrays := ChunkMeshBuilder.build_arrays(chunk)
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var down := 0

	for normal: Vector3 in normals:
		if normal.y <= 0.0:
			down += 1

	_expect(down == 0, "no face points down, found %d" % down)


func _moved_corners(chunk: ChunkFile) -> int:
	var positions := ChunkMeshBuilder.corner_positions(chunk)
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE
	var moved := 0

	for j: int in side:
		for i: int in side:
			var origin := ChunkMeshBuilder.corner_origin(chunk, i, j)

			if not positions[j * side + i].is_equal_approx(origin):
				moved += 1

	return moved


func _only_a_corner_inside_an_unwalkable_block_moves() -> void:
	var size: int = _Const.CHUNK_SIZE
	var block := ChunkFile.blank(0, 0)

	for ly: int in range(10, 13):
		for lx: int in range(10, 13):
			block.flags[ly * size + lx] = _Const.TILE_FLAG_BLOCKED

	_expect(_moved_corners(block) == 4,
		"a 3 x 3 block moves its 4 inner corners, moved %d" % _moved_corners(block))

	var sealed := ChunkFile.blank(0, 0)

	sealed.flags.fill(_Const.TILE_FLAG_WATER)

	var inner := (size - 1) * (size - 1)

	_expect(_moved_corners(sealed) == inner,
		"an all-water chunk moves every corner but the edge ones")


func _neighbour_chunks_draw_the_same_seam() -> void:
	var size: int = _Const.CHUNK_SIZE
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE
	var west := _hilly_chunk(0, 0)
	var east := _hilly_chunk(1, 0)

	west.flags.fill(_Const.TILE_FLAG_BLOCKED)
	east.flags.fill(_Const.TILE_FLAG_BLOCKED)

	for j: int in side:
		east.heights[j * side] = west.heights[j * side + size]

	var west_corners := ChunkMeshBuilder.corner_positions(west)
	var east_corners := ChunkMeshBuilder.corner_positions(east)
	var open := 0

	for j: int in side:
		if not west_corners[j * side + size].is_equal_approx(east_corners[j * side]):
			open += 1

	_expect(open == 0, "the shared edge has no gap, %d corners differ" % open)


func _the_mesh_is_the_same_on_every_build() -> void:
	var chunk := _hilly_chunk(3, -4)

	chunk.flags.fill(_Const.TILE_FLAG_BLOCKED)

	var first := ChunkMeshBuilder.build_arrays(chunk)
	var second := ChunkMeshBuilder.build_arrays(chunk)

	_expect(first[Mesh.ARRAY_VERTEX] == second[Mesh.ARRAY_VERTEX],
		"two builds give the same vertices")
	_expect(first[Mesh.ARRAY_COLOR] == second[Mesh.ARRAY_COLOR],
		"two builds give the same colours")


func _the_diagonal_keeps_one_raised_corner_in_one_triangle() -> void:
	var raised_sw := PackedInt32Array([4, 0, 0, 0])
	var raised_se := PackedInt32Array([0, 4, 0, 0])

	_expect(not ChunkMeshBuilder.splits_sw_ne(raised_sw),
		"a raised southwest corner splits southeast to northwest")
	_expect(ChunkMeshBuilder.splits_sw_ne(raised_se),
		"a raised southeast corner splits southwest to northeast")
	_expect(ChunkMeshBuilder.splits_sw_ne(PackedInt32Array([0, 0, 0, 0])),
		"a flat tile splits southwest to northeast")


func _the_palette_gives_a_stable_colour_to_an_unknown_floor() -> void:
	var first := FloorPalette.color_of("no_such_floor")
	var second := FloorPalette.color_of("no_such_floor")

	_expect(first == second, "an unknown floor gets the same colour each time")

	for floor_name: String in FloorPalette.COLORS:
		_expect(_Const.TILE_FLOOR_TYPES.has(floor_name),
			"the palette key %s is a floor type" % floor_name)


## The server refuses a step steeper than TILE_WALK_LIMIT. The client draws
## the same slope as a cliff face. Read from the constant, so a retune moves
## this test with it.
func _a_face_steeper_than_the_walk_limit_is_a_cliff() -> void:
	var limit: int = _Const.TILE_WALK_LIMIT
	var triangle := PackedInt32Array([0, 1, 3])
	var at_limit := PackedInt32Array([0, 0, 0, limit])
	var above := PackedInt32Array([0, 0, 0, limit + 1])

	_expect(not ChunkMeshBuilder.is_cliff_face(at_limit, triangle),
		"a face that rises by the walk limit is ground")
	_expect(ChunkMeshBuilder.is_cliff_face(above, triangle),
		"a face that rises by more than the walk limit is a cliff")


## A corner raised above the walk limit sits in one triangle of each of its
## four tiles, by the diagonal rule. Those four faces, and no others, take
## the cliff colour.
func _one_raised_corner_makes_one_cliff_face_in_each_tile() -> void:
	var chunk := ChunkFile.blank(0, 0)
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE
	var corner := Vector2i(5, 5)

	chunk.heights[corner.y * side + corner.x] = _Const.TILE_WALK_LIMIT + 1

	var arrays := ChunkMeshBuilder.build_arrays(chunk)
	var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
	var cliffs := 0

	for first: int in range(0, colors.size(), 3):
		if _near_cliff_color(colors[first]):
			cliffs += 1

	_expect(cliffs == 4, "one raised corner makes 4 cliff faces, found %d" % cliffs)


## DESIGN-0013 section 6.2. A roof is steeper than a walk on purpose. The
## same raised corner on a roof floor type draws in the roof colour.
func _a_roof_never_takes_the_cliff_colour() -> void:
	var chunk := ChunkFile.blank(0, 0, 1)
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE
	var corner := Vector2i(5, 5)

	chunk.floor_names = PackedStringArray([_Const.TILE_ROOF_FLOOR_TYPES[0]])
	chunk.heights[corner.y * side + corner.x] = _Const.TILE_WALK_LIMIT * 4

	var colors: PackedColorArray = ChunkMeshBuilder.build_arrays(chunk)[Mesh.ARRAY_COLOR]
	var cliffs := 0

	for first: int in range(0, colors.size(), 3):
		if _near_cliff_color(colors[first]):
			cliffs += 1

	_expect(cliffs == 0, "a steep roof draws no cliff face, found %d" % cliffs)


## True when `color` is the cliff colour with a facet shade on it.
func _a_void_tile_has_no_triangle() -> void:
	# Phase 7b. A void tile is a gap in a plane: the plane below shows.
	var chunk := ChunkFile.blank(0, 0, 1)
	var full: PackedVector3Array = ChunkMeshBuilder.build_arrays(chunk)[Mesh.ARRAY_VERTEX]

	chunk.floor_names.append(_Const.TILE_VOID_FLOOR)
	chunk.floors[0] = 1
	chunk.floors[5] = 1

	var gapped: PackedVector3Array = ChunkMeshBuilder.build_arrays(chunk)[Mesh.ARRAY_VERTEX]

	# Two triangles of three vertices for each tile.
	_expect(full.size() - gapped.size() == 2 * 2 * 3,
		"two void tiles drop four triangles")


func _a_chunk_of_void_builds_an_empty_mesh() -> void:
	var chunk := ChunkFile.blank(0, 0, 1)

	chunk.floor_names = PackedStringArray([_Const.TILE_VOID_FLOOR])

	var mesh := ChunkMeshBuilder.build(chunk)

	_expect(mesh.get_surface_count() == 0, "an all-void chunk has no surface")


func _near_cliff_color(color: Color) -> bool:
	var cliff := FloorPalette.CLIFF_COLOR
	var tolerance := FloorPalette.FACET_SHADE + _EPSILON

	return absf(color.r - cliff.r) <= tolerance \
		and absf(color.g - cliff.g) <= tolerance \
		and absf(color.b - cliff.b) <= tolerance
