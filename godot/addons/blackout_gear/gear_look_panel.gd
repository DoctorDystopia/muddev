@tool
class_name GearLookPanel
extends VBoxContainer
## The worn look of the selected row of the Gear dock (DESIGN-0014
## section 22): the actions of the look, its color table, its hide list,
## and its model. Four folds below the part editor.
##
## ## The Look fold
##
## A row with no worn look has no part to edit. "New look" gives the row a
## copy of the slot shape of its slot (requirement A6). "Copy look" gives it
## the parts and the colors of another look. "Make tier" gives it a look
## with a base (Phase W5). The row then draws the parts of that look, with
## colors of its own. "Remove look" takes the look away.
##
## ## The Colors fold
##
## One row for each color role that the look can give a color to. The
## first choice of a list gives the role the color of the palette. On a
## tier, it gives the color of the base again, and a mark is in front of
## each role with a color of its own.
##
## ## The Hides fold (Phase W4)
##
## One check box for each region of the rig. A ticked region does not draw
## on each other look of the figure: a great helm hides the hair. A region
## that the base of a tier hides has a ticked box that the author cannot
## change.
##
## ## The Model fold (Phase W4, ENG-0011 step L6)
##
## "Import model" asks for a file, and the plugin runs the model pipeline
## on it ([FigurePipeline]). The parts of the look then become the nodes of
## the model. "Parts from model" does the second step only. Three fields
## give the presentation of the served model of the row: its offset, its
## turn in degrees, and its scale. The game draws the model with them
## ([ModelRegistry]). A row with no served model has the fields off.
##
## A served model of the row wins over the worn look on the figure
## (10/17/2026, [FigureOutfit]). The import and "Parts from model" are off
## for such a row while the model field is empty. The import must not write
## over art that it did not bring, and the served model draws as it is.
## "Fit served model to look" takes the moved place of the model away.
##
## "Scale in the hand" scales the whole served model on each stand
## (10/27/2026). The field shows the largest axis of the scale that the
## stand draws. A change keeps the proportions, the bone, and the place.
## The presentation fields do not change the model in the hand: the game
## uses them on the ground and on the family stand.
##
## This panel changes no worn look itself. Each control sends a signal, and
## the plugin makes the change through [FigureLookEdits] and the undo
## history.

signal look_requested(key: String, slot: String)
signal look_removed(key: String)
signal copy_requested(key: String, from_key: String)

## "Make tier".
signal tier_requested(key: String, base_key: String)
signal color_changed(key: String, role: String, color: String)
signal color_removed(key: String, role: String)
signal hide_changed(key: String, region: String, hidden: bool)

## "Import model". `path` is an OS path, and `author` goes into the source
## record.
signal import_requested(key: String, model_key: String, path: String, author: String)

## "Parts from model".
signal model_parts_requested(key: String, model_key: String)

## "Fit served model to look".
signal served_fit_requested(key: String)

## "Scale in the hand". `drawn` is the row of the served part that the
## stand draws before the change ([method served_place]).
signal served_scale_changed(key: String, drawn: Dictionary, size: float)

## The served model of the row has a new offset, turn, or scale. The turn
## is in degrees. `field` names the changed field. The label of a merged
## undo entry carries it.
signal presentation_changed(model_key: String, offset: Vector3, turn: Vector3, scale: float,
	field: String)

## The range of the scale field of a presentation.
const PRESENT_SCALE_HIGH := 20.0
const PRESENT_SCALE_STEP := 0.01

## What the presentation line says for a row with no served model.
const NO_SERVED_MODEL := "The row has no served model, so it has no presentation."

## The tooltip of the import and of "Parts from model" for a row whose
## served model draws on the figure.
const SERVED_WINS := "The figure draws the served model of the row as it is. Type another " \
	+ "key in the model field to import a model of the look."

## The tooltip of "Fit served model to look" when it cannot apply.
const NOT_SERVED := "The figure does not draw a served model for the row."
const NOT_MOVED := "The served model of the row has its first place already."

## The tooltip of "Scale in the hand" for a row whose served model draws.
const SERVED_SCALE_TIP := "The largest axis of the scale of the served model in the hand. " \
	+ "A change scales the whole model, on each stand."

## The first choice of the color list of a color role: the look gives the
## role no color, and the palette gives it one.
const REMOVE_ROLE := "(the color of the palette)"

## The first choice of the color list of a color role of a tier.
const OF_THE_BASE := "(the color of the base look)"

## The mark of a color role of a tier that has a color of its own.
const OWN_MARK := "* "

const IMPORT_TITLE := "Import a model file for the row"

