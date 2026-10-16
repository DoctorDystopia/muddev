@tool
class_name FigureGearPanel
extends VBoxContainer
## The Gear tab of the figure workbench (DESIGN-0014 section 8.6, Phase
## W3): the item catalog with its filters, and the worn look of the selected
## row.
##
## ## The rows
##
## The list has one row for each slot shape, then one row for each item of
## the item catalog ([FigureCatalog]). A row says what the figure shows for
## it: its worn look, the slot shape, or the family shape
## ([FigureOutfit]). The filter keeps one slot, or the rows with no worn
## look (use case 5).
##
## A picked row dresses each stand in that item, so the author sees what a
## player sees (use case 6). The plugin does that. This panel only sends
## the row.
##
## ## The look of the row
##
## Below the list are the actions of a look, its color table, and its parts
## ([FigurePartsPanel]). A row with no worn look has no part to edit. "New
## look from the slot shape" gives the row a look to start from
## (requirement A6).
##
## This panel changes no worn look itself. Each control sends a signal, and
## the plugin makes the change through [FigureLookEdits] and the undo history.
##
## ## The hide list (Phase W4)
##
## The hide list has one check box for each region of the rig. A ticked
## region does not draw on each other look of the figure: a great helm
## hides the hair.
##
## ## A model for the row (Phase W4)
##
## "Import a model file" asks for a file, and the plugin runs the model
## pipeline on it ([FigurePipeline]). The parts of the look then become
## the nodes of the model. "Make the parts from the served model" does the
## second step only, for a model that the served tree has already.
##
## ## The served model in the game (ENG-0011, step L6)
##
## The Model fold has three fields for the served model of the row: its
## offset, its turn in degrees, and its scale. The game draws the model
## with them ([ModelRegistry]). A row with no served model has the fields
## off.
##
## ## A tier (Phase W5)
##
## "Make the row a tier of this look" gives the row a look with a base. The
## row then has the parts of that base, and no part of its own. Its color
## table shows each color role of the base. A color that the author picks
## there goes over the color of the base, and the first choice of a list
## takes it away again. A role with a color of its own has a mark in front
## of its name. A region that the base hides stays hidden.

signal row_chosen(key: String, slot: String)
signal look_requested(key: String, slot: String)
signal look_removed(key: String)
signal copy_requested(key: String, from_key: String)

## "Make the row a tier of this look".
signal tier_requested(key: String, base_key: String)
signal color_changed(key: String, role: String, color: String)
signal color_removed(key: String, role: String)
signal hide_changed(key: String, region: String, hidden: bool)

## "Import a model file". `path` is an OS path, and `author` goes into the
## source record.
signal import_requested(key: String, model_key: String, path: String, author: String)

## "Make the parts from the served model".
signal model_parts_requested(key: String, model_key: String)

## The served model of the row has a new offset, turn, or scale (ENG-0011,
## step L6). The turn is in degrees. `field` names the changed field. The
## label of a merged undo entry carries it.
signal presentation_changed(model_key: String, offset: Vector3, turn: Vector3, scale: float,
	field: String)

const ROW_LIST_HEIGHT := 200.0

## The range of the scale field of a presentation.
const PRESENT_SCALE_HIGH := 20.0
const PRESENT_SCALE_STEP := 0.01

## What the presentation line says for a row with no served model.
const NO_SERVED_MODEL := "The row has no served model, so it has no presentation."

## The first choice of the slot filter.
const EACH_SLOT := "(each slot)"

## The first choice of the color list of a color role: the look gives the
## role no color, and the palette gives it one.
const REMOVE_ROLE := "(the color of the palette)"

## The first choice of the color list of a color role of a tier.
const OF_THE_BASE := "(the color of the base look)"

## The mark of a color role of a tier that has a color of its own.
const OWN_MARK := "* "

## What a row says about its look, by the source of [FigureOutfit].
const SOURCE_TEXT := {
	FigureOutfit.SOURCE_LOOK: "worn look",
	FigureOutfit.SOURCE_SLOT_SHAPE: "slot shape",
	FigureOutfit.SOURCE_FAMILY: "family shape",
	FigureOutfit.SOURCE_NOTHING: "nothing",
}

