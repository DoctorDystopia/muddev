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
##
## ## The position readout (10/21/2026)
##
## The XY button sits in the top-right corner of the map square, across from
## Run. Thus, the strip stays at three buttons. With the button on, the pane
## writes the tile and the plane of the player. The words stand at the bottom
## of the map square. The world map has the same button. Both buttons write
## [member ClientSettings.show_coordinates]. [method coordinates_of] owns the
## words, so the two maps cannot differ.
##
## ## North up, or the camera up (10/27/2026)
##
## "Minimap turns with the camera" in Options turns the ground. Then the way
## the camera looks is at the top, as on the OSRS minimap. Off by default:
## north stays up. The console gives the pane the flat view direction on
## each turn of the camera, through [method set_heading].
## [member ClientSettings.minimap_rotates] says whether the pane uses it.
## The world map never turns.
##
## The turn is one [Transform2D] about the tile of the player, from
## [method _window_transform]. The tile maths stays north up. [method
## _to_pixels] never turns, and [method _to_cell] turns a point back before
## it reads the cell. A map icon, a map dot, the flag, and the readout stand
## upright at their turned points. The ground, the path, the hover outline,
## and the player square turn with the tiles. A turned square shows its
## corners past the map square. Thus, a child that clips, [member _window],
## draws the map, and the ground reaches [method _drawn_radius].
##
## ## The compass (10/27/2026)
##
## A small compass at the top centre of the map square, between Run and XY,
## says where north is. Its needle points to north on the drawn map, from
## [method compass_needle]. With north up, it points up. With the turn on,
## it turns with the ground. It is a drawn mark, not a button.

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
const COLOR_COORDINATES := Color(0.95, 0.95, 0.95)
const COLOR_COORDINATES_OUTLINE := Color(0, 0, 0, 0.85)

## The XY button, and the words of the position readout: the tile, then the
## plane. The world map uses all three.
const COORDINATES_BUTTON_TEXT := "XY"
const COORDINATES_TIP := "Show your coordinates"
const COORDINATES_TEMPLATE := "(%d, %d), plane %d"

## The look of the position readout, in pixels. A fixed size, as for the area
## names on the world map. At the largest font, a long position is wider than
## the pane.
const COORDINATES_FONT_SIZE := 13
const COORDINATES_OUTLINE := 4
const COORDINATES_INSET := 3.0

const MARKER_WIDTH := 2.0
const PATH_WIDTH := 2.0

## The look of the compass, in pixels. The ring, the gap from the top edge
## of the map square, and the half width of the needle. The reach is how far
## the letter stands past the ring. The letter is the size of the readout.
const COMPASS_RADIUS := 9.0
const COMPASS_INSET := 3.0
const COMPASS_REACH := 7.0
const COMPASS_NEEDLE_HALF_WIDTH := 3.0
const COMPASS_LETTER := "N"
const COMPASS_RING_WIDTH := 1.5
const COMPASS_RING_POINTS := 24
const COLOR_COMPASS_FACE := Color(0.043, 0.059, 0.078, 0.85)
const COLOR_COMPASS_RING := Color(0.85, 0.85, 0.85)
const COLOR_COMPASS_NORTH := Color(0.93, 0.16, 0.16)
const COLOR_COMPASS_SOUTH := Color(0.75, 0.75, 0.75)

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

## Whether the pane draws the position readout. Without settings, the shipped
## default.
var _show_coordinates := ClientSettings.DEFAULT_SHOW_COORDINATES

## Whether the pane turns with the camera. Without settings, the shipped
## default.
var _rotates := ClientSettings.DEFAULT_MINIMAP_ROTATES

## Where the camera looks, flat on the grid, with Y to the north. Zero before
## a camera gives one, and north stays up then.
var _heading := Vector2.ZERO

## The square of the map, as a child that clips its drawing. It draws the
## whole map, and the pane itself draws nothing.
var _window: Control

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
var _coordinates_button: Button
var _strip: HBoxContainer


func _init() -> void:
	# It is drawn OVER the 3D pane, so it has to take its own clicks -- STOP,
	# not PASS: a click that fell through would walk the player somewhere else
	# as well as here.
	mouse_filter = Control.MOUSE_FILTER_STOP
	custom_minimum_size = Vector2(150, 150 + STRIP_HEIGHT)

	# One pixel of a chunk image is one tile. A blur would smear the tiles.
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST

	_build_window()
	_build_strip()
	_build_coordinates_button()


