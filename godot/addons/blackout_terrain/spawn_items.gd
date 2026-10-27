@tool
class_name SpawnItems
extends RefCounted
## The item list of the terrain editor: each item that an item spawn may
## name (10/21/2026).
##
## The server owns each fact here. `export_client_constants.py` renders
## `spawn_items.json` from `ITEM_DB`, and a Python test fails when the file
## is stale. This class only reads the file. Never edit the file by hand.
##
## ## The file
##
##     format  1
##     items   [{key, name, family, stackable}, ...], sorted by key
##
## The editor reads it three ways: the Item field of the Object tool and of
## the Objects tab, the model of an item spawn on its tile (the item key and
## its family, as the client draws an item on the ground), and "Check world"
## ([method stacking]). The parity fixture of the checks has a short file of
## the same layout, so the test reads it with this class too.

const _Const := preload("res://autoload/blackout_constants.gd")

## The newest format that this reader knows.
const FORMAT := 1

const ITEMS_PATH := "res://addons/blackout_terrain/spawn_items.json"

## Why the list does not read, or "" for a list that reads.
var error := ""

## Item key -> its row.
var _rows := {}

## The item keys, sorted.
var _keys := PackedStringArray()

## The list of the game, read one time ([method game]).
static var _game: SpawnItems = null


# ─── Reading ────────────────────────────────────────────────────────────────

## The list of a parsed item list file. Check [member error] after.
static func from_data(parsed: Variant) -> SpawnItems:
	var items := SpawnItems.new()

	if typeof(parsed) != TYPE_DICTIONARY or not parsed.has("items"):
		items.error = "the item list is not a table with items"
		return items

	if int(parsed.get("format", 0)) > FORMAT:
		items.error = "the item list has format %s, newer than %d" % [
			str(parsed.get("format")), FORMAT]
		return items

	for row: Variant in parsed["items"]:
		if typeof(row) != TYPE_DICTIONARY or not row.has("key"):
			items.error = "a row of the item list has no key"
			return items

		items._rows[str(row["key"])] = row

	items._keys = PackedStringArray(items._rows.keys())
	items._keys.sort()

	return items


## The list in a file at `path`, a res:// path or an OS path.
static func from_file(path: String) -> SpawnItems:
	if not FileAccess.file_exists(path):
		var missing := SpawnItems.new()

		missing.error = "%s is not there. Run export_client_constants.py" % path
		return missing

	return from_data(JSON.parse_string(FileAccess.get_file_as_string(path)))


## The list of the game, from [constant ITEMS_PATH]. Read one time. Call
## [method forget] after the export writes the file again.
static func game() -> SpawnItems:
	if _game == null:
		_game = from_file(ITEMS_PATH)

	return _game


## Forget the list of the game, so the next [method game] reads the file.
## Not `reload`: on the class, that name calls the reload of the script.
static func forget() -> void:
	_game = null


# ─── Facts ──────────────────────────────────────────────────────────────────

## Each item key, sorted.
func keys() -> PackedStringArray:
	return _keys


## True when an item spawn may name `key`.
func has(key: String) -> bool:
	return _rows.has(key)


## True when the item of `key` stacks. An unknown key does not.
func stacks(key: String) -> bool:
	return bool(_rows.get(key, {}).get("stackable", false))


## The family of the item of `key`: the family that the client draws an item
## on the ground with. An unknown key gives the generic family.
func family(key: String) -> String:
	return str(_rows.get(key, {}).get("family", _Const.ITEM_FAMILY_GENERIC))


## The name of the item of `key` for a person, or the key.
func name_of(key: String) -> String:
	return str(_rows.get(key, {}).get("name", key))


## Item key -> true when the item stacks: the `items` of
## [method TerrainChecks.check_world].
func stacking() -> Dictionary:
	var table := {}

	for key: String in _keys:
		table[key] = stacks(key)

	return table
