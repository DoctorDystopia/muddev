@tool
class_name TileSelection
extends RefCounted
## The tile selection of the Select tool of the Build tab (DESIGN-0013
## section 6.7): a set of tiles, each on one plane. Delete, Copy, Move, and
## "Save as template" act on it.
##
## A drag adds a rectangle. On every plane, it adds the rectangle on the
## edited plane and on each plane above it. A click inside a room adds the
## room, and on every plane, the floors and the roof over it: on each plane
## above, the fill crosses each tile that is not void, from the tiles over
## the plane below. Thus, a click takes a roof with its overhang.
##
## No function calls the editor, so a test drives it with no editor.

const _Const := preload("res://autoload/blackout_constants.gd")

## Vector3i(x, y, plane) of each selected tile.
var keys := {}


func is_empty() -> bool:
	return keys.is_empty()


func clear() -> void:
	keys = {}


func size() -> int:
	return keys.size()


## The lowest and the highest plane of the selection, as Vector2i(low,
## high). (0, 0) when it is empty.
func plane_span() -> Vector2i:
	if keys.is_empty():
		return Vector2i.ZERO

	var low: int = _Const.CHUNK_PLANE_MAX
	var high: int = _Const.TILE_GROUND_PLANE

	for at: Vector3i in keys:
		low = mini(low, at.z)
		high = maxi(high, at.z)

	return Vector2i(low, high)


## The planes that a gesture on `plane` reaches: `plane` alone, or with
## `every_plane` it and each plane above.
static func planes_of(plane: int, every_plane: bool) -> Array[int]:
	var found: Array[int] = [plane]

	if every_plane:
		found.assign(range(plane, _Const.CHUNK_PLANE_MAX + 1))

	return found


## Add or take out (`remove`) each tile of `rect` on each plane of `planes`.
func change_rect(rect: Rect2i, planes: Array[int], remove: bool) -> void:
	for on_plane: int in planes:
		for tile: Vector2i in StructureTools.rect_tiles(rect):
			_change(Vector3i(tile.x, tile.y, on_plane), remove)


func _change(at: Vector3i, remove: bool) -> void:
	if remove:
		keys.erase(at)
	else:
		keys[at] = true


## Add or take out the room around `tile` of `plane`, and with `every_plane`
## the floors over it. Returns the problem, or "". `sets` maps a plane to
## its [ChunkSet].
func change_room(sets: Dictionary, plane: int, tile: Vector2i, every_plane: bool,
		remove: bool) -> String:
	var found := RoomFill.fill(sets[plane], tile)

	if not found["closed"]:
		return "Not a room: the fill found no closed walls. Drag a rectangle."

	var below: Array[Vector2i] = found["tiles"]

	for each: Vector2i in below:
		_change(Vector3i(each.x, each.y, plane), remove)

	if not every_plane:
		return ""

	for on_plane: int in range(plane + 1, _Const.CHUNK_PLANE_MAX + 1):
		below = floors_over(sets.get(on_plane), below)

		for each: Vector2i in below:
			_change(Vector3i(each.x, each.y, on_plane), remove)

	return ""


## The tiles of `chunks` that are not void and that join a tile over
## `below` through tiles that are not void, up to the fill limit.
static func floors_over(chunks: ChunkSet, below: Array[Vector2i]) -> Array[Vector2i]:
	var found: Array[Vector2i] = []

	if chunks == null:
		return found

	var seen := {}

	for tile: Vector2i in below:
		if _has_floor(chunks, tile):
			seen[tile] = true
			found.append(tile)

	var head := 0

	while head < found.size() and found.size() < StructureTools.FILL_LIMIT:
		var tile := found[head]

		head += 1

		for edge: Array in StructureTools.EDGES:
			var next: Vector2i = tile + edge[1]

			if not seen.has(next) and _has_floor(chunks, next):
				seen[next] = true
				found.append(next)

	return found


static func _has_floor(chunks: ChunkSet, tile: Vector2i) -> bool:
	return chunks.has_tile(tile) and chunks.get_floor(tile) != _Const.TILE_VOID_FLOOR


## The world tiles of the selection on any plane, once each.
func footprint() -> Dictionary:
	var tiles := {}

	for at: Vector3i in keys:
		tiles[Vector2i(at.x, at.y)] = true

	return tiles


## The outline of a set of tiles as paths for [method TerrainOverlay.path_mesh]:
## each edge of a tile that no other tile of the set shares.
static func outline_paths(tiles: Dictionary) -> Array:
	var paths := []

	for tile: Vector2i in tiles:
		for edge: Array in StructureTools.EDGES:
			if not tiles.has(tile + edge[1]):
				paths.append(TerrainOverlay.edge_path(tile, edge[0]))

	return paths
