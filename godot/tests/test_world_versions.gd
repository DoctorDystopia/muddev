extends Node
## Tests for the world versions of the Versions tab (10/28/2026):
## [WorldVersions], and the form of the tab.
##
##     godot --headless --path godot res://tests/test_world_versions.tscn
##
## Needs nothing running. Every write goes to a scratch directory under
## `user://`: a world of two chunk files, and a shelf beside it. No file of
## the repository changes. The cases:
##
## 1. A key is a legal chunk file name. A note is one short line.
## 2. A save copies every chunk file, writes the meta file, and lists as
##    the current version. A second save of the key needs `overwrite`.
## 3. A switch restores each file, removes the file the version lacks, and
##    comes back to the same bytes. A switch to the current version changes
##    nothing.
## 4. A switch refuses to drop a world that no version holds, unless told.
## 5. A rename keeps the files and the note. A removal deletes the version
##    and leaves the world.
## 6. A directory copied by hand is a version with no note. A bad meta
##    file lists with its problem.
## 7. A rename of a table row reaches a version, and a removal refuses a
##    row that a version names ([TableEdits]).
## 8. The form of the Versions tab marks the current version and sends the
##    key of the field.

const _Const := preload("res://autoload/blackout_constants.gd")
const _VersionsPanel := preload("res://addons/blackout_terrain/versions_panel.gd")

var _failures := 0
var _root := ""
var _chunks := ""
var _shelf := ""


func _ready() -> void:
	_make_scratch()
	_a_key_and_a_note_follow_the_rules()
	_a_save_copies_the_world()
	_a_switch_restores_each_file()
	_a_switch_never_drops_an_unsaved_world()
	_a_rename_and_a_removal()
	_a_hand_made_version_and_a_bad_meta_file()
	_a_table_change_reaches_a_version()
	_the_form_marks_the_current_version()
	_drop_scratch()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: world_versions")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("FAIL: " + what)


# ─── The scratch world ──────────────────────────────────────────────────────

func _make_scratch() -> void:
	_root = ProjectSettings.globalize_path("user://world_versions_test_%d" % Time.get_ticks_usec())
	_chunks = _root.path_join("chunks")
	_shelf = _root.path_join("versions")
	DirAccess.make_dir_recursive_absolute(_chunks)
	_write_blank(0, 0)
	_write_blank(1, 0)


func _write_blank(cx: int, cy: int) -> void:
	ChunkFile.blank(cx, cy).write_file(_chunks.path_join(ChunkFile.blank(cx, cy).file_name()))


## Raise one corner of a chunk file of the world, so it differs.
func _raise_a_corner(file_name: String) -> void:
	var chunk := ChunkFile.read_file(_chunks.path_join(file_name))

	chunk.heights[0] += 1
	chunk.write_file(_chunks.path_join(file_name))


func _store() -> WorldVersions:
	return WorldVersions.new(_shelf, _chunks)


func _keys(store: WorldVersions) -> Array:
	var keys := []

	for row: Dictionary in store.list():
		keys.append(row["key"])

	return keys


func _drop_scratch() -> void:
	_remove_tree(_root)


static func _remove_tree(directory: String) -> void:
	if not DirAccess.dir_exists_absolute(directory):
		return

	for child: String in DirAccess.get_directories_at(directory):
		_remove_tree(directory.path_join(child))

	for file_name: String in DirAccess.get_files_at(directory):
		DirAccess.remove_absolute(directory.path_join(file_name))

	DirAccess.remove_absolute(directory)


# ─── 1: the rules ───────────────────────────────────────────────────────────

func _a_key_and_a_note_follow_the_rules() -> void:
	_expect(WorldVersions.key_problem("market_v2").is_empty(), "a legal key")

	for key: String in ["", "Market", "a-b", "a b", "../x"]:
		_expect(not WorldVersions.key_problem(key).is_empty(), "the key %s is refused" % key)

	_expect(WorldVersions.note_problem("").is_empty(), "an empty note")
	_expect(WorldVersions.note_problem("two gates").is_empty(), "a short note")
	_expect(not WorldVersions.note_problem("a\nb").is_empty(), "a note of two lines is refused")
	_expect(not WorldVersions.note_problem(
		"x".repeat(_Const.TILE_VERSION_NOTE_MAX_CHARS + 1)).is_empty(), "a long note is refused")


