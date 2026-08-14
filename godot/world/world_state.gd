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


## One Z-level's grid.
class Level:
	extends RefCounted

	var cells: Array[Vector2i] = []
	var kinds: Array[String] = []
	var links: Array = []          # [[Vector2i, Vector2i], ...]
	var seen := 0
	var expected := 1

	func is_complete() -> bool:
		return seen >= expected


## z name -> Level. Z is a map NAME, not an elevation.
var levels: Dictionary = {}

var current_z := ""
var current_cell := Vector2i.ZERO

## Direction name -> destination room number, straight from `room_info.exits`.
## Kept so a click can be refused when there is no door that way, rather than
## sending a command the server will only reject.
var current_exits: Dictionary = {}


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
		level.cells.append(Vector2i(int(entry.get("x", 0)), int(entry.get("y", 0))))
		level.kinds.append(str(entry.get("room_kind", "")))

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


## The exit name that steps from one cell to a neighbouring one.
##
## Empty when the cells are the same or more than one step apart, which is what
## makes a click on a distant tile do nothing rather than send a command the
## server would only refuse. Grid Y grows northward -- confirmed by walking:
## `n` from (2,2) arrives at (2,3), `e` from (2,3) arrives at (3,3).
static func direction_for(delta: Vector2i) -> String:
	if delta == Vector2i.ZERO:
		return ""

	if absi(delta.x) > 1 or absi(delta.y) > 1:
		return ""

	var name := ""

	if delta.y > 0:
		name = "north"
	elif delta.y < 0:
		name = "south"

	if delta.x > 0:
		name += "east"
	elif delta.x < 0:
		name += "west"

	return name


func _cell(raw: Variant) -> Vector2i:
	if typeof(raw) != TYPE_ARRAY or raw.size() != 2:
		return Vector2i.ZERO

	return Vector2i(int(raw[0]), int(raw[1]))
