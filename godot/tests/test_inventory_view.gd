extends Node
## Tests for the inventory VIEW's one job that can be wrong: turning a gesture
## into a command.
##
## The drawing is not tested and deliberately so -- a grid of labels is cheap to
## look at and expensive to assert. What matters is that every command leaving
## this pane was named by the server, and that drop legality is the server's
## answer rather than one this client invented. Those are pure functions of the
## model and are checked here.
##
##     godot --headless --path godot res://tests/test_inventory_view.tscn

const _Const := preload("res://autoload/blackout_constants.gd")
const SlotCell := preload("res://scenes/inventory/slot_cell.gd")

var _failures := 0
var _view: InventoryView
var _state: InventoryState


func _ready() -> void:
	_state = InventoryState.new()
	_state.ingest(_Const.CH_CHAR_ITEMS, _payload())

	_view = InventoryView.new()
	add_child(_view)
	_view.bind(_state)

	_a_carried_to_carried_drag_swaps()
	_a_drag_to_equipment_uses_the_servers_equip_command()
	_a_drag_off_equipment_uses_the_servers_unequip_command()
	_a_gesture_the_server_named_nothing_for_sends_nothing()
	_drop_legality_is_the_servers_answer()
	_emitted_commands_reach_the_signal()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: inventory_view")
	get_tree().quit(0)


func _payload() -> Dictionary:
	return {
		"slots_total": 32.0, "slots_used": 3.0,
		"items": [
			{"id": 101.0, "slot": 0.0, "name": "sword", "asset": "", "family": "weapon",
			 "quantity": 1.0, "stackable": false, "equip_slot": "weapon_hand",
			 "actions": [{"label": "Equip", "command": "equip 1"},
						 {"label": "Drop", "command": "drop 1"}]},
			{"id": 102.0, "slot": 3.0, "name": "chunk", "asset": "", "family": "material",
			 "quantity": 12.0, "stackable": true, "equip_slot": "",
			 "actions": [{"label": "Drop", "command": "drop 4"}]},
			# Equipment the server offered NO equip action for -- a legality
			# edge the client must not paper over by composing one.
			{"id": 106.0, "slot": 6.0, "name": "cursed ring", "asset": "",
			 "family": "jewellery", "quantity": 1.0, "stackable": false,
			 "equip_slot": "ring", "actions": [{"label": "Drop", "command": "drop 7"}]},
		],
		"equipped": [
			{"id": 103.0, "slot": "armor_body", "name": "plate", "asset": "",
			 "family": "armor", "quantity": 1.0, "stackable": false,
			 "equip_slot": "armor_body",
			 "actions": [{"label": "Unequip", "command": "unequip armor_body"}]}],
		"equip_slots": [
			{"slot": "weapon_hand", "label": "Weapon"},
			{"slot": "armor_body", "label": "Body"},
			{"slot": "ring", "label": "Ring"}],
	}


func _a_carried_to_carried_drag_swaps() -> void:
	# The one command this client composes, because a drag knows two endpoints
	# and nothing else does. 1-based, matching serialize_inventory's own +1.
	var command: String = _view._command_for(
		SlotCell.KIND_CARRIED, 0, SlotCell.KIND_CARRIED, 3)

	_expect(command == "swap 1 4", "a carried drag swaps, 1-based")
	_expect(
		_view._command_for(SlotCell.KIND_CARRIED, 2, SlotCell.KIND_CARRIED, 2).is_empty(),
		"a drag onto itself sends nothing")


func _a_drag_to_equipment_uses_the_servers_equip_command() -> void:
	# NOT composed. Looked up in the row's own actions, so this client cannot
	# spell `equip` even if it wanted to.
	var command: String = _view._command_for(
		SlotCell.KIND_CARRIED, 0, SlotCell.KIND_EQUIPPED, "weapon_hand")

	_expect(command == "equip 1", "the server's own equip command is used verbatim")


func _a_drag_off_equipment_uses_the_servers_unequip_command() -> void:
	var command: String = _view._command_for(
		SlotCell.KIND_EQUIPPED, "armor_body", SlotCell.KIND_CARRIED, 8)

	_expect(command == "unequip armor_body", "the server's own unequip command")


func _a_gesture_the_server_named_nothing_for_sends_nothing() -> void:
	# The ring has an equip_slot but the server offered no equip action for it.
	# Composing "equip 7" here would be the client inventing a verb the server
	# deliberately withheld.
	var command: String = _view._command_for(
		SlotCell.KIND_CARRIED, 6, SlotCell.KIND_EQUIPPED, "ring")

	_expect(command.is_empty(),
		"an item the server named no equip action for sends nothing")

	_expect(
		_view._command_for(SlotCell.KIND_EQUIPPED, "armor_body",
			SlotCell.KIND_EQUIPPED, "weapon_hand").is_empty(),
		"equipment to equipment is not a gesture and sends nothing")


func _drop_legality_is_the_servers_answer() -> void:
	# can_equip compares two SERVER-supplied values: the row's equip_slot
	# against the frame's slot.
	var frame := SlotCell.new()
	frame.bind(_state, SlotCell.KIND_EQUIPPED, "weapon_hand", "Weapon")

	var sword := {"kind": SlotCell.KIND_CARRIED, "key": 0,
				  "row": _state.carried_at(0)}
	var chunk := {"kind": SlotCell.KIND_CARRIED, "key": 3,
				  "row": _state.carried_at(3)}

	_expect(frame._can_drop_data(Vector2.ZERO, sword), "the sword may enter the weapon hand")
	_expect(not frame._can_drop_data(Vector2.ZERO, chunk),
		"a material with no equip_slot may not")
	_expect(not frame._can_drop_data(Vector2.ZERO, "junk"),
		"a non-dictionary payload is refused")

	var square := SlotCell.new()
	square.bind(_state, SlotCell.KIND_CARRIED, 8)

	_expect(square._can_drop_data(Vector2.ZERO, sword),
		"anything may be dropped into the bag; the server validates")

	frame.free()
	square.free()


func _emitted_commands_reach_the_signal() -> void:
	var seen: Array = []
	_view.command_requested.connect(func(c: String): seen.append(c))

	_view._on_dropped(SlotCell.KIND_CARRIED, 0, SlotCell.KIND_CARRIED, 3)
	_view._on_dropped(SlotCell.KIND_CARRIED, 6, SlotCell.KIND_EQUIPPED, "ring")

	_expect(seen.size() == 1, "only the gesture with a command emitted")
	_expect(seen[0] == "swap 1 4", "and it emitted the right one")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
