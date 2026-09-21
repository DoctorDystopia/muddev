extends Node
## Unit tests for StepAnimator — the maths that draws a server step as a walk.
##
##     godot --headless --path godot res://tests/test_step_animator.tscn
##
## Needs nothing running, no scene and no clock: every case hands `advance` the
## frame time it wants to test.
##
## The bugs here are all SILENT. Nothing raises when a figure drifts a tile
## behind the server, when a teleport is drawn as a walk through the wall
## between two rooms, or when a walk runs at a different speed on a machine
## with a different frame rate. Each one simply makes the client tell the
## player something the server did not say, which is the one thing the
## animation is not allowed to do.

## One tile, and how long the server takes to cross one. The pane passes its
## own tile size and the tick from the generated constants; the numbers here
## are those, spelled out, because a test that read them from the same place
## the code does would agree with a wrong value.
const STEP := 1.0
const TICK := 0.6

## A frame at 60fps, and one at 10fps. Two rates, one walk.
const FAST_FRAME := 1.0 / 60.0
const SLOW_FRAME := 1.0 / 10.0

const ORIGIN := Vector3.ZERO
const ONE_NORTH := Vector3(0.0, 0.0, -1.0)
const ONE_EAST := Vector3(1.0, 0.0, 0.0)

## A diagonal step: one tile, and the longest move that is still one step.
const ONE_NORTHEAST := Vector3(1.0, 0.0, -1.0)

## Across the map. Nothing walks this, whatever the server calls it.
const ACROSS_THE_MAP := Vector3(40.0, 0.0, -12.0)

var _failures := 0


func _ready() -> void:
	_a_first_sighting_is_not_a_walk()
	_a_step_takes_exactly_one_tick()
	_a_diagonal_is_still_one_step()
	_the_walk_is_the_same_at_any_frame_rate()
	_the_lag_is_never_more_than_one_tick()
	_a_jump_further_than_a_step_snaps()
	_a_new_target_mid_step_carries_on_from_here()
	_the_true_tile_is_marked_for_exactly_as_long_as_the_walk()
	_switching_the_animation_off_lands_the_figure_at_once()
	_an_animator_that_is_off_never_leaves_its_tile()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: step_animator")
	get_tree().quit(0)


# ─── Cases ───────────────────────────────────────────────────────────────────

## Without this every entity in the room swims in from the world origin on the
## frame it is announced, because the first position it is ever given looks
## like a move from wherever the animator happened to start.
func _a_first_sighting_is_not_a_walk() -> void:
	var animator := _animator()

	animator.aim(ACROSS_THE_MAP)

	_expect(animator.drawn() == ACROSS_THE_MAP,
		"the first position is placed, not walked to")
	_expect(not animator.is_travelling(),
		"and nothing is marked, because nothing is moving")


## The whole contract with the server: `goto` steps one tile per tick, so a
## walk that takes any other time drifts. Longer and the figure falls behind
## forever; shorter and it stands waiting on each tile, which is the jump this
## replaced with extra steps in it.
func _a_step_takes_exactly_one_tick() -> void:
	var animator := _animator()

	animator.place(ORIGIN)
	animator.aim(ONE_NORTH)

	var travelled := _run(animator, TICK * 0.5, FAST_FRAME)

	_expect(travelled.distance_to(ONE_NORTH) > 0.1,
		"half a tick in, the figure is still short of the tile")

	travelled = _run(animator, TICK * 0.5 + FAST_FRAME, FAST_FRAME)

	_expect(travelled == ONE_NORTH, "and one tick in, it has arrived")


## A diagonal is ONE step and measures sqrt(2), which is why the snap threshold
## is above one. Getting this wrong would draw every diagonal as a teleport --
## correct in position and wrong in everything the animation exists for.
func _a_diagonal_is_still_one_step() -> void:
	var animator := _animator()

	animator.place(ORIGIN)
	animator.aim(ONE_NORTHEAST)

	_expect(animator.is_travelling(), "a diagonal step is walked, not snapped")
	_expect(animator.drawn() == ORIGIN,
		"and it has not left the tile it started on yet")


## The same walk on a machine at 10fps and one at 60fps. A figure that arrives
## at different times on two machines is a client whose animation is a function
## of the hardware rather than of the server.
func _the_walk_is_the_same_at_any_frame_rate() -> void:
	var fast := _animator()
	var slow := _animator()

	fast.place(ORIGIN)
	slow.place(ORIGIN)
	fast.aim(ONE_EAST)
	slow.aim(ONE_EAST)

	var half := TICK * 0.5
	var here := _run(fast, half, FAST_FRAME)
	var there := _run(slow, half, SLOW_FRAME)

	_expect(here.distance_to(there) < 0.02,
		"both are in the same place half a tick in (%.3f apart)"
		% here.distance_to(there))


