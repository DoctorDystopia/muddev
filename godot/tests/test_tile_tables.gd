extends Node
## Tests for the tables of the Tables tab (10/14/2026): [TileTables],
## [TableEdits], [SourceTable], the key moves of [LookFile], and the form of
## the tab.
##
##     godot --headless --path godot res://tests/test_tile_tables.tscn
##
## Needs nothing running. Every write goes to a scratch directory under
## `user://`: copies of the table files, of the look files, and of the
## fallback tables, one chunk file, and the template fixture of the Python
## test. No file of the repository changes. The cases:
##
## 1. The constants give the tables as the export wrote them, and the table
##    files of the repository give the same keys: the export is current.
## 2. Each table name is an exported table, and each exported field has an
##    empty value.
## 3. A new row needs a legal new key and a word in each text. A save keeps
##    the key.
## 4. A rename reaches the chunk file, the template, the look file, the
##    fallback table, and the default of a new chunk.
## 5. A removal refuses a fixed key, the first row, the last roof, and a key
##    in use, unsaved chunks included. It takes the look rows out.
## 6. A decor kind of the table is an object kind with its scenery at once.
## 7. [SourceTable] renames and erases a row of one line and of many lines.
## 8. The form of the Tables tab gives a row with the fields of its table.

const _Const := preload("res://autoload/blackout_constants.gd")
const _TablesPanel := preload("res://addons/blackout_terrain/tables_panel.gd")

## The template fixture of `world/tests/test_structure_templates.py`.
const TEMPLATE_FIXTURE := "world/tests/fixtures/structures/fixture_stall.json"

## The fallback tables that the scratch directory copies.
const SOURCES := ["res://world/area_look.gd", "res://world/terrain/floor_palette.gd",
	"res://world/terrain/wall_palette.gd"]

var _failures := 0
var _root := ""


func _ready() -> void:
	_the_constants_match_the_files()
	_the_tables_are_exported()
	_source_table_moves_rows()
	_look_file_moves_keys()
	_make_scratch()
	_a_new_row_follows_the_rules()
	_a_rename_reaches_every_file()
	_a_removal_refuses_what_it_must()
	_a_decor_row_is_an_object_kind()
	_the_form_gives_a_row()
	_drop_scratch()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: tile_tables")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("FAIL: " + what)


# ─── 1 and 2: the sources ───────────────────────────────────────────────────

func _the_constants_match_the_files() -> void:
	TileTables.use_constants()
	_expect(Array(TileTables.keys(TileTables.AREAS)) == Array(_Const.TILE_AREAS),
		"the constants give the areas")
	_expect(TileTables.default_area() == _Const.TILE_DEFAULT_AREA, "the default area")
	_expect(TileTables.default_floor() == _Const.TILE_DEFAULT_FLOOR, "the default floor")
	_expect(Array(TileTables.roof_floor_types()) == Array(_Const.TILE_ROOF_FLOOR_TYPES),
		"the constants give the roofs")
	_expect(TileTables.object_kinds().keys() == _Const.OBJECT_KINDS.keys(),
		"the object kinds keep the order of the server")

	for kind: String in _Const.OBJECT_KINDS:
		_expect(TileTables.scenery_of(kind) == _Const.OBJECT_KIND_SCENERY.get(kind, ""),
			"the scenery of %s" % kind)

	var from_constants := {}

	for table: String in _Const.TILE_TABLE_FIELDS:
		from_constants[table] = TileTables.keys(table)

	TileTables.use_files()

	for table: String in _Const.TILE_TABLE_FIELDS:
		_expect(TileTables.keys(table) == from_constants[table],
			"the file of %s gives the keys of the export: run the export" % table)

	_expect(TileTables.errors().is_empty(), "every table file of the repo reads")
	TileTables.use_auto()


func _the_tables_are_exported() -> void:
	for table: String in [TileTables.AREAS, TileTables.FLOOR_TYPES, TileTables.WALL_STYLES,
			TileTables.DECOR_KINDS]:
		_expect(_Const.TILE_TABLE_FIELDS.has(table), "%s is an exported table" % table)

	for table: String in _Const.TILE_TABLE_FIELDS:
		for field: String in _Const.TILE_TABLE_FIELDS[table]:
			_expect(TableEdits.FIELD_DEFAULTS.has(field), "the field %s has an empty value"
				% field)

	_expect(FileAccess.file_exists(FigurePipeline.game_directory().path_join(
		ClientExport.SCRIPT)), "the export script is in the game directory")


# ─── The scratch directory ──────────────────────────────────────────────────

