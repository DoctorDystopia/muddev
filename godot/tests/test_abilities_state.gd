extends Node
## Unit tests for AbilitiesState, the model behind the ability rail. Also
## for AbilityKeys, the table from a key to a slot, and for TipText.
##
##     godot --headless --path godot res://tests/test_abilities_state.tscn
##
## Needs nothing running. The payloads are hand-built, in the shape that
## the JSON parser of Godot gives.

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_another_channel_is_not_ours()
	_a_snapshot_is_read_in_the_servers_order()
	_the_tip_is_read_as_a_title_and_lines()
	_the_active_row_is_found()
	_a_slot_past_the_last_row_is_empty()
	_malformed_rows_are_skipped()
	_reset_forgets_everything()
	_each_key_of_the_table_fires_its_slot()
	_a_shifted_press_does_not_fire_an_unshifted_row()
	_a_press_with_ctrl_fires_nothing()
	_a_key_outside_the_table_fires_nothing()
	_a_slot_past_the_table_has_no_label()
	_the_tip_text_puts_the_title_first_and_skips_empty_lines()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: abilities_state")
	get_tree().quit(0)


static func payload() -> Dictionary:
	return {
		"abilities": [
			{"key": "righteous_fire", "name": "Righteous Fire",
			 "kind": "toggle", "state": "active", "command": "aura off",
			 "reason": "",
			 "tip": {"title": "Righteous Fire",
			         "lines": ["Burns every hostile around you.",
			                   "Scales with Fortitude."]}},
			{"key": "toxic_cloud", "name": "Toxic Cloud",
			 "kind": "toggle", "state": "locked", "command": "",
			 "reason": "Toxic Cloud requires Fortitude level 40.",
			 "tip": {"title": "Toxic Cloud", "lines": ["A cloud."]}},
		],
	}


func _press(keycode: Key, shift: bool = false, ctrl: bool = false) -> InputEventKey:
	var event := InputEventKey.new()
	event.keycode = keycode
	event.pressed = true
	event.shift_pressed = shift
	event.ctrl_pressed = ctrl

	return event


func _expect(condition: bool, message: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("FAIL: %s" % message)


func _another_channel_is_not_ours() -> void:
	var state := AbilitiesState.new()

	_expect(not state.ingest(_Const.CH_CHAR_VITALS, {}), "another channel is refused")
	_expect(not state.has_data, "and leaves no data")


func _a_snapshot_is_read_in_the_servers_order() -> void:
	var state := AbilitiesState.new()

	_expect(state.ingest(_Const.CH_CHAR_ABILITIES, payload()), "ours is taken")
	_expect(state.has_data, "and marks data")
	_expect(state.rows.size() == 2, "one row per ability sent")
	_expect(state.row_at(0)["key"] == "righteous_fire", "the first row is the first slot")
	_expect(state.row_at(1)["command"].is_empty(), "a locked row carries no command")
	_expect(state.row_at(1)["reason"].begins_with("Toxic Cloud"), "and carries its reason")


func _the_tip_is_read_as_a_title_and_lines() -> void:
	var state := AbilitiesState.new()
	state.ingest(_Const.CH_CHAR_ABILITIES, payload())

	var tip: Dictionary = state.row_at(0)["tip"]

	_expect(tip["title"] == "Righteous Fire", "the tip keeps its title")
	_expect(tip["lines"].size() == 2, "and its lines")


func _the_active_row_is_found() -> void:
	var state := AbilitiesState.new()
	state.ingest(_Const.CH_CHAR_ABILITIES, payload())

	_expect(state.active_row()["key"] == "righteous_fire", "the active row is found")


func _a_slot_past_the_last_row_is_empty() -> void:
	var state := AbilitiesState.new()
	state.ingest(_Const.CH_CHAR_ABILITIES, payload())

	_expect(state.row_at(2).is_empty(), "a slot past the rows is empty")
	_expect(state.row_at(-1).is_empty(), "and so is a negative one")


func _malformed_rows_are_skipped() -> void:
	var state := AbilitiesState.new()
	state.ingest(_Const.CH_CHAR_ABILITIES, {"abilities": ["junk", 3.0, {"key": "k"}]})

	_expect(state.rows.size() == 1, "a row that is not a dictionary is dropped")
	_expect(state.row_at(0)["tip"]["lines"].is_empty(), "a row with no tip reads an empty tip")

	state.ingest(_Const.CH_CHAR_ABILITIES, {"abilities": "junk"})
	_expect(state.rows.is_empty(), "a list that is not a list is no rows")


func _reset_forgets_everything() -> void:
	var state := AbilitiesState.new()
	state.ingest(_Const.CH_CHAR_ABILITIES, payload())

	state.reset()

	_expect(not state.has_data, "reset clears the flag")
	_expect(state.rows.is_empty(), "and the rows")
	_expect(state.active_row().is_empty(), "and the active row")


func _each_key_of_the_table_fires_its_slot() -> void:
	# Iterate the table, never enumerate it: a key added later is covered.
	for slot: int in AbilityKeys.SLOTS.size():
		var row: Dictionary = AbilityKeys.SLOTS[slot]
		var event := _press(row[AbilityKeys.ROW_KEYCODE], bool(row[AbilityKeys.ROW_SHIFT]))

		_expect(AbilityKeys.slot_for(event) == slot,
			"key %s fires slot %d" % [row[AbilityKeys.ROW_LABEL], slot])
		_expect(not AbilityKeys.label_for(slot).is_empty(),
			"slot %d has a label" % slot)


func _a_shifted_press_does_not_fire_an_unshifted_row() -> void:
	var row: Dictionary = AbilityKeys.SLOTS[0]
	var event := _press(row[AbilityKeys.ROW_KEYCODE], not bool(row[AbilityKeys.ROW_SHIFT]))

	_expect(AbilityKeys.slot_for(event) == AbilityKeys.NO_SLOT,
		"the other shift state of the first key fires no slot")


func _a_press_with_ctrl_fires_nothing() -> void:
	var row: Dictionary = AbilityKeys.SLOTS[0]
	var event := _press(row[AbilityKeys.ROW_KEYCODE], bool(row[AbilityKeys.ROW_SHIFT]), true)

	_expect(AbilityKeys.slot_for(event) == AbilityKeys.NO_SLOT, "Ctrl belongs to the window")


func _a_key_outside_the_table_fires_nothing() -> void:
	_expect(AbilityKeys.slot_for(_press(KEY_F11)) == AbilityKeys.NO_SLOT,
		"a key outside the table fires no slot")


func _a_slot_past_the_table_has_no_label() -> void:
	_expect(AbilityKeys.label_for(AbilityKeys.slot_count()).is_empty(),
		"a slot past the table has no label")


func _the_tip_text_puts_the_title_first_and_skips_empty_lines() -> void:
	var tip := TipText.read({"title": "Fire", "lines": ["One.", "", "Two."]})
	var text := TipText.format(tip, ["", "Locked."])

	_expect(text == "Fire\nOne.\nTwo.\nLocked.", "title, lines, extra, no blanks: %s" % text)
	_expect(TipText.format(TipText.read("junk")).is_empty(), "no tip is no text")
