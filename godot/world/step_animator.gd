class_name StepAnimator
extends RefCounted
## Where ONE figure is DRAWN, given where the server says it IS.
##
## The server moves a character in whole tiles, one tile per tick. Drawing it
## there and only there is a jump per tick. This slides it instead, and the
## whole of the design is in three rules that keep the slide honest:
##
## **The figure TRAILS the server, and the trail is what makes it smooth.** A
## tile takes [constant WALK_TICKS] ticks to cross, not one. That is the whole
## difference between this and a figure that jitters, and the arithmetic is
## worth stating because the naive version looks right on paper.
##
## Cross a tile in exactly one tick and the figure ARRIVES before the next step
## is announced — every time, because a message cannot arrive earlier than the
## event that caused it. It then stands still until that message lands. The
## walk becomes move, stop, move, stop, at whatever the network and the tick
## grid add to each step. A player reads that as snapping.
##
## Crossing in a little MORE than a tick leaves the figure still moving when
## the next step lands, so the motion never stops. The cost is a trail behind
## the true position, and that trail IS the buffer the irregular arrivals are
## absorbed into. It is what every networked client pays for smooth motion.
##
## **Every crossing takes the same TIME, whatever distance it covers.** That is
## the one rule the trail is bounded by. A step the server coalesced, a frame
## the game dropped, a window the player dragged: each leaves the figure
## further behind, and each is spent inside the one crossing that follows,
## because the speed is set from the distance at the moment the step lands.
##
## In a continuous walk that settles at a trail of about a fifth of a tile just
## before each step, and a little over one tile just after it. It never grows,
## and it never reaches zero — which is the whole point.
##
## **A jump longer than [constant SNAP_STEPS] is not a walk.** A teleport, a
## resync, an island arriving late and moving the ground under everything: none
## of those is movement, and none has a path to draw. They SNAP.
##
## Nothing here is told WHAT it is moving. The observer's own avatar and every
## NPC in [EntityPool] each own one of these, so both animate by one set of
## rules and neither can be smoother than the other.
##
## ## This costs information, and the caller pays it back
##
## While a figure is between tiles it is NOT standing where the server says it
## is, and everything a player does is resolved against the server's tile. So
## [method is_travelling] exists, and the panes that draw a figure use it to
## mark that tile for as long as the figure is away from it — see the true tile
## marks in [WorldView]. The animation is a look; the tile is a fact; the fact
## stays on screen.
##
## Pure maths on a RefCounted, so `test_step_animator.tscn` drives it with no
## scene, no camera and no clock.

## How far the SERVER may move a figure and still have that count as a walk,
## in steps.
##
## It was 1.5 until 09/21/2026, and that teleported the player several times a
## minute. `room_info` is in `COALESCABLE_CHANNELS`, so two steps that land in
## one tick reach the client as ONE message naming a tile two squares away.
## That is a real walk the player took, announced late, and snapping it drew
## exactly the jump the animation exists to remove. Manual movement makes it
## common rather than rare: `BlackoutGotoCmd.auto_step_delay` paces the
## auto-walk, and nothing paces a held key.
##
## Three, so a coalesced run of two steps — 2.83 across on the diagonal — is
## walked, and a longer one is not. The honest cost is that a teleport of three
## tiles or fewer is drawn as a slide of under a second, through whatever
## stands between the two tiles. A map-crossing jump, which is what a teleport
## usually is, still snaps.
const SNAP_STEPS := 3.0

## How long one tile takes to cross, in server ticks.
##
## ABOVE ONE ON PURPOSE. See the class docstring: at exactly one tick the
## figure arrives before the next step can possibly be announced, and it then
## stands still until that step lands. This is the interpolation buffer, and
## its size is both how much irregular arrival the walk absorbs and how far the
## figure trails the truth.
##
## 1.2 absorbs about 120 ms of jitter at a 0.6 s tick. A step delayed by more
## than that is absorbed by the catch-up term instead, which reads as a brief
## quickening rather than as a stop.
const WALK_TICKS := 1.2

## How near the target counts as arrived, in world units.
##
## Exists so the slide ENDS. `move_toward` converges but a float never lands
## exactly, and a figure that is forever 1e-9 from its tile is a true tile mark
## that never goes out.
const ARRIVED := 0.001

## Whether to animate at all. False draws every figure on its true tile, which
## is what the client did before 09/20/2026 and what the player's Options
## checkbox turns it back into.
##
## Written through [method set_animated] rather than assigned, because turning
## it off has to take effect on the same frame: an animation the player just
## switched off must not finish its current step first.
var _animated := true

## Where the figure is drawn, and where the server says it is. Equal whenever
## nothing is moving, which is nearly always.
var _drawn := Vector3.ZERO
var _target := Vector3.ZERO

