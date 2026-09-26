extends Node
## Unit tests for AreaLook and AreaEnvironment: the fog and light table, the
## blend between two areas, and the fog that follows the camera arm.
##
##     godot --headless --path godot res://tests/test_area_look.tscn
##
## Needs nothing running. Headless draws nothing, so each case reads the
## properties of the Environment and the sun. Those properties are the whole
## output of both files.

var _failures := 0

## Two areas with rows, and one with none.
const FIRST_AREA := "oasis"
const SECOND_AREA := "azm_plains"
const NO_SUCH_AREA := "no_such_area"

## A camera arm length, in world units. Any value that is not zero shows that
## the arm moves the fog.
const ARM_LENGTH := 14.0

## How close two floats must be to count as equal.
const TOLERANCE := 0.001

## Physics frames to wait for a SpringArm3D to measure its length.
const ARM_SETTLE_FRAMES := 3


func _ready() -> void:
	_every_row_holds_every_field()
	_every_row_fogs_out_after_it_fogs_in()
	_an_area_with_no_row_gets_the_fallback()
	_a_blend_starts_at_from_and_ends_at_to()
	_an_angle_blends_the_short_way()
	_the_fog_moves_with_the_arm()
	_the_first_area_snaps()
	_a_second_area_blends()
	_a_change_mid_blend_starts_from_the_screen()
	_the_same_area_again_does_nothing()
	await _the_node_reads_the_arm_length()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: area_look")
	get_tree().quit(0)


## A row that lacks a field fails in the blend, in the middle of a walk. This
## finds it at the table.
func _every_row_holds_every_field() -> void:
	for area: String in AreaLook.LOOKS:
		var row: Dictionary = AreaLook.LOOKS[area]

		for field: String in AreaLook.FALLBACK:
			var expected := typeof(AreaLook.FALLBACK[field])
			var has_field := row.has(field)

			_expect(has_field, "%s has the field %s" % [area, field])

			if has_field:
				_expect(typeof(row[field]) == expected,
					"%s.%s has the type of the fallback" % [area, field])

		for field: String in row:
			_expect(AreaLook.FALLBACK.has(field),
				"%s.%s is a field that the blend reads" % [area, field])


func _every_row_fogs_out_after_it_fogs_in() -> void:
	var rows: Dictionary = AreaLook.LOOKS.duplicate()

	rows["(fallback)"] = AreaLook.FALLBACK

	for area: String in rows:
		var row: Dictionary = rows[area]
		var begin: float = row["fog_begin"]
		var end: float = row["fog_end"]

		_expect(begin >= 0.0, "%s starts its fog at or past the player" % area)
		_expect(end > begin, "%s ends its fog after it starts" % area)


func _an_area_with_no_row_gets_the_fallback() -> void:
	var look := AreaLook.look_for(NO_SUCH_AREA)

	_expect(look == AreaLook.FALLBACK, "an unknown area gets the fallback")


func _a_blend_starts_at_from_and_ends_at_to() -> void:
	var from := AreaLook.look_for(FIRST_AREA)
	var to := AreaLook.look_for(SECOND_AREA)
	var start := AreaLook.blend(from, to, 0.0)
	var finish := AreaLook.blend(from, to, 1.0)
	var middle := AreaLook.blend(from, to, 0.5)
	var from_fog: Color = from["fog_color"]
	var to_fog: Color = to["fog_color"]
	var middle_fog: Color = middle["fog_color"]

	_expect(_same_look(start, from), "weight 0 is the first look")
	_expect(_same_look(finish, to), "weight 1 is the second look")
	_expect(middle_fog.is_equal_approx(from_fog.lerp(to_fog, 0.5)),
		"weight 0.5 is half way in colour")


func _an_angle_blends_the_short_way() -> void:
	var from := AreaLook.FALLBACK.duplicate()
	var to := AreaLook.FALLBACK.duplicate()

	from["sun_azimuth"] = 350.0
	to["sun_azimuth"] = 10.0

	var middle := AreaLook.blend(from, to, 0.5)
	var azimuth: float = fposmod(middle["sun_azimuth"], 360.0)
	var through_north := (is_equal_approx(azimuth, 0.0)
		or is_equal_approx(azimuth, 360.0))

	_expect(through_north,
		"350 to 10 degrees passes 0, not 180 (got %.2f)" % azimuth)


func _the_fog_moves_with_the_arm() -> void:
	var look := AreaLook.look_for(FIRST_AREA)
	var depth := AreaLook.fog_depth(look, ARM_LENGTH)
	var begin: float = look["fog_begin"]
	var end: float = look["fog_end"]

	_expect(is_equal_approx(depth.x, ARM_LENGTH + begin),
		"the fog begins its distance past the player")
	_expect(is_equal_approx(depth.y, ARM_LENGTH + end),
		"the fog ends its distance past the player")


