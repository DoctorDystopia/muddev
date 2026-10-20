@tool
class_name FigureFamiliesPanel
extends PartEditor
## The Families tab of the figure workbench (ENG-0011, step L5): the shape
## of each item family with no art of its own, as the look file
## `families.json` holds it ([FamilyLooks]).
##
## The list has one row for each family: each item family of the server,
## each family of the file, and each family of the table of [FamilyShapes].
## A row says where its shape comes from: the file, the table, or nothing.
## A selected family shows on the family stand of the workbench, as the
## game draws it.
##
## A family with a row in the file has the part editor below
## ([PartEditor]). A family with no row has a note and "New shape
## from the fallback": the row then starts from the table, or from the
## generic block. "Remove shape" takes the row out, and the family draws
## its table again.
##
## The model field names the asset key that stands in for the whole family
## (tier 2 of the mesh ladder). An empty field takes the model out.
##
## This panel changes no file itself. Each control sends a signal, and the
## plugin makes the change through the undo history.

signal family_chosen(family: String)

## "New shape from the fallback", and "Remove shape".
signal row_requested(family: String)
signal row_removed(family: String)

## The model field has a new asset key, or "" for no model.
signal model_changed(family: String, model_key: String)

const FAMILY_LIST_HEIGHT := 160.0

const HELP := "Each family with no art of its own draws a shape. Pick a family to " \
	+ "see it on the stand at the right, and change its parts below."

## Where the shape of a family comes from, as the list says it.
const SOURCE_FILE := "the file"
const SOURCE_TABLE := "the table"
const SOURCE_NONE := "nothing, the generic block"

const NEEDS_FAMILY := "Select a family first."

## The server-owned family names.
const _Const := preload("res://autoload/blackout_constants.gd")

var _families := ItemList.new()
var _family_note := Label.new()
var _new_row: Button
var _remove_row: Button
var _model_key := LineEdit.new()
var _set_model: Button

var _looks: FamilyLooks
var _selected_family := ""

## The rows of the family list, as one text.
var _shown_families := ""


func _init() -> void:
	super()
	_build_family_rows()

	var rows: Array[Control] = [FigureFields.label(HELP), _families, _family_note, _new_row,
		_remove_row, FigureFields.label("Model that stands in for the whole family"),
		_model_key, _set_model]

	# A family shape has one bone, so it has no fit.
	fit_controls = false

	# The rows of a family go before the fold of the part editor.
	for index in rows.size():
		add_child(rows[index])
		move_child(rows[index], index)


## The list, the note, the buttons, and the model field.
func _build_family_rows() -> void:
	_families.custom_minimum_size.y = FAMILY_LIST_HEIGHT
	_families.item_selected.connect(func(row: int) -> void:
		select_family(_families.get_item_metadata(row))
		family_chosen.emit(_selected_family))
	_family_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_new_row = FigureFields.button("New shape from the fallback", func() -> void:
		row_requested.emit(_selected_family),
		"Give the family a row in the file, with the parts that it draws now.")
	_remove_row = FigureFields.button("Remove shape", func() -> void:
		row_removed.emit(_selected_family),
		"Take the row of the family out of the file. The family draws its table again.")
	_model_key.placeholder_text = "The asset key of a served model, or empty for none"
	_set_model = FigureFields.button("Set model", func() -> void:
		model_changed.emit(_selected_family, _model_key.text.strip_edges()),
		"Give the family the model with the key in the field.")


## Show the family file. `looks` is the file of the store, and `palette`
## gives the names of the color list of a shape.
func set_families(looks: FamilyLooks, palette: FigurePalette = null) -> void:
	_looks = looks

	if not _selected_family in family_names():
		_selected_family = ""

	_fill_families()
	_show_family()
	set_content(FamilyLooks.stand_rig(), _looks.look_of(_selected_family), null, palette)


## Each family of the list, in sorted order: the item families of the
## server, the families of the file, and the families of the table.
func family_names() -> PackedStringArray:
	var names := PackedStringArray(_Const.ITEM_FAMILIES)

	for family: String in FamilyShapes.families():
		if not family in names:
			names.append(family)

	if _looks != null:
		for family: String in _looks.family_names():
			if not family in names:
				names.append(family)

	names.sort()

	return names


func selected_family() -> String:
	return _selected_family


## The look key of the part editor: the family with its prefix, or "" for
## a family with no row.
func edited_look() -> String:
	if _looks == null or not _looks.has_family(_selected_family):
		return ""

	return FamilyLooks.LOOK_PREFIX + _selected_family


## Select a family of the list. The panel sends no signal.
func select_family(family: String) -> void:
	_selected_family = family if family in family_names() else ""
	_fill_families()
	_show_family()
	set_content(FamilyLooks.stand_rig(), null if _looks == null \
		else _looks.look_of(_selected_family), null, _palette)


## Where the shape of one family comes from: a SOURCE_* constant.
func source_of(family: String) -> String:
	if _looks != null and _looks.has_family(family):
		return SOURCE_FILE

	if FamilyShapes.SHAPES.has(family):
		return SOURCE_TABLE

	return SOURCE_NONE


# ─── Showing the families ───────────────────────────────────────────────────

## Fill the family list. A list with the same rows keeps its scroll bar.
func _fill_families() -> void:
	var names := family_names()
	var lines := PackedStringArray()

	for family: String in names:
		lines.append("%s   %s   %s" % [family, source_of(family), _family_model_text(family)])

	if "\n".join(lines) != _shown_families:
		_shown_families = "\n".join(lines)
		_families.clear()

		for index in names.size():
			_families.add_item(lines[index])
			_families.set_item_metadata(index, names[index])

	_families.deselect_all()

	for index in names.size():
		if names[index] == _selected_family:
			_families.select(index)


## The model of one family for its row: "model <key>", or "".
func _family_model_text(family: String) -> String:
	var model_key := FamilyShapes.model_for(family)

	return "" if model_key.is_empty() else "model " + model_key


## Show the selected family: its note, its buttons, and its model.
func _show_family() -> void:
	var has_family := not _selected_family.is_empty()
	var has_row := _looks != null and _looks.has_family(_selected_family)

	_family_note.text = _family_note_text()
	FigureFields.enable(_new_row, has_family, NEEDS_FAMILY)
	FigureFields.enable(_remove_row, has_row,
		NEEDS_FAMILY if not has_family else "The family has no row in the file.")
	FigureFields.enable(_set_model, has_family, NEEDS_FAMILY)
	_model_key.editable = has_family
	_model_key.text = FamilyShapes.model_for(_selected_family) if has_family else ""


func _family_note_text() -> String:
	if _selected_family.is_empty():
		return "No family is selected."

	match source_of(_selected_family):
		SOURCE_FILE:
			return "%s has a row in the file." % _selected_family
		SOURCE_TABLE:
			return "%s draws the table of FamilyShapes. Make a row to change it." \
				% _selected_family

	return "%s has no row anywhere, so it draws the generic block. Make a row to change it." \
		% _selected_family
