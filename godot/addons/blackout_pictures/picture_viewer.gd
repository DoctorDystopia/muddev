@tool
class_name PictureViewer
extends Control
## The view of the picture editor: one item picture, large, with its guides.
##
## The view draws the rectangle of the item in the render target of
## [ItemStage], with no filter. Thus, each pixel of the picture shows as one
## square, and the author sees the edge of the item as the stage made it.
##
## ## The guides
##
## - The frame is the edge of the cell.
## - The inner frame is the square that a zoom of 100% fills.
## - The cross is the middle of the cell.
## - The grid divides the cell into [constant GRID_CELLS] parts a side.
##
## ## The mouse
##
## A drag with the left button moves the picture. A drag with the right
## button turns it. The wheel changes the zoom. The view only sends the
## gesture. [PictureEditor] makes the new pose, so the fields and the mouse
## change one row.

## Emitted for a drag with the left button, in shares of the cell. A
## positive y is up.
signal offset_dragged(shares: Vector2)

## Emitted for a drag with the right button, in degrees: x is the turn
## about the X axis, and y is the turn about the vertical.
signal turn_dragged(degrees: Vector2)

## Emitted for each step of the wheel: +1 away from the author, -1 to them.
signal zoom_stepped(steps: int)

## The least side of the view, in pixels.
const MIN_SIDE := 256.0

## The pixels between the edge of the view and the picture.
const MARGIN := 12.0

## The degrees of turn for each pixel of a drag.
const TURN_PER_PIXEL := 0.5

## How many parts a side the grid divides the cell into.
const GRID_CELLS := 8

const DEFAULT_BACKGROUND := Color(0.1, 0.11, 0.13)
const FRAME_COLOR := Color(1.0, 1.0, 1.0, 0.7)
const FILL_COLOR := Color(0.35, 0.8, 1.0, 0.6)
const GRID_COLOR := Color(1.0, 1.0, 1.0, 0.12)
const CROSS_COLOR := Color(1.0, 0.85, 0.3, 0.6)

const LINE_WIDTH := 1.0

var _texture: Texture2D
var _guides := true
var _background := DEFAULT_BACKGROUND

## The share of the cell that a zoom of 100% fills.
var _fill := 1.0


func _init() -> void:
	custom_minimum_size = Vector2(MIN_SIDE, MIN_SIDE)
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	clip_contents = true


## Show a picture, or nothing for null.
func show_picture(texture: Texture2D) -> void:
	_texture = texture
	queue_redraw()


## The picture that the view shows, or null.
func picture() -> Texture2D:
	return _texture


## Show or hide the guides.
func set_guides(on: bool) -> void:
	_guides = on
	queue_redraw()


## The colour behind the picture.
func set_background(color: Color) -> void:
	_background = color
	queue_redraw()


## The share of the cell that a zoom of 100% fills, for the inner frame.
func set_fill(share: float) -> void:
	_fill = share
	queue_redraw()


## The square of the cell in the view: the largest square that fits, in the
## middle.
func picture_rect() -> Rect2:
	var side := maxf(minf(size.x, size.y) - (MARGIN * 2.0), 0.0)

	return Rect2((size - (Vector2.ONE * side)) * 0.5, Vector2.ONE * side)


func _draw() -> void:
	var cell := picture_rect()

	draw_rect(Rect2(Vector2.ZERO, size), _background)

	if _texture != null:
		draw_texture_rect(_texture, cell, false)

	if _guides:
		_draw_guides(cell)


func _gui_input(event: InputEvent) -> void:
	var motion := event as InputEventMouseMotion
	var button := event as InputEventMouseButton
	var side := picture_rect().size.x

	if motion != null and side > 0.0:
		if motion.button_mask & MOUSE_BUTTON_MASK_LEFT:
			offset_dragged.emit(Vector2(motion.relative.x, -motion.relative.y) / side)
			accept_event()
		elif motion.button_mask & MOUSE_BUTTON_MASK_RIGHT:
			turn_dragged.emit(Vector2(motion.relative.y, motion.relative.x) * TURN_PER_PIXEL)
			accept_event()

	if button != null and button.pressed:
		if button.button_index == MOUSE_BUTTON_WHEEL_UP:
			zoom_stepped.emit(1)
			accept_event()
		elif button.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			zoom_stepped.emit(-1)
			accept_event()


# ─── Private ────────────────────────────────────────────────────────────────

func _draw_guides(cell: Rect2) -> void:
	var step := cell.size.x / float(GRID_CELLS)

	for line in range(1, GRID_CELLS):
		var along := float(line) * step

		draw_line(cell.position + Vector2(along, 0.0),
			cell.position + Vector2(along, cell.size.y), GRID_COLOR, LINE_WIDTH)
		draw_line(cell.position + Vector2(0.0, along),
			cell.position + Vector2(cell.size.x, along), GRID_COLOR, LINE_WIDTH)

	var middle := cell.get_center()

	draw_line(Vector2(middle.x, cell.position.y), Vector2(middle.x, cell.end.y), CROSS_COLOR,
		LINE_WIDTH)
	draw_line(Vector2(cell.position.x, middle.y), Vector2(cell.end.x, middle.y), CROSS_COLOR,
		LINE_WIDTH)
	draw_rect(cell.grow(-cell.size.x * (1.0 - _fill) * 0.5), FILL_COLOR, false, LINE_WIDTH)
	draw_rect(cell, FRAME_COLOR, false, LINE_WIDTH)