## The titles of the folds of this panel. The dock keeps the state of each
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
	"Fit served model to look": "Take the moved place of the served model away. The model " \
		+ "then takes the box of the worn look, or of the slot shape, again.",
}

## The files that the model pipeline reads. A `.glb` goes in as it is. Each
## other one goes through Blender.
const IMPORT_FILTERS := ["*.glb, *.gltf ; glTF", "*.fbx, *.obj, *.blend ; Through Blender"]

const HIDE_COLUMNS := 2

var _note := Label.new()
var _new_look: Button
var _remove_look: Button
var _copy: Button
var _tier: Button
var _add_role: Button
var _copy_from := OptionButton.new()
var _colors := GridContainer.new()
var _new_role := LineEdit.new()
var _hides := GridContainer.new()
var _model_key := LineEdit.new()
var _author := LineEdit.new()
var _import: Button
var _model_parts: Button
var _served_fit: Button
var _served_scale: SpinBox
var _open_dialog := FileDialog.new()
var _present_line := Label.new()
var _present_offset: HBoxContainer
var _present_turn: HBoxContainer
var _present_scale: SpinBox

## Fold title -> the fold.
var _folds := {}

var _catalog: FigureCatalog
var _rig: FigureRig
var _looks := {}
var _models: FigureModels
var _palette: FigurePalette
var _presentation: ModelPresentation

## The key of the row: an item key, or a slot for a slot shape row.
var _key := ""

## The key of the served model whose presentation the fields show, or "".
var _presented := ""

## The regions of the hide list, the rows of the color table, and the
## models of the look, each as one text.
var _shown_regions := ""
var _shown_colors := ""
var _shown_model := ""


func _init() -> void:
	_add_fold(FOLD_LOOK, _look_rows())
	_add_fold(FOLD_COLORS, _color_rows())
	_add_fold(FOLD_HIDES, _hide_rows())
	_add_fold(FOLD_MODEL, _model_rows())
	# A dialog is a window, not a row of a fold.
	add_child(_open_dialog)


## One fold of this panel, closed at first.
func _add_fold(title: String, rows: Array) -> void:
	_folds[title] = FigureFields.fold(title, FigureFields.column(rows), false)
	add_child(_folds[title])


## The folds of this panel: title -> the fold.
func folds() -> Dictionary:
	return _folds.duplicate()


## Show the look of one row.
##
## - `catalog` tells a slot shape row from an item row.
## - `rig` gives the regions of the hide list.
## - `looks` is key -> [FigureLook], for each worn look of the store.
## - `key` is the row: an item key, a slot, or "" for no row.
## - `models` gives the models of the served tree.
## - `palette` gives the named colors of each color list.
## - `presentation` gives the offset, the turn, and the scale of a served
##   model. Null for the table of [ModelRegistry].
func set_content(catalog: FigureCatalog, rig: FigureRig, looks: Dictionary, key: String,
		models: FigureModels = null, palette: FigurePalette = null,
		presentation: ModelPresentation = null) -> void:
	_catalog = catalog
	_rig = rig
	_looks = looks
	_key = key
	_models = models
	_palette = palette
	_presentation = presentation

	var look: FigureLook = _looks.get(_key)

	_fill_copy_list()
	_note.text = _note_text(look)
	_show_colors(look)
	_show_hides(look)
	_show_model(look)
	_show_served_scale()
	_show_presentation()
	_enable_look_buttons(look)


## The key of the worn look that the panel edits: the row when it has a
## worn look, or "".
func edited_look() -> String:
	return _key if _looks.has(_key) else ""


## True when the look of the row is a tier: it has no part of its own.
func is_tier() -> bool:
	var look: FigureLook = _looks.get(_key)

	return look != null and not look.base().is_empty()


## True when the figure draws the served model of the row in place of its
## worn look ([FigureOutfit]). A slot shape row has no served model.
func serves_model() -> bool:
	if _catalog == null or _rig == null or _key.is_empty() or _catalog.has_slot(_key):
		return false

	var source := FigureOutfit.source_of(_rig, _slot_of(_key), _key, _looks, _models)

	return source == FigureOutfit.SOURCE_MODEL


## The served part that the stand draws for the row, as a part row
## ([method FigureOutfit.served_look]). It holds the bone and the place.
## An empty dictionary for a row with no served model.
func served_place() -> Dictionary:
	if not serves_model():
		return {}

	var drawn := FigureOutfit.served_look(_rig, _slot_of(_key), _key, _looks,
		_catalog.families(), _models)

	return drawn.part(FigureLook.SERVED_PART)


