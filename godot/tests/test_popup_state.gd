extends Node
## Unit tests for PopupState -- the model behind the pop-up -- and for
## ServerAction, the action rules it shares with the inventory.
##
##     godot --headless --path godot res://tests/test_popup_state.tscn
##
## Needs nothing running. Payloads are hand-built in the shape Godot's JSON
## parser produces, floats and all.

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_another_channel_is_not_ours()
	_an_open_snapshot_is_read_and_numbers_become_ints()
	_the_first_action_is_the_default()
	_the_closed_state_empties_the_model()
	_malformed_entries_are_skipped()
	_reset_forgets_everything()
	_a_prompted_action_substitutes_the_amount()
	_a_whole_command_is_sent_verbatim()
	_detail_info_enabled_and_footer_are_read()
	_an_old_row_is_enabled()
	_a_menu_node_is_read()
	_a_grid_is_not_a_menu()
	_timers_are_read_and_count_down()
	_a_pop_up_with_no_timers_has_no_panel()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: popup_state")
	get_tree().quit(0)


static func bank_payload() -> Dictionary:
	return {
		"open": true, "key": "bank", "title": "Bank Vault",
		"status": "Vault 1/100 slots   Carried 1/32",
		"grids": [
			{"key": "vault", "title": "Vault", "slots_total": 1.0,
			 "items": [
				{"id": 41.0, "slot": 0.0, "name": "rusty metal dust",
				 "asset": "", "family": "material", "quantity": 40.0,
				 "stackable": true, "equip_slot": "",
				 "actions": [
					{"label": "Withdraw 5", "command": "withdraw rusty metal dust 5"},
					{"label": "Withdraw 1", "command": "withdraw rusty metal dust 1"},
					{"label": "Withdraw X", "command": "",
					 "template": "withdraw rusty metal dust {amount}",
					 "input": {"kind": "quantity", "min": 1.0, "max": 40.0,
						"label": "Withdraw how many?"}},
					{"label": "Withdraw All", "command": "withdraw rusty metal dust all"},
				]},
			 ]},
			{"key": "carried", "title": "Inventory", "slots_total": 32.0,
			 "items": [
				{"id": 52.0, "slot": 3.0, "name": "rusty metal chunk",
				 "asset": "", "family": "material", "quantity": 1.0,
				 "stackable": false, "equip_slot": "",
				 "actions": [{"label": "Deposit", "command": "deposit 4 1"}]},
			 ]},
		],
		"quantity": [
			{"label": "1", "command": "popup quantity 1", "active": false},
			{"label": "5", "command": "popup quantity 5", "active": true},
			{"label": "X", "command": "", "template": "popup quantity {amount}",
			 "input": {"kind": "quantity", "min": 1.0, "max": 1000000.0,
				"label": "Set the quantity to how many?"}, "active": false},
		],
		"close_command": "popup close",
	}


static func crafting_payload() -> Dictionary:
	return {
		"open": true, "key": "crafting", "title": "Anvil",
		"status": "Making rusty scrap shortsword (1/3)",
		"grids": [
			{"key": "recipes", "title": "Recipes", "slots_total": 2.0,
			 "items": [
				{"id": 0.0, "slot": 0.0, "name": "rusty metal dust",
				 "asset": "rusty_metal_dust", "family": "material",
				 "quantity": 1.0, "detail": "Metalsmith Lv.1",
				 "info": "Needs 1x rusty metal chunk", "enabled": true,
				 "actions": [{"label": "Make 1", "command": "craft rusty metal dust 1"}]},
				{"id": 0.0, "slot": 1.0, "name": "rusty scrap shortsword",
				 "asset": "rusty_scrap_shortsword", "family": "weapon",
				 "quantity": 1.0, "detail": "Metalsmith Lv.4",
				 "info": "Needs 2x rusty scrap metal\nMissing: rusty scrap metal",
				 "enabled": false,
				 "actions": [{"label": "Make", "command": "craft rusty scrap shortsword 1"}]},
			 ]},
		],
		"quantity": [],
		"actions": [{"label": "Stop crafting", "command": "craft cancel"}],
		"close_command": "popup close",
	}


