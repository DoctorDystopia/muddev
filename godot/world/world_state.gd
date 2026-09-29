class_name WorldState
extends RefCounted
## The model of the world in the client, built from the state feed.
##
## It keeps two things out of the renderer.
##
## **The ground.** Since DESIGN-0011 Phase 5 (09/25/2026), the world is the
## tile world. The server sends each chunk of the block around the player on
## `blackout_chunk`, one time for each session. This class keeps the chunks in
## one [ChunkSet] for each plane. The 3D pane and the minimap both draw from
## these sets, so the client parses one payload one time. A room off the tile
## world (Limbo) has no chunk, so it shows no ground.
##
## **Planes.** Since DESIGN-0011 Phase 7b (09/26/2026), the server streams the
## block of every plane. The Z of the room of the observer gives its plane.
## `tile_world` is plane 0, and `tile_world_p<p>` is plane p. [member chunks]
## is the set of the plane of the observer. The ground, the pick, the minimap,
## and [method tile_action] read that set. [TerrainView] draws every plane.
##
## **The walk.** Since 09/28/2026, the server sends the current walk on
## `blackout_walk`: the goal, the whole path, and the room Z. The path comes
## one time, at the start. This class drops each tile of the path as the
## observer steps on it, so the minimap draws only the tiles still to walk.
## The destination marker and the walk path are drawn from these fields.
##
## **The float boundary.** `JSON.parse_string` in Godot returns TYPE_FLOAT for
## every number in a payload, for example `{"x": 3.0}`. A dictionary key of
## 3.0 does not match a key of 3, and nothing reports the miss. Thus, every
## value that this class gives out is an int. This class converts each value
## one time, where it reads it. A walk that converts every number would also
## change the first real fraction that the feed sends.


## Server-owned names, generated from blackout/systems/interface/statefeed/constants.py.
## Preloaded, not autoloaded -- the generated file declares no `extends Node`.
const _Const := preload("res://autoload/blackout_constants.gd")


## Emitted when a chunk arrives, or when a move frees chunks outside the
## block. The 3D pane builds its ground again, and the minimap draws again.
## Neither pane reads the feed itself.
signal chunks_changed

## Emitted when the position, the exits, or the tile actions of the observer
## change.
signal room_changed

## Emitted when a walk starts, ends, or loses a tile of its path.
signal walk_changed


## The chunks of the block around the observer, on the plane of the
## observer. [method _free_far_chunks] keeps each plane to the block. Off the
## tile world, it is the set of plane 0.
var chunks: ChunkSet:
	get:
		return plane_chunks(maxi(current_plane, _Const.TILE_GROUND_PLANE))

## The plane of the observer, from the Z of its room. -1 off the tile world.
var current_plane := -1

## Plane (int) -> the [ChunkSet] of that plane. A plane with no chunk here has
## no key.
var _planes := {}

## The reason for the last chunk file that the reader refused. For a test and
## for a log line.
var last_chunk_error := ""

## The z of the room of the observer: [constant _Const.TILE_WORLD_Z] on
## plane 0 of the tile world, and `tile_world_p<p>` on plane p.
var current_z := ""
var current_cell := Vector2i.ZERO

## Direction name -> destination room number, from `room_info.exits`.
var current_exits: Dictionary = {}

## "x:y" -> {command, kind}, from `room_info.tile_actions`. It covers the tile
## of the observer and each tile that one legal step reaches. The server names
## the whole command. A far tile is not in it: see [method tile_action].
var current_tile_actions: Dictionary = {}

## What to send to stop a walk. It is not in the tile actions, because the
## client tracks its own walk.
var current_cancel_action: Dictionary = {}

## The goal tile of the current walk. Read it only when [method has_walk].
var walk_goal := Vector2i.ZERO

## The room Z of the current walk, so a map draws it only on its own plane.
var walk_z := ""

## The tiles that the current walk still has to step on, in order.
var walk_path: Array[Vector2i] = []

## Whether the player has run on. The walk feed carries it, with or without
## a walk, and [signal walk_changed] fires when it arrives.
var running := false

var _walking := false


