@tool
class_name PartEditor
extends VBoxContainer
## The part editor: the parts of one worn look, the shape list of each
## part, and the fields of the selected part and shape (DESIGN-0014
## section 22).
##
## The Gear dock is its home. The Body tab and the Families tab of the
## Figure dock embed the same editor: [FigureBodyPanel] and
## [FigureFamiliesPanel] extend it, and each one puts its own rows above.
## A body and a family shape are worn looks, so one editor serves the
## three.
##
## ## The tree
##
## One tree holds each part, and below each part its shapes. A click on a
## part row selects the node of the part in the 3D view, and the Godot
## tools then move the part on its bone. A click on a shape row selects
## the node of that shape, and the tools move the shape in the space of
## its part. The workbench writes each move into the look.
##
## ## The toolbar
##
## Two rows of buttons sit above the tree. The first row acts on a part:
## Add part (on the bone of the list), Copy part, Mirror part, and Remove
## part. The second row adds one shape of each kind, with one button for
## each kind of [constant FigureShapeEdits.SHAPE_FIELDS], then Copy shape
## and Remove shape. A new kind of shape is one row of that table, and the
## toolbar grows with no edit here.
##
## While the tree has the focus, Delete removes the selected row, and
## Ctrl+D copies it.
##
## ## The two grids
##
## Below the tree, a grid of two columns shows the part: its name, its
## bone, its region, its place on the bone, and its fit. A second grid
## shows the selected shape: the fields of its kind, then the fields of
## each shape. A label is on the left of each row, and the control is on
## the right. An angle shows in degrees. The file holds radians.
##
## [constant FigureShapeEdits.SHAPE_FIELDS] names the fields of each
## shape, and [constant FigureShapeEdits.FIELD_KINDS] names the control of
## each field. A new key of the shape vocabulary is one row in each table,
## with no edit here.
##
## This panel changes no worn look itself. Each control sends a signal,
## and the plugin makes the change through [FigurePartEdits] and the undo
## history. A signal names the part, not the look. The plugin knows which
## look each editor shows.
##
## ## The fit of a body type (Phase W4)
##
## The place fields show the place of the part on the body type of the
## rig. "Own place on this body type" gives the part a fit row for that
## body type, and the fields then change that row only. "Fit from bone
## lengths" makes the rows from the two rigs. The Body tab hides the two
## controls ([member fit_controls]): a body serves one body type.
##
## ## A part with a model (Phase W4, DESIGN-0014 section 20)
##
## The Part model fold names the model and the node of the selected part,
## and each color role of that node. "Import model for part" sends a file.
## "Part from served model" uses a model that the served tree has. "Shape
## list again" takes the model away.

signal part_chosen(part_name: String)

## A shape row of the tree is selected: the plugin selects its node.
signal shape_chosen(part_name: String, shape_index: int)
signal part_requested(bone: String)
signal part_removed(part_name: String)

## "Copy part", and "Mirror part".
signal part_copied(part_name: String)
signal part_mirrored(part_name: String)

## "Copy shape".
signal shape_copied(part_name: String, shape_index: int)
signal part_renamed(part_name: String, new_name: String)
signal part_bone_changed(part_name: String, bone: String)
signal part_region_changed(part_name: String, region: String)

## `field` names the place field that changed, for example "scale y". The
## label of a merged undo entry carries it. Thus a drag of one field and
## then a drag of another field stay two entries.
signal part_placed(part_name: String, xform: Transform3D, field: String)
signal part_fit_changed(part_name: String, fitted: bool)
signal fit_requested
signal shape_requested(part_name: String, kind: String)
signal shape_removed(part_name: String, shape_index: int)
signal shape_edited(part_name: String, shape_index: int, field: String, value: Variant)

## The model of one part. "Import model for part" sends the file. "Part
## from served model" uses a model that the served tree has. "Shape list
## again" takes the model away.
signal part_model_import_requested(part_name: String, model_key: String, path: String)
signal part_model_requested(part_name: String, model_key: String)
signal part_model_cleared(part_name: String)

const TREE_HEIGHT := 240.0

## The columns of the tree.
const COLUMN_NAME := 0
const COLUMN_BONE := 1
const COLUMN_REGION := 2
const COLUMN_TITLES := ["Part / shape", "Bone / kind", "Region / color"]

## How a shape row of the tree names itself.
const SHAPE_ROW := "shape %d"