const SLOT_SHAPE_ROW := "[slot shape] %s"

const HELP := "Pick a row to dress each figure in it. A row with no worn look " \
	+ "shows the slot shape of its slot. Give it a look, then change the parts " \
	+ "as on the Body tab."

const IMPORT_TITLE := "Import a model file for the row"

## The titles of the folds of this tab. The dock keeps the state of each
## one in the session file.
const FOLD_LOOK := "Look"
const FOLD_COLORS := "Colors"
const FOLD_HIDES := "Hides"
const FOLD_MODEL := "Model"

## How the copy list names a look that is a tier.
const TIER_ROW := "%s (a tier of %s)"

## What the tooltip of a button says when it needs a row.
const NEEDS_ROW := "Select a row first."

## The tooltip of each look button, by its text.
const LOOK_TIPS := {
	"New look": "New look from the slot shape: the row gets a copy of the slot shape of " \
		+ "its slot as its own look. A look that is there goes.",
	"Remove look": "Remove the worn look of the row. The row then shows its slot shape.",
	"Copy look": "Copy the parts, the colors, and the hide list of the look in the list " \
		+ "above into the look of the row. A tier gives the look that it draws.",
	"Make tier": "Make the row a tier of the look in the list above. The row then draws " \
		+ "the parts of that look, with colors of its own.",
	"Add color role": "Add the color role in the field to the color table of the look.",
	"Import model": "Import a model file: the model pipeline builds it, and the parts of " \
		+ "the look become the nodes of the model.",
	"Parts from model": "Make the parts from the served model with the key of the field.",
}

## The files that the model pipeline reads. A `.glb` goes in as it is. Each
## other one goes through Blender.
const IMPORT_FILTERS := ["*.glb, *.gltf ; glTF", "*.fbx, *.obj, *.blend ; Through Blender"]

const HIDE_COLUMNS := 2

var _slot_filter := OptionButton.new()
var _hides := GridContainer.new()
var _model_key := LineEdit.new()
var _author := LineEdit.new()
var _import: Button
var _model_parts: Button
var _open_dialog := FileDialog.new()
var _present_line := Label.new()
var _present_offset: HBoxContainer
var _present_turn: HBoxContainer
var _present_scale: SpinBox

## The key of the served model whose presentation the fields show, or "".
var _presented := ""

## The regions of the hide list, as one text.
var _shown_regions := ""

## The row and the models of its look, as one text.
var _shown_model := ""
var _missing_only := CheckBox.new()
var _text_filter := LineEdit.new()
var _rows := ItemList.new()
var _note := Label.new()

## Fold title -> the fold.
var _folds := {}
var _new_look: Button
var _remove_look: Button
var _copy: Button
var _tier: Button
var _add_role: Button
var _copy_from := OptionButton.new()
var _colors := GridContainer.new()
var _new_role := LineEdit.new()
var _parts_panel := FigurePartsPanel.new()

var _catalog: FigureCatalog
var _rig: FigureRig
var _looks := {}
var _models: FigureModels
var _palette: FigurePalette
var _presentation: ModelPresentation
var _selected := ""

## The rows of the list and the rows of the color table, each as one text.
var _shown_rows := ""
var _shown_colors := ""


func _init() -> void:
	add_child(FigureFields.label(HELP))
	_build_list_rows()
	_add_fold(FOLD_LOOK, _look_rows())
	_add_fold(FOLD_COLORS, _color_rows())
	_add_fold(FOLD_HIDES, _hide_rows())
	_add_fold(FOLD_MODEL, _model_rows())
	add_child(_parts_panel)
	# A dialog is a window, not a row of a fold.
	add_child(_open_dialog)


## One fold of this tab, closed at first. The part editor brings its own
## fold, open at first.
func _add_fold(title: String, rows: Array) -> void:
	_folds[title] = FigureFields.fold(title, FigureFields.column(rows), false)
	add_child(_folds[title])


