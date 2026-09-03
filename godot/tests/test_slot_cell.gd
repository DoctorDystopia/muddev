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

var _failures := 0
var _state: InventoryState
var _sent: Array[String] = []


func _ready() -> void:
	_state = InventoryState.new()
	_state.ingest(_Const.CH_CHAR_ITEMS, _payload())

	_a_whole_command_is_sent_verbatim()
	_an_empty_command_sends_nothing()
	_a_prompted_action_opens_a_dialog()
	_the_dialog_is_bounded_by_the_servers_numbers()
	_confirming_substitutes_the_amount()
	_the_placeholder_is_never_left_in_a_sent_command()
	_a_prompt_the_client_cannot_read_sends_nothing()

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
			 ]},
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


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