## The text of the button that adds one shape, with the kind after it.
const ADD_SHAPE_TEXT := "+ %s"

## The choice of the region list for a part in no region.
const NO_REGION := "(no region)"

## The range of a size field and of a count field of a shape.
const SIZE_HIGH := 5.0
const COUNT_LOW := 1.0
const COUNT_HIGH := 64.0

const SCALE_LOW := 0.01
const SCALE_HIGH := 20.0

const FIT_TEXT := "Own place on this body type (the fit)"
const FIT_ALL_TEXT := "Fit each part from the bone lengths of the other body type."

## What the model line says for a part with no model.
const NO_MODEL := "The part draws its shape list."

const PART_IMPORT_TITLE := "Import a model file for the selected part"

## The titles of the two folds of the editor. The dock keeps the fold state
## by the title.
const FOLD_PARTS := "Parts"
const FOLD_MODEL := "Part model"

## What the tooltip of a control says when it needs a part or a shape.
const NEEDS_PART := FigurePartEdits.NO_PART
const NEEDS_SHAPE := "Select a shape first."

## What the shape heading says with no shape.
const NO_SHAPE := "No shape is selected."

## The heading of the shape grid: the index, the kind, and the part.
const SHAPE_HEADING := "Shape %d (%s) of %s"

## The tooltip of each button of the toolbar, by its text.
const TIPS := {
	"Add part": "Add a part on the bone of the list.",
	"Copy part": "Make a second part at the same place.",
	"Mirror part": "Make the part of the other side: the mirror picture, on the bone of " \
		+ "the other side.",
	"Remove part": "Remove the selected part, with each shape of it. Delete does the same.",
	"Copy shape": "Make a second shape at the same place. Ctrl+D does the same.",
	"Remove shape": "Remove the selected shape. Delete does the same on a shape row.",
	"Import model for part": "Import a model file for the selected part only. Each other " \
		+ "part stays.",
	"Part from served model": "Give the selected part a node of the served model of the field.",
	"Shape list again": "Take the model away from the selected part. Its shape list draws.",
}

## False on the Body tab: the fit controls do not show.
var fit_controls := true:
	set(value):
		fit_controls = value

		for control: Control in [_fit, _fit_label, _fit_all, _fit_all_label]:
			control.visible = value

## The fold that holds each row of the part editor. A panel that extends
## this one puts its own rows before it.
var _fold: FoldableContainer

## The column inside the fold.
var _column := VBoxContainer.new()

var _tree := Tree.new()
var _model_fold: FoldableContainer
var _model_line := Label.new()
var _part_model_key := LineEdit.new()
var _part_dialog := FileDialog.new()
var _import_part: Button
var _use_model: Button
var _clear_model: Button
var _fit := CheckBox.new()
var _fit_label := FigureFields.cell_label("Fit")
var _fit_all: Button
var _fit_all_label := FigureFields.cell_label("")
var _remove_part: Button
var _copy_part: Button
var _mirror_part: Button
var _remove_shape: Button
var _copy_shape: Button
var _new_bone := OptionButton.new()
var _name := LineEdit.new()
var _bone := OptionButton.new()
var _region := OptionButton.new()
var _place_position: HBoxContainer
var _place_rotation: HBoxContainer
var _place_scale: HBoxContainer
var _shape_heading := Label.new()
var _fields := GridContainer.new()

## Shape kind -> the button that adds one.
var _shape_buttons := {}

var _rig: FigureRig
var _look: FigureLook
var _models: FigureModels
var _palette: FigurePalette

## The selected part, or "".
var _selected := ""

## The selected shape row of the tree, or -1 for the part row.
var _shape_row := -1

## True while the editor selects a row by code: the tree then sends
## nothing.
var _filling := false

## Field name -> the control of that field, for the shown shape.
var _field_controls := {}

## The fields that the editor shows, as one text.
var _shown_fields := ""

## The rows of the tree, as one text.
var _shown_tree := ""


func _init() -> void:
	_fold = FigureFields.fold(FOLD_PARTS, _column)
	add_child(_fold)
	_build_toolbar()
	_build_tree()
	_build_part_grid()
	_build_model_fold()
	_build_shape_grid()
	# A dialog is a window, not a row of a fold.
	add_child(_part_dialog)


