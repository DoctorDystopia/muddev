extends Node
## Unit tests for XpTrackerState.
##
##     godot --headless --path godot res://tests/test_xp_tracker_state.tscn
##
## Needs nothing running. Time is a Callable the tests move by hand, so an hour
## of XP per hour is measured without an hour passing.

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0

## The fake clock's reading, in seconds. Boxed so the lambda sees writes.
var _now := {"seconds": 1000.0}


func _ready() -> void:
	_nothing_is_tracked_before_an_award()
	_an_award_starts_the_session_and_counts()
	_one_message_is_one_drop_carrying_its_kind()
	_the_bar_follows_the_primary_skill_of_the_latest_award()
	_numbers_are_ints_not_floats()
	_a_skill_this_client_has_never_heard_of_is_tracked()
	_empty_and_malformed_rows_are_dropped()
	_an_unknown_channel_is_refused()
	_a_rate_waits_for_the_warm_up()
	_a_rate_is_xp_over_the_session_clock()
	_a_skill_rate_is_timed_from_that_skill()
	_a_reset_ends_the_session()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: xp_tracker_state")
	get_tree().quit(0)


func _tracker() -> XpTrackerState:
	var tracker := XpTrackerState.new()
	tracker.clock = func() -> float: return _now["seconds"]

	return tracker


## One award shaped as events.emit_xp_drop builds it, every number a float.
func _row(key: String, name: String, category: String, amount: float,
		level: float = 3.0, current: float = 40.0, needed: float = 120.0) -> Dictionary:
	return {
		"skill_key": key, "name": name, "category": category,
		"amount": amount, "level": level,
		"current_xp": current, "needed_xp": needed,
	}


func _butcher_payload() -> Dictionary:
	return {
		"kind": _Const.MSG_GATHERING,
		"awards": [
			_row("butchery", "Butchery", "Gathering", 25.0),
			_row("cutting", "Cutting", "Gathering", 5.0, 11.0, 400.0, 620.0),
		],
	}


func _hit_payload(strike: float) -> Dictionary:
	return {
		"kind": _Const.MSG_COMBAT,
		"awards": [
			_row("strike", "Strike", "Combat", strike, 42.0, 3000.0, 3400.0),
			_row("fortitude", "Fortitude", "Combat", roundf(strike / 3.0)),
		],
	}


func _nothing_is_tracked_before_an_award() -> void:
	var tracker := _tracker()

	_expect(not tracker.has_data, "a fresh tracker has no session")
	_expect(tracker.focus_row().is_empty(), "and nothing for the bar to follow")
	_expect(tracker.session_rate() == XpTrackerState.NO_RATE,
		"and no rate rather than zero")


func _an_award_starts_the_session_and_counts() -> void:
	var tracker := _tracker()
	tracker.ingest(_Const.CH_XP_DROP, _butcher_payload())
	tracker.ingest(_Const.CH_XP_DROP, _butcher_payload())

	_expect(tracker.has_data, "an award starts a session")
	_expect(tracker.total_xp == 60, "the session total is every point earned")
	_expect(is_equal_approx(tracker.started_at, _now["seconds"]),
		"timed from the first award")

	var rows := tracker.skill_rows()
	_expect(rows.size() == 2, "one row per skill trained")
	_expect(rows.size() == 2 and str(rows[0]["skill_key"]) == "butchery"
		and int(rows[0]["xp"]) == 50,
		"in the order first trained, each with its own total")


func _one_message_is_one_drop_carrying_its_kind() -> void:
	var tracker := _tracker()
	var heard: Array = []
	tracker.dropped.connect(func(kind: String, awards: Array):
		heard.append([kind, awards.size()]))

	tracker.ingest(_Const.CH_XP_DROP, _butcher_payload())

	_expect(heard.size() == 1, "one message is one drop, not one per skill")
	_expect(heard.size() == 1 and heard[0] == [_Const.MSG_GATHERING, 2],
		"carrying the server's kind and every skill in the award")


func _the_bar_follows_the_primary_skill_of_the_latest_award() -> void:
	var tracker := _tracker()
	tracker.ingest(_Const.CH_XP_DROP, _butcher_payload())
	tracker.ingest(_Const.CH_XP_DROP, _hit_payload(12.0))

	var focus := tracker.focus_row()
	_expect(tracker.focus_key == "strike", "the bar moves to the latest award")
	_expect(int(focus.get("level", 0)) == 42 and int(focus.get("needed_xp", 0)) == 3400,
		"and reads that award's progress, not an older one's")