func parts_panel() -> FigurePartsPanel:
	return _parts_panel


## The folds of this tab, with the fold of the part editor: title -> the
## fold.
func folds() -> Dictionary:
	var found := _folds.duplicate()

	found.merge(_parts_panel.folds())

	return found


## The text of the filter above the list. The list keeps the rows whose
## text has it, with no regard to the case.
func filter_text() -> String:
	return _text_filter.text.strip_edges().to_lower()


## The key of the look in the copy list, or "".
func copy_source() -> String:
	if _copy_from.selected < 0:
		return ""

	return _copy_from.get_item_metadata(_copy_from.selected)


## Show a catalog.
##
## - `rig` gives the bones and the slot table.
## - `looks` is key -> [FigureLook], for each worn look of the store.
## - `models` gives the models of the served tree.
## - `palette` gives the named colors of each color list.
## - `presentation` gives the offset, the turn, and the scale of a served
##   model. Null for the table of [ModelRegistry].
func set_content(catalog: FigureCatalog, rig: FigureRig, looks: Dictionary,
		models: FigureModels = null, palette: FigurePalette = null,
		presentation: ModelPresentation = null) -> void:
	_catalog = catalog
	_rig = rig
	_looks = looks
	_models = models
	_palette = palette
	_presentation = presentation

	if not _is_row(_selected):
		_selected = ""

	_fill_filter()
	_fill_rows()
	_show_look()


## The key of the selected row: an item key, or a slot for a slot shape row.
## "" for no row.
func selected_key() -> String:
	return _selected


## The slot of the selected row, or "".
func selected_slot() -> String:
	return _slot_of(_selected)


## The key of the worn look that the tab edits: the selected row when it has
## a worn look, or "".
func edited_look() -> String:
	return _selected if _looks.has(_selected) else ""


## Select a row by its key. The panel sends no signal. A row that the filter
## hides takes the filter off.
func select_row(key: String) -> void:
	if not _is_row(key):
		key = ""

	if key == _selected:
		return

	_selected = key

	if not key.is_empty() and not key in _row_keys():
		_slot_filter.select(0)
		_missing_only.set_pressed_no_signal(false)
		_text_filter.text = ""

	_fill_rows()
	_show_look()


## What the figure shows for one row: a SOURCE_* of [FigureOutfit].
func source_of(key: String) -> String:
	if _catalog == null or _rig == null or not _is_row(key):
		return FigureOutfit.SOURCE_NOTHING

	return FigureOutfit.source_of(_rig, _slot_of(key), key, _looks)


## One line for the selected row: the item, its slot, and what the figure
## shows for it (requirement A8). "" for no row.
func item_line() -> String:
	if _selected.is_empty():
		return ""

	var slot := _slot_of(_selected)

	if _selected == slot:
		return "The slot shape of %s: %s." % [slot, _slot_shape_state(slot)]

	return "%s, slot %s: the figure shows the %s." % [_catalog.item(_selected)["name"],
		slot, SOURCE_TEXT[source_of(_selected)]]


# ─── Building the panel ─────────────────────────────────────────────────────

func _build_list_rows() -> void:
	_slot_filter.item_selected.connect(func(_index: int) -> void: _fill_rows())
	_missing_only.text = "Only the rows with no worn look"
	_missing_only.toggled.connect(func(_on: bool) -> void: _fill_rows())
	_text_filter.placeholder_text = "Keep the rows with this text"
	_text_filter.clear_button_enabled = true
	_text_filter.text_changed.connect(func(_text: String) -> void: _fill_rows())
	_rows.custom_minimum_size.y = ROW_LIST_HEIGHT
	_rows.item_selected.connect(func(row: int) -> void:
		select_row(_rows.get_item_metadata(row))
		row_chosen.emit(_selected, selected_slot()))
	add_child(FigureFields.label("Slot of the rows"))
	add_child(_slot_filter)
	add_child(_missing_only)
	add_child(_text_filter)
	add_child(FigureFields.label("Rows (name, slot, what the figure shows)"))
	add_child(_rows)


