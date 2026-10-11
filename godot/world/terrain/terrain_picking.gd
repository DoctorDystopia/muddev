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

## World units for one step of the wall march. Less than a sixth of
## [constant WallMeshBuilder.THICKNESS], so no step crosses a slab.
const WALL_STEP := 0.02

const _Const := preload("res://autoload/blackout_constants.gd")

## The four wall bits, and the side of the tile that each one stands on, as
## a unit offset in tile space from the tile centre.
const _WALL_SIDES := [
	[_Const.TILE_FLAG_WALL_NORTH, Vector2(0, 1)],
	[_Const.TILE_FLAG_WALL_EAST, Vector2(1, 0)],
	[_Const.TILE_FLAG_WALL_SOUTH, Vector2(0, -1)],
	[_Const.TILE_FLAG_WALL_WEST, Vector2(-1, 0)],
]


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


## The tile whose wall slab the ray meets first, before the ground, or null.
##
## A wall is a look on the edge of a tile, so [method ray_hit] goes through
## it and meets the ground past the wall. Alt and a click of a Build tool
## sample a wall style, and the author clicks the slab, not the ground. The
## march follows the rule of [WallMeshBuilder]: a slab is
## [constant WallMeshBuilder.THICKNESS] deep inside its tile. Its top meets a
## floor of `above`, else it is the height of the wall style. With `down`, every
## slab is [constant WallMeshBuilder.DOWN_HEIGHT] tall.
static func wall_hit(chunks: ChunkSet, origin: Vector3, direction: Vector3,
		above: ChunkSet = null, down: bool = false) -> Variant:
	var ground: Variant = ray_hit(chunks, origin, direction)

	if ground == null:
		return null

	var ray := direction.normalized()
	var reach := origin.distance_to(ground)
	var travelled := 0.0

	while travelled < reach:
		var point := origin + ray * travelled
		var tile: Variant = _slab_at(chunks, point, above, down)

		if tile != null:
			return tile

		travelled += WALL_STEP

	return null


## The tile of the slab that holds the world position `world`, or null.
static func _slab_at(chunks: ChunkSet, world: Vector3, above: ChunkSet,
		down: bool) -> Variant:
	var at := tile_point(world)
	var tile := ChunkSet.tile_at(at)
	var flags := chunks.get_flags(tile)

	if flags & _Const.TILE_FLAGS_WALLS == 0:
		return null

	var ground := _ground_y(chunks, world)

	if is_nan(ground) or world.y < ground - WallMeshBuilder.SINK \
			or world.y > ground + _rise(chunks, above, tile, at, down):
		return null

	var offset := at - Vector2(tile)
	var inner := 0.5 - WallMeshBuilder.THICKNESS / ChunkMeshBuilder.TILE_SIZE

	for side: Array in _WALL_SIDES:
		if flags & side[0] and offset.dot(side[1]) >= inner:
			return tile

	return null


## The height of the slabs of `tile` over the ground at `at`, in world units.
static func _rise(chunks: ChunkSet, above: ChunkSet, tile: Vector2i, at: Vector2,
		down: bool) -> float:
	if down:
		return WallMeshBuilder.DOWN_HEIGHT

	var ground := chunks.height_at(at) * ChunkMeshBuilder.HEIGHT_STEP

	if above != null and above.has_tile(tile) \
			and above.get_floor(tile) != _Const.TILE_VOID_FLOOR:
		return maxf(above.height_at(at) * ChunkMeshBuilder.HEIGHT_STEP - ground,
			WallMeshBuilder.MIN_HEIGHT)

	return WallMeshBuilder.height_of(chunks.get_wall_style(tile))


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