## The key of the look in the copy list, or "".
func copy_source() -> String:
	if _copy_from.selected < 0:
		return ""

	return _copy_from.get_item_metadata(_copy_from.selected)


## The key of the served model of one row, or "". The look of the row can
## name the model. If not, the key of the row is the model when the served
## tree has it.
static func presented_model(looks: Dictionary, models: FigureModels, key: String) -> String:
	var look: FigureLook = looks.get(key)

	if look != null and not look.model_keys().is_empty():
		return look.model_keys()[0]

	if models != null and models.has(key):
		return key

	return ""


## A build runs now: the import button is off until it ends, with the
## reason in its tooltip. The plugin calls this.
func set_importing(busy: bool) -> void:
	if busy:
		FigureFields.enable(_import, false, "A build runs now. Wait until it ends.")
	else:
		_show_model(_looks.get(_key))


## The asset key of the model of the row: the text of its field, or the
## key of the row for an empty field.
func model_key() -> String:
	var typed := _model_key.text.strip_edges()

	return _key if typed.is_empty() else typed


## Show an author in the field of the import form. The dock keeps the last
## one in its session file.
func set_author(author: String) -> void:
	_author.text = author


# ─── Building the panel ─────────────────────────────────────────────────────

## The rows of the Look fold: the note, and the look buttons.
func _look_rows() -> Array:
	_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_new_look = _look_button("New look", func() -> void:
		look_requested.emit(_key, _slot_of(_key)))
	_remove_look = _look_button("Remove look", func() -> void:
		look_removed.emit(_key))
	_copy = _look_button("Copy look", func() -> void:
		copy_requested.emit(_key, copy_source()))
	_tier = _look_button("Make tier", func() -> void:
		tier_requested.emit(_key, copy_source()))

	return [_note, _new_look, _remove_look,
		FigureFields.label("The look to copy, or the base of a tier"), _copy_from, _copy, _tier]


## A button of this panel, with its tooltip from [constant LOOK_TIPS].
func _look_button(text: String, action: Callable) -> Button:
	return FigureFields.button(text, action, LOOK_TIPS[text])


## The rows of the Colors fold: the color table, and the new role form.
func _color_rows() -> Array:
	_add_role = _look_button("Add color role", func() -> void:
		color_changed.emit(_key, _new_role.text.strip_edges(), _new_role_color()))
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
		model_parts_requested.emit(_key, model_key()))
	_served_fit = _look_button("Fit served model to look", func() -> void:
		served_fit_requested.emit(_key))
	_served_scale = FigureFields.spin(FigureLookEdits.SERVED_SCALE_LOW, PartEditor.SCALE_HIGH,
		FigureFields.LENGTH_STEP, 1.0)
	_served_scale.value_changed.connect(_send_served_scale)
	_model_key.placeholder_text = "The asset key of the model. Empty for the key of the row"
	_model_key.text_changed.connect(func(_text: String) -> void:
		_enable_model_buttons(_looks.get(_key)))
	_author.placeholder_text = "The author of the model file, for its source record"
	_open_dialog.title = IMPORT_TITLE
	_open_dialog.access = FileDialog.ACCESS_FILESYSTEM
	_open_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	_open_dialog.filters = PackedStringArray(IMPORT_FILTERS)
	_open_dialog.file_selected.connect(func(path: String) -> void:
		import_requested.emit(_key, model_key(), path, _author.text.strip_edges()))

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
		_author, _import, _model_parts, _served_fit,
		FigureFields.label("Scale in the hand (the whole served model, on each stand)"),
		_served_scale,
		FigureFields.label("Presentation of the served model on the ground, not in the hand"),
		_present_line,
		FigureFields.label("Offset, in units of the unit box"), _present_offset,
		FigureFields.label("Turn (degrees)"), _present_turn,
		FigureFields.label("Scale, a multiplier on the unit box"), _present_scale]


# ─── The look of the row ────────────────────────────────────────────────────

func _slot_of(key: String) -> String:
	if _catalog == null:
		return ""

	return key if _catalog.has_slot(key) else _catalog.slot_of(key)


## Send the presentation of the served model of the row, after a change of
## the field `field`.
func _send_presentation(field: String) -> void:
	if not _presented.is_empty():
		presentation_changed.emit(_presented, FigureFields.vector_of(_present_offset),
			FigureFields.vector_of(_present_turn), _present_scale.value, field)


## "Scale in the hand" changed: send the row, the served part that the
## stand draws now, and the new scale.
func _send_served_scale(size: float) -> void:
	var drawn := served_place()

	if not drawn.is_empty():
		served_scale_changed.emit(_key, drawn, size)


