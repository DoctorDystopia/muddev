class_name MinimapView
extends Control
## The map you are standing on, drawn small, in the corner of the world pane.
##
## ## It is drawn from the FEED, not from the ASCII map
##
## The notes this came from described the minimap as "the XYMap print we are
## currently getting, just moved to its own pane". Routing that text here would
## have been almost free -- one more chat tab -- and it was the wrong trade.
## `blackout_map` already carries every node with its `room_kind` and every
## link, `room_info` already carries the observer's coordinates, and
## [WorldState] already reassembles both for the 3D pane. Drawing from the same
## model gives three things the text cannot:
##
##   - It scales with `content_scale_factor`, where a monospace block cannot.
##   - It is CLICKABLE, and by the same [method WorldState.tile_action] the 3D
##     pane uses -- so click-to-walk works here with no new server contract and
##     no second copy of the rules.
##   - It lets the server stop sending the ASCII map to this client entirely,
##     which is the single largest reduction in text-pane noise available: the
##     map was re-`msg`ed on every `look`, and `look` runs on every step.
##
## ## It draws only the level you are on
##
## The 3D pane lays every island out along world X because it can afford the
## space. A minimap that did the same would be mostly empty desert at a scale
## nobody can read. `Z` is a map NAME, so "the current island" is the honest
## unit here, and `goto` does not cross maps anyway.
##
## ## Colours are [MapPalette]'s
##
## The same tables the 3D pane draws with, so the two panes cannot disagree
## about what a Bank looks like. They moved out of `world_view.gd` for exactly
## this reason.
##
## That includes WHICH of the two palettes applies. A map whose ground is drawn
## as art colours only the room kinds somebody chose a colour for and leaves the
## rest neutral, and this pane follows it -- both because a minimap disagreeing
## with the map beside it is the failure above, and because it is the better
## minimap on its own terms: a field of hashed hues is a field in which the bank
## does not stand out. [method MapPalette.is_surfaced] owns the question, and it
## is asked of the CONSOLE's resolver, so both panes get one answer.

## Emitted with a whole command a telnet player could have typed.
##
## The server named it -- this pane substitutes nothing into it. Same contract
## as a clicked tile in the 3D pane, because it is literally the same lookup.
signal command_requested(command: String)

## How much of a cell the drawn square fills. Below 1.0 so the grid reads as
## tiles with gaps rather than as a solid block of colour.
const CELL_FILL := 0.78

## Pixels of clear space inside the pane's own rectangle.
const PADDING := 6.0

## Bounds on how big a cell may be drawn, in pixels.
##
## A floor because a map is unreadable below a couple of pixels a tile, and a
## ceiling because a two-room map would otherwise draw two enormous squares.
const MIN_CELL_PIXELS := 3.0
const MAX_CELL_PIXELS := 14.0

const COLOR_BACKGROUND := Color(0.043, 0.059, 0.078, 0.82)
const COLOR_LINK := Color("2e4256")
const COLOR_MARKER := Color(0.208, 0.878, 0.753)
const COLOR_HOVER := Color(1, 1, 1, 0.35)

const LINK_WIDTH := 1.5
const MARKER_WIDTH := 2.0

## Shown when no map has arrived yet.
const NO_MAP_TEXT := "no map"

var _state: WorldState

## Where art comes from, bound by the console. Read for ONE question -- whether
## this map's ground is drawn as art -- and never to draw anything: nothing on a
## minimap is a mesh.
var _meshes: MeshResolver

## The cell under the cursor, or a sentinel when the cursor is elsewhere.
## Vector2i has no null, and (0,0) is a real cell on every map.
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
## The model is the CONSOLE's, and is the same instance the 3D pane draws. A
## second WorldState would mean two chunk reassemblies of one map and, on a
## resync, two of them briefly disagreeing -- which is the reason the console
## owns `_char`, `_items` and `_summary` too.
##
## `meshes` is the console's resolver, the same instance the 3D pane and the
## inventory were given, for the same reason the state is shared: a second one
## would mean a second manifest fetch and two panes that could answer
## [method MapPalette.is_surfaced] differently about one map.
##
## The redraw on `manifest_ready` is what makes that answer land. Until the
## manifest arrives no key can have art, so a surfaced map would otherwise draw
## once in the bare palette and stay that way for the session.
func bind(state: WorldState, meshes: MeshResolver) -> void:
	_state = state
	_state.map_ready.connect(_on_map_ready)
	_state.room_changed.connect(queue_redraw)

	_meshes = meshes

	if _meshes != null:
		_meshes.manifest_ready.connect(_on_manifest_ready)

	queue_redraw()


func _on_manifest_ready(_count: int) -> void:
	queue_redraw()


func _on_map_ready(_z: String) -> void:
	queue_redraw()


# ─── Drawing ─────────────────────────────────────────────────────────────────

