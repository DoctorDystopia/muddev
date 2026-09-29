class_name ChunkSet
extends RefCounted
## A set of loaded chunks, read and written at WORLD coordinates.
##
## The terrain editor (Phase 3) edits through this class, and the client
## (Phase 5) streams chunks into it. A caller never computes which chunk holds
## a tile or a corner. This class owns that rule.
##
## ## Seams
##
## A corner on a chunk edge belongs to two chunks, and a corner at a chunk
## corner belongs to four. Each of those chunk files stores the height. Thus
## [method set_corner] writes every owner, and [method corner_is_editable]
## refuses a corner with an owner that is not loaded. If the editor wrote a
## corner with an unloaded owner, the file of that owner would disagree at the
## seam. The Python seam test would then fail on the next run.
##
## ## Coordinates
##
## World tile (x, y) is local tile (x - cx * 64, y - cy * 64) of chunk
## (cx, cy). World corner (x, y) is the southwest corner of world tile (x, y).
## A point in tile space is a Vector2: tile (x, y) covers x - 0.5 .. x + 0.5,
## as in [ChunkMeshBuilder].

const _Const := preload("res://autoload/blackout_constants.gd")

## Chunk coordinate (Vector2i) to [ChunkFile].
var _chunks := {}

## Chunk coordinates that changed since the last [method mark_clean].
var _dirty := {}


# ─── The set ────────────────────────────────────────────────────────────────

func add(chunk: ChunkFile) -> void:
	_chunks[Vector2i(chunk.cx, chunk.cy)] = chunk


func remove(chunk_coord: Vector2i) -> void:
	_chunks.erase(chunk_coord)
	_dirty.erase(chunk_coord)


func has_chunk(chunk_coord: Vector2i) -> bool:
	return _chunks.has(chunk_coord)


## The chunk at `chunk_coord`, or null when it is not loaded.
func get_chunk(chunk_coord: Vector2i) -> ChunkFile:
	return _chunks.get(chunk_coord)


func chunk_coords() -> Array[Vector2i]:
	var coords: Array[Vector2i] = []

	coords.assign(_chunks.keys())

	return coords


func dirty_coords() -> Array[Vector2i]:
	var coords: Array[Vector2i] = []

	coords.assign(_dirty.keys())

	return coords


func mark_clean(chunk_coord: Vector2i) -> void:
	_dirty.erase(chunk_coord)


# ─── Addressing ─────────────────────────────────────────────────────────────

## The chunk that holds world tile `tile`. The division is exact: the
## subtraction first makes each coordinate a multiple of the chunk size.
static func chunk_of_tile(tile: Vector2i) -> Vector2i:
	var size: int = _Const.CHUNK_SIZE

	@warning_ignore("integer_division")
	return Vector2i((tile.x - posmod(tile.x, size)) / size,
		(tile.y - posmod(tile.y, size)) / size)


## The local coordinates of world tile or corner `world` in chunk `chunk_coord`.
static func local_of(world: Vector2i, chunk_coord: Vector2i) -> Vector2i:
	return world - chunk_coord * _Const.CHUNK_SIZE


## The world tile that holds a point in tile space.
static func tile_at(point: Vector2) -> Vector2i:
	return Vector2i(roundi(point.x), roundi(point.y))


## Every chunk that stores world corner `corner`: one, two, or four.
static func corner_owners(corner: Vector2i) -> Array[Vector2i]:
	var size: int = _Const.CHUNK_SIZE
	var home := chunk_of_tile(corner)
	var columns: Array[int] = [home.x]
	var rows: Array[int] = [home.y]
	var owners: Array[Vector2i] = []

	if posmod(corner.x, size) == 0:
		columns.append(home.x - 1)

	if posmod(corner.y, size) == 0:
		rows.append(home.y - 1)

	for column: int in columns:
		for row: int in rows:
			owners.append(Vector2i(column, row))

	return owners


# ─── Corner heights ─────────────────────────────────────────────────────────

## True when every chunk that stores `corner` is loaded.
func corner_is_editable(corner: Vector2i) -> bool:
	for owner: Vector2i in corner_owners(corner):
		if not _chunks.has(owner):
			return false

	return true


## True when at least one chunk that stores `corner` is loaded.
func corner_is_loaded(corner: Vector2i) -> bool:
	var home := chunk_of_tile(corner)

	return _chunks.has(home)


## The height of world corner `corner`, in height steps. 0 when no owner is
## loaded.
func get_corner(corner: Vector2i) -> int:
	for owner: Vector2i in corner_owners(corner):
		var chunk: ChunkFile = _chunks.get(owner)

		if chunk != null:
			return chunk.heights[_corner_index(corner, owner)]

	return 0


## Write the height of `corner` to every loaded owner, clamped to the legal
## range. The caller checks [method corner_is_editable] first.
func set_corner(corner: Vector2i, height: int) -> void:
	var legal := clampi(height, _Const.CHUNK_HEIGHT_MIN, _Const.CHUNK_HEIGHT_MAX)

	for owner: Vector2i in corner_owners(corner):
		var chunk: ChunkFile = _chunks.get(owner)

		if chunk == null:
			continue

		var index := _corner_index(corner, owner)

		if chunk.heights[index] != legal:
			chunk.heights[index] = legal
			_dirty[owner] = true


static func _corner_index(corner: Vector2i, owner: Vector2i) -> int:
	var local := local_of(corner, owner)

	return local.y * _Const.CHUNK_CORNERS_PER_SIDE + local.x


