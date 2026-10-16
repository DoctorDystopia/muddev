@tool
class_name FigurePartsPanel
extends VBoxContainer
## The parts of one worn look, and the shape list of each part: the editor
## that the Body tab and the Gear tab of the figure workbench share
## (DESIGN-0014 section 8.6).
##
## A body is a worn look, so one panel edits a body and the look of an
## item. [FigureBodyPanel] is this panel with the rows of a body above it.
## [FigureGearPanel] holds one below its item list.
##
## This panel changes no worn look itself. Each control sends a signal, and
## the plugin makes the change through [FigurePartEdits] and the undo history.
## A signal names the part, not the look. The plugin knows which look each
## tab shows.
##
## ## The fields of a shape
##
## [constant FigureShapeEdits.SHAPE_FIELDS] names the fields of each shape, and
## [constant FigureShapeEdits.FIELD_KINDS] names the control of each field. A new
## key of the shape vocabulary is one row in each table, with no edit here.
##
## An angle shows in degrees. The file holds radians.
##
## ## The fit of a body type (Phase W4)
##
## The place fields show the place of the part on the body type of the
## rig. "Own place on this body type" gives the part a fit row for that
## body type, and the fields then change that row only. "Fit each part from
## the bone lengths" makes the rows from the two rigs. The Body tab hides
## the two controls ([member fit_controls]): a body serves one body type.
##
## ## A part with a model (Phase W4)
##
## A line below the part list names the model and the node of the selected
## part, and each color role of that node.
##
## ## A copy, and the other side (Phase W6)
##
## "Copy the selected part" and "Copy the selected shape" make a second one
## at the same place. "Make the part of the other side" makes the mirror
## picture of a part on the bone of the other side
## ([method FigurePartEdits.mirror_part]). Each row of the color list of a
## shape has a mark in its color.

signal part_chosen(part_name: String)
signal part_requested(bone: String)
signal part_removed(part_name: String)

## "Copy the selected part", and "Make the part of the other side".
signal part_copied(part_name: String)
signal part_mirrored(part_name: String)

## "Copy the selected shape".
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

const PART_LIST_HEIGHT := 200.0
const SHAPE_LIST_HEIGHT := 90.0

## The choice of the region list for a part in no region.
const NO_REGION := "(no region)"

## The range of a size field and of a count field of a shape.
const SIZE_HIGH := 5.0
const COUNT_LOW := 1.0
const COUNT_HIGH := 64.0

const SCALE_LOW := 0.01
const SCALE_HIGH := 20.0

const FIT_TEXT := "Own place on this body type (the fit)"
const FIT_ALL_TEXT := "Fit each part from the bone lengths"

## What the model line says for a part with no model.
const NO_MODEL := "The part draws its shape list."

## The title of the fold that holds the part editor. The dock keeps the fold
## state by this title.
const FOLD_PARTS := "Parts"

## What the tooltip of a control says when it needs a part.
const NEEDS_PART := "Select a part first."

## False on the Body tab: the fit controls do not show.
var fit_controls := true:
	set(value):
		fit_controls = value
		_fit.visible = value
		_fit_all.visible = value

## The fold that holds each row of the part editor. A panel that extends
## this one puts its own rows before it.
var _fold: FoldableContainer

## The column inside the fold.
var _column := VBoxContainer.new()

var _parts := ItemList.new()
var _model_line := Label.new()
var _fit := CheckBox.new()
var _fit_all: Button
var _remove_part: Button
var _copy_part: Button
var _mirror_part: Button
var _add_shape: Button
var _remove_shape: Button
var _copy_shape: Button
var _new_bone := OptionButton.new()
var _name := LineEdit.new()
var _bone := OptionButton.new()
var _region := OptionButton.new()
var _place_position: HBoxContainer
var _place_rotation: HBoxContainer
var _place_scale: HBoxContainer
var _shapes := ItemList.new()
var _new_kind := OptionButton.new()
var _fields := VBoxContainer.new()

var _rig: FigureRig
var _look: FigureLook
var _models: FigureModels
var _palette: FigurePalette
var _selected := ""

## Field name -> the control of that field, for the shown shape.
var _field_controls := {}

## The fields that the panel shows, as one text.
var _shown_fields := ""