## Show the largest axis of the scale of the served model in the hand. A
## row with no served model has the field off.
func _show_served_scale() -> void:
	var drawn := served_place()
	var known := not drawn.is_empty()
	var size := FigureLookEdits.largest_scale(drawn) if known else 1.0

	_served_scale.set_value_no_signal(size)
	_served_scale.editable = known
	_served_scale.tooltip_text = SERVED_SCALE_TIP if known else NOT_SERVED


## Show the offset, the turn, and the scale of the served model of the row.
## A row with no served model has the fields off.
func _show_presentation() -> void:
	_presented = presented_model(_looks, _models, _key)

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


## The named color of a new color role of a look. It is the color of the
## role in the palette, or the generic color.
func _new_role_color() -> String:
	var role := _new_role.text.strip_edges()

	if _palette == null:
		return MeshPalette.GENERIC

	return _palette.roles().get(role, MeshPalette.GENERIC)


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
	var has_row := not _key.is_empty()

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
		hide_changed.emit(_key, region, pressed))

	return box


## The model field shows the model that the parts of the look name. It
## changes only with the row or with the models of the look, so a key that
## the author types stays.
func _show_model(look: FigureLook) -> void:
	var keys := PackedStringArray() if look == null else look.model_keys()
	var shown := _key + ":" + ",".join(keys)

	if shown != _shown_model:
		_shown_model = shown
		_model_key.text = "" if keys.is_empty() or keys[0] == _key else keys[0]

	_enable_model_buttons(look)


## The import and "Parts from model" need a row. For a row whose served
## model draws, they need another key in the model field also. "Fit served
## model to look" needs a served model with a moved place.
func _enable_model_buttons(look: FigureLook) -> void:
	var served := serves_model()
	var reason := NEEDS_ROW if _key.is_empty() else SERVED_WINS
	var usable := not _key.is_empty() and (model_key() != _key or not served)
	var moved := look != null and not look.served().is_empty()

	FigureFields.enable(_import, usable, reason)
	FigureFields.enable(_model_parts, usable, reason)
	FigureFields.enable(_served_fit, served and moved, NOT_MOVED if served else NOT_SERVED)


func _note_text(look: FigureLook) -> String:
	if _key.is_empty():
		return "No row is selected."

	if serves_model():
		return "The figure draws the served model of %s, in place of the worn look. " % _key \
			+ "The worn look, or the slot shape, stands in while the model is not in hand. " \
			+ "It also gives the model its first place. Click the model on a stand to move it. " \
			+ "Scale in the hand, in the Model fold, scales the whole model."

	if look != null and not look.base().is_empty():
		var problem := look.base_problem(_looks)
		var text := "%s is a tier of %s. It has the parts of that look, so select " \
			% [_key, look.base()] + "the row of that look to change a part."

		return text if problem.is_empty() else "%s It draws no part now: %s." % [text, problem]

	if look != null:
		return "%s has a worn look." % _key

	if _catalog != null and _catalog.has_slot(_key):
		return "%s has no slot shape. The figure shows the family shape of each item." % _key

	return "%s has no worn look. The figure shows the slot shape of its slot, or the " \
		% _key + "family shape of the item."


## Show one row for each color role that the look can give a color to.
## [method FigureLookEdits.roles_of_look] gives the roles. They come from the
## color table, from the shapes, and from the surfaces of the models.
##
## The rows stay while the roles and the color names stay. Thus, a list
## keeps the focus through a change. A tier shows each role of its base
## also. A mark is on each role of a tier that has a color of its own.
func _show_colors(look: FigureLook) -> void:
	var tier := look != null and not look.base().is_empty()
	var drawn: FigureLook = null if look == null else look.resolved(_looks)
	var shown: Dictionary = {} if drawn == null else drawn.colors()
	var roles: Array = [] if drawn == null \
		else Array(FigureLookEdits.roles_of_look(drawn, _models, _palette))
	var names := FigurePaletteEdits.color_choices(_palette)
	var labels := PackedStringArray()

	for role: String in roles:
		labels.append((OWN_MARK if tier and look.colors().has(role) else "") + role)

	var wanted := "%s|%s|%s" % [",".join(labels), ",".join(names), tier]

	if wanted != _shown_colors:
		_shown_colors = wanted

		for child: Node in _colors.get_children():
			_colors.remove_child(child)
			child.queue_free()

		for index in roles.size():
			_colors.add_child(FigureFields.cell_label(labels[index]))
			_colors.add_child(_new_color_list(roles[index], names,
				OF_THE_BASE if tier else REMOVE_ROLE))

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
			color_removed.emit(_key, role)
		else:
			color_changed.emit(_key, role, list.get_item_text(index)))

	return list
