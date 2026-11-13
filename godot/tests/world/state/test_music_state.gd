extends Node
## Unit tests for MusicState, the model behind the Music tab and the player.
##
##     godot --headless --path godot res://tests/world/state/test_music_state.tscn
##
## Needs nothing running. The payloads are hand-built, in the shape that
## the JSON parser of Godot gives.

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_another_channel_is_not_ours()
	_a_snapshot_is_read_in_the_servers_order()
	_the_area_is_read()
	_a_row_is_found_by_its_key()
	_the_unlocked_rows_are_filtered_by_state_and_area()
	_malformed_rows_are_skipped()
	_reset_forgets_everything()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: music_state")
	get_tree().quit(0)


static func payload() -> Dictionary:
	return {
		_Const.MUSIC_AREA_KEY: "azm_plains",
		_Const.MUSIC_ROWS_KEY: [
			{"key": "frigid_memory", "name": "Frigid Memory",
			 "area": "azm_plains", "state": "unlocked", "hint": ""},
			{"key": "dune_song", "name": "Dune Song",
			 "area": "azm_plains", "state": "locked", "hint": "Walk the dunes."},
			{"key": "oasis_calm", "name": "Oasis Calm",
			 "area": "oasis", "state": "unlocked", "hint": ""},
		],
	}


func _expect(condition: bool, message: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("FAIL: %s" % message)


func _another_channel_is_not_ours() -> void:
	var state := MusicState.new()

	_expect(not state.ingest(_Const.CH_CHAR_QUESTS, {}), "a quest snapshot is refused")
	_expect(not state.has_data, "and the model still has nothing")


func _a_snapshot_is_read_in_the_servers_order() -> void:
	var state := MusicState.new()
	var fired := [0]

	state.changed.connect(func(): fired[0] += 1)

	_expect(state.ingest(_Const.CH_CHAR_MUSIC, payload()), "ours is taken")
	_expect(state.has_data, "and the model has data")
	_expect(fired[0] == 1, "and changed fired one time")
	_expect(state.rows.size() == 3, "three rows")
	_expect(str(state.rows[0]["key"]) == "frigid_memory", "the first row is the first of the server")
	_expect(str(state.rows[1]["hint"]) == "Walk the dunes.", "a locked row keeps its hint")
	_expect(str(state.rows[2]["area"]) == "oasis", "a row keeps its area")


func _the_area_is_read() -> void:
	var state := MusicState.new()

	state.ingest(_Const.CH_CHAR_MUSIC, payload())
	_expect(state.area == "azm_plains", "the area of the snapshot")

	var off_world := payload()
	off_world[_Const.MUSIC_AREA_KEY] = ""
	state.ingest(_Const.CH_CHAR_MUSIC, off_world)
	_expect(state.area == "", "an empty area is read as empty")


func _a_row_is_found_by_its_key() -> void:
	var state := MusicState.new()

	state.ingest(_Const.CH_CHAR_MUSIC, payload())
	_expect(str(state.row_for("dune_song")["name"]) == "Dune Song", "a row by its key")
	_expect(state.row_for("no_such").is_empty(), "an unknown key gives an empty row")
	_expect(state.is_unlocked("frigid_memory"), "an unlocked row is unlocked")
	_expect(not state.is_unlocked("dune_song"), "a locked row is not")
	_expect(not state.is_unlocked("no_such"), "an unknown key is not")


func _the_unlocked_rows_are_filtered_by_state_and_area() -> void:
	var state := MusicState.new()

	state.ingest(_Const.CH_CHAR_MUSIC, payload())
	_expect(state.unlocked_count() == 2, "two rows are unlocked")
	_expect(state.unlocked_rows().size() == 2, "and the list has the two")
	_expect(state.unlocked_rows_in("azm_plains").size() == 1, "one of them is in the area")
	_expect(str(state.unlocked_rows_in("azm_plains")[0]["key"]) == "frigid_memory",
		"and it is the right one")
	_expect(state.unlocked_rows_in("nowhere").is_empty(), "an unknown area has none")


func _malformed_rows_are_skipped() -> void:
	var state := MusicState.new()

	state.ingest(_Const.CH_CHAR_MUSIC,
		{_Const.MUSIC_ROWS_KEY: ["junk", 3.0, {"key": "k", "state": "unlocked"}]})
	_expect(state.rows.size() == 1, "a string and a number are skipped")
	_expect(str(state.rows[0]["name"]) == "", "a missing field reads as empty")

	state.ingest(_Const.CH_CHAR_MUSIC, {_Const.MUSIC_ROWS_KEY: "junk"})
	_expect(state.rows.is_empty(), "rows that are not a list read as none")


func _reset_forgets_everything() -> void:
	var state := MusicState.new()

	state.ingest(_Const.CH_CHAR_MUSIC, payload())
	state.reset()
	_expect(not state.has_data, "no data after a reset")
	_expect(state.rows.is_empty(), "no rows after a reset")
	_expect(state.area == "", "no area after a reset")
