class_name MinimapView
extends Control
## The ground around you, drawn small, in the corner of the world pane.
##
## ## It is drawn from the chunks, not from the ASCII map
##
## DESIGN-0011 Phase 5 (Nick, 09/25/2026). The client already holds the
## chunks of the block around the player in [WorldState], for the 3D pane.
## This pane draws a window of tiles from the same [ChunkSet]. [MapRaster]
## owns the colour of a tile, and the world map uses the same rule. The pane
## draws each chunk as one image, built one time when the chunk arrives.
##
## It is still CLICKABLE, through the same [method WorldState.tile_action] that
## the 3D pane uses. A click on a far tile thus walks there, with no second
## copy of the rules.
##
## ## What it draws (09/28/2026, the OSRS minimap)
##
##   - The tile of the player: a white square.
##   - A map dot for each entity that [EntityRoster] holds: white for another
##     player, yellow for an NPC, red for an item on the ground.
##     [constant DOT_COLOURS] is the table. A kind with no row draws no dot.
##   - A map icon for each chunk object in the window, through [MapIcons]: a
##     bank, a node, a transition, a ladder.
##   - The destination marker: a red flag on the goal tile of the walk.
##   - The walk path, when the player turns it on in Options. Nick removed
##     the button on the pane to keep the corner clear (09/28/2026).
##
## The feed sends entities within `STATEFEED_ENTITY_RADIUS` (10 tiles) only.
## At a wider zoom, no dot shows past that ring. The map icons come from the
## chunks, so they show everywhere.
##
## ## A window, not the whole world
##
## A chunk is 64 x 64 tiles and the block is 3 x 3 chunks. The pane draws the
## tiles within [method radius] of the player, and it moves with the player.
## The zoom picks the radius from [constant ZOOM_RADII]. The widest step stays
## inside the block, which reaches at least 64 tiles past the player.
##
## ## The strip
##
## A row of buttons sits under the map: zoom out, zoom in, and the world map.
## The map is the square above the strip.
##
## ## The Run button
##
## A toggle in the top-left corner of the map square, as the run orb of OSRS
## sits by its minimap. It is not on the strip, which stays at three buttons
## (Nick, 09/28/2026). The walk feed says whether run is on, and the button
## shows that. A press sends the run command and puts the button back to the
## server fact until the feed answers.

## Emitted with a whole command a telnet player could have typed. The server
## named it, or spelled its template. Same contract as a clicked tile in the
## 3D pane, because it is the same lookup.
signal command_requested(command: String)

## Emitted when the player presses the world map button. The console opens
## the world map.
signal world_map_requested

const _Const := preload("res://autoload/blackout_constants.gd")

## The zoom steps: the tiles on each side of the player, widest last.
const ZOOM_RADII: Array[int] = [8, 12, 16, 20, 28, 40]

## Pixels of clear space inside the rectangle of the pane.
const PADDING := 6.0

## The height of the button strip under the map, in pixels. The theme gives a
## button 31 pixels.
const STRIP_HEIGHT := 32.0

## Entity kind -> the colour of its map dot. Keyed by the generated names, so
## this table cannot name a kind that does not exist. A look, for Nick to tune.
const DOT_COLOURS := {
	_Const.FAMILY_CHARACTER: Color(0.96, 0.96, 0.96),
	_Const.FAMILY_NPC: Color(1.0, 0.86, 0.2),
	_Const.FAMILY_ITEM: Color(0.93, 0.22, 0.2),
}

## The order of the dots, lowest first, so a player is never under an item.
const DOT_ORDER: Array[String] = [
	_Const.FAMILY_ITEM, _Const.FAMILY_NPC, _Const.FAMILY_CHARACTER]

const COLOR_BACKGROUND := Color(0.043, 0.059, 0.078, 0.82)
const COLOR_MARKER := Color(0.208, 0.878, 0.753)
const COLOR_SELF := Color(1, 1, 1)
const COLOR_HOVER := Color(1, 1, 1, 0.35)
const COLOR_FLAG := Color(0.93, 0.16, 0.16)
const COLOR_FLAG_POLE := Color(0.95, 0.95, 0.95)
const COLOR_PATH := Color(1.0, 0.95, 0.55, 0.75)
const COLOR_DOT_OUTLINE := Color(0, 0, 0, 0.8)

