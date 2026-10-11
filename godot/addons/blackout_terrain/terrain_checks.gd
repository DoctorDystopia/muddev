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
##
## ## Notes
##
## A rule of [code]TILE_CHECK_NOTE_RULES[/code] gives a note. A note warns
## and fails no test ([method is_note]). The `unreachable` rule walks the
## world from the respawn point (DESIGN-0013 section 6.7). [StepGrid] holds
## the twin of the server step rule.

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
		found.append_array(_check_floors(chunk))

		for thing: Dictionary in chunk.global_objects():
			found.append_array(_check_object(planes, chunk.plane, thing))

			if thing["kind"] == _Const.TILE_RESPAWN_KIND:
				respawns.append(Vector3i(thing["x"], thing["y"], chunk.plane))

	found.append_array(_check_respawn(respawns))
	found.append_array(_check_reach(chunk_files, planes, respawns))
	found.sort_custom(_before)

	return found


## The rules of a whole world. A structure workbench holds no respawn point,
## so these rules say nothing about a template there.
const WORLD_RULES := [_Const.TILE_CHECK_RESPAWN_COUNT, _Const.TILE_CHECK_UNREACHABLE]


## `found` without the findings of [constant WORLD_RULES]: "Check world" in
## the structure workbench (DESIGN-0013 Phase S6).
static func for_workbench(found: Array[Dictionary]) -> Array[Dictionary]:
	var kept: Array[Dictionary] = []

	for finding: Dictionary in found:
		if not WORLD_RULES.has(finding["rule"]):
			kept.append(finding)

	return kept


## One line of text for a finding, for the dock.
static func describe(finding: Dictionary) -> String:
	var kind := "note" if is_note(finding) else "finding"

	return "%s %s: %s" % [kind, finding["rule"], finding["message"]]


## True for a note: a warning that fails no test.
static func is_note(finding: Dictionary) -> bool:
	return _Const.TILE_CHECK_NOTE_RULES.has(finding["rule"])


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

	# A decor kind may stand on a Blocked tile (DESIGN-0013 section 6.5).
	var is_decor: bool = _Const.OBJECT_KINDS[kind] == _Const.OBJECT_CATEGORY_DECOR

	if not is_decor and not _walkable(planes, plane, tile):
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


## The findings of [method _floor_findings] for each tile of a file that is
## void or a roof. Every other floor gives none.
static func _check_floors(chunk: ChunkFile) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var size: int = _Const.CHUNK_SIZE

	for index: int in chunk.floors.size():
		var floor_name := chunk.floor_names[chunk.floors[index]]

		if floor_name != _Const.TILE_VOID_FLOOR \
				and not _Const.TILE_ROOF_FLOOR_TYPES.has(floor_name):
			continue

		@warning_ignore("integer_division")
		var tile := Vector2i(chunk.cx * size + index % size,
			chunk.cy * size + index / size)

		found.append_array(_floor_findings(floor_name, tile, chunk.plane,
			chunk.flags[index]))

	return found


## The findings of one tile by its floor: a void tile that is open or has a
## wall, and a roof tile that is open.
static func _floor_findings(floor_name: String, tile: Vector2i, plane: int,
		flags: int) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var where := "%s at %s plane %d" % [floor_name, tile, plane]
	var blocked := flags & _Const.TILE_FLAG_BLOCKED != 0

	if floor_name == _Const.TILE_VOID_FLOOR:
		if not blocked:
			found.append(_finding(_Const.TILE_CHECK_VOID_OPEN, tile, plane,
				where + " is not Blocked"))

		if flags & _Const.TILE_FLAGS_WALLS:
			found.append(_finding(_Const.TILE_CHECK_WALL_ON_VOID, tile, plane,
				where + " carries a wall"))

	if _Const.TILE_ROOF_FLOOR_TYPES.has(floor_name) and not blocked:
		found.append(_finding(_Const.TILE_CHECK_ROOF_WALKABLE, tile, plane,
			where + " is a roof, but is not Blocked"))

	return found


## The cheap rules on the tiles of one Build gesture, as `(x, y, plane)`:
## the floor rules on each tile, and the object rules on each object of the
## tile and of the same tile one plane up and down, since a climb lands
## there. `sets` maps a plane to its [ChunkSet]. The live check of the
## Build tab (DESIGN-0013 section 6.7). "Check world" runs every rule.
static func check_tiles(sets: Dictionary, tiles: Array[Vector3i]) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var objects := {}

	for point: Vector3i in tiles:
		var chunks: ChunkSet = sets.get(point.z)
		var tile := Vector2i(point.x, point.y)

		if chunks == null or not chunks.has_tile(tile):
			continue

		found.append_array(_floor_findings(chunks.get_floor(tile), tile, point.z,
			chunks.get_flags(tile)))

		for step: int in [-1, 0, 1]:
			objects[point + Vector3i(0, 0, step)] = true

	for point: Vector3i in objects:
		var chunks: ChunkSet = sets.get(point.z)

		if chunks == null:
			continue

		for thing: Dictionary in chunks.objects_at(Vector2i(point.x, point.y)):
			var placed := {"kind": thing["kind"], "x": point.x, "y": point.y,
				"text": thing["text"]}

			found.append_array(_check_object(sets, point.z, placed))

	found.sort_custom(_before)

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


