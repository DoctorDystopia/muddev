class_name WorldMapView
extends FloatingBox
## The world map: a large map of every chunk of one plane, in a floating box
## over the world pane.
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
##   - The legend, in a column at the right side (10/19/2026).
##   - The position readout, while the XY button is on: your tile and your
##     plane (10/21/2026). The minimap has the same button, and both buttons
##     write one setting.
##
## ## It moves nothing
##
## Nick chose a view-only map. A drag pans, the mouse wheel zooms around the
## cursor, and a click walks nowhere. A walk across the world can hit the
## limit of the A* search, so a click that walked would often fail.
##
## ## A floating box (10/19/2026)
##
## [FloatingBox] owns the box, as it owns the box of the pop-up: the dim over
## the world, the move, the grips, and the first rect between the docks. The
## rect is [member ClientSettings.world_map_rect]. Until 10/19/2026 the map
## was a fixed box over the docks.
##
## Nick chose the rule of the pop-up for a click beside the box: the world
## takes no click, and the docks stay in reach. Thus, the map sits under the
## docks, as the pop-up does, and over the pop-up. Esc reads the key in
## `_input`, and the pop-up reads it in `_unhandled_input`. Thus, Esc closes
## the box on top first.
##
## ## The legend (10/19/2026)
##
## [WorldMapLegend] names each map icon and each marker. The Legend button
## shows or hides it. A click on an icon row hides the map icons of that
## category on the world map. The minimap does not change. [ClientSettings]
## keeps both choices, and the map reads them at each draw. Thus, Reset in
## Options shows every icon again at once.

## Pixels for each tile at each zoom step.
const ZOOM_STEPS: Array[int] = [1, 2, 3, 4, 6, 8]
const DEFAULT_ZOOM := 3

const TITLE_TEXT := "World map"
const LEGEND_TEXT := "Legend"

## The position readout: the words of [method MinimapView.coordinates_of],
## marked as yours. The tile under the cursor stands in the same row.
const POSITION_TEMPLATE := "You: %s"

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
const SELF_OUTLINE_WIDTH := 2.0

## The height of the destination marker: tiles of the zoom, and the bounds in
## pixels. The cloth is a triangle, in parts of that height.
const FLAG_SHARE := 3.0
const FLAG_MIN_PX := 10.0
const FLAG_MAX_PX := 18.0
const FLAG_CLOTH_WIDTH := 0.7
const FLAG_CLOTH_TIP := 0.2
const FLAG_CLOTH_DROP := 0.45
const FLAG_POLE_WIDTH := 1.5

const PATH_WIDTH := 2.0

var _map: WorldMapState
var _state: WorldState

## The plane on show, and the zoom in pixels for each tile.
var _plane := 0
var _zoom := DEFAULT_ZOOM

## The world point at the centre of the canvas. A tile t covers [t, t + 1).
var _centre := Vector2.ZERO

## plane -> ImageTexture, built again when the image of the plane changes.
var _textures := {}

var _dragging := false

## The two choices of the legend, when no settings are bound. A test binds
## none. With settings, [ClientSettings] is the one owner of both.
var _local_hidden := PackedStringArray()
var _local_legend := ClientSettings.DEFAULT_WORLD_MAP_LEGEND

## The XY button, when no settings are bound. With settings,
## [member ClientSettings.show_coordinates] is the one owner.
var _local_coordinates := ClientSettings.DEFAULT_SHOW_COORDINATES

var _canvas: Control
var _plane_label: Label
var _readout: Label
var _position: Label
var _coordinates_button: Button
var _plane_down: Button
var _plane_up: Button
var _legend_button: Button
var _legend_scroll: ScrollContainer
var _legend: WorldMapLegend


## The box, the title bar and the grips come from [FloatingBox].
func _init() -> void:
	super()
	name = "WorldMap"
	_title.text = TITLE_TEXT
	_build_title_buttons()

	var body := HBoxContainer.new()

	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_column.add_child(body)
	body.add_child(_build_canvas())
	body.add_child(_build_legend())
	_column.add_child(_build_footer())


## Bind to the models. The console owns all three.
func bind(map: WorldMapState, state: WorldState,
		settings: ClientSettings = null) -> void:
	_map = map
	_state = state
	bind_settings(settings)
	_map.plane_changed.connect(_on_plane_changed)
	_map.index_arrived.connect(_on_index)
	_state.room_changed.connect(_canvas.queue_redraw)
	_state.room_changed.connect(_sync_coordinates)
	_state.walk_changed.connect(_canvas.queue_redraw)

	if _settings != null:
		_settings.changed.connect(_on_settings_changed)

	_sync_legend()
	_sync_coordinates()


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
	_sync_legend()
	_canvas.queue_redraw()

	# Deferred: a pane that changed size while the box was hidden needs the
	# layout pass that sizes this control.
	_place_box.call_deferred()


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


