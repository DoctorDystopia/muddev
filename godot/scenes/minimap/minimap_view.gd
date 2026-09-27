class_name MinimapView
extends Control
## The ground around you, drawn small, in the corner of the world pane.
##
## ## It is drawn from the chunks, not from the ASCII map
##
## DESIGN-0011 Phase 5 (Nick, 09/25/2026). The client already holds the
## chunks of the block around the player in [WorldState], for the 3D pane.
## This pane draws a window of tiles from the same [ChunkSet]:
##
##   - A walkable tile shows the colour of its floor type, from [FloorPalette],
##     the palette of the 3D ground. The two panes thus show one colour for
##     one floor.
##   - A blocked tile or a water tile shows that colour darker.
##   - The tile of the player has a mark, as before.
##
## It is still CLICKABLE, through the same [method WorldState.tile_action] that
## the 3D pane uses. A click on a far tile thus walks there, with no second
## copy of the rules.
##
## It draws no entities yet. The entity rows live in [EntityPool], in the 3D
## pane, and not in [WorldState]. The handoff lists that as a debt.
##
## ## A window, not the whole world
##
## A chunk is 64 x 64 tiles and the block is 3 x 3 chunks. That is too many
## tiles for a pane of 150 pixels. The pane draws the tiles within
## [constant WINDOW_RADIUS] of the player, and it moves with the player.

## Emitted with a whole command a telnet player could have typed. The server
## named it, or spelled its template. Same contract as a clicked tile in the
## 3D pane, because it is the same lookup.
signal command_requested(command: String)

const _Const := preload("res://autoload/blackout_constants.gd")

## The tiles on each side of the player that the pane draws.
const WINDOW_RADIUS := 20

## How much of a cell the drawn square fills. 1.0: on a window this dense, a
## gap between tiles is noise.
const CELL_FILL := 1.0

## Pixels of clear space inside the rectangle of the pane.
const PADDING := 6.0

## How much darker a tile that no one can stand on is drawn, from 0 to 1.
const UNWALKABLE_DARKEN := 0.55

const COLOR_BACKGROUND := Color(0.043, 0.059, 0.078, 0.82)
const COLOR_MARKER := Color(0.208, 0.878, 0.753)
const COLOR_HOVER := Color(1, 1, 1, 0.35)

const MARKER_WIDTH := 2.0

var _state: WorldState

## The cell under the cursor, and whether the cursor is over the pane.
## Vector2i has no null, and (0,0) is a real cell.
var _hover_cell := Vector2i.ZERO
var _hovering := false


func _init() -> void:
	# It is drawn OVER the 3D pane, so it has to take its own clicks -- STOP,
	# not PASS: a click that fell through would walk the player somewhere else
	# as well as here.
	mouse_filter = Control.MOUSE_FILTER_STOP
	custom_minimum_size = Vector2(150, 150)


## Bind to the world model and follow it.
##
## The model belongs to the CONSOLE, and the 3D pane draws the same instance.
## `meshes` is not read: nothing on this minimap is a mesh. The console
## passes it, and the argument stays so that the console needs no edit.
func bind(state: WorldState, _meshes: MeshResolver = null) -> void:
	_state = state
	_state.chunks_changed.connect(queue_redraw)
	_state.room_changed.connect(queue_redraw)

	queue_redraw()


# ─── Drawing ─────────────────────────────────────────────────────────────────

func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), COLOR_BACKGROUND)

	if _state == null or not _state.has_ground():
		return

	var cell_px := _cell_pixels()
	var origin := _origin(cell_px)
	var centre := _state.current_cell

	for dy: int in range(-WINDOW_RADIUS, WINDOW_RADIUS + 1):
		for dx: int in range(-WINDOW_RADIUS, WINDOW_RADIUS + 1):
			_draw_tile(centre + Vector2i(dx, dy), cell_px, origin)

	if _hovering:
		_draw_cell_outline(_hover_cell, cell_px, origin, COLOR_HOVER)

	_draw_cell_outline(centre, cell_px, origin, COLOR_MARKER)


