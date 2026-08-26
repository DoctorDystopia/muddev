extends Node
## Unit tests for InventoryState. Needs no server -- payloads are hand-built in
## the shape Godot's JSON parser produces.
##
##     godot --headless --path godot res://tests/test_inventory_state.tscn

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_a_snapshot_replaces_everything()
	_slot_is_polymorphic()
	_empty_frames_are_carried_through()
	_actions_come_from_the_server()
	_equip_legality_compares_server_values()
	_swap_is_one_based_and_uses_the_server_spelling()
	_a_malformed_payload_is_survived()
	_an_unknown_channel_is_refused()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: inventory_state")
	get_tree().quit(0)


func _payload() -> Dictionary:
	return {
		"slots_total": 32.0,
		"slots_used": 2.0,
		"items": [
			{"id": 101.0, "slot": 0.0, "name": "rusty scrap shortsword",
			 "asset": "rusty_scrap_shortsword", "family": "weapon",
			 "quantity": 1.0, "stackable": false, "equip_slot": "weapon_hand",
			 "actions": [{"label": "Equip", "command": "equip 1"},
						 {"label": "Drop", "command": "drop 1"}]},
			{"id": 102.0, "slot": 5.0, "name": "rusty metal chunk",
			 "asset": "", "family": "material",
			 "quantity": 12.0, "stackable": true, "equip_slot": "",
			 "actions": [{"label": "Drop", "command": "drop 6"}]},
		],
		"equipped": [
			{"id": 103.0, "slot": "armor_body", "name": "scrap plate",
			 "asset": "", "family": "armor", "quantity": 1.0,
			 "stackable": false, "equip_slot": "armor_body",
			 "actions": [{"label": "Unequip", "command": "unequip armor_body"}]},
		],
		"equip_slots": [
			{"slot": "weapon_hand", "label": "Weapon hand"},
			{"slot": "armor_body", "label": "Body"},
			{"slot": "a_slot_added_tomorrow", "label": "Future"},
		],
	}


func _a_snapshot_replaces_everything() -> void:
	# Not deltas, deliberately. A missed delta on your own inventory is a
	# phantom item you will try to click.
	var inv := InventoryState.new()

	_expect(not inv.has_data, "no data before the first payload")
	inv.ingest(_Const.CH_CHAR_ITEMS, _payload())
	_expect(inv.has_data, "data after it")
	_expect(inv.slots_total == 32 and inv.slots_used == 2, "counts are ints")
	_expect(inv.carried.size() == 2, "two carried rows")

	# A later snapshot with one item must not leave the other standing.
	inv.ingest(_Const.CH_CHAR_ITEMS, {
		"slots_total": 32.0, "slots_used": 0.0,
		"items": [], "equipped": [], "equip_slots": [],
	})
	_expect(inv.carried.is_empty(), "a re-sent snapshot replaces rather than merges")
	_expect(inv.equipped.is_empty(), "and clears equipment too")


func _slot_is_polymorphic() -> void:
	# The trap: carried slot is an array index, equipped slot is a
	# WieldLocation string. Coercing the whole payload would file every worn
	# item in carried slot 0.
	var inv := InventoryState.new()
	inv.ingest(_Const.CH_CHAR_ITEMS, _payload())

	_expect(inv.carried.has(0) and inv.carried.has(5),
		"carried rows are keyed by int index")
	_expect(typeof(inv.carried.keys()[0]) == TYPE_INT, "and the key is an int")
	_expect(inv.equipped.has("armor_body"),
		"worn rows are keyed by the WieldLocation string")
	_expect(inv.carried_at(0).get("name") == "rusty scrap shortsword",
		"slot 0 holds the sword")
	_expect(inv.carried_at(7).is_empty(), "an unoccupied slot is empty, not null")
	_expect(inv.equipped_at("weapon_hand").is_empty(),
		"an empty equipment slot is empty")
	_expect(inv.carried_at(5).get("quantity") == 12,
		"a stack quantity is an int")


func _empty_frames_are_carried_through() -> void:
	# Adding a slot to WieldLocation must light up a new frame with no client
	# edit -- so the frame list is iterated, never restated.
	var inv := InventoryState.new()
	inv.ingest(_Const.CH_CHAR_ITEMS, _payload())

	_expect(inv.equip_frames.size() == 3, "every frame ships, occupied or not")
	_expect(inv.equip_frames[0].get("label") == "Weapon hand", "frames carry labels")
	_expect(inv.equip_frames[2].get("slot") == "a_slot_added_tomorrow",
		"a slot this client has never heard of still draws")


func _actions_come_from_the_server() -> void:
	# The browser pane had a verb table once. It was wrong within a week and a
	# superuser walked off with a Foundry Furnace.
	var inv := InventoryState.new()
	inv.ingest(_Const.CH_CHAR_ITEMS, _payload())

	var actions := inv.actions_for(inv.carried_at(0))

	_expect(actions.size() == 2, "the sword offers two actions")
	_expect(actions[0].get("command") == "equip 1",
		"and the command is the server's whole string")
	_expect(inv.actions_for({}).is_empty(), "a missing row offers nothing")


func _equip_legality_compares_server_values() -> void:
	var inv := InventoryState.new()
	inv.ingest(_Const.CH_CHAR_ITEMS, _payload())

	var sword := inv.carried_at(0)
	var chunk := inv.carried_at(5)

	_expect(inv.can_equip(sword, "weapon_hand"), "the sword fits the weapon hand")
	_expect(not inv.can_equip(sword, "armor_body"), "but not the body slot")
	_expect(not inv.can_equip(chunk, "weapon_hand"),
		"a material with no equip_slot fits nowhere")


func _swap_is_one_based_and_uses_the_server_spelling() -> void:
	# Player-facing slot numbers are 1-based; serialize_inventory applies the
	# same +1 when it builds its own commands, so the two agree.
	var inv := InventoryState.new()

	_expect(inv.swap_command(0, 5) == "swap 1 6", "indices become 1-based")
	_expect(inv.swap_command(3, 3).is_empty(), "a drag onto itself is a no-op")
	_expect(inv.swap_command(0, 1).begins_with("swap "),
		"the verb is the server's, from the generated template")


func _a_malformed_payload_is_survived() -> void:
	var inv := InventoryState.new()

	inv.ingest(_Const.CH_CHAR_ITEMS, {
		"slots_total": 32.0, "items": "junk",
		"equipped": 7.0, "equip_slots": [1.0, "x"],
	})

	_expect(inv.carried.is_empty(), "a non-array items field is dropped")
	_expect(inv.equipped.is_empty(), "a non-array equipped field is dropped")
	_expect(inv.equip_frames.is_empty(), "non-dictionary frames are skipped")
	_expect(inv.has_data, "and it still counts as having been told")


func _an_unknown_channel_is_refused() -> void:
	var inv := InventoryState.new()

	_expect(not inv.ingest("room_info", {}), "another channel is refused")
	_expect(not inv.has_data, "and changes nothing")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