# ─── 2: a save ──────────────────────────────────────────────────────────────

func _a_save_copies_the_world() -> void:
	var store := _store()

	_expect(store.list().is_empty(), "an empty shelf lists nothing")
	_expect(store.current_key().is_empty(), "an empty shelf has no current version")

	var result := store.save("flat", "two chunks")

	_expect(result["problem"].is_empty() and result["count"] == 2, "a save copies two chunks")
	_expect(_keys(store) == ["flat"], "the shelf lists the version")

	var row: Dictionary = store.list()[0]

	_expect(row["note"] == "two chunks" and row["chunks"] == 2, "the row has the note and the count")
	_expect(not row["saved"].is_empty() and row["saved"].ends_with("Z"), "the row has a save time")
	_expect(WorldVersions.digests(store.path_of("flat")) == WorldVersions.digests(_chunks),
		"the version holds the bytes of the world")
	_expect(store.current_key() == "flat", "the saved version is the current one")
	_expect(not store.save("flat", "")["problem"].is_empty(), "a second save of the key is refused")
	_expect(not store.save("Bad Key", "")["problem"].is_empty(), "a bad key is refused")
	_write_blank(2, 0)
	_expect(store.save("flat", "", true)["count"] == 3, "an overwrite takes the third chunk")
	DirAccess.remove_absolute(_chunks.path_join("chunk_2_0_p0.json"))
	store.save("flat", "", true)
	_expect(not FileAccess.file_exists(store.path_of("flat").path_join("chunk_2_0_p0.json")),
		"an overwrite drops the file the world lost")


# ─── 3: a switch ────────────────────────────────────────────────────────────

func _a_switch_restores_each_file() -> void:
	var store := _store()

	_raise_a_corner("chunk_0_0_p0.json")
	_write_blank(2, 0)
	store.save("hill", "a corner up, a third chunk")

	var before := WorldVersions.digests(_chunks)
	var result := store.switch_to("flat")

	_expect(result["problem"].is_empty(), "a switch from a saved world needs no drop")
	_expect(result["changed"] == [["chunk_0_0_p0.json", TerrainSyncState.STATE_CHANGED],
		["chunk_2_0_p0.json", TerrainSyncState.STATE_NEW]],
		"the switch names the files it changed: %s" % [result["changed"]])
	_expect(Array(WorldVersions.chunk_names(_chunks)) == ["chunk_0_0_p0.json", "chunk_1_0_p0.json"],
		"the extra chunk is gone")
	_expect(store.current_key() == "flat", "the world is the version now")
	_expect(store.switch_to("flat")["changed"].is_empty(), "a switch to the current version changes nothing")
	store.switch_to("hill")
	_expect(WorldVersions.digests(_chunks) == before, "a cycle comes back to the same bytes")
	_expect(not store.switch_to("nowhere")["problem"].is_empty(), "a version that is not there")


# ─── 4: the drop rule ───────────────────────────────────────────────────────

func _a_switch_never_drops_an_unsaved_world() -> void:
	var store := _store()

	_raise_a_corner("chunk_1_0_p0.json")
	_expect(store.current_key().is_empty(), "the changed world is no version")

	var refused := store.switch_to("flat")

	_expect(not refused["problem"].is_empty(), "a switch refuses to drop the world")
	_expect(store.current_key().is_empty(), "the refusal changes nothing")
	_expect(store.switch_to("flat", true)["problem"].is_empty(), "a drop switches anyway")
	_expect(store.current_key() == "flat", "the world is flat after the drop")


# ─── 5: rename and remove ───────────────────────────────────────────────────

func _a_rename_and_a_removal() -> void:
	var store := _store()

	_expect(store.rename("flat", "plain").is_empty(), "a rename")
	_expect(_keys(store) == ["hill", "plain"], "the shelf lists the new key: %s" % [_keys(store)])
	_expect(store.current_key() == "plain", "the current version follows the rename")
	_expect(not store.rename("plain", "Plain").is_empty(), "a bad new key is refused")
	_expect(not store.rename("plain", "hill").is_empty(), "a taken key is refused")
	_expect(not store.rename("gone", "x").is_empty(), "a version that is not there")
	_expect(store.remove("hill").is_empty(), "a removal")
	_expect(_keys(store) == ["plain"], "the version is gone")
	_expect(WorldVersions.chunk_names(_chunks).size() == 2, "the world keeps its files")
	_expect(not store.remove("hill").is_empty(), "a second removal is refused")