## The folds of this editor: title -> the fold. The dock keeps the state
## of each one in the session file.
func folds() -> Dictionary:
	return {FOLD_PARTS: _fold, FOLD_MODEL: _model_fold}


## Show the parts of one worn look.
##
## - `rig` gives the bones and the regions.
## - `look` is null for no look.
## - `models` gives the color roles of a part with a model.
## - `palette` gives the names of the color list of a shape.
func set_content(rig: FigureRig, look: FigureLook, models: FigureModels = null,
		palette: FigurePalette = null) -> void:
	_rig = rig
	_look = look
	_models = models
	_palette = palette

	if _look == null or _look.part(_selected).is_empty():
		_selected = ""
		_shape_row = -1

	if _shape_row >= _shape_count():
		_shape_row = -1

	_fill_lists()
	_fill_tree()
	_show_part()
	_show_shape()


func selected_part() -> String:
	return _selected


## The index of the shape that the shape grid shows, or -1: the selected
## shape row, else the first shape of the selected part.
func selected_shape() -> int:
	if _shape_row >= 0:
		return _shape_row

	return 0 if _shape_count() > 0 else -1


## True when a shape row of the tree is selected, and not a part row.
func shape_row_selected() -> bool:
	return _shape_row >= 0


## The number of parts in the tree.
func part_count() -> int:
	return 0 if _look == null else _look.parts().size()


## Select a part of the tree. The editor sends no signal.
func select_part(part_name: String) -> void:
	if _look == null or _look.part(part_name).is_empty():
		part_name = ""

	if part_name == _selected and _shape_row < 0:
		return

	_selected = part_name
	_shape_row = -1
	_fill_tree()
	_show_part()
	_show_shape()


## Select a shape of the selected part by its index. The editor sends no
## signal.
func select_shape(shape_index: int) -> void:
	if shape_index < 0 or shape_index >= _shape_count():
		return

	_shape_row = shape_index
	_fill_tree()
	_show_shape()


## The bone of the list beside "Add part", or "".
func new_part_bone() -> String:
	return FigureFields.text_of(_new_bone)


## The asset key of the model of the selected part: the text of the field,
## or `<look key>_<part name>`.
func part_model_key() -> String:
	var typed := _part_model_key.text.strip_edges()

	if not typed.is_empty() or _look == null or _selected.is_empty():
		return typed

	return "%s_%s" % [_look.key(), _selected]


# ─── Building the editor ────────────────────────────────────────────────────

## The two rows of buttons above the tree.
func _build_toolbar() -> void:
	var parts := HFlowContainer.new()
	var shapes := HFlowContainer.new()

	_remove_part = _tool_button("Remove part", func() -> void: part_removed.emit(_selected))
	_copy_part = _tool_button("Copy part", func() -> void: part_copied.emit(_selected))
	_mirror_part = _tool_button("Mirror part", func() -> void: part_mirrored.emit(_selected))
	_new_bone.tooltip_text = "The bone of a new part."

	for control: Control in [_new_bone, _tool_button("Add part", func() -> void:
			part_requested.emit(FigureFields.text_of(_new_bone))), _copy_part, _mirror_part,
			_remove_part]:
		parts.add_child(control)

	for kind: String in FigureShapeEdits.SHAPE_FIELDS:
		_shape_buttons[kind] = FigureFields.button(ADD_SHAPE_TEXT % kind, func() -> void:
			shape_requested.emit(_selected, kind), "Add a %s to the selected part." % kind)
		shapes.add_child(_shape_buttons[kind])

	_copy_shape = _tool_button("Copy shape", func() -> void:
		shape_copied.emit(_selected, selected_shape()))
	_remove_shape = _tool_button("Remove shape", func() -> void:
		shape_removed.emit(_selected, selected_shape()))
	shapes.add_child(_copy_shape)
	shapes.add_child(_remove_shape)
	_column.add_child(parts)
	_column.add_child(shapes)


## A button of the toolbar, with its tooltip from [constant TIPS].
func _tool_button(text: String, action: Callable) -> Button:
	return FigureFields.button(text, action, TIPS[text])


func _build_tree() -> void:
	_tree.columns = COLUMN_TITLES.size()
	_tree.column_titles_visible = true
	_tree.hide_root = true
	_tree.custom_minimum_size.y = TREE_HEIGHT
	_tree.size_flags_vertical = Control.SIZE_EXPAND_FILL

	for column in COLUMN_TITLES.size():
		_tree.set_column_title(column, COLUMN_TITLES[column])
		_tree.set_column_expand(column, true)

	_tree.item_selected.connect(_on_tree_selected)
	_tree.gui_input.connect(_on_tree_input)
	_column.add_child(_tree)