const MARKER_WIDTH := 2.0
const PATH_WIDTH := 2.0

## The size of a dot and of an icon, as a part of a cell, and their limits in
## pixels. A dot stays visible at the widest zoom and small at the closest.
const DOT_SHARE := 0.4
const DOT_MIN_PX := 2.0
const DOT_MAX_PX := 4.0
const ICON_SHARE := 1.4
const ICON_MIN_PX := 5.0
const ICON_MAX_PX := 10.0

var _state: WorldState
var _roster: EntityRoster
var _settings: ClientSettings

## The zoom step in use. Without settings, the shipped default.
var _radius := ClientSettings.DEFAULT_MINIMAP_RADIUS

## Whether the walk path is drawn. Without settings, the shipped default.
var _show_path := ClientSettings.DEFAULT_SHOW_WALK_PATH

## ChunkFile -> the ImageTexture of its ground. See [method _texture_of].
var _chunk_textures := {}

## The cell under the cursor, and whether the cursor is over the map.
## Vector2i has no null, and (0,0) is a real cell.
var _hover_cell := Vector2i.ZERO
var _hovering := false

var _zoom_out_button: Button
var _zoom_in_button: Button
var _world_map_button: Button
var _run_button: Button


func _init() -> void:
	# It is drawn OVER the 3D pane, so it has to take its own clicks -- STOP,
	# not PASS: a click that fell through would walk the player somewhere else
	# as well as here.
	mouse_filter = Control.MOUSE_FILTER_STOP
	custom_minimum_size = Vector2(150, 150 + STRIP_HEIGHT)

	# One pixel of a chunk image is one tile. A blur would smear the tiles.
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST

	_build_strip()


## Bind to the world model and follow it.
##
## The model belongs to the CONSOLE, and the 3D pane draws the same instance.
## `meshes` is not read: nothing on this minimap is a mesh. The console
## passes it, and the argument stays so that the console needs no edit.
func bind(state: WorldState, _meshes: MeshResolver = null) -> void:
	_state = state
	_state.chunks_changed.connect(_on_chunks_changed)
	_state.chunks_changed.connect(queue_redraw)
	_state.room_changed.connect(queue_redraw)
	_state.walk_changed.connect(queue_redraw)
	_state.walk_changed.connect(_sync_run_button)

	_sync_run_button()
	queue_redraw()


## Draw a map dot for each entity of the roster. The console owns the roster,
## and the 3D pane draws the same one.
func bind_entities(roster: EntityRoster) -> void:
	_roster = roster
	_roster.changed.connect(queue_redraw)

	queue_redraw()


## Read the zoom and the path toggle from the settings, and write them back
## when the player uses the buttons.
func bind_settings(settings: ClientSettings) -> void:
	_settings = settings
	_settings.changed.connect(_apply_settings)
	_apply_settings()


func _apply_settings() -> void:
	_radius = nearest_zoom(_settings.minimap_radius)
	_show_path = _settings.show_walk_path
	_sync_zoom_buttons()
	queue_redraw()


# ─── The strip ───────────────────────────────────────────────────────────────

func _build_strip() -> void:
	var strip := HBoxContainer.new()

	strip.name = "Strip"
	strip.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	strip.offset_top = -STRIP_HEIGHT

	# A larger font makes the buttons taller. The strip then grows up over
	# the map, not down past the pane.
	strip.grow_vertical = Control.GROW_DIRECTION_BEGIN
	strip.alignment = BoxContainer.ALIGNMENT_CENTER
	strip.mouse_filter = Control.MOUSE_FILTER_PASS
	add_child(strip)

	_zoom_out_button = _strip_button(strip, "-", "Zoom out")
	_zoom_out_button.pressed.connect(zoom_out)
	_zoom_in_button = _strip_button(strip, "+", "Zoom in")
	_zoom_in_button.pressed.connect(zoom_in)

	_world_map_button = _strip_button(strip, "Map", "Open the world map")
	_world_map_button.pressed.connect(world_map_requested.emit)

	_sync_zoom_buttons()
	_build_run_button()


func _strip_button(strip: HBoxContainer, text: String,
		tip: String) -> Button:
	var button := Button.new()

	button.text = text
	button.tooltip_text = tip
	button.focus_mode = Control.FOCUS_NONE
	strip.add_child(button)

	return button


