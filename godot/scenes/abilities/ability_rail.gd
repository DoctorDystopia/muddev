class_name AbilityRail
extends VBoxContainer
## The ability rail: one button for each ability, over the world pane.
## Drawn from [AbilitiesState].
##
## ## A rail, not a bar
##
## Every ability that exists today is a toggle, so the rail is one column
## of toggles in the order that the server gives. No slot is empty, and
## nothing is dragged. Nick chose this over a slotted bar on 10/20/2026,
## with the slotted bar as the next step when an ability with a cast or a
## cooldown exists. The snapshot it reads is the one that bar reads too.
##
## ## It lights what the server says, not what was clicked
##
## A click sends the command of the row and puts the button back. The
## republish of the server is what moves the light. The rule of
## [CombatOptionsView]. A locked row is a disabled button, and its tip
## says why.
##
## ## The key is a label in the corner
##
## [AbilityKeys] says which key fires which slot. The rail prints that key
## on the button, so the player reads the key where the ability is. The
## console turns the key press into [method press_slot].
##
## ## The buttons take the mouse, the gaps do not
##
## A button must take a click. The container ignores the mouse, so an
## empty rail lets a click through to the tile under it, as the XP HUD
## does.
##
## ## An augment row has a button for each power level
##
## After the button of an augment row come small buttons, one for each
## power level: `1`, `2`, `3` (11/12/2026). The button of the current power
## level is lit. A click on another one sends the line that the server
## named for it: it lights an out augment at that power level, or moves a
## lit one there. Shift and the key of the slot still turn the dial, so the
## keyboard and the mouse reach the same lines. The light of a power level
## button moves only when the server republishes, as the light of a row
## does.
##
## Author: Nick Hobar
## Creation date: 10/20/2026

const _Const := preload("res://autoload/blackout_constants.gd")

## Fired with the whole line a telnet player would type. The console sends
## it through `Evennia.command`, the one path everything acts through.
signal command_requested(command: String)

## Presentation. The client's own.
const BUTTON_HEIGHT := 34
const BUTTON_MIN_WIDTH := 150
const ROW_SEPARATION := 4
const BUTTON_TEXT := "%s  %s"
const NO_KEY_TEXT := "%s"

## The power level of a lit augment row, after its name: "Reflex 2/3"
## (DESIGN-0015). A row with no power level dial, or one that is out,
## shows none.
const POWER_LEVEL_TEXT := "%s %d/%d"

## The note of a row, after the name and the power level: the roll of
## Overclock, "Overclock +14%" (DESIGN-0015, Phase 5). The server says the text. An
## empty note draws nothing.
const NOTE_TEXT := "%s %s"

## The last line of the tip of a locked row. The reason comes from the
## server and goes after it.
const LOCKED_HEADING := "Locked:"

## The power level buttons of an augment row. Item 0 of the list that the
## server sends is power level 1, so the text of a button is its index
## plus one.
const POWER_BUTTON_WIDTH := 26
const POWER_BUTTON_TEXT := "%d"
const POWER_BUTTON_TIP := "Power level %d"
const POWER_BUTTON_SEPARATION := 2

var _state: AbilitiesState
var _buttons: Array[Button] = []

## The power level buttons of each row, in the order of [member _buttons].
## An empty list for a row with no power level dial.
var _power_buttons: Array = []

## The node of each row in the rail: its button, or the line that holds
## its button and its power level buttons.
var _drawn: Array[Control] = []


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_theme_constant_override("separation", ROW_SEPARATION)


## Draw from this model from now on.
func bind(state: AbilitiesState) -> void:
	_state = state
	_state.changed.connect(_rebuild)
	_rebuild()


## The buttons, in slot order. For the tests.
func buttons() -> Array[Button]:
	return _buttons


## The power level buttons of the row at an index of [method buttons], the
## lowest power level first. Empty for a row with no dial. For the tests.
func power_level_buttons(index: int) -> Array:
	if index < 0 or index >= _power_buttons.size():
		return []

	return _power_buttons[index]


## The node of the row at an index of [method buttons]. For the tests.
func row_node(index: int) -> Control:
	if index < 0 or index >= _drawn.size():
		return null

	return _drawn[index]


## Fire one slot, as a key press does. Nothing happens past the last row,
## or on a row that the server locked.
func press_slot(slot: int) -> void:
	var row := _toggle_row_at(slot)

	if row.is_empty():
		return

	_send(row)


func _rebuild() -> void:
	for node: Control in _drawn:
		node.queue_free()

	_drawn.clear()
	_buttons.clear()
	_power_buttons.clear()

	if _state == null:
		return

	# The set row takes its own key, not a slot. The toggle rows keep their
	# index as their slot, so the set row goes last and counts as no slot.
	var slot := 0

	for row: Dictionary in _state.rows:
		var is_set := str(row["kind"]) == _Const.ABILITY_KIND_SET
		var button := _button(slot, row, is_set)
		var power_buttons := _power_level_buttons(row)
		var node: Control = button

		if not power_buttons.is_empty():
			node = _line(button, power_buttons)

		add_child(node)
		_drawn.append(node)
		_buttons.append(button)
		_power_buttons.append(power_buttons)

		if not is_set:
			slot += 1


