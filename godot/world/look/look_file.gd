@tool
class_name LookFile
extends RefCounted
## A look file: one JSON file under `res://world/look/` that holds a look
## of the game, for example the colour of each floor type or the fog of
## each area. The author edits it from the Look tab of the terrain editor,
## and the game reads it at start.
##
## The rule of the repo holds: Python owns what is true, and the client
## owns what it looks like. A look file is the client's. The server never
## reads one, and the Python guard tests only check that each key names a
## real server fact.
##
## Each reader keeps its old table as the fallback. A key with no row in
## the file draws as before the file existed. Thus, a new floor type, wall
## style, or area needs no edit here, and a missing file breaks nothing.
##
## A read goes through a cache, so a mesh build pays for no file read. A
## write puts the content in the cache too, so the next build sees it.
## [method forget] drops one file from the cache, for a test and for a
## reload after an edit outside Godot.

## The directory of every look file.
const DIRECTORY := "res://world/look"

## The `format` of a look file that this reader understands.
const FORMAT := 1

static var _cache := {}


## The content of the file at `path`, or an empty dictionary for a file
## that is not there or does not read. The content comes from the cache
## after the first read.
static func read(path: String) -> Dictionary:
	if _cache.has(path):
		return _cache[path]

	var data := {}

	if FileAccess.file_exists(path):
		data = FigureJson.parse(FileAccess.get_file_as_string(path))

	_cache[path] = data

	return data


## Write `data` to the file at `path`, with sorted keys, so the same content
## gives the same bytes. Returns the error of the write.
static func write(path: String, data: Dictionary) -> Error:
	var file := FileAccess.open(path, FileAccess.WRITE)

	if file == null:
		return FileAccess.get_open_error()

	file.store_string(FigureJson.to_text(data))
	file.close()
	_cache[path] = data

	return OK


## Move the row `old` of the table `section` to `new`, in the file at
## `path`. The Tables tab calls it for a rename of a server row. Returns
## true when the file changed. A file with no row `old` stays as it is.
static func rename_key(path: String, section: String, old: String, new: String) -> bool:
	var data: Dictionary = read(path).duplicate(true)
	var rows: Variant = data.get(section)

	if not rows is Dictionary or not rows.has(old):
		return false

	rows[new] = rows[old]
	rows.erase(old)

	return write(path, data) == OK


## Take the row `key` out of the table `section`, in the file at `path`.
## Returns true when the file changed.
static func erase_key(path: String, section: String, key: String) -> bool:
	var data: Dictionary = read(path).duplicate(true)
	var rows: Variant = data.get(section)

	if not rows is Dictionary or not rows.has(key):
		return false

	rows.erase(key)

	return write(path, data) == OK


## Drop `path` from the cache, so the next read goes to the disk.
static func forget(path: String) -> void:
	_cache.erase(path)


## Put `data` in the cache for `path`, and write no file. A test gives a
## reader its content this way, and forgets it after.
static func put(path: String, data: Dictionary) -> void:
	_cache[path] = data


## The colour of a hex text, or `fallback` for a text that is no colour.
static func color_of(value: Variant, fallback: Color) -> Color:
	if typeof(value) != TYPE_STRING or not Color.html_is_valid(value):
		return fallback

	return Color.html(value)


## The hex text of a colour, six digits, as the files store it.
static func hex_of(color: Color) -> String:
	return color.to_html(false)


## One field of a look as the files store it: the hex text of a colour, or
## a number.
static func stored_of(value: Variant) -> Variant:
	if value is Color:
		return hex_of(value)

	return float(value)