## The square of the map, as the first child, so the buttons stay on top. The
## clip keeps a turned ground off the padding and the strip. The child takes
## no click: the pane reads the clicks, and the child only draws.
func _build_window() -> void:
	_window = Control.new()
	_window.name = "Window"
	_window.clip_contents = true
	_window.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_window.draw.connect(_draw_window)
	add_child(_window)


## Fit the window to the map square and draw it again. Every change of the
## map comes here, because the child draws the map, not the pane.
func _redraw() -> void:
	var cell_px := _cell_pixels()
	var side := float(window_side()) * cell_px

	_window.position = _origin(cell_px)
	_window.size = Vector2(side, side)
	_window.queue_redraw()


## Bind to the world model and follow it.
##
## The model belongs to the CONSOLE, and the 3D pane draws the same instance.
## `meshes` is not read: nothing on this minimap is a mesh. The console
## passes it, and the argument stays so that the console needs no edit.
func bind(state: WorldState, _meshes: MeshResolver = null) -> void:
	_state = state
	_state.chunks_changed.connect(_on_chunks_changed)
	_state.chunks_changed.connect(_redraw)
	_state.room_changed.connect(_redraw)
	_state.walk_changed.connect(_redraw)
	_state.walk_changed.connect(_sync_run_button)

	_sync_run_button()
	_redraw()


## Draw a map dot for each entity of the roster. The console owns the roster,
## and the 3D pane draws the same one.
func bind_entities(roster: EntityRoster) -> void:
	_roster = roster
	_roster.changed.connect(_redraw)

	_redraw()


## Read the zoom and the two toggles from the settings, and write them back
## when the player uses the buttons.
func bind_settings(settings: ClientSettings) -> void:
	_settings = settings
	_settings.changed.connect(_apply_settings)
	_apply_settings()


func _apply_settings() -> void:
	_radius = nearest_zoom(_settings.minimap_radius)
	_show_path = _settings.show_walk_path
	_show_coordinates = _settings.show_coordinates
	_rotates = _settings.minimap_rotates
	_sync_zoom_buttons()
	_sync_coordinates_button()
	_redraw()


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

	# The position readout stands on the top of the strip. See
	# [method _draw_coordinates].
	_strip = strip
	strip.item_rect_changed.connect(_redraw)

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


# ─── The position readout ────────────────────────────────────────────────────

func _build_coordinates_button() -> void:
	_coordinates_button = Button.new()
	_coordinates_button.name = "Coordinates"
	_coordinates_button.text = COORDINATES_BUTTON_TEXT
	_coordinates_button.tooltip_text = COORDINATES_TIP
	_coordinates_button.toggle_mode = true
	_coordinates_button.focus_mode = Control.FOCUS_NONE

	# Held to the right edge, so it stays in the corner when the pane grows.
	# A zero width grows to the minimum size of the button, to the left.
	_coordinates_button.anchor_left = 1.0
	_coordinates_button.anchor_right = 1.0
	_coordinates_button.offset_left = -PADDING
	_coordinates_button.offset_right = -PADDING
	_coordinates_button.offset_top = PADDING
	_coordinates_button.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_coordinates_button.toggled.connect(set_coordinates_shown)
	add_child(_coordinates_button)

	_sync_coordinates_button()


## The words of the position of the player: the tile, then the plane. Empty
## off the tile world. The world map shows the same words.
static func coordinates_of(state: WorldState) -> String:
	if state == null or not state.on_tile_world():
		return ""

	return COORDINATES_TEMPLATE % [
		state.current_cell.x, state.current_cell.y, state.current_plane]


## The position readout that the pane draws now. Empty while the XY button
## is off. Public, so a test can read it with no canvas.
func coordinates_text() -> String:
	if not _show_coordinates:
		return ""

	return coordinates_of(_state)


## True while the XY button is on.
func coordinates_shown() -> bool:
	return _show_coordinates


## Show or hide the position readout, as the XY button does. With settings,
## the settings keep the choice, and the world map follows it.
func set_coordinates_shown(shown: bool) -> void:
	if _settings != null:
		_settings.set_show_coordinates(shown)

	_show_coordinates = shown
	_sync_coordinates_button()
	_redraw()


func _sync_coordinates_button() -> void:
	_coordinates_button.set_pressed_no_signal(_show_coordinates)


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

	_redraw()