func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), COLOR_BACKGROUND)

	var level := _level()

	if level == null or level.cells.is_empty():
		return

	var bounds := _bounds(level)
	var cell_px := _cell_pixels(bounds)
	var origin := _origin(bounds, cell_px)

	_draw_links(level, bounds, cell_px, origin)
	_draw_cells(level, bounds, cell_px, origin)

	if _hovering:
		_draw_cell_outline(_hover_cell, bounds, cell_px, origin, COLOR_HOVER)

	_draw_cell_outline(
		_state.current_cell, bounds, cell_px, origin, COLOR_MARKER)


func _draw_cells(level: WorldState.Level, bounds: Rect2i, cell_px: float,
		origin: Vector2) -> void:
	var square := Vector2.ONE * cell_px * CELL_FILL
	var inset := (cell_px - square.x) * 0.5

	# Once per redraw, not once per cell: which palette applies is a property of
	# the island, and every cell being drawn belongs to the same one.
	var surfaced := MapPalette.is_surfaced(_state.current_z, _meshes)

	for index: int in level.cells.size():
		var at := _to_pixels(level.cells[index], bounds, cell_px, origin)

		draw_rect(Rect2(at + Vector2.ONE * inset, square),
			MapPalette.tile_colour(level.kinds[index], surfaced))


func _draw_links(level: WorldState.Level, bounds: Rect2i, cell_px: float,
		origin: Vector2) -> void:
	var centre := Vector2.ONE * cell_px * 0.5

	for link: Array in level.links:
		var from := _to_pixels(link[0], bounds, cell_px, origin) + centre
		var to := _to_pixels(link[1], bounds, cell_px, origin) + centre

		draw_line(from, to, COLOR_LINK, LINK_WIDTH)


func _draw_cell_outline(cell: Vector2i, bounds: Rect2i, cell_px: float,
		origin: Vector2, colour: Color) -> void:
	var at := _to_pixels(cell, bounds, cell_px, origin)

	draw_rect(Rect2(at, Vector2.ONE * cell_px), colour, false, MARKER_WIDTH)


# ─── Geometry ────────────────────────────────────────────────────────────────

## The level the observer is standing on, or null.
func _level() -> WorldState.Level:
	if _state == null or not _state.levels.has(_state.current_z):
		return null

	return _state.levels[_state.current_z]


## The cell-space rectangle a level occupies.
##
## Read from the cells rather than assumed to start at the origin: a map's
## coordinates are the xygrid's, and nothing promises they begin at (0,0).
func _bounds(level: WorldState.Level) -> Rect2i:
	var low := level.cells[0]
	var high := level.cells[0]

	for cell: Vector2i in level.cells:
		low = Vector2i(mini(low.x, cell.x), mini(low.y, cell.y))
		high = Vector2i(maxi(high.x, cell.x), maxi(high.y, cell.y))

	return Rect2i(low, high - low)


func _cell_pixels(bounds: Rect2i) -> float:
	var across := float(bounds.size.x + 1)
	var down := float(bounds.size.y + 1)
	var room := size - Vector2.ONE * PADDING * 2.0
	var fit := minf(room.x / across, room.y / down)

	return clampf(fit, MIN_CELL_PIXELS, MAX_CELL_PIXELS)


## Where the grid's top-left corner sits, so the map is centred in the pane.
func _origin(bounds: Rect2i, cell_px: float) -> Vector2:
	var drawn := Vector2(
		float(bounds.size.x + 1) * cell_px, float(bounds.size.y + 1) * cell_px)

	return (size - drawn) * 0.5


## Cell -> the top-left pixel of its square.
##
## Y is FLIPPED. Grid Y grows northward and screen Y grows downward, so a map
## drawn without the flip reads upside down against both the 3D pane and the
## text one. `world_view._tile_position` makes the same correction with `-z`.
func _to_pixels(cell: Vector2i, bounds: Rect2i, cell_px: float,
		origin: Vector2) -> Vector2:
	return origin + Vector2(
		float(cell.x - bounds.position.x) * cell_px,
		float(bounds.position.y + bounds.size.y - cell.y) * cell_px)


## The inverse: a point in the pane -> the cell under it.
##
## Returns a cell whether or not the map has a node there. Deciding what an
## empty cell affords is [method WorldState.tile_action]'s job, and it already
## answers "nothing" for one -- a second opinion here would be a second owner.
func _to_cell(point: Vector2) -> Vector2i:
	var level := _level()

	if level == null or level.cells.is_empty():
		return Vector2i.ZERO

	var bounds := _bounds(level)
	var cell_px := _cell_pixels(bounds)
	var origin := _origin(bounds, cell_px)
	var local := (point - origin) / cell_px

	return Vector2i(
		bounds.position.x + floori(local.x),
		bounds.position.y + bounds.size.y - floori(local.y))


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


## Send whatever the server said a click on this cell does.
##
## Nothing is composed here and nothing is refused here. An empty action is the
## server declining -- see [method WorldState.tile_action], which documents why
## the client no longer has an opinion about which tiles are reachable.
func _walk_to(cell: Vector2i) -> void:
	if _state == null:
		return

	var action := _state.tile_action(cell)
	var command := str(action.get("command", ""))

	if command.is_empty():
		return

	command_requested.emit(command)
