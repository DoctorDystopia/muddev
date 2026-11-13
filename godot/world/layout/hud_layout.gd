class_name HudLayout
extends RefCounted
## The rules of the HUD layout: where an element sits, how a drop picks its
## anchor, and how an edge snaps. Pure. It holds no node, no setting and no
## mouse, so a test checks each rule with numbers only.
##
## ## An element keeps its distance from the nearest corner
##
## A layout entry stores an anchor and an offset, not a position. The anchor
## is a point on each axis of the pane: 0 is the left or the top edge, 0.5 is
## the centre, and 1 is the right or the bottom edge. The position of an
## element is `anchor * (pane - footprint) + offset`. Thus an element with the
## anchor (1, 0) keeps its distance from the top-right corner when the window
## changes size. The minimap stays at the top right in every window.
##
## A drop picks the anchor from the centre of the element. The left third of
## the pane gives 0, the middle third gives 0.5, and the right third gives 1.
## The player never sets an anchor by hand.
##
## ## The footprint is what the player sees
##
## An element has a size and a scale. The footprint is the size times the
## scale: the rect on the screen. The rules here work on the footprint. The
## entry keeps the size without the scale, so a change of scale does not
## change the size that the player gave.
##
## ## A layout entry is partial
##
## An entry holds only the fields that the player changed. A missing field
## takes the default of the element. [method sanitize_entry] drops each field
## that has a wrong type, so a hand-edited file gives the default and not a
## crash.
##
## Author: Nick Hobar
## Creation date: 09/29/2026

## The fields of one layout entry.
const KEY_ANCHOR := "anchor"
const KEY_OFFSET := "offset"
const KEY_SIZE := "size"
const KEY_SHOWN := "shown"
const KEY_OPACITY := "opacity"
const KEY_SCALE := "scale"

## How far an element stays inside the pane edges when it snaps to them, and
## how far the shipped layout keeps each element from the edge, in pixels.
const EDGE_MARGIN := 8.0

## The space that a snap leaves between two elements that touch, in pixels.
const GAP := 8.0

## How near an edge must come to a line before it snaps to it, in pixels.
const SNAP_DISTANCE := 10.0

## The limits on the scale of one element. The global interface scale in
## Options applies on top of it.
const MIN_SCALE := 0.5
const MAX_SCALE := 2.0
const DEFAULT_SCALE := 1.0

## The limits on the opacity of one element. An element can set a higher
## floor. See [member HudSlot.min_opacity].
const MIN_OPACITY := 0.0
const MAX_OPACITY := 1.0
const DEFAULT_OPACITY := 1.0

## The largest pixel figure that a saved entry can carry. A fence around a
## number read from a file, not a limit on a box that the player can make.
const MAX_PIXELS := 4000.0

## The anchor on one axis is 0, 0.5 or 1.
const ANCHOR_STEP := 0.5

## The part of the pane that gives each anchor. See [method nearest_anchor].
const ANCHOR_THIRD := 1.0 / 3.0


## Where an element sits, from its anchor, its offset and its footprint.
static func position_for(anchor: Vector2, offset: Vector2, footprint: Vector2,
		pane: Vector2) -> Vector2:
	return anchor * (pane - footprint) + offset


## The offset that puts an element of `footprint` at `position`. The inverse
## of [method position_for].
static func offset_for(anchor: Vector2, position: Vector2, footprint: Vector2,
		pane: Vector2) -> Vector2:
	return position - anchor * (pane - footprint)


## The anchor of the third of the pane that holds the centre of `rect`.
static func nearest_anchor(rect: Rect2, pane: Vector2) -> Vector2:
	var centre := rect.get_center()

	return Vector2(_axis_anchor(centre.x, pane.x), _axis_anchor(centre.y, pane.y))