func _sync_zoom_buttons() -> void:
	_zoom_in_button.disabled = _radius == ZOOM_RADII[0]
	_zoom_out_button.disabled = _radius == ZOOM_RADII[ZOOM_RADII.size() - 1]


# ─── The heading ─────────────────────────────────────────────────────────────

## Where the camera looks, flat on the grid with Y to the north, from
## [method WorldView.camera_forward]. The pane keeps it whether or not it
## turns. Thus, a later tick of the option turns the map at once.
func set_heading(forward: Vector2) -> void:
	if forward.is_equal_approx(_heading):
		return

	_heading = forward

	if _rotates:
		_redraw()


## True while the pane turns with the camera.
func rotates() -> bool:
	return _rotates


## The turn of the drawn ground, in radians. Zero with north up.
##
## With the option on, the way the camera looks goes to the top. The angle
## runs COUNTER to the heading. A camera that looks east, heading (1, 0),
## turns the map a quarter turn to the left. Then the east tile stands above
## the player. A heading of zero, before a camera gives one, keeps north up.
func heading_angle() -> float:
	if not _rotates or _heading.is_zero_approx():
		return 0.0

	return -atan2(_heading.x, _heading.y)


## The turn of the window, about its centre: the tile of the player. The
## identity with north up. In the space of the window, not of the pane.
func _window_transform(cell_px: float) -> Transform2D:
	var angle := heading_angle()

	if is_zero_approx(angle):
		return Transform2D.IDENTITY

	var centre := Vector2.ONE * float(window_side()) * cell_px * 0.5

	return Transform2D(angle, centre) * Transform2D(0.0, -centre)


## The centre of a cell as the pane draws it, after the turn, in the space
## of the pane. Public, so a test can check the turn with no canvas.
func drawn_point_of(cell: Vector2i) -> Vector2:
	var cell_px := _cell_pixels()
	var origin := _origin(cell_px)

	return origin + _window_transform(cell_px) * _centre_of(cell, cell_px, Vector2.ZERO)


## The tiles on each side of the player that the ground reaches. A turned
## window shows its corners past the map square. Thus, the drawn ground must
## reach the corners of the turned square: the radius times the square root
## of two. The chunks of the block reach at least 64 tiles past the player,
## and the widest zoom turned needs 57.
func _drawn_radius() -> int:
	if is_zero_approx(heading_angle()):
		return _radius

	return ceili(float(_radius) * sqrt(2.0))


# ─── Drawing ─────────────────────────────────────────────────────────────────

## Draw the map on the window. The origin of the window is the top-left of
## the map square, so each draw gets a zero origin. The ground, the path,
## the hover outline, and the player square turn with the tiles. The icons,
## the dots, the flag, and the readout stand upright at their turned points.
func _draw_window() -> void:
	var cell_px := _cell_pixels()
	var origin := Vector2.ZERO
	var turn := _window_transform(cell_px)

	_window.draw_rect(Rect2(Vector2.ZERO, _window.size), COLOR_BACKGROUND)

	if _state == null or not _state.has_ground():
		return

	_window.draw_set_transform_matrix(turn)
	_draw_ground(cell_px, origin)
	_window.draw_set_transform_matrix(Transform2D.IDENTITY)
	_draw_icons(cell_px, origin, turn)

	if _show_path:
		_window.draw_set_transform_matrix(turn)
		_draw_walk_path(cell_px, origin)
		_window.draw_set_transform_matrix(Transform2D.IDENTITY)

	_draw_dots(cell_px, origin, turn)
	_window.draw_set_transform_matrix(turn)

	if _hovering:
		_draw_cell_outline(_hover_cell, cell_px, origin, COLOR_HOVER)

	_draw_self(cell_px, origin)
	_window.draw_set_transform_matrix(Transform2D.IDENTITY)
	_draw_flag(cell_px, origin, turn)
	_draw_coordinates()
	_draw_compass()


## Draw the part of each chunk image that the window covers. A turned window
## covers more than the square: see [method _drawn_radius].
func _draw_ground(cell_px: float, origin: Vector2) -> void:
	var chunk_size: int = _Const.CHUNK_SIZE
	var drawn := _drawn_radius()
	var low := _state.current_cell - Vector2i.ONE * drawn
	var high := _state.current_cell + Vector2i.ONE * drawn
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

			_window.draw_texture_rect_region(_texture_of(chunk), target, source)


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


