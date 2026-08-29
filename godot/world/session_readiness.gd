class_name SessionReadiness
extends Node
## Whether the player can actually play yet, and what is still missing.
##
## ## The gap this closes
##
## Logging in is not arriving. [LoginView] dismisses itself the moment
## `char_vitals` lands, because vitals are only sent for a PUPPETED character
## and that is the honest signal that a body exists. But a body is not a world:
## `blackout_map` is still arriving in chunks, `room_info` has not necessarily
## said where you are standing, and not one `.glb` has been fetched. For a
## second or three the player is looking at a pane that is empty, then wrong,
## then right — and every click they land in that window is a real command sent
## about a world they cannot see yet.
##
## Godot's own boot splash covers the ENGINE starting. It is gone long before
## any of this begins, which is why a second screen is not redundant.
##
## ## Four facts, in the order they arrive
##
##     a body      char_vitals landed          -> CharState.has_vitals
##     a place     room_info named a map       -> WorldState.current_z
##     a map       every chunk of it arrived   -> Level.is_complete()
##     the art     nothing left in flight      -> MeshResolver.in_flight_count()
##
## They genuinely do complete in that order, but nothing here assumes it: each
## is tested independently and the phase is whichever is missing FIRST, so a
## server that reorders them reports the truth rather than a stale label.
##
## ## The decision is pure; the clock is not
##
## [method phase_for] is static and takes every input as an argument. It is the
## whole rule, and it can be tested without a socket, a timer or a frame — the
## same split [ReconnectPolicy] makes, for the same reason. This node is only
## the thing that reads the live state and holds a stopwatch.
##
## ## Why it POLLS rather than binding a signal
##
## Three of the four facts announce themselves ([signal CharState.changed],
## [signal WorldState.map_ready], [signal MeshResolver.refreshed]) and the
## fourth does not: a model going INTO flight emits nothing, because
## [method ModelLoader.request] is called from a draw and adding a signal there
## would make every entity rebuild chatter. Binding the three that do exist
## would therefore give a readiness model that can be told art finished but
## never that more of it started — which is precisely the case that must not be
## missed, since it is what a premature "ready" looks like.
##
## So it reads all four on a tick, and the tick runs ONLY while the veil is up.
## It costs nothing after the first few seconds of a session and it cannot
## desynchronise from a signal it forgot to connect.

## Emitted when the phase changes. Not on every tick — a view that redrew sixty
## times a second to show the same word is a view that flickers.
signal changed(phase: Phase)

## What is missing, named by the first fact that is.
##
## OFFSTAGE is not a loading state. It is "no body yet", which is the login
## form's screen and not this one's; see [method is_veiled].
enum Phase {
	OFFSTAGE,
	PLACING,
	MAPPING,
	ART,
	READY,
}

## How long the art has to stay quiet before it counts as finished.
##
## NOT paranoia. Models are fetched lazily, as whatever needs them is drawn, so
## the in-flight set legitimately empties between batches: the map completes,
## the terrain layer asks for its tiles, and a moment later the entity layer
## asks for the NPCs standing on them. Lifting on the first zero would raise the
## veil on a room that is still missing everyone in it.
const SETTLE_SECONDS := 0.4

## The longest the veil may ever stand, measured from the body arriving.
##
## A CEILING, not a timeout — nothing is cancelled and nothing is reported as
## failed. It exists because every other exit from this screen depends on
## something arriving, and a player who is never getting their art must still
## be given their game. [constant ModelLoader.TIMEOUT_SECONDS] is 20, so a
## single stuck fetch resolves itself well inside this; the ceiling is for the
## pathological case of several of them in series.
const CEILING_SECONDS := 30.0

## When to offer the player the way out.
##
## Late enough that a normal login never sees it — the whole sequence is under a
## second on a warm cache — and early enough that a bad one is not a stare.
const SKIP_OFFER_SECONDS := 6.0

## How often the four facts are re-read while the veil is up.
const POLL_SECONDS := 0.1

var _char: CharState
var _world: WorldState
var _meshes: MeshResolver

var _phase := Phase.OFFSTAGE

## Seconds since the art last had anything in flight. Measures QUIET, not
## elapsed time: any fetch in the air puts it back to zero.
var _art_idle := 0.0

## Seconds since a body arrived. The ceiling and the skip offer are both
## measured from there rather than from the socket opening, because the time
## spent on the login form is the player's own and not a wait.
var _waited := 0.0

## When the body arrived and when the art was last busy, as monotonic
## milliseconds. `-1` means no body.
##
## MEASURED, not counted. The obvious build adds POLL_SECONDS per tick, and it
## is wrong in precisely the situation this class exists for: a Timer fires on
## the main loop, so a client whose frames are hitching -- which is what heavy
## asset loading looks like -- ticks fewer than ten times a second and a counted
## clock runs slow. The ceiling would then be a promise about ticks rather than
## about seconds, and the worse the stall the longer the player waits for the
## release that is supposed to rescue them from it.
var _body_since_msec := -1
var _art_busy_msec := 0

## The stopwatch. A Timer rather than `_process` so the tick rate is stated
## once, here, instead of being whatever the frame rate happens to be.
var _tick: Timer

