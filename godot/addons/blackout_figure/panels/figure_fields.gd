@tool
class_name FigureFields
extends RefCounted
## The small controls that each tab of the figure workbench uses: a number
## field, a row of three number fields for a vector, and a list of names.
##
## Requirement A3 of DESIGN-0014 says that each number has a field. These
## routines make that field the same way in each tab.

## The range and the step of a length field, in the units of the figure.
const LENGTH_LOW := -5.0
const LENGTH_HIGH := 5.0
const LENGTH_STEP := 0.001

## The range and the step of an angle field, in degrees.
const ANGLE_LIMIT := 360.0
const ANGLE_STEP := 0.1

const AXES := 3

## The name of each axis of a vector row, for the label of an undo entry.
const AXIS_NAMES := ["x", "y", "z"]

## The side of the color mark of a row of a color list, in pixels.
const MARK_SIZE := 12

## The meta of a button that keeps its own tooltip while the button is off.
const TOOLTIP_META := "figure_tooltip"

## Six hex digits -> the color mark of that color.
static var _marks := {}


## A number field.
static func spin(low: float, high: float, step: float, value := 0.0) -> SpinBox:
	var box := SpinBox.new()

	box.min_value = low
	box.max_value = high
	box.step = step
	box.value = value
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	return box


## A row of three number fields. `on_change` gets the vector of the row
## after each change by the author. With `with_axis`, it also gets the index
## of the field that changed. A merged undo entry needs that index in its
## label: a drag of x and then a drag of y must stay two entries.
static func vector_row(low: float, high: float, step: float,
		on_change: Callable, with_axis := false) -> HBoxContainer:
	var row := HBoxContainer.new()

	for axis in AXES:
		var box := spin(low, high, step)

		# The author sees which axis a field is.
		box.prefix = AXIS_NAMES[axis]
		box.value_changed.connect(func(_value: float) -> void:
			if with_axis:
				on_change.call(vector_of(row), axis)
			else:
				on_change.call(vector_of(row)))
		row.add_child(box)

	return row


## The vector of a row of [method vector_row].
static func vector_of(row: HBoxContainer) -> Vector3:
	return Vector3((row.get_child(0) as SpinBox).value, (row.get_child(1) as SpinBox).value,
		(row.get_child(2) as SpinBox).value)


## Show a vector in a row of [method vector_row]. The row sends no change.
static func set_vector(row: HBoxContainer, vector: Vector3) -> void:
	for axis in AXES:
		(row.get_child(axis) as SpinBox).set_value_no_signal(vector[axis])


## Fill a list with names. A list that has those names keeps its choice.
static func fill(list: OptionButton, names: Array) -> void:
	var same := list.item_count == names.size()

	for index in names.size():
		same = same and list.get_item_text(index) == str(names[index])

	if same:
		return

	list.clear()

	for item: Variant in names:
		list.add_item(str(item))


## Select a name of a list. A name that the list does not have selects
## nothing.
static func select_text(list: OptionButton, text: String) -> void:
	for index: int in list.item_count:
		if list.get_item_text(index) == text:
			list.select(index)
			return

	list.select(-1)


## The selected name of a list, or "".
static func text_of(list: OptionButton) -> String:
	if list.selected < 0:
		return ""

	return list.get_item_text(list.selected)


## Give each row of a color list a mark in its color. The list holds a
## named color or a color role on each row. `look_colors` is the color
## table of the shown look, for a row with a color role. The first `skip`
## rows are no color, and they get no mark.
static func mark_colors(list: OptionButton, palette: FigurePalette, look_colors := {},
		skip := 0) -> void:
	if palette == null:
		return

	for index in range(skip, list.item_count):
		var named := palette.named_for(list.get_item_text(index), look_colors)

		list.set_item_icon(index, color_mark(palette.color_of(named)))


## A small square of one color, for a row of a list. One square for each
## color serves each list.
static func color_mark(color: Color) -> ImageTexture:
	var hex := color.to_html(false)

	if not _marks.has(hex):
		var image := Image.create(MARK_SIZE, MARK_SIZE, false, Image.FORMAT_RGBA8)

		image.fill(Color(color, 1.0))
		_marks[hex] = ImageTexture.create_from_image(image)

	return _marks[hex]


## A label with its text.
static func label(text: String) -> Label:
	var made := Label.new()

	made.text = text
	made.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	return made


## A label for a cell of a grid: one line, with no wrap. A label that wraps
## has no least width, so a grid gives it the width of one letter.
static func cell_label(text: String) -> Label:
	var made := Label.new()

	made.text = text

	return made


## A button with its text and its action. The text is a verb and an object,
## at most four words. `tooltip` is the full sentence that says what the
## button does.
static func button(text: String, action: Callable, tooltip := "") -> Button:
	var made := Button.new()

	made.text = text
	made.tooltip_text = tooltip
	made.set_meta(TOOLTIP_META, tooltip)
	made.pressed.connect(action)

	return made


## Turn a button of [method button] on or off. An off button shows `reason`
## as its tooltip. An on button shows its own tooltip again.
static func enable(made: Button, on: bool, reason: String) -> void:
	made.disabled = not on
	made.tooltip_text = made.get_meta(TOOLTIP_META, "") if on else reason


## A section that the author can fold: a header with `title`, and
## `content` below it. The dock keeps the fold state of each section in
## the session file, by the title.
static func fold(title: String, content: Control, open := true) -> FoldableContainer:
	var made := FoldableContainer.new()

	made.title = title
	made.folded = not open
	made.add_child(content)

	return made


## Put each control of `rows` into one column, for the content of a fold.
static func column(rows: Array) -> VBoxContainer:
	var made := VBoxContainer.new()

	for row: Control in rows:
		made.add_child(row)

	return made
