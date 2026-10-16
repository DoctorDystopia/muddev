@tool
extends VBoxContainer
## The Tables tab of the terrain editor (Nick, 10/14/2026): the rows of the
## four server tables that an author adds to. These are the areas, the
## floor types, the wall styles, and the decor kinds.
##
## Pick a table, then a row. The fields below show the row. Four buttons act:
##
## - **New row** adds the fields as a new row, with the key of the Key
##   field. "New" beside a list of the paint values strip opens this tab
##   with empty fields.
## - **Save row** writes the fields to the selected row. The key stays.
## - **Rename row** gives the selected row the key of the Key field. It
##   rewrites each chunk file, template, and look row that names the key.
## - **Remove row** takes out a row that nothing uses.
##
## The fields come from [code]TILE_TABLE_FIELDS[/code], the export of the
## Python row classes. Thus, a new field of a row class gets a text field
## here with no edit. [constant FIELD_TEXTS] names the known fields.
##
## This panel changes no file. It sends a signal, and the plugin confirms,
## then calls [TableEdits].

## "New row": add `row` to `table`.
signal add_requested(table: String, row: Dictionary)

## "Save row": give the row `key` the fields of `row`.
signal save_requested(table: String, key: String, row: Dictionary)

## "Rename row": give the row `old` the key `new`.
signal rename_requested(table: String, old: String, new: String)

## "Remove row".
signal remove_requested(table: String, key: String)

## "Read the files again": the plugin drops the cache of [TileTables].
signal reload_requested

const _Const := preload("res://autoload/blackout_constants.gd")
const _Fields := preload("res://addons/blackout_terrain/terrain_fields.gd")

## The name of each table on the tab.
const TABLE_TEXTS := {
	TileTables.AREAS: "Areas",
	TileTables.FLOOR_TYPES: "Floor types",
	TileTables.WALL_STYLES: "Wall styles",
	TileTables.DECOR_KINDS: "Decor kinds",
}

## Each known field: the label and the tooltip.
const FIELD_TEXTS := {
	"key": ["Key", "The name that a chunk file stores: a-z, 0-9, and _."],
	"note": ["Note", "What the row is for. No player sees it."],
	"name": ["Room name", "The room name of a plain tile of the area. A player sees it."],
	"desc": ["Room text", "The room text of a plain tile of the area. A player sees it."],
	"roof": ["Roof floor", "The Roof tool lays a roof floor, and a roof tile must be "
		+ "Blocked."],
	"scenery": ["Scenery", "What the client draws on the tile: a primitive, or the key "
		+ "of a model."],
}

## The height of the row list and of the room text, in pixels.
const ROWS_HEIGHT := 140.0
const TEXT_HEIGHT := 60.0

var _table := OptionButton.new()
var _rows := ItemList.new()
var _hint := Label.new()

## The tables in the order of the list.
var _tables: Array = []

## Field name to its control. Field name to its label and its control.
var _controls := {}
var _field_rows := {}


func _init() -> void:
	name = "Tables"
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_build_intro()
	_build_table_rows()
	_build_fields()
	_build_buttons()
	_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_hint)
	_show_table()


# ─── Reading ────────────────────────────────────────────────────────────────

## The table of the list.
func table() -> String:
	return _tables[_table.selected] if _table.selected >= 0 else ""


## The key of the selected row, or "".
func selected_key() -> String:
	var picked := _rows.get_selected_items()

	return "" if picked.is_empty() else str(_rows.get_item_metadata(picked[0]))


## The fields of the form as a row of the table.
func form_row() -> Dictionary:
	var row := {}

	for field: String in TableEdits.fields_of(table()):
		row[field] = _value_of(field)

	return row


# ─── Writing ────────────────────────────────────────────────────────────────

## Show `on` with an empty form, and put the cursor in the Key field. The
## "New" buttons of the paint values strip call it.
func start_new_row(on: String) -> void:
	_table.select(maxi(_tables.find(on), 0))
	_show_table()
	_rows.deselect_all()
	_fill_form(TableEdits.empty_row(table()))
	_hint.text = "Type a key and the fields, then click New row."

	var key: Control = _controls.get(TileTables.FIELD_KEY)

	if key != null and key.is_inside_tree():
		key.grab_focus()


## Read the rows again, after a change. The selection follows `rename`,
## `{table, old, new}`, or the key `select`.
func refresh(rename := {}, select := "") -> void:
	var keep := selected_key()

	keep = _Fields.follow_of(rename, table()).get(keep, keep)

	if not select.is_empty():
		keep = select

	_fill_rows(keep)


func set_hint(text: String) -> void:
	_hint.text = text


# ─── Building ───────────────────────────────────────────────────────────────

