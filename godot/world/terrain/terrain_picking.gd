class_name TerrainPicking
extends RefCounted
## The point where a ray meets the drawn ground of a [ChunkSet].
##
## The terrain editor finds the brush centre with this. The client (Phase 5)
## replaces the flat-plane pick in `world_view._cell_under` with it
## (DESIGN-0011 section 6.6).
##
## The method is a ray march on [method ChunkSet.height_at], then a bisection.
## It reads the height grid, not the mesh, so it needs no collision shape.
## Jitter moves only unwalkable ground sideways, so a pick on scenery can be
## off by up to [constant ChunkMeshBuilder.JITTER_MAX]. A pick on walkable
## ground is exact.

## World units for one march step. Half a tile does not step over a tile.
const MARCH_STEP := 0.5

## The longest ray, in world units.
const MAX_DISTANCE := 600.0

## Bisection rounds after the march finds a crossing.
const BISECT_ROUNDS := 16


## The world position where the ray first meets the ground, or null.
static func ray_hit(chunks: ChunkSet, origin: Vector3,
		direction: Vector3) -> Variant:
	var ray := direction.normalized()
	var previous := origin
	var travelled := 0.0

	while travelled < MAX_DISTANCE:
		travelled += MARCH_STEP

		var point := origin + ray * travelled
		var below := _is_below_ground(chunks, point)

		if below:
			return _bisect(chunks, previous, point)

		previous = point

	return null


## A world position to a point in tile space.
static func tile_point(world: Vector3) -> Vector2:
	return Vector2(world.x / ChunkMeshBuilder.TILE_SIZE,
		-world.z / ChunkMeshBuilder.TILE_SIZE)


static func _ground_y(chunks: ChunkSet, world: Vector3) -> float:
	var height := chunks.height_at(tile_point(world))

	return height * ChunkMeshBuilder.HEIGHT_STEP


static func _is_below_ground(chunks: ChunkSet, world: Vector3) -> bool:
	var ground := _ground_y(chunks, world)

	return not is_nan(ground) and world.y <= ground


static func _bisect(chunks: ChunkSet, above: Vector3, below: Vector3) -> Vector3:
	var high := above
	var low := below

	for round_index: int in BISECT_ROUNDS:
		var middle := (high + low) * 0.5

		if _is_below_ground(chunks, middle):
			low = middle
		else:
			high = middle

	return low