## The rows of the Look fold: the note, and the look buttons.
func _look_rows() -> Array:
	_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_new_look = _look_button("New look", func() -> void:
		look_requested.emit(_selected, selected_slot()))
	_remove_look = _look_button("Remove look", func() -> void:
		look_removed.emit(_selected))
	_copy = _look_button("Copy look", func() -> void:
		copy_requested.emit(_selected, copy_source()))
	_tier = _look_button("Make tier", func() -> void:
		tier_requested.emit(_selected, copy_source()))

	return [_note, _new_look, _remove_look,
		FigureFields.label("The look to copy, or the base of a tier"), _copy_from, _copy, _tier]


## A button of the Look fold, with its tooltip from [constant LOOK_TIPS].
func _look_button(text: String, action: Callable) -> Button:
	return FigureFields.button(text, action, LOOK_TIPS[text])


## The rows of the Colors fold: the color table, and the new role form.
func _color_rows() -> Array:
	_add_role = _look_button("Add color role", func() -> void:
		color_changed.emit(_selected, _new_role.text.strip_edges(), _new_role_color()))
	_colors.columns = 2
	_new_role.placeholder_text = "The name of a new color role, for example trim"

	return [FigureFields.label("Colors of the look (color role, color)"), _colors, _new_role,
		_add_role]


func _hide_rows() -> Array:
	_hides.columns = HIDE_COLUMNS

	return [FigureFields.label("Regions that the look hides on each other look"), _hides]


func _model_rows() -> Array:
	_import = _look_button("Import model", func() -> void:
		_open_dialog.popup_centered_ratio())
	_model_parts = _look_button("Parts from model", func() -> void:
		model_parts_requested.emit(_selected, model_key()))
	_model_key.placeholder_text = "The asset key of the model. Empty for the key of the row"
	_author.placeholder_text = "The author of the model file, for its source record"
	_open_dialog.title = IMPORT_TITLE
	_open_dialog.access = FileDialog.ACCESS_FILESYSTEM
	_open_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	_open_dialog.filters = PackedStringArray(IMPORT_FILTERS)
	_open_dialog.file_selected.connect(func(path: String) -> void:
		import_requested.emit(_selected, model_key(), path, _author.text.strip_edges()))

	_present_line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_present_offset = FigureFields.vector_row(FigureFields.LENGTH_LOW, FigureFields.LENGTH_HIGH,
		FigureFields.LENGTH_STEP, func(_vector: Vector3, axis: int) -> void:
			_send_presentation("offset " + FigureFields.AXIS_NAMES[axis]), true)
	_present_turn = FigureFields.vector_row(-FigureFields.ANGLE_LIMIT, FigureFields.ANGLE_LIMIT,
		FigureFields.ANGLE_STEP, func(_vector: Vector3, axis: int) -> void:
			_send_presentation("turn " + FigureFields.AXIS_NAMES[axis]), true)
	_present_scale = FigureFields.spin(ModelPresentation.SCALE_LOW, PRESENT_SCALE_HIGH,
		PRESENT_SCALE_STEP, 1.0)
	_present_scale.value_changed.connect(func(_value: float) -> void:
		_send_presentation("scale"))

	return [FigureFields.label("Model of the look (a file in figure space)"), _model_key,
		_author, _import, _model_parts,
		FigureFields.label("Presentation of the served model in the game"), _present_line,
		FigureFields.label("Offset, in units of the unit box"), _present_offset,
		FigureFields.label("Turn (degrees)"), _present_turn,
		FigureFields.label("Scale, a multiplier on the unit box"), _present_scale]


## Send the presentation of the served model of the row, after a change of
## the field `field`.
func _send_presentation(field: String) -> void:
	if not _presented.is_empty():
		presentation_changed.emit(_presented, FigureFields.vector_of(_present_offset),
			FigureFields.vector_of(_present_turn), _present_scale.value, field)