func _make_scratch() -> void:
	_root = ProjectSettings.globalize_path("user://tile_tables_test_%d" % Time.get_ticks_usec())

	for part: String in ["tables", "chunks", "structures", "look", "source"]:
		DirAccess.make_dir_recursive_absolute(_root.path_join(part))

	for table: String in _Const.TILE_TABLE_FIELDS:
		_copy(TileTables.file_path(table), _root.path_join("tables").path_join(
			TileTables.file_path(table).get_file()))

	for path: String in [AreaLook.PATH, TerrainPalette.PATH] + SOURCES:
		_copy(path, _scratch_of(path))

	var game := FigurePipeline.game_directory()

	_copy(game.path_join(TEMPLATE_FIXTURE), _root.path_join("structures/fixture_stall.json"))
	TileTables.use_files(_root.path_join("tables"))
	_write_chunk()


## The scratch copy of a look file or a fallback table.
func _scratch_of(path: String) -> String:
	var part := "look" if path.ends_with(".json") else "source"

	return _root.path_join(part).path_join(path.get_file())


## One chunk on the default floor and area, with a crate on it.
func _write_chunk() -> void:
	var chunk := ChunkFile.blank(0, 0)

	chunk.objects.append({"kind": "crate", "x": 1, "y": 1, "rotation": 0, "text": ""})
	chunk.write_file(_root.path_join("chunks").path_join(chunk.file_name()))


func _edits() -> TableEdits:
	var edits := TableEdits.new()

	edits.chunk_directories = PackedStringArray([_root.path_join("chunks")])
	edits.template_directories = PackedStringArray([_root.path_join("structures")])
	edits.look_files = {
		TileTables.AREAS: [[_scratch_of(AreaLook.PATH), AreaLook.KEY_AREAS]],
		TileTables.FLOOR_TYPES: [[_scratch_of(TerrainPalette.PATH), TerrainPalette.KEY_FLOORS]],
	}
	edits.source_tables = {
		TileTables.AREAS: [[_scratch_of(SOURCES[0]), "LOOKS"]],
		TileTables.FLOOR_TYPES: [[_scratch_of(SOURCES[1]), "COLORS"]],
	}

	return edits


func _drop_scratch() -> void:
	for part: String in ["tables", "chunks", "structures", "look", "source"]:
		var directory := _root.path_join(part)

		for file_name: String in DirAccess.get_files_at(directory):
			DirAccess.remove_absolute(directory.path_join(file_name))

		DirAccess.remove_absolute(directory)

	DirAccess.remove_absolute(_root)
	LookFile.forget(_scratch_of(AreaLook.PATH))
	LookFile.forget(_scratch_of(TerrainPalette.PATH))
	TileTables.use_auto()


static func _copy(from: String, to: String) -> void:
	var file := FileAccess.open(to, FileAccess.WRITE)

	file.store_string(FileAccess.get_file_as_string(from))
	file.close()


static func _area_row(key: String) -> Dictionary:
	return {"key": key, "note": "A test area.", "name": "Test", "desc": "Dust."}


# ─── 3: new and save ────────────────────────────────────────────────────────

func _a_new_row_follows_the_rules() -> void:
	var edits := _edits()
	var first := TileTables.default_area()

	_expect(not edits.add(TileTables.AREAS, _area_row("Bad Key")).is_empty(),
		"a key with a space and a capital is refused")
	_expect(not edits.add(TileTables.AREAS, _area_row(first)).is_empty(),
		"a key of the table is refused")
	_expect(not edits.add(TileTables.AREAS, _area_row("x\n")).is_empty(),
		"a key with a last line feed is refused")

	var empty := _area_row("empty_name")

	empty["name"] = "  "
	_expect(not edits.add(TileTables.AREAS, empty).is_empty(), "an empty text is refused")
	_expect(edits.add(TileTables.AREAS, _area_row("test_area")).is_empty(), "a new area adds")
	_expect(TileTables.keys(TileTables.AREAS)[-1] == "test_area", "a new row goes last")

	var changed := _area_row("test_area")

	changed["note"] = "A new note."
	_expect(edits.save(TileTables.AREAS, "test_area", changed).is_empty(), "a save writes")
	_expect(TileTables.row(TileTables.AREAS, "test_area")["note"] == "A new note.",
		"the saved note reads back")
	_expect(not edits.save(TileTables.AREAS, first, changed).is_empty(),
		"a save with another key is refused")
	_expect(not edits.save(TileTables.AREAS, "no_such_area", _area_row("no_such_area"))
		.is_empty(), "a save of a key that the table lacks is refused")


