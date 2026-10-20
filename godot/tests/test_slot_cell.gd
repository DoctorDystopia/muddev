extends Node
## Tests for the one thing a slot cell decides: what to send when the player
## picks one of the server's named actions.
##
## Three shapes reach [method InventorySlotCell._on_menu_id], and getting any
## of them wrong sells the wrong thing:
##
##     a whole command   -> send it verbatim
##     a prompted action -> ask for the amount, then substitute and send
##     an empty command  -> send nothing, ever
##
## The prompted case is why this file exists. Sell X and Deposit X ship with an
## EMPTY `command` on purpose — that is what makes them inert on a client that
## never learned to ask, instead of sending a literal placeholder at the
## parser. A cell that read the empty-command guard first would therefore have
## made the prompt permanently unreachable, which is exactly the bug this
## checks for.
##
## The dialog's LOOK is not tested. What is tested is that it appears, that it
## is bounded by the server's own numbers, and that confirming it emits the
## substituted command.
##
##     godot --headless --path godot res://tests/test_slot_cell.tscn

const _Const := preload("res://autoload/blackout_constants.gd")
const SlotCell := preload("res://scenes/inventory/slot_cell.gd")

const STACK_QUANTITY := 12
const CHOSEN_AMOUNT := 4

## The Drop that the server names for the stack, in its list and under its
## own key. LAST in the list, so a test that sent the first action by mistake
## cannot pass.
const DROP_ACTION := {"label": "Drop", "command": "drop 7"}

## A carried slot whose row carries no Drop key.
const NO_DROP_SLOT := 8

## Disposable, rather than the real profile: one case here writes a size.
const SETTINGS_PATH := "user://test_slot_cell.cfg"

var _failures := 0
var _state: InventoryState
var _sent: Array[String] = []


func _ready() -> void:
	_state = InventoryState.new()
	_state.ingest(_Const.CH_CHAR_ITEMS, _payload())

	_a_whole_command_is_sent_verbatim()
	_a_left_click_sends_the_first_action()
	_a_drag_does_not_send_the_first_action()
	_an_empty_command_sends_nothing()
	_a_prompted_action_opens_a_dialog()
	_the_dialog_is_bounded_by_the_servers_numbers()
	_confirming_substitutes_the_amount()
	_the_placeholder_is_never_left_in_a_sent_command()
	_a_prompt_the_client_cannot_read_sends_nothing()
	_the_box_remembers_the_size_the_player_gave_it()
	_a_shift_click_drops_when_the_player_turned_it_on()
	_a_shift_click_is_a_click_when_the_option_is_off()
	_a_shift_click_on_a_row_with_no_drop_is_a_click()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: slot_cell")
	get_tree().quit(0)


## One stackable carried row carrying all three action shapes at once.
##
## Floats throughout, because that is what Godot's JSON parser produces and
## the int boundary is [InventoryState]'s job rather than this file's.
func _payload() -> Dictionary:
	return {
		"slots_total": 32.0,
		"slots_used": 1.0,
		"items": [
			{"id": 101.0, "slot": 6.0, "name": "rusty metal dust",
			 "asset": "", "family": "crafting_material",
			 "quantity": float(STACK_QUANTITY), "stackable": true,
			 "equip_slot": "",
			 "actions": [
				{"label": "Sell 1", "command": "sell 7 1"},
				{"label": "Sell X", "command": "", "template": "sell 7 {amount}",
				 "input": {"kind": "quantity", "min": 1.0,
						   "max": float(STACK_QUANTITY),
						   "label": "Sell how many?"}},
				{"label": "Sell All", "command": "sell 7 all"},
				{"label": "Declined", "command": ""},
				DROP_ACTION,
			 ],
			 _Const.INVENTORY_DROP_KEY: DROP_ACTION},
			# No Drop key, as a worn row has none.
			{"id": 102.0, "slot": float(NO_DROP_SLOT), "name": "scrap plate",
			 "asset": "", "family": "armor", "quantity": 1.0,
			 "stackable": false, "equip_slot": "",
			 "actions": [{"label": "Inspect", "command": "inspect 9"}]},
		],
		"equipped": [],
		"equip_slots": [],
	}