## The rule that keeps the animation honest. Whatever a figure is behind by --
## a frame the game dropped, a window the player dragged, a step that arrived
## while the last one was still running -- one tick of play spends all of it.
func _the_lag_is_never_more_than_one_tick() -> void:
	var animator := _animator()

	animator.place(ORIGIN)
	animator.aim(ONE_EAST)

	# One frame into the walk, the server steps again. The figure is now behind
	# by most of a tile ON TOP of the tile it has yet to cross.
	animator.advance(FAST_FRAME)
	animator.aim(ONE_EAST + ONE_EAST)

	var landed := _run(animator, TICK + FAST_FRAME, FAST_FRAME)

	_expect(landed == ONE_EAST + ONE_EAST,
		"a step taken while behind still lands within the tick")


## A teleport is not a walk. Drawing one as a walk is a figure crossing every
## tile in between, and there is no promise whatever that those tiles are
## walkable -- or that they are on the same island.
func _a_jump_further_than_a_step_snaps() -> void:
	var animator := _animator()

	animator.place(ORIGIN)
	animator.aim(ACROSS_THE_MAP)

	_expect(animator.drawn() == ACROSS_THE_MAP, "a teleport is drawn at once")
	_expect(not animator.is_travelling(),
		"so there is no walk to mark a true tile for")


## What a player walking a path actually is: a step arriving before the last
## one finished. The figure carries on from where it had got to rather than
## restarting from the tile it was aiming at.
func _a_new_target_mid_step_carries_on_from_here() -> void:
	var animator := _animator()

	animator.place(ORIGIN)
	animator.aim(ONE_EAST)

	var midway := _run(animator, TICK * 0.5, FAST_FRAME)

	animator.aim(ONE_EAST + ONE_EAST)

	_expect(animator.drawn() == midway,
		"re-aiming moves nothing on its own")
	_expect(animator.target() == ONE_EAST + ONE_EAST,
		"and the true tile is the new one immediately")


## The information the animation costs, and the moment it is paid back. The
## mark goes on when the figure leaves its square and off when it arrives --
## not a frame later, because `move_toward` converges without ever landing
## exactly and a mark waiting for equality would never go out.
func _the_true_tile_is_marked_for_exactly_as_long_as_the_walk() -> void:
	var animator := _animator()

	animator.place(ORIGIN)

	_expect(not animator.is_travelling(), "a figure at rest marks nothing")

	animator.aim(ONE_NORTH)

	_expect(animator.is_travelling(),
		"the square it is bound for is marked as soon as it is named")

	_run(animator, TICK + FAST_FRAME, FAST_FRAME)

	_expect(not animator.is_travelling(),
		"and the mark goes out when the figure arrives")


## A player who turns the animation off is not asking to watch the last walk
## finish.
func _switching_the_animation_off_lands_the_figure_at_once() -> void:
	var animator := _animator()

	animator.place(ORIGIN)
	animator.aim(ONE_NORTH)
	animator.advance(FAST_FRAME)
	animator.set_animated(false)

	_expect(animator.drawn() == ONE_NORTH,
		"the figure is on its true tile the moment the setting changes")
	_expect(not animator.is_travelling(),
		"and its mark goes with it")


## With the animation off, `aim` has to PLACE rather than leave the drawn
## position for the next frame. EntityPool reads `drawn` as it rebuilds and
## only then starts advancing, so an aim that moved nothing would draw every
## entity one step behind for as long as the setting stayed off.
func _an_animator_that_is_off_never_leaves_its_tile() -> void:
	var animator := _animator()

	animator.set_animated(false)
	animator.place(ORIGIN)
	animator.aim(ONE_EAST)

	_expect(animator.drawn() == ONE_EAST,
		"aiming lands the figure with no frame in between")


# ─── Helpers ─────────────────────────────────────────────────────────────────

func _animator() -> StepAnimator:
	return StepAnimator.new(STEP, TICK)


## Advance for `seconds` in frames of `frame`, and answer where the figure got
## to. The last frame is short rather than dropped, so the total time is the
## time asked for at either frame rate.
func _run(animator: StepAnimator, seconds: float, frame: float) -> Vector3:
	var left := seconds
	var at := animator.drawn()

	while left > 0.0:
		at = animator.advance(minf(frame, left))
		left -= frame

	return at


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
