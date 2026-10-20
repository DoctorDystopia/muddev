extends Node
## Unit tests for PerformanceState.
##
##     godot --headless --path godot res://tests/test_performance_state.tscn
##
## Needs nothing running. The payloads are hand-built in the shape that
## Godot's JSON parser produces: every number a float, the flag a bool.

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0
var _now := {"msec": 10_000}


func _ready() -> void:
	_a_ring_keeps_its_newest_samples_oldest_first()
	_frames_give_a_frame_rate_and_a_peak()
	_a_tick_reading_lands_in_every_ring()
	_the_late_count_is_the_flag_the_server_sent()
	_another_channel_is_refused()
	_silence_is_measured_by_the_injected_clock()
	_the_rings_forget_on_a_disconnect()
	_the_frames_forget_on_their_own()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: performance_state")
	get_tree().quit(0)


func _state() -> PerformanceState:
	var state := PerformanceState.new()
	state.clock = func() -> int: return _now["msec"]

	return state


func _reading(tick: int, interval: float, duration: float, late: bool) -> Dictionary:
	return {"tick": float(tick), "interval": interval, "duration": duration,
		"handlers": 3.0, "failing": 1.0, "late": late}


func _a_ring_keeps_its_newest_samples_oldest_first() -> void:
	var ring := PerformanceState.Ring.new(3)

	_expect(ring.count == 0 and ring.values().is_empty(), "an empty ring has no values")

	ring.push(1.0)
	ring.push(2.0)
	_expect(ring.values() == PackedFloat32Array([1.0, 2.0]), "two pushes read in order")

	ring.push(3.0)
	ring.push(4.0)
	_expect(ring.values() == PackedFloat32Array([2.0, 3.0, 4.0]),
		"a full ring drops its oldest sample")
	_expect(ring.count == 3, "and its count stops at the capacity")
	_expect(is_equal_approx(ring.newest(), 4.0), "the newest is the last push")
	_expect(is_equal_approx(ring.mean(), 3.0), "the mean is over the kept samples")
	_expect(is_equal_approx(ring.peak(), 4.0), "and so is the peak")


func _frames_give_a_frame_rate_and_a_peak() -> void:
	var state := _state()

	_expect(not state.has_frames() and is_zero_approx(state.fps()),
		"no frame, no frame rate")

	for _frame: int in 10:
		state.record_frame(1.0 / 60.0)

	state.record_frame(1.0 / 20.0)

	_expect(state.has_frames(), "a frame is recorded")
	_expect(absf(state.peak_frame_ms() - 50.0) < 0.01, "the peak is the slow frame in ms")
	_expect(state.fps() > 50.0 and state.fps() < 60.0,
		"the frame rate comes from the mean frame time")
	_expect(state.frame_ms().size() == 11, "every frame is in the ring")


func _a_tick_reading_lands_in_every_ring() -> void:
	var state := _state()
	var fired := [0]
	state.changed.connect(func(): fired[0] += 1)

	_expect(not state.has_ticks(), "no tick before the first reading")

	var taken := state.ingest(_Const.CH_TICK_PERF, _reading(41, 0.6, 0.002, false))
	state.ingest(_Const.CH_TICK_PERF, _reading(42, 0.65, 0.004, false))

	_expect(taken, "the channel is this model's")
	_expect(fired[0] == 2, "each reading fires changed")
	_expect(state.latest_tick == 42, "the newest tick number is kept")
	_expect(state.handlers == 3 and state.failing == 1, "and the rotation counts")
	_expect(state.tick_intervals_ms() == PackedFloat32Array([600.0, 650.0]),
		"the gap is kept in milliseconds, oldest first")
	_expect(state.tick_durations_ms() == PackedFloat32Array([2.0, 4.0]),
		"and so is the work")
	_expect(is_equal_approx(state.newest_tick_interval_ms(), 650.0), "the newest gap")
	_expect(is_equal_approx(state.peak_tick_duration_ms(), 4.0), "the peak work")


func _the_late_count_is_the_flag_the_server_sent() -> void:
	# The model holds no copy of the late rule. A gap that LOOKS late with no
	# flag is not counted, and a flagged gap is, whatever its number.
	var state := _state()

	state.ingest(_Const.CH_TICK_PERF, _reading(1, 5.0, 0.001, false))
	state.ingest(_Const.CH_TICK_PERF, _reading(2, 0.6, 0.001, true))

	_expect(state.late_count == 1, "the flag decides, not the number")
	_expect(state.tick_late_flags() == PackedFloat32Array([0.0, 1.0]),
		"and each flag sits beside its reading")


func _another_channel_is_refused() -> void:
	var state := _state()

	var taken := state.ingest(_Const.CH_CHAR_VITALS, {"hp": 10.0})

	_expect(not taken, "a vitals message is not this model's")
	_expect(not state.has_ticks(), "and leaves no reading")


func _silence_is_measured_by_the_injected_clock() -> void:
	var state := _state()

	_expect(is_equal_approx(state.seconds_since_tick(), PerformanceState.NO_TICK),
		"no tick, no silence")

	_now["msec"] = 10_000
	state.ingest(_Const.CH_TICK_PERF, _reading(1, 0.6, 0.001, false))
	_now["msec"] = 12_500

	_expect(is_equal_approx(state.seconds_since_tick(), 2.5),
		"the silence is the clock since the newest reading")


func _the_rings_forget_on_a_disconnect() -> void:
	var state := _state()
	state.ingest(_Const.CH_TICK_PERF, _reading(7, 0.6, 0.001, true))
	state.record_frame(0.016)

	state.reset_server()

	_expect(not state.has_ticks(), "the tick rings are empty")
	_expect(state.latest_tick == 0 and state.late_count == 0 and state.handlers == 0,
		"and the counts are zero")
	_expect(is_equal_approx(state.seconds_since_tick(), PerformanceState.NO_TICK),
		"and there is no silence to measure")
	_expect(state.has_frames(), "the frames are the client's and stay")


func _the_frames_forget_on_their_own() -> void:
	var state := _state()
	state.record_frame(0.016)
	state.ingest(_Const.CH_TICK_PERF, _reading(7, 0.6, 0.001, false))

	state.reset_frames()

	_expect(not state.has_frames(), "the frame ring is empty")
	_expect(state.has_ticks(), "and the ticks stay")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
