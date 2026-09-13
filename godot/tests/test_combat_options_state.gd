extends Node
## Unit tests for CombatOptionsState -- the model behind the Combat tab.
##
##     godot --headless --path godot res://tests/test_combat_options_state.tscn
##
## Needs nothing running. Payloads are hand-built in the shape Godot's JSON
## parser produces, floats and all.

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_another_channel_is_not_ours()
	_a_snapshot_is_read_and_numbers_become_ints()
	_the_active_style_is_found()
	_bare_hands_offer_no_choice()
	_malformed_rows_are_skipped()
	_reset_forgets_everything()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: combat_options_state")
	get_tree().quit(0)


static func armed_payload() -> Dictionary:
	return {
		"weapon_name": "rusty scrap shortsword", "armed": true,
		"combat_level": 12.0, "attack_speed_ticks": 4.0,
		"attack_speed_seconds": 2.4,
		"styles": [
			{"key": "irimi", "name": "Irimi", "attack_type": "stab",
			 "weapon_style": "accurate",
			 "boosts": [{"skill_key": "strike", "name": "Strike", "amount": 3.0}],
			 "xp_skills": [{"skill_key": "strike", "name": "Strike"}],
			 "active": true, "command": "combatoptions irimi"},
			{"key": "guard", "name": "Guard", "attack_type": "stab",
			 "weapon_style": "defensive",
			 "boosts": [{"skill_key": "defense", "name": "Defense", "amount": 3.0}],
			 "xp_skills": [{"skill_key": "defense", "name": "Defense"}],
			 "active": false, "command": "combatoptions guard"},
		],
	}


static func unarmed_payload() -> Dictionary:
	return {
		"weapon_name": "bare hands", "armed": false,
		"combat_level": 3.0, "attack_speed_ticks": 4.0,
		"attack_speed_seconds": 2.4,
		"styles": [
			{"key": "punch", "name": "Punch", "attack_type": "crush",
			 "weapon_style": "accurate", "boosts": [], "xp_skills": [],
			 "active": true, "command": ""},
		],
	}


func _another_channel_is_not_ours() -> void:
	var state := CombatOptionsState.new()

	_expect(not state.ingest(_Const.CH_CHAR_SKILLS, armed_payload()),
		"a payload on another channel is declined")
	_expect(not state.has_data, "and leaves the model empty")


func _a_snapshot_is_read_and_numbers_become_ints() -> void:
	var state := CombatOptionsState.new()
	var fired := [0]
	state.changed.connect(func(): fired[0] += 1)

	_expect(state.ingest(_Const.CH_CHAR_COMBAT, armed_payload()),
		"char_combat is ours")
	_expect(fired[0] == 1, "and announces itself once")
	_expect(state.weapon_name == "rusty scrap shortsword", "the weapon is named")
	_expect(state.armed, "and it is wielded")
	_expect(typeof(state.combat_level) == TYPE_INT and state.combat_level == 12,
		"combat level arrives as a float and is kept as an int")
	_expect(state.attack_speed_ticks == 4, "ticks too")
	_expect(is_equal_approx(state.attack_speed_seconds, 2.4),
		"seconds stay fractional")
	_expect(state.styles.size() == 2, "every style row is kept")

	var boost: Dictionary = state.styles[0]["boosts"][0]

	_expect(typeof(boost["amount"]) == TYPE_INT and boost["amount"] == 3,
		"a boost amount is an int")
	_expect(state.styles[1]["command"] == "combatoptions guard",
		"the server's command is kept verbatim")


func _the_active_style_is_found() -> void:
	var state := CombatOptionsState.new()
	state.ingest(_Const.CH_CHAR_COMBAT, armed_payload())

	_expect(state.active_style().get("key", "") == "irimi",
		"the row the server marked active")
	_expect(state.has_choice(), "a weapon with commands offers a choice")


func _bare_hands_offer_no_choice() -> void:
	var state := CombatOptionsState.new()
	state.ingest(_Const.CH_CHAR_COMBAT, unarmed_payload())

	_expect(not state.armed, "bare hands are not armed")
	_expect(not state.has_choice(), "and a row with no command is no choice")
	_expect(state.active_style().get("key", "") == "punch",
		"but the style they fight with is still shown")


func _malformed_rows_are_skipped() -> void:
	var state := CombatOptionsState.new()
	var payload := armed_payload()
	payload["styles"] = ["nonsense", 4.0, payload["styles"][0]]

	state.ingest(_Const.CH_CHAR_COMBAT, payload)

	_expect(state.styles.size() == 1, "only dictionaries become rows")

	payload["styles"] = "not a list"
	state.ingest(_Const.CH_CHAR_COMBAT, payload)

	_expect(state.styles.is_empty(), "and a styles field that is not a list is none")
	_expect(state.active_style().is_empty(), "with no active style to report")


func _reset_forgets_everything() -> void:
	var state := CombatOptionsState.new()
	state.ingest(_Const.CH_CHAR_COMBAT, armed_payload())
	state.reset()

	_expect(not state.has_data, "a dropped socket forgets the snapshot")
	_expect(state.styles.is_empty() and state.weapon_name.is_empty(),
		"and every field with it")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