# ─── 6: a hand-made version ─────────────────────────────────────────────────

func _a_hand_made_version_and_a_bad_meta_file() -> void:
	var store := _store()
	var copied := store.path_of("copied")

	DirAccess.make_dir_recursive_absolute(copied)

	for file_name: String in WorldVersions.chunk_names(_chunks):
		DirAccess.copy_absolute(_chunks.path_join(file_name), copied.path_join(file_name))

	var row: Dictionary = store.list()[0]

	_expect(row["key"] == "copied" and row["note"].is_empty() and row["saved"].is_empty()
		and row["chunks"] == 2 and row["problem"].is_empty(), "a copied directory is a version")
	_expect(store.current_key() == "copied", "and it is current")

	var meta := copied.path_join(_Const.TILE_VERSION_META_FILE)

	for text: String in ["{", '{"format": 99}', '{"format": 1, "extra": 1}',
			'{"format": 1, "note": 5}', '{"format": 1, "note": "a\\nb"}']:
		var file := FileAccess.open(meta, FileAccess.WRITE)

		file.store_string(text)
		file.close()
		_expect(not store.list()[0]["problem"].is_empty(), "the meta %s is refused" % text)

	_expect(store.remove("copied").is_empty(), "the hand-made version goes")


# ─── 7: the tables reach a version ──────────────────────────────────────────

## One chunk of the world names the last area of the table. A version
## holds a copy of it. [TableEdits] reads the table files of the
## repository. It writes nothing here: `uses` and `remove_problem` only
## read.
func _a_table_change_reaches_a_version() -> void:
	var store := _store()
	var edits := TableEdits.new()
	var area: String = TileTables.keys(TileTables.AREAS)[-1]
	var chunk := ChunkFile.read_file(_chunks.path_join("chunk_0_0_p0.json"))

	chunk.area_names.append(area)
	chunk.write_file(_chunks.path_join("chunk_0_0_p0.json"))
	store.save("named", "names the last area")
	edits.chunk_directories = PackedStringArray([_chunks])
	edits.version_shelves = PackedStringArray([_shelf])
	edits.template_directories = PackedStringArray()

	var found := edits.uses(TileTables.AREAS, area)

	_expect(found["chunks"].size() == 2, "the area is in one world file and one version file, "
		+ "found %d" % found["chunks"].size())
	_expect(not edits.remove_problem(TileTables.AREAS, area).is_empty(),
		"a removal refuses a row that a version names")
	edits.version_shelves = PackedStringArray()
	_expect(edits.uses(TileTables.AREAS, area)["chunks"].size() == 1,
		"with no shelf, only the world file names it")
	store.remove("named")
	store.switch_to("plain", true)


# ─── 8: the form ────────────────────────────────────────────────────────────

func _the_form_marks_the_current_version() -> void:
	var store := _store()
	var panel := _VersionsPanel.new()
	var sent := []

	add_child(panel)
	panel.save_requested.connect(func(key: String, note: String) -> void:
		sent.append(["save", key, note]))
	panel.switch_requested.connect(func(key: String) -> void: sent.append(["switch", key]))
	panel.refresh(store.list(), store.current_key())
	_expect(panel.row_count() == 1, "one row")
	_expect(panel.row_text("plain").begins_with(panel.CURRENT_MARK), "the current version is marked")
	_raise_a_corner("chunk_0_0_p0.json")
	panel.refresh(store.list(), store.current_key())
	_expect(not panel.row_text("plain").begins_with(panel.CURRENT_MARK),
		"a changed world has no mark")
	panel.set_key_text("  next ")
	panel.set_note_text(" the note ")
	_press(panel, "Save version")
	_expect(sent == [["save", "next", "the note"]], "Save version sends the fields: %s" % [sent])
	_press(panel, "Switch to version")
	_expect(sent[-1] == ["switch", ""], "Switch with no selection sends an empty key")
	panel.queue_free()


## Press the button of `panel` with the text `text`.
func _press(panel: Control, text: String) -> void:
	for button: Node in panel.find_children("*", "Button", true, false):
		if button.text == text:
			button.pressed.emit()
			return

	_expect(false, "no button %s" % text)
