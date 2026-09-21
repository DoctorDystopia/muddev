extends Node3D
## Orbit rig that follows the player's avatar.
##
## It followed the MARKER until 09/20/2026, and the difference is the whole
## point of the split: the marker is the square the server has you on and it
## snaps, while the avatar slides towards it. A camera tied to the marker would
## jump a whole tile per tick however smoothly the figure walked under it.
##
## Pitch is stored as ELEVATION ABOVE THE HORIZON rather than as a polar angle,
## because every clamp is naturally expressed that way: floor it just above
## ground level, cap it just under straight down. Straight down is excluded on
## purpose -- at exactly PI/2 the look-at up-vector degenerates and the view
## snaps to an arbitrary yaw.
##
## The arm is a SpringArm3D rather than hand-rolled trigonometry, which is the
## one thing the earlier proof of concept got better than blackout3d.js did: it
## already handles pushing the camera in when something is between it and the
## focus, for free, the day this scene grows anything to collide with.
##
## **Orbit is MIDDLE-drag, not right-drag.** The right button belongs to the
## world pane's Choose Option menu; see [method _handle_button].

const ORBIT_SPEED := 0.006      # radians per pixel MIDDLE-dragged
const ZOOM_STEP := 1.12         # distance multiplier per wheel notch
const DISTANCE_START := 14.0
const DISTANCE_MIN := 0.5
const DISTANCE_MAX := 60.0
const PITCH_START := 0.63
const PITCH_MIN := -0.5
const PITCH_MAX := 1.45
const YAW_START := 0.40
const FOCUS_HEIGHT := 0.30      # aim above the avatar's base, not at it

## How hard the rig is pulled towards the focus, per second.
##
## It is a RATE, not a fraction of the gap per frame, and [method _process]
## turns it into one with an exponential rather than by multiplying by the
## frame time. Those are the same number only at a steady frame rate: the old
## `min(speed * delta, 1)` form clamped to a hard snap below 8 frames per
## second and tightened smoothly above it, so the camera lagged differently on
## two machines watching the same walk.
const FOLLOW_SPEED := 8.0

@export var target: Node3D

@onready var _arm: SpringArm3D = $SpringArm3D

var _yaw := YAW_START
var _pitch := PITCH_START
var _distance := DISTANCE_START
var _dragging := false


func _ready() -> void:
	_apply()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		_handle_button(event)
		return

	if event is InputEventMouseMotion and _dragging:
		_yaw -= event.relative.x * ORBIT_SPEED
		_pitch = clampf(_pitch + event.relative.y * ORBIT_SPEED, PITCH_MIN, PITCH_MAX)
		_apply()


func _process(delta: float) -> void:
	if target == null:
		return

	var focus := target.global_position + Vector3(0.0, FOCUS_HEIGHT, 0.0)

	# 1 - e^(-k dt) is the fraction of the remaining gap an exponential decay
	# closes in dt, and it is the only form that gives the same path whatever
	# the frame rate. It also cannot overshoot, however long a frame took.
	var weight := 1.0 - exp(-FOLLOW_SPEED * delta)

	global_position = global_position.lerp(focus, weight)


## MIDDLE drag orbits, and that is a deliberate reassignment.
##
## It was the RIGHT button until 09/10/2026, when the world pane grew a
## right-click Choose Option menu. Sharing one button between "turn the camera"
## and "ask what this is" cannot be made to feel right: opening on the press
## pops a menu at the start of every turn, and opening on the release pops one
## at the end of every turn unless the click is distinguished from the drag by
## a pixel threshold -- which then has to be tuned, and is wrong for somebody.
## The menu is worth more on the button players expect it on, so the camera
## moved.
func _handle_button(event: InputEventMouseButton) -> void:
	match event.button_index:
		MOUSE_BUTTON_MIDDLE:
			_dragging = event.pressed
		MOUSE_BUTTON_WHEEL_UP:
			_zoom(1.0 / ZOOM_STEP)
		MOUSE_BUTTON_WHEEL_DOWN:
			_zoom(ZOOM_STEP)


func _zoom(factor: float) -> void:
	_distance = clampf(_distance * factor, DISTANCE_MIN, DISTANCE_MAX)
	_apply()


func _apply() -> void:
	rotation.y = _yaw
	_arm.rotation.x = -_pitch
	_arm.spring_length = _distance
