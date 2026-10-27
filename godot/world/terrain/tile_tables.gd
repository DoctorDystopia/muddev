@tool
class_name TileTables
extends RefCounted
## The one GDScript reader of the four server tables that an author adds
## rows to: the areas, the floor types, the wall styles, and the decor kinds
## (10/14/2026). `blackout/world/table_file.py` is the Python reader, and
## its docstring gives the format of a table file.
##
## ## Two sources
##
## - **The editor** reads the table files of the game directory,
##   `blackout/world/tables/`. The Tables tab of the terrain editor writes
##   them. Thus, each list of the editor follows a new row at once, with no
##   export and no reload.
## - **The game** reads the generated constants. The export of the server
##   made them, and the game must read what its server reads. The world map
##   sends a floor type as its index in [code]TILE_FLOOR_TYPES[/code], for
##   example.
##
## A test picks the source with [method use_files] or [method use_constants].
## [method use_auto] gives the rule back.
##
## A table file that does not read gives the constants for that table, and
## [method errors] names the file. Thus, a bad hand edit never empties a list
## of the editor.
##
## ## The object kinds
##
## Only the decor kinds are a table file. Every other object kind is a
## Python row, because it names a spawner, a target, or a climb. Thus
## [method object_kinds] joins the constants, less their decor rows, and the
## decor table. The Python table puts the decor rows last too.
##
## ## The cache
##
## A read goes through a cache, so a mesh build pays for no file read. A
## write through [method write_rows] drops the cache. [method forget] drops it
## too, for a test and for an edit outside Godot.

const _Const := preload("res://autoload/blackout_constants.gd")

## The names of the tables, as the keys of [code]TILE_TABLE_FIELDS[/code].
const AREAS := "areas"
const FLOOR_TYPES := "floor_types"
const WALL_STYLES := "wall_styles"
const DECOR_KINDS := "decor_kinds"

## The keys of a table file, and the fields that a reader here uses.
const KEY_FORMAT := "format"
const KEY_ROWS := "rows"
const FIELD_KEY := "key"
const FIELD_ROOF := "roof"
const FIELD_SCENERY := "scenery"

enum Source { AUTO, FILES, CONSTANTS }

static var _source := Source.AUTO

## The directory of [method use_files], or "" for the game directory.
static var _directory := ""

## Table name to `{rows, index, keys}`.
static var _cache := {}

## Table name to the problem of its file.
static var _errors := {}

## The map of [method object_kinds], or empty before the first call.
static var _kinds := {}


# ─── The source ─────────────────────────────────────────────────────────────

## The table directory, as an OS path.
static func directory() -> String:
	if not _directory.is_empty():
		return _directory

	var project := ProjectSettings.globalize_path("res://")
	var game := project.path_join(ChunkFile.GAME_DIRECTORY_FROM_PROJECT)

	return game.path_join(_Const.TILE_TABLE_DIRECTORY).simplify_path()


## The path of the file of `table`.
static func file_path(table: String) -> String:
	return directory().path_join(table + _Const.TILE_TABLE_FILE_SUFFIX)


## True when the tables come from the files. See "Two sources" above.
static func reads_files() -> bool:
	match _source:
		Source.FILES:
			return true
		Source.CONSTANTS:
			return false

	return Engine.is_editor_hint() and DirAccess.dir_exists_absolute(directory())


## Read the files of `from`, or of the game directory for "". A test.
static func use_files(from := "") -> void:
	_source = Source.FILES
	_directory = from
	forget()


## Read the generated constants. A test.
static func use_constants() -> void:
	_source = Source.CONSTANTS
	_directory = ""
	forget()


## The rule of "Two sources" again.
static func use_auto() -> void:
	_source = Source.AUTO
	_directory = ""
	forget()


## Drop the cache, so the next read goes to the source.
static func forget() -> void:
	_cache.clear()
	_errors.clear()
	_kinds.clear()


## One line for each table file that did not read.
static func errors() -> PackedStringArray:
	return PackedStringArray(_errors.values())


# ─── The rows ───────────────────────────────────────────────────────────────

## A copy of every row of `table`, in the order of the table.
static func rows(table: String) -> Array[Dictionary]:
	var copies: Array[Dictionary] = []

	for table_row: Dictionary in _entry(table)["rows"]:
		copies.append(table_row.duplicate(true))

	return copies


## Every key of `table`, in the order of the table.
static func keys(table: String) -> PackedStringArray:
	return _entry(table)["keys"]


## A copy of the row of `key`, or an empty Dictionary.
static func row(table: String, key: String) -> Dictionary:
	var found: Dictionary = _entry(table)["index"].get(key, {})

	return found.duplicate(true)


static func has_key(table: String, key: String) -> bool:
	return _entry(table)["index"].has(key)


## Write `new_rows` as the file of `table`, in the canonical text of
## [FigureJson]. Returns the error of the write. The cache drops.
static func write_rows(table: String, new_rows: Array[Dictionary]) -> Error:
	var data := {KEY_FORMAT: _Const.TILE_TABLE_FORMAT, KEY_ROWS: new_rows}
	var file := FileAccess.open(file_path(table), FileAccess.WRITE)

	if file == null:
		return FileAccess.get_open_error()

	file.store_string(FigureJson.to_text(data))
	file.close()
	forget()

	return OK