func _draw_tile(tile: Vector2i, cell_px: float, origin: Vector2) -> void:
	var colour := tile_colour(_state.chunks, tile)

	if colour.a <= 0.0:
		return

	var square := Vector2.ONE * cell_px * CELL_FILL

	draw_rect(Rect2(_to_pixels(tile, cell_px, origin), square), colour)


## The colour of one tile on the minimap. Transparent when its chunk is not
## loaded, and on a void tile, which has no floor (Phase 7b). Static and
## public, so a test can check the rule with no scene.
static func tile_colour(chunks: ChunkSet, tile: Vector2i) -> Color:
	if not chunks.has_tile(tile):
		return Color(0, 0, 0, 0)

	var floor_name := chunks.get_floor(tile)

	if floor_name == _Const.TILE_VOID_FLOOR:
		return Color(0, 0, 0, 0)

	var colour := FloorPalette.color_of(floor_name)

	if chunks.get_flags(tile) & _Const.TILE_FLAGS_UNWALKABLE:
		colour = colour.darkened(UNWALKABLE_DARKEN)

	return colour


func _draw_cell_outline(cell: Vector2i, cell_px: float, origin: Vector2,
		colour: Color) -> void:
	var at := _to_pixels(cell, cell_px, origin)

	draw_rect(Rect2(at, Vector2.ONE * cell_px), colour, false, MARKER_WIDTH)


# ─── Geometry ────────────────────────────────────────────────────────────────

## The tiles along one side of the window.
static func window_side() -> int:
	return WINDOW_RADIUS * 2 + 1


func _cell_pixels() -> float:
	var room := size - Vector2.ONE * PADDING * 2.0
	var fit := minf(room.x, room.y) / float(window_side())

	return maxf(fit, 1.0)


## Where the top-left corner of the window sits, so the window is centred.
func _origin(cell_px: float) -> Vector2:
	var drawn := Vector2.ONE * float(window_side()) * cell_px

	return (size - drawn) * 0.5


## Cell -> the top-left pixel of its square.
##
## Y is FLIPPED. Grid Y grows to the north and screen Y grows down. The 3D
## pane makes the same flip with -Z.
func _to_pixels(cell: Vector2i, cell_px: float, origin: Vector2) -> Vector2:
	var low := _state.current_cell - Vector2i.ONE * WINDOW_RADIUS
	var high_y := _state.current_cell.y + WINDOW_RADIUS

	return origin + Vector2(float(cell.x - low.x) * cell_px,
		float(high_y - cell.y) * cell_px)


## The inverse: a point in the pane -> the cell under it.
##
## Returns a cell whether or not a chunk holds it. [method WorldState.tile_action]
## decides what a cell affords, and it answers "nothing" for one with no chunk.
func _to_cell(point: Vector2) -> Vector2i:
	if _state == null:
		return Vector2i.ZERO

	var cell_px := _cell_pixels()
	var local := (point - _origin(cell_px)) / cell_px
	var low_x := _state.current_cell.x - WINDOW_RADIUS
	var high_y := _state.current_cell.y + WINDOW_RADIUS

	return Vector2i(low_x + floori(local.x), high_y - floori(local.y))


# ─── Input ───────────────────────────────────────────────────────────────────

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_hover_at((event as InputEventMouseMotion).position)
		return

	if not (event is InputEventMouseButton):
		return

	var click := event as InputEventMouseButton

	if click.button_index != MOUSE_BUTTON_LEFT or not click.pressed:
		return

	_walk_to(_to_cell(click.position))
	accept_event()


func _notification(what: int) -> void:
	if what == NOTIFICATION_MOUSE_EXIT and _hovering:
		_hovering = false
		queue_redraw()


func _hover_at(point: Vector2) -> void:
	var cell := _to_cell(point)

	if _hovering and cell == _hover_cell:
		return

	_hover_cell = cell
	_hovering = true
	queue_redraw()


## Send whatever a click on this cell does. Nothing is composed or refused
## here: [method WorldState.tile_action] owns the answer.
func _walk_to(cell: Vector2i) -> void:
	if _state == null:
		return

	var action := _state.tile_action(cell)
	var command := str(action.get("command", ""))

	if command.is_empty():
		return

	command_requested.emit(command)
