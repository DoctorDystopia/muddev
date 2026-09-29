class_name WorldMapView
extends PanelContainer
## The world map: a large map of every chunk of one plane, over the world pane.
##
## ## What it shows (09/28/2026, the OSRS world map)
##
##   - The ground of the plane, from the image of [WorldMapState].
##   - A map icon for each chunk object, through [MapIcons].
##   - The name of each area.
##   - "You are here": your tile, on your plane.
##   - The destination marker and the walk path, as on the minimap. The path
##     follows the same setting.
##   - The tile under the cursor, as `(x, y)`, for a player who types
##     `goto x,y`.
##
## ## It moves nothing
##
## Nick chose a view-only map. A drag pans, the mouse wheel zooms around the
## cursor, and a click walks nowhere. A walk across the world can hit the
## limit of the A* search, so a click that walked would often fail.
##
## ## Where it lives
##
## A sibling of the world pane's other boxes, as [PopupView] is: above the
## docks, under the right-click menu and the veil. Built in code, because its
## contents depend on nothing in the scene. Esc or the close button hides it.

## Pixels for each tile at each zoom step.
const ZOOM_STEPS: Array[int] = [1, 2, 3, 4, 6, 8]
const DEFAULT_ZOOM := 3

## Clear space around the box, inside the world pane.
const MARGIN := 24.0

const LABEL_FONT_SIZE := 14
const LABEL_OUTLINE := 4

const COLOR_BACKGROUND := Color(0.03, 0.04, 0.05, 1.0)
const COLOR_LABEL := Color(0.95, 0.9, 0.75)
const COLOR_LABEL_OUTLINE := Color(0, 0, 0, 0.85)
const COLOR_SELF := Color(1, 1, 1)
const COLOR_SELF_OUTLINE := Color(0.208, 0.878, 0.753)
const COLOR_FLAG := Color(0.93, 0.16, 0.16)
const COLOR_FLAG_POLE := Color(0.95, 0.95, 0.95)
const COLOR_PATH := Color(1.0, 0.95, 0.55, 0.75)

const ICON_SHARE := 1.6
const ICON_MIN_PX := 6.0
const ICON_MAX_PX := 12.0
const SELF_MIN_PX := 6.0

var _map: WorldMapState
var _state: WorldState
var _settings: ClientSettings

## The plane on show, and the zoom in pixels for each tile.
var _plane := 0
var _zoom := DEFAULT_ZOOM

## The world point at the centre of the canvas. A tile t covers [t, t + 1).
var _centre := Vector2.ZERO

## plane -> ImageTexture, built again when the image of the plane changes.
var _textures := {}

var _dragging := false

var _canvas: Control
var _plane_label: Label
var _readout: Label
var _plane_down: Button
var _plane_up: Button


func _init() -> void:
	name = "WorldMap"
	visible = false

	# The look of the other boxes over the world pane: the dock, the pop-up.
	theme_type_variation = &"PopupBox"
	mouse_filter = Control.MOUSE_FILTER_STOP
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	offset_left = MARGIN
	offset_top = MARGIN
	offset_right = -MARGIN
	offset_bottom = -MARGIN

	var column := VBoxContainer.new()

	add_child(column)
	column.add_child(_build_title_bar())

	_canvas = Control.new()
	_canvas.name = "Canvas"
	_canvas.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_canvas.clip_contents = true
	_canvas.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_canvas.mouse_filter = Control.MOUSE_FILTER_STOP
	_canvas.draw.connect(_draw_map)
	_canvas.gui_input.connect(_on_canvas_input)
	_canvas.resized.connect(_clamp_centre)
	column.add_child(_canvas)

	_readout = Label.new()
	_readout.text = " "
	column.add_child(_readout)


## Bind to the models. The console owns all three.
func bind(map: WorldMapState, state: WorldState,
		settings: ClientSettings = null) -> void:
	_map = map
	_state = state
	_settings = settings
	_map.plane_changed.connect(_on_plane_changed)
	_map.index_arrived.connect(_on_index)
	_state.room_changed.connect(_canvas.queue_redraw)
	_state.walk_changed.connect(_canvas.queue_redraw)

	if _settings != null:
		_settings.changed.connect(_canvas.queue_redraw)


# ─── Open and close ──────────────────────────────────────────────────────────

## Show the map on the plane of the player, centred on the player. Does
## nothing more when it is already open, so a second request keeps the view.
func open() -> void:
	if visible:
		return

	visible = true
	_plane = _start_plane()
	_centre = Vector2(_state.current_cell) + Vector2.ONE * 0.5
	_clamp_centre()
	_sync_plane_controls()
	_canvas.queue_redraw()


func close() -> void:
	visible = false
	_dragging = false


func _input(event: InputEvent) -> void:
	if not visible:
		return

	if event is InputEventKey and event.pressed and not event.echo \
			and (event as InputEventKey).keycode == KEY_ESCAPE:
		close()
		get_viewport().set_input_as_handled()