## A cell bound to the one row, with its emissions recorded.
func _cell() -> InventorySlotCell:
	var cell := SlotCell.new()
	add_child(cell)
	cell.bind(_state, SlotCell.KIND_CARRIED, 6)
	cell.action_chosen.connect(func(command: String) -> void:
		_sent.append(command)
	)

	return cell


func _actions() -> Array:
	return _state.actions_for(_state.carried_at(6))


## The dialog a cell opened, or null. Found by type rather than by name: the
## cell builds it in code and this test must not depend on what it is called.
func _dialog_under(cell: InventorySlotCell) -> AcceptDialog:
	for child: Node in cell.get_children():
		if child is AcceptDialog:
			return child as AcceptDialog

	return null


func _spin_in(dialog: AcceptDialog) -> SpinBox:
	for child: Node in dialog.get_children():
		if child is SpinBox:
			return child as SpinBox

	return null


func _a_whole_command_is_sent_verbatim() -> void:
	_sent.clear()
	var cell := _cell()

	cell._on_menu_id(0)

	_expect(_sent == ["sell 7 1"], "a named command is sent as named")
	cell.free()


func _a_left_click_sends_the_first_action() -> void:
	_sent.clear()
	var cell := _cell()

	cell._gui_input(_left_click(true))
	_expect(_sent.is_empty(), "a left-button press waits for its release")
	cell._gui_input(_left_click(false))

	_expect(_sent == ["sell 7 1"], "a left click sends the first action")
	cell.free()


func _a_drag_does_not_send_the_first_action() -> void:
	_sent.clear()
	var cell := _cell()

	cell._gui_input(_left_click(true))
	# Typed Variant, not inferred: `_get_drag_data` returns Variant, and an
	# inferred declaration off one is a warning this project treats as an
	# error -- so the whole file failed to parse and the scene hung.
	var drag_data: Variant = cell._get_drag_data(Vector2.ZERO)
	cell._gui_input(_left_click(false))

	_expect(drag_data != null, "a populated cell starts a drag")
	_expect(_sent.is_empty(), "a drag does not send the first action")
	cell.free()


func _left_click(pressed: bool, shift: bool = false) -> InputEventMouseButton:
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = pressed
	click.shift_pressed = shift

	return click


## A press and a release with Shift held, as the player gives it.
func _shift_click(cell: InventorySlotCell) -> void:
	cell._gui_input(_left_click(true, true))
	cell._gui_input(_left_click(false, true))


## Settings on a disposable file, with the Shift option set as asked.
func _settings_with_shift_drop(on: bool) -> ClientSettings:
	_clean_settings()
	var settings := ClientSettings.new(SETTINGS_PATH)
	settings.set_shift_click_drop(on)

	return settings


func _a_shift_click_drops_when_the_player_turned_it_on() -> void:
	_sent.clear()
	var cell := _cell()
	cell.bind_settings(_settings_with_shift_drop(true))

	_shift_click(cell)
	_expect(_sent == [DROP_ACTION["command"]],
		"a Shift + left click sends the Drop that the server named")

	_sent.clear()
	cell._gui_input(_left_click(true))
	cell._gui_input(_left_click(false))
	_expect(_sent == ["sell 7 1"], "a plain left click still sends the first action")

	cell.free()
	_clean_settings()


func _a_shift_click_is_a_click_when_the_option_is_off() -> void:
	_sent.clear()
	var cell := _cell()
	cell.bind_settings(_settings_with_shift_drop(false))

	_shift_click(cell)
	_expect(_sent == ["sell 7 1"],
		"with the option off, a Shift + left click sends the first action")

	cell.free()
	_clean_settings()


func _a_shift_click_on_a_row_with_no_drop_is_a_click() -> void:
	_sent.clear()
	var cell := SlotCell.new()
	add_child(cell)
	cell.bind(_state, SlotCell.KIND_CARRIED, NO_DROP_SLOT)
	cell.bind_settings(_settings_with_shift_drop(true))
	cell.action_chosen.connect(func(command: String) -> void:
		_sent.append(command)
	)

	_shift_click(cell)
	_expect(_sent == ["inspect 9"],
		"a row with no Drop key gets the first action, never a guessed drop")

	cell.free()
	_clean_settings()