## The rows of the part list and of the shape list, each as one text.
var _shown_parts := ""
var _shown_shapes := ""


func _init() -> void:
	_fold = FigureFields.fold(FOLD_PARTS, _column)
	add_child(_fold)
	_build_part_rows()
	_build_place_rows()
	_build_shape_rows()


## The folds of this panel: title -> the fold. The dock keeps the state of
## each one in the session file.
func folds() -> Dictionary:
	return {FOLD_PARTS: _fold}


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

	_fill_lists()
	_fill_parts()
	_show_part()
	_show_shapes()
	_show_shape()


func selected_part() -> String:
	return _selected


## Select a shape of the selected part by its index. The panel sends no
## signal.
func select_shape(shape_index: int) -> void:
	if shape_index >= 0 and shape_index < _shapes.item_count:
		_shapes.select(shape_index)
		_show_shape()


## The bone of the list above "Add a part on this bone", or "".
func new_part_bone() -> String:
	return FigureFields.text_of(_new_bone)


## Select a part of the list. The panel sends no signal.
func select_part(part_name: String) -> void:
	if _look == null or _look.part(part_name).is_empty():
		part_name = ""

	if part_name == _selected:
		return

	_selected = part_name
	_shapes.deselect_all()
	_fill_parts()
	_show_part()
	_show_shapes()
	_show_shape()


## The index of the selected shape, or -1.
func selected_shape() -> int:
	var rows := _shapes.get_selected_items()

	return -1 if rows.is_empty() else rows[0]


# ─── Building the panel ─────────────────────────────────────────────────────

func _build_part_rows() -> void:
	_parts.custom_minimum_size.y = PART_LIST_HEIGHT
	_parts.item_selected.connect(func(row: int) -> void:
		select_part(_parts.get_item_metadata(row))
		part_chosen.emit(_selected))
	_model_line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_column.add_child(FigureFields.label("Parts (name, bone, region)"))
	_column.add_child(_parts)
	_column.add_child(_model_line)
	_column.add_child(_new_bone)
	_column.add_child(FigureFields.button("Add part", func() -> void:
		part_requested.emit(FigureFields.text_of(_new_bone)),
		"Add a part on the bone of the list above."))
	_remove_part = FigureFields.button("Remove part", func() -> void:
		part_removed.emit(_selected), "Remove the selected part.")
	_copy_part = FigureFields.button("Copy part", func() -> void:
		part_copied.emit(_selected), "Make a second part at the same place.")
	_mirror_part = FigureFields.button("Mirror part", func() -> void:
		part_mirrored.emit(_selected),
		"Make the part of the other side: the mirror picture, on the bone of the other side.")
	_column.add_child(_remove_part)
	_column.add_child(_copy_part)
	_column.add_child(_mirror_part)


## A new name goes out on Enter, and also when the field loses the focus
## with another text in it. A click on another control then does not drop
## the typed name.
func _send_rename() -> void:
	var text := _name.text.strip_edges()

	if _name.editable and not _selected.is_empty() and text != _selected:
		part_renamed.emit(_selected, text)


func _build_place_rows() -> void:
	_name.text_submitted.connect(func(_text: String) -> void: _send_rename())
	_name.focus_exited.connect(_send_rename)
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

	for pair: Array in [["Name of the selected part (Enter to rename)", _name],
			["Bone (the part stays where it is)", _bone], ["Region", _region],
			["Position on the bone", _place_position],
			["Rotation in degrees", _place_rotation],
			["Scale", _place_scale]]:
		_column.add_child(FigureFields.label(pair[0]))
		_column.add_child(pair[1])

	_column.add_child(_fit)
	_column.add_child(_fit_all)


func _build_shape_rows() -> void:
	_shapes.custom_minimum_size.y = SHAPE_LIST_HEIGHT
	_shapes.item_selected.connect(func(_row: int) -> void: _show_shape())
	_column.add_child(FigureFields.label("Shape list of the selected part"))
	_column.add_child(_shapes)
	FigureFields.fill(_new_kind, FigureShapeEdits.SHAPE_FIELDS.keys())
	_column.add_child(_new_kind)
	_add_shape = FigureFields.button("Add shape", func() -> void:
		shape_requested.emit(_selected, FigureFields.text_of(_new_kind)),
		"Add a shape of the kind in the list above to the selected part.")
	_remove_shape = FigureFields.button("Remove shape", func() -> void:
		shape_removed.emit(_selected, selected_shape()), "Remove the selected shape.")
	_copy_shape = FigureFields.button("Copy shape", func() -> void:
		shape_copied.emit(_selected, selected_shape()),
		"Make a second shape at the same place.")
	_column.add_child(_add_shape)
	_column.add_child(_remove_shape)
	_column.add_child(_copy_shape)
	_column.add_child(_fields)


