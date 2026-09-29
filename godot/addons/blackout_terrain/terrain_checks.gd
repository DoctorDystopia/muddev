@tool
class_name TerrainChecks
extends RefCounted
## The content rules of a tile world, for the "Check world" button.
##
## The GDScript twin of `blackout/world/tile_checks.py`. That module's
## docstring gives each rule and the reason for it. The Python test runs the
## rules over the world chunk files. The editor runs them over the block that
## the author edits, before a save.
##
## ## The parity
##
## `tests/test_terrain_checks.tscn` and the Python `test_tile_checks` read the
## same fixtures in `blackout/world/tests/fixtures/checks/` and compare with
## one `expected.json`. The rule names come from the generated constants.
##
## A finding is `{rule, x, y, plane, message}`. The message is for a person,
## and it is not part of the parity.

const _Const := preload("res://autoload/blackout_constants.gd")

## The fixtures of the parity test, from the game directory.
const FIXTURES_FROM_GAME := "world/tests/fixtures/checks"


## Check the content rules over every chunk file of a world. Returns the
## findings, sorted by rule, plane, y, and x. Empty means the world is good.
static func check_world(chunk_files: Array[ChunkFile]) -> Array[Dictionary]:
	var planes := _plane_sets(chunk_files)
	var found: Array[Dictionary] = []
	var respawns: Array[Vector3i] = []

	for chunk: ChunkFile in chunk_files:
		found.append_array(_check_void(chunk))

		for thing: Dictionary in chunk.global_objects():
			found.append_array(_check_object(planes, chunk.plane, thing))

			if thing["kind"] == _Const.TILE_RESPAWN_KIND:
				respawns.append(Vector3i(thing["x"], thing["y"], chunk.plane))

	found.append_array(_check_respawn(respawns))
	found.sort_custom(_before)

	return found


## One line of text for a finding, for the dock.
static func describe(finding: Dictionary) -> String:
	return "%s: %s" % [finding["rule"], finding["message"]]


## True when an object of `kind` carries text: the words of a signpost. The
## sign text rule and the editor both ask here.
static func takes_text(kind: String) -> bool:
	return _Const.OBJECT_KINDS.get(kind, "") == _Const.OBJECT_TEXT_CATEGORY


# ─── The rules ───────────────────────────────────────────────────────────────

static func _plane_sets(chunk_files: Array[ChunkFile]) -> Dictionary:
	var planes := {}

	for chunk: ChunkFile in chunk_files:
		if not planes.has(chunk.plane):
			planes[chunk.plane] = ChunkSet.new()

		planes[chunk.plane].add(chunk)

	return planes


static func _walkable(planes: Dictionary, plane: int, tile: Vector2i) -> bool:
	var chunks: ChunkSet = planes.get(plane)

	if chunks == null or not chunks.has_tile(tile):
		return false

	return not chunks.get_flags(tile) & _Const.TILE_FLAGS_UNWALKABLE


static func _check_object(planes: Dictionary, plane: int,
		thing: Dictionary) -> Array[Dictionary]:
	var kind: String = thing["kind"]
	var tile := Vector2i(thing["x"], thing["y"])
	var where := "%s at %s plane %d" % [kind, tile, plane]
	var found: Array[Dictionary] = []

	if not _Const.OBJECT_KINDS.has(kind):
		found.append(_finding(_Const.TILE_CHECK_UNKNOWN_KIND, tile, plane,
			where + ": no such object kind"))
		return found

	if takes_text(kind) == thing["text"].is_empty():
		var problem := "has no text" if takes_text(kind) else "has text, but is no sign"

		found.append(_finding(_Const.TILE_CHECK_SIGN_TEXT, tile, plane,
			where + ": " + problem))

	if not _walkable(planes, plane, tile):
		found.append(_finding(_Const.TILE_CHECK_OBJECT_UNWALKABLE, tile, plane,
			where + ": stands on a Blocked or water tile"))

	var target: Array = _Const.OBJECT_KIND_TARGETS.get(kind, [])

	if not target.is_empty() \
			and not _walkable(planes, plane, Vector2i(target[0], target[1])):
		found.append(_finding(_Const.TILE_CHECK_TRANSITION_LANDING, tile, plane,
			where + ": target %s is not open" % [target]))

	for way: String in _Const.OBJECT_KIND_CLIMBS.get(kind, []):
		var landing: int = plane + _Const.CLIMB_PLANE_STEPS[way]

		if not _walkable(planes, landing, tile):
			found.append(_finding(_Const.TILE_CHECK_CLIMB_LANDING, tile, plane,
				where + ": climb %s lands on no open tile of plane %d" % [way, landing]))

	return found


static func _check_void(chunk: ChunkFile) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var void_index := chunk.floor_names.find(_Const.TILE_VOID_FLOOR)

	if void_index < 0:
		return found

	var size: int = _Const.CHUNK_SIZE

	for index: int in chunk.floors.size():
		if chunk.floors[index] != void_index \
				or chunk.flags[index] & _Const.TILE_FLAG_BLOCKED:
			continue

		@warning_ignore("integer_division")
		var tile := Vector2i(chunk.cx * size + index % size,
			chunk.cy * size + index / size)

		found.append(_finding(_Const.TILE_CHECK_VOID_OPEN, tile, chunk.plane,
			"void at %s plane %d is not Blocked" % [tile, chunk.plane]))

	return found


static func _check_respawn(respawns: Array[Vector3i]) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	if respawns.size() == 1:
		return found

	if respawns.is_empty():
		found.append(_finding(_Const.TILE_CHECK_RESPAWN_COUNT, Vector2i.ZERO,
			_Const.TILE_GROUND_PLANE, "the world has no respawn point"))
		return found

	for point: Vector3i in respawns:
		found.append(_finding(_Const.TILE_CHECK_RESPAWN_COUNT,
			Vector2i(point.x, point.y), point.z, "one of %d respawn points, at (%d, %d) plane %d"
			% [respawns.size(), point.x, point.y, point.z]))

	return found


# ─── Findings ────────────────────────────────────────────────────────────────

static func _finding(rule: String, tile: Vector2i, plane: int,
		message: String) -> Dictionary:
	return {"rule": rule, "x": tile.x, "y": tile.y, "plane": plane,
		"message": message}


## The sort of the Python `Finding`: rule, then plane, then y, then x.
static func _before(a: Dictionary, b: Dictionary) -> bool:
	for field: String in ["rule", "plane", "y", "x"]:
		if a[field] != b[field]:
			return a[field] < b[field]

	return false