func _an_empty_command_sends_nothing() -> void:
	_sent.clear()
	var cell := _cell()

	cell._on_menu_id(3)

	_expect(_sent.is_empty(), "an empty command sends nothing")
	_expect(_dialog_under(cell) == null, "and opens no dialog")
	cell.free()


func _a_prompted_action_opens_a_dialog() -> void:
	_sent.clear()
	var cell := _cell()

	cell._on_menu_id(1)

	_expect(_sent.is_empty(), "a prompted action sends nothing yet")
	_expect(_dialog_under(cell) != null, "a prompted action opens a dialog")
	cell.free()


func _the_dialog_is_bounded_by_the_servers_numbers() -> void:
	var cell := _cell()
	cell._on_menu_id(1)
	var spin := _spin_in(_dialog_under(cell))

	_expect(spin != null, "the dialog carries a spin box")
	_expect(int(spin.max_value) == STACK_QUANTITY,
			"the maximum is the row's own quantity")
	_expect(int(spin.min_value) >= 1, "the minimum is never zero")
	cell.free()


func _confirming_substitutes_the_amount() -> void:
	_sent.clear()
	var cell := _cell()
	cell._on_menu_id(1)
	var dialog := _dialog_under(cell)
	_spin_in(dialog).value = CHOSEN_AMOUNT

	dialog.confirmed.emit()

	_expect(_sent == ["sell 7 %d" % CHOSEN_AMOUNT],
			"confirming sends the substituted command")
	cell.free()


func _the_placeholder_is_never_left_in_a_sent_command() -> void:
	# The failure mode a non-empty `command` carrying the placeholder would
	# have had, asserted over every action on the row rather than trusted --
	# and independent of the cases above, so reordering them cannot turn this
	# into a pass over an empty list.
	var clean := true

	for action: Dictionary in _actions():
		var composed := _state.action_command(action, CHOSEN_AMOUNT)
		clean = clean and not composed.contains(_Const.ACTION_AMOUNT_PLACEHOLDER)

	_expect(clean, "no composed command carries a placeholder")


func _a_prompt_the_client_cannot_read_sends_nothing() -> void:
	# An `input` naming a kind this client has no box for is the server asking
	# a question it cannot answer. It declines rather than guessing a number.
	var action := {"label": "Weigh X", "command": "",
				   "template": "weigh 7 {amount}",
				   "input": {"kind": "colour", "min": 1.0, "max": 9.0}}

	_expect(_state.action_prompt(action).is_empty(),
			"an unknown prompt kind is not a prompt")
	_expect(_state.action_command(action, 3).is_empty(),
			"and composes no command")


## A box is built per prompt and freed on close, so a size the player dragged
## has nowhere to live but [ClientSettings]. Every box was the wrapped one
## before 09/21/2026, however many times the player widened the last.
##
## The size is read when the box CLOSES. A size read from the resize gesture
## would be a file write for each frame of the drag.
##
## The size it OPENS at is asserted as a decision, through
## [method AmountPrompt.wanted_size], and the method says why: a headless
## display is 64 pixels square, so it refuses to spawn a real box at all.
func _the_box_remembers_the_size_the_player_gave_it() -> void:
	_clean_settings()
	var settings := ClientSettings.new(SETTINGS_PATH)

	_expect(AmountPrompt.wanted_size(settings) == Vector2i.ZERO,
		"the first box wraps its contents")
	_expect(AmountPrompt.wanted_size(null) == Vector2i.ZERO,
		"and so does one opened with no settings at all")

	# Opened with nothing remembered, so this box asks for its wrapped size
	# and the headless display can actually spawn it.
	var cell := _cell()
	cell.bind_settings(settings)
	cell._on_menu_id(1)

	var dialog := _dialog_under(cell)
	_expect(dialog != null, "a prompted action still opens a box")

	dialog.size = Vector2i(510, 300)
	var ended := dialog.size
	dialog.close_requested.emit()

	var reloaded := ClientSettings.new(SETTINGS_PATH)
	reloaded.load_from_disk()
	_expect(reloaded.amount_size == ended,
		"closing writes down what the player left")
	_expect(AmountPrompt.wanted_size(reloaded) == ended,
		"and the next box opens at it")

	cell.free()
	_clean_settings()


func _clean_settings() -> void:
	if FileAccess.file_exists(SETTINGS_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