# ─── Run ─────────────────────────────────────────────────────────────────────

func _build_run_button() -> void:
	_run_button = Button.new()
	_run_button.name = "Run"
	_run_button.text = "Run"
	_run_button.tooltip_text = "Run: two tiles each tick (R)"
	_run_button.toggle_mode = true
	_run_button.focus_mode = Control.FOCUS_NONE
	_run_button.position = Vector2(PADDING, PADDING)
	_run_button.pressed.connect(_on_run_pressed)
	add_child(_run_button)


## Ask the server to turn run the other way. The button shows the server fact
## again at once, and the walk feed moves it when the change is real.
func _on_run_pressed() -> void:
	command_requested.emit(_Const.RUN_TOGGLE_COMMAND)
	_sync_run_button()


## Show whether run is on, from the walk feed.
func _sync_run_button() -> void:
	var running := _state != null and _state.running

	_run_button.set_pressed_no_signal(running)


## True while the Run button shows run on.
func run_shown() -> bool:
	return _run_button.button_pressed


# ─── Zoom ────────────────────────────────────────────────────────────────────

## The tiles on each side of the player that the pane draws now.
func radius() -> int:
	return _radius


## The zoom step nearest to a radius. A radius between two steps takes the
## closer one, and a tie takes the smaller.
static func nearest_zoom(value: int) -> int:
	var best := ZOOM_RADII[0]

	for step: int in ZOOM_RADII:
		if absi(step - value) < absi(best - value):
			best = step

	return best


## Show fewer tiles, bigger. Nothing at the closest step.
func zoom_in() -> void:
	_set_zoom_index(ZOOM_RADII.find(_radius) - 1)


## Show more tiles, smaller. Nothing at the widest step.
func zoom_out() -> void:
	_set_zoom_index(ZOOM_RADII.find(_radius) + 1)


func _set_zoom_index(index: int) -> void:
	var clamped := clampi(index, 0, ZOOM_RADII.size() - 1)
	var chosen := ZOOM_RADII[clamped]

	if chosen == _radius:
		return

	_radius = chosen
	_sync_zoom_buttons()

	if _settings != null:
		_settings.set_minimap_radius(chosen)

	queue_redraw()


func _sync_zoom_buttons() -> void:
	_zoom_in_button.disabled = _radius == ZOOM_RADII[0]
	_zoom_out_button.disabled = _radius == ZOOM_RADII[ZOOM_RADII.size() - 1]


# ─── Drawing ─────────────────────────────────────────────────────────────────

func _draw() -> void:
	var cell_px := _cell_pixels()
	var origin := _origin(cell_px)
	var side := float(window_side()) * cell_px

	draw_rect(Rect2(origin, Vector2(side, side)), COLOR_BACKGROUND)

	if _state == null or not _state.has_ground():
		return

	_draw_ground(cell_px, origin)
	_draw_icons(cell_px, origin)

	if _show_path:
		_draw_walk_path(cell_px, origin)

	_draw_dots(cell_px, origin)

	if _hovering:
		_draw_cell_outline(_hover_cell, cell_px, origin, COLOR_HOVER)

	_draw_self(cell_px, origin)
	_draw_flag(cell_px, origin)


## Draw the part of each chunk image that the window covers.
func _draw_ground(cell_px: float, origin: Vector2) -> void:
	var chunk_size: int = _Const.CHUNK_SIZE
	var low := _window_low()
	var high := low + Vector2i.ONE * (window_side() - 1)
	var first := ChunkSet.chunk_of_tile(low)
	var last := ChunkSet.chunk_of_tile(high)

	for cy: int in range(first.y, last.y + 1):
		for cx: int in range(first.x, last.x + 1):
			var coord := Vector2i(cx, cy)
			var chunk := _state.chunks.get_chunk(coord)

			if chunk == null:
				continue

			var chunk_low := coord * chunk_size
			var from := Vector2i(maxi(low.x, chunk_low.x), maxi(low.y, chunk_low.y))
			var to := Vector2i(mini(high.x, chunk_low.x + chunk_size - 1),
				mini(high.y, chunk_low.y + chunk_size - 1))
			var tiles := to - from + Vector2i.ONE

			# Image row 0 is the north row of the chunk.
			var source := Rect2(float(from.x - chunk_low.x),
				float(chunk_size - 1 - (to.y - chunk_low.y)),
				float(tiles.x), float(tiles.y))
			var target := Rect2(_to_pixels(Vector2i(from.x, to.y), cell_px, origin),
				Vector2(tiles) * cell_px)

			draw_texture_rect_region(_texture_of(chunk), target, source)


