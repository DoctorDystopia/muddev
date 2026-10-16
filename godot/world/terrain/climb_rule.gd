class_name ClimbRule
extends RefCounted
## Where a ladder and a flight of stairs lead, and which tiles a flight
## covers (Nick, 10/16/2026). The GDScript twin of `climb_landing` and
## `flight_tiles` in `blackout/world/object_kinds.py`.
##
## A ladder goes straight up: it lands on its own tile, one plane up or
## down. A flight of stairs has a run of tiles ([method TileTables.climb_run]).
## The steps stand on the tiles in front of the way up, along the facing of
## its object. The way up lands past the top step. The twin of the way up
## stands there, on the plane above, at the same rotation. Its way down lands
## on the foot.
##
## ## The stairwell
##
## The tiles over the steps, on the plane above, are the stairwell. They are
## void, so the floor above does not cover the steps. A stairwell tile is
## still part of the structure:
##
## - A wall under it rises to meet the plane above ([WallMeshBuilder]).
## - A wall on it is legal: the wall of the upper room stands over the
##   opening ([TerrainChecks], rule `wall_on_void`).
## - The Wall line puts a wall on it, not on the void tile across the edge
##   ([StructureTools]).
##
## The client, the editor, and the checks all read this class, so the three
## cannot disagree. `test_structure_tools.tscn`, `test_wall_mesh.tscn`, and
## `test_prop_mesh.tscn` test it. The fixture of the checks holds two flights
## and a wall on a stairwell, in both languages.

const _Const := preload("res://autoload/blackout_constants.gd")

## The landing of a flight is the first tile past its top step.
const PAST_THE_TOP := 1


## The tile step that the front of an object faces at `rotation`.
static func facing(rotation: int) -> Vector2i:
	var step: Array = _Const.CHUNK_ROTATION_STEPS[posmod(rotation,
		_Const.CHUNK_ROTATION_COUNT)]

	return Vector2i(step[0], step[1])


## The tile step of a climb `way` from an object at `rotation`: along its
## facing for a climb up, against it for a climb down.
static func way_step(rotation: int, way: String) -> Vector2i:
	return facing(rotation) * int(_Const.CLIMB_PLANE_STEPS[way])


## The tile where a climb of `kind` at `tile` and `rotation` lands, one plane
## up or down by `way`. A ladder lands on its own tile. A flight lands past
## its top step: the run and one more tile.
static func landing(tile: Vector2i, kind: String, rotation: int, way: String) -> Vector2i:
	var run := TileTables.climb_run(kind)

	if run == 0:
		return tile

	return tile + way_step(rotation, way) * (run + PAST_THE_TOP)


## The tiles between a climb object and its landing, from the object out.
## For a way up, they are the steps. For a way down, they are the stairwell
## over the steps. A ladder has none.
static func flight_tiles(tile: Vector2i, kind: String, rotation: int,
		way: String) -> Array[Vector2i]:
	var tiles: Array[Vector2i] = []

	for index: int in range(1, TileTables.climb_run(kind) + 1):
		tiles.append(tile + way_step(rotation, way) * index)

	return tiles


## The stairwell tiles that the objects of `chunk` give, as world tiles in
## a Dictionary. With `own_plane`, the tiles on the plane of the chunk: from
## each way down. Else the tiles on the plane above it: from each way up.
static func stairwell_tiles(chunk: ChunkFile, own_plane: bool) -> Dictionary:
	var tiles := {}

	if chunk == null:
		return tiles

	var way: String = _Const.CLIMB_DOWN if own_plane else _Const.CLIMB_UP
	var origin := Vector2i(chunk.cx, chunk.cy) * _Const.CHUNK_SIZE

	for thing: Dictionary in chunk.objects:
		var kind: String = thing["kind"]

		if way not in _Const.OBJECT_KIND_CLIMBS.get(kind, []):
			continue

		var tile := origin + Vector2i(thing["x"], thing["y"])

		for well: Vector2i in flight_tiles(tile, kind, thing["rotation"], way):
			tiles[well] = true

	return tiles


## True when `tile` of the plane of `here` is a stairwell tile: a way up on
## `below` has a step under it, or a way down on `here` has it behind. Either
## set may be null. It reads the chunk sets, so a flight across a chunk edge
## counts. [method stairwell_tiles] gives the same tiles for one chunk.
static func is_stairwell(below: ChunkSet, here: ChunkSet, tile: Vector2i) -> bool:
	for rotation: int in _Const.CHUNK_ROTATION_COUNT:
		var ahead := facing(rotation)

		for index: int in range(1, _longest_run() + 1):
			if _flight_reaches(below, tile - ahead * index, rotation, index,
					_Const.CLIMB_UP):
				return true

			if _flight_reaches(here, tile + ahead * index, rotation, index,
					_Const.CLIMB_DOWN):
				return true

	return false


## True when an object on `tile` of `chunks` at `rotation` has a way `way`
## and a run of `index` tiles or more.
static func _flight_reaches(chunks: ChunkSet, tile: Vector2i, rotation: int,
		index: int, way: String) -> bool:
	if chunks == null:
		return false

	for thing: Dictionary in chunks.objects_at(tile):
		var kind: String = thing["kind"]

		if posmod(thing["rotation"], _Const.CHUNK_ROTATION_COUNT) == rotation \
				and way in _Const.OBJECT_KIND_CLIMBS.get(kind, []) \
				and TileTables.climb_run(kind) >= index:
			return true

	return false


## The longest run of any climb kind.
static func _longest_run() -> int:
	var longest := 0

	for kind: String in _Const.OBJECT_KIND_CLIMB_RUNS:
		longest = maxi(longest, _Const.OBJECT_KIND_CLIMB_RUNS[kind])

	return longest