static func menu_payload() -> Dictionary:
	return {
		"open": true, "key": "menu", "title": "Shopkeeper", "status": "",
		"grids": [], "quantity": [], "actions": [],
		"text": "[color=#ffff00]Welcome.[/color] What do you need?",
		"choices": [
			{"key": "1", "label": "Buy items", "command": "1"},
			{"key": "2", "label": "Sell items", "command": "2"},
		],
		"input": {"label": "Type your answer"},
		"close_command": "q",
	}


static func closed_payload() -> Dictionary:
	return {"open": false, "key": "", "title": "", "status": "", "grids": [],
		"quantity": [], "close_command": ""}


func _another_channel_is_not_ours() -> void:
	var state := PopupState.new()

	_expect(not state.ingest(_Const.CH_CHAR_ITEMS, bank_payload()),
		"a payload on another channel is declined")
	_expect(not state.is_open, "and leaves the model closed")


func _an_open_snapshot_is_read_and_numbers_become_ints() -> void:
	var state := PopupState.new()
	var fired := [0]
	state.changed.connect(func(): fired[0] += 1)

	_expect(state.ingest(_Const.CH_CHAR_POPUP, bank_payload()), "char_popup is ours")
	_expect(fired[0] == 1, "and announces itself once")
	_expect(state.is_open, "the pop-up is open")
	_expect(state.title == "Bank Vault", "the title is read")
	_expect(state.grids.size() == 2, "both grids are read, in order")
	_expect(state.grids[1]["slots_total"] == 32, "slots_total is an int")

	var row := state.row_at(1, 3)
	_expect(row.get("name", "") == "rusty metal chunk",
		"a row is found by its int slot, not by a float")
	_expect(typeof(row["quantity"]) == TYPE_INT, "quantity is an int")
	_expect(state.row_at(1, 0).is_empty(), "an empty slot is an empty row")
	_expect(state.row_at(9, 0).is_empty(), "a missing grid is an empty row")
	_expect(state.close_command == "popup close", "the close command is read")


func _the_first_action_is_the_default() -> void:
	var state := PopupState.new()
	state.ingest(_Const.CH_CHAR_POPUP, bank_payload())

	var action := PopupState.default_action(state.row_at(0, 0))

	_expect(action.get("command", "") == "withdraw rusty metal dust 5",
		"a left click sends the first action the server listed")
	_expect(PopupState.default_action({}).is_empty(),
		"a row with no actions has no default")


func _the_closed_state_empties_the_model() -> void:
	var state := PopupState.new()
	state.ingest(_Const.CH_CHAR_POPUP, bank_payload())
	state.ingest(_Const.CH_CHAR_POPUP, closed_payload())

	_expect(not state.is_open, "the closed snapshot closes it")
	_expect(state.grids.is_empty(), "and drops the grids")


func _malformed_entries_are_skipped() -> void:
	var state := PopupState.new()
	var payload := bank_payload()
	payload["grids"] = ["not a grid", {"key": "g", "title": "G",
		"slots_total": 2.0, "items": ["not a row", {"slot": 1.0, "name": "ok"}]}]
	payload["quantity"] = [7, {"label": "1", "command": "popup quantity 1"}]
	state.ingest(_Const.CH_CHAR_POPUP, payload)

	_expect(state.grids.size() == 1, "a grid that is not a dict is skipped")
	_expect(state.row_at(0, 1).get("name", "") == "ok", "a good row survives")
	_expect(state.quantity.size() == 1, "a button that is not a dict is skipped")


func _reset_forgets_everything() -> void:
	var state := PopupState.new()
	state.ingest(_Const.CH_CHAR_POPUP, bank_payload())
	state.reset()

	_expect(not state.is_open, "reset closes it")
	_expect(state.close_command.is_empty(), "and forgets the close command")