## `rect`, moved and made smaller until it is fully inside the pane.
##
## The one owner of "an element stays on the screen". A layout saved by a wide
## window comes back into a narrow one here, and is not refused on the way in.
static func clamp_into(rect: Rect2, pane: Vector2) -> Rect2:
	var room := pane.max(Vector2.ONE)
	var fitted := rect.size.min(room)
	var top_left := rect.position.clamp(Vector2.ZERO, room - fitted)

	return Rect2(top_left, fitted)


## `rect`, moved so that an edge or the centre meets a line near it.
##
## The lines are the pane edges one [constant EDGE_MARGIN] in, the centre of
## the pane, and the edges and centres of `others`. An edge also snaps one
## [constant GAP] outside an edge of another element, so two elements that
## touch keep the same space as the shipped layout. The size never changes.
static func snap_move(rect: Rect2, others: Array[Rect2], pane: Vector2,
		distance: float = SNAP_DISTANCE) -> Rect2:
	var moved := rect

	for axis: int in [Vector2.AXIS_X, Vector2.AXIS_Y]:
		var low := rect.position[axis]
		var high := rect.end[axis]
		var centre := rect.get_center()[axis]
		var best := _nearest_delta(low, _low_lines(others, pane, axis), distance)
		best = _closer(best, _nearest_delta(high, _high_lines(others, pane, axis), distance))
		best = _closer(best, _nearest_delta(centre, _centre_lines(others, pane, axis), distance))

		if is_finite(best):
			moved.position[axis] += best

	return moved


## `rect`, with each edge in `edges` moved to a line near it.
##
## `edges` are the bits of [ResizeGrips]. Only those edges move, and an edge
## does not move when the snap makes the rect smaller than `smallest`.
static func snap_edges(rect: Rect2, edges: int, others: Array[Rect2],
		pane: Vector2, smallest: Vector2, distance: float = SNAP_DISTANCE) -> Rect2:
	var low := rect.position
	var high := rect.end
	var sides := [
		[ResizeGrips.LEFT, Vector2.AXIS_X, true],
		[ResizeGrips.RIGHT, Vector2.AXIS_X, false],
		[ResizeGrips.TOP, Vector2.AXIS_Y, true],
		[ResizeGrips.BOTTOM, Vector2.AXIS_Y, false],
	]

	for side: Array in sides:
		var bit: int = side[0]
		var axis: int = side[1]
		var is_low: bool = side[2]

		if edges & bit == 0:
			continue

		if is_low:
			var delta := _nearest_delta(low[axis], _low_lines(others, pane, axis), distance)

			if is_finite(delta) and high[axis] - (low[axis] + delta) >= smallest[axis]:
				low[axis] += delta
		else:
			var delta := _nearest_delta(high[axis], _high_lines(others, pane, axis), distance)

			if is_finite(delta) and (high[axis] + delta) - low[axis] >= smallest[axis]:
				high[axis] += delta

	return Rect2(low, high - low)


## One entry as the file gave it, with each unusable field dropped.
##
## The anchor and the offset go together: an entry with only one of them
## keeps neither. A number out of its bounds is clamped, not dropped.
static func sanitize_entry(value: Variant) -> Dictionary:
	var entry := {}

	if typeof(value) != TYPE_DICTIONARY:
		return entry

	var raw: Dictionary = value
	var anchor: Variant = _vector(raw.get(KEY_ANCHOR))
	var offset: Variant = _vector(raw.get(KEY_OFFSET))
	var size: Variant = _vector(raw.get(KEY_SIZE))

	if anchor != null and offset != null:
		entry[KEY_ANCHOR] = _snap_anchor(anchor)
		entry[KEY_OFFSET] = (offset as Vector2).clamp(
			-Vector2.ONE * MAX_PIXELS, Vector2.ONE * MAX_PIXELS)

	if size != null and (size as Vector2).x > 0.0 and (size as Vector2).y > 0.0:
		entry[KEY_SIZE] = (size as Vector2).clamp(Vector2.ONE, Vector2.ONE * MAX_PIXELS)

	if typeof(raw.get(KEY_SHOWN)) == TYPE_BOOL:
		entry[KEY_SHOWN] = raw[KEY_SHOWN]

	if _is_number(raw.get(KEY_OPACITY)):
		entry[KEY_OPACITY] = clampf(float(raw[KEY_OPACITY]), MIN_OPACITY, MAX_OPACITY)

	if _is_number(raw.get(KEY_SCALE)):
		entry[KEY_SCALE] = clampf(float(raw[KEY_SCALE]), MIN_SCALE, MAX_SCALE)

	return entry


