extends Node
## Unit tests for WorldMapView: the maths of the pan, the zoom, and the
## planes, the floating box, and the legend.
##
##     godot --headless --path godot res://tests/test_world_map_view.tscn
##
## Needs nothing running. Drawing is not tested: headless, there is no canvas
## to read back. The maths that puts a tile on the screen is.

const Const := preload("res://autoload/blackout_constants.gd")

## Where the player stands: chunk (1, 0) of plane 0.
const HOME := Vector2i(70, 10)

## Disposable, rather than the real profile: the settings cases write here.
const SETTINGS_PATH := "user://test_world_map_view.cfg"

## A pane and a gap between the docks, as the console gives them.
const PANE := Vector2(1920, 1080)
const GAP_LEFT := 528.0
const GAP_RIGHT := 1452.0

var _failures := 0
var _map: WorldMapState
var _state: WorldState
var _view: WorldMapView


func _ready() -> void:
	_it_opens_on_the_player_and_the_plane_of_the_player()
	_a_tile_round_trips_through_the_canvas_at_each_zoom()
	_north_is_up()
	_a_zoom_keeps_the_point_under_the_cursor()
	_a_pan_stays_inside_the_world()
	_the_plane_steps_stop_at_the_ends()
	_a_second_open_keeps_the_view()
	_escape_closes_it()
	_it_is_a_floating_box_with_a_raised_grip_on_each_edge()
	_the_box_stays_inside_the_pane()
	_the_first_box_opens_between_the_docks()
	await _the_players_box_survives_the_client()
	_the_legend_names_each_map_icon_with_the_server_label()
	_a_legend_click_hides_that_kind_of_icon()
	_the_legend_button_shows_and_hides_the_legend()
	_the_legend_choices_live_in_the_settings()
	_the_walk_path_row_follows_options()

	_clean_settings()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: world_map_view")
	get_tree().quit(0)


func _fresh(settings: ClientSettings = null) -> void:
	if _view != null:
		_view.queue_free()

	_map = WorldMapState.new()
	_map.ingest_index({"planes": [0.0, 1.0], "labels": [], "chunks": [
		[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]})

	_state = WorldState.new()
	_state.ingest_room_info({"coords": [float(HOME.x), float(HOME.y),
		Const.TILE_WORLD_Z]})

	_view = WorldMapView.new()
	add_child(_view)
	_view.bind(_map, _state, settings)
	_view._canvas.size = Vector2(400, 300)


func _clean_settings() -> void:
	if FileAccess.file_exists(SETTINGS_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))


## The categories that have a map icon, in the order of the server. Derived,
## so a new category with an icon needs no edit here.
func _icon_categories() -> Array[String]:
	var found: Array[String] = []

	for category: String in Const.OBJECT_CATEGORIES:
		if MapIcons.has_icon(category):
			found.append(category)

	return found


func _it_opens_on_the_player_and_the_plane_of_the_player() -> void:
	_fresh()
	_view.open()

	_expect(_view.visible, "open shows the map")
	_expect(_view.plane() == 0, "on the plane of the player")
	_expect(_view.tile_at(_view._canvas.size * 0.5) == HOME,
		"with the player under the centre")


func _a_tile_round_trips_through_the_canvas_at_each_zoom() -> void:
	_fresh()
	_view.open()

	for step: int in WorldMapView.ZOOM_STEPS.size():
		for tile: Vector2i in [HOME, HOME + Vector2i(9, -4), Vector2i(3, 60)]:
			var point := _view.canvas_point(Vector2(tile) + Vector2.ONE * 0.5)

			if _view.tile_at(point) != tile:
				_fail("%s round-trips at zoom %d" % [tile, _view.zoom()])
				return

		_view.step_zoom(1)

	_pass("each tile round-trips through the canvas at each zoom")


func _north_is_up() -> void:
	_fresh()
	_view.open()

	var here := _view.canvas_point(Vector2(HOME))
	var north := _view.canvas_point(Vector2(HOME + Vector2i(0, 5)))

	_expect(north.y < here.y, "a higher grid Y is drawn further up")


