extends Node
## Tests for the picture editor (11/16/2026): [PictureEditor], with its item
## list, its view, and its fields.
##
##     godot --headless --path godot res://tests/addons/blackout_pictures/test_picture_editor.tscn
##
## Needs nothing running and no editor. It reads the served model tree and
## the item list of the repository. It writes one picture file under
## `user://` only, and it removes that file at its end. No test names an
## item key: each key comes from the item list. The cases:
##
## 1. The editor opens on the first item, with the default pose and a
##    picture. The list has a row for each item.
## 2. A typed value changes the pose of the item, the drawn picture, and
##    the mark of its row. Only that value changes.
## 3. The mouse of the view moves, turns, and zooms. A turn wraps, and a
##    zoom stops at the top of its range.
## 4. Reset gives the default pose, and the content keeps no row.
## 5. Copy and Paste give the pose of one item to another item.
## 6. Save writes the file, and a second editor reads the pose from it.
## 7. Revert drops each unsaved pose.
## 8. The two filters keep the right rows. A selected item that a filter
##    hides takes the filters off.
## 9. The list gets its pictures some at a time.
## 10. A file that does not read gives a problem, and Save writes nothing.

const TOLERANCE := 0.0001

const TYPED_ZOOM := 60.0
const TYPED_TURN := 45.0

## A text that no item has, for the text filter.
const NO_SUCH_TEXT := "no item has this text"

const BAD_FILE_TEXT := "this is no JSON object"

var _failures := 0
var _path := ""


func _ready() -> void:
	_path = "user://picture_editor_test_%d.json" % Time.get_ticks_usec()

	_the_editor_opens_on_the_first_item()
	_a_typed_value_changes_the_pose()
	_the_mouse_moves_turns_and_zooms()
	_reset_gives_the_default_pose()
	_copy_and_paste_give_a_pose_to_another_item()
	_save_writes_the_file()
	_revert_drops_each_unsaved_pose()
	_the_filters_keep_the_right_rows()
	_the_list_gets_its_pictures_some_at_a_time()
	_a_bad_file_gives_a_problem()

	DirAccess.remove_absolute(ProjectSettings.globalize_path(_path))
	LookFile.forget(PicturePose.PATH)

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: picture_editor")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


## An open editor on the item list of the game, with the test file as its
## picture file. Each case starts with no file.
func _editor() -> PictureEditor:
	var editor := PictureEditor.new()

	DirAccess.remove_absolute(ProjectSettings.globalize_path(_path))
	add_child(editor)
	editor.open("", SpawnItems.game(), _path)

	return editor


func _close(editor: PictureEditor) -> void:
	editor.close()
	remove_child(editor)
	editor.free()


## The node that the stage of the editor draws for its selected item.
func _drawn(editor: PictureEditor) -> Node3D:
	var stage := editor._stage
	var key := editor.selected_key()

	for index: int in stage._sources.size():
		if str(stage._sources[index][0]) == key:
			return stage._items.get(index)

	return null


func _zoom(editor: PictureEditor) -> float:
	return PicturePose.zoom_of(editor.shown_pose())


## True when two rows give one pose. The file rounds each number. Thus, a
## pose of the file can differ from its row of before the save.
func _same_pose(first: Dictionary, second: Dictionary) -> bool:
	return absf(PicturePose.zoom_of(first) - PicturePose.zoom_of(second)) < TOLERANCE \
		and PicturePose.offset_of(first).is_equal_approx(PicturePose.offset_of(second)) \
		and PicturePose.turn_of(first).is_equal_approx(PicturePose.turn_of(second))


func _the_editor_opens_on_the_first_item() -> void:
	var editor := _editor()
	var keys := SpawnItems.game().keys()

	_expect(keys.size() >= 2, "the item list of the game has two items")
	_expect(editor.is_open(), "the editor is open")
	_expect(editor.selected_key() == keys[0], "the editor opens on the first item")
	_expect(editor._list.shown_keys() == keys, "the list has a row for each item")
	_expect(PicturePose.is_default(editor.shown_pose()), "a new item has the default pose")
	_expect(editor._viewer.picture() != null, "the view shows the picture of the item")
	_expect(_drawn(editor) != null, "the stage draws the item")
	_expect(not editor.has_unsaved_changes(), "an editor with no change has nothing to save")
	_expect(editor._save_button.disabled, "Save is off with nothing to save")
	_close(editor)


