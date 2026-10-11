@tool
class_name RoomFill
extends RefCounted
## "Click inside a room" for the Build tools (DESIGN-0013 section 6.7): the
## tiles of the room around one tile.
##
## The fill starts at the clicked tile and crosses each open edge of the
## plane: a cardinal edge with no wall bit on either side, into a loaded
## tile that is not Blocked. It stops at [constant StructureTools.FILL_LIMIT]
## tiles. A fill that reaches the limit is not a room: a doorway or a gap
## lets it out. The author then drags a rectangle.
##
## The rule is not the step rule of the server. A slope does not stop the
## fill, and no diagonal crosses an edge. A room is what its walls close.

const _Const := preload("res://autoload/blackout_constants.gd")


## The fill from `start`: `{tiles: Array[Vector2i], closed: bool}`. `closed`
## is false when the fill reached the limit, or when `start` is not open.
static func fill(chunks: ChunkSet, start: Vector2i,
		limit: int = StructureTools.FILL_LIMIT) -> Dictionary:
	var tiles: Array[Vector2i] = []

	if not _open(chunks, start):
		return {"tiles": tiles, "closed": false}

	var seen := {start: true}

	tiles.append(start)

	var head := 0

	while head < tiles.size():
		var tile := tiles[head]

		head += 1

		for next: Vector2i in _neighbours(chunks, tile):
			if seen.has(next):
				continue

			if tiles.size() >= limit:
				return {"tiles": tiles, "closed": false}

			seen[next] = true
			tiles.append(next)

	return {"tiles": tiles, "closed": true}


## The tiles across each open edge of `tile`.
static func _neighbours(chunks: ChunkSet, tile: Vector2i) -> Array[Vector2i]:
	var found: Array[Vector2i] = []
	var flags := chunks.get_flags(tile)

	for edge: Array in StructureTools.EDGES:
		var next: Vector2i = tile + edge[1]

		if flags & edge[0] or chunks.get_flags(next) & edge[2]:
			continue

		if _open(chunks, next):
			found.append(next)

	return found


static func _open(chunks: ChunkSet, tile: Vector2i) -> bool:
	return chunks.has_tile(tile) \
		and not chunks.get_flags(tile) & _Const.TILE_FLAG_BLOCKED
