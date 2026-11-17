extends Node
## Tests for the picture pose of an item ([PicturePose]): the look file
## `item_pictures.json`, and its values.
##
##     godot --headless --path godot res://tests/world/look/test_picture_pose.tscn
##
## Needs nothing running. It gives the reader its content through the cache
## of [LookFile], so no file of the repository changes. The cases:
##
## 1. A row with no key gives the default pose. The default turn is the
##    tilt, then the turn about the vertical.
## 2. Each value of a row stays in its range. A value of a wrong type gives
##    the default.
## 3. The turn of a row has the order of [member Node3D.rotation].
## 4. The offset stops at the edge of the cell. A smaller picture has more
##    room.
## 5. A row of the default pose takes the row of the item out of the
##    content. Each other row goes in as a full row.
## 6. A content with a bad form names its problem. An empty content has
##    none.
## 7. A row of the cache of [LookFile] is the row of the item.
## 8. The picture file of the repository reads, with no problem.

const TOLERANCE := 0.0001

const ITEM := "some_item"
const OTHER_ITEM := "some_other_item"

## The side of the square that a picture can fill, for the offset cases.
const SIDE := 0.96

var _failures := 0


func _ready() -> void:
	_no_key_gives_the_default_pose()
	_each_value_stays_in_its_range()
	_the_turn_has_the_order_of_a_rotation()
	_the_offset_stops_at_the_edge()
	_a_default_row_leaves_the_content()
	_a_bad_form_names_its_problem()
	_the_cache_gives_the_row()
	_the_repository_file_reads()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: picture_pose")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _no_key_gives_the_default_pose() -> void:
	var tilt := Basis(Vector3.RIGHT, deg_to_rad(PicturePose.DEFAULT_TURN.x))
	var turn := Basis(Vector3.UP, deg_to_rad(PicturePose.DEFAULT_TURN.y))

	_expect(is_equal_approx(PicturePose.zoom_of({}), PicturePose.DEFAULT_ZOOM),
		"a row with no zoom has the default zoom")
	_expect(PicturePose.offset_of({}).is_equal_approx(PicturePose.DEFAULT_OFFSET),
		"a row with no offset has the default offset")
	_expect(PicturePose.turn_of({}).is_equal_approx(PicturePose.DEFAULT_TURN),
		"a row with no turn has the default turn")
	_expect(PicturePose.basis_of({}).is_equal_approx(turn * tilt),
		"the default turn is the tilt, then the turn about the vertical")
	_expect(PicturePose.is_default({}), "an empty row is the default pose")
	_expect(PicturePose.is_default(PicturePose.default_row()),
		"the default row is the default pose")
	_expect(is_equal_approx(PicturePose.DEFAULT_ZOOM, PicturePose.ZOOM_HIGH),
		"the default zoom fills the cell")


func _each_value_stays_in_its_range() -> void:
	var high := {PicturePose.KEY_ZOOM: PicturePose.ZOOM_HIGH * 3.0,
		PicturePose.KEY_OFFSET: [PicturePose.OFFSET_LIMIT * 3.0, -PicturePose.OFFSET_LIMIT * 3.0]}
	var low := {PicturePose.KEY_ZOOM: 0.0}
	var wrong := {PicturePose.KEY_ZOOM: "large", PicturePose.KEY_OFFSET: [1.0],
		PicturePose.KEY_TURN: "left"}

	_expect(is_equal_approx(PicturePose.zoom_of(high), PicturePose.ZOOM_HIGH),
		"a zoom above the range stops at its top")
	_expect(is_equal_approx(PicturePose.zoom_of(low), PicturePose.ZOOM_LOW),
		"a zoom below the range stops at its bottom")
	_expect(PicturePose.offset_of(high).is_equal_approx(
		Vector2(PicturePose.OFFSET_LIMIT, -PicturePose.OFFSET_LIMIT)),
		"an offset out of the range stops at the edge of the cell")
	_expect(PicturePose.is_default(wrong), "each value of a wrong type gives its default")

	var made := PicturePose.row_from(PicturePose.ZOOM_HIGH * 3.0,
		Vector2.ONE * PicturePose.OFFSET_LIMIT * 3.0, Vector3.ZERO)

	_expect(is_equal_approx(made[PicturePose.KEY_ZOOM], PicturePose.ZOOM_HIGH),
		"a made row holds a zoom of the range")
	_expect(is_equal_approx(made[PicturePose.KEY_OFFSET][0], PicturePose.OFFSET_LIMIT),
		"a made row holds an offset of the range")


func _the_turn_has_the_order_of_a_rotation() -> void:
	var degrees := Vector3(40.0, -75.0, 20.0)
	var row := PicturePose.row_from(PicturePose.DEFAULT_ZOOM, Vector2.ZERO, degrees)
	var node := Node3D.new()

	node.rotation_degrees = degrees
	_expect(PicturePose.basis_of(row).is_equal_approx(node.basis),
		"the turn of a row is the rotation of a node with those degrees")
	_expect(PicturePose.turn_of(row).is_equal_approx(degrees), "a row keeps its turn in degrees")
	node.free()