func _a_typed_value_changes_the_pose() -> void:
	var editor := _editor()
	var key := editor.selected_key()
	var before := _drawn(editor).transform

	editor._fields.type_value(PictureFields.FIELD_ZOOM, TYPED_ZOOM)

	var pose := editor.shown_pose()

	_expect(absf(_zoom(editor) - (TYPED_ZOOM / PictureFields.PERCENT)) < TOLERANCE,
		"a typed zoom is the zoom of the pose")
	_expect(PicturePose.turn_of(pose).is_equal_approx(PicturePose.DEFAULT_TURN)
		and PicturePose.offset_of(pose).is_equal_approx(PicturePose.DEFAULT_OFFSET),
		"a typed zoom changes no other value")
	_expect(PicturePose.has_picture(editor._content, key), "the content has the row of the item")
	_expect(PicturePose.file_row(key) == editor._content[PicturePose.KEY_PICTURES][key],
		"the stage reads the row of the editor")
	_expect(not _drawn(editor).transform.is_equal_approx(before),
		"the stage draws the item again with its pose")
	_expect(editor.has_unsaved_changes() and editor.unsaved_count() == 1,
		"one item has an unsaved pose")
	_expect(not editor._save_button.disabled, "Save is on with a pose to save")
	_expect(editor._list._row_text(key).ends_with(PictureItemList.OWN_POSE_MARK),
		"the row of the item has the mark of a pose of its own")

	editor._fields.type_value(PictureFields.FIELD_TURN_Z, TYPED_TURN)
	_expect(is_equal_approx(PicturePose.turn_of(editor.shown_pose()).z, TYPED_TURN)
		and absf(_zoom(editor) - (TYPED_ZOOM / PictureFields.PERCENT)) < TOLERANCE,
		"a typed angle keeps the typed zoom")
	_close(editor)


func _the_mouse_moves_turns_and_zooms() -> void:
	var editor := _editor()
	var viewer := editor._viewer
	var limit := PicturePose.TURN_LIMIT
	var step := PictureEditor.ZOOM_WHEEL_STEP

	viewer.zoom_stepped.emit(1)
	_expect(is_equal_approx(_zoom(editor), PicturePose.ZOOM_HIGH),
		"a zoom stops at the top of its range")
	viewer.zoom_stepped.emit(-2)
	_expect(absf(_zoom(editor) - (PicturePose.ZOOM_HIGH - (step * 2.0))) < TOLERANCE,
		"two steps of the wheel make the picture smaller")

	viewer.offset_dragged.emit(Vector2(0.04, -0.02))
	viewer.offset_dragged.emit(Vector2(0.04, -0.02))
	_expect(PicturePose.offset_of(editor.shown_pose()).is_equal_approx(Vector2(0.08, -0.04)),
		"two drags with the left button add their offsets")

	var turn := PicturePose.turn_of(editor.shown_pose())

	viewer.turn_dragged.emit(Vector2(10.0, limit * 2.0))

	var turned := PicturePose.turn_of(editor.shown_pose())

	_expect(is_equal_approx(turned.x, turn.x + 10.0), "a drag with the right button turns about X")
	_expect(absf(turned.y - turn.y) < TOLERANCE, "a full turn about the vertical wraps")
	_expect(is_equal_approx(turned.z, turn.z), "a drag leaves the turn about Z")
	_expect(editor._fields.shown_pose() == editor.shown_pose(),
		"the fields show the pose that the mouse made")
	_close(editor)


func _reset_gives_the_default_pose() -> void:
	var editor := _editor()
	var key := editor.selected_key()

	editor._fields.type_value(PictureFields.FIELD_ZOOM, TYPED_ZOOM)
	editor._fields.press("Reset pose")
	_expect(PicturePose.is_default(editor.shown_pose()), "Reset gives the default pose")
	_expect(not PicturePose.has_picture(editor._content, key),
		"the content keeps no row of the default pose")
	_expect(not editor.has_unsaved_changes(), "a reset to the pose of the file leaves no change")
	_close(editor)


func _copy_and_paste_give_a_pose_to_another_item() -> void:
	var editor := _editor()
	var keys := SpawnItems.game().keys()

	editor._fields.type_value(PictureFields.FIELD_ZOOM, TYPED_ZOOM)
	editor._fields.type_value(PictureFields.FIELD_TURN_Y, TYPED_TURN)

	var copied := editor.shown_pose()

	editor._fields.press("Copy pose")
	editor.select_item(keys[1])
	_expect(PicturePose.is_default(editor.shown_pose()), "the second item has the default pose")
	editor._fields.press("Paste pose")
	_expect(editor.selected_key() == keys[1] and editor.shown_pose() == copied,
		"Paste gives the second item the pose of the first item")
	_expect(editor.unsaved_count() == 2, "two items have an unsaved pose")
	_close(editor)


