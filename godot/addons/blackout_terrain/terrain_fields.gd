@tool
extends RefCounted
## The control makers that the panels of the terrain editor share: a row
## with a label, a button, a list, and a number field. One owner, so the
## dock and the Build tab build a row the same way.
##
## A button text is a verb and an object, at most four words. The sentence
## that explains it goes into the tooltip.


## A label over `control`, both as children of `parent`. Returns the label,
## so a caller can hide the pair.
static func row(parent: Control, label_text: String, control: Control,
		tip := "") -> Label:
	var label := Label.new()

	label.text = label_text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	if not tip.is_empty():
		label.tooltip_text = tip
		control.tooltip_text = tip

	parent.add_child(label)
	parent.add_child(control)

	return label


## A button with `text`, and `tip` as its tooltip, that calls `action`.
static func button(text: String, action: Callable, tip := "") -> Button:
	var made := Button.new()

	made.text = text
	made.tooltip_text = tip
	made.pressed.connect(action)

	return made


## A check box with `text`, and `tip` as its tooltip.
static func check(text: String, pressed: bool, tip := "") -> CheckBox:
	var made := CheckBox.new()

	made.text = text
	made.button_pressed = pressed
	made.tooltip_text = tip

	return made


## Set the range, the step, and the value of a number field.
static func spin(field: SpinBox, low: float, high: float, step: float,
		value: float) -> SpinBox:
	field.min_value = low
	field.max_value = high
	field.step = step
	field.value = value
	field.allow_greater = false
	field.allow_lesser = false

	return field


## Fill a list with names.
static func fill(list: OptionButton, names: Array) -> void:
	for item: String in names:
		list.add_item(item)


## Fill `list` with `names` again, and keep its choice. `follow` maps an old
## name to its new name, so a choice follows a rename. A choice that no row
## has any more gives the first row.
static func refill(list: OptionButton, names: Array, follow := {}) -> void:
	var chosen := text_of(list)

	chosen = follow.get(chosen, chosen)
	list.clear()
	fill(list, names)
	select_text(list, chosen)


## The `{old: new}` of a rename of `table`, or an empty Dictionary. A rename
## is `{table, old, new}`, as the plugin sends it after the Tables tab.
static func follow_of(rename: Dictionary, table: String) -> Dictionary:
	if rename.get("table", "") != table:
		return {}

	return {rename["old"]: rename["new"]}


## Select the row of a list with `text`. A text that no row has leaves the
## list as it is.
static func select_text(list: OptionButton, text: String) -> void:
	for index: int in list.item_count:
		if list.get_item_text(index) == text:
			list.select(index)
			return


## The text of the selected row, or "" for an empty list.
static func text_of(list: OptionButton) -> String:
	if list.selected < 0:
		return ""

	return list.get_item_text(list.selected)


## A label in `color`, for a legend.
static func swatch(text: String, color: Color) -> Label:
	var label := Label.new()

	label.text = text
	label.add_theme_color_override("font_color", color)

	return label
