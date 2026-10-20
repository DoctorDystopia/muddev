extends Node
## Tests for the jobs of the ability rail that can be wrong. Every command
## that leaves it came from the server. A click does not light a row that
## the server did not confirm. A key press fires the slot of its row. A
## locked row cannot fire.
##
## The drawing is not tested. A column of buttons is cheap to look at.
##
##     godot --headless --path godot res://tests/test_ability_rail.tscn

const _Const := preload("res://autoload/blackout_constants.gd")
const _StateTest := preload("res://tests/test_abilities_state.gd")

var _failures := 0
var _rail: AbilityRail
var _state: AbilitiesState
var _sent: Array[String] = []


func _ready() -> void:
	_state = AbilitiesState.new()
	_rail = AbilityRail.new()
	add_child(_rail)
	_rail.command_requested.connect(func(command: String): _sent.append(command))
	_rail.bind(_state)

	_nothing_is_drawn_before_a_snapshot()

	_state.ingest(_Const.CH_CHAR_ABILITIES, _StateTest.payload())

	_a_button_is_drawn_for_every_row()
	_the_button_names_its_key()
	_the_active_row_is_lit_and_the_locked_row_is_disabled()
	_clicking_the_active_row_sends_the_servers_command()
	_a_click_does_not_move_the_light_by_itself()
	_a_key_press_fires_the_slot_of_its_row()
	_a_locked_slot_sends_nothing()
	_a_slot_past_the_rows_sends_nothing()
	_a_republish_moves_the_light()
	_the_buttons_never_take_the_keyboard()
	_the_tip_of_a_locked_row_says_why()
	_the_rail_itself_ignores_the_mouse()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: ability_rail")
	get_tree().quit(0)


func _expect(condition: bool, message: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("FAIL: %s" % message)


## What the engine does on a real click of a toggle button: flip, then emit.
func _click(button: Button) -> void:
	button.set_pressed_no_signal(not button.button_pressed)
	button.pressed.emit()


func _nothing_is_drawn_before_a_snapshot() -> void:
	_expect(_rail.buttons().is_empty(), "no buttons before char_abilities")


func _a_button_is_drawn_for_every_row() -> void:
	_expect(_rail.buttons().size() == 2, "one button per row sent")


func _the_button_names_its_key() -> void:
	_expect(_rail.buttons()[0].text.begins_with(AbilityKeys.label_for(0)),
		"the first button starts with the label of the first key")
	_expect(_rail.buttons()[0].text.ends_with("Righteous Fire"),
		"and ends with the name of the ability")


func _the_active_row_is_lit_and_the_locked_row_is_disabled() -> void:
	_expect(_rail.buttons()[0].button_pressed, "the active row is lit")
	_expect(not _rail.buttons()[0].disabled, "and can be clicked")
	_expect(not _rail.buttons()[1].button_pressed, "the locked row is not lit")
	_expect(_rail.buttons()[1].disabled, "and cannot be clicked")


func _clicking_the_active_row_sends_the_servers_command() -> void:
	_sent.clear()

	_click(_rail.buttons()[0])

	_expect(_sent == ["aura off"], "the click sends exactly the command the row carried")


func _a_click_does_not_move_the_light_by_itself() -> void:
	_expect(_rail.buttons()[0].button_pressed,
		"the active row stays lit until the server says otherwise")


func _a_key_press_fires_the_slot_of_its_row() -> void:
	_sent.clear()

	_rail.press_slot(0)

	_expect(_sent == ["aura off"], "the key sends the command of its slot")


func _a_locked_slot_sends_nothing() -> void:
	_sent.clear()

	_rail.press_slot(1)

	_expect(_sent.is_empty(), "a locked row sends nothing")


func _a_slot_past_the_rows_sends_nothing() -> void:
	_sent.clear()

	_rail.press_slot(7)

	_expect(_sent.is_empty(), "a slot with no row sends nothing")


func _a_republish_moves_the_light() -> void:
	var payload := _StateTest.payload()
	payload["abilities"][0]["state"] = "ready"
	payload["abilities"][0]["command"] = "aura Righteous Fire"

	_state.ingest(_Const.CH_CHAR_ABILITIES, payload)

	_expect(not _rail.buttons()[0].button_pressed, "the republish puts the light out")

	_sent.clear()
	_rail.press_slot(0)
	_expect(_sent == ["aura Righteous Fire"], "and the key now lights it")


func _the_buttons_never_take_the_keyboard() -> void:
	for button: Button in _rail.buttons():
		_expect(button.focus_mode == Control.FOCUS_NONE, "a button never takes focus")


func _the_tip_of_a_locked_row_says_why() -> void:
	var tip := _rail.buttons()[1].tooltip_text

	_expect(tip.begins_with("Toxic Cloud"), "the tip starts with the title")
	_expect(tip.contains("Fortitude level 40"), "and ends with the reason of the lock")


func _the_rail_itself_ignores_the_mouse() -> void:
	_expect(_rail.mouse_filter == Control.MOUSE_FILTER_IGNORE,
		"a click between the buttons reaches the world")