## The height of the drawn ground at a point in tile space, in height steps.
## NAN when the chunk under the point is not loaded.
func height_at(point: Vector2) -> float:
	var tile := tile_at(point)
	var owner := chunk_of_tile(tile)
	var chunk: ChunkFile = _chunks.get(owner)

	if chunk == null:
		return NAN

	var origin := Vector2(owner * _Const.CHUNK_SIZE)
	var uv := point + Vector2(0.5, 0.5) - origin

	return ChunkMeshBuilder.surface_height(chunk, uv.x, uv.y)


# ─── Tile layers ────────────────────────────────────────────────────────────

func has_tile(tile: Vector2i) -> bool:
	return _chunks.has(chunk_of_tile(tile))


func get_flags(tile: Vector2i) -> int:
	var chunk := _tile_chunk(tile)

	return chunk.flags[_tile_index(tile)] if chunk != null else 0


func set_flags(tile: Vector2i, flags: int) -> void:
	var chunk := _tile_chunk(tile)

	if chunk == null:
		return

	var legal := flags & _Const.TILE_FLAGS_ALL

	if chunk.flags[_tile_index(tile)] != legal:
		chunk.flags[_tile_index(tile)] = legal
		_dirty[chunk_of_tile(tile)] = true


## The floor type name of a tile. Empty when it is not loaded.
func get_floor(tile: Vector2i) -> String:
	var chunk := _tile_chunk(tile)

	return chunk.floor_names[chunk.floors[_tile_index(tile)]] if chunk != null else ""


func set_floor(tile: Vector2i, floor_name: String) -> void:
	var chunk := _tile_chunk(tile)

	if chunk == null:
		return

	var index := _name_index(chunk.floor_names, floor_name)

	if chunk.floors[_tile_index(tile)] != index:
		chunk.floors[_tile_index(tile)] = index
		_dirty[chunk_of_tile(tile)] = true


## The area name of a tile. Empty when it is not loaded.
func get_area(tile: Vector2i) -> String:
	var chunk := _tile_chunk(tile)

	return chunk.area_names[chunk.areas[_tile_index(tile)]] if chunk != null else ""


func set_area(tile: Vector2i, area_name: String) -> void:
	var chunk := _tile_chunk(tile)

	if chunk == null:
		return

	var index := _name_index(chunk.area_names, area_name)

	if chunk.areas[_tile_index(tile)] != index:
		chunk.areas[_tile_index(tile)] = index
		_dirty[chunk_of_tile(tile)] = true


func _tile_chunk(tile: Vector2i) -> ChunkFile:
	return _chunks.get(chunk_of_tile(tile))


static func _tile_index(tile: Vector2i) -> int:
	var local := local_of(tile, chunk_of_tile(tile))

	return local.y * _Const.CHUNK_SIZE + local.x


## The index of `name` in `names`. A new name goes at the end.
static func _name_index(names: PackedStringArray, name: String) -> int:
	var index := names.find(name)

	if index < 0:
		names.append(name)
		index = names.size() - 1

	return index


# ─── Objects ────────────────────────────────────────────────────────────────

## Each object on world tile `tile`, as `{kind, rotation, text}`.
func objects_at(tile: Vector2i) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var chunk := _tile_chunk(tile)

	if chunk == null:
		return found

	var local := local_of(tile, chunk_of_tile(tile))

	for thing: Dictionary in chunk.objects:
		if thing["x"] == local.x and thing["y"] == local.y:
			found.append({"kind": thing["kind"], "rotation": thing["rotation"],
				"text": thing.get("text", "")})

	return found


## Place an object on `tile`. `text` is the words of a signpost, or "".
func add_object(tile: Vector2i, kind: String, rotation: int,
		text: String = "") -> void:
	var chunk := _tile_chunk(tile)

	if chunk == null:
		return

	var local := local_of(tile, chunk_of_tile(tile))

	chunk.objects.append({"kind": kind, "x": local.x, "y": local.y,
		"rotation": rotation, "text": text})
	_dirty[chunk_of_tile(tile)] = true


## Remove one object with this kind, rotation, and text from `tile`. True
## when one was there.
func remove_object(tile: Vector2i, kind: String, rotation: int,
		text: String = "") -> bool:
	var chunk := _tile_chunk(tile)

	if chunk == null:
		return false

	var local := local_of(tile, chunk_of_tile(tile))

	for index: int in chunk.objects.size():
		var thing: Dictionary = chunk.objects[index]

		if thing["x"] == local.x and thing["y"] == local.y \
				and thing["kind"] == kind and thing["rotation"] == rotation \
				and thing.get("text", "") == text:
			chunk.objects.remove_at(index)
			_dirty[chunk_of_tile(tile)] = true
			return true

	return false


# ─── Seams ──────────────────────────────────────────────────────────────────

## One line for each shared corner where two loaded chunks disagree. The
## Python `seam_mismatches` applies the same rule to the files on disk.
func seam_mismatches() -> PackedStringArray:
	var found := PackedStringArray()
	var size: int = _Const.CHUNK_SIZE

	for coord: Vector2i in _chunks:
		for step: Vector2i in [Vector2i(1, 0), Vector2i(0, 1)]:
			if not _chunks.has(coord + step):
				continue

			for along: int in size + 1:
				var local := Vector2i(size, along) if step.x == 1 else Vector2i(along, size)
				var corner := coord * size + local
				var mine: int = _chunks[coord].heights[_corner_index(corner, coord)]
				var theirs: int = _chunks[coord + step].heights[
					_corner_index(corner, coord + step)]

				if mine != theirs:
					found.append("corner %s: %d in %s, %d in %s" % [corner, mine,
						coord, theirs, coord + step])

	return found
