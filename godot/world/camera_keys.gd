class_name CameraKeys
extends RefCounted
## The arrow keys that the player holds, and which way they turn the camera.
##
## ## Why the camera has keys
##
## A middle drag turns the camera. Most trackpads have no middle button. The
## arrow keys give a trackpad player the same turn and tilt. The wheel zoom
## needs no key, because a two-finger scroll on a trackpad is a wheel.
##
## ## Why the turn is a rate
##
## A held arrow key turns the camera until the player lets go, as in OSRS.
## [method turn] gives the direction of the held keys, and [OrbitCamera]
## multiplies it by a speed and the frame time. The turn thus has one speed at
## every frame rate.
##
## The keys work while the map has the keyboard, as WASD does. In the input,
## Up and Down walk the command history, and Left and Right move the caret.
## The console owns that rule, not this class.
##
## Pure state with no node and no clock, so `test_camera_keys.tscn` drives it
## with key codes.

## Keycode to its turn. X is the yaw: +1 turns the view to the left. Y is the
## pitch: +1 lifts the camera, so it looks down more steeply.
##
## Left moves the camera to its own left around the avatar, so the view turns
## to the right (Nick, 10/26/2026). The first build had the two rows the other
## way, and Nick found them flipped in play.
const BINDINGS := {
	KEY_LEFT: Vector2(-1.0, 0.0),
	KEY_RIGHT: Vector2(1.0, 0.0),
	KEY_UP: Vector2(0.0, 1.0),
	KEY_DOWN: Vector2(0.0, -1.0),
}

## The keycodes held now.
var _held: Array[int] = []


## Whether this key turns the camera.
static func is_camera_key(keycode: int) -> bool:
	return BINDINGS.has(keycode)


## A key went down. Returns true when it is a camera key.
##
## A key that is already down changes nothing. The OS repeats a held key, but
## the hold is one turn.
func press(keycode: int) -> bool:
	if not is_camera_key(keycode):
		return false

	if not _held.has(keycode):
		_held.append(keycode)

	return true


## A key went up.
func release(keycode: int) -> void:
	_held.erase(keycode)


## Forget every held key. For a loss of focus, where no key-up arrives.
func clear() -> void:
	_held.clear()


## True while a camera key is down.
func is_holding() -> bool:
	return not _held.is_empty()


## The turn of the held keys: each axis -1, 0 or +1.
##
## Two keys that oppose (Left and Right) cancel, and the camera stays still.
## Left and Up together turn and tilt at the same time.
func turn() -> Vector2:
	var total := Vector2.ZERO

	for keycode: int in _held:
		total += BINDINGS[keycode]

	return total.sign()
