extends Node
## Unit tests for SessionReadiness. Needs no server, no account, no socket and
## no clock -- every case calls the STATIC rule with the elapsed times it wants
## to test, which is the whole reason that rule takes them as arguments.
##
##     godot --headless --path godot res://tests/test_session_readiness.tscn
##
## Exits 0 when every case passes, 1 on any failure.

const _Const := preload("res://autoload/blackout_constants.gd")

const _Phase := SessionReadiness.Phase

## Long enough to be past the settle window, short of the ceiling. Named so a
## case reads as "the art has been quiet" rather than as a bare float.
const SETTLED := SessionReadiness.SETTLE_SECONDS + 0.1

## A wait that has not hit any deadline.
const EARLY := 0.5

var _failures := 0


func _ready() -> void:
	_no_body_is_the_login_screen_not_a_loading_one()
	_each_missing_fact_names_itself()
	_the_facts_are_tested_independently_of_arrival_order()
	_an_empty_flight_is_not_yet_finished()
	_a_second_batch_re_veils_within_the_settle_window()
	_everything_present_and_quiet_is_ready()
	_the_ceiling_wins_over_whatever_is_missing()
	_a_skip_wins_immediately()
	_only_the_loading_phases_draw_the_veil()
	await _the_live_node_walks_the_phases()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: session_readiness")
	get_tree().quit(0)


# ─── Cases ───────────────────────────────────────────────────────────────────

func _no_body_is_the_login_screen_not_a_loading_one() -> void:
	# The trap this guards: a veil that treats "not ready" as "draw me" covers
	# the login form, and the player has no way to log in at all.
	var phase := SessionReadiness.phase_for(false, false, false, 0, 0.0, 0.0, false)

	_expect(phase == _Phase.OFFSTAGE, "no body reports OFFSTAGE")
	_expect(not SessionReadiness.is_loading(phase),
		"OFFSTAGE does not draw the veil")

	# Still OFFSTAGE even when everything else somehow looks finished: without a
	# puppeted character there is nothing to be ready FOR.
	_expect(SessionReadiness.phase_for(false, true, true, 0, SETTLED, EARLY,
		false) == _Phase.OFFSTAGE, "no body outranks every other fact")


func _each_missing_fact_names_itself() -> void:
	# The point of naming them: "Loading" for eight seconds is indistinguishable
	# from a hang, and the phase is what makes a stall diagnosable.
	_expect(SessionReadiness.phase_for(true, false, false, 0, SETTLED, EARLY,
		false) == _Phase.PLACING, "a body with no room reports PLACING")

	_expect(SessionReadiness.phase_for(true, true, false, 0, SETTLED, EARLY,
		false) == _Phase.MAPPING, "a room with an incomplete map reports MAPPING")

	_expect(SessionReadiness.phase_for(true, true, true, 3, 0.0, EARLY,
		false) == _Phase.ART, "a complete map with models in flight reports ART")


func _the_facts_are_tested_independently_of_arrival_order() -> void:
	# They do arrive in order today. Nothing in the rule may DEPEND on that, or
	# a server that reorders them reports a phase that is merely stale.
	#
	# A map that completed before room_info named it is the real case: chunks
	# for a map are sent on their own channel and do not wait on the room.
	_expect(SessionReadiness.phase_for(true, false, true, 0, SETTLED, EARLY,
		false) == _Phase.PLACING,
		"a complete map still reports PLACING while the room is unknown")

	# And art that finished before the map did.
	_expect(SessionReadiness.phase_for(true, true, false, 0, SETTLED, EARLY,
		false) == _Phase.MAPPING,
		"quiet art still reports MAPPING while chunks are outstanding")


func _an_empty_flight_is_not_yet_finished() -> void:
	# THE BUG THIS EXISTS FOR. Models are fetched lazily as things are drawn, so
	# the in-flight set empties between batches -- the terrain asks for its
	# tiles, and a moment later the entity layer asks for the NPCs standing on
	# them. Lifting on the first zero shows a room with nobody in it.
	_expect(SessionReadiness.phase_for(true, true, true, 0, 0.0, EARLY,
		false) == _Phase.ART,
		"zero in flight is still ART until the settle window has passed")

	_expect(SessionReadiness.phase_for(true, true, true, 0,
		SessionReadiness.SETTLE_SECONDS - 0.01, EARLY, false) == _Phase.ART,
		"a hair inside the settle window is still ART")


func _a_second_batch_re_veils_within_the_settle_window() -> void:
	# The other half of the same rule: a request arriving during the quiet
	# window has to put the phase back, not be averaged away.
	_expect(SessionReadiness.phase_for(true, true, true, 2, SETTLED, EARLY,
		false) == _Phase.ART,
		"anything in flight is ART however long the last quiet ran")


