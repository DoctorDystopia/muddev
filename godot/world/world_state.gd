class_name WorldState
extends RefCounted
## The client's model of the world, assembled from the state feed.
##
## Exists to keep two things out of the renderer.
##
## **Chunk reassembly.** A map arrives as `chunk_count` messages; only chunk 0
## carries the links (see mapexport.build_map_chunks). Nothing can be drawn
## until the last one lands.
##
## **The float boundary.** Godot's `JSON.parse_string` returns TYPE_FLOAT for
## every number in a payload -- `{"x": 3.0, "num": 19863.0}`, always. A
## dictionary keyed on that will not match a key written as `3`, and the
## failure is silent. Every value this class hands out is already an int, and
## the conversion happens once, here, at the point of use rather than as a
## blanket walk: every numeric field in the feed happens to be integral today,
## so a recursive coercion would look correct and would quietly corrupt the
## first genuinely fractional field anyone adds.


## Server-owned names, generated from blackout/systems/statefeed/constants.py.
## Preloaded, not autoloaded -- the generated file declares no `extends Node`.
const _Const := preload("res://autoload/blackout_constants.gd")


## One Z-level's grid.
class Level:
	extends RefCounted

	var cells: Array[Vector2i] = []
	var kinds: Array[String] = []
	var links: Array = []          # [[Vector2i, Vector2i], ...]

	## cell -> {command, kind}: the pathfinder `goto` to that node, stamped
	## once per session because the walk to (6,3) is the same from anywhere on
	## the map. A node the server gave no action affords nothing.
	var actions: Dictionary = {}

	var seen := 0
	var expected := 1

	func is_complete() -> bool:
		return seen >= expected


## z name -> Level. Z is a map NAME, not an elevation.
var levels: Dictionary = {}

var current_z := ""
var current_cell := Vector2i.ZERO

## Direction name -> destination room number, straight from `room_info.exits`.
var current_exits: Dictionary = {}

## "x:y" -> {command, kind}, covering the observer's own tile and everything
## one REAL exit away. Straight from `room_info.tile_actions`.
##
## The server names the whole command; nothing here substitutes into it. It
## also covers only the near tiles, because the walk to a distant node does not
## change when the observer moves and is stamped on the map node instead.
var current_tile_actions: Dictionary = {}

## What to send to stop a walk already running. NOT part of tile_actions,
## because whether a walk IS running is the client's own tracking -- the client
## is what started it.
var current_cancel_action: Dictionary = {}


## Fold one `blackout_map` chunk into the model.
##
## Returns the z name when that level is now complete and ready to draw, or an
## empty string when more chunks are still due.
func ingest_map_chunk(payload: Dictionary) -> String:
	var z := str(payload.get("z", ""))
	var index := int(payload.get("chunk_index", 0))

	# Chunk 0 restarts the level. A resync re-sends the whole map, and
	# appending to the previous copy would double every tile.
	if index == 0 or not levels.has(z):
		levels[z] = Level.new()

	var level: Level = levels[z]
	level.expected = int(payload.get("chunk_count", 1))
	level.seen += 1

	for entry: Dictionary in payload.get("nodes", []):
		var cell := Vector2i(int(entry.get("x", 0)), int(entry.get("y", 0)))
		level.cells.append(cell)
		level.kinds.append(str(entry.get("room_kind", "")))

		var action: Dictionary = entry.get("action", {})

		if not action.is_empty():
			level.actions[cell] = action

	for entry: Dictionary in payload.get("links", []):
		var from := _cell(entry.get("from"))
		var to := _cell(entry.get("to"))

		if from != to:
			level.links.append([from, to])

	if level.is_complete():
		return z

	return ""


## Record where the observer is standing.
func ingest_room_info(payload: Dictionary) -> void:
	var coords: Array = payload.get("coords", [])

	if coords.size() != 3:
		return

	current_cell = Vector2i(int(coords[0]), int(coords[1]))
	current_z = str(coords[2])
	current_exits = payload.get("exits", {})
	current_tile_actions = payload.get("tile_actions", {})
	current_cancel_action = payload.get("cancel_action", {})


## What clicking a cell means, as {command, kind}. Empty means "do nothing".
##
## THE SERVER DECIDES. This replaced a grid-delta -> direction-name table that
## the browser pane deleted for cause on 08/23/2026: that table could not
## express a one-way exit, a diagonal link, or a map whose geometry and
## direction names disagree, and it got the diagonal case wrong once in the
## direction of "the tiles nearest the player were the only ones that could not
## be clicked". Directions now come from the room's REAL spawned exits.
##
## Two lookups and one distinction:
##
##   near tile, EMPTY command -> {} . The server says no.
##   near tile, ABSENT        -> fall through to the node's own `goto`.
##
## Nothing on the server sends an empty command today. It used to, for every
## cardinal neighbour reached by no exit, on the theory that an unlinked
## neighbour is a wall the player can see -- and that theory made the foundry
## tile at oasis (6,3), joined to four DIAGONAL neighbours and two steps from
## (6,2) below it, permanently unclickable. The branch stays because the field
## is a wire contract, not because anything fills it.
##
## A node the map gave no `action` affords nothing either, and a map TRANSITION
## is that case: it spawns no room for `goto` to resolve, so it is reached by
## stepping onto it from beside it -- a near action, not a fall-through.
##
## `cell` is resolved in the CURRENT island's coordinate space by
## WorldView._cell_under, so a click on another island lands on a cell this map
## has no node for and correctly affords nothing. `goto` does not cross maps.
func tile_action(cell: Vector2i) -> Dictionary:
	var key := _Const.TILE_KEY_TEMPLATE \
		.replace("{x}", str(cell.x)) \
		.replace("{y}", str(cell.y))

	if current_tile_actions.has(key):
		var near: Dictionary = current_tile_actions[key]

		if str(near.get("command", "")).is_empty():
			return {}

		return near

	if not levels.has(current_z):
		return {}

	var level: Level = levels[current_z]

	return level.actions.get(cell, {})


func _cell(raw: Variant) -> Vector2i:
	if typeof(raw) != TYPE_ARRAY or raw.size() != 2:
		return Vector2i.ZERO

	return Vector2i(int(raw[0]), int(raw[1]))
