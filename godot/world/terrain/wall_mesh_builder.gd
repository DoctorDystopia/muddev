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

const _Const := preload("res://autoload/blackout_constants.gd")

## The height of a wall over the ground, in world units. A figure is about
## one unit tall ([constant EntityPool.ENTITY_SCALE]).
const HEIGHT := 0.75

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
## surface.
static func build(chunk: ChunkFile) -> ArrayMesh:
	var size: int = _Const.CHUNK_SIZE
	var out := _Surface.new()

	for ly: int in size:
		for lx: int in size:
			var flag := chunk.flags[ly * size + lx]

			for wall: Array in _WALLS:
				if flag & wall[0]:
					_add_wall(chunk, lx, ly, wall[1], wall[2], out)

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


## How many walls one chunk has. For a test.
static func wall_count(chunk: ChunkFile) -> int:
	var count := 0

	for flag: int in chunk.flags:
		for wall: Array in _WALLS:
			if flag & wall[0]:
				count += 1

	return count


## Add the five faces of one slab: two sides, two ends, and the top.
static func _add_wall(chunk: ChunkFile, lx: int, ly: int, start: Vector2i,
		end: Vector2i, out: _Surface) -> void:
	var tile := Vector2i(lx, ly)
	var sink := Vector3.DOWN * SINK
	var outer_a := ChunkMeshBuilder.corner_origin(chunk, lx + start.x,
		ly + start.y) + sink
	var outer_b := ChunkMeshBuilder.corner_origin(chunk, lx + end.x,
		ly + end.y) + sink
	var centre := _tile_centre(chunk, tile, outer_a.y)
	var middle := (outer_a + outer_b) * 0.5
	var inward := Vector3(centre.x - middle.x, 0.0, centre.z - middle.z).normalized()
	var inner_a := outer_a + inward * THICKNESS
	var inner_b := outer_b + inward * THICKNESS
	var up := Vector3.UP * (HEIGHT + SINK)
	var core := (outer_a + inner_b) * 0.5 + up * 0.5
	var amount := ChunkMeshBuilder.hash_unit(chunk.cx * _Const.CHUNK_SIZE + lx,
		chunk.cy * _Const.CHUNK_SIZE + ly, _SALT_SHADE) * 2.0 - 1.0
	var side := FloorPalette.shade(FloorPalette.WALL_COLOR, amount)
	var top := FloorPalette.shade(FloorPalette.WALL_TOP_COLOR, amount)

	_add_quad([outer_a, outer_b, outer_b + up, outer_a + up], core, side, out)
	_add_quad([inner_a, inner_b, inner_b + up, inner_a + up], core, side, out)
	_add_quad([outer_a, inner_a, inner_a + up, outer_a + up], core, side, out)
	_add_quad([outer_b, inner_b, inner_b + up, outer_b + up], core, side, out)
	_add_quad([outer_a + up, outer_b + up, inner_b + up, inner_a + up], core,
		top, out)


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