func _a_zoom_keeps_the_point_under_the_cursor() -> void:
	_fresh()
	_view.open()

	var cursor := Vector2(90, 60)
	var before := _view.world_point_at(cursor)

	_view.zoom_at(cursor, 1)

	_expect(_view.world_point_at(cursor).is_equal_approx(before),
		"the world point under the cursor stays under it")


func _a_pan_stays_inside_the_world() -> void:
	_fresh()
	_view.open()
	_view.pan_by(Vector2(-100000, 100000))

	var rect := _map.bounds(0)
	var centre := _view.centre()

	_expect(centre.x <= rect.end.x and centre.y >= rect.position.y,
		"a pan past the edge stops at the edge")


func _the_plane_steps_stop_at_the_ends() -> void:
	_fresh()
	_view.open()

	_view.step_plane(1)
	_expect(_view.plane() == 1, "up goes to the plane above")

	_view.step_plane(1)
	_expect(_view.plane() == 1, "and stops at the top plane")

	_view.step_plane(-1)
	_view.step_plane(-1)
	_expect(_view.plane() == 0, "down stops at the lowest plane")


func _a_second_open_keeps_the_view() -> void:
	_fresh()
	_view.open()
	_view.pan_by(Vector2(40, 0))

	var moved := _view.centre()

	_view.open()
	_expect(_view.centre() == moved, "a second open does not recentre")


func _escape_closes_it() -> void:
	_fresh()
	_view.open()

	var escape := InputEventKey.new()

	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	_view._input(escape)

	_expect(not _view.visible, "Esc closes the map")


## Nick, 10/19/2026: the world map acts like the pop-up. The box is the same
## class, so a drag on any edge or corner sizes it, and no dock covers a grip.
func _it_is_a_floating_box_with_a_raised_grip_on_each_edge() -> void:
	_fresh()

	var grips := _view.grips()
	var expected := ResizeGrips.EDGES + ResizeGrips.CORNERS

	_expect(_view is FloatingBox, "the world map is a floating box")
	_expect(_view.title_text() == WorldMapView.TITLE_TEXT, "with its title")
	_expect(grips.offered().size() == expected.size(),
		"the box has a grip on every edge and every corner")

	for edges: int in expected:
		var grip := grips.grip(edges)
		_expect(grip != null and grip.top_level,
			"the grip for edges %d is raised" % edges)


func _the_box_stays_inside_the_pane() -> void:
	_fresh()
	_view.open()
	_view.size = PANE

	var pane := Rect2(Vector2.ZERO, PANE).grow(-FloatingBox.EDGE_MARGIN)

	_view.resize_box(PANE * 4.0)
	_expect(pane.encloses(_view.box_rect()), "a huge drag stops at the pane")

	_view.resize_box(Vector2.ONE)
	var small := _view.box_rect().size
	_expect(small.x >= FloatingBox.MIN_BOX_SIZE.x
		and small.y >= FloatingBox.MIN_BOX_SIZE.y,
		"a tiny drag stops at the smallest box")

	_view.move_box(Vector2(-400, 9000))
	_expect(pane.encloses(_view.box_rect()), "a move cannot push it out of the pane")


## The first box opens in the gap between the docks, as the pop-up does. The
## map is under the docks, so a box over a dock would hide a part of the map.
func _the_first_box_opens_between_the_docks() -> void:
	_fresh()
	_view.open()
	_view.size = PANE
	_view.set_dock_gap(GAP_LEFT, GAP_RIGHT)

	var box := _view.box_rect()

	_expect(is_equal_approx(box.get_center().x, (GAP_LEFT + GAP_RIGHT) / 2.0),
		"the first box is centred in the gap")
	_expect(box.position.x >= GAP_LEFT and box.end.x <= GAP_RIGHT,
		"and covers neither dock")


