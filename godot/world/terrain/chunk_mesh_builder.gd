class_name ChunkMeshBuilder
extends RefCounted
## One mesh for one chunk file, and the height of the ground that it draws.
##
## The terrain editor (Phase 3) and the game client (Phase 5) both draw a
## chunk through this class. DESIGN-0011 section 6.3: what the author sees is
## what the player sees. Section 6.8 gives the low-poly rules that it follows:
##
## 1. Flat shading. Each triangle has its own three vertices and one normal.
## 2. The colour of a triangle comes from the floor type of its tile, through
##    [FloorPalette]. A position hash makes each face a little lighter or
##    darker.
## 3. Jitter comes from a hash of the world position, never from the global
##    RNG. Thus every client and the editor draw the same facets.
## 4. No jitter on a walkable tile. A corner moves only when all four tiles
##    around it are unwalkable, and a corner on the chunk edge never moves.
##    The edge rule keeps the seam between two chunks closed.
##
## ## The ground surface
##
## Each tile is two triangles. [method splits_sw_ne] picks the diagonal, and
## [method surface_height] reads the height on the same two triangles. Thus an
## entity at [method surface_height] stands exactly on the drawn ground. Jitter
## moves only unwalkable ground, where no entity stands.
##
## ## Coordinates
##
## A tile is one world unit. Tile (x, y) has its centre at (x, 0, -y), as in
## `world_view.gd`: grid Y grows to the north, and north is -Z. Corner (i, j)
## of a chunk is the southwest corner of its local tile (i, j).

const _Const := preload("res://autoload/blackout_constants.gd")

## World units for one height step. OSRS: a tile is 128 units, and one height
## step is 8 of them. Nick chose the same ratio, 09/24/2026.
const HEIGHT_STEP := 1.0 / 16.0

## World units along one side of a tile.
const TILE_SIZE := 1.0

## The largest sideways move of a scenery corner, in tiles.
const JITTER_MAX := 0.2

## Salts, so each use of the position hash reads different bits.
const _SALT_JITTER_X := 11
const _SALT_JITTER_Z := 23
const _SALT_SHADE := 37

## The bits of the position hash that [method hash_unit] keeps.
const _HASH_MASK := 0x7fffffff
const _HASH_PRIME_X := 73856093
const _HASH_PRIME_Y := 19349663
const _HASH_PRIME_SALT := 83492791
const _HASH_MIX := 0x45d9f3b
const _HASH_SHIFT := 16


## The three arrays that a mesh grows in. A class, not an Array of packed
## arrays: a packed array read out of an Array can be a copy, and then an
## append changes the copy only.
class _Surface:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()


# ─── The ground surface ─────────────────────────────────────────────────────

## True when a tile with these corners splits on its southwest to northeast
## diagonal. `corners` is (southwest, southeast, northwest, northeast), as
## [method ChunkFile.corner_heights] gives it.
##
## The rule: split on the diagonal whose two ends differ less. Then one
## raised corner makes one sloped triangle, and the other triangle stays flat.
## A tie splits southwest to northeast.
static func splits_sw_ne(corners: PackedInt32Array) -> bool:
	var rise_sw_ne := absi(corners[0] - corners[3])
	var rise_se_nw := absi(corners[1] - corners[2])

	return rise_sw_ne <= rise_se_nw


## The height of the drawn ground, in height steps, at a point of a chunk.
##
## `u` and `v` are local corner coordinates: corner (i, j) is at u = i, v = j,
## and tile (lx, ly) covers lx..lx+1 and ly..ly+1. A point outside the chunk
## is clamped to its edge.
static func surface_height(chunk: ChunkFile, u: float, v: float) -> float:
	var size: int = _Const.CHUNK_SIZE
	var clamped_u := clampf(u, 0.0, size)
	var clamped_v := clampf(v, 0.0, size)
	var lx := mini(int(floorf(clamped_u)), size - 1)
	var ly := mini(int(floorf(clamped_v)), size - 1)
	var corners := chunk.corner_heights(lx, ly)
	var fu := clamped_u - lx
	var fv := clamped_v - ly

	return _triangle_height(corners, fu, fv)


## The height inside one tile, on the triangle that holds (fu, fv).
static func _triangle_height(corners: PackedInt32Array, fu: float,
		fv: float) -> float:
	var sw := float(corners[0])
	var se := float(corners[1])
	var nw := float(corners[2])
	var ne := float(corners[3])

	if splits_sw_ne(corners):
		if fu >= fv:
			return sw + (se - sw) * fu + (ne - se) * fv

		return sw + (nw - sw) * fv + (ne - nw) * fu

	if fu + fv <= 1.0:
		return sw + (se - sw) * fu + (nw - sw) * fv

	return ne + (nw - ne) * (1.0 - fu) + (se - ne) * (1.0 - fv)


# ─── The position hash ──────────────────────────────────────────────────────

## A number in 0..1 from a world tile position and a salt. The same inputs
## give the same number on every machine. It reads no RNG.
static func hash_unit(world_x: int, world_y: int, salt: int) -> float:
	var mixed := (world_x * _HASH_PRIME_X) ^ (world_y * _HASH_PRIME_Y) \
		^ (salt * _HASH_PRIME_SALT)

	mixed = mixed & _HASH_MASK
	mixed = ((mixed >> _HASH_SHIFT) ^ mixed) * _HASH_MIX & _HASH_MASK
	mixed = ((mixed >> _HASH_SHIFT) ^ mixed) * _HASH_MIX & _HASH_MASK
	mixed = (mixed >> _HASH_SHIFT) ^ mixed

	return float(mixed & _HASH_MASK) / float(_HASH_MASK)


