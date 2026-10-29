@tool
class_name TableEdits
extends RefCounted
## The rules of the Tables tab (Nick, 10/14/2026): add a row, save the
## fields of a row, rename a key, and remove a row, in the four table files
## of [TileTables]. The panel only asks. The plugin confirms, and then
## calls here.
##
## ## A rename reaches each file that names the key
##
## 1. Each chunk file of the world, and of the structure workbench.
## 2. Each template of `blackout/world/structures/`, and the template
##    fixture of the tests ([constant TEMPLATE_FIXTURES]).
## 3. The look file rows of the key: the area look, the floor colour, and
##    the wall colour and height.
## 4. The fallback table rows of the client ([SourceTable]).
## 5. The table file, last.
##
## The plugin saves the open block first, and reads it again after. The
## check fixture of the tests reads its names from the tables, and
## [ClientExport] builds it again after each change.
##
## ## A removal refuses a key in use
##
## A chunk file, an unsaved chunk, or a template that names the key keeps
## it. The look rows and the fallback rows of a removed key go with it, so
## no client key names nothing.
##
## ## Fixed keys
##
## [method protect_problem] owns them:
##
## - The first row of the areas, the floor types, and the wall styles is
##   the default of a new chunk. A rename is legal, a removal is not.
## - The void floor and the plain wall style are constants of the client
##   and of the chunk file format. Neither a rename nor a removal is legal.
## - The last roof floor type stays a roof: the Roof tool needs one.
##
## The server reads a table at start. Thus, a new row reaches the game after
## a restart of the server. The plugin runs the client export after each
## change ([ClientExport]).

const _Const := preload("res://autoload/blackout_constants.gd")

const ACTION_RENAME := "rename"
const ACTION_REMOVE := "remove"

## The value of each field of an empty row. Its type is the type of the
## field. `test_tile_tables.gd` checks that it covers each exported field.
const FIELD_DEFAULTS := {
	"key": "",
	"note": "",
	"name": "",
	"desc": "",
	"roof": false,
	"scenery": "",
}

## The name list of a chunk file and of a template for each table. The
## decor kinds are in the objects.
const NAME_LISTS := {
	TileTables.AREAS: "area_names",
	TileTables.FLOOR_TYPES: "floor_names",
	TileTables.WALL_STYLES: "wall_names",
}

## The served model manifest, under [method TerrainModels.repo_origin].
const MANIFEST := "static/webclient/models/manifest.json"

## The template fixture of `world/tests/test_structure_templates.py`, from
## the game directory. That test checks its names against the tables, so a
## rename reaches it as it reaches a template of the world.
const TEMPLATE_FIXTURES := "world/tests/fixtures/structures"

## The directories whose chunk files a rename and a removal read.
var chunk_directories := PackedStringArray()

## The shelves whose versions a rename and a removal read (10/28/2026).
## Each directory of a shelf holds the chunk files of one version. A
## version names the rows of today, so a rename reaches it, and a removal
## refuses a row that it names. Thus, a switch to it never brings a stale
## name back.
var version_shelves := PackedStringArray()

## The directories whose templates a rename and a removal read.
var template_directories := PackedStringArray()

## Table to `[[look file path, section], ...]`.
var look_files := {}

## Table to `[[GDScript path, table name], ...]`.
var source_tables := {}


func _init() -> void:
	chunk_directories = PackedStringArray([ChunkFile.world_directory(),
		ProjectSettings.globalize_path(TerrainWorld.WORKBENCH_DIRECTORY)])
	template_directories = PackedStringArray([StructureTemplate.world_directory(),
		_game_directory().path_join(TEMPLATE_FIXTURES)])
	version_shelves = PackedStringArray([WorldVersions.world_shelf()])
	look_files = {
		TileTables.AREAS: [[AreaLook.PATH, AreaLook.KEY_AREAS]],
		TileTables.FLOOR_TYPES: [[TerrainPalette.PATH, TerrainPalette.KEY_FLOORS]],
		TileTables.WALL_STYLES: [[TerrainPalette.PATH, TerrainPalette.KEY_WALLS]],
	}
	source_tables = {
		TileTables.AREAS: [["res://world/area_look.gd", "LOOKS"]],
		TileTables.FLOOR_TYPES: [["res://world/terrain/floor_palette.gd", "COLORS"]],
		TileTables.WALL_STYLES: [["res://world/terrain/wall_palette.gd", "COLORS"],
			["res://world/terrain/wall_palette.gd", "HEIGHTS"]],
	}