## The ground texture of one chunk, built on the first use.
func _texture_of(chunk: ChunkFile) -> ImageTexture:
	if not _chunk_textures.has(chunk):
		_chunk_textures[chunk] = ImageTexture.create_from_image(
			MapRaster.chunk_image(chunk))

	return _chunk_textures[chunk]


## Drop the texture of each chunk that the model no longer holds, so a chunk
## that the server sends again gets a new image.
func _on_chunks_changed() -> void:
	for chunk: ChunkFile in _chunk_textures.keys():
		if _state.chunks.get_chunk(Vector2i(chunk.cx, chunk.cy)) != chunk:
			_chunk_textures.erase(chunk)


func _draw_icons(cell_px: float, origin: Vector2) -> void:
	var chunk_size: int = _Const.CHUNK_SIZE
	var icon_px := clampf(cell_px * ICON_SHARE, ICON_MIN_PX, ICON_MAX_PX)

	for coord: Vector2i in _state.chunks.chunk_coords():
		var chunk := _state.chunks.get_chunk(coord)

		for placed: Dictionary in chunk.objects:
			var tile := coord * chunk_size + Vector2i(int(placed["x"]), int(placed["y"]))

			if not _in_window(tile):
				continue

			var category := MapIcons.category_of(str(placed["kind"]))

			MapIcons.draw(self, category, _centre_of(tile, cell_px, origin), icon_px)


func _draw_dots(cell_px: float, origin: Vector2) -> void:
	if _roster == null:
		return

	var dot_px := clampf(cell_px * DOT_SHARE, DOT_MIN_PX, DOT_MAX_PX)

	for kind: String in DOT_ORDER:
		for tile: Vector2i in dot_tiles(kind):
			var centre := _centre_of(tile, cell_px, origin)

			draw_circle(centre, dot_px + 1.0, COLOR_DOT_OUTLINE)
			draw_circle(centre, dot_px, DOT_COLOURS[kind])


## The tiles of every entity of one kind that the window shows, on the plane
## of the player. Public, so a test can check the dots with no canvas.
func dot_tiles(kind: String) -> Array[Vector2i]:
	var tiles: Array[Vector2i] = []

	if _roster == null or _state == null:
		return tiles

	for entity: Dictionary in _roster.rows():
		if str(entity.get("kind", "")) != kind:
			continue

		if EntityRoster.z_of(entity) != _state.current_z:
			continue

		var tile: Variant = EntityRoster.tile_of(entity)

		if tile != null and _in_window(tile):
			tiles.append(tile)

	return tiles


func _draw_self(cell_px: float, origin: Vector2) -> void:
	var at := _to_pixels(_state.current_cell, cell_px, origin)
	var inset := cell_px * 0.2

	draw_rect(Rect2(at + Vector2.ONE * inset, Vector2.ONE * (cell_px - inset * 2.0)),
		COLOR_SELF)
	_draw_cell_outline(_state.current_cell, cell_px, origin, COLOR_MARKER)


## The destination marker: a flag on a pole, standing on the goal tile.
func _draw_flag(cell_px: float, origin: Vector2) -> void:
	if not _state.walk_on_current_plane() or not _in_window(_state.walk_goal):
		return

	var foot := _centre_of(_state.walk_goal, cell_px, origin)
	var height := clampf(cell_px * 2.0, 8.0, 14.0)
	var top := foot - Vector2(0, height)
	var cloth := PackedVector2Array([top, top + Vector2(height * 0.7, height * 0.2),
		top + Vector2(0, height * 0.45)])

	draw_line(foot, top, COLOR_FLAG_POLE, 1.5)
	draw_colored_polygon(cloth, COLOR_FLAG)


