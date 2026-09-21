class_name StepAnimator
extends RefCounted
## Where ONE figure is DRAWN, given where the server says it IS.
##
## The server moves a character in whole tiles, one tile per tick. Drawing it
## there and only there is a jump per tick. This slides it instead, and the
## whole of the design is in two rules that keep the slide honest:
##
## **The drawn position is never more than one tick behind the true one.** The
## speed is not a constant. It is whatever covers the remaining distance in one
## tick, floored at walking pace — so a figure that fell behind catches up
## inside the next tick rather than accumulating a lag the player has to
## account for. A client that can drift arbitrarily far from the server is a
## client that lies, and this is the arithmetic that stops it.
##
## **A jump longer than a step is not a walk.** A teleport, a resync, an island
## arriving late and moving the ground under everything: none of those is
## movement, and none has a path to draw. They SNAP. This is the same rule
## [method WorldView.yaw_towards] applies to facing, for the same reason, and
## the two thresholds are deliberately the same shape: one step, diagonals
## included.
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

## How far a figure may be moved and still have that count as a walk, in steps.
##
## Above one because a diagonal step is one step and measures sqrt(2). Below
## two so that no jump ACROSS a tile is ever drawn as a walk through the tile
## between them — which is a figure walking through a wall on every teleport
## that happens to land two tiles away.
const SNAP_STEPS := 1.5

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

## False until the first position arrives. A first sighting is not a walk from
## the world origin, so it places rather than animates — without this every
## entity in the room would swim in from the middle of the first island on the
## frame it was announced.
var _placed := false

## One tile, in world units, and how long the server takes to cross one.
##
## BOTH ARE GIVEN, neither is assumed. The tile size belongs to the pane that
## draws tiles, and the tick belongs to the server — it arrives in the
## generated constants, because a walk animation timed to anything but the
## server's own step either arrives early and waits or falls behind forever.
var _step: float
var _seconds: float


func _init(step: float, seconds: float) -> void:
	_step = maxf(step, ARRIVED)
	_seconds = maxf(seconds, ARRIVED)


## Put the figure somewhere with no animation at all.
##
## For a first sighting and for anything the caller already knows is not a
## walk. [method aim] calls it for both cases it recognises itself.
func place(position: Vector3) -> void:
	_drawn = position
	_target = position
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

	if _drawn.distance_to(position) > _step * SNAP_STEPS:
		place(position)
		return

	_target = position


## Move the figure for one frame and answer where to draw it.
##
## The speed is `max(one step, the distance left) / one tick`. The floor is
## walking pace, so a normal step takes exactly as long as the server's own;
## the other term is the catch-up, so any lag is spent inside one tick however
## it was acquired. Both are divided by the tick rather than by a frame, which
## is what makes this independent of the frame rate.
func advance(delta: float) -> Vector3:
	if not _animated:
		_drawn = _target
		return _drawn

	var remaining := _drawn.distance_to(_target)

	if remaining <= ARRIVED:
		_drawn = _target
		return _drawn

	var speed := maxf(_step, remaining) / _seconds

	_drawn = _drawn.move_toward(_target, speed * delta)

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
