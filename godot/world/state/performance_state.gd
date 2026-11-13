class_name PerformanceState
extends RefCounted
## The numbers that the performance view draws: the frame time of this
## client, and the reading of each server tick from `blackout_tick_perf`.
##
## Two clocks, two owners. The frame time is the CLIENT's own reading. The
## view records one sample for each frame that it draws, and nothing here
## reaches the server. The tick reading is the SERVER's fact. The server
## says how long the gap was, how long the work took, how many handlers
## ticked, and whether the gap was late. This model holds no copy of the
## late rule. It counts the flag that the server sent.
##
## ## A ring for each series
##
## Each series is a ring of a fixed size. A full ring drops its oldest
## sample. Thus, the view draws a window that moves, and the model never
## grows. [constant FRAME_SAMPLES] frames is about four seconds at 60 fps.
## [constant TICK_SAMPLES] ticks is one minute at the shipped tick.
##
## ## The clock is injected
##
## [member clock] gives the time in milliseconds. A test sets it, so
## "no tick for two seconds" is a number and not a wait.
##
## Author: Nick Hobar
## Creation date: 10/16/2026

const _Const := preload("res://autoload/blackout_constants.gd")

## How many frame samples the frame ring keeps.
const FRAME_SAMPLES := 240

## How many tick readings the tick rings keep.
const TICK_SAMPLES := 100

const MS_PER_SECOND := 1000.0

## No tick arrived yet. [method seconds_since_tick] returns this.
const NO_TICK := -1.0

## Fired after a tick reading lands.
signal changed

## Milliseconds now. The view leaves the default. A test replaces it.
var clock := func() -> int: return Time.get_ticks_msec()

## The tick number of the newest reading. Zero before the first one.
var latest_tick := 0

## The size of the rotation and the failing handlers, from the newest reading.
var handlers := 0
var failing := 0

## How many readings in the ring the server marked late.
var late_count := 0

var _frames := Ring.new(FRAME_SAMPLES)
var _intervals := Ring.new(TICK_SAMPLES)
var _durations := Ring.new(TICK_SAMPLES)
var _late := Ring.new(TICK_SAMPLES)
var _last_tick_msec := -1


## One ring of floats. The oldest sample goes first in [method values].
class Ring extends RefCounted:
	var capacity: int
	var count := 0
	var _samples: PackedFloat32Array
	var _head := 0

	func _init(size: int) -> void:
		capacity = size
		_samples.resize(size)

	func push(value: float) -> void:
		_samples[_head] = value
		_head = (_head + 1) % capacity
		count = mini(count + 1, capacity)

	## The samples, oldest first.
	func values() -> PackedFloat32Array:
		var out := PackedFloat32Array()
		out.resize(count)
		var start := (_head - count + capacity) % capacity

		for index: int in count:
			out[index] = _samples[(start + index) % capacity]

		return out

	func newest() -> float:
		if count == 0:
			return 0.0

		return _samples[(_head - 1 + capacity) % capacity]

	func mean() -> float:
		if count == 0:
			return 0.0

		var total := 0.0

		for value: float in values():
			total += value

		return total / float(count)

	func peak() -> float:
		var top := 0.0

		for value: float in values():
			top = maxf(top, value)

		return top

	## How many samples are over zero. For a ring of flags.
	func set_count() -> int:
		var found := 0

		for value: float in values():
			if value > 0.0:
				found += 1

		return found

	func clear() -> void:
		count = 0
		_head = 0


# ─── The frame ring ──────────────────────────────────────────────────────────

## Record the time of one frame, in seconds, as `_process` gives it.
func record_frame(delta: float) -> void:
	_frames.push(delta * MS_PER_SECOND)


## Frames per second, from the mean frame time of the ring. Zero before the
## first frame.
func fps() -> float:
	var mean := _frames.mean()

	if mean <= 0.0:
		return 0.0

	return MS_PER_SECOND / mean


func frame_ms() -> PackedFloat32Array:
	return _frames.values()


func mean_frame_ms() -> float:
	return _frames.mean()


func peak_frame_ms() -> float:
	return _frames.peak()


func has_frames() -> bool:
	return _frames.count > 0


## Forget the frames. The view calls this when it comes back on screen, so
## the graph does not start with the frames of a view that was hidden.
func reset_frames() -> void:
	_frames.clear()


# ─── The tick rings ──────────────────────────────────────────────────────────

## Offer one message. Returns true when the channel is this model's, so the
## console stops offering it.
func ingest(channel: String, payload: Dictionary) -> bool:
	if channel != _Const.CH_TICK_PERF:
		return false

	latest_tick = int(payload.get("tick", 0))
	handlers = int(payload.get("handlers", 0))
	failing = int(payload.get("failing", 0))
	_intervals.push(float(payload.get("interval", 0.0)) * MS_PER_SECOND)
	_durations.push(float(payload.get("duration", 0.0)) * MS_PER_SECOND)
	_late.push(1.0 if bool(payload.get("late", false)) else 0.0)
	late_count = _late.set_count()
	_last_tick_msec = clock.call()
	changed.emit()

	return true


func has_ticks() -> bool:
	return _intervals.count > 0


## The gap before each tick, in milliseconds, oldest first.
func tick_intervals_ms() -> PackedFloat32Array:
	return _intervals.values()


## The work of each tick, in milliseconds, oldest first.
func tick_durations_ms() -> PackedFloat32Array:
	return _durations.values()


## One flag for each reading: 1.0 when the server marked the tick late.
func tick_late_flags() -> PackedFloat32Array:
	return _late.values()


func newest_tick_interval_ms() -> float:
	return _intervals.newest()


func mean_tick_interval_ms() -> float:
	return _intervals.mean()


func peak_tick_interval_ms() -> float:
	return _intervals.peak()


func newest_tick_duration_ms() -> float:
	return _durations.newest()


func peak_tick_duration_ms() -> float:
	return _durations.peak()


## Seconds since the newest reading landed, by [member clock]. [constant
## NO_TICK] before the first one.
func seconds_since_tick() -> float:
	if _last_tick_msec < 0:
		return NO_TICK

	var now: int = clock.call()

	return float(now - _last_tick_msec) / MS_PER_SECOND


## Forget the server. The console calls this when the socket closes, so a
## reconnect does not draw the ticks of the session before it.
func reset_server() -> void:
	_intervals.clear()
	_durations.clear()
	_late.clear()
	latest_tick = 0
	handlers = 0
	failing = 0
	late_count = 0
	_last_tick_msec = -1
	changed.emit()
