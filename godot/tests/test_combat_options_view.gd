extends Node
## Tests for the Combat tab's jobs that can be wrong: every command leaving it
## was named by the server, a click does not claim a style the server has not
## confirmed, and a republish is what moves the highlight.
##
## The drawing is not tested -- four buttons are cheap to look at and expensive
## to assert.
##
##     godot --headless --path godot res://tests/test_combat_options_view.tscn

const _Const := preload("res://autoload/blackout_constants.gd")
const _StateTest := preload("res://tests/test_combat_options_state.gd")

var _failures := 0
var _view: CombatOptionsView
var _state: CombatOptionsState
var _sent: Array[String] = []


func _ready() -> void:
	_state = CombatOptionsState.new()
	_view = CombatOptionsView.new()
	add_child(_view)
	_view.command_requested.connect(func(command: String): _sent.append(command))
	_view.bind(_state)

	_nothing_is_drawn_before_a_snapshot()

	_state.ingest(_Const.CH_CHAR_COMBAT, _StateTest.armed_payload())

	_a_button_is_drawn_for_every_style()
	_only_the_active_style_is_lit()
	_clicking_another_style_sends_the_servers_command()
	_a_click_does_not_move_the_highlight_by_itself()
	_clicking_the_active_style_sends_nothing()
	_a_republish_moves_the_highlight()
	_the_buttons_never_take_the_keyboard()
	_the_active_style_is_described()
	_bare_hands_draw_a_style_that_cannot_be_clicked()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: combat_options_view")
	get_tree().quit(0)


func _button(style_name: String) -> Button:
	for button: Button in _view.style_buttons():
		if button.text.begins_with(style_name):
			return button

	return null


## What the engine does on a real click of a toggle button: flip, then emit.
func _click(button: Button) -> void:
	button.set_pressed_no_signal(not button.button_pressed)
	button.pressed.emit()


func _nothing_is_drawn_before_a_snapshot() -> void:
	_expect(_view.style_buttons().is_empty(), "no buttons before char_combat")
	_expect(_all_text(_view).contains(CombatOptionsView.NO_DATA_TEXT),
		"and the pane says it is waiting")


func _a_button_is_drawn_for_every_style() -> void:
	# Iterate, never enumerate: the buttons are built from what arrived.
	_expect(_view.style_buttons().size() == 2, "one button per style sent")


func _only_the_active_style_is_lit() -> void:
	_expect(_button("Irimi").button_pressed, "the active style is lit")
	_expect(not _button("Guard").button_pressed, "and the other is not")


func _clicking_another_style_sends_the_servers_command() -> void:
	_sent.clear()

	_click(_button("Guard"))

	_expect(_sent == ["combatoptions guard"],
		"the click sends exactly the command the row carried")


func _a_click_does_not_move_the_highlight_by_itself() -> void:
	# The server's republish lights the new style. Lighting it here would show
	# a style the server may yet refuse.
	_expect(not _button("Guard").button_pressed,
		"the clicked style stays unlit until the server says otherwise")
	_expect(_button("Irimi").button_pressed, "and the active one stays lit")


func _clicking_the_active_style_sends_nothing() -> void:
	_sent.clear()

	_click(_button("Irimi"))

	_expect(_sent.is_empty(), "the active style sends nothing")
	_expect(_button("Irimi").button_pressed, "and is not unlit by the click")


func _a_republish_moves_the_highlight() -> void:
	var payload := _StateTest.armed_payload()
	payload["styles"][0]["active"] = false
	payload["styles"][1]["active"] = true

	_state.ingest(_Const.CH_CHAR_COMBAT, payload)

	_expect(_button("Guard").button_pressed, "the snapshot lights Guard")
	_expect(not _button("Irimi").button_pressed, "and unlights Irimi")


func _the_buttons_never_take_the_keyboard() -> void:
	# Focus IS the mode in this client. A focused button would turn the next
	# letter the player types into a walk.
	for button: Button in _view.style_buttons():
		_expect(button.focus_mode == Control.FOCUS_NONE,
			"%s refuses focus" % button.text.get_slice("\n", 0))


func _the_active_style_is_described() -> void:
	var text := _all_text(_view)

	_expect(text.contains("rusty scrap shortsword"), "the weapon is named")
	_expect(text.contains("Combat level: 12"), "with the combat level")
	_expect(text.contains("2.4s"), "and the server's attack speed in seconds")
	_expect(text.contains("Defense +3"), "the active style's boost is listed")


func _bare_hands_draw_a_style_that_cannot_be_clicked() -> void:
	_state.ingest(_Const.CH_CHAR_COMBAT, _StateTest.unarmed_payload())
	_sent.clear()

	var punch := _button("Punch")

	_expect(punch != null and punch.disabled,
		"a row with no command is drawn disabled")

	_click(punch)

	_expect(_sent.is_empty(), "and sends nothing even if clicked")
	_expect(_all_text(_view).contains(CombatOptionsView.NO_CHOICE_TEXT),
		"and the pane says how to get a choice")


## Every Label's text under one node, joined.
func _all_text(node: Node) -> String:
	var parts: PackedStringArray = []

	for child: Node in node.get_children():
		if child is Label:
			parts.append((child as Label).text)

		parts.append(_all_text(child))

	return " ".join(parts)


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
