class_name PerformanceView
extends Control
## The performance view: the frame rate of this client and the server tick,
## each as a line of text over a graph. Drawn from [PerformanceState].
##
## ## Three graphs
##
## 1. The frame time of this client, in milliseconds, with a guide line at
##    the frame time of 60 fps. A spike here is this machine, or the browser.
## 2. The gap before each server tick, with a guide line at `TICK_SECONDS`.
##    The server marks a late tick, and the view draws a red dot on it. A
##    spike here is the server, or the path to it.
## 3. The work of each server tick: how long the engine took from the start
##    of the tick to the end of its feed phase. A tick that takes most of its
##    gap is a server that is about to run late.
##
## The two server graphs read the same channel, `blackout_tick_perf`. The
## console subscribes to it only while this view is on, because it is one
## message on every tick. See [method Console._sync_performance_subscription].
##
## ## It draws itself
##
## One [method _draw], no child controls. The view records one frame sample
## for each `_process` and redraws. Thus, it costs nothing while hidden: the
## console gates it, and a hidden view stops its process.
##
## ## It never takes a click
##
## The view sits over the world, and a graph that swallowed a click would eat
## a move meant for the tile under it. The rule [XpHudView] follows.
##
## The client owns every colour, size and unit here. The server sends
## seconds and the view shows milliseconds.
##
## Author: Nick Hobar
## Creation date: 10/16/2026

const _Const := preload("res://autoload/blackout_constants.gd")

## The frame time that the client guide line marks. A look, not a rule.
const TARGET_FPS := 60.0
const TARGET_FRAME_MS := 1000.0 / TARGET_FPS

## The tick gap that the server guide line marks, from the exported clock.
const TARGET_TICK_MS := _Const.TICK_SECONDS * 1000.0

## No tick for this long reads as a stall on the server line.
const STALL_SECONDS := 2.0

## The least ceiling of each graph, as a share over its guide line. Thus, the
## guide is always inside the graph, and a quiet series does not fill it.
const CEILING_OVER_GUIDE := 1.25

## The ceiling of the work graph before any sample passes it.
const WORK_FLOOR_MS := 10.0

## Presentation constants. All of them are the client's.
const FONT_SIZE := 12
const PADDING := 8.0
const LINE_HEIGHT := 16.0
const GRAPH_HEIGHT := 44.0
const BLOCK_GAP := 6.0
const LINE_WIDTH := 1.0
const LATE_DOT_RADIUS := 2.5

const COLOR_BACKGROUND := Color(0.043, 0.059, 0.078, 0.82)
const COLOR_TEXT := Color(0.9, 0.92, 0.94)
const COLOR_DIM := Color(0.55, 0.6, 0.66)
const COLOR_GRAPH_BACK := Color(1.0, 1.0, 1.0, 0.04)
const COLOR_GUIDE := Color(1.0, 1.0, 1.0, 0.25)
const COLOR_FRAME := Color(0.208, 0.878, 0.753)
const COLOR_TICK := Color(1.0, 0.86, 0.2)
const COLOR_WORK := Color(0.6, 0.7, 1.0, 0.85)
const COLOR_LATE := Color(0.93, 0.16, 0.16)

var _state: PerformanceState


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = Vector2(240.0, card_height())
	visibility_changed.connect(_on_visibility_changed)
	set_process(false)


func bind(state: PerformanceState) -> void:
	_state = state
	_state.changed.connect(queue_redraw)
	set_process(is_visible_in_tree())
	queue_redraw()


## The height of the card: three blocks of a line and a graph.
static func card_height() -> float:
	return PADDING * 2.0 + 3.0 * (LINE_HEIGHT + GRAPH_HEIGHT) + 2.0 * BLOCK_GAP


func _process(delta: float) -> void:
	if _state == null:
		return

	_state.record_frame(delta)
	queue_redraw()


## A hidden view records no frames. A view that comes back starts its frame
## graph again, so it shows no frames of the time that it was hidden.
func _on_visibility_changed() -> void:
	var shown := is_visible_in_tree()
	set_process(shown and _state != null)

	if shown and _state != null:
		_state.reset_frames()


# ─── Text ────────────────────────────────────────────────────────────────────

## The client line: `60 fps · 16.7 ms · peak 33.1 ms`.
static func client_line(state: PerformanceState) -> String:
	if not state.has_frames():
		return "client: waiting for a frame"

	return "%d fps · %.1f ms · peak %.1f ms" % [
		roundi(state.fps()), state.mean_frame_ms(), state.peak_frame_ms()]


