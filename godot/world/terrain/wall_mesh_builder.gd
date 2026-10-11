class_name WallMeshBuilder
extends RefCounted
## The walls of one chunk: one thin slab on each tile edge with a wall flag.
##
## A wall flag is a server fact: a walker cannot cross that edge, and a shot
## cannot cross it (DESIGN-0011 Phase 6). Until this class, only the terrain
## editor showed a wall, as a flat mark. A player saw no wall and walked into
## an edge that the server refused. The slab is a look. It is a plain
## primitive, and art can replace it later.
##
## The client ([TerrainView]) and the terrain editor ([TerrainWorld]) both draw
## the walls through this class, as they both draw the ground through
## [ChunkMeshBuilder]. Thus, what an author sees is what a player sees.
##
## ## The shape
##
## Each slab stands on the edge and reaches [constant THICKNESS] into its own
## tile. A wall on the north edge of one tile and a wall on the south edge of
## the tile above it thus stand side by side, with no overlap and no flicker.
## Each end of the slab stands on the corner height of that end, so a wall
## follows a slope. The base sinks [constant SINK] into the ground, so no gap
## shows under a wall on a slope.
##
## The coordinates are those of [ChunkMeshBuilder].
##
## ## The wall top (DESIGN-0013 section 6.3)
##
## A wall under a floor rises to meet it. When the same tile of the plane
## above has a floor that is not void, the two top corners of the wall take
## the corner heights of that tile at the edge. Else the top is the height
## of the wall style of the tile over the ground ([method height_of]). A gable
## end wall under a gable roof thus fills itself, with no data. A top under
## the ground of its own wall stays [constant MIN_HEIGHT] over it.
##
## ## The wall style (DESIGN-0013 section 6.4)
##
## Each tile has one wall style: a server fact in the chunk file. The style
## gives the colour of the walls of the tile ([WallPalette]) and their height
## with nothing above them. A style on a tile with no wall bit draws nothing.

const _Const := preload("res://autoload/blackout_constants.gd")

## The height of a wall in the "walls down" view of the editor.
const DOWN_HEIGHT := 0.1

## The lowest top of a wall over its ground, in world units.
const MIN_HEIGHT := 0.05

## How far a wall reaches into its tile, in world units.
const THICKNESS := 0.12

## How far the base of a wall sinks into the ground, in world units.
const SINK := 0.05

## A salt of the position hash, so the shade of a wall differs from the shade
## of the ground under it.
const _SALT_SHADE := 71

## The four walls: flag bit, then the two corners of the edge as (i, j)
## offsets from the south-west corner of the tile. The same edges as the
## editor marks of [TerrainOverlay].
const _WALLS := [
	[_Const.TILE_FLAG_WALL_NORTH, Vector2i(0, 1), Vector2i(1, 1)],
	[_Const.TILE_FLAG_WALL_EAST, Vector2i(1, 0), Vector2i(1, 1)],
	[_Const.TILE_FLAG_WALL_SOUTH, Vector2i(0, 0), Vector2i(1, 0)],
	[_Const.TILE_FLAG_WALL_WEST, Vector2i(0, 0), Vector2i(0, 1)],
]


## The arrays of the mesh under construction. A class, not a Dictionary: a
## packed array read out of a Dictionary is a copy.
class _Surface:
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var colors := PackedColorArray()


## The wall mesh of one chunk. A chunk with no wall gives a mesh with no
## surface. `above` is the chunk of the same coordinates on the plane above,
## or null. With `down`, every wall is [constant DOWN_HEIGHT] tall and meets
## no floor: the "walls down" view of the editor.
static func build(chunk: ChunkFile, above: ChunkFile = null,
		down: bool = false) -> ArrayMesh:
	var size: int = _Const.CHUNK_SIZE
	var out := _Surface.new()

	for ly: int in size:
		for lx: int in size:
			var flag := chunk.flags[ly * size + lx]

			if flag & _Const.TILE_FLAGS_WALLS == 0:
				continue

			var style := chunk.wall_style_name(lx, ly)
			var height := DOWN_HEIGHT if down else height_of(style)
			var ceiling := above if not down and _has_floor(above, ly * size + lx) else null

			for wall: Array in _WALLS:
				if flag & wall[0]:
					_add_wall(chunk, ceiling, Vector2i(lx, ly), wall, height, style, out)

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


## The height of a wall of `style` over the ground, in world units, when no
## floor is above it. A style with no height draws at the height of the
## default style. A figure is about one unit tall
## ([constant EntityPool.ENTITY_SCALE]).
static func height_of(style: String) -> float:
	var heights: Dictionary = _Const.TILE_WALL_STYLE_HEIGHTS
	var steps: int = heights.get(style, heights[_Const.TILE_DEFAULT_WALL_STYLE])

	return steps * ChunkMeshBuilder.HEIGHT_STEP


