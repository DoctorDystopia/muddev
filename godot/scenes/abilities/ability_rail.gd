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

## The last line of the tip of a locked row. The reason comes from the
## server and goes after it.
const LOCKED_HEADING := "Locked:"

var _state: AbilitiesState
var _buttons: Array[Button] = []


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


## Fire one slot, as a key press does. Nothing happens past the last row,
## or on a row that the server locked.
func press_slot(slot: int) -> void:
	var row := _state.row_at(slot) if _state != null else {}

	if row.is_empty():
		return

	_send(row)


func _rebuild() -> void:
	for button: Button in _buttons:
		button.queue_free()

	_buttons.clear()

	if _state == null:
		return

	for slot: int in _state.rows.size():
		var button := _button(slot, _state.rows[slot])
		add_child(button)
		_buttons.append(button)


## One ability. Lit when the server says it is active, disabled when the
## server named no command for it.
##
## `FOCUS_NONE` for the rule the tab strip follows: focus IS the mode in
## this client, and a button that took the keyboard would turn the next
## letter of the player into a movement command.
func _button(slot: int, row: Dictionary) -> Button:
	var button := Button.new()
	var key_label := AbilityKeys.label_for(slot)

	if key_label.is_empty():
		button.text = NO_KEY_TEXT % str(row["name"])
	else:
		button.text = BUTTON_TEXT % [key_label, str(row["name"])]

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