# ─── Reach ───────────────────────────────────────────────────────────────────

## One unreachable note for each pocket of walkable tiles that no walk from a
## respawn point reaches. The twin of `_check_reach` in `tile_checks.py`.
static func _check_reach(chunk_files: Array[ChunkFile], planes: Dictionary,
		respawns: Array[Vector3i]) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	if respawns.is_empty():
		return found

	var grids := {}

	for plane: int in planes:
		grids[plane] = StepGrid.of(chunk_files, plane)

	var reached := _reached(grids, _links(chunk_files, planes), respawns)
	var seen := {}
	var order: Array = grids.keys()

	order.sort()

	# Plane, then index order (south row first): the first tile of a pocket
	# is its lowest.
	for plane: int in order:
		var grid: StepGrid = grids[plane]

		for index: int in grid.tile_count():
			if not grid.walkable_at(index):
				continue

			var tile := grid.tile_at(index)
			var point := Vector3i(tile.x, tile.y, plane)

			if reached.has(point) or seen.has(point):
				continue

			var count := _flood_pocket(grid, point, reached, seen)

			found.append(_finding(_Const.TILE_CHECK_UNREACHABLE, tile, plane,
				"%d walkable tile(s) from %s plane %d that no walk from the respawn point reaches"
				% [count, tile, plane]))

	return found


## (x, y, plane) to the (x, y, plane) of each walkable tile where the
## transitions and the climbs of that tile lead.
static func _links(chunk_files: Array[ChunkFile], planes: Dictionary) -> Dictionary:
	var links := {}

	for chunk: ChunkFile in chunk_files:
		for thing: Dictionary in chunk.global_objects():
			var tile := Vector2i(thing["x"], thing["y"])
			var point := Vector3i(tile.x, tile.y, chunk.plane)
			var target: Array = _Const.OBJECT_KIND_TARGETS.get(thing["kind"], [])
			var ends: Array[Vector3i] = []

			if not target.is_empty():
				ends.append(Vector3i(target[0], target[1], chunk.plane))

			for way: String in _Const.OBJECT_KIND_CLIMBS.get(thing["kind"], []):
				ends.append(Vector3i(tile.x, tile.y, chunk.plane + _Const.CLIMB_PLANE_STEPS[way]))

			for end: Vector3i in ends:
				if _walkable(planes, end.z, Vector2i(end.x, end.y)):
					if not links.has(point):
						links[point] = []

					links[point].append(end)

	return links


## Every (x, y, plane) that a walk from `starts` reaches.
static func _reached(grids: Dictionary, links: Dictionary,
		starts: Array[Vector3i]) -> Dictionary:
	var reached := {}
	var queue: Array[Vector3i] = []

	for point: Vector3i in starts:
		var grid: StepGrid = grids.get(point.z)

		if grid != null and grid.walkable(Vector2i(point.x, point.y)) \
				and not reached.has(point):
			reached[point] = true
			queue.append(point)

	var head := 0

	while head < queue.size():
		var point := queue[head]
		var ends := _step_ends(grids[point.z], point)

		head += 1
		ends.append_array(links.get(point, []))

		for end: Vector3i in ends:
			if not reached.has(end):
				reached[end] = true
				queue.append(end)

	return reached


## The (x, y, plane) of each tile that one legal step from `point` reaches.
static func _step_ends(grid: StepGrid, point: Vector3i) -> Array[Vector3i]:
	var ends: Array[Vector3i] = []
	var start := Vector2i(point.x, point.y)

	for step: Vector2i in StepGrid.STEPS:
		var end := start + step

		if grid.can_step(start, end):
			ends.append(Vector3i(end.x, end.y, point.z))

	return ends


## Mark each unreached tile that steps join to `start`. Returns the count.
static func _flood_pocket(grid: StepGrid, start: Vector3i, reached: Dictionary,
		seen: Dictionary) -> int:
	var queue: Array[Vector3i] = [start]
	var head := 0

	seen[start] = true

	while head < queue.size():
		var point := queue[head]

		head += 1

		for end: Vector3i in _step_ends(grid, point):
			if not reached.has(end) and not seen.has(end):
				seen[end] = true
				queue.append(end)

	return queue.size()


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
