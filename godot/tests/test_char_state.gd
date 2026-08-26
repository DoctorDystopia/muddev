extends Node
## Unit tests for CharState. Needs no server and no account -- every payload is
## hand-built in the shape Godot's JSON parser produces, which is the point:
## every number arrives as a FLOAT.
##
##     godot --headless --path godot res://tests/test_char_state.tscn
##
## Exits 0 when every case passes, 1 on any failure.

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_floats_become_ints()
	_an_unknown_channel_is_refused()
	_health_fraction_never_divides_by_zero()
	_no_vitals_is_not_the_same_as_no_health()
	_levels_are_open_and_converted()
	_is_me_is_false_before_the_avatar_arrives()
	_changed_fires_once_per_ingest()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: char_state")
	get_tree().quit(0)


# ─── Cases ───────────────────────────────────────────────────────────────────

func _floats_become_ints() -> void:
	# The silent failure this guards: 19.0 never matches a key written as 19,
	# and "%d/%d" on floats prints something that only looks right.
	var state := CharState.new()

	state.ingest(_Const.CH_CHAR_VITALS, {"hp": 19.0, "max_hp": 40.0})
	state.ingest(_Const.CH_CHAR_AVATAR,
		{"entity_id": 19863.0, "asset": "player_character", "family": "character"})

	_expect(state.hp == 19 and typeof(state.hp) == TYPE_INT, "hp is an int")
	_expect(state.max_hp == 40, "max_hp is an int")
	_expect(state.entity_id == 19863, "entity_id is an int")
	_expect(state.asset == "player_character", "asset carries through")


func _an_unknown_channel_is_refused() -> void:
	# ingest() reporting false is what lets console.gd route without a second
	# match on channel names that could drift from this file.
	var state := CharState.new()

	_expect(not state.ingest("blackout_map", {"z": "oasis"}),
		"a channel this model does not own is refused")
	_expect(state.ingest(_Const.CH_CHAR_STATUS, {"in_combat": true}),
		"a channel it does own is claimed")


func _health_fraction_never_divides_by_zero() -> void:
	var state := CharState.new()

	_expect(is_equal_approx(state.health_fraction(), 0.0),
		"no data is a zero fraction, not a division by zero")

	state.ingest(_Const.CH_CHAR_VITALS, {"hp": 10.0, "max_hp": 0.0})
	_expect(is_equal_approx(state.health_fraction(), 0.0),
		"a zero maximum is a zero fraction")

	state.ingest(_Const.CH_CHAR_VITALS, {"hp": 30.0, "max_hp": 40.0})
	_expect(is_equal_approx(state.health_fraction(), 0.75), "3/4 health")

	# Overheal must not drive a bar past its end.
	state.ingest(_Const.CH_CHAR_VITALS, {"hp": 60.0, "max_hp": 40.0})
	_expect(is_equal_approx(state.health_fraction(), 1.0), "overheal clamps to 1")


func _no_vitals_is_not_the_same_as_no_health() -> void:
	# Without this distinction a player who has just logged in sees an empty
	# bar and reads it as being dead.
	var state := CharState.new()

	_expect(not state.has_vitals, "vitals are absent before the first message")

	state.ingest(_Const.CH_CHAR_VITALS, {"hp": 0.0, "max_hp": 40.0})

	_expect(state.has_vitals, "vitals are present once sent, even on zero hp")
	_expect(state.hp == 0, "and zero really is zero")


func _levels_are_open_and_converted() -> void:
	# The server owns which skills exist; a skill added under skill_defs/ must
	# arrive here with no edit in the client.
	var state := CharState.new()

	state.ingest(_Const.CH_CHAR_STATUS, {
		"in_combat": false,
		"levels": {"cutting": 7.0, "a_skill_invented_tomorrow": 3.0},
	})

	_expect(state.levels.get("cutting") == 7, "a level is an int")
	_expect(state.levels.get("a_skill_invented_tomorrow") == 3,
		"a skill this client has never heard of still arrives")

	state.ingest(_Const.CH_CHAR_STATUS, {"in_combat": false, "levels": "junk"})
	_expect(state.levels.is_empty(), "a malformed levels field is dropped, not fatal")


func _is_me_is_false_before_the_avatar_arrives() -> void:
	# entity_id defaults to 0, and combat payloads carry 0 for a missing target.
	# Comparing them directly would make every such event look like it was
	# about the observer -- a white flash on yourself for someone else's miss.
	var state := CharState.new()

	_expect(not state.is_me(0), "an unknown id is not the observer")

	state.ingest(_Const.CH_CHAR_AVATAR, {"entity_id": 42.0})

	_expect(state.is_me(42), "the observer's own id matches")
	_expect(not state.is_me(0), "a missing target id still does not match")


func _changed_fires_once_per_ingest() -> void:
	# The HUD redraws on this signal; firing on a refused channel would redraw
	# on every map chunk.
	var state := CharState.new()
	var counter := {"n": 0}

	state.changed.connect(func(): counter["n"] += 1)

	state.ingest(_Const.CH_CHAR_VITALS, {"hp": 1.0, "max_hp": 2.0})
	state.ingest("blackout_map", {})

	_expect(counter["n"] == 1, "changed fires for ours and not for others")


# ─── Private helpers ─────────────────────────────────────────────────────────

func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
