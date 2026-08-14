extends Node3D
## Orbit rig that follows the player marker.
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

const ORBIT_SPEED := 0.006      # radians per pixel dragged
const ZOOM_STEP := 1.12         # distance multiplier per wheel notch
const DISTANCE_START := 14.0
const DISTANCE_MIN := 3.5
const DISTANCE_MAX := 60.0
const PITCH_START := 0.63
const PITCH_MIN := 0.12
const PITCH_MAX := 1.45
const YAW_START := 0.40
const FOCUS_HEIGHT := 0.30      # aim above the marker's base, not at it
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

	global_position = global_position.lerp(focus, minf(FOLLOW_SPEED * delta, 1.0))


func _handle_button(event: InputEventMouseButton) -> void:
	match event.button_index:
		MOUSE_BUTTON_RIGHT:
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
