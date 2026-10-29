@tool
extends VBoxContainer
## The Versions tab of the terrain editor (Nick, 10/28/2026): the shelf of
## saved worlds under `blackout/world/versions/`. A map author saves the
## world as a version, switches the world to another, and comes back, with
## no terminal and no git.
##
## The list shows each version: its key, its chunk count, its save date,
## and its note. The version that equals the world of now is marked. Five
## buttons act:
##
## - **Save version** saves the world as the version of the Key field, with
##   the Note field. The unsaved chunks of the block save first. A key that
##   exists asks before it is replaced.
## - **Switch to version** makes the selected version the world. The block
##   reads again. When no version holds the world of now, it asks first
##   and counts the files that go.
## - **Rename version** gives the selected version the key of the Key
##   field.
## - **Remove version** deletes the selected version. It asks first.
## - **Read files again** reads the shelf again, after a change outside
##   Godot.
##
## This panel changes no file. It sends a signal, and the plugin confirms,
## then calls [WorldVersions].

## "Save version": save the world as `key`, with `note`.
signal save_requested(key: String, note: String)

## "Switch to version": make `key` the world.
signal switch_requested(key: String)

## "Rename version": give `old` the key `new`.
signal rename_requested(old: String, new: String)

## "Remove version".
signal remove_requested(key: String)

## "Read files again".
signal reload_requested

const _Fields := preload("res://addons/blackout_terrain/terrain_fields.gd")

## The mark of the version that equals the world of now.
const CURRENT_MARK := "* "

## The height of the list, in pixels.
const ROWS_HEIGHT := 160.0

## The text of a version with no save time.
const NO_DATE := "no date"

var _rows := ItemList.new()
var _key := LineEdit.new()
var _note := LineEdit.new()
var _hint := Label.new()


func _init() -> void:
	name = "Versions"
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_build_intro()
	_rows.custom_minimum_size.y = ROWS_HEIGHT
	_rows.item_selected.connect(func(_index: int) -> void: _show_row())
	add_child(_rows)
	_key.placeholder_text = "a-z, 0-9, and _"
	_Fields.row(self, "Key", _key, "The key of a new version, or the new key of a rename.")
	_note.placeholder_text = "one line"
	_Fields.row(self, "Note", _note, "What the version is for. One line.")
	_build_buttons()
	_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_hint)


# ─── Reading ────────────────────────────────────────────────────────────────

## The key of the selected version, or "".
func selected_key() -> String:
	var picked := _rows.get_selected_items()

	return "" if picked.is_empty() else str(_rows.get_item_metadata(picked[0]))


## The Key field, with no space at either end.
func key_text() -> String:
	return _key.text.strip_edges()


## The Note field, with no space at either end.
func note_text() -> String:
	return _note.text.strip_edges()


## The number of rows of the list.
func row_count() -> int:
	return _rows.item_count


## The text of the row of `key`, or "".
func row_text(key: String) -> String:
	for index: int in _rows.item_count:
		if _rows.get_item_metadata(index) == key:
			return _rows.get_item_text(index)

	return ""


# ─── Writing ────────────────────────────────────────────────────────────────

## Fill the list from `versions`, the rows of [method WorldVersions.list],
## and mark `current`. The selection follows `select`, or stays.
func refresh(versions: Array[Dictionary], current: String, select := "") -> void:
	var keep := selected_key() if select.is_empty() else select

	_rows.clear()

	for row: Dictionary in versions:
		var index := _rows.add_item(_row_text(row, current))

		_rows.set_item_metadata(index, row["key"])
		_rows.set_item_tooltip(index, row["note"] if row["problem"].is_empty()
			else row["problem"])

		if row["key"] == keep:
			_rows.select(index)

	if versions.is_empty():
		_hint.text = "The shelf is empty. Type a key, then click Save version."
	elif current.is_empty():
		_hint.text = "No version holds the world of now. Save it to keep it."
	else:
		_hint.text = "The world is the version %s." % current


func set_hint(text: String) -> void:
	_hint.text = text


## Put `key` in the Key field: after a save, so a second save overwrites it.
func set_key_text(key: String) -> void:
	_key.text = key


func set_note_text(note: String) -> void:
	_note.text = note


static func _row_text(row: Dictionary, current: String) -> String:
	var mark: String = CURRENT_MARK if row["key"] == current else "   "
	var when: String = row["saved"].get_slice("T", 0) if not row["saved"].is_empty() \
		else NO_DATE
	var text := "%s%s  (%d chunks, %s)" % [mark, row["key"], row["chunks"], when]

	if not row["problem"].is_empty():
		return text + "  PROBLEM: " + row["problem"]

	if not row["note"].is_empty():
		text += "  " + row["note"]

	return text


# ─── Building ───────────────────────────────────────────────────────────────

func _build_intro() -> void:
	var intro := Label.new()

	intro.text = "The saved worlds, under blackout/world/versions/. A switch " \
		+ "replaces the chunk files of the world. The server shows the new world " \
		+ "after a stop, scripts/sync_tile_objects.py --apply, and a start."
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(intro)


func _build_buttons() -> void:
	var buttons := HFlowContainer.new()

	buttons.add_child(_Fields.button("Save version", func() -> void:
		save_requested.emit(key_text(), note_text()),
		"Save the world chunk files as the version of the Key field. "
		+ "The unsaved chunks of the block save first."))
	buttons.add_child(_Fields.button("Switch to version", func() -> void:
		switch_requested.emit(selected_key()),
		"Make the selected version the world. The block reads again."))
	buttons.add_child(_Fields.button("Rename version", func() -> void:
		rename_requested.emit(selected_key(), key_text()),
		"Give the selected version the key of the Key field."))
	buttons.add_child(_Fields.button("Remove version", func() -> void:
		remove_requested.emit(selected_key()),
		"Delete the selected version from the shelf."))
	buttons.add_child(_Fields.button("Read files again", reload_requested.emit,
		"Read the shelf again, after a change outside Godot."))
	add_child(buttons)


func _show_row() -> void:
	var key := selected_key()

	if key.is_empty():
		return

	_key.text = key
	_hint.text = "%s. Switch to version makes it the world. Type a new key, then " % key \
		+ "Rename version."