## Each icon stands upright at the turned centre of its tile.
func _draw_icons(cell_px: float, origin: Vector2, turn: Transform2D) -> void:
	var chunk_size: int = _Const.CHUNK_SIZE
	var icon_px := clampf(cell_px * ICON_SHARE, ICON_MIN_PX, ICON_MAX_PX)

	for coord: Vector2i in _state.chunks.chunk_coords():
		var chunk := _state.chunks.get_chunk(coord)

		for placed: Dictionary in chunk.objects:
			var tile := coord * chunk_size + Vector2i(int(placed["x"]), int(placed["y"]))

			if not _in_window(tile):
				continue

			var category := MapIcons.category_of(str(placed["kind"]))

			MapIcons.draw(_window, category, turn * _centre_of(tile, cell_px, origin),
				icon_px)


func _draw_dots(cell_px: float, origin: Vector2, turn: Transform2D) -> void:
	if _roster == null:
		return

	var dot_px := clampf(cell_px * DOT_SHARE, DOT_MIN_PX, DOT_MAX_PX)

	for kind: String in DOT_ORDER:
		for tile: Vector2i in dot_tiles(kind):
			var centre := turn * _centre_of(tile, cell_px, origin)

			_window.draw_circle(centre, dot_px + 1.0, COLOR_DOT_OUTLINE)
			_window.draw_circle(centre, dot_px, DOT_COLOURS[kind])


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

	_window.draw_rect(Rect2(at + Vector2.ONE * inset,
		Vector2.ONE * (cell_px - inset * 2.0)), COLOR_SELF)
	_draw_cell_outline(_state.current_cell, cell_px, origin, COLOR_MARKER)


## The destination marker: a flag on a pole, standing upright on the turned
## centre of the goal tile.
func _draw_flag(cell_px: float, origin: Vector2, turn: Transform2D) -> void:
	if not _state.walk_on_current_plane() or not _in_window(_state.walk_goal):
		return

	var foot := turn * _centre_of(_state.walk_goal, cell_px, origin)
	var height := clampf(cell_px * 2.0, 8.0, 14.0)
	var top := foot - Vector2(0, height)
	var cloth := PackedVector2Array([top, top + Vector2(height * 0.7, height * 0.2),
		top + Vector2(0, height * 0.45)])

	_window.draw_line(foot, top, COLOR_FLAG_POLE, 1.5)
	_window.draw_colored_polygon(cloth, COLOR_FLAG)


## The walk path: a line from the player through each tile still to walk.
## Only the segments with both ends in the window are drawn.
func _draw_walk_path(cell_px: float, origin: Vector2) -> void:
	if not _state.walk_on_current_plane():
		return

	var previous := _state.current_cell

	for tile: Vector2i in _state.walk_path:
		if _in_window(previous) and _in_window(tile):
			_window.draw_line(_centre_of(previous, cell_px, origin),
				_centre_of(tile, cell_px, origin), COLOR_PATH, PATH_WIDTH)

		previous = tile


## The position readout, centred at the bottom of the window, over the
## ground. A large font makes the strip grow up over the map. Then the words
## stand on the top of the strip, not under its buttons. The strip sits in
## the space of the pane, so its top moves by the origin of the window.
func _draw_coordinates() -> void:
	var text := coordinates_text()

	if text.is_empty():
		return

	var font := get_theme_default_font()
	var width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1,
		COORDINATES_FONT_SIZE).x
	var bottom := minf(_window.size.y, _strip.position.y - _window.position.y)
	var at := Vector2((size.x - width) * 0.5 - _window.position.x,
		bottom - COORDINATES_INSET - font.get_descent(COORDINATES_FONT_SIZE))

	_window.draw_string_outline(font, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1,
		COORDINATES_FONT_SIZE, COORDINATES_OUTLINE, COLOR_COORDINATES_OUTLINE)
	_window.draw_string(font, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1,
		COORDINATES_FONT_SIZE, COLOR_COORDINATES)


## Where north is on the drawn map, as a unit vector in screen space: up
## with north up, and turned with the ground when the map turns. Public, so
## a test can check the needle with no canvas.
func compass_needle() -> Vector2:
	return Vector2.UP.rotated(heading_angle())


## The centre of the compass, in the space of the pane. It is the top
## centre of the map square, with room above it for the letter at the
## north tip.
func compass_centre() -> Vector2:
	var cell_px := _cell_pixels()
	var side := float(window_side()) * cell_px

	return _origin(cell_px) + Vector2(side * 0.5,
		COMPASS_INSET + COMPASS_REACH + COMPASS_RADIUS)