# ─── The rect between runs ───────────────────────────────────────────────────

func _stored_rect() -> Rect2:
	return _settings.world_map_rect


func _store_rect(rect: Rect2) -> void:
	_settings.set_world_map_rect(rect)


# ─── Building ────────────────────────────────────────────────────────────────

## The buttons after the title: the plane, the zoom, XY, the legend, and
## Close.
func _build_title_buttons() -> void:
	_plane_down = _bar_button("Down", "Show the plane below")
	_plane_down.pressed.connect(step_plane.bind(-1))
	_plane_label = Label.new()
	_title_bar.add_child(_plane_label)
	_plane_up = _bar_button("Up", "Show the plane above")
	_plane_up.pressed.connect(step_plane.bind(1))

	_bar_button("-", "Zoom out").pressed.connect(step_zoom.bind(-1))
	_bar_button("+", "Zoom in").pressed.connect(step_zoom.bind(1))
	_bar_button("Me", "Centre on you").pressed.connect(centre_on_player)

	_coordinates_button = _bar_button(MinimapView.COORDINATES_BUTTON_TEXT,
		MinimapView.COORDINATES_TIP)
	_coordinates_button.toggle_mode = true
	_coordinates_button.toggled.connect(set_coordinates_shown)

	_legend_button = _bar_button(LEGEND_TEXT, "Show or hide the legend")
	_legend_button.toggle_mode = true
	_legend_button.toggled.connect(set_legend_shown)

	_add_close_button(close).focus_mode = Control.FOCUS_NONE


## A button of the title bar. It takes no keyboard focus, so a click on it
## leaves the keyboard with the game input.
func _bar_button(text: String, tip: String) -> Button:
	var button := Button.new()

	button.text = text
	button.tooltip_text = tip
	button.focus_mode = Control.FOCUS_NONE
	_title_bar.add_child(button)

	return button


func _build_canvas() -> Control:
	_canvas = Control.new()
	_canvas.name = "Canvas"
	_canvas.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_canvas.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_canvas.clip_contents = true
	_canvas.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_canvas.mouse_filter = Control.MOUSE_FILTER_STOP
	_canvas.draw.connect(_draw_map)
	_canvas.gui_input.connect(_on_canvas_input)
	_canvas.resized.connect(_clamp_centre)

	return _canvas


## The legend, in a scroll. A short box then does not grow to hold every row.
## The scroll takes the width of the legend, so no row is cut.
func _build_legend() -> Control:
	_legend_scroll = ScrollContainer.new()
	_legend_scroll.name = "LegendScroll"
	_legend_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED

	_legend = WorldMapLegend.new()
	_legend.icon_toggled.connect(set_icon_shown)
	_legend_scroll.add_child(_legend)

	return _legend_scroll


## The row under the canvas: the tile under the cursor at the left, and the
## position readout at the right.
func _build_footer() -> Control:
	var footer := HBoxContainer.new()

	footer.name = "Footer"
	_readout = Label.new()
	_readout.text = " "
	_readout.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	footer.add_child(_readout)

	_position = Label.new()
	_position.name = "Position"
	footer.add_child(_position)

	return footer


func _sync_plane_controls() -> void:
	var held: Array[int] = _map.planes if _map != null else []
	var at := held.find(_plane)

	_plane_label.text = "Plane %d" % _plane
	_plane_down.disabled = at <= 0
	_plane_up.disabled = at < 0 or at >= held.size() - 1


# ─── The legend ──────────────────────────────────────────────────────────────

## The legend. For tests.
func legend() -> WorldMapLegend:
	return _legend


## True when the legend shows.
func legend_shown() -> bool:
	if _settings != null:
		return _settings.world_map_legend

	return _local_legend


## Show or hide the legend, as the Legend button does.
func set_legend_shown(shown: bool) -> void:
	if _settings != null:
		_settings.set_world_map_legend(shown)
	else:
		_local_legend = shown

	_sync_legend()


## True when the map draws the map icons of `category`.
func icon_shown(category: String) -> bool:
	return not _hidden_icons().has(category)


## Show or hide the map icons of one category, as a click on its legend row
## does.
func set_icon_shown(category: String, shown: bool) -> void:
	var hidden_categories := _hidden_icons().duplicate()
	var at := hidden_categories.find(category)

	if shown and at >= 0:
		hidden_categories.remove_at(at)
	elif not shown and at < 0:
		hidden_categories.append(category)

	if _settings != null:
		_settings.set_world_map_hidden_icons(hidden_categories)
	else:
		_local_hidden = hidden_categories

	_sync_legend()
	_canvas.queue_redraw()