## The server line: `tick 1234 · 600 ms · peak 640 ms · 3 handlers · 0 late`.
## Before the first tick it says so. After a silence it names the stall.
static func server_line(state: PerformanceState) -> String:
	if not state.has_ticks():
		return "server: waiting for a tick"

	var silence := state.seconds_since_tick()

	if silence >= STALL_SECONDS:
		return "server: no tick for %.1f s" % silence

	return "tick %d · %d ms · peak %d ms · %d handlers · %d late" % [
		state.latest_tick, roundi(state.newest_tick_interval_ms()),
		roundi(state.peak_tick_interval_ms()), state.handlers, state.late_count]


## The work line: `work 2.1 ms · peak 8.4 ms · 1 failing`.
static func work_line(state: PerformanceState) -> String:
	if not state.has_ticks():
		return ""

	var line := "work %.1f ms · peak %.1f ms" % [
		state.newest_tick_duration_ms(), state.peak_tick_duration_ms()]

	if state.failing > 0:
		line += " · %d failing" % state.failing

	return line


# ─── Geometry ────────────────────────────────────────────────────────────────

## The ceiling of a graph: the peak of the series, or the guide with room
## over it, whichever is higher.
static func ceiling_for(values: PackedFloat32Array, guide: float) -> float:
	var top := guide * CEILING_OVER_GUIDE

	for value: float in values:
		top = maxf(top, value)

	return top


## Place each sample in the rect. The oldest sample is at the left edge, and
## a full ring reaches the right edge. The ceiling is the top of the rect.
static func scale_points(values: PackedFloat32Array, capacity: int, rect: Rect2,
		ceiling: float) -> PackedVector2Array:
	var points := PackedVector2Array()
	points.resize(values.size())
	var step := rect.size.x / float(maxi(capacity - 1, 1))

	for index: int in values.size():
		var share := clampf(values[index] / ceiling, 0.0, 1.0) if ceiling > 0.0 else 0.0
		points[index] = Vector2(rect.position.x + step * index,
			rect.end.y - share * rect.size.y)

	return points


## The y of a guide value in the rect.
static func guide_y(rect: Rect2, guide: float, ceiling: float) -> float:
	if ceiling <= 0.0:
		return rect.end.y

	return rect.end.y - clampf(guide / ceiling, 0.0, 1.0) * rect.size.y


# ─── Drawing ─────────────────────────────────────────────────────────────────

func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), COLOR_BACKGROUND)

	if _state == null:
		return

	var font := get_theme_default_font()
	var y := PADDING

	y = _draw_block(font, y, client_line(_state), _state.frame_ms(),
		PerformanceState.FRAME_SAMPLES, TARGET_FRAME_MS, COLOR_FRAME, false)
	y = _draw_block(font, y, server_line(_state), _state.tick_intervals_ms(),
		PerformanceState.TICK_SAMPLES, TARGET_TICK_MS, COLOR_TICK, true)
	_draw_block(font, y, work_line(_state), _state.tick_durations_ms(),
		PerformanceState.TICK_SAMPLES, WORK_FLOOR_MS, COLOR_WORK, false, true)


## One line of text over one graph. Returns the y under the block.
func _draw_block(font: Font, top: float, text: String, values: PackedFloat32Array,
		capacity: int, guide: float, color: Color, mark_late: bool,
		as_bars := false) -> float:
	var text_color := COLOR_TEXT if values.size() > 0 else COLOR_DIM
	draw_string(font, Vector2(PADDING, top + LINE_HEIGHT - 4.0), text,
		HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, text_color)

	var rect := Rect2(PADDING, top + LINE_HEIGHT, size.x - PADDING * 2.0, GRAPH_HEIGHT)
	draw_rect(rect, COLOR_GRAPH_BACK)

	var ceiling := ceiling_for(values, guide)
	var guide_line_y := guide_y(rect, guide, ceiling)
	draw_line(Vector2(rect.position.x, guide_line_y), Vector2(rect.end.x, guide_line_y),
		COLOR_GUIDE, LINE_WIDTH)

	var points := scale_points(values, capacity, rect, ceiling)

	if as_bars:
		_draw_bars(points, rect, capacity, color)
	elif points.size() >= 2:
		draw_polyline(points, color, LINE_WIDTH)

	if mark_late:
		_draw_late_dots(points)

	return rect.end.y + BLOCK_GAP


func _draw_bars(points: PackedVector2Array, rect: Rect2, capacity: int, color: Color) -> void:
	var width := maxf(rect.size.x / float(maxi(capacity, 1)), 1.0)

	for point: Vector2 in points:
		var height := rect.end.y - point.y

		if height <= 0.0:
			continue

		draw_rect(Rect2(point.x, point.y, width, height), color)


## A red dot on each tick that the server marked late.
func _draw_late_dots(points: PackedVector2Array) -> void:
	var flags := _state.tick_late_flags()

	for index: int in mini(points.size(), flags.size()):
		if flags[index] > 0.0:
			draw_circle(points[index], LATE_DOT_RADIUS, COLOR_LATE)
