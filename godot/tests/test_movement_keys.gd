extends Node
## Unit tests for MovementKeys.
##
##     godot --headless --path godot res://tests/test_movement_keys.tscn

var _failures := 0

## The two layouts the webclient binds, kept here as the thing under test
## rather than imported from the table — a test that derived both halves from
## BINDINGS could not notice a key missing from one of them.
const WASD := {
	KEY_W: "north", KEY_A: "west", KEY_S: "south", KEY_D: "east",
	KEY_Q: "northwest", KEY_E: "northeast",
	KEY_Z: "southwest", KEY_C: "southeast",
}

const VI := {
	KEY_K: "north", KEY_H: "west", KEY_J: "south", KEY_L: "east",
	KEY_Y: "northwest", KEY_U: "northeast",
	KEY_B: "southwest", KEY_N: "southeast",
}


func _ready() -> void:
	_both_layouts_are_bound()
	_the_two_layouts_reach_the_same_places()
	_every_binding_names_a_compass_direction()
	_an_unbound_key_means_nothing()
	_the_direction_list_is_derived_from_the_table()
	_a_camera_to_the_north_changes_nothing()
	_a_camera_to_the_east_turns_each_key_a_quarter()
	_a_camera_between_two_directions_snaps_to_one()
	_no_camera_heading_changes_nothing()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: movement_keys")
	get_tree().quit(0)


## Spelled out per key, because the bug this guards is one corner being wrong.
func _both_layouts_are_bound() -> void:
	for layout: Dictionary in [WASD, VI]:
		for keycode: int in layout:
			_expect(MovementKeys.command_for(keycode) == layout[keycode],
				"%s means %s" % [OS.get_keycode_string(keycode), layout[keycode]])


## A player who knows either layout should find the other already working, so
## neither may reach somewhere the other cannot.
func _the_two_layouts_reach_the_same_places() -> void:
	var wasd_places: Array = WASD.values()
	var vi_places: Array = VI.values()

	wasd_places.sort()
	vi_places.sort()

	_expect(wasd_places == vi_places,
		"WASD and vi keys cover the same eight destinations")


## Derived from the table rather than a literal list, so a binding added
## tomorrow is checked without an edit here.
func _every_binding_names_a_compass_direction() -> void:
	var compass := ["north", "northeast", "east", "southeast",
		"south", "southwest", "west", "northwest"]

	for keycode: int in MovementKeys.BINDINGS:
		var command: String = MovementKeys.BINDINGS[keycode]

		_expect(compass.has(command),
			"%s is bound to a real direction, not '%s'"
			% [OS.get_keycode_string(keycode), command])


## Empty, not null, so a caller can test the result directly.
func _an_unbound_key_means_nothing() -> void:
	for keycode: int in [KEY_F, KEY_ENTER, KEY_ESCAPE, KEY_SPACE, KEY_1]:
		_expect(MovementKeys.command_for(keycode) == "",
			"%s is not a movement key" % OS.get_keycode_string(keycode))
		_expect(not MovementKeys.is_movement_key(keycode),
			"and says so")


func _the_direction_list_is_derived_from_the_table() -> void:
	var listed := MovementKeys.directions()

	for keycode: int in MovementKeys.BINDINGS:
		_expect(listed.has(MovementKeys.BINDINGS[keycode]),
			"%s's direction is listed" % OS.get_keycode_string(keycode))

	for direction: String in listed:
		_expect(MovementKeys.BINDINGS.values().has(direction),
			"%s is listed only because something is bound to it" % direction)


## A camera that looks north is the old layout: W is north, and so on.
func _a_camera_to_the_north_changes_nothing() -> void:
	for direction: String in MovementKeys.directions():
		_expect(MovementKeys.steered(direction, Vector2(0, 1)) == direction,
			"%s stays %s with the camera to the north" % [direction, direction])


## Spelled out for the four keys and one diagonal, because the bug this
## guards is a turn the wrong way: D walking north, not south.
func _a_camera_to_the_east_turns_each_key_a_quarter() -> void:
	var east := Vector2(1, 0)
	var expected := {
		"north": "east", "east": "south", "south": "west", "west": "north",
		"northwest": "northeast",
	}

	for key: String in expected:
		_expect(MovementKeys.steered(key, east) == expected[key],
			"%s walks %s with the camera to the east" % [key, expected[key]])


func _a_camera_between_two_directions_snaps_to_one() -> void:
	var slightly_east_of_north := Vector2(0.2, 1.0)
	var northeast_ish := Vector2(1.0, 0.9)

	_expect(MovementKeys.steered("north", slightly_east_of_north) == "north",
		"a small turn keeps W at north")
	_expect(MovementKeys.steered("north", northeast_ish) == "northeast",
		"a turn near 45 degrees makes W northeast")


func _no_camera_heading_changes_nothing() -> void:
	_expect(MovementKeys.steered("west", Vector2.ZERO) == "west",
		"no heading leaves the key as it is")
	_expect(MovementKeys.steered("", Vector2(1, 0)) == "",
		"no key stays no key")


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