func _a_prompted_action_substitutes_the_amount() -> void:
	var state := PopupState.new()
	state.ingest(_Const.CH_CHAR_POPUP, bank_payload())
	var prompted: Dictionary = state.row_at(0, 0)["actions"][2]

	var prompt := ServerAction.prompt(prompted)

	_expect(int(prompt[_Const.ACTION_INPUT_MAX_KEY]) == 40, "the bound is read")
	_expect(ServerAction.command(prompted, 7) == "withdraw rusty metal dust 7",
		"the amount goes where the server put the placeholder")


func _a_whole_command_is_sent_verbatim() -> void:
	var action := {"label": "Withdraw 5", "command": "withdraw rusty metal dust 5"}

	_expect(ServerAction.prompt(action).is_empty(), "a whole command asks nothing")
	_expect(ServerAction.command(action, 99) == "withdraw rusty metal dust 5",
		"and ignores any amount")
	_expect(ServerAction.command({"label": "No"}).is_empty(),
		"an empty command is the server declining")


func _detail_info_enabled_and_footer_are_read() -> void:
	var state := PopupState.new()
	state.ingest(_Const.CH_CHAR_POPUP, crafting_payload())
	var dim := state.row_at(0, 1)

	_expect(dim["detail"] == "Metalsmith Lv.4", "detail is read")
	_expect(not dim["enabled"], "enabled false is read")
	_expect(str(dim["info"]).contains("Missing"), "info is read")
	_expect(state.footer.size() == 1, "the footer buttons are read")
	_expect(state.footer[0]["command"] == "craft cancel",
		"with the server's command")


func _an_old_row_is_enabled() -> void:
	var state := PopupState.new()
	state.ingest(_Const.CH_CHAR_POPUP, bank_payload())

	_expect(state.row_at(0, 0)["enabled"],
		"a row with no enabled field is drawn lit")
	_expect(state.footer.is_empty(), "a pop-up with no actions has no footer")


func _a_menu_node_is_read() -> void:
	var state := PopupState.new()
	state.ingest(_Const.CH_CHAR_POPUP, menu_payload())

	_expect(state.is_menu(), "a node with text and options is a menu")
	_expect(state.choices.size() == 2, "every option is read, in order")
	_expect(state.option_command("2") == "2", "an option key names its command")
	_expect(state.option_command("9").is_empty(), "an unknown key names nothing")
	_expect(state.input.get("label", "") == "Type your answer", "the box is read")


func _a_grid_is_not_a_menu() -> void:
	var state := PopupState.new()
	state.ingest(_Const.CH_CHAR_POPUP, bank_payload())

	_expect(not state.is_menu(), "a grid pop-up is not a menu")
	_expect(state.input.is_empty(), "and offers no text box")


static func curing_payload() -> Dictionary:
	var payload := bank_payload()
	payload["key"] = "crafting"
	payload["timers"] = {
		"title": "Curing slots", "total": 3.0,
		"slots": [
			{"name": "cured chuck", "ready": false, "remaining": 30.0, "duration": 60.0},
			{"name": "cured steak", "ready": true, "remaining": 0.0, "duration": 60.0},
		],
	}

	return payload


func _timers_are_read_and_count_down() -> void:
	var state := PopupState.new()
	state.ingest(_Const.CH_CHAR_POPUP, curing_payload())

	var slots: Array = state.timers["slots"]
	var running: Dictionary = slots[0]
	var later := state.received_msec + 10000

	_expect(state.has_timers(), "a timed station has a side panel")
	_expect(state.timers["total"] == 3, "the slot count becomes an int")
	_expect(slots.size() == 2, "every slot is read, in order")
	_expect(bool(slots[1]["ready"]), "a finished slot is ready")
	_expect(is_equal_approx(state.seconds_left(running, later), 20.0),
		"ten seconds later, twenty are left")
	_expect(state.seconds_left(running, later + 60000) == 0.0,
		"the count stops at zero")


func _a_pop_up_with_no_timers_has_no_panel() -> void:
	var state := PopupState.new()
	state.ingest(_Const.CH_CHAR_POPUP, bank_payload())

	_expect(not state.has_timers(), "a bank has no side panel")


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  x %s" % what)