# ─── The checks ─────────────────────────────────────────────────────────────

## The fields of a row of `table`, in the order of the server row class.
static func fields_of(table: String) -> Array:
	return _Const.TILE_TABLE_FIELDS.get(table, [])


## An empty row of `table`.
static func empty_row(table: String) -> Dictionary:
	var made := {}

	for field: String in fields_of(table):
		made[field] = FIELD_DEFAULTS.get(field, "")

	return made


## The problem of a new key of `table`, or "".
static func key_problem(table: String, key: String) -> String:
	if key.is_empty():
		return "Type a key."

	var found := RegEx.create_from_string(_Const.CHUNK_NAME_PATTERN).search(key)

	# A whole match: `$` also matches before a last line feed.
	if found == null or found.get_string() != key:
		return "A key holds only a-z, 0-9, and _: %s does not." % key

	if TileTables.has_key(table, key):
		return "The table has the key %s already." % key

	if table == TileTables.DECOR_KINDS and TileTables.object_kinds().has(key):
		return "The object kind %s is there already." % key

	return ""


## The problem of the fields of `row`, or "". Each field of the table must
## be there with its type, and each text must hold a word.
static func row_problem(table: String, row: Dictionary) -> String:
	for field: String in fields_of(table):
		var wanted: Variant = FIELD_DEFAULTS.get(field, "")

		if not row.has(field) or typeof(row[field]) != typeof(wanted):
			return "The field %s is missing." % field

		if row[field] is String and row[field].strip_edges().is_empty():
			return "Fill the field %s." % field

	for field: String in row:
		if not field in fields_of(table):
			return "A row of %s has no field %s." % [table, field]

	if row.has(TileTables.FIELD_SCENERY) and not row[TileTables.FIELD_SCENERY] \
			in scenery_choices():
		return "No primitive and no model has the key %s." % row[TileTables.FIELD_SCENERY]

	return ""


## The problem of a rename or a removal of `key`, or "". See "Fixed keys".
static func protect_problem(table: String, key: String, action: String) -> String:
	var keys := TileTables.keys(table)

	if not key in keys:
		return "The table has no key %s." % key

	if table == TileTables.FLOOR_TYPES and key == _Const.TILE_VOID_FLOOR:
		return "%s is a fixed key: the client and the editor name it." % key

	if table == TileTables.WALL_STYLES and key == _Const.TILE_DEFAULT_WALL_STYLE:
		return "%s is a fixed key: the style of each chunk file of format 1." % key

	if action != ACTION_REMOVE:
		return ""

	if table != TileTables.DECOR_KINDS and keys[0] == key:
		return "%s is the first row: the default of a new chunk. Rename it." % key

	if _is_last_roof(table, key):
		return "%s is the last roof floor type. The Roof tool needs one." % key

	return ""


## Every scenery key that a decor kind may name: the primitives, then each
## model of the served manifest.
static func scenery_choices() -> Array:
	var choices: Array = _Const.SCENERY_PRIMITIVES.duplicate()
	var path := TerrainModels.repo_origin().path_join(MANIFEST)

	if FileAccess.file_exists(path):
		var models: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))

		if models is Dictionary:
			var keys: Array = models.keys()

			keys.sort()
			choices.append_array(keys)

	return choices


static func _is_last_roof(table: String, key: String) -> bool:
	if table != TileTables.FLOOR_TYPES or not TileTables.is_roof(key):
		return false

	return TileTables.roof_floor_types().size() == 1


# ─── Add and save ───────────────────────────────────────────────────────────

## Add `row` at the end of `table`. Returns the problem, or "".
func add(table: String, row: Dictionary) -> String:
	var problem := key_problem(table, row.get(TileTables.FIELD_KEY, ""))

	if problem.is_empty():
		problem = row_problem(table, row)

	if not problem.is_empty():
		return problem

	var rows := TileTables.rows(table)

	rows.append(row.duplicate())

	return _write(table, rows)