## A whole layout as the file gave it: element key -> entry. A key that is not
## a string, and an entry with nothing usable in it, are dropped.
static func sanitize(value: Variant) -> Dictionary:
	var layout := {}

	if typeof(value) != TYPE_DICTIONARY:
		return layout

	var raw: Dictionary = value

	for key: Variant in raw:
		if typeof(key) != TYPE_STRING and typeof(key) != TYPE_STRING_NAME:
			continue

		var entry := sanitize_entry(raw[key])

		if not entry.is_empty():
			layout[str(key)] = entry

	return layout


static func _axis_anchor(centre: float, length: float) -> float:
	if length <= 0.0:
		return 0.0

	var part := centre / length

	if part < ANCHOR_THIRD:
		return 0.0

	if part > 1.0 - ANCHOR_THIRD:
		return 1.0

	return ANCHOR_STEP


## The lines that the left or the top edge of a rect snaps to.
static func _low_lines(others: Array[Rect2], _pane: Vector2, axis: int) -> Array[float]:
	var lines: Array[float] = [EDGE_MARGIN]

	# Align with the left edge of the other, or sit one gap to its right. No
	# line puts two edges flush: it is less than the snap distance from the
	# gap line, and the drag would jump between the two.
	for other: Rect2 in others:
		lines.append_array([other.position[axis], other.end[axis] + GAP])

	return lines


## The lines that the right or the bottom edge of a rect snaps to.
static func _high_lines(others: Array[Rect2], pane: Vector2, axis: int) -> Array[float]:
	var lines: Array[float] = [pane[axis] - EDGE_MARGIN]

	for other: Rect2 in others:
		lines.append_array([other.end[axis], other.position[axis] - GAP])

	return lines


## The lines that the centre of a rect snaps to.
static func _centre_lines(others: Array[Rect2], pane: Vector2, axis: int) -> Array[float]:
	var lines: Array[float] = [pane[axis] / 2.0]

	for other: Rect2 in others:
		lines.append(other.get_center()[axis])

	return lines


## The move that puts `value` on the nearest line within `distance`, or INF
## when no line is that near.
static func _nearest_delta(value: float, lines: Array[float], distance: float) -> float:
	var best := INF

	for line: float in lines:
		var delta := line - value

		if absf(delta) <= distance and absf(delta) < absf(best):
			best = delta

	return best


## The smaller of two moves. INF is no move.
static func _closer(first: float, second: float) -> float:
	return second if absf(second) < absf(first) else first


## A Vector2 from a Vector2 or a Vector2i, or null from anything else.
static func _vector(value: Variant) -> Variant:
	if typeof(value) == TYPE_VECTOR2:
		return value

	if typeof(value) == TYPE_VECTOR2I:
		return Vector2(value)

	return null


static func _is_number(value: Variant) -> bool:
	return typeof(value) == TYPE_FLOAT or typeof(value) == TYPE_INT


## Each axis of an anchor to the nearest of 0, 0.5 and 1.
static func _snap_anchor(anchor: Vector2) -> Vector2:
	var clamped := anchor.clamp(Vector2.ZERO, Vector2.ONE)

	return Vector2(snappedf(clamped.x, ANCHOR_STEP), snappedf(clamped.y, ANCHOR_STEP))
