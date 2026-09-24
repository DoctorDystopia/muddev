class_name ResizeGrips
extends RefCounted
## The grips that size a box: one on each free edge and one on each free
## corner. The pop-up and both docks use it.
##
## ## Why one class
##
## Until 09/22/2026 the pop-up had one grip, in its bottom-right corner, and
## each dock had its own copy of the grip code. The control panel draws over
## the pop-up, so a bank under the panel had no grip that the player could
## reach. Now the owner of a box names its free edges, and this class makes
## the grips, lays them out, and reports each drag.
##
## ## A raised grip draws over every other box
##
## A grip with `raised` set is a `top_level` Control. Godot draws a top-level
## item after every item that is not top-level, and the GUI picks it first. The
## pop-up raises its grips, so a dock over the pop-up cannot cover them. A
## dock does not raise its grips, because a raised grip also draws over the
## loading veil. The docks keep clear of each other instead. See
## [method PanelDock.keep_clear_of].
##
## ## A drag reports the whole offset
##
## [signal dragged] gives the offset from the press, not the last step. The
## owner applies it to the rect that it had at the press, through
## [method dragged_rect]. A drag past the smallest box thus leaves the box at
## that size, and the edge comes back only when the mouse does.
##
## ## Nothing here knows what the box holds
##
## The owner decides what a drag means: the pop-up moves an edge, and a dock
## changes its size and keeps its corner.
##
## Author: Nick Hobar
## Creation date: 09/22/2026

## Emitted when a left press starts a drag on a grip.
signal drag_started

## Emitted for each step of a drag, with the edges of the grip and the offset
## from the press, in the pixels of the box.
signal dragged(edges: int, offset: Vector2)

## The edges of a box, as bits. A corner is two edges.
const LEFT := 1
const TOP := 2
const RIGHT := 4
const BOTTOM := 8
const ALL_EDGES := LEFT | TOP | RIGHT | BOTTOM

## The single edges, and the corners, in the order the grips are made. The
## corners come last, so they draw over the ends of the edge grips and take
## the clicks there.
const EDGES: Array[int] = [LEFT, TOP, RIGHT, BOTTOM]
const CORNERS: Array[int] = [TOP | LEFT, TOP | RIGHT, BOTTOM | LEFT, BOTTOM | RIGHT]

## How thick an edge grip is, and how big a corner grip is, in pixels. Each
## grip straddles its edge, so half of it is over the box.
const THICKNESS := 6.0
const CORNER_SIZE := 16.0

## An idle grip, and a grip under the mouse or in a drag.
const IDLE_COLOR := Color(1, 1, 1, 0.35)
const HOT_COLOR := Color(1, 1, 1, 0.7)

## edges -> the grip Control.
var _grips := {}

## The edges of the grip in a drag, or 0.
var _drag_edges := 0

## The offset from the press, in the pixels of the box.
var _offset := Vector2.ZERO

## The grip under the mouse, or null. It draws in [constant HOT_COLOR].
var _hot: Control

## The box that the grips surround.
var _box: Control


## Make the grips for `free_edges` of `box`, and add them to `host`.
##
## A corner grip is made only when both of its edges are free. `raised` makes
## each grip `top_level`. See the class notes. The grips follow each move and
## each resize of the box, so the host never places them.
func _init(host: Control, box: Control, free_edges: int, raised: bool) -> void:
	_box = box

	for edges: int in EDGES + CORNERS:
		if edges & free_edges != edges:
			continue

		var grip := _build_grip(edges, raised)
		host.add_child(grip)
		_grips[edges] = grip

	box.item_rect_changed.connect(place)


## The rect that a drag of `edges` by `offset` gives to `rect`.
##
## Only the edges in the drag move. Each moved edge stops where the box would
## be smaller than `smallest`, or where it would leave `bounds`. The edges
## that do not move stay where they are, so a drag on the left edge never
## moves the right edge.
static func dragged_rect(rect: Rect2, edges: int, offset: Vector2,
		smallest: Vector2, bounds: Rect2) -> Rect2:
	var left := rect.position.x
	var top := rect.position.y
	var right := rect.end.x
	var bottom := rect.end.y

	if edges & LEFT:
		left = clampf(left + offset.x, bounds.position.x, right - smallest.x)

	if edges & RIGHT:
		right = clampf(right + offset.x, left + smallest.x, bounds.end.x)

	if edges & TOP:
		top = clampf(top + offset.y, bounds.position.y, bottom - smallest.y)

	if edges & BOTTOM:
		bottom = clampf(bottom + offset.y, top + smallest.y, bounds.end.y)

	return Rect2(left, top, right - left, bottom - top)