## Give the row `key` of `table` the fields of `row`. The key stays: a new
## key is a rename. Returns the problem, or "".
func save(table: String, key: String, row: Dictionary) -> String:
	var problem := row_problem(table, row)

	if not TileTables.has_key(table, key):
		problem = "The table has no key %s." % key

	if problem.is_empty() and row[TileTables.FIELD_KEY] != key:
		problem = "The key changed. Use Rename row for a new key."

	if problem.is_empty() and _is_last_roof(table, key) \
			and not row.get(TileTables.FIELD_ROOF, true):
		problem = "%s is the last roof floor type. The Roof tool needs one." % key

	if not problem.is_empty():
		return problem

	var rows := TileTables.rows(table)

	for index: int in rows.size():
		if rows[index][TileTables.FIELD_KEY] == key:
			rows[index] = row.duplicate()

	return _write(table, rows)


func _write(table: String, rows: Array[Dictionary]) -> String:
	var error := TileTables.write_rows(table, rows)

	if error != OK:
		return "Could not write %s: %s." % [TileTables.file_path(table), error_string(error)]

	return ""


# ─── Uses ───────────────────────────────────────────────────────────────────

## The files that name `key` of `table`: `{chunks, templates}`, each a list
## of paths from the game directory. `extra` holds the chunks of the open
## block, unsaved edits included.
func uses(table: String, key: String, extra: Array[ChunkFile] = []) -> Dictionary:
	var chunks := {}
	var templates := PackedStringArray()

	for path: String in _all_chunk_paths():
		var chunk := ChunkFile.read_file(path)

		if chunk.error.is_empty() and names_key(chunk, table, key):
			chunks[_label(path)] = true

	for chunk: ChunkFile in extra:
		if names_key(chunk, table, key):
			chunks["%s (open block)" % chunk.file_name()] = true

	for path: String in _template_paths():
		var template := StructureTemplate.read_file(path)

		if template.error.is_empty() and names_key(template, table, key):
			templates.append(_label(path))

	return {"chunks": PackedStringArray(chunks.keys()), "templates": templates}


## True when `holder`, a [ChunkFile] or a [StructureTemplate], names `key`
## of `table`.
static func names_key(holder: Object, table: String, key: String) -> bool:
	if NAME_LISTS.has(table):
		return key in holder.get(NAME_LISTS[table])

	for thing: Dictionary in holder.get("objects"):
		if thing["kind"] == key:
			return true

	return false


## Each chunk file of [member chunk_directories], and of each version of
## [member version_shelves].
func _all_chunk_paths() -> PackedStringArray:
	var paths := PackedStringArray()
	var directories := Array(chunk_directories)

	for shelf: String in version_shelves:
		if DirAccess.dir_exists_absolute(shelf):
			for key: String in DirAccess.get_directories_at(shelf):
				directories.append(shelf.path_join(key))

	for directory: String in directories:
		if not DirAccess.dir_exists_absolute(directory):
			continue

		for file_name: String in DirAccess.get_files_at(directory):
			if ChunkFile.is_chunk_file_name(file_name):
				paths.append(directory.path_join(file_name))

	return paths


## Each template file of [member template_directories].
func _template_paths() -> PackedStringArray:
	var paths := PackedStringArray()

	for directory: String in template_directories:
		for template_key: String in StructureTemplate.list_keys(directory):
			paths.append(StructureTemplate.path_for(directory, template_key))

	return paths


## The game directory of this repo, as an OS path.
static func _game_directory() -> String:
	var project := ProjectSettings.globalize_path("res://")

	return project.path_join(ChunkFile.GAME_DIRECTORY_FROM_PROJECT).simplify_path()


## `path` from the game directory, or its directory and file name outside
## it. The directory keeps two files of one name apart: a chunk of the
## workbench and a chunk of a version.
static func _label(path: String) -> String:
	var game := _game_directory() + "/"

	if path.begins_with(game):
		return path.trim_prefix(game)

	return path.get_base_dir().get_file().path_join(path.get_file())


# ─── Rename ─────────────────────────────────────────────────────────────────

## The problem of a rename, or "".
static func rename_problem(table: String, old: String, new: String) -> String:
	var problem := protect_problem(table, old, ACTION_RENAME)

	if problem.is_empty():
		problem = key_problem(table, new)

	return problem


