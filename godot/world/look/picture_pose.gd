@tool
class_name PicturePose
extends RefCounted
## The picture pose of each item as a look file: `item_pictures.json` under
## `res://world/look/` (11/16/2026). A picture pose is the zoom, the offset,
## and the turn of one item picture.
##
## [ItemStage] asks this file for each picture that it draws. An item with
## no row gets the default pose: the picture fills its cell, stands in the
## middle, and has the default turn. Thus, a new item needs no row.
##
## ## The file
##
##     format    1
##     pictures  asset key -> {zoom, offset, turn}
##
## - `zoom` is the share of the cell that the picture fills on its longer
##   side, from [constant ZOOM_LOW] to [constant ZOOM_HIGH]. The stage fits
##   the picture first, so a zoom of 1 fills the cell at each turn.
## - `offset` is `[x, y]` in shares of the cell. A positive x moves the
##   picture to the right, and a positive y moves it up.
## - `turn` is `[x, y, z]` in degrees, in the order of
##   [member Node3D.rotation]. The file holds degrees, because the author
##   types them.
##
## Each key is optional. A key that the row lacks has its default value.
##
## ## A picture stays in its cell
##
## Each picture of a pane is one rectangle of one render target. A picture
## that leaves its cell draws in the cell of the next item. Thus, the zoom
## stops at 1, and [method placed_offset] stops the offset at the edge of
## the cell. A smaller zoom gives the offset more room.
##
## The picture editor (`addons/blackout_pictures`) writes the file. The
## Python guard checks that each key names an item.

const PATH := LookFile.DIRECTORY + "/item_pictures.json"

const FORMAT := 1

const KEY_FORMAT := "format"
const KEY_PICTURES := "pictures"
const KEY_ZOOM := "zoom"
const KEY_OFFSET := "offset"
const KEY_TURN := "turn"

## The pose of an item with no row.
const DEFAULT_ZOOM := 1.0
const DEFAULT_OFFSET := Vector2.ZERO

## The default turn, in degrees. A fixed tilt makes a flat-on orthographic
## camera read as 3D. A turn of zero about the vertical shows a flat item
## flat-on, with no depth.
const DEFAULT_TURN := Vector3(-19.5, 31.5, 0.0)

## The range of the zoom. See "A picture stays in its cell".
const ZOOM_LOW := 0.1
const ZOOM_HIGH := 1.0

## The largest offset on one axis, as a share of the cell: from the middle
## of the cell to its edge.
const OFFSET_LIMIT := 0.5

## The largest turn about one axis, in degrees.
const TURN_LIMIT := 180.0

## How many numbers an offset holds.
const OFFSET_SIZE := 2


# ─── The rows ───────────────────────────────────────────────────────────────

## The row of the file for one item, read from the cache of [LookFile]. An
## empty dictionary for an item with no row.
static func file_row(asset_key: String) -> Dictionary:
	return _row_in(LookFile.read(PATH), asset_key)


## The full row of one item: the row of `content`, with the default value
## for each key that the row lacks. `content` is the content of a picture
## file.
static func shown_row(content: Dictionary, asset_key: String) -> Dictionary:
	var row := _row_in(content, asset_key)

	return row_from(zoom_of(row), offset_of(row), turn_of(row))


## A row of the file. `turn` is in degrees.
static func row_from(zoom: float, offset: Vector2, turn: Vector3) -> Dictionary:
	return {
		KEY_ZOOM: clampf(zoom, ZOOM_LOW, ZOOM_HIGH),
		KEY_OFFSET: [clampf(offset.x, -OFFSET_LIMIT, OFFSET_LIMIT),
			clampf(offset.y, -OFFSET_LIMIT, OFFSET_LIMIT)],
		KEY_TURN: FigureJson.from_vector3(turn),
	}


## The row of the default pose.
static func default_row() -> Dictionary:
	return row_from(DEFAULT_ZOOM, DEFAULT_OFFSET, DEFAULT_TURN)


## True when a row gives the default pose. The file keeps no such row.
static func is_default(row: Dictionary) -> bool:
	return is_equal_approx(zoom_of(row), DEFAULT_ZOOM) \
		and offset_of(row).is_equal_approx(DEFAULT_OFFSET) \
		and turn_of(row).is_equal_approx(DEFAULT_TURN)


# ─── The values of a row ────────────────────────────────────────────────────

## The zoom of a row, in its range. The default for a row with no zoom.
static func zoom_of(row: Dictionary) -> float:
	var zoom: Variant = row.get(KEY_ZOOM)

	if not typeof(zoom) in [TYPE_INT, TYPE_FLOAT]:
		return DEFAULT_ZOOM

	return clampf(zoom, ZOOM_LOW, ZOOM_HIGH)