func _the_offset_stops_at_the_edge() -> void:
	var push := {PicturePose.KEY_OFFSET: [PicturePose.OFFSET_LIMIT, -PicturePose.OFFSET_LIMIT]}
	var nudge := {PicturePose.KEY_OFFSET: [0.1, 0.0]}
	var full := Vector2(SIDE, SIDE * 0.5)
	var half := Vector2(SIDE, SIDE) * 0.5

	var placed := PicturePose.placed_offset(push, full, SIDE)

	_expect(is_zero_approx(placed.x), "a picture that fills the cell on X has no room on X")
	_expect(absf(placed.y + (SIDE * 0.25)) < TOLERANCE,
		"the offset on Y stops where the outline meets the edge")

	placed = PicturePose.placed_offset(push, half, SIDE)
	_expect(placed.is_equal_approx(Vector2(SIDE, -SIDE) * 0.25),
		"a smaller picture has more room on each axis")
	_expect(PicturePose.placed_offset(nudge, half, SIDE).is_equal_approx(Vector2(0.1 * SIDE, 0.0)),
		"an offset inside the room is a share of the side")
	_expect(PicturePose.placed_offset(push, Vector2.ONE * SIDE * 2.0, SIDE) == Vector2.ZERO,
		"an outline larger than the cell gets no offset")


func _a_default_row_leaves_the_content() -> void:
	var content := {}
	var row := {PicturePose.KEY_ZOOM: 0.5}

	PicturePose.set_picture(content, ITEM, row)
	_expect(PicturePose.has_picture(content, ITEM), "a changed pose goes into the content")
	_expect(content.get(PicturePose.KEY_FORMAT) == PicturePose.FORMAT,
		"the content gets its format")
	_expect(PicturePose.problem_of(content).is_empty(), "the content has a good form")

	var kept: Dictionary = content[PicturePose.KEY_PICTURES][ITEM]

	_expect(kept.has(PicturePose.KEY_ZOOM) and kept.has(PicturePose.KEY_OFFSET)
		and kept.has(PicturePose.KEY_TURN), "the row of the content is a full row")
	_expect(is_equal_approx(PicturePose.zoom_of(PicturePose.shown_row(content, ITEM)), 0.5),
		"the shown row has the zoom of the content")
	_expect(PicturePose.is_default(PicturePose.shown_row(content, OTHER_ITEM)),
		"an item with no row shows the default pose")

	PicturePose.set_picture(content, ITEM, PicturePose.default_row())
	_expect(not PicturePose.has_picture(content, ITEM),
		"a row of the default pose takes the row out")
	_expect(not PicturePose.clear_picture(content, ITEM), "a second removal changes nothing")
	PicturePose.set_picture(content, "", row)
	_expect(content[PicturePose.KEY_PICTURES].is_empty(), "an empty key gets no row")


func _a_bad_form_names_its_problem() -> void:
	var good := {PicturePose.KEY_FORMAT: PicturePose.FORMAT,
		PicturePose.KEY_PICTURES: {ITEM: {PicturePose.KEY_ZOOM: 0.5}}}
	var bad_rows := [
		"a text",
		{PicturePose.KEY_ZOOM: "large"},
		{PicturePose.KEY_OFFSET: [0.0, 0.0, 0.0]},
		{PicturePose.KEY_TURN: [0.0, 0.0]},
	]

	_expect(PicturePose.problem_of({}).is_empty(), "an empty content has no problem")
	_expect(PicturePose.problem_of(good).is_empty(), "a good content has no problem")
	_expect(not PicturePose.problem_of({PicturePose.KEY_PICTURES: {}}).is_empty(),
		"a content with no format has a problem")
	_expect(not PicturePose.problem_of({PicturePose.KEY_FORMAT: PicturePose.FORMAT + 1}).is_empty(),
		"a newer format has a problem")
	_expect(not PicturePose.problem_of({PicturePose.KEY_FORMAT: PicturePose.FORMAT,
		PicturePose.KEY_PICTURES: []}).is_empty(), "pictures that are no table have a problem")

	for row: Variant in bad_rows:
		var content := {PicturePose.KEY_FORMAT: PicturePose.FORMAT,
			PicturePose.KEY_PICTURES: {ITEM: row}}

		_expect(PicturePose.problem_of(content).contains(ITEM),
			"the problem of the row %s names its item" % str(row))


func _the_cache_gives_the_row() -> void:
	var content := {}

	PicturePose.set_picture(content, ITEM, {PicturePose.KEY_ZOOM: 0.5})
	LookFile.put(PicturePose.PATH, content)
	_expect(is_equal_approx(PicturePose.zoom_of(PicturePose.file_row(ITEM)), 0.5),
		"the row of the cache is the row of the item")
	_expect(PicturePose.file_row(OTHER_ITEM).is_empty(), "an item with no row gives an empty row")
	LookFile.put(PicturePose.PATH, {PicturePose.KEY_PICTURES: "no table"})
	_expect(PicturePose.file_row(ITEM).is_empty(), "pictures that are no table give no row")
	LookFile.forget(PicturePose.PATH)


func _the_repository_file_reads() -> void:
	var text := FileAccess.get_file_as_string(PicturePose.PATH)
	var content := FigureJson.parse(text)

	_expect(not content.is_empty(), "the picture file of the repository is one JSON object")
	_expect(PicturePose.problem_of(content).is_empty(),
		"the picture file of the repository has a good form: %s"
			% PicturePose.problem_of(content))

	for asset_key: String in content.get(PicturePose.KEY_PICTURES, {}):
		_expect(not PicturePose.is_default(content[PicturePose.KEY_PICTURES][asset_key]),
			"the file keeps no row of the default pose (%s)" % asset_key)