## How fast the current crossing runs, in world units per second.
##
## SET WHEN A STEP LANDS, and held until the next one. It is not recomputed per
## frame from the distance that is left, and that is the difference between a
## crossing that ends and one that does not: a speed proportional to the
## remaining distance is an exponential, which halves the gap forever and never
## closes it. Setting it once makes every crossing take [member _seconds], and
## that is what bounds the trail.
var _speed := 0.0

## False until the first position arrives. A first sighting is not a walk from
## the world origin, so it places rather than animates — without this every
## entity in the room would swim in from the middle of the first island on the
## frame it was announced.
var _placed := false

## One tile in world units, and how long this draws one tile as taking.
##
## BOTH COME FROM ELSEWHERE, neither is assumed. The tile size belongs to the
## pane that draws tiles. The tick belongs to the server and arrives in the
## generated constants, because a walk paced by anything but the server's own
## step drifts from it with no bound.
##
## `_seconds` is that tick multiplied by [constant WALK_TICKS], and the
## multiplication happens HERE rather than at each call site. Both callers pass
## the same tick, and a buffer applied by one of them and not the other would
## be an NPC and a player walking at two different speeds.
var _step: float
var _seconds: float


func _init(step: float, tick: float) -> void:
	_step = maxf(step, ARRIVED)
	_seconds = maxf(tick, ARRIVED) * WALK_TICKS


## Put the figure somewhere with no animation at all.
##
## For a first sighting and for anything the caller already knows is not a
## walk. [method aim] calls it for both cases it recognises itself.
func place(position: Vector3) -> void:
	_drawn = position
	_target = position
	_speed = 0.0
	_placed = true


## The server says the figure is here now.
##
## Snaps rather than slides when the move is longer than [constant SNAP_STEPS],
## and on the first call of all. Everything else is a step, and a step that
## arrives mid-slide simply re-aims: the figure carries on from wherever it had
## got to, which is what a player walking a path is.
##
## With the animation off this places, rather than aiming and leaving the drawn
## position for the next frame to fix. A caller is entitled to read
## [method drawn] straight after this one, and [EntityPool] does: it places
## every node as it rebuilds and only then starts advancing them.
func aim(position: Vector3) -> void:
	if not _animated or not _placed:
		place(position)
		return

	# Measured from the last TARGET, never from where the figure is drawn. The
	# figure trails during a walk, so a drawn-to-new measurement reads an
	# ordinary step as more than two tiles and snaps the whole walk. What this
	# has to judge is the move the SERVER made.
	var moved := _target.distance_to(position)

	if moved > _step * SNAP_STEPS:
		place(position)
		return

	# A target that did not move does not restart the crossing. Most aims are
	# this: the pane re-aims on every relayout, and EntityPool re-aims every
	# entity in the room on every step the OBSERVER takes. Re-timing a crossing
	# that is already running would stretch it, and a figure that is nearly
	# home would slow down because somebody else moved.
	if moved <= ARRIVED:
		return

	_target = position
	_speed = _drawn.distance_to(_target) / _seconds


## Move the figure for one frame and answer where to draw it.
##
## Constant speed, at whatever [method aim] set. Nothing here reads the
## distance to decide how fast to go, and nothing here eases in or out: a
## crossing is a straight line at one speed, and it ends after [member
## _seconds]. Time drives it rather than the frame, which is what makes the
## walk the same on a machine at 10 frames a second and one at 240.
##
## The speed is not capped. A cap could not bound the trail, which is the
## property that keeps the client honest, and the case it would guard against
## -- a figure crossing three tiles in one crossing -- is a player who really
## did move that fast.
func advance(delta: float) -> Vector3:
	if not _animated:
		_drawn = _target
		return _drawn

	if _drawn.distance_to(_target) <= ARRIVED:
		_drawn = _target
		return _drawn

	_drawn = _drawn.move_toward(_target, _speed * delta)

	return _drawn


## Where the figure is drawn right now, with no time passing.
func drawn() -> Vector3:
	return _drawn


## Where the server says the figure is. The true tile, in world units.
func target() -> Vector3:
	return _target


## Whether the figure is away from its true tile, and the mark for that tile
## therefore has to be on screen.
##
## False while the animation is off, because the figure is then standing on the
## tile itself and a mark under it would say nothing.
func is_travelling() -> bool:
	if not _animated:
		return false

	return _drawn.distance_to(_target) > ARRIVED


## Turn the animation on or off.
##
## Turning it OFF lands the figure on its true tile immediately. A player who
## switches the animation off mid-walk asked to stop seeing one, not to watch
## the last one finish.
func set_animated(value: bool) -> void:
	_animated = value

	if not value:
		_drawn = _target


func is_animated() -> bool:
	return _animated