## The offset of a row, in shares of the cell and in its range. The default
## for a row with no offset.
static func offset_of(row: Dictionary) -> Vector2:
	var offset: Variant = row.get(KEY_OFFSET)

	if not FigureJson.is_numbers(offset, OFFSET_SIZE):
		return DEFAULT_OFFSET

	return Vector2(clampf(offset[0], -OFFSET_LIMIT, OFFSET_LIMIT),
		clampf(offset[1], -OFFSET_LIMIT, OFFSET_LIMIT))


## The turn of a row, in degrees. The default for a row with no turn.
static func turn_of(row: Dictionary) -> Vector3:
	return FigureJson.vector3(row.get(KEY_TURN), DEFAULT_TURN)


## The turn of a row as the camera sees the item. A turn of the file has
## the order of [member Node3D.rotation]: the turn about Z comes first, then
## the tilt about X, then the turn about the vertical.
static func basis_of(row: Dictionary) -> Basis:
	var degrees := turn_of(row)
	var radians := Vector3(deg_to_rad(degrees.x), deg_to_rad(degrees.y), deg_to_rad(degrees.z))

	return Basis.from_euler(radians)


## The offset that the stage gives a picture, in the units of `side`.
##
## - `drawn` is the size of the outline of the picture after the zoom.
## - `side` is the side of the square that a picture can fill.
##
## The offset of the row stops where the outline meets the edge of that
## square. See "A picture stays in its cell".
static func placed_offset(row: Dictionary, drawn: Vector2, side: float) -> Vector2:
	var wanted := offset_of(row) * side
	var room := ((Vector2.ONE * side) - drawn) * 0.5

	room = room.max(Vector2.ZERO)

	return wanted.clamp(-room, room)


# ─── The content of a picture file ──────────────────────────────────────────

## Give one item its row in `content`: the content of a picture file. A row
## of the default pose takes the row of the item out, so the file holds
## only what an author changed.
static func set_picture(content: Dictionary, asset_key: String, row: Dictionary) -> void:
	if asset_key.is_empty():
		return

	if is_default(row):
		clear_picture(content, asset_key)
		return

	if typeof(content.get(KEY_PICTURES)) != TYPE_DICTIONARY:
		content[KEY_PICTURES] = {}

	content[KEY_FORMAT] = FORMAT
	content[KEY_PICTURES][asset_key] = row_from(zoom_of(row), offset_of(row), turn_of(row))


## Take the row of one item out of `content`. Returns true when the content
## changed.
static func clear_picture(content: Dictionary, asset_key: String) -> bool:
	var rows: Variant = content.get(KEY_PICTURES)

	if typeof(rows) != TYPE_DICTIONARY or not rows.has(asset_key):
		return false

	rows.erase(asset_key)

	return true


## True when `content` has a row for the item.
static func has_picture(content: Dictionary, asset_key: String) -> bool:
	return not _row_in(content, asset_key).is_empty()


## Why the content of a picture file has a bad form, or "". An empty content
## has a good form: it is a file that is not there.
static func problem_of(content: Dictionary) -> String:
	if content.is_empty():
		return ""

	var format: Variant = content.get(KEY_FORMAT)

	if not typeof(format) in [TYPE_INT, TYPE_FLOAT] or format < 1:
		return "a picture file needs a format number"

	if format > FORMAT:
		return "format %d is newer than this reader (format %d)" % [format, FORMAT]

	if typeof(content.get(KEY_PICTURES, {})) != TYPE_DICTIONARY:
		return "pictures must be a table"

	for asset_key: String in content.get(KEY_PICTURES, {}):
		var problem := _row_problem(asset_key, content[KEY_PICTURES][asset_key])

		if not problem.is_empty():
			return problem

	return ""


# ─── Private ────────────────────────────────────────────────────────────────

## The row of one item in the content of a picture file, or an empty
## dictionary.
static func _row_in(content: Dictionary, asset_key: String) -> Dictionary:
	var rows: Variant = content.get(KEY_PICTURES, {})

	if typeof(rows) != TYPE_DICTIONARY:
		return {}

	var row: Variant = rows.get(asset_key, {})

	return row if typeof(row) == TYPE_DICTIONARY else {}


static func _row_problem(asset_key: String, row: Variant) -> String:
	if typeof(row) != TYPE_DICTIONARY:
		return "the picture %s needs a table" % asset_key

	if row.has(KEY_ZOOM) and not typeof(row[KEY_ZOOM]) in [TYPE_INT, TYPE_FLOAT]:
		return "the zoom of the picture %s must be a number" % asset_key

	if row.has(KEY_OFFSET) and not FigureJson.is_numbers(row[KEY_OFFSET], OFFSET_SIZE):
		return "the offset of the picture %s must be [x, y]" % asset_key

	if row.has(KEY_TURN) and not FigureJson.is_numbers(row[KEY_TURN], FigureJson.VECTOR_SIZE):
		return "the turn of the picture %s must be [x, y, z]" % asset_key

	return ""