func _start_plane() -> int:
	if _state.current_plane >= 0 and _map.planes.has(_state.current_plane):
		return _state.current_plane

	if _map.planes.is_empty():
		return 0

	return _map.planes[0]


## The index can land after the button opened an empty map. Then the map
## moves to the plane of the player and centres on the player.
func _on_index() -> void:
	if visible and not _map.planes.has(_plane):
		centre_on_player()

	_sync_plane_controls()
	_canvas.queue_redraw()


func _on_plane_changed(changed: int) -> void:
	_textures.erase(changed)

	if changed == _plane:
		_clamp_centre()
		_canvas.queue_redraw()


# ─── The title bar ───────────────────────────────────────────────────────────

func _build_title_bar() -> HBoxContainer:
	var bar := HBoxContainer.new()
	var title := Label.new()

	title.text = "World map"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bar.add_child(title)

	_plane_down = _bar_button(bar, "Down", "Show the plane below")
	_plane_down.pressed.connect(step_plane.bind(-1))
	_plane_label = Label.new()
	bar.add_child(_plane_label)
	_plane_up = _bar_button(bar, "Up", "Show the plane above")
	_plane_up.pressed.connect(step_plane.bind(1))

	_bar_button(bar, "-", "Zoom out").pressed.connect(step_zoom.bind(-1))
	_bar_button(bar, "+", "Zoom in").pressed.connect(step_zoom.bind(1))
	_bar_button(bar, "Me", "Centre on you").pressed.connect(centre_on_player)
	_bar_button(bar, "X", "Close the world map").pressed.connect(close)

	return bar


func _bar_button(bar: HBoxContainer, text: String, tip: String) -> Button:
	var button := Button.new()

	button.text = text
	button.tooltip_text = tip
	button.focus_mode = Control.FOCUS_NONE
	bar.add_child(button)

	return button


func _sync_plane_controls() -> void:
	var held: Array[int] = _map.planes if _map != null else []
	var at := held.find(_plane)

	_plane_label.text = "Plane %d" % _plane
	_plane_down.disabled = at <= 0
	_plane_up.disabled = at < 0 or at >= held.size() - 1


# ─── Plane, zoom, and pan ────────────────────────────────────────────────────

## The plane on show.
func plane() -> int:
	return _plane


## Show the next plane up (+1) or down (-1) that holds a chunk.
func step_plane(direction: int) -> void:
	var at := _map.planes.find(_plane)
	var next := clampi(at + direction, 0, _map.planes.size() - 1)

	if at < 0 or next == at:
		return

	_plane = _map.planes[next]
	_clamp_centre()
	_sync_plane_controls()
	_canvas.queue_redraw()


## The pixels for each tile now.
func zoom() -> int:
	return _zoom


## Zoom one step in (+1) or out (-1), around the centre of the canvas.
func step_zoom(direction: int) -> void:
	zoom_at(_canvas.size * 0.5, direction)


## Zoom one step around a point of the canvas. The world point under it
## stays under it.
func zoom_at(point: Vector2, direction: int) -> void:
	var at := ZOOM_STEPS.find(_zoom)
	var next := clampi(at + direction, 0, ZOOM_STEPS.size() - 1)

	if next == at:
		return

	var anchor := world_point_at(point)
	var offset := point - _canvas.size * 0.5

	_zoom = ZOOM_STEPS[next]
	_centre = Vector2(anchor.x - offset.x / _zoom, anchor.y + offset.y / _zoom)
	_clamp_centre()
	_canvas.queue_redraw()


## Move the view by a drag of `delta` pixels.
func pan_by(delta: Vector2) -> void:
	_centre += Vector2(-delta.x, delta.y) / float(_zoom)
	_clamp_centre()
	_canvas.queue_redraw()


func centre_on_player() -> void:
	_plane = _start_plane()
	_sync_plane_controls()

	_centre = Vector2(_state.current_cell) + Vector2.ONE * 0.5
	_clamp_centre()
	_canvas.queue_redraw()


## The world point at the centre of the canvas.
func centre() -> Vector2:
	return _centre


## Keep the centre inside the bounds of the plane, so the map cannot scroll
## away into the dark.
func _clamp_centre() -> void:
	if _map == null:
		return

	var rect := _map.bounds(_plane)

	if rect.size == Vector2i.ZERO:
		return

	_centre = Vector2(
		clampf(_centre.x, rect.position.x, rect.end.x),
		clampf(_centre.y, rect.position.y, rect.end.y))


# ─── Geometry ────────────────────────────────────────────────────────────────

## A world point -> a point of the canvas. Y is flipped: grid Y grows north.
func canvas_point(world: Vector2) -> Vector2:
	var offset := Vector2(world.x - _centre.x, _centre.y - world.y) * _zoom

	return _canvas.size * 0.5 + offset


