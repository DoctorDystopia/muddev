extends Node
## Tests for the skills VIEW's two jobs that can be wrong: turning a click into
## a command, and honouring the player's choice about where the answer goes.
##
## The drawing is not tested and deliberately so -- a grid of labels is cheap to
## look at and expensive to assert. What matters is that every command leaving
## this pane was NAMED BY THE SERVER, that the three detail modes each do what
## they say, and that a rebuild does not throw away the sheet the player just
## opened. Those are the parts a screenshot would not catch.
##
##     godot --headless --path godot res://tests/test_skills_view.tscn

const _Const := preload("res://autoload/blackout_constants.gd")

## Somewhere disposable, so a test run never touches the real profile.
const SETTINGS_PATH := "user://test_skills_view.cfg"

var _failures := 0
var _view: SkillsView
var _state: SkillsState
var _settings: ClientSettings
var _sent: Array[String] = []


func _ready() -> void:
	_state = SkillsState.new()
	_settings = ClientSettings.new(SETTINGS_PATH)

	_view = SkillsView.new()
	add_child(_view)
	_view.command_requested.connect(func(command: String): _sent.append(command))
	_view.bind(_state, _settings)

	_state.ingest(_Const.CH_CHAR_SKILLS, _payload())

	_a_cell_is_drawn_for_every_skill()
	_a_click_sends_the_command_the_server_named()
	_pane_only_opens_the_sheet_and_asks_for_nothing()
	_log_only_leaves_the_grid_where_it_was()
	_the_open_sheet_survives_a_republish()
	_a_sheet_for_a_skill_that_stopped_being_sent_falls_back()
	_the_sheet_lists_what_the_skill_unlocks()
	_large_numbers_are_grouped()

	DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: skills_view")
	get_tree().quit(0)


func _payload() -> Dictionary:
	return {
		"skills": [
			{
				"key": "brawn", "name": "Brawn", "category": "Combat",
				"description": "Raw force.", "level": 4.0, "max_level": 127.0,
				"current_xp": 30.0, "needed_xp": 120.0, "remaining_xp": 90.0,
				"total_xp": 400.0, "next_level_at": 490.0,
				"unlocked": true, "command": "skills brawn", "unlocks": [],
			},
			{
				"key": "cutting", "name": "Cutting", "category": "Gathering",
				"description": "Harvesting anything cuttable.",
				"level": 7.0, "max_level": 127.0,
				"current_xp": 50.0, "needed_xp": 100.0, "remaining_xp": 50.0,
				"total_xp": 1234567.0, "next_level_at": 1234617.0,
				"unlocked": true, "command": "skills cutting",
				"unlocks": [{"title": "Gathering Unlocks", "rows": [
					{"name": "Scrap pole", "level": 1.0, "note": "yields pole"},
					{"name": "Iron bough", "level": 40.0, "note": ""},
				]}],
			},
		],
		"categories": ["Combat", "Gathering"],
		"total_level": 11.0, "total_xp": 1234967.0, "max_level": 127.0,
		"closest": {"skill_key": "cutting", "level": 7.0, "current_xp": 50.0,
					"needed_xp": 100.0, "remaining_xp": 50.0},
	}


## Every cell the grid is currently drawing, in tree order.
func _cells() -> Array:
	var found: Array = []

	_collect_cells(_view, found)

	return found


func _collect_cells(node: Node, into: Array) -> void:
	for child: Node in node.get_children():
		if child is SkillCell:
			into.append(child)

		_collect_cells(child, into)


## Click one skill by key, whatever the grid's current layout is.
func _click(skill_key: String) -> bool:
	for cell: SkillCell in _cells():
		if str(cell.row().get("key", "")) == skill_key:
			cell.chosen.emit(str(cell.row().get("command", "")))
			return true

	return false


func _a_cell_is_drawn_for_every_skill() -> void:
	# Iterate, never enumerate: the grid is built from what arrived.
	_expect(_cells().size() == 2, "one cell per skill the server sent")


