class_name WorldMapState
extends RefCounted
## The world map in the client: one image and one icon list for each plane.
##
## ## Where it comes from
##
## The `worldmap` command asks for it (09/28/2026). The server sends the index
## on `blackout_world_map`, then one world map summary for each chunk on
## `blackout_world_map_chunk`. `statefeed/worldmap.py` owns the encoding, and
## [MapRaster] owns the colour of each tile. The server sends a summary one
## time for each session, so this model keeps every one it gets.
##
## ## Why not [WorldState]
##
## [WorldState] holds the chunks of the block around the player, and it frees
## a chunk that falls outside the block. The 3D ground and the minimap draw
## from it. The world map holds every chunk of every plane, with no heights,
## and it frees nothing. Two lifetimes, two models.
##
## ## The image of a plane
##
## One pixel for each tile, row 0 north. The index gives the chunks of each
## plane, so this model knows the bounds of a plane before any summary lands,
## and paints each summary into its place when it arrives.

const _Const := preload("res://autoload/blackout_constants.gd")

## The index arrived. The console opens the world map on it, so a typed
## `worldmap` opens the map as the button does.
signal index_arrived

## A summary was painted into the image of a plane.
signal plane_changed(plane: int)

## Every plane that holds a chunk, lowest first.
var planes: Array[int] = []

## {text, x, y, plane} for each area, as the server sent them.
var labels: Array[Dictionary] = []

## plane -> Rect2i of its tiles: position is the south-west tile.
var _bounds := {}

## plane -> Image, one pixel for each tile.
var _images := {}

## plane -> {Vector2i chunk -> its summary}. Kept, so an index with new
## bounds can paint every summary again.
var _summaries := {}


## Put one feed message into this model. Returns true when the channel is one
## of the two world map channels.
func ingest(channel: String, payload: Dictionary) -> bool:
	match channel:
		_Const.CH_WORLD_MAP:
			ingest_index(payload)
			index_arrived.emit()

		_Const.CH_WORLD_MAP_CHUNK:
			var plane := ingest_summary(payload)

			if plane >= 0:
				plane_changed.emit(plane)

		_:
			return false

	return true


## Record the index: the planes, the labels, and the bounds of each plane.
func ingest_index(payload: Dictionary) -> void:
	planes.clear()

	for plane in payload.get("planes", []):
		planes.append(int(plane))

	planes.sort()
	labels.clear()

	for label in payload.get("labels", []):
		if label is Dictionary:
			labels.append(label)

	var new_bounds := _bounds_of(payload.get("chunks", []))

	for plane: int in new_bounds:
		if _bounds.get(plane) != new_bounds[plane]:
			_bounds[plane] = new_bounds[plane]
			_repaint(plane)


## Record one summary and paint it. Returns its plane, or -1 for a payload
## that is not a summary.
func ingest_summary(payload: Dictionary) -> int:
	var chunk: Array = payload.get("chunk", [])

	if chunk.size() != 2:
		return -1

	var plane := int(payload.get("plane", 0))
	var coord := Vector2i(int(chunk[0]), int(chunk[1]))

	if not _summaries.has(plane):
		_summaries[plane] = {}

	_summaries[plane][coord] = payload
	_paint(plane, coord, payload)

	return plane


## True once an index has arrived.
func has_data() -> bool:
	return not planes.is_empty()


## The tiles of one plane: position is the south-west tile. Empty for a plane
## with no chunk.
func bounds(plane: int) -> Rect2i:
	return _bounds.get(plane, Rect2i())


## The image of one plane, or null for a plane with no chunk.
func image(plane: int) -> Image:
	return _images.get(plane)


## {category, tile} of each chunk object of one plane that has a map icon.
func icons(plane: int) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	for summary: Dictionary in _summaries.get(plane, {}).values():
		for placed in summary.get("objects", []):
			var category := MapIcons.category_of(str(placed.get("kind", "")))

			if MapIcons.has_icon(category):
				found.append({"category": category,
					"tile": Vector2i(int(placed.get("x", 0)), int(placed.get("y", 0)))})

	return found


## The labels of one plane.
func labels_of(plane: int) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	for label: Dictionary in labels:
		if int(label.get("plane", 0)) == plane:
			found.append(label)

	return found


## plane -> Rect2i over every chunk that the index names.
static func _bounds_of(chunks: Array) -> Dictionary:
	var size: int = _Const.CHUNK_SIZE
	var found := {}

	for entry in chunks:
		if not (entry is Array) or entry.size() != 3:
			continue

		var plane := int(entry[2])
		var rect := Rect2i(Vector2i(int(entry[0]), int(entry[1])) * size,
			Vector2i.ONE * size)

		found[plane] = found[plane].merge(rect) if found.has(plane) else rect

	return found


## Build the image of a plane again for new bounds, and paint every summary.
func _repaint(plane: int) -> void:
	var rect: Rect2i = _bounds[plane]

	_images[plane] = Image.create_empty(rect.size.x, rect.size.y, false,
		Image.FORMAT_RGBA8)

	for coord: Vector2i in _summaries.get(plane, {}):
		_paint(plane, coord, _summaries[plane][coord])


func _paint(plane: int, coord: Vector2i, summary: Dictionary) -> void:
	if not _images.has(plane):
		return

	var rect: Rect2i = _bounds[plane]
	var chunk_low := coord * _Const.CHUNK_SIZE

	if not rect.encloses(Rect2i(chunk_low, Vector2i.ONE * _Const.CHUNK_SIZE)):
		return

	MapRaster.paint_summary(_images[plane], str(summary.get("tiles", "")),
		chunk_low, rect.position)