## Rename `old` of `table` to `new` in each file of "A rename reaches each
## file that names the key". Returns `{problem, lines}`: the lines say
## what changed and what did not write.
func rename(table: String, old: String, new: String) -> Dictionary:
	var problem := rename_problem(table, old, new)

	if not problem.is_empty():
		return {"problem": problem, "lines": PackedStringArray()}

	var lines := PackedStringArray()

	lines.append(_rename_chunks(table, old, new))
	lines.append(_rename_templates(table, old, new))
	lines.append(_follow_looks(table, old, new))

	var rows := TileTables.rows(table)

	for row: Dictionary in rows:
		if row[TileTables.FIELD_KEY] == old:
			row[TileTables.FIELD_KEY] = new

	problem = _write(table, rows)

	return {"problem": problem, "lines": lines}


func _rename_chunks(table: String, old: String, new: String) -> String:
	var written := 0
	var failed := PackedStringArray()

	for path: String in _all_chunk_paths():
		var chunk := ChunkFile.read_file(path)

		if not chunk.error.is_empty() or not names_key(chunk, table, old):
			continue

		rename_in(chunk, table, old, new)

		if chunk.write_file(path) == OK:
			written += 1
		else:
			failed.append(_label(path))

	return _report("chunk file", written, failed)


func _rename_templates(table: String, old: String, new: String) -> String:
	var written := 0
	var failed := PackedStringArray()

	for path: String in _template_paths():
		var template := StructureTemplate.read_file(path)

		if not template.error.is_empty() or not names_key(template, table, old):
			continue

		rename_in(template, table, old, new)

		if template.write_file(path) == OK:
			written += 1
		else:
			failed.append(_label(path))

	return _report("template", written, failed)


## Rename `old` to `new` in `holder`, a [ChunkFile] or a [StructureTemplate].
static func rename_in(holder: Object, table: String, old: String, new: String) -> void:
	if NAME_LISTS.has(table):
		var names: PackedStringArray = holder.get(NAME_LISTS[table])

		names[names.find(old)] = new
		holder.set(NAME_LISTS[table], names)
		return

	for thing: Dictionary in holder.get("objects"):
		if thing["kind"] == old:
			thing["kind"] = new


## Rename the look rows and the fallback rows of `old`. With `new` empty,
## take them out.
func _follow_looks(table: String, old: String, new: String) -> String:
	var changed := PackedStringArray()

	for pair: Array in look_files.get(table, []):
		var moved := LookFile.erase_key(pair[0], pair[1], old) if new.is_empty() \
			else LookFile.rename_key(pair[0], pair[1], old, new)

		if moved:
			changed.append(pair[0].get_file())

	for pair: Array in source_tables.get(table, []):
		var moved := SourceTable.erase_in_file(pair[0], pair[1], old) if new.is_empty() \
			else SourceTable.rename_in_file(pair[0], pair[1], old, new)

		if moved:
			changed.append("%s %s" % [pair[0].get_file(), pair[1]])

	if changed.is_empty():
		return "No look row named %s." % old

	return "Look rows: %s." % ", ".join(changed)


static func _report(what: String, written: int, failed: PackedStringArray) -> String:
	var line := "Wrote %d %s(s)." % [written, what]

	if not failed.is_empty():
		line += " COULD NOT WRITE: %s." % ", ".join(failed)

	return line


# ─── Remove ─────────────────────────────────────────────────────────────────

## The problem of a removal, or "". `extra` holds the chunks of the open
## block.
func remove_problem(table: String, key: String, extra: Array[ChunkFile] = []) -> String:
	var problem := protect_problem(table, key, ACTION_REMOVE)

	if not problem.is_empty():
		return problem

	var found := uses(table, key, extra)
	var names: PackedStringArray = found["chunks"] + found["templates"]

	if names.is_empty():
		return ""

	return "%s is in use. Paint it out first: %s." % [key, ", ".join(names)]


## Take `key` out of `table`, with its look rows. Returns `{problem, lines}`.
func remove(table: String, key: String, extra: Array[ChunkFile] = []) -> Dictionary:
	var problem := remove_problem(table, key, extra)

	if not problem.is_empty():
		return {"problem": problem, "lines": PackedStringArray()}

	var lines := PackedStringArray([_follow_looks(table, key, "")])
	var kept: Array[Dictionary] = []

	for row: Dictionary in TileTables.rows(table):
		if row[TileTables.FIELD_KEY] != key:
			kept.append(row)

	return {"problem": _write(table, kept), "lines": lines}