## The grid of the selected part: one label and one control on each row.
func _build_part_grid() -> void:
	var grid := GridContainer.new()

	grid.columns = 2
	_name.text_submitted.connect(func(_text: String) -> void: _send_rename())
	_name.focus_exited.connect(_send_rename)
	_name.tooltip_text = "The name of the part. Enter renames it."
	_bone.tooltip_text = "The bone of the part. The part stays where it is."
	_bone.item_selected.connect(func(_index: int) -> void:
		part_bone_changed.emit(_selected, FigureFields.text_of(_bone)))
	_region.item_selected.connect(func(index: int) -> void:
		part_region_changed.emit(_selected, "" if index == 0 else FigureFields.text_of(_region)))
	_place_position = FigureFields.vector_row(FigureFields.LENGTH_LOW,
		FigureFields.LENGTH_HIGH, FigureFields.LENGTH_STEP,
		_on_place_changed.bind("position"), true)
	_place_rotation = FigureFields.vector_row(-FigureFields.ANGLE_LIMIT,
		FigureFields.ANGLE_LIMIT, FigureFields.ANGLE_STEP,
		_on_place_changed.bind("rotation"), true)
	_place_scale = FigureFields.vector_row(SCALE_LOW, SCALE_HIGH,
		FigureFields.LENGTH_STEP, _on_place_changed.bind("scale"), true)
	_fit.text = FIT_TEXT
	_fit.toggled.connect(func(pressed: bool) -> void:
		part_fit_changed.emit(_selected, pressed))
	_fit_all = FigureFields.button("Fit from bone lengths", fit_requested.emit, FIT_ALL_TEXT)

	for pair: Array in [["Name", _name], ["Bone", _bone], ["Region", _region],
			["Position", _place_position], ["Rotation (degrees)", _place_rotation],
			["Scale", _place_scale], [_fit_label, _fit], [_fit_all_label, _fit_all]]:
		grid.add_child(pair[0] if pair[0] is Control else FigureFields.cell_label(pair[0]))
		(pair[1] as Control).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		grid.add_child(pair[1])

	_column.add_child(FigureFields.label("Selected part"))
	_column.add_child(grid)


## The fold of the model of the selected part: a model file for this part
## only, the served model for this part, or the shape list again. The field
## gives the asset key of the model. An empty field gives
## [method part_model_key].
func _build_model_fold() -> void:
	_model_line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_part_model_key.placeholder_text = "The asset key of the model of the part. " \
		+ "Empty for <look>_<part>"
	_part_dialog.title = PART_IMPORT_TITLE
	_part_dialog.access = FileDialog.ACCESS_FILESYSTEM
	_part_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	_part_dialog.filters = PackedStringArray(GearLookPanel.IMPORT_FILTERS)
	_part_dialog.file_selected.connect(func(path: String) -> void:
		part_model_import_requested.emit(_selected, part_model_key(), path))
	_import_part = _tool_button("Import model for part", func() -> void:
		_part_dialog.popup_centered_ratio())
	_use_model = _tool_button("Part from served model", func() -> void:
		part_model_requested.emit(_selected, part_model_key()))
	_clear_model = _tool_button("Shape list again", func() -> void:
		part_model_cleared.emit(_selected))
	_model_fold = FigureFields.fold(FOLD_MODEL, FigureFields.column([_model_line,
		_part_model_key, _import_part, _use_model, _clear_model]), false)
	_column.add_child(_model_fold)


## The grid of the selected shape. Its rows come with the shape.
func _build_shape_grid() -> void:
	_shape_heading.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_fields.columns = 2
	_column.add_child(_shape_heading)
	_column.add_child(_fields)


## Each button that needs a part is off while no part is selected, with the
## reason in its tooltip. The two shape buttons need a shape also.
func _enable_buttons() -> void:
	var has_part := not _selected.is_empty()

	for button: Button in [_remove_part, _copy_part, _mirror_part, _import_part, _use_model,
			_clear_model]:
		FigureFields.enable(button, has_part, NEEDS_PART)

	for kind: String in _shape_buttons:
		FigureFields.enable(_shape_buttons[kind], has_part, NEEDS_PART)

	for button: Button in [_copy_shape, _remove_shape]:
		FigureFields.enable(button, selected_shape() >= 0, NEEDS_PART if not has_part \
			else NEEDS_SHAPE)