## The compass: a ring, a red needle to north, a grey needle to south, and
## the letter past the north tip. Upright on the window, whatever the turn.
func _draw_compass() -> void:
	var centre := compass_centre() - _window.position
	var needle := compass_needle()
	var across := needle.orthogonal() * COMPASS_NEEDLE_HALF_WIDTH
	var tip := centre + needle * COMPASS_RADIUS
	var tail := centre - needle * COMPASS_RADIUS

	_window.draw_circle(centre, COMPASS_RADIUS, COLOR_COMPASS_FACE)
	_window.draw_arc(centre, COMPASS_RADIUS, 0.0, TAU, COMPASS_RING_POINTS,
		COLOR_COMPASS_RING, COMPASS_RING_WIDTH)
	_window.draw_colored_polygon(
		PackedVector2Array([tip, centre + across, centre - across]), COLOR_COMPASS_NORTH)
	_window.draw_colored_polygon(
		PackedVector2Array([tail, centre - across, centre + across]), COLOR_COMPASS_SOUTH)
	_draw_compass_letter(centre + needle * (COMPASS_RADIUS + COMPASS_REACH))


## The letter N, centred on a point. The font gives the width and the
## height, so the letter sits on the point at every UI scale.
func _draw_compass_letter(at: Vector2) -> void:
	var font := get_theme_default_font()
	var box := font.get_string_size(COMPASS_LETTER, HORIZONTAL_ALIGNMENT_LEFT, -1,
		COORDINATES_FONT_SIZE)
	var ascent := font.get_ascent(COORDINATES_FONT_SIZE)
	var descent := font.get_descent(COORDINATES_FONT_SIZE)
	var baseline := at + Vector2(-box.x * 0.5, (ascent - descent) * 0.5)

	_window.draw_string_outline(font, baseline, COMPASS_LETTER,
		HORIZONTAL_ALIGNMENT_LEFT, -1, COORDINATES_FONT_SIZE, COORDINATES_OUTLINE,
		COLOR_COORDINATES_OUTLINE)
	_window.draw_string(font, baseline, COMPASS_LETTER, HORIZONTAL_ALIGNMENT_LEFT,
		-1, COORDINATES_FONT_SIZE, COLOR_COORDINATES)


func _draw_cell_outline(cell: Vector2i, cell_px: float, origin: Vector2,
		colour: Color) -> void:
	var at := _to_pixels(cell, cell_px, origin)

	_window.draw_rect(Rect2(at, Vector2.ONE * cell_px), colour, false, MARKER_WIDTH)


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


## True for a tile that the ground reaches. A turned window reaches past the
## square: see [method _drawn_radius].
func _in_window(tile: Vector2i) -> bool:
	var offset := tile - _state.current_cell
	var drawn := _drawn_radius()

	return absi(offset.x) <= drawn and absi(offset.y) <= drawn


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
## A turned map turns the point back first, so a click lands on the tile
## that the player sees under the cursor.
func _to_cell(point: Vector2) -> Vector2i:
	if _state == null:
		return Vector2i.ZERO

	var cell_px := _cell_pixels()
	var unturned := _window_transform(cell_px).affine_inverse() * (point - _origin(cell_px))
	var local := unturned / cell_px
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
				var swap_pace := _settings != null and _settings.swaps_pace(click)

				_walk_to(_to_cell(click.position), swap_pace)

			accept_event()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED and _window != null:
		_redraw()

	if what == NOTIFICATION_MOUSE_EXIT and _hovering:
		_hovering = false
		_redraw()


func _hover_at(point: Vector2) -> void:
	if not _on_window(point):
		if _hovering:
			_hovering = false
			_redraw()

		return

	var cell := _to_cell(point)

	if _hovering and cell == _hover_cell:
		return

	_hover_cell = cell
	_hovering = true
	_redraw()


## Send whatever a click on this cell does. This pane composes nothing and
## refuses nothing. [method WorldState.click_command] owns the answer.
##
## `swap_pace` is true for a Ctrl + left click with the option on. The walk
## then goes at the pace that is not the run toggle.
func _walk_to(cell: Vector2i, swap_pace := false) -> void:
	if _state == null:
		return

	var command := _state.click_command(cell, swap_pace)

	if command.is_empty():
		return

	command_requested.emit(command)