## A point of the canvas -> the world point under it.
func world_point_at(point: Vector2) -> Vector2:
	var offset := (point - _canvas.size * 0.5) / float(_zoom)

	return Vector2(_centre.x + offset.x, _centre.y - offset.y)


## A point of the canvas -> the tile under it.
func tile_at(point: Vector2) -> Vector2i:
	var world := world_point_at(point)

	return Vector2i(floori(world.x), floori(world.y))


func _tile_centre(tile: Vector2i) -> Vector2:
	return canvas_point(Vector2(tile) + Vector2.ONE * 0.5)


# ─── Drawing ─────────────────────────────────────────────────────────────────

func _draw_map() -> void:
	_canvas.draw_rect(Rect2(Vector2.ZERO, _canvas.size), COLOR_BACKGROUND)

	if _map == null or not _map.has_data():
		return

	_draw_ground()
	_draw_icons()

	if _on_player_plane():
		if _settings != null and _settings.show_walk_path:
			_draw_walk_path()

		_draw_self()
		_draw_flag()

	_draw_labels()


func _draw_ground() -> void:
	var rect := _map.bounds(_plane)
	var texture := _texture_of(_plane)

	if texture == null:
		return

	# The image row 0 is the north edge of the bounds.
	var top_left := canvas_point(Vector2(rect.position.x, rect.end.y))

	_canvas.draw_texture_rect(texture,
		Rect2(top_left, Vector2(rect.size) * _zoom), false)


func _texture_of(shown: int) -> ImageTexture:
	if not _textures.has(shown):
		var image := _map.image(shown)

		if image == null:
			return null

		_textures[shown] = ImageTexture.create_from_image(image)

	return _textures[shown]


func _draw_icons() -> void:
	var icon_px := clampf(_zoom * ICON_SHARE, ICON_MIN_PX, ICON_MAX_PX)

	for icon: Dictionary in _map.icons(_plane):
		MapIcons.draw(_canvas, icon["category"], _tile_centre(icon["tile"]),
			icon_px)


func _draw_labels() -> void:
	var font := get_theme_default_font()

	for label: Dictionary in _map.labels_of(_plane):
		var text := str(label.get("text", ""))
		var width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1,
			LABEL_FONT_SIZE).x
		var tile := Vector2i(int(label.get("x", 0)), int(label.get("y", 0)))
		var at := _tile_centre(tile) - Vector2(width * 0.5, 0)

		_canvas.draw_string_outline(font, at, text, HORIZONTAL_ALIGNMENT_LEFT,
			-1, LABEL_FONT_SIZE, LABEL_OUTLINE, COLOR_LABEL_OUTLINE)
		_canvas.draw_string(font, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1,
			LABEL_FONT_SIZE, COLOR_LABEL)


func _on_player_plane() -> bool:
	return _state != null and _state.on_tile_world() \
		and _state.current_plane == _plane


func _draw_self() -> void:
	var side := maxf(float(_zoom), SELF_MIN_PX)
	var middle := _tile_centre(_state.current_cell)
	var rect := Rect2(middle - Vector2.ONE * side * 0.5, Vector2.ONE * side)

	_canvas.draw_rect(rect, COLOR_SELF)
	_canvas.draw_rect(rect, COLOR_SELF_OUTLINE, false, 2.0)


func _draw_flag() -> void:
	if not _state.walk_on_current_plane():
		return

	var foot := _tile_centre(_state.walk_goal)
	var height := clampf(_zoom * 3.0, 10.0, 18.0)
	var top := foot - Vector2(0, height)
	var cloth := PackedVector2Array([top, top + Vector2(height * 0.7, height * 0.2),
		top + Vector2(0, height * 0.45)])

	_canvas.draw_line(foot, top, COLOR_FLAG_POLE, 1.5)
	_canvas.draw_colored_polygon(cloth, COLOR_FLAG)


func _draw_walk_path() -> void:
	if not _state.walk_on_current_plane() or _state.walk_path.is_empty():
		return

	var points := PackedVector2Array([_tile_centre(_state.current_cell)])

	for tile: Vector2i in _state.walk_path:
		points.append(_tile_centre(tile))

	_canvas.draw_polyline(points, COLOR_PATH, 2.0)


# ─── Input ───────────────────────────────────────────────────────────────────

func _on_canvas_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		var motion := event as InputEventMouseMotion

		if _dragging:
			pan_by(motion.relative)

		_show_readout(motion.position)
		return

	if not (event is InputEventMouseButton):
		return

	var click := event as InputEventMouseButton

	match click.button_index:
		MOUSE_BUTTON_WHEEL_UP:
			if click.pressed:
				zoom_at(click.position, 1)

		MOUSE_BUTTON_WHEEL_DOWN:
			if click.pressed:
				zoom_at(click.position, -1)

		MOUSE_BUTTON_LEFT:
			_dragging = click.pressed

	_canvas.accept_event()


func _show_readout(point: Vector2) -> void:
	var tile := tile_at(point)

	_readout.text = "(%d, %d)" % [tile.x, tile.y]
