extends Node
## Unit tests for CameraKeys and OrbitCamera.turn.
##
##     godot --headless --path godot res://tests/test_camera_keys.tscn

## A frame time for the turn cases, in seconds.
const DELTA := 0.25

var _failures := 0


func _ready() -> void:
	_each_arrow_turns_its_own_way()
	_a_repeat_of_the_os_changes_nothing()
	_a_released_key_stops_the_turn()
	_two_keys_that_oppose_cancel()
	_a_turn_and_a_tilt_go_together()
	_a_key_that_is_not_an_arrow_is_ignored()
	_clear_forgets_every_key()
	_no_camera_key_is_a_movement_key()
	_a_held_key_turns_at_the_rate_of_the_rig()
	_the_tilt_keeps_the_clamp_of_the_drag()
	_left_moves_the_camera_to_its_left()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: camera_keys")
	get_tree().quit(0)


func _each_arrow_turns_its_own_way() -> void:
	for keycode: int in CameraKeys.BINDINGS:
		var keys := CameraKeys.new()

		_expect(keys.press(keycode), "%s is a camera key" % OS.get_keycode_string(keycode))
		_expect(keys.turn() == CameraKeys.BINDINGS[keycode],
			"%s alone gives its own turn" % OS.get_keycode_string(keycode))


func _a_repeat_of_the_os_changes_nothing() -> void:
	var keys := CameraKeys.new()
	keys.press(KEY_LEFT)
	keys.press(KEY_LEFT)

	_expect(keys.turn() == CameraKeys.BINDINGS[KEY_LEFT], "a repeat does not turn faster")

	keys.release(KEY_LEFT)
	_expect(not keys.is_holding(), "and one release lets go")


func _a_released_key_stops_the_turn() -> void:
	var keys := CameraKeys.new()
	keys.press(KEY_RIGHT)
	keys.release(KEY_RIGHT)

	_expect(not keys.is_holding(), "no key is held")
	_expect(keys.turn() == Vector2.ZERO, "no turn after the release")


func _two_keys_that_oppose_cancel() -> void:
	var keys := CameraKeys.new()
	keys.press(KEY_LEFT)
	keys.press(KEY_RIGHT)

	_expect(keys.turn() == Vector2.ZERO, "Left and Right cancel")


func _a_turn_and_a_tilt_go_together() -> void:
	var keys := CameraKeys.new()
	keys.press(KEY_LEFT)
	keys.press(KEY_UP)

	_expect(keys.turn() == CameraKeys.BINDINGS[KEY_LEFT] + CameraKeys.BINDINGS[KEY_UP],
		"Left and Up turn and tilt at the same time")


func _a_key_that_is_not_an_arrow_is_ignored() -> void:
	var keys := CameraKeys.new()

	_expect(not keys.press(KEY_W), "W is not a camera key")
	_expect(not keys.is_holding(), "and nothing is held")


func _clear_forgets_every_key() -> void:
	var keys := CameraKeys.new()
	keys.press(KEY_LEFT)
	keys.press(KEY_UP)
	keys.clear()

	_expect(keys.turn() == Vector2.ZERO, "no turn after a clear")


## The console reads the camera keys before the movement keys. A key in both
## tables would turn the camera and never walk.
func _no_camera_key_is_a_movement_key() -> void:
	for keycode: int in CameraKeys.BINDINGS:
		_expect(not MovementKeys.is_movement_key(keycode),
			"%s does not walk" % OS.get_keycode_string(keycode))


func _a_held_key_turns_at_the_rate_of_the_rig() -> void:
	var rig := _rig()
	var yaw := rig.rotation.y

	var axis: Vector2 = CameraKeys.BINDINGS[KEY_LEFT]

	rig.turn(axis, DELTA)
	_expect(is_equal_approx(rig.rotation.y, yaw + axis.x * OrbitCamera.KEY_YAW_SPEED * DELTA),
		"a held key turns by the speed times the frame time")

	var after := rig.rotation.y

	rig.turn(Vector2.ZERO, DELTA)
	_expect(is_equal_approx(rig.rotation.y, after), "no held key, no turn")

	rig.queue_free()


func _the_tilt_keeps_the_clamp_of_the_drag() -> void:
	var rig := _rig()
	var arm: SpringArm3D = rig.get_node("SpringArm3D")
	var long_hold := (OrbitCamera.PITCH_MAX - OrbitCamera.PITCH_MIN) / OrbitCamera.KEY_PITCH_SPEED * 2.0

	rig.turn(CameraKeys.BINDINGS[KEY_UP], long_hold)
	_expect(is_equal_approx(-arm.rotation.x, OrbitCamera.PITCH_MAX), "Up stops at the top of the tilt")

	rig.turn(CameraKeys.BINDINGS[KEY_DOWN], long_hold)
	_expect(is_equal_approx(-arm.rotation.x, OrbitCamera.PITCH_MIN), "Down stops at the bottom of the tilt")

	rig.queue_free()


## Left moves the camera to its own left around the avatar, so the view turns
## to the right (Nick, 10/26/2026). The view looks along -Z of the arm. A turn
## to the right is clockwise from above, so the cross product points down.
func _left_moves_the_camera_to_its_left() -> void:
	var rig := _rig()
	var before := _view_of(rig)

	rig.turn(CameraKeys.BINDINGS[KEY_LEFT], DELTA)
	_expect(before.cross(_view_of(rig)).y < 0.0, "Left turns the view to the right")

	rig.queue_free()


## A rig in the tree, with the arm that its script reads.
func _rig() -> OrbitCamera:
	var rig := OrbitCamera.new()
	var arm := SpringArm3D.new()
	arm.name = "SpringArm3D"
	rig.add_child(arm)
	add_child(rig)
	return rig


func _view_of(rig: OrbitCamera) -> Vector3:
	var arm: SpringArm3D = rig.get_node("SpringArm3D")
	return -arm.global_basis.z


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