## The key of the served model of one row, or "". The look of the row can
## name the model. If not, the key of the row is the model when the served
## tree has it.
func presented_model(key: String) -> String:
	var look: FigureLook = _looks.get(key)

	if look != null and not look.model_keys().is_empty():
		return look.model_keys()[0]

	if _models != null and _models.has(key):
		return key

	return ""


## Show the offset, the turn, and the scale of the served model of the row.
## A row with no served model has the fields off.
func _show_presentation() -> void:
	_presented = presented_model(_selected)

	var known := not _presented.is_empty()
	var content: Dictionary = {} if _presentation == null else _presentation.data
	var row := ModelPresentation.shown_row(_presented, content) if known else {}

	_present_line.text = "The served model %s." % _presented if known else NO_SERVED_MODEL
	FigureFields.set_vector(_present_offset, FigureJson.vector3(row.get(ModelPresentation.KEY_OFFSET)))
	FigureFields.set_vector(_present_turn, FigureJson.vector3(row.get(ModelPresentation.KEY_TURN)))
	_present_scale.set_value_no_signal(float(row.get(ModelPresentation.KEY_SCALE, 1.0)))

	for axis in FigureFields.AXES:
		(_present_offset.get_child(axis) as SpinBox).editable = known
		(_present_turn.get_child(axis) as SpinBox).editable = known

	_present_scale.editable = known


## A build runs now: the import button is off until it ends, with the
## reason in its tooltip. The plugin calls this.
func set_importing(busy: bool) -> void:
	if busy:
		FigureFields.enable(_import, false, "A build runs now. Wait until it ends.")
	else:
		_show_model(_looks.get(_selected))


## The asset key of the model of the row: the text of its field, or the
## key of the row for an empty field.
func model_key() -> String:
	var typed := _model_key.text.strip_edges()

	return _selected if typed.is_empty() else typed


## Show an author in the field of the import form. The dock keeps the last
## one in its options file.
func set_author(author: String) -> void:
	_author.text = author


# ─── The rows ───────────────────────────────────────────────────────────────

## True for a key that can be a row: a slot or an item of the catalog.
func _is_row(key: String) -> bool:
	return _catalog != null and (_catalog.has_slot(key) or _catalog.has_item(key))


func _slot_of(key: String) -> String:
	if _catalog == null:
		return ""

	return key if _catalog.has_slot(key) else _catalog.slot_of(key)


func _fill_filter() -> void:
	var names: Array = [EACH_SLOT]

	if _catalog != null:
		names.append_array(Array(_catalog.slot_keys()))

	FigureFields.fill(_slot_filter, names)

	if _slot_filter.selected < 0:
		_slot_filter.select(0)


## The keys of the rows that the filter keeps: each slot shape, then each
## item, slot by slot.
func _row_keys() -> PackedStringArray:
	var keys := PackedStringArray()
	var items := PackedStringArray()

	if _catalog == null:
		return keys

	for slot: String in _catalog.slot_keys():
		if _slot_filter.selected > 0 and FigureFields.text_of(_slot_filter) != slot:
			continue

		keys.append(slot)

		for row: Dictionary in _catalog.items_of(slot):
			items.append(row["key"])

	keys.append_array(items)

	var kept := PackedStringArray()
	var text := filter_text()

	for key: String in keys:
		if _missing_only.button_pressed and _looks.has(key):
			continue

		if text.is_empty() or _row_text(key).to_lower().contains(text):
			kept.append(key)

	return kept


## Fill the list. A list with the same rows stays, so a drag of a part does
## not move the scroll bar.
func _fill_rows() -> void:
	var keys := _row_keys()
	var lines := PackedStringArray()

	for key: String in keys:
		lines.append(_row_text(key))

	if "\n".join(lines) != _shown_rows:
		_shown_rows = "\n".join(lines)
		_rows.clear()

		for index in keys.size():
			_rows.add_item(lines[index])
			_rows.set_item_metadata(index, keys[index])

	_rows.deselect_all()

	for index in keys.size():
		if keys[index] == _selected:
			_rows.select(index)


