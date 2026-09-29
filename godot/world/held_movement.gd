class_name HeldMovement
extends RefCounted
## The movement keys that the player holds, and when to send their direction.
##
## ## Why the client sends the key again and again
##
## The server moves a walker on the tick (`systems/gameplay/movement/walk.py`).
## A direction command is ONE tick of movement: one tile, or two tiles when
## the player runs. A held key must thus reach the server at least one time
## each tick, or the walker stops for a tick. This sends the direction when a
## key goes down. It sends it again every [member _interval] seconds while
## the key stays down. The console gives half a tick, so each tick gets
## a send even with some network jitter.
##
## The server makes a new walk from the current tile on each command. The
## sends thus never stack. When the player lets go, the sends stop, and the
## walker moves at most one tick more. The client sends no "stop". A lost
## key-up event can thus never make a walk that goes on for ever.
##
## ## Why the keys are a list
##
## Traditional WASD: W and D held together walk northeast. The list keeps the
## order of the presses. When two keys cancel, [method MovementKeys.combined]
## thus lets the newest key win.
##
## Pure state with no node and no clock, so `test_held_movement.tscn` drives
## it with numbers.

## The keycodes held now, oldest first.
var _held: Array[int] = []

## Seconds since the last send.
var _since_send := 0.0

## Seconds between two sends of a held direction.
var _interval: float


func _init(interval: float) -> void:
	_interval = maxf(interval, 0.01)


## A key went down. Returns the direction to send now, or "".
##
## A key that is already down returns "". The OS repeats a held key, but the
## timer in [method advance] owns the repeats.
func press(keycode: int) -> String:
	if not MovementKeys.is_movement_key(keycode) or _held.has(keycode):
		return ""

	_held.append(keycode)
	_since_send = 0.0

	return direction()


## A key went up.
func release(keycode: int) -> void:
	_held.erase(keycode)


## Forget every held key. For a loss of focus, where no key-up arrives.
func clear() -> void:
	_held.clear()


## True while a movement key is down.
func is_holding() -> bool:
	return not _held.is_empty()


## The direction of the held keys, or "".
func direction() -> String:
	return MovementKeys.combined(_held)


## Time passed. Returns the direction to send now, or "".
func advance(delta: float) -> String:
	if _held.is_empty():
		return ""

	_since_send += delta

	if _since_send < _interval:
		return ""

	_since_send = 0.0

	return direction()
