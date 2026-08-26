extends Node
## Unit tests for SummaryState.
##
##     godot --headless --path godot res://tests/test_summary_state.tscn

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_panels_arrive_in_the_servers_order()
	_a_panel_this_client_has_never_heard_of_still_renders()
	_a_panel_reporting_nothing_is_kept()
	_values_render_for_a_human()
	_floats_that_are_whole_print_as_ints()
	_nested_values_render_one_level()
	_a_malformed_payload_is_survived()
	_an_unknown_channel_is_refused()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: summary_state")
	get_tree().quit(0)


func _payload() -> Dictionary:
	return {"panels": {
		"vitals": {"hp": 31.0, "max_hp": 40.0, "combat_level": 7.0,
				   "in_combat": false, "aura": "none"},
		"skills": {"cutting": 7.0, "metalsmithing": 12.0},
		"holdings": {},
		"a_band_added_tomorrow": {"some_field": "some value"},
	}}


func _panels_arrive_in_the_servers_order() -> void:
	# PANEL_REGISTRY decides order for the text dossier, and Godot's JSON
	# parser preserves document order -- so the two screens agree without
	# either of them saying so.
	var summary := SummaryState.new()
	summary.ingest(_Const.CH_CHAR_SUMMARY, _payload())

	var keys := summary.panel_keys()

	_expect(summary.has_data, "data after the first payload")
	_expect(keys.size() == 4, "every panel is kept")
	_expect(keys[0] == "vitals" and keys[1] == "skills",
		"panels keep the order the server sent them in")


func _a_panel_this_client_has_never_heard_of_still_renders() -> void:
	# The whole contract: adding a band is ONE file under panel_defs/.
	var summary := SummaryState.new()
	summary.ingest(_Const.CH_CHAR_SUMMARY, _payload())

	var rows := summary.rows_for("a_band_added_tomorrow")

	_expect(rows.size() == 1, "an unknown panel produces rows")
	_expect(rows[0][0] == "Some Field", "its field name is humanised")
	_expect(rows[0][1] == "some value", "and its value carries through")


func _a_panel_reporting_nothing_is_kept() -> void:
	# A panel legitimately reports nothing when the system behind it has
	# nothing to say. Dropping it would make a quiet band look like a removed
	# one.
	var summary := SummaryState.new()
	summary.ingest(_Const.CH_CHAR_SUMMARY, _payload())

	_expect(summary.panels.has("holdings"), "an empty panel is still a panel")
	_expect(summary.rows_for("holdings").is_empty(), "and has no rows")
	_expect(summary.rows_for("not_a_panel").is_empty(),
		"an unknown key returns an empty array, never null")


func _values_render_for_a_human() -> void:
	var summary := SummaryState.new()
	summary.ingest(_Const.CH_CHAR_SUMMARY, _payload())

	var rows := summary.rows_for("vitals")
	var seen: Dictionary = {}

	for row: Array in rows:
		seen[str(row[0])] = str(row[1])

	_expect(seen.get("Hp") == "31", "an int renders bare")
	_expect(seen.get("Max Hp") == "40", "a snake_case field is humanised")
	_expect(seen.get("In Combat") == "no", "a bool reads as yes/no")


func _floats_that_are_whole_print_as_ints() -> void:
	# Every number in a parsed payload is a float. "Combat level 7.0" is wrong
	# on a screen a player reads.
	_expect(SummaryState.render_value(7.0) == "7", "a whole float prints as an int")
	_expect(SummaryState.render_value(0.0) == "0", "including zero")
	_expect(SummaryState.render_value(1.5) == "1.5",
		"a genuinely fractional value keeps its point")


func _nested_values_render_one_level() -> void:
	# summary_data promises every value survives json.dumps, so arrays and
	# nested dicts are possible even if no panel uses one today.
	_expect(SummaryState.render_value([1.0, 2.0]) == "1, 2", "an array joins")
	_expect(SummaryState.render_value({"a_key": 3.0}) == "A Key 3",
		"a nested dict renders inline")
	_expect(SummaryState.render_value(null).is_empty(), "null renders as nothing")


func _a_malformed_payload_is_survived() -> void:
	# A dossier is a read-only screen. Refusing to draw it because one band is
	# broken helps nobody.
	var summary := SummaryState.new()
	summary.ingest(_Const.CH_CHAR_SUMMARY,
		{"panels": {"good": {"x": 1.0}, "bad": "not a dict", "worse": 7.0}})

	_expect(summary.panels.size() == 1, "non-dictionary panels are dropped")
	_expect(summary.panels.has("good"), "and the good one survives")

	summary.ingest(_Const.CH_CHAR_SUMMARY, {"panels": "junk"})
	_expect(summary.panels.is_empty(), "a junk panels field yields nothing")
	_expect(summary.has_data, "but it still counts as having been told")


func _an_unknown_channel_is_refused() -> void:
	var summary := SummaryState.new()

	_expect(not summary.ingest("char_vitals", {}), "another channel is refused")
	_expect(not summary.has_data, "and changes nothing")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
