extends Node
## Tests for [HudLayout] -- the rules of where a HUD element sits.
##
##     godot --headless --path godot res://tests/test_hud_layout.tscn
##
## Every rule is a static function on numbers, so each case is a rect and a
## pane. No node, no window, no mouse.

const PANE := Vector2(1600, 900)
const NARROW_PANE := Vector2(1280, 720)

var _failures := 0


func _ready() -> void:
	_a_drop_takes_the_anchor_of_its_third()
	_the_position_and_the_offset_are_inverses()
	_an_element_keeps_its_distance_from_its_corner()
	_a_rect_is_kept_inside_the_pane()
	_a_move_snaps_to_the_pane_edge()
	_a_move_snaps_beside_another_element()
	_a_move_far_from_every_line_does_not_snap()
	_a_resize_snaps_only_the_dragged_edge()
	_a_resize_snap_never_goes_under_the_smallest_size()
	_a_bad_entry_keeps_only_its_good_fields()
	_a_bad_layout_keeps_only_its_good_entries()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: hud_layout")
	get_tree().quit(0)


func _a_drop_takes_the_anchor_of_its_third() -> void:
	var box := Vector2(100, 100)

	_expect(HudLayout.nearest_anchor(Rect2(Vector2(10, 10), box), PANE) == Vector2(0, 0),
		"a box in the top-left third anchors top-left")
	_expect(HudLayout.nearest_anchor(Rect2(Vector2(1480, 780), box), PANE) == Vector2(1, 1),
		"a box in the bottom-right third anchors bottom-right")
	_expect(HudLayout.nearest_anchor(Rect2(Vector2(750, 10), box), PANE) == Vector2(0.5, 0),
		"a box at the top centre anchors top-centre")


func _the_position_and_the_offset_are_inverses() -> void:
	var anchor := Vector2(1, 0.5)
	var footprint := Vector2(300, 200)
	var position := Vector2(1200, 400)
	var offset := HudLayout.offset_for(anchor, position, footprint, PANE)

	_expect(HudLayout.position_for(anchor, offset, footprint, PANE).is_equal_approx(position),
		"the offset of a position gives the position back")


## The reason for the anchor: a minimap moved to the top right stays at the top
## right in a smaller window, the same distance from the corner.
func _an_element_keeps_its_distance_from_its_corner() -> void:
	var footprint := Vector2(242, 274)
	var rect := Rect2(Vector2(PANE.x - footprint.x - 20, 30), footprint)
	var anchor := HudLayout.nearest_anchor(rect, PANE)
	var offset := HudLayout.offset_for(anchor, rect.position, footprint, PANE)
	var moved := HudLayout.position_for(anchor, offset, footprint, NARROW_PANE)

	_expect(is_equal_approx(NARROW_PANE.x - (moved.x + footprint.x), 20.0),
		"the right edge stays 20 pixels from the right of a smaller pane")
	_expect(is_equal_approx(moved.y, 30.0), "and the top stays 30 pixels down")


func _a_rect_is_kept_inside_the_pane() -> void:
	var off := HudLayout.clamp_into(Rect2(Vector2(1500, -40), Vector2(300, 200)), PANE)

	_expect(off.position == Vector2(1300, 0), "a rect off the edge comes back inside")

	var huge := HudLayout.clamp_into(Rect2(Vector2(0, 0), Vector2(5000, 5000)), PANE)

	_expect(huge.size == PANE, "a rect larger than the pane is made smaller")


func _a_move_snaps_to_the_pane_edge() -> void:
	var near := Rect2(Vector2(HudLayout.EDGE_MARGIN + 4, 300), Vector2(200, 100))
	var snapped := HudLayout.snap_move(near, [], PANE)

	_expect(is_equal_approx(snapped.position.x, HudLayout.EDGE_MARGIN),
		"a left edge near the margin snaps to it")
	_expect(snapped.size == near.size, "and the size does not change")