## A login is not a walk. The first area must be on screen at once.
func _the_first_area_snaps() -> void:
	var rig := _new_rig()
	var node: AreaEnvironment = rig["node"]
	var sun: DirectionalLight3D = rig["sun"]
	var target := AreaLook.look_for(FIRST_AREA)
	var fog: Color = target["fog_color"]
	var elevation := deg_to_rad(float(target["sun_elevation"]))

	node.set_area(FIRST_AREA)

	_expect(_same_look(node.drawn_look(), target), "the first area snaps")
	_expect(node.environment.background_color.is_equal_approx(fog),
		"the background is the fog colour")
	_expect(node.environment.fog_light_color.is_equal_approx(fog),
		"and so is the fog")
	_expect(is_equal_approx(sun.rotation.x, -elevation),
		"the sun stands at the elevation of the area")
	_expect(rig["emitted"].size() == 1, "the change is announced one time")

	_free_rig(rig)


func _a_second_area_blends() -> void:
	var rig := _new_rig()
	var node: AreaEnvironment = rig["node"]
	var from := AreaLook.look_for(FIRST_AREA)
	var to := AreaLook.look_for(SECOND_AREA)
	var half := AreaEnvironment.BLEND_SECONDS * 0.5

	node.set_area(FIRST_AREA)
	node.set_area(SECOND_AREA)

	_expect(_same_look(node.drawn_look(), from),
		"a second area does not snap")

	node._process(half)

	var expected := AreaLook.blend(from, to, 0.5)

	_expect(_same_look(node.drawn_look(), expected),
		"half the blend time gives half the blend")

	node._process(half)

	_expect(_same_look(node.drawn_look(), to), "the blend ends at the target")

	var last: Dictionary = rig["emitted"].back()

	_expect(_same_look(last, to), "the announced look is the target")

	_free_rig(rig)


## Two changes close together, for example a step back across a border. The
## second blend must start from the colours on screen, not jump back.
func _a_change_mid_blend_starts_from_the_screen() -> void:
	var rig := _new_rig()
	var node: AreaEnvironment = rig["node"]

	node.set_area(FIRST_AREA)
	node.set_area(SECOND_AREA)
	node._process(AreaEnvironment.BLEND_SECONDS * 0.5)

	var on_screen := node.drawn_look()

	node.set_area(FIRST_AREA)

	_expect(_same_look(node.drawn_look(), on_screen),
		"a change mid-blend starts where the screen is")

	_free_rig(rig)


func _the_same_area_again_does_nothing() -> void:
	var rig := _new_rig()
	var node: AreaEnvironment = rig["node"]

	node.set_area(FIRST_AREA)
	node.set_area(FIRST_AREA)

	_expect(rig["emitted"].size() == 1, "the same area is not announced again")

	_free_rig(rig)


## The arm is a real SpringArm3D here. It measures its length in a physics
## frame, so this case waits for some.
func _the_node_reads_the_arm_length() -> void:
	var rig := _new_rig()
	var node: AreaEnvironment = rig["node"]
	var arm: SpringArm3D = rig["arm"]
	var sun: DirectionalLight3D = rig["sun"]

	arm.spring_length = ARM_LENGTH
	node.set_area(FIRST_AREA)

	for frame: int in ARM_SETTLE_FRAMES:
		await get_tree().physics_frame

	node._process(0.0)

	var expected := AreaLook.fog_depth(AreaLook.look_for(FIRST_AREA),
		arm.get_hit_length())

	_expect(is_equal_approx(arm.get_hit_length(), ARM_LENGTH),
		"the arm measured its length (got %.2f)" % arm.get_hit_length())
	_expect(is_equal_approx(node.environment.fog_depth_begin, expected.x),
		"the fog begins at the arm plus the look")
	_expect(is_equal_approx(node.environment.fog_depth_end, expected.y),
		"the fog ends at the arm plus the look")
	_expect(is_equal_approx(sun.directional_shadow_max_distance, expected.y),
		"the shadows stop at the fog end")

	_free_rig(rig)


# ─── Helpers ─────────────────────────────────────────────────────────────────

## An AreaEnvironment with a sun and an arm, the shape `world.tscn` gives it.
func _new_rig() -> Dictionary:
	var root := Node3D.new()
	var node := AreaEnvironment.new()
	var sun := DirectionalLight3D.new()
	var arm := SpringArm3D.new()
	var emitted: Array = []

	node.environment = Environment.new()
	node.sun = sun
	node.arm = arm
	node.look_changed.connect(
		func(look: Dictionary) -> void: emitted.append(look))

	root.add_child(sun)
	root.add_child(arm)
	root.add_child(node)
	add_child(root)

	return {"root": root, "node": node, "sun": sun, "arm": arm,
		"emitted": emitted}


func _free_rig(rig: Dictionary) -> void:
	var root: Node3D = rig["root"]

	remove_child(root)
	root.free()


func _same_look(first: Dictionary, second: Dictionary) -> bool:
	for field: String in AreaLook.FALLBACK:
		if not _same_value(first[field], second[field]):
			return false

	return true


func _same_value(first: Variant, second: Variant) -> bool:
	if first is Color:
		var first_color: Color = first

		return first_color.is_equal_approx(second)

	return absf(float(first) - float(second)) < TOLERANCE


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
