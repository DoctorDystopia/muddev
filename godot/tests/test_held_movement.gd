extends Node
## Unit tests for HeldMovement and MovementKeys.combined.
##
##     godot --headless --path godot res://tests/test_held_movement.tscn

const INTERVAL := 0.3

var _failures := 0


func _ready() -> void:
	_a_press_sends_at_once()
	_a_repeat_of_the_os_sends_nothing()
	_a_held_key_sends_again_each_interval()
	_a_released_key_stops_the_sends()
	_two_keys_make_a_diagonal()
	_two_keys_that_cancel_give_the_newest()
	_a_key_that_is_not_movement_is_ignored()
	_clear_forgets_every_key()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: held_movement")
	get_tree().quit(0)


func _a_press_sends_at_once() -> void:
	var held := HeldMovement.new(INTERVAL)

	_expect(held.press(KEY_W) == "north", "W sends north at once")


func _a_repeat_of_the_os_sends_nothing() -> void:
	var held := HeldMovement.new(INTERVAL)
	held.press(KEY_W)

	_expect(held.press(KEY_W) == "", "a second press of a held key sends nothing")


func _a_held_key_sends_again_each_interval() -> void:
	var held := HeldMovement.new(INTERVAL)
	held.press(KEY_A)

	_expect(held.advance(INTERVAL * 0.5) == "", "no send before the interval")
	_expect(held.advance(INTERVAL * 0.6) == "west", "a send after the interval")
	_expect(held.advance(INTERVAL * 0.5) == "", "the interval starts again")


func _a_released_key_stops_the_sends() -> void:
	var held := HeldMovement.new(INTERVAL)
	held.press(KEY_S)
	held.release(KEY_S)

	_expect(not held.is_holding(), "no key is held")
	_expect(held.advance(INTERVAL * 2.0) == "", "no send after the release")


func _two_keys_make_a_diagonal() -> void:
	var held := HeldMovement.new(INTERVAL)
	held.press(KEY_W)

	_expect(held.press(KEY_D) == "northeast", "W and D walk northeast")

	held.release(KEY_W)
	_expect(held.direction() == "east", "D alone walks east again")


func _two_keys_that_cancel_give_the_newest() -> void:
	var held := HeldMovement.new(INTERVAL)
	held.press(KEY_W)

	_expect(held.press(KEY_S) == "south", "S after W wins the tie")


func _a_key_that_is_not_movement_is_ignored() -> void:
	var held := HeldMovement.new(INTERVAL)

	_expect(held.press(KEY_F) == "", "F is not a movement key")
	_expect(not held.is_holding(), "and nothing is held")


func _clear_forgets_every_key() -> void:
	var held := HeldMovement.new(INTERVAL)
	held.press(KEY_W)
	held.press(KEY_D)
	held.clear()

	_expect(held.direction() == "", "no direction after a clear")


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