## How many walls one chunk has. For a test.
static func wall_count(chunk: ChunkFile) -> int:
	var count := 0

	for flag: int in chunk.flags:
		for wall: Array in _WALLS:
			if flag & wall[0]:
				count += 1

	return count


## True when local tile `index` of `above` has a floor that is not void.
static func _has_floor(above: ChunkFile, index: int) -> bool:
	if above == null:
		return false

	return above.floor_names[above.floors[index]] != _Const.TILE_VOID_FLOOR


## Add the five faces of one slab: two sides, two ends, and the top. `wall`
## is a row of [constant _WALLS]. `ceiling` is the chunk above when its tile
## has a floor, else null. `style` is the wall style of the tile.
static func _add_wall(chunk: ChunkFile, ceiling: ChunkFile, tile: Vector2i,
		wall: Array, height: float, style: String, out: _Surface) -> void:
	var start: Vector2i = tile + wall[1]
	var end: Vector2i = tile + wall[2]
	var sink := Vector3.DOWN * SINK
	var outer_a := ChunkMeshBuilder.corner_origin(chunk, start.x, start.y) + sink
	var outer_b := ChunkMeshBuilder.corner_origin(chunk, end.x, end.y) + sink
	var centre := _tile_centre(chunk, tile, outer_a.y)
	var middle := (outer_a + outer_b) * 0.5
	var inward := Vector3(centre.x - middle.x, 0.0, centre.z - middle.z).normalized()
	var inner_a := outer_a + inward * THICKNESS
	var inner_b := outer_b + inward * THICKNESS
	var up_a := Vector3.UP * _rise(ceiling, start, outer_a.y, height)
	var up_b := Vector3.UP * _rise(ceiling, end, outer_b.y, height)
	var core := (outer_a + inner_b) * 0.5 + (up_a + up_b) * 0.25
	var amount := ChunkMeshBuilder.hash_unit(chunk.cx * _Const.CHUNK_SIZE + tile.x,
		chunk.cy * _Const.CHUNK_SIZE + tile.y, _SALT_SHADE) * 2.0 - 1.0
	var side := FloorPalette.shade(WallPalette.side_color(style), amount)
	var top := FloorPalette.shade(WallPalette.top_color(style), amount)

	_add_quad([outer_a, outer_b, outer_b + up_b, outer_a + up_a], core, side, out)
	_add_quad([inner_a, inner_b, inner_b + up_b, inner_a + up_a], core, side, out)
	_add_quad([outer_a, inner_a, inner_a + up_a, outer_a + up_a], core, side, out)
	_add_quad([outer_b, inner_b, inner_b + up_b, outer_b + up_b], core, side, out)
	_add_quad([outer_a + up_a, outer_b + up_b, inner_b + up_b, inner_a + up_a],
		core, top, out)


## How far one end of a wall rises over its sunk base `base_y`, in world
## units. Under a floor, the top meets the corner of the plane above.
static func _rise(ceiling: ChunkFile, corner: Vector2i,
		base_y: float, height: float) -> float:
	var ground_y := base_y + SINK

	if ceiling == null:
		return height + SINK

	var top_y := ChunkMeshBuilder.corner_origin(ceiling, corner.x, corner.y).y

	return maxf(top_y, ground_y + MIN_HEIGHT) - base_y


## The world point of the centre of a local tile, at height `y`.
static func _tile_centre(chunk: ChunkFile, tile: Vector2i, y: float) -> Vector3:
	var world_x := chunk.cx * _Const.CHUNK_SIZE + tile.x
	var world_y := chunk.cy * _Const.CHUNK_SIZE + tile.y

	return Vector3(world_x * ChunkMeshBuilder.TILE_SIZE, y,
		-world_y * ChunkMeshBuilder.TILE_SIZE)


## Add a quad of four corners in ring order as two triangles, each with its
## front away from `core`, the middle of the slab.
static func _add_quad(ring: Array, core: Vector3, color: Color,
		out: _Surface) -> void:
	_add_triangle(ring[0], ring[1], ring[2], core, color, out)
	_add_triangle(ring[0], ring[2], ring[3], core, color, out)


## Add one triangle with its front away from `core`. As in
## [ChunkMeshBuilder], (c - a) x (b - a) points out of the front.
static func _add_triangle(a: Vector3, b: Vector3, c: Vector3, core: Vector3,
		color: Color, out: _Surface) -> void:
	var normal := (c - a).cross(b - a)
	var outward := (a + b + c) / 3.0 - core

	if normal.dot(outward) < 0.0:
		var swap := b

		b = c
		c = swap
		normal = -normal

	normal = normal.normalized()

	for corner: Vector3 in [a, b, c]:
		out.vertices.append(corner)
		out.normals.append(normal)
		out.colors.append(color)