## The rows of the file at `path`, or `{error}` for a file that does not
## read. The light check of a reader: the Python reader has every rule.
static func read_file(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {"error": "%s is not there." % path}

	var data := FigureJson.parse(FileAccess.get_file_as_string(path))
	var found: Variant = data.get(KEY_ROWS)

	if data.get(KEY_FORMAT) != _Const.TILE_TABLE_FORMAT:
		return {"error": "%s: the format is not %d." % [path, _Const.TILE_TABLE_FORMAT]}

	if not found is Array or found.is_empty():
		return {"error": "%s: the file has no rows." % path}

	for item: Variant in found:
		if not item is Dictionary or not item.get(FIELD_KEY) is String:
			return {"error": "%s: a row has no key." % path}

	return {"rows": found}


# ─── The facts ──────────────────────────────────────────────────────────────

## The area of a new chunk: the first row.
static func default_area() -> String:
	return keys(AREAS)[0]


## The floor type of a new chunk: the first row.
static func default_floor() -> String:
	return keys(FLOOR_TYPES)[0]


## The roof floor types, in the order of the table.
static func roof_floor_types() -> PackedStringArray:
	var roofs := PackedStringArray()

	for found: Dictionary in _entry(FLOOR_TYPES)["rows"]:
		if found.get(FIELD_ROOF, false):
			roofs.append(found[FIELD_KEY])

	return roofs


static func is_roof(floor_name: String) -> bool:
	var found: Dictionary = _entry(FLOOR_TYPES)["index"].get(floor_name, {})

	return found.get(FIELD_ROOF, false)


static func decor_kinds() -> PackedStringArray:
	return keys(DECOR_KINDS)


static func is_decor(kind: String) -> bool:
	return has_key(DECOR_KINDS, kind)


## Every object kind and its category: the Python rows of the constants,
## then the decor table.
static func object_kinds() -> Dictionary:
	if not _kinds.is_empty():
		return _kinds

	for kind: String in _Const.OBJECT_KINDS:
		if _Const.OBJECT_KINDS[kind] != _Const.OBJECT_CATEGORY_DECOR:
			_kinds[kind] = _Const.OBJECT_KINDS[kind]

	for kind: String in decor_kinds():
		_kinds[kind] = _Const.OBJECT_CATEGORY_DECOR

	return _kinds


## The category of `kind`, or "" for a kind that no table has.
static func object_category(kind: String) -> String:
	return object_kinds().get(kind, "")


## The scenery of `kind`: the decor row, then the constants. "" for none.
static func scenery_of(kind: String) -> String:
	var found: Dictionary = _entry(DECOR_KINDS)["index"].get(kind, {})

	if not found.is_empty():
		return found.get(FIELD_SCENERY, "")

	if _Const.OBJECT_KINDS.get(kind, "") == _Const.OBJECT_CATEGORY_DECOR:
		return ""

	return _Const.OBJECT_KIND_SCENERY.get(kind, "")


## Every scenery key that some object kind names, each one time, in the
## order of the kinds. The Look tab lists them for a light ([LightLook]).
static func scenery_keys() -> PackedStringArray:
	var found := PackedStringArray()

	for kind: String in object_kinds():
		var key := scenery_of(kind)

		if not key.is_empty() and not found.has(key):
			found.append(key)

	return found


## The tiles of the flight of a climb kind, or 0 for a ladder and every
## other kind. A climb is a Python row, so the constants hold it.
static func climb_run(kind: String) -> int:
	return _Const.OBJECT_KIND_CLIMB_RUNS.get(kind, 0)


# ─── The cache ──────────────────────────────────────────────────────────────

static func _entry(table: String) -> Dictionary:
	if not _cache.has(table):
		_cache[table] = _indexed(_rows_from_source(table))

	return _cache[table]


static func _rows_from_source(table: String) -> Array:
	if not reads_files():
		return _constant_rows(table)

	var read := read_file(file_path(table))

	if read.has("error"):
		_errors[table] = read["error"]
		return _constant_rows(table)

	return read["rows"]


static func _indexed(found: Array) -> Dictionary:
	var index := {}
	var names := PackedStringArray()

	for item: Dictionary in found:
		index[item[FIELD_KEY]] = item
		names.append(item[FIELD_KEY])

	return {"rows": found, "index": index, "keys": names}


## The rows of `table` as the generated constants give them: the key, and
## the roof or the scenery.
static func _constant_rows(table: String) -> Array:
	var made := []

	match table:
		AREAS:
			for key: String in _Const.TILE_AREAS:
				made.append({FIELD_KEY: key})
		FLOOR_TYPES:
			for key: String in _Const.TILE_FLOOR_TYPES:
				made.append({FIELD_KEY: key, FIELD_ROOF: key in _Const.TILE_ROOF_FLOOR_TYPES})
		WALL_STYLES:
			for key: String in _Const.TILE_WALL_STYLES:
				made.append({FIELD_KEY: key})
		DECOR_KINDS:
			for key: String in _Const.OBJECT_KINDS:
				if _Const.OBJECT_KINDS[key] == _Const.OBJECT_CATEGORY_DECOR:
					made.append({FIELD_KEY: key,
						FIELD_SCENERY: _Const.OBJECT_KIND_SCENERY.get(key, "")})

	return made