## Put one feed message into this model.
##
## Returns true when the payload was for this model. The console then routes
## with no second list of channel names. [CharState], [InventoryState] and
## [SummaryState] keep the same contract.
##
## **The CONSOLE calls this, not a pane.** The 3D world and the minimap draw
## the same ground. If each pane read the feed, the client would parse each
## chunk two times.
func ingest(channel: String, payload: Dictionary) -> bool:
	match channel:
		_Const.CH_TILE_CHUNK:
			if ingest_chunk(payload):
				chunks_changed.emit()

		_Const.CH_ROOM_INFO:
			ingest_room_info(payload)
			room_changed.emit()

			if _free_far_chunks():
				chunks_changed.emit()

			if _trim_walk_path():
				walk_changed.emit()

		_Const.CH_WALK:
			ingest_walk(payload)
			walk_changed.emit()

		_:
			return false

	return true


## Put one `blackout_chunk` message into the model.
##
## Returns true when the chunk is good and is now in [member chunks]. The
## model drops a chunk that the reader refuses, and it keeps the reason in
## [member last_chunk_error]. The server reads the same file with the Python
## reader. Thus, a refusal here is a parity bug.
func ingest_chunk(payload: Dictionary) -> bool:
	var chunk := ChunkFile.from_dict(payload.get("chunk_file"))

	if not chunk.error.is_empty():
		last_chunk_error = chunk.error
		push_warning("blackout_chunk refused: %s" % chunk.error)
		return false

	plane_chunks(chunk.plane).add(chunk)

	return true


## The chunk set of one plane. An empty set for a plane with no chunk yet. The
## set joins the model, so a chunk that lands later goes into it.
func plane_chunks(plane: int) -> ChunkSet:
	if not _planes.has(plane):
		_planes[plane] = ChunkSet.new()

	return _planes[plane]


## Every plane that holds a chunk, lowest first.
func planes_held() -> Array[int]:
	var held: Array[int] = []

	for plane: int in _planes:
		if not _planes[plane].chunk_coords().is_empty():
			held.append(plane)

	held.sort()

	return held


## The plane of a room Z, or -1 when the Z is not a plane of the tile world.
## The twin of `planes.plane_of_z` in Python, from the same generated names.
static func plane_of_z(z: String) -> int:
	for plane: int in range(_Const.TILE_GROUND_PLANE, _Const.CHUNK_PLANE_MAX + 1):
		if z == plane_z(plane):
			return plane

	return -1


## The room Z of a plane: the world name for plane 0, else the template.
static func plane_z(plane: int) -> String:
	if plane == _Const.TILE_GROUND_PLANE:
		return _Const.TILE_WORLD_Z

	return _Const.TILE_PLANE_Z_TEMPLATE.format(
		{"world": _Const.TILE_WORLD_Z, "plane": plane})


## Record where the observer stands.
func ingest_room_info(payload: Dictionary) -> void:
	var coords: Array = payload.get("coords", [])

	if coords.size() != 3:
		return

	current_cell = Vector2i(int(coords[0]), int(coords[1]))
	current_z = str(coords[2])
	current_plane = plane_of_z(current_z)
	current_exits = payload.get("exits", {})
	current_tile_actions = payload.get("tile_actions", {})
	current_cancel_action = payload.get("cancel_action", {})


## Record the walk that the server sent. An empty goal ends the walk.
func ingest_walk(payload: Dictionary) -> void:
	var goal: Array = payload.get("goal", [])

	running = bool(payload.get("running", false))
	walk_path.clear()
	_walking = goal.size() == 2

	if not _walking:
		walk_z = ""
		return

	walk_goal = Vector2i(int(goal[0]), int(goal[1]))
	walk_z = str(payload.get("z", ""))

	for tile in payload.get("path", []):
		if tile is Array and tile.size() == 2:
			walk_path.append(Vector2i(int(tile[0]), int(tile[1])))

	# The first step can land before this message does.
	_trim_walk_path()


## True while a walk runs.
func has_walk() -> bool:
	return _walking


## True while a walk runs on the plane of the observer. A map draws the
## destination marker and the walk path only then.
func walk_on_current_plane() -> bool:
	return _walking and walk_z == current_z