## The rect of the map survives the client, in its own setting. A map that
## shared the rect of the pop-up would move the bank.
func _the_players_box_survives_the_client() -> void:
	_clean_settings()
	var settings := ClientSettings.new(SETTINGS_PATH)
	settings.set_world_map_rect(Rect2(30, 40, 820, 520))

	_fresh(settings)
	_view.size = PANE
	_view.open()
	_view._place_box()

	_expect(_view.box_rect().position == Vector2(30, 40),
		"the map opens where the player left it")

	_view.resize_box(Vector2(640, 480))
	var ended := _view.box_rect()
	await get_tree().create_timer(FloatingBox.RECT_SAVE_DELAY + 0.2).timeout

	var reloaded := ClientSettings.new(SETTINGS_PATH)
	reloaded.load_from_disk()
	_expect(reloaded.world_map_rect == ended,
		"and a drag writes the rect the box ended at")
	_expect(reloaded.popup_rect == ClientSettings.DEFAULT_POPUP_RECT,
		"into the setting of the map, not of the pop-up")
	_clean_settings()


func _the_legend_names_each_map_icon_with_the_server_label() -> void:
	_fresh()

	var legend := _view.legend()

	_expect(legend.categories() == _icon_categories(),
		"the legend has one icon row for each category with a map icon")

	for category: String in legend.categories():
		_expect(WorldMapLegend.label_of(category)
			== str(Const.OBJECT_CATEGORY_LABELS[category]),
			"the %s row shows the label of the server" % category)


func _a_legend_click_hides_that_kind_of_icon() -> void:
	_fresh()

	var category := _icon_categories()[0]
	var box := _view.legend().check_box(category)

	_expect(box.button_pressed and _view.icon_shown(category),
		"every kind of icon shows at first")

	box.button_pressed = false
	_expect(not _view.icon_shown(category), "a click hides that kind of icon")

	for other: String in _icon_categories().slice(1):
		_expect(_view.icon_shown(other), "and no other kind (%s)" % other)

	box.button_pressed = true
	_expect(_view.icon_shown(category), "a second click shows it again")


func _the_legend_button_shows_and_hides_the_legend() -> void:
	_fresh()

	_expect(_view.legend_shown() and _view._legend_scroll.visible,
		"the legend shows at first")

	_view._legend_button.button_pressed = false
	_expect(not _view.legend_shown() and not _view._legend_scroll.visible,
		"the Legend button hides it")

	_view._legend_button.button_pressed = true
	_expect(_view._legend_scroll.visible, "and shows it again")


## With settings bound, the settings own both choices. A reload keeps them,
## and Reset in Options shows every icon and the legend again at once.
func _the_legend_choices_live_in_the_settings() -> void:
	_clean_settings()
	var settings := ClientSettings.new(SETTINGS_PATH)
	_fresh(settings)

	var category := _icon_categories()[0]

	_view.legend().check_box(category).button_pressed = false
	_view._legend_button.button_pressed = false
	_expect(settings.world_map_hidden_icons.has(category)
		and not settings.world_map_legend, "both choices reach the settings")

	settings.reset()
	_expect(_view.icon_shown(category)
		and _view.legend().check_box(category).button_pressed,
		"Reset shows the icon and checks its box again")
	_expect(_view._legend_scroll.visible and _view._legend_button.button_pressed,
		"and shows the legend again")
	_clean_settings()


## The map draws the walk path only while Options asks for it. The legend
## names only what the map can draw.
func _the_walk_path_row_follows_options() -> void:
	_clean_settings()
	var settings := ClientSettings.new(SETTINGS_PATH)
	_fresh(settings)

	settings.set_show_walk_path(false)
	_expect(not _view.legend().path_row_shown(),
		"with the walk path off, the legend has no walk path row")

	settings.set_show_walk_path(true)
	_expect(_view.legend().path_row_shown(), "with it on, the row shows")
	_clean_settings()


func _expect(passed: bool, what: String) -> void:
	if passed:
		_pass(what)
		return

	_fail(what)


func _pass(what: String) -> void:
	print("  ok   %s" % what)


func _fail(what: String) -> void:
	_failures += 1
	printerr("  FAIL %s" % what)