# ─── The corners ────────────────────────────────────────────────────────────

## The world position of corner (i, j), with no jitter.
static func corner_origin(chunk: ChunkFile, i: int, j: int) -> Vector3:
	var size: int = _Const.CHUNK_SIZE
	var world_x := chunk.cx * size + i
	var world_y := chunk.cy * size + j
	var height := chunk.heights[j * _Const.CHUNK_CORNERS_PER_SIDE + i]

	return Vector3((world_x - 0.5) * TILE_SIZE, height * HEIGHT_STEP,
		-(world_y - 0.5) * TILE_SIZE)


## True when corner (i, j) may move: it is inside the chunk, and all four
## tiles around it are unwalkable.
static func corner_jitters(chunk: ChunkFile, i: int, j: int) -> bool:
	var size: int = _Const.CHUNK_SIZE

	if i <= 0 or j <= 0 or i >= size or j >= size:
		return false

	for tile: Vector2i in [Vector2i(i - 1, j - 1), Vector2i(i, j - 1),
			Vector2i(i - 1, j), Vector2i(i, j)]:
		var flag := chunk.flags[tile.y * size + tile.x]

		if not (flag & _Const.TILE_FLAGS_UNWALKABLE):
			return false

	return true


## Every corner of the chunk as a world position, jitter included. Row 0
## first, as the height grid.
static func corner_positions(chunk: ChunkFile) -> PackedVector3Array:
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE
	var size: int = _Const.CHUNK_SIZE
	var positions := PackedVector3Array()

	positions.resize(side * side)

	for j: int in side:
		for i: int in side:
			var position := corner_origin(chunk, i, j)

			if corner_jitters(chunk, i, j):
				var world_x := chunk.cx * size + i
				var world_y := chunk.cy * size + j
				var shift_x := hash_unit(world_x, world_y, _SALT_JITTER_X) * 2.0 - 1.0
				var shift_z := hash_unit(world_x, world_y, _SALT_JITTER_Z) * 2.0 - 1.0

				position += Vector3(shift_x, 0.0, shift_z) * JITTER_MAX * TILE_SIZE

			positions[j * side + i] = position

	return positions


# ─── The mesh ───────────────────────────────────────────────────────────────

## The mesh of one chunk: two flat-shaded triangles for each tile, coloured
## by floor type. The chunk must have no [member ChunkFile.error].
static func build(chunk: ChunkFile) -> ArrayMesh:
	var arrays := build_arrays(chunk)
	var mesh := ArrayMesh.new()

	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)

	return mesh


## The surface arrays of [method build], for a caller that needs the raw data,
## for example a test or a collision shape.
static func build_arrays(chunk: ChunkFile) -> Array:
	var size: int = _Const.CHUNK_SIZE
	var positions := corner_positions(chunk)
	var floor_colors := _floor_colors(chunk)
	var out := _Surface.new()

	for ly: int in size:
		for lx: int in size:
			var base: Color = floor_colors[chunk.floors[ly * size + lx]]

			_add_tile(chunk, positions, lx, ly, base, out)

	var arrays := []

	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = out.vertices
	arrays[Mesh.ARRAY_NORMAL] = out.normals
	arrays[Mesh.ARRAY_COLOR] = out.colors

	return arrays


static func _floor_colors(chunk: ChunkFile) -> Array[Color]:
	var colors: Array[Color] = []

	for floor_name: String in chunk.floor_names:
		colors.append(FloorPalette.color_of(floor_name))

	return colors


## Add the two triangles of local tile (lx, ly) to `out`.
static func _add_tile(chunk: ChunkFile, positions: PackedVector3Array, lx: int,
		ly: int, base: Color, out: _Surface) -> void:
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE
	var sw := positions[ly * side + lx]
	var se := positions[ly * side + lx + 1]
	var nw := positions[(ly + 1) * side + lx]
	var ne := positions[(ly + 1) * side + lx + 1]
	var world_x := chunk.cx * _Const.CHUNK_SIZE + lx
	var world_y := chunk.cy * _Const.CHUNK_SIZE + ly
	var first_shade := hash_unit(world_x, world_y, _SALT_SHADE) * 2.0 - 1.0
	var second_shade := hash_unit(world_y, world_x, _SALT_SHADE) * 2.0 - 1.0
	var first_color := FloorPalette.shade(base, first_shade)
	var second_color := FloorPalette.shade(base, second_shade)

	if splits_sw_ne(chunk.corner_heights(lx, ly)):
		_add_triangle(sw, se, ne, first_color, out)
		_add_triangle(sw, ne, nw, second_color, out)
	else:
		_add_triangle(sw, se, nw, first_color, out)
		_add_triangle(se, ne, nw, second_color, out)


## Add one triangle, wound so that its front faces up. Godot draws a
## clockwise triangle as its front, and then (c - a) x (b - a) points out of
## the front.
static func _add_triangle(a: Vector3, b: Vector3, c: Vector3, color: Color,
		out: _Surface) -> void:
	var normal := (c - a).cross(b - a)

	if normal.y < 0.0:
		var swap := b

		b = c
		c = swap
		normal = -normal

	normal = normal.normalized()

	for corner: Vector3 in [a, b, c]:
		out.vertices.append(corner)
		out.normals.append(normal)
		out.colors.append(color)