## Each button that needs a part is off while no part is selected, with the
## reason in its tooltip.
func _enable_part_buttons() -> void:
	for button: Button in [_remove_part, _copy_part, _mirror_part, _add_shape, _remove_shape,
			_copy_shape]:
		FigureFields.enable(button, not _selected.is_empty(), NEEDS_PART)


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


## Fill the part list. A look with the same rows keeps the list, so a drag
## of a part does not move the scroll bar.
func _fill_parts() -> void:
	var lines := PackedStringArray()
	var rows: Array = [] if _look == null else _look.parts()

	for row: Dictionary in rows:
		lines.append("%s   %s   %s" % [row["name"], row["bone"], row["region"]])

	if "\n".join(lines) != _shown_parts:
		_shown_parts = "\n".join(lines)
		_parts.clear()

		for index in rows.size():
			_parts.add_item(lines[index])
			_parts.set_item_metadata(index, rows[index]["name"])

	_parts.deselect_all()

	for index in rows.size():
		if rows[index]["name"] == _selected:
			_parts.select(index)


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
	_model_line.visible = not row.is_empty()
	_enable_part_buttons()


## The line of the selected part: its model, its node, and the color roles
## of that node. A role is the name of a material of the model.
func _model_text(row: Dictionary) -> String:
	var model_key: String = row.get("model", "")
	var node_name: String = row.get("node", "")

	if model_key.is_empty():
		return NO_MODEL

	if _models == null or not _models.has_node(model_key, node_name):
		return "Model %s, node %s: not in the served tree. The part draws its shape list." \
			% [model_key, node_name]

	return "Model %s, node %s. Color roles: %s." % [model_key, node_name,
		", ".join(_models.material_names(model_key, node_name))]


## Fill the shape list of the selected part. The list keeps its selected
## row when the part still has that row.
func _show_shapes() -> void:
	var kept := selected_shape()
	var shapes: Array = [] if _look == null else _look.part(_selected).get("shapes", [])
	var lines := PackedStringArray()

	for shape: Dictionary in shapes:
		lines.append("%s   %s" % [shape["shape"], shape.get("color", "")])

	if _selected + "\n" + "\n".join(lines) == _shown_shapes:
		return

	_shown_shapes = _selected + "\n" + "\n".join(lines)
	_shapes.clear()

	for line: String in lines:
		_shapes.add_item(line)

	if kept >= 0 and kept < shapes.size():
		_shapes.select(kept)
	elif not shapes.is_empty():
		_shapes.select(0)


## Show the fields of the selected shape. The controls stay while the
## fields stay, so a field keeps the focus through a change.
func _show_shape() -> void:
	var shape := _shown_shape()
	var fields: Array = [] if shape.is_empty() else FigureShapeEdits.fields_of(shape)
	var wanted := ",".join(fields) + ":" + ",".join(_color_roles()) + ":" \
		+ ",".join(FigurePaletteEdits.finish_choices(_palette))

	if wanted != _shown_fields:
		_shown_fields = wanted
		_field_controls.clear()

		for child: Node in _fields.get_children():
			_fields.remove_child(child)
			child.queue_free()

		for field: String in fields:
			_field_controls[field] = _new_field(field)
			_fields.add_child(FigureFields.label(_field_title(field)))
			_fields.add_child(_field_controls[field])

	for field: String in fields:
		_set_field(field, FigureShapeEdits.shape_value(shape, field))


## The selected shape of the selected part, or an empty dictionary.
func _shown_shape() -> Dictionary:
	var index := selected_shape()
	var shapes: Array = [] if _look == null else _look.part(_selected).get("shapes", [])

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

	var length :=FigureFields.spin(0.0, SIZE_HIGH, FigureFields.LENGTH_STEP)

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