func _hidden_icons() -> PackedStringArray:
	if _settings != null:
		return _settings.world_map_hidden_icons

	return _local_hidden


## Make the legend, its button, and its rows say what the settings say.
##
## A legend that appears raises the smallest box. This places the box again,
## so the wider box stays inside the pane.
func _sync_legend() -> void:
	var shown := legend_shown()
	var path_drawn := _settings != null and _settings.show_walk_path

	_legend_button.set_pressed_no_signal(shown)
	_legend.sync(_hidden_icons(), path_drawn)

	if _legend_scroll.visible == shown:
		return

	_legend_scroll.visible = shown
	_place_box.call_deferred()


func _on_settings_changed() -> void:
	_sync_legend()
	_sync_coordinates()
	_canvas.queue_redraw()


# ─── The position readout ────────────────────────────────────────────────────

## True when the map shows the position readout.
func coordinates_shown() -> bool:
	if _settings != null:
		return _settings.show_coordinates

	return _local_coordinates


## Show or hide the position readout, as the XY button does. The minimap
## follows, because both maps read one setting.
func set_coordinates_shown(shown: bool) -> void:
	if _settings != null:
		_settings.set_show_coordinates(shown)
	else:
		_local_coordinates = shown

	_sync_coordinates()


## The position readout that the map shows now. Empty while the XY button is
## off, and off the tile world. For tests.
func coordinates_text() -> String:
	return _position.text


## Make the XY button and the position readout say what the setting says,
## and where the player stands now.
func _sync_coordinates() -> void:
	var shown := coordinates_shown()
	var words := MinimapView.coordinates_of(_state)

	_coordinates_button.set_pressed_no_signal(shown)

	if not shown or words.is_empty():
		_position.text = ""
		return

	_position.text = POSITION_TEMPLATE % words


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


# ─── The markers, for the map and the legend ─────────────────────────────────

## Draw the mark of the tile of the player: a square `side` pixels across.
## The legend draws its sample with the same call, so the two cannot differ.
static func draw_self_mark(canvas: CanvasItem, middle: Vector2, side: float) -> void:
	var rect := Rect2(middle - Vector2.ONE * side * 0.5, Vector2.ONE * side)

	canvas.draw_rect(rect, COLOR_SELF)
	canvas.draw_rect(rect, COLOR_SELF_OUTLINE, false, SELF_OUTLINE_WIDTH)


## Draw the destination marker: a flag `height` pixels tall, on a pole that
## stands on `foot`.
static func draw_flag(canvas: CanvasItem, foot: Vector2, height: float) -> void:
	var top := foot - Vector2(0, height)
	var cloth := PackedVector2Array([top,
		top + Vector2(height * FLAG_CLOTH_WIDTH, height * FLAG_CLOTH_TIP),
		top + Vector2(0, height * FLAG_CLOTH_DROP)])

	canvas.draw_line(foot, top, COLOR_FLAG_POLE, FLAG_POLE_WIDTH)
	canvas.draw_colored_polygon(cloth, COLOR_FLAG)


## Draw the walk path through `points`.
static func draw_path(canvas: CanvasItem, points: PackedVector2Array) -> void:
	canvas.draw_polyline(points, COLOR_PATH, PATH_WIDTH)


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


## Each map icon of the plane, except the kinds that the player hid in the
## legend.
func _draw_icons() -> void:
	var icon_px := clampf(_zoom * ICON_SHARE, ICON_MIN_PX, ICON_MAX_PX)
	var hidden_categories := _hidden_icons()

	for icon: Dictionary in _map.icons(_plane):
		var category: String = icon["category"]

		if hidden_categories.has(category):
			continue

		MapIcons.draw(_canvas, category, _tile_centre(icon["tile"]), icon_px)


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

	draw_self_mark(_canvas, _tile_centre(_state.current_cell), side)


func _draw_flag() -> void:
	if not _state.walk_on_current_plane():
		return

	var height := clampf(_zoom * FLAG_SHARE, FLAG_MIN_PX, FLAG_MAX_PX)

	draw_flag(_canvas, _tile_centre(_state.walk_goal), height)


func _draw_walk_path() -> void:
	if not _state.walk_on_current_plane() or _state.walk_path.is_empty():
		return

	var points := PackedVector2Array([_tile_centre(_state.current_cell)])

	for tile: Vector2i in _state.walk_path:
		points.append(_tile_centre(tile))

	draw_path(_canvas, points)


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
