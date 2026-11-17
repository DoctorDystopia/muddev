@tool
class_name PictureFields
extends VBoxContainer
## The fields of the picture editor: one number field and one slider for
## each value of a picture pose ([PicturePose]).
##
## The author types a value or moves its slider. The two show one value.
## The zoom and the offsets are percents of the cell. The turns are degrees.
##
## The panel keeps the exact pose that it shows. A change of one field
## changes that value only. Thus, a drag in the view can give a value
## between two steps of a field, and a later change of another field keeps
## it.
##
## This panel changes no file. It sends the new row, and [PictureEditor]
## puts the row in the content of the picture file.

## Emitted after each change by the author, with the full row.
signal pose_changed(row: Dictionary)

const PERCENT := 100.0

## The step of each field, and the step of its arrows.
const FIELD_STEP := 0.1
const ARROW_STEP := 1.0

const LABEL_WIDTH := 96.0
const FIELD_WIDTH := 110.0

const FIELD_ZOOM := "zoom"
const FIELD_OFFSET_X := "offset_x"
const FIELD_OFFSET_Y := "offset_y"
const FIELD_TURN_X := "turn_x"
const FIELD_TURN_Y := "turn_y"
const FIELD_TURN_Z := "turn_z"

const SUFFIX_PERCENT := "%"
const SUFFIX_DEGREES := "deg"

## One row for each field: the key, the label, the lowest value, the highest
## value, and the suffix.
const ROWS := [
	[FIELD_ZOOM, "Zoom", PicturePose.ZOOM_LOW * PERCENT, PicturePose.ZOOM_HIGH * PERCENT,
		SUFFIX_PERCENT],
	[FIELD_OFFSET_X, "X offset", -PicturePose.OFFSET_LIMIT * PERCENT,
		PicturePose.OFFSET_LIMIT * PERCENT, SUFFIX_PERCENT],
	[FIELD_OFFSET_Y, "Y offset", -PicturePose.OFFSET_LIMIT * PERCENT,
		PicturePose.OFFSET_LIMIT * PERCENT, SUFFIX_PERCENT],
	[FIELD_TURN_X, "X angle", -PicturePose.TURN_LIMIT, PicturePose.TURN_LIMIT, SUFFIX_DEGREES],
	[FIELD_TURN_Y, "Y angle", -PicturePose.TURN_LIMIT, PicturePose.TURN_LIMIT, SUFFIX_DEGREES],
	[FIELD_TURN_Z, "Z angle", -PicturePose.TURN_LIMIT, PicturePose.TURN_LIMIT, SUFFIX_DEGREES],
]

const HELP := "A zoom of 100% fills the cell at each angle. The offset stops at the edge " \
	+ "of the cell, so a smaller zoom gives it more room. In the view: drag with the left " \
	+ "button to move the picture, drag with the right button to turn it, and turn the " \
	+ "wheel to zoom."

const RESET_TIP := "Give this item the default pose. The picture file then keeps no row for it."
const COPY_TIP := "Keep the pose of this item, for a paste on another item."
const PASTE_TIP := "Give this item the pose that Copy kept."
const NO_COPY := "Copy a pose first."
const NO_ITEM := "Pick an item first."

## Field key -> its number field. The slider of a field shares its value.
var _boxes := {}

var _reset: Button
var _copy: Button
var _paste: Button

## The exact pose that the fields show, as a full row.
var _row := PicturePose.default_row()

## The row that Copy kept, or empty.
var _copied := {}

var _enabled := false


func _init() -> void:
	var grid := GridContainer.new()

	grid.columns = 3
	add_child(grid)

	for row: Array in ROWS:
		_add_row(grid, row)

	var buttons := HBoxContainer.new()

	_reset = FigureFields.button("Reset pose", _on_reset, RESET_TIP)
	_copy = FigureFields.button("Copy pose", _on_copy, COPY_TIP)
	_paste = FigureFields.button("Paste pose", _on_paste, PASTE_TIP)
	buttons.add_child(_reset)
	buttons.add_child(_copy)
	buttons.add_child(_paste)
	add_child(buttons)
	add_child(FigureFields.label(HELP))
	set_enabled(false)


