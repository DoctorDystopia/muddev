@tool
class_name StepGrid
extends RefCounted
## The walk facts of one plane of a world, in flat arrays: the flags and the
## tile height of each tile. The `unreachable` rule of [TerrainChecks] walks
## a whole world, and a [ChunkSet] read costs a Dictionary lookup for each
## tile. These arrays cost an index.
##
## ## The step rule
##
## [method can_step] is the GDScript twin of `TileGrid.check_step` in
## `blackout/systems/core/tilegrid/grid.py`, with the walk limit. A step
## enters a loaded tile that is not Blocked or water. A cardinal step crosses
## no wall on either side of its edge. A diagonal step needs both L-shaped
## legs open, so it cuts no corner. The tile heights (the lowest corner) of
## the two ends differ by no more than [code]TILE_WALK_LIMIT[/code].
##
## The pockets of the check fixture test this rule in both languages, against
## one `expected.json`. A change to the Python rule changes this class too.
##
## The grid covers the rectangle of the chunks of its plane. A tile of that
## rectangle with no chunk is not loaded, and no step enters it.

const _Const := preload("res://autoload/blackout_constants.gd")

## The eight steps of a walker, as (dx, dy).
const STEPS: Array[Vector2i] = [Vector2i(0, 1), Vector2i(1, 1), Vector2i(1, 0),
	Vector2i(1, -1), Vector2i(0, -1), Vector2i(-1, -1), Vector2i(-1, 0),
	Vector2i(-1, 1)]

## The wall bit that stops a cardinal step out of a tile, by offset.
const _WALL_LEAVING := {
	Vector2i(0, 1): _Const.TILE_FLAG_WALL_NORTH,
	Vector2i(1, 0): _Const.TILE_FLAG_WALL_EAST,
	Vector2i(0, -1): _Const.TILE_FLAG_WALL_SOUTH,
	Vector2i(-1, 0): _Const.TILE_FLAG_WALL_WEST,
}

## The wall bit that stops a cardinal step into a tile, by offset.
const _WALL_ENTERING := {
	Vector2i(0, 1): _Const.TILE_FLAG_WALL_SOUTH,
	Vector2i(1, 0): _Const.TILE_FLAG_WALL_WEST,
	Vector2i(0, -1): _Const.TILE_FLAG_WALL_NORTH,
	Vector2i(-1, 0): _Const.TILE_FLAG_WALL_EAST,
}

var plane := 0

## The world tile of index 0: the south-west tile of the rectangle.
var low := Vector2i.ZERO
var width := 0
var height := 0

var _flags := PackedInt32Array()
var _loaded := PackedByteArray()
var _heights := PackedInt32Array()


## The grid of every chunk of `chunk_files` on `on_plane`.
static func of(chunk_files: Array[ChunkFile], on_plane: int) -> StepGrid:
	var grid := StepGrid.new()
	var mine: Array[ChunkFile] = []

	grid.plane = on_plane

	for chunk: ChunkFile in chunk_files:
		if chunk.plane == on_plane:
			mine.append(chunk)

	if mine.is_empty():
		return grid

	grid._size_to(mine)

	for chunk: ChunkFile in mine:
		grid._fill(chunk)

	return grid


func _size_to(mine: Array[ChunkFile]) -> void:
	var size: int = _Const.CHUNK_SIZE
	var low_chunk := Vector2i(mine[0].cx, mine[0].cy)
	var high_chunk := low_chunk

	for chunk: ChunkFile in mine:
		low_chunk = low_chunk.min(Vector2i(chunk.cx, chunk.cy))
		high_chunk = high_chunk.max(Vector2i(chunk.cx, chunk.cy))

	low = low_chunk * size
	width = (high_chunk.x - low_chunk.x + 1) * size
	height = (high_chunk.y - low_chunk.y + 1) * size
	_flags.resize(width * height)
	_flags.fill(_Const.TILE_FLAG_BLOCKED)
	_loaded.resize(width * height)
	_heights.resize(width * height)


## Copy the flags and the tile heights of one chunk into the arrays.
func _fill(chunk: ChunkFile) -> void:
	var size: int = _Const.CHUNK_SIZE
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE
	var origin := Vector2i(chunk.cx, chunk.cy) * size - low

	for ly: int in size:
		var row := (origin.y + ly) * width + origin.x

		for lx: int in size:
			var south := ly * side + lx
			var north := south + side

			_flags[row + lx] = chunk.flags[ly * size + lx]
			_loaded[row + lx] = 1
			_heights[row + lx] = mini(mini(chunk.heights[south], chunk.heights[south + 1]),
				mini(chunk.heights[north], chunk.heights[north + 1]))


## How many tiles the rectangle holds.
func tile_count() -> int:
	return width * height


## The index of `tile`, or -1 off the rectangle.
func index_of(tile: Vector2i) -> int:
	var local := tile - low

	if local.x < 0 or local.y < 0 or local.x >= width or local.y >= height:
		return -1

	return local.y * width + local.x


## The world tile of `index`. Index order is south row first, then west.
func tile_at(index: int) -> Vector2i:
	@warning_ignore("integer_division")
	return low + Vector2i(index % width, index / width)


func walkable_at(index: int) -> bool:
	return _loaded[index] == 1 and not _flags[index] & _Const.TILE_FLAGS_UNWALKABLE


func walkable(tile: Vector2i) -> bool:
	var index := index_of(tile)

	return index >= 0 and walkable_at(index)


## True when one step from `start` to `end` is legal. See the class comment.
func can_step(start: Vector2i, end: Vector2i) -> bool:
	var offset := end - start

	if not walkable(end):
		return false

	if offset.x != 0 and offset.y != 0:
		for side: Vector2i in [Vector2i(end.x, start.y), Vector2i(start.x, end.y)]:
			if not (walkable(side) and _open_edge(start, side) and _open_edge(side, end)):
				return false
	elif not _open_edge(start, end):
		return false

	var rise := _heights[index_of(end)] - _heights[index_of(start)]

	return absi(rise) <= _Const.TILE_WALK_LIMIT


## True when no wall on either side stops a cardinal step. Both tiles are on
## the rectangle.
func _open_edge(from: Vector2i, to: Vector2i) -> bool:
	var offset := to - from

	if _flags[index_of(from)] & _WALL_LEAVING[offset]:
		return false

	return not _flags[index_of(to)] & _WALL_ENTERING[offset]