# ─── Showing a look ─────────────────────────────────────────────────────────

## The bone lists and the region list, from the rig.
func _fill_lists() -> void:
	var bones: Array = [] if _rig == null else Array(_rig.bone_names())
	var regions: Array = [NO_REGION]

	if _rig != null:
		var names := _rig.regions().keys()

		names.sort()
		regions.append_array(names)

	FigureFields.fill(_new_bone, bones)
	FigureFields.fill(_bone, bones)
	FigureFields.fill(_region, regions)

	if _new_bone.selected < 0 and _new_bone.item_count > 0:
		_new_bone.select(0)


## The shapes of the selected part.
func _shapes() -> Array:
	if _look == null or _selected.is_empty():
		return []

	return _look.part(_selected).get("shapes", [])


func _shape_count() -> int:
	return _shapes().size()


## Fill the tree: one row for each part, and one row below it for each
## shape. A look with the same rows keeps the tree, so a drag of a part
## does not move the scroll bar. The selected row follows the selection.
func _fill_tree() -> void:
	var rows: Array = [] if _look == null else _look.parts()
	var lines := PackedStringArray()

	for row: Dictionary in rows:
		lines.append("%s|%s|%s" % [row["name"], row["bone"], row["region"]])

		for shape: Dictionary in row.get("shapes", []):
			lines.append("  %s|%s" % [shape["shape"], shape.get("color", "")])

	if "\n".join(lines) != _shown_tree:
		_shown_tree = "\n".join(lines)
		_rebuild_tree(rows)

	_select_row()


func _rebuild_tree(rows: Array) -> void:
	_tree.clear()

	var root := _tree.create_item()

	for row: Dictionary in rows:
		var item := _tree.create_item(root)

		item.set_text(COLUMN_NAME, row["name"])
		item.set_text(COLUMN_BONE, row["bone"])
		item.set_text(COLUMN_REGION, row["region"])
		item.set_metadata(COLUMN_NAME, [row["name"]])

		var shapes: Array = row.get("shapes", [])

		for index in shapes.size():
			var child := _tree.create_item(item)

			child.set_text(COLUMN_NAME, SHAPE_ROW % index)
			child.set_text(COLUMN_BONE, shapes[index]["shape"])
			child.set_text(COLUMN_REGION, shapes[index].get("color", ""))
			child.set_metadata(COLUMN_NAME, [row["name"], index])


## Select the row of the selected part or shape, with no signal.
func _select_row() -> void:
	var wanted: Array = [] if _selected.is_empty() else [_selected]

	if _shape_row >= 0:
		wanted.append(_shape_row)

	_filling = true
	_tree.deselect_all()

	var item := _item_of(_tree.get_root(), wanted)

	if item != null:
		item.select(COLUMN_NAME)
		_tree.scroll_to_item(item)

	_filling = false


## The item with one metadata below `item`, or null.
func _item_of(item: TreeItem, wanted: Array) -> TreeItem:
	if item == null or wanted.is_empty():
		return null

	for child: TreeItem in item.get_children():
		if child.get_metadata(COLUMN_NAME) == wanted:
			return child

		var found := _item_of(child, wanted)

		if found != null:
			return found

	return null


## Show the selected part. The place is that of the body type of the rig,
## so it is the fit row when the part has one.
func _show_part() -> void:
	var body_key := "" if _rig == null else _rig.key()
	var row := {} if _look == null else _look.placed_row(_selected, body_key)
	var place := FigureLook.part_transform(row)
	var region: String = row.get("region", "")
	var fitted := _look != null and not _look.fit_row(body_key, _selected).is_empty()

	_name.text = _selected
	_name.editable = not row.is_empty()
	FigureFields.select_text(_bone, row.get("bone", ""))
	FigureFields.select_text(_region, NO_REGION if region.is_empty() else region)
	FigureFields.set_vector(_place_position, place.origin)
	FigureFields.set_vector(_place_rotation, _degrees(FigureJson.vector3(row.get("rotation"))))
	FigureFields.set_vector(_place_scale, FigureJson.vector3(row.get("scale"), Vector3.ONE))
	_fit.set_pressed_no_signal(fitted)
	_fit.disabled = row.is_empty()
	_model_line.text = _model_text(row)
	_enable_buttons()