## The walk path: a line from the player through each tile still to walk.
## Only the segments with both ends in the window are drawn.
func _draw_walk_path(cell_px: float, origin: Vector2) -> void:
	if not _state.walk_on_current_plane():
		return

	var previous := _state.current_cell

	for tile: Vector2i in _state.walk_path:
		if _in_window(previous) and _in_window(tile):
			draw_line(_centre_of(previous, cell_px, origin),
				_centre_of(tile, cell_px, origin), COLOR_PATH, PATH_WIDTH)

		previous = tile


func _draw_cell_outline(cell: Vector2i, cell_px: float, origin: Vector2,
		colour: Color) -> void:
	var at := _to_pixels(cell, cell_px, origin)

	draw_rect(Rect2(at, Vector2.ONE * cell_px), colour, false, MARKER_WIDTH)


# ─── Geometry ────────────────────────────────────────────────────────────────

## The tiles along one side of the window.
func window_side() -> int:
	return _radius * 2 + 1


## The square of the pane that holds the map: everything above the strip.
func map_rect() -> Rect2:
	return Rect2(Vector2.ZERO, Vector2(size.x, maxf(size.y - STRIP_HEIGHT, 0.0)))


func _cell_pixels() -> float:
	var room := map_rect().size - Vector2.ONE * PADDING * 2.0
	var fit := minf(room.x, room.y) / float(window_side())

	return maxf(fit, 1.0)


## Where the top-left corner of the window sits, so the window is centred in
## the map square.
func _origin(cell_px: float) -> Vector2:
	var drawn := Vector2.ONE * float(window_side()) * cell_px

	return (map_rect().size - drawn) * 0.5


## The south-west tile of the window.
func _window_low() -> Vector2i:
	return _state.current_cell - Vector2i.ONE * _radius


func _in_window(tile: Vector2i) -> bool:
	var offset := tile - _state.current_cell

	return absi(offset.x) <= _radius and absi(offset.y) <= _radius


## Cell -> the top-left pixel of its square.
##
## Y is FLIPPED. Grid Y grows to the north and screen Y grows down. The 3D
## pane makes the same flip with -Z.
func _to_pixels(cell: Vector2i, cell_px: float, origin: Vector2) -> Vector2:
	var low := _window_low()
	var high_y := _state.current_cell.y + _radius

	return origin + Vector2(float(cell.x - low.x) * cell_px,
		float(high_y - cell.y) * cell_px)


func _centre_of(cell: Vector2i, cell_px: float, origin: Vector2) -> Vector2:
	return _to_pixels(cell, cell_px, origin) + Vector2.ONE * cell_px * 0.5


## The inverse: a point in the pane -> the cell under it.
##
## Returns a cell whether or not a chunk holds it. [method WorldState.tile_action]
## decides what a cell affords, and it answers "nothing" for one with no chunk.
func _to_cell(point: Vector2) -> Vector2i:
	if _state == null:
		return Vector2i.ZERO

	var cell_px := _cell_pixels()
	var local := (point - _origin(cell_px)) / cell_px
	var low_x := _state.current_cell.x - _radius
	var high_y := _state.current_cell.y + _radius

	return Vector2i(low_x + floori(local.x), high_y - floori(local.y))


## True when a point in the pane is on the drawn window, not on the padding
## or the strip.
func _on_window(point: Vector2) -> bool:
	var cell_px := _cell_pixels()
	var side := float(window_side()) * cell_px

	return Rect2(_origin(cell_px), Vector2(side, side)).has_point(point)


# ─── Input ───────────────────────────────────────────────────────────────────

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_hover_at((event as InputEventMouseMotion).position)
		return

	if not (event is InputEventMouseButton):
		return

	var click := event as InputEventMouseButton

	if not click.pressed:
		return

	match click.button_index:
		MOUSE_BUTTON_WHEEL_UP:
			zoom_in()
			accept_event()

		MOUSE_BUTTON_WHEEL_DOWN:
			zoom_out()
			accept_event()

		MOUSE_BUTTON_LEFT:
			if _on_window(click.position):
				_walk_to(_to_cell(click.position))

			accept_event()


func _notification(what: int) -> void:
	if what == NOTIFICATION_MOUSE_EXIT and _hovering:
		_hovering = false
		queue_redraw()


func _hover_at(point: Vector2) -> void:
	if not _on_window(point):
		if _hovering:
			_hovering = false
			queue_redraw()

		return

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