func _numbers_are_ints_not_floats() -> void:
	var tracker := _tracker()
	tracker.ingest(_Const.CH_XP_DROP, _butcher_payload())
	var focus := tracker.focus_row()

	_expect(typeof(tracker.total_xp) == TYPE_INT, "the total is an int")
	_expect(typeof(focus["current_xp"]) == TYPE_INT, "and so is the progress")


func _a_skill_this_client_has_never_heard_of_is_tracked() -> void:
	var tracker := _tracker()
	tracker.ingest(_Const.CH_XP_DROP, {"kind": "quest", "awards": [
		_row("a_skill_added_tomorrow", "Tomorrow", "A Category Added Tomorrow", 9.0)]})

	_expect(str(tracker.focus_row().get("name", "")) == "Tomorrow",
		"a skill added on the server is tracked with the name it arrived with")


func _empty_and_malformed_rows_are_dropped() -> void:
	var tracker := _tracker()
	var drops := {"n": 0}
	tracker.dropped.connect(func(_k: String, _a: Array): drops["n"] += 1)

	var consumed := tracker.ingest(_Const.CH_XP_DROP, {"awards": [
		"not a dict", {"skill_key": "", "amount": 5.0},
		_row("strike", "Strike", "Combat", 0.0)]})

	_expect(consumed, "a message of ours with nothing usable is still ours")
	_expect(not tracker.has_data, "but it starts no session")
	_expect(drops["n"] == 0, "and draws no drop")

	tracker.ingest(_Const.CH_XP_DROP, {"awards": "junk"})
	_expect(not tracker.has_data, "a junk award list is survived")


func _an_unknown_channel_is_refused() -> void:
	var tracker := _tracker()

	_expect(not tracker.ingest(_Const.CH_CHAR_SKILLS, _butcher_payload()),
		"another channel is refused")
	_expect(not tracker.has_data, "and changes nothing")


func _a_rate_waits_for_the_warm_up() -> void:
	# Two seconds into a fight one swing reads as tens of thousands an hour.
	var tracker := _tracker()
	tracker.ingest(_Const.CH_XP_DROP, _hit_payload(40.0))
	_now["seconds"] += XpTrackerState.RATE_WARMUP_SECONDS - 1.0

	_expect(tracker.session_rate() == XpTrackerState.NO_RATE,
		"no rate is shown inside the warm-up")
	_expect(XpTrackerState.rate_per_hour(100, 0.0) == XpTrackerState.NO_RATE,
		"and zero elapsed never divides")


func _a_rate_is_xp_over_the_session_clock() -> void:
	var tracker := _tracker()
	tracker.ingest(_Const.CH_XP_DROP, _hit_payload(1500.0))
	_now["seconds"] += 1800.0

	# 1500 strike + 500 fortitude over half an hour.
	_expect(tracker.session_rate() == 4000,
		"2,000 XP in half an hour is 4,000 an hour")
	_expect(XpTrackerState.rate_per_hour(0, 3600.0) == 0,
		"and an idle hour is a real zero")


func _a_skill_rate_is_timed_from_that_skill() -> void:
	# An hour of fighting and then five minutes of butchering is not an hour of
	# Butchery.
	var tracker := _tracker()
	tracker.ingest(_Const.CH_XP_DROP, _hit_payload(900.0))
	_now["seconds"] += 3600.0
	tracker.ingest(_Const.CH_XP_DROP, _butcher_payload())
	_now["seconds"] += 300.0

	_expect(tracker.skill_rate("butchery") == 300,
		"25 Butchery in five minutes is 300 an hour")
	_expect(tracker.skill_rate("strike") == roundi(900.0 * 3600.0 / 3900.0),
		"while Strike is timed from its own first award")
	_expect(tracker.skill_rate("never_trained") == XpTrackerState.NO_RATE,
		"and an untrained skill has no rate")


func _a_reset_ends_the_session() -> void:
	var tracker := _tracker()
	tracker.ingest(_Const.CH_XP_DROP, _butcher_payload())
	tracker.reset()

	_expect(not tracker.has_data, "a reset ends the session")
	_expect(tracker.total_xp == 0 and tracker.skill_rows().is_empty(),
		"and forgets every total")

	_now["seconds"] += 500.0
	tracker.ingest(_Const.CH_XP_DROP, _butcher_payload())
	_expect(is_equal_approx(tracker.started_at, _now["seconds"]),
		"and the next award starts a new clock")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
