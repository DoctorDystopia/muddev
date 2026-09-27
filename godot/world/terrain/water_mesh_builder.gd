class_name WaterMeshBuilder
extends RefCounted
## The water surface of one chunk: one flat square on each tile with the
## water flag.
##
## DESIGN-0011 debt 8. The water flag is a server fact (a walker cannot stand
## there). The surface is a look. The client ([TerrainView]) and the terrain
## editor ([TerrainWorld]) both draw it through this class, as they both draw
## the ground through [ChunkMeshBuilder].
##
## ## The height of the surface
##
## A water tile draws its surface at the height of its highest corner. Thus,
## to make a pond, the author lowers the bed and paints the water flag. The
## corners on the shore stay at the height of the shore, so the surface
## meets the bank. A flat water tile draws its surface [constant LIFT] over
## the bed, so the two do not flicker.
##
## The coordinates are those of [ChunkMeshBuilder].

const _Const := preload("res://autoload/blackout_constants.gd")

## World units between the highest corner and the water surface.
const LIFT := 0.02

## A salt of the position hash, so the shade of a water tile differs from the
## shade of its bed.
const _SALT_SHADE := 53


## The height of the water surface of local tile (lx, ly), in height steps.
static func surface_steps(chunk: ChunkFile, lx: int, ly: int) -> int:
	var corners := chunk.corner_heights(lx, ly)
	var top := corners[0]

	for height: int in corners:
		top = maxi(top, height)

	return top


## The water mesh of one chunk. A chunk with no water tile gives a mesh with
## no surface.
static func build(chunk: ChunkFile) -> ArrayMesh:
	var size: int = _Const.CHUNK_SIZE
	var vertices := PackedVector3Array()
	var colors := PackedColorArray()

	for ly: int in size:
		for lx: int in size:
			if chunk.flags[ly * size + lx] & _Const.TILE_FLAG_WATER:
				_add_tile(chunk, lx, ly, vertices, colors)

	var mesh := ArrayMesh.new()

	if vertices.is_empty():
		return mesh

	var normals := PackedVector3Array()
	var arrays := []

	normals.resize(vertices.size())
	normals.fill(Vector3.UP)
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_COLOR] = colors
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)

	return mesh


## Add the two triangles of one water tile, wound so that the front faces up.
static func _add_tile(chunk: ChunkFile, lx: int, ly: int,
		vertices: PackedVector3Array, colors: PackedColorArray) -> void:
	var world_x := chunk.cx * _Const.CHUNK_SIZE + lx
	var world_y := chunk.cy * _Const.CHUNK_SIZE + ly
	var y := surface_steps(chunk, lx, ly) * ChunkMeshBuilder.HEIGHT_STEP + LIFT
	var west := (world_x - 0.5) * ChunkMeshBuilder.TILE_SIZE
	var east := west + ChunkMeshBuilder.TILE_SIZE
	var south := -(world_y - 0.5) * ChunkMeshBuilder.TILE_SIZE
	var north := south - ChunkMeshBuilder.TILE_SIZE
	var sw := Vector3(west, y, south)
	var se := Vector3(east, y, south)
	var nw := Vector3(west, y, north)
	var ne := Vector3(east, y, north)
	var amount := ChunkMeshBuilder.hash_unit(world_x, world_y, _SALT_SHADE) * 2.0 - 1.0
	var color := FloorPalette.shade(FloorPalette.WATER_COLOR, amount)

	# Clockwise seen from above is the front in Godot.
	for corner: Vector3 in [sw, nw, ne, sw, ne, se]:
		vertices.append(corner)
		colors.append(color)