## The line of the selected part: its model, its node, and the color roles
## of that node. A role is the name of a material of the model.
func _model_text(row: Dictionary) -> String:
	var model_key: String = row.get("model", "")
	var node_name: String = row.get("node", "")

	if row.is_empty():
		return NEEDS_PART

	if model_key.is_empty():
		return NO_MODEL

	if _models == null or not _models.has_node(model_key, node_name):
		return "Model %s, node %s: not in the served tree. The part draws its shape list." \
			% [model_key, node_name]

	return "Model %s, node %s. Color roles: %s." % [model_key, node_name,
		", ".join(_models.material_names(model_key, node_name))]


## Show the fields of the selected shape. The controls stay while the
## fields stay, so a field keeps the focus through a change.
func _show_shape() -> void:
	var shape := _shown_shape()
	var fields: Array = [] if shape.is_empty() else FigureShapeEdits.fields_of(shape)
	var wanted := ",".join(fields) + ":" + ",".join(_color_roles()) + ":" \
		+ ",".join(FigurePaletteEdits.finish_choices(_palette))

	_shape_heading.text = NO_SHAPE if shape.is_empty() \
		else SHAPE_HEADING % [selected_shape(), shape["shape"], _selected]

	if wanted != _shown_fields:
		_shown_fields = wanted
		_field_controls.clear()

		for child: Node in _fields.get_children():
			_fields.remove_child(child)
			child.queue_free()

		for field: String in fields:
			_field_controls[field] = _new_field(field)
			_fields.add_child(FigureFields.cell_label(_field_title(field)))
			_fields.add_child(_field_controls[field])

	for field: String in fields:
		_set_field(field, FigureShapeEdits.shape_value(shape, field))

	_enable_buttons()


## The shown shape of the selected part, or an empty dictionary.
func _shown_shape() -> Dictionary:
	var index := selected_shape()
	var shapes := _shapes()

	if index < 0 or index >= shapes.size():
		return {}

	return shapes[index]


## The names that a shape can have as its color. The list has each named
## color and each color role of the palette. It also has each color role
## of the color table of the look.
func _color_roles() -> Array:
	var roles := FigurePaletteEdits.color_choices(_palette)
	var more: Array = [] if _palette == null else Array(_palette.role_names())

	if _look != null:
		more.append_array(_look.colors().keys())

	for role: String in more:
		if not role in roles:
			roles.append(role)

	roles.sort()

	return roles


static func _field_title(field: String) -> String:
	if FigureShapeEdits.FIELD_KINDS[field] == FigureShapeEdits.FIELD_ANGLES:
		return field + " (degrees)"

	return field


## The control of one field of a shape.
func _new_field(field: String) -> Control:
	var send := func(value: Variant) -> void:
		shape_edited.emit(_selected, selected_shape(), field, value)
	var control := _field_control(field, send)

	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	return control


func _field_control(field: String, send: Callable) -> Control:
	match FigureShapeEdits.FIELD_KINDS[field]:
		FigureShapeEdits.FIELD_VECTOR:
			return FigureFields.vector_row(FigureFields.LENGTH_LOW, FigureFields.LENGTH_HIGH,
				FigureFields.LENGTH_STEP, send)
		FigureShapeEdits.FIELD_ANGLES:
			return FigureFields.vector_row(-FigureFields.ANGLE_LIMIT, FigureFields.ANGLE_LIMIT,
				FigureFields.ANGLE_STEP, func(degrees: Vector3) -> void:
					send.call(_radians(degrees)))
		FigureShapeEdits.FIELD_COUNT:
			var count := FigureFields.spin(COUNT_LOW, COUNT_HIGH, 1.0)

			count.value_changed.connect(func(value: float) -> void: send.call(int(value)))
			return count
		FigureShapeEdits.FIELD_FLAG:
			var flag := CheckBox.new()

			flag.toggled.connect(send)
			return flag
		FigureShapeEdits.FIELD_COLOR, FigureShapeEdits.FIELD_FINISH:
			return _new_choice(field, send)
		FigureShapeEdits.FIELD_SIGNED:
			var shift := FigureFields.spin(FigureFields.LENGTH_LOW, FigureFields.LENGTH_HIGH,
				FigureFields.LENGTH_STEP)

			shift.value_changed.connect(send)
			return shift

	var length := FigureFields.spin(0.0, SIZE_HIGH, FigureFields.LENGTH_STEP)

	length.value_changed.connect(send)

	return length