func _everything_present_and_quiet_is_ready() -> void:
	_expect(SessionReadiness.phase_for(true, true, true, 0, SETTLED, EARLY,
		false) == _Phase.READY, "all four facts and a settled queue is READY")


func _the_ceiling_wins_over_whatever_is_missing() -> void:
	# A player whose art never arrives must still be given their game. Checked
	# BEFORE the missing-fact branches for exactly this reason: a session that
	# never receives a map would otherwise report MAPPING forever and the
	# ceiling would be unreachable.
	var stuck := SessionReadiness.phase_for(true, false, false, 4, 0.0,
		SessionReadiness.CEILING_SECONDS, false)

	_expect(stuck == _Phase.READY,
		"the ceiling releases a session that is missing everything")

	_expect(SessionReadiness.phase_for(true, false, false, 4, 0.0,
		SessionReadiness.CEILING_SECONDS - 0.1, false) == _Phase.PLACING,
		"a hair under the ceiling still reports what is missing")


func _a_skip_wins_immediately() -> void:
	# No waiting period and no deadline: the player asked.
	_expect(SessionReadiness.phase_for(true, false, false, 9, 0.0, 0.0,
		true) == _Phase.READY, "a skip releases the veil at once")

	# But it cannot conjure a body. Skipping at the login form would hide a
	# form the player still has to use.
	_expect(SessionReadiness.phase_for(false, false, false, 0, 0.0, 0.0,
		true) == _Phase.OFFSTAGE, "a skip does not outrank a missing body")


func _only_the_loading_phases_draw_the_veil() -> void:
	# Derived from the enum rather than listed, so a phase added later is
	# covered here without an edit -- and has to be classified deliberately.
	var loading := [_Phase.PLACING, _Phase.MAPPING, _Phase.ART]

	for name: String in _Phase:
		var phase: int = _Phase[name]
		var expected: bool = loading.has(phase)

		_expect(SessionReadiness.is_loading(phase) == expected,
			"%s %s the veil" % [name, "draws" if expected else "does not draw"])



## The other half: the node, its Timer and the four live reads.
##
## Everything above tests the RULE with numbers handed to it. This drives the
## real thing over real time, through the models' own public API, and is the
## only case that can catch the wiring the rule cannot see -- a read pointed at
## the wrong field, a clock that never starts, a tick that stops early.
func _the_live_node_walks_the_phases() -> void:
	var char_state := CharState.new()
	var world := WorldState.new()
	var meshes := MeshResolver.new(ModelRegistry.new(), "")
	add_child(meshes)

	var readiness := SessionReadiness.new()
	readiness.bind(char_state, world, meshes)
	add_child(readiness)

	await _ticks()
	_expect(readiness.phase() == _Phase.OFFSTAGE,
		"live: no body is OFFSTAGE, so the login form is left alone")

	char_state.ingest(_Const.CH_CHAR_VITALS, {"hp": 5.0, "max_hp": 5.0})
	await _ticks()
	_expect(readiness.phase() == _Phase.PLACING,
		"live: vitals alone put the veil up at PLACING")

	world.ingest_room_info({"coords": [1.0, 2.0, "oasis"]})
	await _ticks()
	_expect(readiness.phase() == _Phase.MAPPING,
		"live: a named room moves it to MAPPING")

	# Straight to READY, with no ART phase at all, and that is correct rather
	# than a skipped step. Nothing was ever fetched in this test, so the art has
	# been quiet since the body arrived and the settle window closed long before
	# the map did -- which is exactly the real case of a client whose models are
	# all already cached. The window delays a session that HAS art coming; it is
	# not a toll every login pays.
	#
	# Asserting ART here instead is the mistake this comment exists to stop
	# somebody making twice: the first draft of this case did, and the failure
	# read like a bug in the settle window rather than a wrong expectation.
	# The window itself is covered above, by the cases that hand `phase_for` the
	# quiet directly.
	world.ingest_map_chunk({"z": "oasis", "chunk_index": 0, "chunk_count": 1,
		"nodes": [], "links": []})
	await _ticks()
	_expect(readiness.phase() == _Phase.READY,
		"live: a session with no art to fetch is not held by the settle window")
	_expect(not readiness.is_veiled(), "live: READY stops drawing the veil")

	# A drop is a new session: the next login is waited for again.
	readiness.reset()
	char_state.reset()
	await _ticks()
	_expect(readiness.phase() == _Phase.OFFSTAGE,
		"live: a reset session waits for the next login")

	readiness.queue_free()
	meshes.queue_free()


# ─── Private helpers ─────────────────────────────────────────────────────────

## Let a few poll ticks run, so a phase change has actually been published.
func _ticks() -> void:
	await _wait(SessionReadiness.POLL_SECONDS * 3.0)


func _wait(seconds: float) -> void:
	await get_tree().create_timer(seconds).timeout


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