# ─── 4: rename ──────────────────────────────────────────────────────────────

func _a_rename_reaches_every_file() -> void:
	var edits := _edits()
	var old := TileTables.default_area()
	var result := edits.rename(TileTables.AREAS, old, "renamed_area")
	var chunk := ChunkFile.read_file(_root.path_join("chunks/chunk_0_0_p0.json"))
	var template := StructureTemplate.read_file(_root.path_join("structures/fixture_stall.json"))
	var looks: Dictionary = LookFile.read(_scratch_of(AreaLook.PATH))[AreaLook.KEY_AREAS]
	var source := FileAccess.get_file_as_string(_scratch_of(SOURCES[0]))

	_expect(result["problem"].is_empty(), "the rename succeeds: %s" % result["problem"])
	_expect("renamed_area" in chunk.area_names and not old in chunk.area_names,
		"the chunk file names the new key")
	_expect("renamed_area" in template.area_names, "the template names the new key")
	_expect(looks.has("renamed_area") and not looks.has(old), "the look row moves")
	_expect(SourceTable.has_key(source, "LOOKS", "renamed_area")
		and not SourceTable.has_key(source, "LOOKS", old), "the fallback row moves")
	_expect(TileTables.default_area() == "renamed_area", "the default follows the rename")
	_expect(ChunkFile.blank(5, 5).area_names[0] == "renamed_area",
		"a new chunk takes the renamed default")
	_expect(not TableEdits.rename_problem(TileTables.FLOOR_TYPES,
		_Const.TILE_VOID_FLOOR, "nothing").is_empty(), "the void floor keeps its key")
	_expect(not TableEdits.rename_problem(TileTables.WALL_STYLES,
		_Const.TILE_DEFAULT_WALL_STYLE, "other").is_empty(), "the plain style keeps its key")


# ─── 5: remove ──────────────────────────────────────────────────────────────

func _a_removal_refuses_what_it_must() -> void:
	var edits := _edits()

	_expect(not edits.remove_problem(TileTables.AREAS, TileTables.default_area()).is_empty(),
		"the first row stays")
	_expect(not edits.remove_problem(TileTables.DECOR_KINDS, "table").is_empty(),
		"a decor kind of a template stays")
	edits.add(TileTables.AREAS, _area_row("open_area"))

	var unsaved := ChunkFile.blank(9, 9)

	unsaved.area_names = PackedStringArray(["open_area"])
	_expect(not edits.remove_problem(TileTables.AREAS, "open_area", [unsaved]).is_empty(),
		"an unsaved chunk keeps its area")
	_expect(edits.remove(TileTables.AREAS, "open_area")["problem"].is_empty(),
		"an unused area goes")
	_expect(not TileTables.has_key(TileTables.AREAS, "open_area"), "the row is gone")
	_a_removal_takes_the_look_rows()
	_the_last_roof_stays(edits)


func _a_removal_takes_the_look_rows() -> void:
	var edits := _edits()
	var spare: String = TileTables.keys(TileTables.AREAS)[-2]
	var source := FileAccess.get_file_as_string(_scratch_of(SOURCES[0]))
	var had_row := SourceTable.has_key(source, "LOOKS", spare)

	_expect(edits.remove(TileTables.AREAS, spare)["problem"].is_empty(),
		"the area %s goes" % spare)

	source = FileAccess.get_file_as_string(_scratch_of(SOURCES[0]))
	_expect(not SourceTable.has_key(source, "LOOKS", spare), "its fallback row goes")
	_expect(not LookFile.read(_scratch_of(AreaLook.PATH))[AreaLook.KEY_AREAS].has(spare),
		"its look row goes")

	if not had_row:
		print("NOTE: the area %s had no fallback row to take out." % spare)


func _the_last_roof_stays(edits: TableEdits) -> void:
	var roofs := TileTables.roof_floor_types()

	for index: int in range(1, roofs.size()):
		_expect(edits.remove(TileTables.FLOOR_TYPES, roofs[index])["problem"].is_empty(),
			"the roof %s goes" % roofs[index])

	var last := roofs[0]
	var row := TileTables.row(TileTables.FLOOR_TYPES, last)

	row["roof"] = false
	_expect(not edits.remove_problem(TileTables.FLOOR_TYPES, last).is_empty(),
		"the last roof stays")
	_expect(not edits.save(TileTables.FLOOR_TYPES, last, row).is_empty(),
		"the last roof keeps its roof flag")


# ─── 6: decor ───────────────────────────────────────────────────────────────

