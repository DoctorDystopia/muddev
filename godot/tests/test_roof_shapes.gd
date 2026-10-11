extends Node
## Tests for [RoofShapes]: the corner heights of each roof shape
## (DESIGN-0013 section 6.2).
##
##     godot --headless --path godot res://tests/test_roof_shapes.tscn
##
## Needs nothing running and no editor. Each case reads the pitch and the
## size from its own locals, so a retune of the defaults moves no case.

const _PITCH := 4

## Even on both sides, so each shape has a corner at its centre.
const _SIZE := Vector2i(4, 6)

var _failures := 0


func _ready() -> void:
	_a_flat_roof_does_not_rise()
	_a_gable_ridge_follows_its_turn()
	_a_hip_rises_from_every_edge()
	_a_pyramid_has_one_apex()
	_a_pyramid_on_a_square_is_a_hip()
	_a_shed_rises_from_its_low_edge()
	_four_turns_give_the_shape_back()
	_the_overhang_hangs_below_the_wall_line()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: roof_shapes")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _rise(rises: PackedInt32Array, size: Vector2i, at: Vector2i) -> int:
	return rises[at.y * (size.x + 1) + at.x]


## The corners on the outer edge of a roof of `size` tiles.
static func _edge_corners(size: Vector2i) -> Array[Vector2i]:
	var corners: Array[Vector2i] = []

	for j: int in size.y + 1:
		for i: int in size.x + 1:
			if i == 0 or j == 0 or i == size.x or j == size.y:
				corners.append(Vector2i(i, j))

	return corners


func _a_flat_roof_does_not_rise() -> void:
	var rises := RoofShapes.rises(_SIZE, RoofShapes.Shape.FLAT, _PITCH, 0)

	_expect(rises.size() == (_SIZE.x + 1) * (_SIZE.y + 1), "one rise for each corner")
	_expect(rises.count(0) == rises.size(), "no corner of a flat roof rises")


func _a_gable_ridge_follows_its_turn() -> void:
	var along_x := RoofShapes.rises(_SIZE, RoofShapes.Shape.GABLE, _PITCH, 0)
	var along_y := RoofShapes.rises(_SIZE, RoofShapes.Shape.GABLE, _PITCH, 1)
	@warning_ignore("integer_division")
	var middle := _SIZE / 2

	for i: int in _SIZE.x + 1:
		_expect(_rise(along_x, _SIZE, Vector2i(i, middle.y)) == _PITCH * middle.y,
			"turn 0: corner %d of the middle row is on the ridge" % i)
		_expect(_rise(along_x, _SIZE, Vector2i(i, 0)) == 0,
			"turn 0: corner %d of the south edge is on the eave" % i)

	for j: int in _SIZE.y + 1:
		_expect(_rise(along_y, _SIZE, Vector2i(middle.x, j)) == _PITCH * middle.x,
			"turn 1: corner %d of the middle column is on the ridge" % j)
		_expect(_rise(along_y, _SIZE, Vector2i(0, j)) == 0,
			"turn 1: corner %d of the west edge is on the eave" % j)


func _a_hip_rises_from_every_edge() -> void:
	var rises := RoofShapes.rises(_SIZE, RoofShapes.Shape.HIP, _PITCH, 0)
	@warning_ignore("integer_division")
	var peak := _PITCH * mini(_SIZE.x, _SIZE.y) / 2

	for corner: Vector2i in _edge_corners(_SIZE):
		_expect(_rise(rises, _SIZE, corner) == 0, "edge corner %s is on the eave" % corner)

	_expect(rises.count(peak) == _SIZE.y - _SIZE.x + 1,
		"the ridge of a hip runs along the long side")


func _a_pyramid_has_one_apex() -> void:
	var rises := RoofShapes.rises(_SIZE, RoofShapes.Shape.PYRAMID, _PITCH, 0)
	var highest := 0

	for rise: int in rises:
		highest = maxi(highest, rise)

	for corner: Vector2i in _edge_corners(_SIZE):
		_expect(_rise(rises, _SIZE, corner) == 0, "edge corner %s is on the eave" % corner)

	_expect(rises.count(highest) == 1, "a pyramid has one highest corner")
	@warning_ignore("integer_division")
	_expect(_rise(rises, _SIZE, _SIZE / 2) == highest, "the apex is at the centre")


func _a_pyramid_on_a_square_is_a_hip() -> void:
	var square := Vector2i(_SIZE.x, _SIZE.x)

	_expect(RoofShapes.rises(square, RoofShapes.Shape.PYRAMID, _PITCH, 0)
		== RoofShapes.rises(square, RoofShapes.Shape.HIP, _PITCH, 0),
		"on a square, the pyramid and the hip are one shape")


func _a_shed_rises_from_its_low_edge() -> void:
	# turn -> a corner on the low edge, and the corner across from it.
	var cases := {
		0: [Vector2i(1, 0), Vector2i(1, _SIZE.y)],
		1: [Vector2i(0, 1), Vector2i(_SIZE.x, 1)],
		2: [Vector2i(1, _SIZE.y), Vector2i(1, 0)],
		3: [Vector2i(_SIZE.x, 1), Vector2i(0, 1)],
	}

	for turn: int in cases:
		var rises := RoofShapes.rises(_SIZE, RoofShapes.Shape.SHED, _PITCH, turn)
		var low: Vector2i = cases[turn][0]
		var high: Vector2i = cases[turn][1]
		var span := absi(high.x - low.x) + absi(high.y - low.y)

		_expect(_rise(rises, _SIZE, low) == 0, "turn %d: the low edge is on the eave" % turn)
		_expect(_rise(rises, _SIZE, high) == _PITCH * span,
			"turn %d: the high edge rises one pitch for each tile" % turn)


func _four_turns_give_the_shape_back() -> void:
	for shape: int in RoofShapes.SHAPE_NAMES.size():
		for turn: int in RoofShapes.TURNS:
			_expect(RoofShapes.rises(_SIZE, shape, _PITCH, turn)
				== RoofShapes.rises(_SIZE, shape, _PITCH, turn + RoofShapes.TURNS),
				"%s: four more turns change nothing" % RoofShapes.SHAPE_NAMES[shape])


func _the_overhang_hangs_below_the_wall_line() -> void:
	var eave := 40
	var overhang := 2

	_expect(RoofShapes.outer_eave(eave, RoofShapes.Shape.GABLE, _PITCH, overhang)
		== eave - _PITCH * overhang, "a sloped roof hangs one pitch for each tile")
	_expect(RoofShapes.outer_eave(eave, RoofShapes.Shape.FLAT, _PITCH, overhang) == eave,
		"a flat roof stays level")
