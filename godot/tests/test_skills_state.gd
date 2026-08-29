extends Node
## Unit tests for SkillsState.
##
##     godot --headless --path godot res://tests/test_skills_state.tscn

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_a_roster_arrives_in_the_servers_order()
	_a_skill_this_client_has_never_heard_of_is_kept()
	_rows_are_found_by_key_and_by_category()
	_numbers_are_ints_not_floats()
	_progress_is_the_level_fraction_not_the_cumulative_one()
	_a_capped_roster_reports_no_closest()
	_a_malformed_payload_is_survived()
	_an_unknown_channel_is_refused()
	_a_drop_clears_the_roster()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: skills_state")
	get_tree().quit(0)


## A payload shaped exactly as `systems/statefeed/skills.py` builds one, with
## every number a float -- which is what `JSON.parse_string` always returns.
func _payload() -> Dictionary:
	return {
		"skills": [
			{
				"key": "brawn", "name": "Brawn", "category": "Combat",
				"description": "Raw force.",
				"level": 4.0, "max_level": 127.0,
				"current_xp": 30.0, "needed_xp": 120.0, "remaining_xp": 90.0,
				"total_xp": 400.0, "next_level_at": 490.0,
				"unlocked": true, "command": "skills brawn",
				"unlocks": [],
			},
			{
				"key": "cutting", "name": "Cutting", "category": "Gathering",
				"description": "Harvesting anything cuttable.",
				"level": 7.0, "max_level": 127.0,
				"current_xp": 50.0, "needed_xp": 100.0, "remaining_xp": 50.0,
				"total_xp": 900.0, "next_level_at": 950.0,
				"unlocked": true, "command": "skills cutting",
				"unlocks": [{"title": "Gathering Unlocks", "rows": [
					{"name": "Scrap pole", "level": 1.0, "note": "yields pole"},
				]}],
			},
			{
				"key": "a_skill_added_tomorrow", "name": "Tomorrow",
				"category": "A Category Added Tomorrow",
				"description": "", "level": 1.0, "max_level": 127.0,
				"current_xp": 0.0, "needed_xp": 83.0, "remaining_xp": 83.0,
				"total_xp": 0.0, "next_level_at": 83.0,
				"unlocked": false, "command": "skills a_skill_added_tomorrow",
				"unlocks": [],
			},
		],
		"categories": ["Combat", "Gathering", "A Category Added Tomorrow"],
		"total_level": 12.0,
		"total_xp": 1300.0,
		"max_level": 127.0,
		"closest": {"skill_key": "cutting", "level": 7.0, "current_xp": 50.0,
					"needed_xp": 100.0, "remaining_xp": 50.0},
	}


func _bound() -> SkillsState:
	var state := SkillsState.new()
	state.ingest(_Const.CH_CHAR_SKILLS, _payload())

	return state


func _a_roster_arrives_in_the_servers_order() -> void:
	# The server sorts by (category, name) so the grid and the text screens
	# agree without either of them saying so. A second opinion here would be
	# the place they start to differ.
	var state := _bound()

	_expect(state.has_data, "data after the first payload")
	_expect(state.skills.size() == 3, "every row is kept")
	_expect(str(state.skills[0]["key"]) == "brawn",
		"rows keep the order the server sent them in")
	_expect(state.categories.size() == 3, "and so do the categories")


func _a_skill_this_client_has_never_heard_of_is_kept() -> void:
	# The whole contract: adding a skill is ONE file under skill_defs/, and a
	# category with no colour entry draws the fallback rather than vanishing.
	var state := _bound()
	var row := state.row_for("a_skill_added_tomorrow")

	_expect(not row.is_empty(), "an unknown skill produces a row")
	_expect(str(row["name"]) == "Tomorrow", "with the name the server gave it")
	_expect(state.rows_in("A Category Added Tomorrow").size() == 1,
		"filed under the category the server gave it")


func _rows_are_found_by_key_and_by_category() -> void:
	var state := _bound()

	_expect(str(state.row_for("cutting")["name"]) == "Cutting",
		"a row is found by key")
	_expect(state.row_for("not_a_skill").is_empty(),
		"an unknown key returns an empty dictionary, never null")
	_expect(state.rows_in("Combat").size() == 1, "a category filters")
	_expect(state.rows_in("Nothing").is_empty(),
		"an unknown category returns an empty array")


func _numbers_are_ints_not_floats() -> void:
	# Every number in a parsed payload is a float, and "%d" on one is not what
	# it looks like. Converted at ingest, as QuestState and CharState do it.
	var state := _bound()
	var row := state.row_for("cutting")

	_expect(typeof(row["level"]) == TYPE_INT, "a level is an int")
	_expect(typeof(state.total_level) == TYPE_INT, "so is the total level")
	_expect(state.total_xp == 1300, "and the total XP keeps its value")
	_expect(state.max_level == 127, "the cap arrives from the server")
	_expect(typeof(state.closest["remaining_xp"]) == TYPE_INT,
		"and the closest reading is converted too")


func _progress_is_the_level_fraction_not_the_cumulative_one() -> void:
	# current_xp / needed_xp, never total_xp -- mixing them is what once
	# produced a "1154 / 152" bar on the server's own screen.
	var state := _bound()

	_expect(is_equal_approx(
		SkillsState.level_fraction(state.row_for("cutting")), 0.5),
		"half way through a level reads as 0.5")
	_expect(is_equal_approx(
		SkillsState.level_fraction({"current_xp": 1, "needed_xp": 0}), 1.0),
		"a zero threshold reads as complete rather than dividing")
	_expect(is_equal_approx(
		SkillsState.level_fraction({"current_xp": 400, "needed_xp": 100}), 1.0),
		"and an overshoot is clamped rather than overfilling the bar")


func _a_capped_roster_reports_no_closest() -> void:
	# "Every skill is at the cap" is a real state, and the server says so with
	# an empty dict rather than a null so a client branches once, not three
	# ways.
	var payload := _payload()
	payload["closest"] = {}

	var state := SkillsState.new()
	state.ingest(_Const.CH_CHAR_SKILLS, payload)

	_expect(state.closest.is_empty(), "an empty closest stays empty")
	_expect(typeof(state.closest) == TYPE_DICTIONARY, "and stays a dictionary")


func _a_malformed_payload_is_survived() -> void:
	# A roster is a read-only screen. Refusing to draw it because one row is
	# broken helps nobody.
	var state := SkillsState.new()
	state.ingest(_Const.CH_CHAR_SKILLS, {
		"skills": [{"key": "good", "name": "Good"}, "not a dict", 7.0],
		"categories": "junk",
		"closest": "junk",
	})

	_expect(state.skills.size() == 1, "non-dictionary rows are dropped")
	_expect(state.categories.is_empty(), "a junk category list yields nothing")
	_expect(state.closest.is_empty(), "a junk closest yields nothing")
	_expect(state.has_data, "but it still counts as having been told")
	_expect(str(state.skills[0]["command"]).is_empty(),
		"a row with no command carries an empty one rather than failing")


func _an_unknown_channel_is_refused() -> void:
	var state := SkillsState.new()

	_expect(not state.ingest("char_summary", {}), "another channel is refused")
	_expect(not state.has_data, "and changes nothing")


func _a_drop_clears_the_roster() -> void:
	# A websocket close ends the Evennia Session, so levels left on screen
	# describe a character nobody is puppeting.
	var state := _bound()
	state.reset()

	_expect(not state.has_data, "a drop forgets that we were told")
	_expect(state.skills.is_empty(), "and forgets the roster")
	_expect(state.total_level == 0, "and the totals with it")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