## Show a pose. The panel sends no change.
func show_pose(row: Dictionary) -> void:
	var offset := PicturePose.offset_of(row)
	var turn := PicturePose.turn_of(row)

	_row = PicturePose.row_from(PicturePose.zoom_of(row), offset, turn)
	_show(FIELD_ZOOM, PicturePose.zoom_of(row) * PERCENT)
	_show(FIELD_OFFSET_X, offset.x * PERCENT)
	_show(FIELD_OFFSET_Y, offset.y * PERCENT)
	_show(FIELD_TURN_X, turn.x)
	_show(FIELD_TURN_Y, turn.y)
	_show(FIELD_TURN_Z, turn.z)


## The pose of the fields, as a full row of the picture file.
func shown_pose() -> Dictionary:
	return _row.duplicate(true)


## Turn the fields on for an item, or off for no item.
func set_enabled(on: bool) -> void:
	_enabled = on

	for box: SpinBox in _boxes.values():
		box.editable = on

	FigureFields.enable(_reset, on, NO_ITEM)
	FigureFields.enable(_copy, on, NO_ITEM)
	FigureFields.enable(_paste, on and not _copied.is_empty(),
		NO_COPY if on else NO_ITEM)


## Type a value into one field, as the author does. For tests.
func type_value(field: String, value: float) -> void:
	(_boxes[field] as SpinBox).value = value


## Press one button by its text, as the author does. For tests.
func press(text: String) -> void:
	for button: Button in [_reset, _copy, _paste]:
		if button.text == text and not button.disabled:
			button.pressed.emit()


# ─── Private ────────────────────────────────────────────────────────────────

## One row of the grid: the label, the number field, and the slider.
func _add_row(grid: GridContainer, row: Array) -> void:
	var field: String = row[0]
	var label := FigureFields.cell_label(row[1])
	var box := FigureFields.spin(row[2], row[3], FIELD_STEP)
	var slider := HSlider.new()

	label.custom_minimum_size.x = LABEL_WIDTH
	box.suffix = row[4]
	box.custom_arrow_step = ARROW_STEP
	box.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	box.custom_minimum_size.x = FIELD_WIDTH
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER

	# The slider takes the range of the field. The two then show one value,
	# with one range and one step.
	box.share(slider)
	box.value_changed.connect(func(typed: float) -> void: _on_typed(field, typed))
	grid.add_child(label)
	grid.add_child(box)
	grid.add_child(slider)
	_boxes[field] = box


func _show(field: String, value: float) -> void:
	(_boxes[field] as SpinBox).set_value_no_signal(value)


## The author changed one field. Only that value of the pose changes.
func _on_typed(field: String, typed: float) -> void:
	var zoom := PicturePose.zoom_of(_row)
	var offset := PicturePose.offset_of(_row)
	var turn := PicturePose.turn_of(_row)

	match field:
		FIELD_ZOOM:
			zoom = typed / PERCENT
		FIELD_OFFSET_X:
			offset.x = typed / PERCENT
		FIELD_OFFSET_Y:
			offset.y = typed / PERCENT
		FIELD_TURN_X:
			turn.x = typed
		FIELD_TURN_Y:
			turn.y = typed
		FIELD_TURN_Z:
			turn.z = typed

	_row = PicturePose.row_from(zoom, offset, turn)
	pose_changed.emit(shown_pose())


func _on_reset() -> void:
	show_pose(PicturePose.default_row())
	pose_changed.emit(shown_pose())


func _on_copy() -> void:
	_copied = shown_pose()
	set_enabled(_enabled)


func _on_paste() -> void:
	if _copied.is_empty():
		return

	show_pose(_copied)
	pose_changed.emit(shown_pose())