func _new_choice(field: String, send: Callable) -> OptionButton:
	var list := OptionButton.new()
	var names: Array = _color_roles()

	# The first choice of the finish is the finish of the named color.
	if FigureShapeEdits.FIELD_KINDS[field] == FigureShapeEdits.FIELD_FINISH:
		names = [FigureShapeEdits.FINISH_OF_COLOR] + FigurePaletteEdits.finish_choices(_palette)

	FigureFields.fill(list, names)
	list.item_selected.connect(func(_index: int) -> void:
		send.call(FigureFields.text_of(list)))

	return list


## Show one value in the control of its field. The control sends no change.
func _set_field(field: String, value: Variant) -> void:
	var control: Control = _field_controls[field]

	match FigureShapeEdits.FIELD_KINDS[field]:
		FigureShapeEdits.FIELD_VECTOR:
			FigureFields.set_vector(control, value)
		FigureShapeEdits.FIELD_ANGLES:
			FigureFields.set_vector(control, _degrees(value))
		FigureShapeEdits.FIELD_FLAG:
			(control as CheckBox).set_pressed_no_signal(value)
		FigureShapeEdits.FIELD_COLOR:
			FigureFields.select_text(control, str(value))
			FigureFields.mark_colors(control, _palette,
				{} if _look == null else _look.colors())
		FigureShapeEdits.FIELD_FINISH:
			FigureFields.select_text(control, str(value))
		_:
			(control as SpinBox).set_value_no_signal(value)


# ─── The signals of the controls ────────────────────────────────────────────

## The author selected a row of the tree: a part, or a shape of a part.
func _on_tree_selected() -> void:
	if _filling:
		return

	var item := _tree.get_selected()
	var wanted: Array = [] if item == null else item.get_metadata(COLUMN_NAME)

	if wanted.is_empty():
		return

	_selected = wanted[0]
	_shape_row = wanted[1] if wanted.size() > 1 else -1
	_show_part()
	_show_shape()

	if _shape_row >= 0:
		shape_chosen.emit(_selected, _shape_row)
	else:
		part_chosen.emit(_selected)


## Delete removes the selected row, and Ctrl+D copies it.
func _on_tree_input(event: InputEvent) -> void:
	var key := event as InputEventKey

	if key == null or not key.pressed or key.echo or _selected.is_empty():
		return

	if key.keycode == KEY_DELETE:
		_tree.accept_event()

		if _shape_row >= 0:
			shape_removed.emit(_selected, _shape_row)
		else:
			part_removed.emit(_selected)
	elif key.keycode == KEY_D and key.ctrl_pressed:
		_tree.accept_event()

		if _shape_row >= 0:
			shape_copied.emit(_selected, _shape_row)
		else:
			part_copied.emit(_selected)


## A new name goes out on Enter, and also when the field loses the focus
## with another text in it. A click on another control then does not drop
## the typed name.
func _send_rename() -> void:
	var text := _name.text.strip_edges()

	if _name.editable and not _selected.is_empty() and text != _selected:
		part_renamed.emit(_selected, text)


## One of the nine place fields changed: send the place of the part, and
## the name of the field. `row_name` is bound at the row: position,
## rotation, or scale.
func _on_place_changed(_vector: Vector3, axis: int, row_name: String) -> void:
	if _selected.is_empty():
		return

	var turn := _radians(FigureFields.vector_of(_place_rotation))
	var basis := Basis.from_euler(turn).scaled_local(FigureFields.vector_of(_place_scale))

	part_placed.emit(_selected, Transform3D(basis, FigureFields.vector_of(_place_position)),
		"%s %s" % [row_name, FigureFields.AXIS_NAMES[axis]])


static func _degrees(radians: Vector3) -> Vector3:
	return Vector3(rad_to_deg(radians.x), rad_to_deg(radians.y), rad_to_deg(radians.z))


static func _radians(degrees: Vector3) -> Vector3:
	return Vector3(deg_to_rad(degrees.x), deg_to_rad(degrees.y), deg_to_rad(degrees.z))