## True when the observer stands on the tile world, on any plane.
func on_tile_world() -> bool:
	return current_plane >= _Const.TILE_GROUND_PLANE


## True when the chunk under the observer is here, so the observer has ground
## to stand on. [SessionReadiness] waits for this.
func has_ground() -> bool:
	return on_tile_world() and chunks.has_tile(current_cell)


## The height of the drawn ground at the centre of a tile, in world units.
## Null when its chunk is not loaded. A guess of zero would stand a figure
## inside a hill. A `plane` of -1 means the plane of the observer.
func ground_y(tile: Vector2i, plane: int = -1) -> Variant:
	var chosen: ChunkSet = chunks if plane < 0 else plane_chunks(plane)
	var height := chosen.height_at(Vector2(tile))

	if is_nan(height):
		return null

	return height * ChunkMeshBuilder.HEIGHT_STEP


## The area of a tile, or "" when its chunk is not loaded.
func area_at(tile: Vector2i) -> String:
	return chunks.get_area(tile)


## What a click on a cell means, as {command, kind}. Empty means "do nothing".
##
## THE SERVER DECIDES. The browser pane had a table from a grid delta to a
## direction name, and it deleted that table on 08/23/2026. The table could not
## show a one-way exit or a diagonal link.
##
## Three answers, in this order:
##
## 1. A near tile that the server listed gives its action. An empty command
##    gives {}.
## 2. A far walkable tile of the tile world gives the walk to it. The server
##    spells the command one time, in [constant _Const.TILE_WALK_TEMPLATE],
##    and this fills in the tile. A chunk has 4,096 tiles, so no feed can list
##    each one. [method WorldView.approach_command] fills an entity template
##    in the same way.
## 3. Anything else gives {}: a blocked tile, water, or a chunk not loaded.
##
## The chunk flags say which tile is walkable. They are server facts: the
## server reads the same chunk file. `goto` still refuses a walk that it cannot
## find, in words, in the text pane.
func tile_action(cell: Vector2i) -> Dictionary:
	var key := _Const.TILE_KEY_TEMPLATE \
		.replace("{x}", str(cell.x)) \
		.replace("{y}", str(cell.y))

	if current_tile_actions.has(key):
		var near: Dictionary = current_tile_actions[key]

		if str(near.get("command", "")).is_empty():
			return {}

		return near

	if not on_tile_world() or not chunks.has_tile(cell):
		return {}

	if chunks.get_flags(cell) & _Const.TILE_FLAGS_UNWALKABLE:
		return {}

	var command := _Const.TILE_WALK_TEMPLATE \
		.replace("{x}", str(cell.x)) \
		.replace("{y}", str(cell.y))

	return {"command": command, "kind": _Const.KIND_WALK}


## The chunk coordinates of the block around a tile. The server streams the
## same block (`TileWorld.block_keys`) with the same radius.
static func block_of(tile: Vector2i) -> Array[Vector2i]:
	var centre := ChunkSet.chunk_of_tile(tile)
	var radius: int = _Const.CHUNK_STREAM_RADIUS
	var block: Array[Vector2i] = []

	for dx: int in range(-radius, radius + 1):
		for dy: int in range(-radius, radius + 1):
			block.append(centre + Vector2i(dx, dy))

	return block


## Drop each tile of the walk path up to the tile of the observer. Returns
## true if one went. A tile not on the path drops nothing: the server ends a
## walk that leaves its path.
func _trim_walk_path() -> bool:
	if not _walking or walk_z != current_z:
		return false

	var at := walk_path.find(current_cell)

	if at < 0:
		return false

	walk_path = walk_path.slice(at + 1)

	return true


## Free each chunk outside the block around the observer. Returns true if one
## went. The server forgets the same chunks, so a walk back sends them again.
func _free_far_chunks() -> bool:
	if not on_tile_world():
		return false

	var block := block_of(current_cell)
	var freed := false

	for plane_set: ChunkSet in _planes.values():
		for coord: Vector2i in plane_set.chunk_coords():
			if not block.has(coord):
				plane_set.remove(coord)
				freed = true

	return freed