func _row_text(key: String) -> String:
	if _catalog.has_slot(key):
		return "%s   %s" % [SLOT_SHAPE_ROW % _catalog.label_of(key), _slot_shape_state(key)]

	return "%s   %s   %s%s" % [_catalog.item(key)["name"], _catalog.slot_of(key),
		SOURCE_TEXT[source_of(key)], _tier_text(key)]


## What a row says after its source when its look is a tier, or "".
func _tier_text(key: String) -> String:
	var look: FigureLook = _looks.get(key)

	if look == null or look.base().is_empty():
		return ""

	return ", a tier of %s" % look.base()


## The named color of a new color role of a look. It is the color of the
## role in the palette, or the generic color.
func _new_role_color() -> String:
	var role := _new_role.text.strip_edges()

	if _palette == null:
		return MeshPalette.GENERIC

	return _palette.roles().get(role, MeshPalette.GENERIC)


## What a slot shape row says: a slot with no slot shape shows the family
## shape of each item.
func _slot_shape_state(slot: String) -> String:
	return "has a look" if _looks.has(slot) else "none, so the family shape draws"


# ─── The look of the selected row ───────────────────────────────────────────

func _show_look() -> void:
	var look: FigureLook = _looks.get(_selected)
	var is_tier := look != null and not look.base().is_empty()

	_fill_copy_list()
	_note.text = _note_text(look)
	_show_colors(look)
	_show_hides(look)
	_show_model(look)
	_show_presentation()
	_enable_look_buttons(look)
	# A tier has no part of its own. The author changes a part on the row of
	# the look that has it.
	_parts_panel.set_content(_rig, null if is_tier else look, _models, _palette)


## Fill the copy list with each look of the store, in sorted order. A row
## of a tier says so: the copy takes the look that the tier draws. The row
## keeps the key as its metadata. The list keeps its choice.
func _fill_copy_list() -> void:
	var keys := _looks.keys()
	var kept := copy_source()
	var labels := []

	keys.sort()

	for key: String in keys:
		var base: String = _looks[key].base()

		labels.append(key if base.is_empty() else TIER_ROW % [key, base])

	FigureFields.fill(_copy_from, labels)

	for index in keys.size():
		_copy_from.set_item_metadata(index, keys[index])

		if keys[index] == kept:
			_copy_from.select(index)

	if _copy_from.selected < 0 and _copy_from.item_count > 0:
		_copy_from.select(0)


## Each button that needs a row is off while no row is selected, with the
## reason in its tooltip. The remove button needs a look also.
func _enable_look_buttons(look: FigureLook) -> void:
	var has_row := not _selected.is_empty()

	for button: Button in [_new_look, _copy, _tier, _add_role]:
		FigureFields.enable(button, has_row, NEEDS_ROW)

	FigureFields.enable(_remove_look, look != null,
		NEEDS_ROW if not has_row else "The row has no worn look.")


## The regions that the base of a tier hides. A look with no base gives an
## empty list.
func _base_hides(look: FigureLook) -> Array:
	if look == null or not _looks.has(look.base()):
		return []

	return _looks[look.base()].resolved(_looks).hides()


## Show one check box for each region of the rig, in the order of the
## names. A box is ticked when the look hides its region. The boxes stay
## while the regions stay. A region that the base of a tier hides has a
## ticked box that the author cannot change.
func _show_hides(look: FigureLook) -> void:
	var regions: Array = [] if _rig == null else _rig.regions().keys()
	var from_base := _base_hides(look)

	regions.sort()

	if ",".join(regions) != _shown_regions:
		_shown_regions = ",".join(regions)

		for child: Node in _hides.get_children():
			_hides.remove_child(child)
			child.queue_free()

		for region: String in regions:
			_hides.add_child(_new_hide_box(region))

	for index in regions.size():
		var box := _hides.get_child(index) as CheckBox

		var hidden: bool = look != null \
			and (regions[index] in look.hides() or regions[index] in from_base)

		box.set_pressed_no_signal(hidden)
		box.disabled = look == null or regions[index] in from_base


