class_name WorldState
extends RefCounted
## The model of the world in the client, built from the state feed.
##
## It keeps two things out of the renderer.
##
## **The ground.** Since DESIGN-0011 Phase 5 (09/25/2026), the world is the
## tile world. The server sends each chunk of the block around the player on
## `blackout_chunk`, one time for each session. This class keeps the chunks in
## one [ChunkSet]. The 3D pane and the minimap both draw from that set, so the
## client parses one payload one time. The island levels of the xyzgrid maps
## are gone. Nick chose "tile world only". Thus, a player on an xyzgrid map
## sees no ground in Godot until Phase 4b moves every player.
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


## Every chunk of the block around the observer. [method _free_far_chunks]
## keeps it to the block.
var chunks := ChunkSet.new()

## The reason for the last chunk file that the reader refused. For a test and
## for a log line.
var last_chunk_error := ""

## The z of the room of the observer. It is [constant _Const.TILE_WORLD_Z] on
## the tile world, and a map name on an xyzgrid map.
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

	chunks.add(chunk)

	return true


## Record where the observer stands.
func ingest_room_info(payload: Dictionary) -> void:
	var coords: Array = payload.get("coords", [])

	if coords.size() != 3:
		return

	current_cell = Vector2i(int(coords[0]), int(coords[1]))
	current_z = str(coords[2])
	current_exits = payload.get("exits", {})
	current_tile_actions = payload.get("tile_actions", {})
	current_cancel_action = payload.get("cancel_action", {})


## True when the observer stands on the tile world.
func on_tile_world() -> bool:
	return current_z == _Const.TILE_WORLD_Z


## True when the chunk under the observer is here, so the observer has ground
## to stand on. [SessionReadiness] waits for this.
func has_ground() -> bool:
	return on_tile_world() and chunks.has_tile(current_cell)


## The height of the drawn ground at the centre of a tile, in world units.
## Null when its chunk is not loaded. A guess of zero would stand a figure
## inside a hill.
func ground_y(tile: Vector2i) -> Variant:
	var height := chunks.height_at(Vector2(tile))

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


## Free each chunk outside the block around the observer. Returns true if one
## went. The server forgets the same chunks, so a walk back sends them again.
func _free_far_chunks() -> bool:
	if not on_tile_world():
		return false

	var block := block_of(current_cell)
	var freed := false

	for coord: Vector2i in chunks.chunk_coords():
		if not block.has(coord):
			chunks.remove(coord)
			freed = true

	return freed
