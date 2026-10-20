extends Node
## Unit tests for PerformanceView.
##
##     godot --headless --path godot res://tests/test_performance_view.tscn
##
## Needs nothing running. It checks what a screenshot does not show. The
## view never takes a click. Every number it prints comes from the model.
## The geometry puts each sample where the graph says it is.

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0
var _now := {"msec": 10_000}


func _ready() -> void:
	_the_client_line_names_the_frame_rate_and_the_peak()
	_the_server_line_waits_then_names_the_tick_then_names_a_stall()
	_the_work_line_names_the_failing_handlers_only_when_there_are_some()
	_the_ceiling_keeps_the_guide_inside_the_graph()
	_samples_fill_the_rect_from_the_left_and_a_full_ring_reaches_the_right()
	_the_view_takes_no_click_and_has_a_height()
	_a_hidden_view_records_no_frames()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: performance_view")
	get_tree().quit(0)


func _state() -> PerformanceState:
	var state := PerformanceState.new()
	state.clock = func() -> int: return _now["msec"]

	return state


func _reading(tick: int, interval: float, duration: float, late: bool) -> Dictionary:
	return {"tick": float(tick), "interval": interval, "duration": duration,
		"handlers": 3.0, "failing": 0.0, "late": late}


func _the_client_line_names_the_frame_rate_and_the_peak() -> void:
	var state := _state()

	_expect(PerformanceView.client_line(state).begins_with("client: waiting"),
		"no frame reads as waiting")

	for _frame: int in 10:
		state.record_frame(0.02)

	var line := PerformanceView.client_line(state)

	_expect(line.begins_with("50 fps"), "the frame rate leads: %s" % line)
	_expect(line.contains("20.0 ms"), "the mean frame time follows: %s" % line)
	_expect(line.contains("peak 20.0 ms"), "and the peak ends it: %s" % line)


func _the_server_line_waits_then_names_the_tick_then_names_a_stall() -> void:
	var state := _state()

	_expect(PerformanceView.server_line(state).begins_with("server: waiting"),
		"no tick reads as waiting")

	_now["msec"] = 10_000
	state.ingest(_Const.CH_TICK_PERF, _reading(41, 0.6, 0.002, false))
	state.ingest(_Const.CH_TICK_PERF, _reading(42, 0.7, 0.002, true))

	var line := PerformanceView.server_line(state)

	_expect(line.begins_with("tick 42"), "the tick number leads: %s" % line)
	_expect(line.contains("700 ms"), "the newest gap follows, in ms: %s" % line)
	_expect(line.contains("peak 700 ms"), "then the peak gap: %s" % line)
	_expect(line.contains("3 handlers"), "then the rotation: %s" % line)
	_expect(line.contains("1 late"), "and the late count the server flagged: %s" % line)

	_now["msec"] = 10_000 + int(PerformanceView.STALL_SECONDS * 1000.0) + 500

	line = PerformanceView.server_line(state)
	_expect(line.begins_with("server: no tick for"), "a silence names a stall: %s" % line)


func _the_work_line_names_the_failing_handlers_only_when_there_are_some() -> void:
	var state := _state()

	_expect(PerformanceView.work_line(state).is_empty(), "no tick, no work line")

	state.ingest(_Const.CH_TICK_PERF, _reading(1, 0.6, 0.0021, false))

	var line := PerformanceView.work_line(state)
	_expect(line.begins_with("work 2.1 ms"), "the newest work leads: %s" % line)
	_expect(not line.contains("failing"), "no failing handler, no word of one: %s" % line)

	var failing := _reading(2, 0.6, 0.0084, false)
	failing["failing"] = 2.0
	state.ingest(_Const.CH_TICK_PERF, failing)

	line = PerformanceView.work_line(state)
	_expect(line.contains("peak 8.4 ms"), "the peak work follows: %s" % line)
	_expect(line.contains("2 failing"), "and a failing handler is named: %s" % line)


func _the_ceiling_keeps_the_guide_inside_the_graph() -> void:
	var quiet := PackedFloat32Array([1.0, 2.0])

	_expect(is_equal_approx(PerformanceView.ceiling_for(quiet, 16.0),
		16.0 * PerformanceView.CEILING_OVER_GUIDE),
		"a quiet series leaves the guide under the top")

	var loud := PackedFloat32Array([1.0, 50.0])

	_expect(is_equal_approx(PerformanceView.ceiling_for(loud, 16.0), 50.0),
		"a spike becomes the ceiling")


func _samples_fill_the_rect_from_the_left_and_a_full_ring_reaches_the_right() -> void:
	var rect := Rect2(10.0, 20.0, 100.0, 40.0)
	var values := PackedFloat32Array([0.0, 50.0, 100.0])

	var points := PerformanceView.scale_points(values, 3, rect, 100.0)

	_expect(points.size() == 3, "one point for each sample")
	_expect(points[0].is_equal_approx(Vector2(10.0, 60.0)),
		"the oldest sits at the left edge, and zero at the bottom")
	_expect(points[1].is_equal_approx(Vector2(60.0, 40.0)), "half way up at half the ceiling")
	_expect(points[2].is_equal_approx(Vector2(110.0, 20.0)),
		"a full ring reaches the right edge, and the ceiling the top")

	var partial := PerformanceView.scale_points(PackedFloat32Array([100.0]), 5, rect, 100.0)
	_expect(partial[0].x < rect.end.x, "a ring that is not full stops short of the right")

	var over := PerformanceView.scale_points(PackedFloat32Array([250.0]), 1, rect, 100.0)
	_expect(is_equal_approx(over[0].y, rect.position.y), "a sample over the ceiling is clamped")

	_expect(is_equal_approx(PerformanceView.guide_y(rect, 50.0, 100.0), 40.0),
		"the guide sits at its share of the height")


func _the_view_takes_no_click_and_has_a_height() -> void:
	var view := PerformanceView.new()
	add_child(view)
	view.bind(_state())

	_expect(view.mouse_filter == Control.MOUSE_FILTER_IGNORE, "the view ignores the mouse")
	_expect(view.get_child_count() == 0, "and has no child that could take it")
	_expect(view.custom_minimum_size.y > 0.0, "it asks for the height of its three blocks")
	_expect(is_equal_approx(view.custom_minimum_size.y, PerformanceView.card_height()),
		"and that height is the card height")

	view.queue_free()


func _a_hidden_view_records_no_frames() -> void:
	var view := PerformanceView.new()
	add_child(view)
	var state := _state()
	view.bind(state)

	_expect(view.is_processing(), "a shown view records frames")

	view.visible = false

	_expect(not view.is_processing(), "a hidden view does not")

	state.record_frame(0.016)
	view.visible = true

	_expect(view.is_processing(), "a view that comes back records again")
	_expect(not state.has_frames(), "and starts its frame graph over")

	view.queue_free()


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