func _new_hide_box(region: String) -> CheckBox:
	var box := CheckBox.new()

	box.text = region
	box.toggled.connect(func(pressed: bool) -> void:
		hide_changed.emit(_selected, region, pressed))

	return box


## The model field shows the model that the parts of the look name. It
## changes only with the row or with the models of the look, so a key that
## the author types stays. The two buttons need a row.
func _show_model(look: FigureLook) -> void:
	var keys := PackedStringArray() if look == null else look.model_keys()
	var shown := _selected + ":" + ",".join(keys)

	if shown != _shown_model:
		_shown_model = shown
		_model_key.text = "" if keys.is_empty() or keys[0] == _selected else keys[0]

	FigureFields.enable(_import, not _selected.is_empty(), NEEDS_ROW)
	FigureFields.enable(_model_parts, not _selected.is_empty(), NEEDS_ROW)


func _note_text(look: FigureLook) -> String:
	if _selected.is_empty():
		return "No row is selected."

	if look != null and not look.base().is_empty():
		var problem := look.base_problem(_looks)
		var text := "%s is a tier of %s. It has the parts of that look, so select " \
			% [_selected, look.base()] + "the row of that look to change a part."

		return text if problem.is_empty() else "%s It draws no part now: %s." % [text, problem]

	if look != null:
		return "%s has a worn look." % _selected

	if _catalog.has_slot(_selected):
		return "%s has no slot shape. The figure shows the family shape of each item." \
			% _selected

	return "%s has no worn look. The figure shows the %s." % [_selected,
		SOURCE_TEXT[source_of(_selected)]]


## Show one row for each color role that the look can give a color to.
## [method FigureLookEdits.roles_of_look] gives the roles. They come from the
## color table, from the shapes, and from the surfaces of the models.
##
## The rows stay while the roles and the color names stay. Thus, a list
## keeps the focus through a change. A tier shows each role of its base
## also. A mark is on each role of a tier that has a color of its own.
func _show_colors(look: FigureLook) -> void:
	var is_tier := look != null and not look.base().is_empty()
	var drawn: FigureLook = null if look == null else look.resolved(_looks)
	var shown: Dictionary = {} if drawn == null else drawn.colors()
	var roles: Array = [] if drawn == null \
		else Array(FigureLookEdits.roles_of_look(drawn, _models, _palette))
	var names := FigurePaletteEdits.color_choices(_palette)
	var labels := PackedStringArray()

	for role: String in roles:
		labels.append((OWN_MARK if is_tier and look.colors().has(role) else "") + role)

	var wanted := "%s|%s|%s" % [",".join(labels), ",".join(names), is_tier]

	if wanted != _shown_colors:
		_shown_colors = wanted

		for child: Node in _colors.get_children():
			_colors.remove_child(child)
			child.queue_free()

		for index in roles.size():
			_colors.add_child(FigureFields.cell_label(labels[index]))
			_colors.add_child(_new_color_list(roles[index], names,
				OF_THE_BASE if is_tier else REMOVE_ROLE))

	for index in roles.size():
		var list := _colors.get_child(index * 2 + 1) as OptionButton

		# A role with no color of the look shows the first choice.
		FigureFields.select_text(list, shown.get(roles[index], list.get_item_text(0)))
		FigureFields.mark_colors(list, _palette, {}, 1)


## The color list of one color role: `first`, then each named color. The
## first choice removes the role from the color table of the look. The role
## then has the color that the palette gives it. On a tier, it has the
## color of the base again.
func _new_color_list(role: String, names: Array, first: String) -> OptionButton:
	var list := OptionButton.new()

	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_item(first)

	for color_name: String in names:
		list.add_item(color_name)

	list.item_selected.connect(func(index: int) -> void:
		if index == 0:
			color_removed.emit(_selected, role)
		else:
			color_changed.emit(_selected, role, list.get_item_text(index)))

	return list