## Lay the grips along the box.
##
## In global pixels, so a raised grip and a plain grip take the same path.
## A top-level grip reads its position in the canvas, and so does a
## `global_position`.
func place() -> void:
	if not _box.is_inside_tree():
		return

	var rect := _box.get_global_rect()

	for edges: int in _grips:
		var grip: Control = _grips[edges]
		var grip_rect := _grip_rect(rect, edges)
		grip.global_position = grip_rect.position
		grip.size = grip_rect.size


## Show or hide every grip. A box whose size is not the player's has none.
func set_shown(shown: bool) -> void:
	for grip: Control in _grips.values():
		grip.visible = shown


## The grip for `edges`, or null when the box offers none there. For tests.
func grip(edges: int) -> Control:
	return _grips.get(edges, null)


## The edges and corners that have a grip. For tests.
func offered() -> Array:
	return _grips.keys()


## One whole drag of the grip of `edges`: a press, a move by `offset`, and a
## release. Public so a test can drag with no mouse.
##
## The mouse takes the same three steps, so the gesture and the test take one
## path.
func drag(edges: int, offset: Vector2) -> void:
	_start(edges)
	_move(offset)
	_drag_edges = 0


## The rect of one grip around a box rect.
##
## An edge grip runs the length of its edge. A corner grip is a square on the
## corner point.
static func _grip_rect(rect: Rect2, edges: int) -> Rect2:
	var half := THICKNESS / 2.0

	if edges == LEFT:
		return Rect2(rect.position.x - half, rect.position.y, THICKNESS, rect.size.y)

	if edges == RIGHT:
		return Rect2(rect.end.x - half, rect.position.y, THICKNESS, rect.size.y)

	if edges == TOP:
		return Rect2(rect.position.x, rect.position.y - half, rect.size.x, THICKNESS)

	if edges == BOTTOM:
		return Rect2(rect.position.x, rect.end.y - half, rect.size.x, THICKNESS)

	var x := rect.end.x if edges & RIGHT else rect.position.x
	var y := rect.end.y if edges & BOTTOM else rect.position.y
	var corner := Vector2.ONE * CORNER_SIZE

	return Rect2(Vector2(x, y) - corner / 2.0, corner)


## The cursor for one grip: a two-way arrow along the drag.
static func _cursor_for(edges: int) -> Control.CursorShape:
	if edges == LEFT or edges == RIGHT:
		return Control.CURSOR_HSIZE

	if edges == TOP or edges == BOTTOM:
		return Control.CURSOR_VSIZE

	# The "\" diagonal joins the top-left and the bottom-right corners.
	if edges == TOP | LEFT or edges == BOTTOM | RIGHT:
		return Control.CURSOR_FDIAGSIZE

	return Control.CURSOR_BDIAGSIZE


func _build_grip(edges: int, raised: bool) -> Control:
	var grip := Control.new()
	grip.top_level = raised
	grip.mouse_filter = Control.MOUSE_FILTER_STOP
	grip.mouse_default_cursor_shape = _cursor_for(edges)
	grip.gui_input.connect(_follow_drag.bind(grip, edges))
	grip.mouse_entered.connect(_set_hot.bind(grip))
	grip.mouse_exited.connect(_set_hot.bind(null))
	grip.draw.connect(_draw_grip.bind(grip, edges))

	return grip


## An edge grip is a plain bar. Visible on purpose: an edge that can be
## dragged and does not say so is an edge nobody drags.
##
## A corner grip draws only while it is hot. The two edge bars already meet
## under it.
func _draw_grip(grip: Control, edges: int) -> void:
	var hot := grip == _hot or edges == _drag_edges

	if edges in CORNERS and not hot:
		return

	grip.draw_rect(Rect2(Vector2.ZERO, grip.size), HOT_COLOR if hot else IDLE_COLOR)


func _set_hot(grip: Control) -> void:
	var was := _hot
	_hot = grip

	for item: Control in [was, grip]:
		if item != null:
			item.queue_redraw()


## A left press starts the drag, motion adds to the offset, and the release
## ends it.
##
## The control that took the press keeps the motion until the release, so the
## drag follows the mouse off the grip. The motion is in the pixels of the
## grip, which are the pixels of the box: `gui_input` applies the UI scale.
func _follow_drag(event: InputEvent, grip: Control, edges: int) -> void:
	if event is InputEventMouseButton:
		var click := event as InputEventMouseButton

		if click.button_index == MOUSE_BUTTON_LEFT:
			if click.pressed:
				_start(edges)
			else:
				_drag_edges = 0

			grip.queue_redraw()
			grip.accept_event()

		return

	if not (event is InputEventMouseMotion) or _drag_edges != edges:
		return

	var motion := (event as InputEventMouseMotion).relative
	_move(_offset + motion)
	grip.accept_event()


func _start(edges: int) -> void:
	_drag_edges = edges
	_offset = Vector2.ZERO
	drag_started.emit()


func _move(offset: Vector2) -> void:
	_offset = offset
	dragged.emit(_drag_edges, _offset)