func _a_decor_row_is_an_object_kind() -> void:
	var edits := _edits()
	var barrel := {"key": "barrel", "note": "A rusty barrel.", "scenery": "crate"}

	_expect(not edits.add(TileTables.DECOR_KINDS, {"key": "signpost", "note": "A sign.",
		"scenery": "crate"}).is_empty(), "a decor key of another object kind is refused")
	_expect(not edits.add(TileTables.DECOR_KINDS, {"key": "odd", "note": "Odd.",
		"scenery": "no_such_model"}).is_empty(), "a scenery that nothing draws is refused")
	_expect(edits.add(TileTables.DECOR_KINDS, barrel).is_empty(), "a new decor kind adds")
	_expect(TileTables.object_category("barrel") == _Const.OBJECT_CATEGORY_DECOR,
		"the new decor is an object kind")
	_expect(StructureTools.is_decor("barrel"), "the Decor tool takes it")
	_expect(TileTables.scenery_of("barrel") == "crate", "it draws its scenery")
	_expect(edits.rename(TileTables.DECOR_KINDS, "crate", "wooden_crate")["problem"].is_empty(),
		"a decor kind renames")

	var chunk := ChunkFile.read_file(_root.path_join("chunks/chunk_0_0_p0.json"))
	var template := StructureTemplate.read_file(_root.path_join("structures/fixture_stall.json"))

	_expect(TableEdits.names_key(chunk, TileTables.DECOR_KINDS, "wooden_crate"),
		"the chunk object takes the new kind")
	_expect(TableEdits.names_key(template, TileTables.DECOR_KINDS, "wooden_crate"),
		"the template object takes the new kind")


# ─── 7: the fallback tables ─────────────────────────────────────────────────

const _SOURCE_TEXT := "const OTHER := {\n\t\"a\": 1,\n}\n\nconst ROWS := {\n" \
	+ "\t\"one\": Color(\"112233\"),\n\t# The second row.\n\t\"two\": {\n\t\t\"x\": 1,\n" \
	+ "\t},\n\t\"three\": 3,\n}\n"


func _source_table_moves_rows() -> void:
	var renamed := SourceTable.rename_key(_SOURCE_TEXT, "ROWS", "one", "uno")

	_expect(SourceTable.has_key(renamed, "ROWS", "uno"), "a one line row renames")
	_expect(not SourceTable.has_key(renamed, "ROWS", "one"), "the old key goes")
	_expect(SourceTable.rename_key(_SOURCE_TEXT, "ROWS", "a", "b") == _SOURCE_TEXT,
		"a key of another table stays")

	var erased := SourceTable.erase_key(_SOURCE_TEXT, "ROWS", "two")

	_expect(not SourceTable.has_key(erased, "ROWS", "two"), "a row of many lines goes")
	_expect(not "second row" in erased, "its comment goes with it")
	_expect(SourceTable.has_key(erased, "ROWS", "three") and SourceTable.has_key(erased,
		"ROWS", "one"), "the other rows stay")
	_expect(erased.count("\n") == _SOURCE_TEXT.count("\n") - 4, "four lines go")


func _look_file_moves_keys() -> void:
	var path := "user://tile_tables_look_%d.json" % Time.get_ticks_usec()

	LookFile.write(path, {"format": 1, "areas": {"old": {"fog_end": 9.0}}})
	_expect(LookFile.rename_key(path, "areas", "old", "new"), "a look row moves")
	LookFile.forget(path)
	_expect(LookFile.read(path)["areas"].has("new"), "the move is in the file")
	_expect(not LookFile.rename_key(path, "areas", "missing", "x"), "no row, no change")
	_expect(LookFile.erase_key(path, "areas", "new"), "a look row goes")
	_expect(LookFile.read(path)["areas"].is_empty(), "the file has no row")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	LookFile.forget(path)


# ─── 8: the form ────────────────────────────────────────────────────────────

func _the_form_gives_a_row() -> void:
	var panel := _TablesPanel.new()

	add_child(panel)
	panel.start_new_row(TileTables.FLOOR_TYPES)
	_expect(panel.table() == TileTables.FLOOR_TYPES, "New opens the floor types")
	_expect(panel.form_row().keys() == TableEdits.fields_of(TileTables.FLOOR_TYPES),
		"the form gives the fields of a floor type")
	_expect(panel.form_row()["roof"] is bool, "the roof field is a flag")
	panel.refresh({}, TileTables.default_floor())
	_expect(panel.selected_key() == TileTables.default_floor(), "a refresh selects a key")
	_expect(panel.form_row()["key"] == TileTables.default_floor(), "the form shows the row")
	panel.queue_free()