func _build_intro() -> void:
	var intro := Label.new()

	intro.text = "The rows of the server tables. A change writes a file of " \
		+ "blackout/world/tables/, then runs the client export. The server reads " \
		+ "a new row after a restart."
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(intro)


func _build_table_rows() -> void:
	for found: String in _Const.TILE_TABLE_FIELDS:
		_tables.append(found)
		_table.add_item(TABLE_TEXTS.get(found, found))

	_table.item_selected.connect(func(_index: int) -> void: _show_table())
	_Fields.row(self, "Table", _table)
	_rows.custom_minimum_size.y = ROWS_HEIGHT
	_rows.item_selected.connect(func(_index: int) -> void: _show_row())
	add_child(_rows)


## One control for each field of every table. [method _show_table] shows
## the fields of the table of the list.
func _build_fields() -> void:
	for found: String in _Const.TILE_TABLE_FIELDS:
		for field: String in TableEdits.fields_of(found):
			if _controls.has(field):
				continue

			var texts: Array = FIELD_TEXTS.get(field, [field, ""])
			var control := _control_for(field)
			var label := _Fields.row(self, texts[0], control, texts[1])

			_controls[field] = control
			_field_rows[field] = [label, control]


static func _control_for(field: String) -> Control:
	var default: Variant = TableEdits.FIELD_DEFAULTS.get(field, "")

	if default is bool:
		return CheckBox.new()

	if field == TileTables.FIELD_SCENERY:
		var choices := OptionButton.new()

		_Fields.fill(choices, TableEdits.scenery_choices())
		return choices

	if field == "desc":
		var text := TextEdit.new()

		text.custom_minimum_size.y = TEXT_HEIGHT
		text.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
		return text

	return LineEdit.new()


func _build_buttons() -> void:
	var buttons := HFlowContainer.new()

	buttons.add_child(_Fields.button("New row", func() -> void:
		add_requested.emit(table(), form_row()),
		"Add the fields as a new row, with the key of the Key field."))
	buttons.add_child(_Fields.button("Save row", func() -> void:
		save_requested.emit(table(), selected_key(), form_row()),
		"Write the fields to the selected row. The key stays."))
	buttons.add_child(_Fields.button("Rename row", func() -> void:
		rename_requested.emit(table(), selected_key(), _key_text()),
		"Give the selected row the key of the Key field, in every file that names it."))
	buttons.add_child(_Fields.button("Remove row", func() -> void:
		remove_requested.emit(table(), selected_key()),
		"Take out the selected row. A row that a chunk or a template uses stays."))
	buttons.add_child(_Fields.button("Read files again", reload_requested.emit,
		"Read the table files again, after an edit outside Godot."))
	add_child(buttons)


# ─── The form ───────────────────────────────────────────────────────────────

## Show the fields of the table of the list, and its rows.
func _show_table() -> void:
	var shown := TableEdits.fields_of(table())

	for field: String in _field_rows:
		for control: Control in _field_rows[field]:
			control.visible = field in shown

	_fill_rows("")
	_fill_form(TableEdits.empty_row(table()))


func _fill_rows(select: String) -> void:
	_rows.clear()

	for row: Dictionary in TileTables.rows(table()):
		var key: String = row[TileTables.FIELD_KEY]
		var index := _rows.add_item("%s: %s" % [key, row.get("note", "")])

		_rows.set_item_metadata(index, key)
		_rows.set_item_tooltip(index, key)

		if key == select:
			_rows.select(index)

	if not select.is_empty():
		_show_row()


func _show_row() -> void:
	var key := selected_key()

	if key.is_empty():
		return

	var row := TableEdits.empty_row(table())

	row.merge(TileTables.row(table(), key), true)
	_fill_form(row)
	_hint.text = "%s. Edit the fields, then Save row. Type a new key, then Rename row." % key


func _fill_form(row: Dictionary) -> void:
	for field: String in row:
		var control: Control = _controls.get(field)

		if control is CheckBox:
			(control as CheckBox).button_pressed = bool(row[field])
		elif control is OptionButton:
			_Fields.select_text(control as OptionButton, str(row[field]))
		elif control is TextEdit:
			(control as TextEdit).text = str(row[field])
		elif control is LineEdit:
			(control as LineEdit).text = str(row[field])


func _value_of(field: String) -> Variant:
	var control: Control = _controls.get(field)

	if control is CheckBox:
		return (control as CheckBox).button_pressed

	if control is OptionButton:
		return _Fields.text_of(control as OptionButton)

	if control is TextEdit:
		return (control as TextEdit).text.strip_edges()

	if control is LineEdit:
		return (control as LineEdit).text.strip_edges()

	return TableEdits.FIELD_DEFAULTS.get(field, "")


func _key_text() -> String:
	return str(_value_of(TileTables.FIELD_KEY))