## Set by the player, and never cleared for the rest of the session: having
## chosen to go in early once, they are not asked again on the next room.
var _skipped := false


## The whole rule, as a function of nothing but its arguments.
##
## Every branch is a fact that must already be true before the next one is even
## asked, which is what makes the order here the report rather than an
## assumption about arrival order.
##
## `waited` and the ceiling are checked BEFORE the missing-fact branches so that
## an expired ceiling wins over whatever is still absent. Checked after, a
## session that never receives a map would report MAPPING forever and the
## ceiling would be unreachable.
static func phase_for(has_body: bool, has_room: bool, map_complete: bool,
		in_flight: int, art_idle: float, waited: float,
		skipped: bool) -> Phase:
	if not has_body:
		return Phase.OFFSTAGE

	if skipped or waited >= CEILING_SECONDS:
		return Phase.READY

	if not has_room:
		return Phase.PLACING

	if not map_complete:
		return Phase.MAPPING

	if in_flight > 0 or art_idle < SETTLE_SECONDS:
		return Phase.ART

	return Phase.READY


## Whether a phase is one the veil should be drawn for.
##
## OFFSTAGE and READY are both "not loading", and they are deliberately not the
## same thing anywhere else: OFFSTAGE is the login form's screen. A veil that
## covered it would hide the one control the player needs.
static func is_loading(phase: Phase) -> bool:
	return phase == Phase.PLACING or phase == Phase.MAPPING or phase == Phase.ART


## Follow the models that answer the four questions.
func bind(char_state: CharState, world: WorldState,
		meshes: MeshResolver) -> void:
	_char = char_state
	_world = world
	_meshes = meshes


func _ready() -> void:
	_tick = Timer.new()
	_tick.wait_time = POLL_SECONDS
	_tick.timeout.connect(_on_tick)
	add_child(_tick)
	_tick.start()


## The player's own decision to go in without waiting.
##
## Deliberately one-way. A session that has been entered is entered; re-veiling
## on the next map load would be a screen appearing over a game already being
## played.
func skip() -> void:
	if _skipped:
		return

	_skipped = true
	_on_tick()


func phase() -> Phase:
	return _phase


func is_veiled() -> bool:
	return is_loading(_phase)


## Whether the way out has been on offer long enough to show it.
func may_skip() -> bool:
	return _waited >= SKIP_OFFER_SECONDS


## How many models are still being fetched. Zero is not by itself readiness;
## see [constant SETTLE_SECONDS].
func in_flight() -> int:
	if _meshes == null:
		return 0

	return _meshes.in_flight_count()


## Forget the session. Called when the socket drops, for the same reason
## [method CharState.reset] is: the next socket is a new Evennia Session at the
## connection screen, so the next login has to be waited for again.
##
## `_skipped` is cleared here and only here. It is one-way WITHIN a session;
## a new session is a new decision.
func reset() -> void:
	_art_idle = 0.0
	_waited = 0.0
	_body_since_msec = -1
	_skipped = false
	_publish(Phase.OFFSTAGE)


# ─── Private ─────────────────────────────────────────────────────────────────

## Re-read the four facts and republish if the answer moved.
func _on_tick() -> void:
	if _char == null or _world == null:
		return

	var has_body: bool = _char.has_vitals
	var now := Time.get_ticks_msec()

	# The stopwatches only run once there is a body to wait for. Before that the
	# player is at the login form and the time is theirs.
	if not has_body:
		_body_since_msec = -1
		_waited = 0.0
		_art_idle = 0.0
	else:
		# Both clocks start together on the first tick that sees a body, so the
		# settle window cannot be satisfied by quiet that elapsed before there
		# was anything to be quiet about.
		if _body_since_msec < 0:
			_body_since_msec = now
			_art_busy_msec = now

		if in_flight() > 0:
			_art_busy_msec = now

		_waited = float(now - _body_since_msec) / 1000.0
		_art_idle = float(now - _art_busy_msec) / 1000.0

	_publish(phase_for(has_body, _has_room(), _map_complete(), in_flight(),
		_art_idle, _waited, _skipped))


## Whether `room_info` has named the map the observer is standing on.
func _has_room() -> bool:
	return not _world.current_z.is_empty()


## Whether every chunk of the map the observer is standing on has landed.
##
## False for a map with no [WorldState.Level] at all, which is the state between
## `room_info` naming a z and the first chunk of it arriving — the level is
## keyed by the name the room named, so a missing entry means nothing of that
## map has been received rather than that it is empty.
func _map_complete() -> bool:
	var z := _world.current_z

	if not _world.levels.has(z):
		return false

	var level: WorldState.Level = _world.levels[z]

	return level.is_complete()


## Store the phase and announce a change, then stop ticking once there is
## nothing left to watch for.
func _publish(next: Phase) -> void:
	if next == _phase:
		return

	_phase = next
	changed.emit(_phase)

	# The tick exists to raise the veil. Once it is up or down for good there is
	# nothing to poll for, and a client that kept reading four models ten times
	# a second for the rest of the session would be paying for a screen nobody
	# is looking at. `reset()` restarts it by publishing OFFSTAGE.
	if _tick == null:
		return

	if _phase == Phase.READY:
		_tick.stop()
	elif _tick.is_stopped():
		_tick.start()