## Two elements that touch keep one GAP between them, the same space as the
## shipped layout.
func _a_move_snaps_beside_another_element() -> void:
	var other := Rect2(Vector2(400, 400), Vector2(200, 200))
	var near := Rect2(Vector2(other.end.x + HudLayout.GAP + 5, 405), Vector2(100, 100))
	var others: Array[Rect2] = [other]
	var snapped := HudLayout.snap_move(near, others, PANE)

	_expect(is_equal_approx(snapped.position.x, other.end.x + HudLayout.GAP),
		"a left edge near another element snaps one gap beside it")
	_expect(is_equal_approx(snapped.position.y, other.position.y),
		"and its top aligns with the top of the other element")


func _a_move_far_from_every_line_does_not_snap() -> void:
	var far := Rect2(Vector2(313, 287), Vector2(97, 61))

	_expect(HudLayout.snap_move(far, [], PANE) == far, "a rect far from every line stays")


func _a_resize_snaps_only_the_dragged_edge() -> void:
	var rect := Rect2(Vector2(300, 300), Vector2(200, 200))
	rect.size.x = PANE.x - HudLayout.EDGE_MARGIN - rect.position.x - 5
	var snapped := HudLayout.snap_edges(rect, ResizeGrips.RIGHT, [], PANE, Vector2.ONE)

	_expect(is_equal_approx(snapped.end.x, PANE.x - HudLayout.EDGE_MARGIN),
		"the dragged right edge snaps to the margin")
	_expect(is_equal_approx(snapped.position.x, rect.position.x),
		"and the left edge stays")


func _a_resize_snap_never_goes_under_the_smallest_size() -> void:
	# The right edge of `other` is 4 pixels left of the right edge of `rect`.
	var other := Rect2(Vector2(330, 100), Vector2(10, 10))
	var rect := Rect2(Vector2(304, 300), Vector2(40, 40))
	var others: Array[Rect2] = [other]
	var snapped := HudLayout.snap_edges(rect, ResizeGrips.RIGHT, others, PANE,
		Vector2(40, 40))

	_expect(snapped == rect, "a snap that would make the rect too small does not happen")


func _a_bad_entry_keeps_only_its_good_fields() -> void:
	var entry := HudLayout.sanitize_entry({
		HudLayout.KEY_ANCHOR: Vector2(0.9, 0.2),
		HudLayout.KEY_SIZE: "wide",
		HudLayout.KEY_SCALE: 9.0,
		HudLayout.KEY_OPACITY: -1,
		HudLayout.KEY_SHOWN: "yes",
	})

	_expect(not entry.has(HudLayout.KEY_ANCHOR),
		"an anchor with no offset is dropped with it")
	_expect(not entry.has(HudLayout.KEY_SIZE), "a size that is not a vector is dropped")
	_expect(is_equal_approx(entry.get(HudLayout.KEY_SCALE, 0.0), HudLayout.MAX_SCALE),
		"a runaway scale is clamped")
	_expect(is_equal_approx(entry.get(HudLayout.KEY_OPACITY, 1.0), HudLayout.MIN_OPACITY),
		"and so is an opacity under zero")
	_expect(not entry.has(HudLayout.KEY_SHOWN), "a Shown that is not a bool is dropped")

	var anchored := HudLayout.sanitize_entry({
		HudLayout.KEY_ANCHOR: Vector2(0.9, 0.2),
		HudLayout.KEY_OFFSET: Vector2i(3, 4),
	})

	_expect(anchored.get(HudLayout.KEY_ANCHOR) == Vector2(1, 0),
		"an anchor goes to the nearest of 0, 0.5 and 1")
	_expect(anchored.get(HudLayout.KEY_OFFSET) == Vector2(3, 4),
		"and an integer offset becomes a float one")


func _a_bad_layout_keeps_only_its_good_entries() -> void:
	var layout := HudLayout.sanitize({
		"minimap": {HudLayout.KEY_SHOWN: false},
		"xp": "not an entry",
		7: {HudLayout.KEY_SHOWN: false},
	})

	_expect(layout.keys() == ["minimap"], "only the usable entry is kept")
	_expect(HudLayout.sanitize("not a layout").is_empty(), "a layout that is not a dictionary is empty")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