func _save_writes_the_file() -> void:
	var editor := _editor()
	var key := editor.selected_key()

	editor._fields.type_value(PictureFields.FIELD_ZOOM, TYPED_ZOOM)

	var pose := editor.shown_pose()

	_expect(editor.save() == OK, "the save succeeds")
	_expect(not editor.has_unsaved_changes(), "a saved editor has nothing to save")
	_expect(PicturePose.problem_of(FigureJson.parse(FileAccess.get_file_as_string(_path)))
		.is_empty(), "the written file has a good form")
	editor.close()
	remove_child(editor)
	editor.free()

	# No `_editor()` here: it removes the file.
	var second := PictureEditor.new()

	add_child(second)
	second.open("", SpawnItems.game(), _path)
	second.select_item(key)
	_expect(_same_pose(second.shown_pose(), pose),
		"a second editor reads the pose from the file")
	_expect(not second.has_unsaved_changes(), "a pose of the file is no change")
	_close(second)


func _revert_drops_each_unsaved_pose() -> void:
	var editor := _editor()
	var key := editor.selected_key()

	editor._fields.type_value(PictureFields.FIELD_ZOOM, TYPED_ZOOM)
	editor.save()
	editor._fields.type_value(PictureFields.FIELD_TURN_X, TYPED_TURN)

	var changed := _drawn(editor).transform

	editor.revert()

	var pose := editor.shown_pose()

	_expect(not editor.has_unsaved_changes(), "a revert leaves no change")
	_expect(absf(PicturePose.zoom_of(pose) - (TYPED_ZOOM / PictureFields.PERCENT)) < TOLERANCE
		and is_equal_approx(PicturePose.turn_of(pose).x, PicturePose.DEFAULT_TURN.x),
		"a revert keeps the saved zoom and drops the unsaved angle")
	_expect(editor.selected_key() == key, "a revert keeps the selected item")
	_expect(not _drawn(editor).transform.is_equal_approx(changed),
		"a revert draws the item again")
	_expect(editor._fields.shown_pose() == pose, "the fields show the pose of the file")
	_close(editor)


func _the_filters_keep_the_right_rows() -> void:
	var editor := _editor()
	var list := editor._list
	var keys := SpawnItems.game().keys()
	var posed := editor.selected_key()

	editor._fields.type_value(PictureFields.FIELD_ZOOM, TYPED_ZOOM)
	list.pick_pose_filter(PictureItemList.FILTER_OWN_POSE)
	_expect(list.shown_keys() == PackedStringArray([posed]),
		"the first filter keeps the items with a pose of their own")
	list.pick_pose_filter(PictureItemList.FILTER_DEFAULT_POSE)
	_expect(list.shown_keys().size() == keys.size() - 1 and not posed in list.shown_keys(),
		"the second filter keeps the items with the default pose")
	list.pick_pose_filter(PictureItemList.FILTER_EACH)
	list.type_filter(keys[1].to_upper())
	_expect(keys[1] in list.shown_keys(), "the text filter finds a key, with no regard to the case")
	list.type_filter(NO_SUCH_TEXT)
	_expect(list.shown_keys().is_empty(), "a text that no item has keeps no row")
	editor.select_item(keys[1])
	_expect(list.shown_keys() == keys and list.selected_key() == keys[1],
		"a selected item that a filter hides takes the filters off")
	_close(editor)


func _the_list_gets_its_pictures_some_at_a_time() -> void:
	var editor := _editor()
	var list := editor._list
	var count := PictureEditor.PICTURES_PER_FRAME

	_expect(list.picture_count() == 0, "a new list has no picture")
	_expect(list.fill_pictures(count) == count and list.picture_count() == count,
		"one call gives a picture to some rows")
	_expect(list.fill_pictures(count) == count and list.picture_count() == count * 2,
		"the next call gives a picture to the next rows")
	list.type_filter(NO_SUCH_TEXT)
	list.type_filter("")
	_expect(list.picture_count() == count * 2, "a filter change keeps each picture of the list")
	_close(editor)


func _a_bad_file_gives_a_problem() -> void:
	var editor := _editor()
	var file := FileAccess.open(_path, FileAccess.WRITE)

	file.store_string(BAD_FILE_TEXT)
	file.close()
	editor.revert()
	_expect(not editor._problem.is_empty(), "a file that is no JSON object gives a problem")
	_expect(editor._save_button.disabled, "Save is off for a file that does not read")
	editor._fields.type_value(PictureFields.FIELD_ZOOM, TYPED_ZOOM)
	_expect(editor.save() != OK, "the save of a file that does not read writes nothing")
	_expect(FileAccess.get_file_as_string(_path) == BAD_FILE_TEXT, "the file stays as it was")
	_close(editor)