## One row with a power level dial: its button, then its power level
## buttons. The line ignores the mouse, as the rail does, so a click in a
## gap reaches the world. The row button takes the width that is left, so
## the right edges of all rows line up.
func _line(button: Button, power_buttons: Array[Button]) -> HBoxContainer:
	var line := HBoxContainer.new()

	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	line.add_theme_constant_override("separation", POWER_BUTTON_SEPARATION)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line.add_child(button)

	for power_button: Button in power_buttons:
		line.add_child(power_button)

	return line


## The power level buttons of one row, the lowest first. None for a row
## with no dial, or for a server that sends no lines.
##
## The button of the current power level is lit and never disabled, so it
## draws lit. Its line is empty, and a click on it sends nothing. Any other
## button with an empty line is disabled: the row is locked.
func _power_level_buttons(row: Dictionary) -> Array[Button]:
	var made: Array[Button] = []

	if not AbilitiesState.has_power_levels(row):
		return made

	var lines: Array = row.get("power_level_commands", [])
	var current := int(row["power_level"])

	for index: int in lines.size():
		var power_level := index + 1
		var command := str(lines[index])
		var is_current := power_level == current
		var power_button := Button.new()

		power_button.text = POWER_BUTTON_TEXT % power_level
		power_button.toggle_mode = true
		power_button.button_pressed = is_current
		power_button.disabled = command.is_empty() and not is_current
		power_button.focus_mode = Control.FOCUS_NONE
		power_button.custom_minimum_size = Vector2(POWER_BUTTON_WIDTH, BUTTON_HEIGHT)
		power_button.tooltip_text = POWER_BUTTON_TIP % power_level
		power_button.pressed.connect(
			_on_power_level_pressed.bind(power_button, is_current, command))
		made.append(power_button)

	return made


## A power level button was clicked. Put it back, then ask. The republish
## of the server moves the light.
func _on_power_level_pressed(power_button: Button, is_current: bool, command: String) -> void:
	power_button.set_pressed_no_signal(is_current)

	if command.is_empty():
		return

	command_requested.emit(command)


## Fire the set row, as its key does. Nothing happens when the server sent
## no set row.
func press_set() -> void:
	var row := _state.set_row() if _state != null else {}

	if row.is_empty():
		return

	_send(row)


## Turn the power level dial of one slot, as Shift and its key do. The
## server names the line of the next power level on a lit row. An out row
## carries none, so the rail sends nothing for it.
func power_level_slot(slot: int) -> void:
	var row := _toggle_row_at(slot)

	if row.is_empty():
		return

	var command := str(row["power_level_command"])

	if command.is_empty():
		return

	command_requested.emit(command)


## The toggle row in one slot: the rows that are no set row, by index.
func _toggle_row_at(slot: int) -> Dictionary:
	if _state == null or slot < 0:
		return {}

	var index := 0

	for row: Dictionary in _state.rows:
		if str(row["kind"]) == _Const.ABILITY_KIND_SET:
			continue

		if index == slot:
			return row

		index += 1

	return {}


## One ability. Lit when the server says it is active, disabled when the
## server named no command for it.
##
## `FOCUS_NONE` for the rule the tab strip follows: focus IS the mode in
## this client, and a button that took the keyboard would turn the next
## letter of the player into a movement command.
func _button(slot: int, row: Dictionary, is_set: bool = false) -> Button:
	var button := Button.new()
	var key_label := AbilityKeys.SET_LABEL if is_set else AbilityKeys.label_for(slot)
	var name_text := str(row["name"])

	if AbilitiesState.has_power_levels(row) and int(row["power_level"]) > 0:
		name_text = POWER_LEVEL_TEXT % [
			name_text, int(row["power_level"]), int(row["power_levels"])]

	var note := str(row.get(_Const.ABILITY_NOTE_KEY, ""))

	if not note.is_empty():
		name_text = NOTE_TEXT % [name_text, note]

	if key_label.is_empty():
		button.text = NO_KEY_TEXT % name_text
	else:
		button.text = BUTTON_TEXT % [key_label, name_text]

	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.toggle_mode = true
	button.button_pressed = _is_active(row)
	button.disabled = str(row["command"]).is_empty()
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size = Vector2(BUTTON_MIN_WIDTH, BUTTON_HEIGHT)
	button.tooltip_text = _tooltip(row)
	button.pressed.connect(_on_pressed.bind(button, row))

	return button


## A button was clicked. Put it back, then ask.
##
## The active row DOES send: its command puts the aura out, which is what
## a click on a lit toggle means.
func _on_pressed(button: Button, row: Dictionary) -> void:
	button.set_pressed_no_signal(_is_active(row))
	_send(row)


func _send(row: Dictionary) -> void:
	var command := str(row["command"])

	if command.is_empty():
		return

	command_requested.emit(command)


func _tooltip(row: Dictionary) -> String:
	var extra: Array = []

	if str(row["state"]) == _Const.ABILITY_STATE_LOCKED:
		extra.append(LOCKED_HEADING)
		extra.append(str(row["reason"]))

	return TipText.format(row["tip"], extra)


static func _is_active(row: Dictionary) -> bool:
	return str(row["state"]) == _Const.ABILITY_STATE_ACTIVE
