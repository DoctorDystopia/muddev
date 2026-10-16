@tool
extends HFlowContainer
## A row of toggle buttons, one for each tool. The text of a button names
## its number key: "Raise (1)". One click or one key picks a tool, in place
## of a dropdown that needs two clicks.

## The tool changed by a click or by [method pick_tool].
signal tool_changed(index: int)

## The key of each button, in the order of the tools. A tool past the
## tenth has no key.
const KEY_NAMES := ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]

var _group := ButtonGroup.new()
var _buttons: Array[Button] = []


## Make one button for each name. `tips` gives the tooltip of each one.
func set_tools(names: Array, tips: Array = []) -> void:
	for button: Button in _buttons:
		remove_child(button)
		button.queue_free()

	_buttons.clear()

	for index: int in names.size():
		var button := Button.new()

		button.text = labelled(names[index], index)
		button.toggle_mode = true
		button.button_group = _group
		button.tooltip_text = tips[index] if index < tips.size() else ""
		button.pressed.connect(func() -> void: tool_changed.emit(index))
		add_child(button)
		_buttons.append(button)

	if not _buttons.is_empty():
		_buttons[0].set_pressed_no_signal(true)


## The text of the button of tool `index`: the name and its key.
static func labelled(tool_label: String, index: int) -> String:
	if index < KEY_NAMES.size():
		return "%s (%s)" % [tool_label, KEY_NAMES[index]]

	return tool_label


func current_tool() -> int:
	for index: int in _buttons.size():
		if _buttons[index].button_pressed:
			return index

	return 0


## Press the button of tool `index`, and send no signal.
func select_tool(index: int) -> void:
	for other: int in _buttons.size():
		_buttons[other].set_pressed_no_signal(other == index)


## Press the button of tool `index`, and send [signal tool_changed]: a
## number key.
func pick_tool(index: int) -> void:
	if index < 0 or index >= _buttons.size() or index == current_tool():
		return

	select_tool(index)
	tool_changed.emit(index)