func _a_click_sends_the_command_the_server_named() -> void:
	# The pane composes nothing. `skills cutting` is the server's own string,
	# and a client verb table has been deleted twice here for being wrong.
	_sent.clear()
	_settings.set_skill_detail(ClientSettings.SKILL_DETAIL_BOTH)

	_expect(_click("cutting"), "the cutting cell is clickable")
	_expect(_sent == ["skills cutting"],
		"the click sends exactly the command the row carried")
	_expect(_view._selected == "cutting", "and both mode opens the sheet too")

	_view._close_detail()


func _pane_only_opens_the_sheet_and_asks_for_nothing() -> void:
	# The server cannot be asked for a skill quietly -- the command that
	# renders the sheet renders it INTO THE LOG, which is what this mode exists
	# to avoid. So it sends nothing and draws from the snapshot it already has,
	# which is complete because the server ships the whole ladder per row.
	_sent.clear()
	_settings.set_skill_detail(ClientSettings.SKILL_DETAIL_PANE)

	_click("cutting")

	_expect(_sent.is_empty(),
		"pane mode sends nothing, so no sheet lands in the log")
	_expect(_view._selected == "cutting", "and opens the sheet anyway")
	_expect(_cells().is_empty(), "the grid gives way to it")

	_view._close_detail()
	_expect(_cells().size() == 2, "and back returns the grid")


func _log_only_leaves_the_grid_where_it_was() -> void:
	_sent.clear()
	_settings.set_skill_detail(ClientSettings.SKILL_DETAIL_LOG)

	_click("cutting")

	_expect(_sent == ["skills cutting"], "log mode sends the command")
	_expect(_view._selected.is_empty(), "and opens no sheet")
	_expect(_cells().size() == 2, "leaving the grid on screen")


func _the_open_sheet_survives_a_republish() -> void:
	# LOAD-BEARING. char_skills republishes whenever a level moves, on resync,
	# and whenever the player types `skills` -- and every one of those fires
	# `changed`. A sheet that rebuilt from scratch would throw itself away the
	# moment the skill being read levelled, which is the moment a player is
	# most likely to be looking at it.
	_settings.set_skill_detail(ClientSettings.SKILL_DETAIL_PANE)
	_click("cutting")

	_state.ingest(_Const.CH_CHAR_SKILLS, _payload())

	_expect(_view._selected == "cutting", "the selection outlives a snapshot")
	_expect(_cells().is_empty(), "and the sheet is still the thing on screen")


func _a_sheet_for_a_skill_that_stopped_being_sent_falls_back() -> void:
	# A skill removed on the server disappears from the roster. The pane must
	# not be left showing a page about it.
	var thinned := _payload()
	thinned["skills"] = [thinned["skills"][0]]
	thinned["categories"] = ["Combat"]

	_state.ingest(_Const.CH_CHAR_SKILLS, thinned)

	_expect(_view._selected.is_empty(),
		"a selection nothing carries any more is dropped")
	_expect(_cells().size() == 1, "and the grid comes back")

	_state.ingest(_Const.CH_CHAR_SKILLS, _payload())


func _the_sheet_lists_what_the_skill_unlocks() -> void:
	# The unlock ladder is why the sheet is worth more than a level. It ships
	# in the snapshot, so opening it costs no round trip.
	_settings.set_skill_detail(ClientSettings.SKILL_DETAIL_PANE)
	_click("cutting")

	var text := _all_text(_view)

	_expect(text.contains("Gathering Unlocks"), "the section heading is drawn")
	_expect(text.contains("Scrap pole"), "and a reached row")
	_expect(text.contains("Iron bough"), "and one still ahead")
	_expect(text.contains("yields pole"), "with the server's note beside it")

	_view._close_detail()


func _large_numbers_are_grouped() -> void:
	# "1234967" is a number a player has to count digits on.
	_expect(SkillsView._grouped(1234967) == "1,234,967", "millions group")
	_expect(SkillsView._grouped(999) == "999", "three digits are left alone")
	_expect(SkillsView._grouped(0) == "0", "and so is zero")
	_expect(_all_text(_view).contains("1,234,967"),
		"the grid's total XP is grouped where the player reads it")


## Every Label's text under one node, joined. Cheap enough for a pane this
## size, and it keeps the assertions about CONTENT rather than about which
## container something landed in.
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
