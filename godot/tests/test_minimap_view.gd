extends Node
## Unit tests for MinimapView on the tile world.
##
##     godot --headless --path godot res://tests/test_minimap_view.tscn
##
## Needs nothing running. Feeds a real [WorldState] a chunk payload and a
## room, and asks the pane where things are.
##
## Drawing is not tested: headless, there is no canvas to read back. Every
## piece of MATHS behind the drawing is tested, because that is where a
## minimap goes wrong: a map upside down against the 3D pane, a click that
## walks the player to the wrong tile, or a dot on the wrong tile.

const Const := preload("res://autoload/blackout_constants.gd")

## The tile of the player, in chunk (0, 0), and a blocked tile near it.
const HOME := Vector2i(20, 30)
const BLOCKED := Vector2i(22, 31)

## The settings file of the turn cases, removed after each.
const TURN_SETTINGS_PATH := "user://test_minimap_turn.cfg"

var _failures := 0
var _state: WorldState
var _roster: EntityRoster
var _map: MinimapView


func _ready() -> void:
	_the_cell_under_a_point_round_trips_at_each_zoom()
	_north_is_up_at_each_zoom()
	_the_window_follows_the_player()
	_a_click_on_a_far_tile_walks_there()
	_a_blocked_or_missing_tile_sends_nothing()
	_a_blocked_tile_is_drawn_darker()
	_the_pane_redraws_when_the_world_changes()
	_the_zoom_steps_in_and_out_and_stops_at_the_ends()
	_the_mouse_wheel_zooms()
	_a_saved_radius_snaps_to_a_step()
	_the_zoom_and_the_path_toggle_are_saved()
	_a_dot_stands_on_the_tile_of_its_entity()
	_a_dot_off_the_plane_or_out_of_the_window_is_not_drawn()
	_the_world_map_button_asks_for_the_world_map()
	_the_run_button_follows_the_walk_feed()
	_a_press_of_run_sends_the_toggle_and_keeps_the_fact()
	_a_ctrl_click_on_the_map_swaps_walk_and_run()
	_the_xy_button_shows_the_position_readout()
	_the_position_readout_follows_the_player()
	_the_xy_choice_lives_in_the_settings()
	_the_map_keeps_north_up_until_the_player_asks()
	_the_map_turns_with_the_camera_when_the_player_asks()
	_a_click_on_a_turned_map_lands_on_the_tile_under_the_cursor()
	_the_compass_points_to_north_on_the_drawn_map()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: minimap_view")
	get_tree().quit(0)


## A bound pane over one chunk, sized so the maths has room to work.
func _fresh() -> void:
	if _map != null:
		_map.queue_free()

	_state = WorldState.new()
	_roster = EntityRoster.new()
	_map = MinimapView.new()
	_map.size = Vector2(164, 164 + MinimapView.STRIP_HEIGHT)
	add_child(_map)
	_map.bind(_state)
	_map.bind_entities(_roster)

	var chunk := ChunkFile.blank(0, 0)

	chunk.flags[BLOCKED.y * Const.CHUNK_SIZE + BLOCKED.x] = Const.TILE_FLAG_BLOCKED
	_state.ingest(Const.CH_TILE_CHUNK,
		{"chunk_file": JSON.parse_string(chunk.to_text())})
	_stand(HOME)


func _stand(tile: Vector2i) -> void:
	_state.ingest(Const.CH_ROOM_INFO, {
		"coords": [float(tile.x), float(tile.y), Const.TILE_WORLD_Z],
		"exits": {},
		"tile_actions": {},
	})


## Every cell of the window maps to a point that maps back to the same cell.
## This is the whole of click-to-walk.
func _the_cell_under_a_point_round_trips_at_each_zoom() -> void:
	_fresh()

	for step: int in MinimapView.ZOOM_RADII:
		_set_radius(step)

		for offset: Vector2i in [Vector2i.ZERO, Vector2i(step, step),
				Vector2i(-step, -step), Vector2i(3, -7)]:
			var cell := HOME + offset

			if _map._to_cell(_centre_of(cell)) != cell:
				_fail("%s round-trips at radius %d" % [cell, step])
				return

	_pass("each cell round-trips through its own centre at each zoom")


## Grid Y grows NORTHWARD and screen Y grows downward.
func _north_is_up_at_each_zoom() -> void:
	_fresh()

	for step: int in MinimapView.ZOOM_RADII:
		_set_radius(step)

		var south := _centre_of(HOME)
		var north := _centre_of(HOME + Vector2i(0, 3))
		var east := _centre_of(HOME + Vector2i(3, 0))

		if not (north.y < south.y and east.x > south.x):
			_fail("north is up and east is right at radius %d" % step)
			return

	_pass("north is up and east is right at each zoom")


func _the_window_follows_the_player() -> void:
	_fresh()

	var before := _centre_of(HOME)

	_stand(HOME + Vector2i(5, 0))

	var after := _centre_of(HOME + Vector2i(5, 0))

	_expect(before.is_equal_approx(after),
		"the player tile is drawn in the same place after a move")


func _a_click_on_a_far_tile_walks_there() -> void:
	_fresh()

	var target := HOME + Vector2i(6, -4)
	var expected := Const.TILE_WALK_TEMPLATE \
		.replace("{x}", str(target.x)).replace("{y}", str(target.y))
	var sent: Array[String] = []

	_map.command_requested.connect(func(line): sent.append(line))
	_map._walk_to(target)

	_expect(sent.size() == 1 and sent[0] == expected,
		"the walk the server spelled reaches the console")


func _a_blocked_or_missing_tile_sends_nothing() -> void:
	_fresh()

	var sent: Array[String] = []

	_map.command_requested.connect(func(line): sent.append(line))
	_map._walk_to(BLOCKED)
	_expect(sent.is_empty(), "a blocked tile sends nothing")

	_map._walk_to(Vector2i(-40, -40))
	_expect(sent.is_empty(), "and neither does a tile with no chunk")


func _a_blocked_tile_is_drawn_darker() -> void:
	_fresh()

	var open := MapRaster.chunk_set_colour(_state.chunks, HOME)
	var blocked := MapRaster.chunk_set_colour(_state.chunks, BLOCKED)
	var missing := MapRaster.chunk_set_colour(_state.chunks, Vector2i(-40, -40))

	_expect(open == FloorPalette.color_of(_state.chunks.get_floor(HOME)),
		"an open tile shows its floor colour")
	_expect(blocked.v < open.v, "a blocked tile is darker")
	_expect(missing.a == 0.0, "a tile with no chunk is not drawn")

	var image := MapRaster.chunk_image(_state.chunks.get_chunk(Vector2i.ZERO))
	var top: int = Const.CHUNK_SIZE - 1

	_expect(_near(image.get_pixel(BLOCKED.x, top - BLOCKED.y), blocked),
		"the chunk image has the same colour, with row 0 north")


func _the_pane_redraws_when_the_world_changes() -> void:
	# The pane holds no copy of the ground, so it has to be TOLD. The child
	# window draws the map, so the pane routes each change through _redraw.
	_fresh()

	_expect(_state.chunks_changed.is_connected(_map._redraw),
		"a chunk arriving redraws the pane")
	_expect(_state.room_changed.is_connected(_map._redraw),
		"and so does a step to another tile")
	_expect(_state.walk_changed.is_connected(_map._redraw),
		"and so does a change of the walk")
	_expect(_roster.changed.is_connected(_map._redraw),
		"and so does an entity message")
	_expect(_map._window.draw.is_connected(_map._draw_window),
		"and the window draws the map")


func _the_zoom_steps_in_and_out_and_stops_at_the_ends() -> void:
	_fresh()

	var steps := MinimapView.ZOOM_RADII
	var start := _map.radius()
	var at := steps.find(start)

	_map.zoom_in()
	_expect(_map.radius() == steps[at - 1], "zoom in shows fewer tiles")

	_map.zoom_out()
	_map.zoom_out()
	_expect(_map.radius() == steps[at + 1], "zoom out shows more tiles")

	for _i: int in steps.size():
		_map.zoom_out()

	_expect(_map.radius() == steps[steps.size() - 1],
		"zoom out stops at the widest step")

	for _i: int in steps.size():
		_map.zoom_in()

	_expect(_map.radius() == steps[0], "zoom in stops at the closest step")


func _the_mouse_wheel_zooms() -> void:
	_fresh()

	var start := _map.radius()
	var wheel := InputEventMouseButton.new()

	wheel.button_index = MOUSE_BUTTON_WHEEL_UP
	wheel.pressed = true
	wheel.position = _map.map_rect().get_center()
	_map._gui_input(wheel)

	_expect(_map.radius() < start, "the wheel up zooms in")


func _a_saved_radius_snaps_to_a_step() -> void:
	_expect(MinimapView.nearest_zoom(21) == 20, "21 snaps to 20")
	_expect(MinimapView.nearest_zoom(1) == MinimapView.ZOOM_RADII[0],
		"a radius under the steps snaps to the closest step")
	_expect(MinimapView.nearest_zoom(999) == MinimapView.ZOOM_RADII[-1],
		"a radius over the steps snaps to the widest step")


func _the_zoom_and_the_path_toggle_are_saved() -> void:
	_fresh()

	var path := "user://test_minimap_settings.cfg"
	var settings := ClientSettings.new(path)

	_map.bind_settings(settings)
	_map.zoom_out()
	_expect(settings.minimap_radius == _map.radius(),
		"a zoom from the pane reaches the settings")

	settings.set_minimap_radius(MinimapView.ZOOM_RADII[0])
	_expect(_map.radius() == MinimapView.ZOOM_RADII[0],
		"a zoom from the settings reaches the pane")

	settings.set_show_walk_path(true)
	_expect(_map._show_path, "the walk path setting from Options reaches the pane")

	var labels: Array[String] = []

	for button: Node in _map.get_node("Strip").get_children():
		labels.append((button as Button).text)

	_expect(labels == ["-", "+", "Map"],
		"the strip holds only the zoom and the world map buttons")

	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))


func _a_dot_stands_on_the_tile_of_its_entity() -> void:
	_fresh()

	var npc_tile := HOME + Vector2i(3, 2)

	_roster.ingest(Const.CH_ROOM_PLAYERS, {"entities": [
		_entity(1, Const.FAMILY_NPC, npc_tile),
		_entity(2, Const.FAMILY_CHARACTER, HOME + Vector2i(-1, 0)),
	]})

	_expect(_map.dot_tiles(Const.FAMILY_NPC) == [npc_tile],
		"an NPC dot stands on the tile of the NPC")
	_expect(_map.dot_tiles(Const.FAMILY_CHARACTER).size() == 1,
		"another player gets a dot of its own kind")
	_expect(_map.dot_tiles(Const.FAMILY_ITEM).is_empty(),
		"a kind with no entity has no dot")


func _a_dot_off_the_plane_or_out_of_the_window_is_not_drawn() -> void:
	_fresh()

	var upper := WorldState.plane_z(1)
	var far := HOME + Vector2i(_map.radius() + 1, 0)

	_roster.ingest(Const.CH_ROOM_PLAYERS, {"entities": [
		_entity(1, Const.FAMILY_NPC, HOME + Vector2i(1, 1), upper),
		_entity(2, Const.FAMILY_NPC, far),
	]})

	_expect(_map.dot_tiles(Const.FAMILY_NPC).is_empty(),
		"no dot for an entity on another plane or past the window")


func _the_world_map_button_asks_for_the_world_map() -> void:
	_fresh()

	var asked: Array[bool] = []

	_map.world_map_requested.connect(func(): asked.append(true))
	_map._world_map_button.pressed.emit()

	_expect(asked.size() == 1, "the world map button asks the console")


func _the_run_button_follows_the_walk_feed() -> void:
	_fresh()

	_expect(not _map.run_shown(), "run shows off before the feed says")

	_state.ingest(Const.CH_WALK, {"goal": [], "path": [], "running": true})
	_expect(_map.run_shown(), "the feed turns the Run button on")

	_state.ingest(Const.CH_WALK, {"goal": [], "path": [], "running": false})
	_expect(not _map.run_shown(), "and off again")


func _a_press_of_run_sends_the_toggle_and_keeps_the_fact() -> void:
	_fresh()

	var sent: Array[String] = []

	_map.command_requested.connect(func(line): sent.append(line))
	_map._run_button.button_pressed = true
	_map._run_button.pressed.emit()

	_expect(sent == [Const.RUN_TOGGLE_COMMAND], "a press sends the run command")
	_expect(not _map.run_shown(),
		"the button shows the server fact until the feed answers")


## A Ctrl + left click on the map sends the paced walk, at the pace that is
## not the toggle. With the option off, it is a plain click.
func _a_ctrl_click_on_the_map_swaps_walk_and_run() -> void:
	_fresh()

	var path := "user://test_minimap_ctrl_settings.cfg"
	var settings := ClientSettings.new(path)
	var target := HOME + Vector2i(6, -4)
	var paced := Const.TILE_PACED_WALK_TEMPLATE \
		.replace("{x}", str(target.x)).replace("{y}", str(target.y))
	var plain := Const.TILE_WALK_TEMPLATE \
		.replace("{x}", str(target.x)).replace("{y}", str(target.y))
	var sent: Array[String] = []

	# Set, not read from the default, so a change of the default breaks
	# nothing here.
	settings.set_ctrl_click_swaps_run(true)
	_map.bind_settings(settings)
	_map.command_requested.connect(func(line): sent.append(line))
	_state.ingest(Const.CH_WALK, {"goal": [], "path": [], "running": true})
	_map._gui_input(_left_click(_centre_of(target), true))

	_expect(sent == [paced.replace("{pace}", Const.GOTO_PACE_WALK)],
		"with run on, a Ctrl click walks there")

	settings.set_ctrl_click_swaps_run(false)
	_map._gui_input(_left_click(_centre_of(target), true))

	_expect(sent.size() == 2 and sent[1] == plain,
		"with the option off, a Ctrl click is a plain click")

	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))


## The XY button is a toggle of the pane, not of the strip. Set, not read from
## the default, so a change of the default breaks nothing here.
func _the_xy_button_shows_the_position_readout() -> void:
	_fresh()
	_map.set_coordinates_shown(false)

	_expect(_map.coordinates_text().is_empty(), "with XY off, the pane writes nothing")
	_expect(_map._coordinates_button.get_parent() == _map,
		"the XY button sits on the map square, not on the strip")

	_map._coordinates_button.button_pressed = true
	_expect(_map.coordinates_shown(), "a press of XY turns the readout on")
	_expect(_map.coordinates_text() == _words(HOME, Const.TILE_GROUND_PLANE),
		"and the pane writes the tile and the plane of the player")

	_map._coordinates_button.button_pressed = false
	_expect(_map.coordinates_text().is_empty(), "a second press turns it off")


func _the_position_readout_follows_the_player() -> void:
	_fresh()
	_map.set_coordinates_shown(true)

	var next := HOME + Vector2i(4, -2)

	_stand(next)
	_expect(_map.coordinates_text() == _words(next, Const.TILE_GROUND_PLANE),
		"a step to another tile changes the readout")

	_state.ingest(Const.CH_ROOM_INFO, {
		"coords": [float(next.x), float(next.y), WorldState.plane_z(1)]})
	_expect(_map.coordinates_text() == _words(next, 1),
		"a climb to another plane changes the plane in the readout")

	_state.ingest(Const.CH_ROOM_INFO, {"coords": [0.0, 0.0, "not_a_plane"]})
	_expect(_map.coordinates_text().is_empty(),
		"off the tile world, the readout is empty")


## One setting serves both maps. The world map test checks the other half.
func _the_xy_choice_lives_in_the_settings() -> void:
	_fresh()

	var path := "user://test_minimap_xy_settings.cfg"
	var settings := ClientSettings.new(path)

	settings.set_show_coordinates(false)
	_map.bind_settings(settings)
	_map._coordinates_button.button_pressed = true
	_expect(settings.show_coordinates, "a press of XY reaches the settings")

	settings.set_show_coordinates(false)
	_expect(not _map.coordinates_shown()
		and not _map._coordinates_button.button_pressed,
		"a change in the settings reaches the pane and its button")

	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))


## The words that the readout must show for a tile on a plane.
## Off by default: a heading changes nothing until the option is on.
func _the_map_keeps_north_up_until_the_player_asks() -> void:
	_fresh()

	var settings := _bound_settings()
	var east := HOME + Vector2i(3, 0)

	_expect(not _map.rotates() and not settings.minimap_rotates,
		"the minimap keeps north up by default")

	_map.set_heading(Vector2(1.0, 0.0))

	var player := _map.drawn_point_of(HOME)
	var drawn := _map.drawn_point_of(east)

	_expect(is_zero_approx(_map.heading_angle()),
		"a camera to the east turns nothing while the option is off")
	_expect(drawn.x > player.x and is_equal_approx(drawn.y, player.y),
		"and the east tile stays to the right of the player")

	_drop_settings(settings)


## With the option on, the way the camera looks is at the top. The player
## stays at the centre, and the drawn points come back when the option goes
## off again.
func _the_map_turns_with_the_camera_when_the_player_asks() -> void:
	_fresh()

	var settings := _bound_settings()
	var east := HOME + Vector2i(3, 0)
	var north := HOME + Vector2i(0, 3)
	var player := _map.drawn_point_of(HOME)

	settings.set_minimap_rotates(true)
	_map.set_heading(Vector2(1.0, 0.0))

	var drawn_east := _map.drawn_point_of(east)
	var drawn_north := _map.drawn_point_of(north)

	_expect(_map.rotates(), "the option from Options reaches the pane")
	_expect(_map.drawn_point_of(HOME).is_equal_approx(player),
		"the player stays at the centre of a turned map")
	_expect(drawn_east.y < player.y and is_equal_approx(drawn_east.x, player.x),
		"the east tile stands above the player with the camera to the east")
	_expect(drawn_north.x < player.x and is_equal_approx(drawn_north.y, player.y),
		"and the north tile stands to the left")
	_expect(_map._drawn_radius() > _map.radius(),
		"the ground reaches past the square, to fill the turned corners")

	_map.set_heading(Vector2(0.0, 1.0))
	_expect(is_zero_approx(_map.heading_angle()),
		"a camera to the north turns nothing")

	_map.set_heading(Vector2(1.0, 0.0))
	settings.set_minimap_rotates(false)
	_expect(_map.drawn_point_of(east).x > player.x,
		"the option off puts north up again, with the heading kept")

	_drop_settings(settings)


## A click on a turned map walks to the tile the player sees under the
## cursor, at each zoom.
func _a_click_on_a_turned_map_lands_on_the_tile_under_the_cursor() -> void:
	_fresh()

	var settings := _bound_settings()

	settings.set_minimap_rotates(true)
	_map.set_heading(Vector2(0.6, -0.8))

	for step: int in MinimapView.ZOOM_RADII:
		_set_radius(step)

		for offset: Vector2i in [Vector2i.ZERO, Vector2i(step, 0),
				Vector2i(0, -step), Vector2i(3, -7)]:
			var cell := HOME + offset

			if _map._to_cell(_map.drawn_point_of(cell)) != cell:
				_fail("%s round-trips on a turned map at radius %d" % [cell, step])
				_drop_settings(settings)
				return

	_pass("each cell round-trips through its drawn centre on a turned map")

	var sent: Array[String] = []
	_map.command_requested.connect(func(line): sent.append(line))
	_set_radius(MinimapView.ZOOM_RADII[0])

	var goal := HOME + Vector2i(2, 3)
	_map._gui_input(_left_click(_map.drawn_point_of(goal), false))

	_expect(sent == [_state.click_command(goal)],
		"a click on a turned map walks to the tile under the cursor")

	_drop_settings(settings)


## The needle points up with north up, and turns with the ground. The
## compass sits on the map square, between the Run and XY buttons.
func _the_compass_points_to_north_on_the_drawn_map() -> void:
	_fresh()

	var settings := _bound_settings()
	var centre := _map.compass_centre()
	var letter_top := centre.y - MinimapView.COMPASS_RADIUS - MinimapView.COMPASS_REACH

	_expect(_map.compass_needle().is_equal_approx(Vector2.UP),
		"with north up, the needle points up")
	_expect(_map.map_rect().has_point(centre) and letter_top >= 0.0,
		"the compass and its letter sit on the map square")
	_expect(centre.x > _map._run_button.get_rect().end.x
		and centre.x < _map._coordinates_button.get_rect().position.x,
		"between the Run and XY buttons")

	settings.set_minimap_rotates(true)
	_map.set_heading(Vector2(1.0, 0.0))

	_expect(_map.compass_needle().is_equal_approx(Vector2.LEFT),
		"with the camera to the east, the needle points left, where north is drawn")
	_expect(_map.compass_centre().is_equal_approx(centre),
		"and the compass itself stays put")

	_drop_settings(settings)


## A settings file of this test, bound to the pane.
func _bound_settings() -> ClientSettings:
	var settings := ClientSettings.new(TURN_SETTINGS_PATH)

	_map.bind_settings(settings)

	return settings


func _drop_settings(_settings: ClientSettings) -> void:
	DirAccess.remove_absolute(ProjectSettings.globalize_path(TURN_SETTINGS_PATH))


func _words(tile: Vector2i, plane: int) -> String:
	return MinimapView.COORDINATES_TEMPLATE % [tile.x, tile.y, plane]


func _left_click(point: Vector2, ctrl: bool) -> InputEventMouseButton:
	var click := InputEventMouseButton.new()

	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	click.position = point
	click.ctrl_pressed = ctrl

	return click


func _entity(id: int, kind: String, tile: Vector2i,
		z: String = Const.TILE_WORLD_Z) -> Dictionary:
	return {"id": float(id), "kind": kind,
		"coords": [float(tile.x), float(tile.y), z]}


func _set_radius(step: int) -> void:
	while _map.radius() < step:
		_map.zoom_out()

	while _map.radius() > step:
		_map.zoom_in()


## The centre of the drawn square of a cell, in pane coordinates.
func _centre_of(cell: Vector2i) -> Vector2:
	var cell_px := _map._cell_pixels()
	var origin := _map._origin(cell_px)

	return _map._to_pixels(cell, cell_px, origin) + Vector2.ONE * cell_px * 0.5


## Two colours within one step of an 8-bit channel. An image stores 8 bits.
func _near(first: Color, second: Color) -> bool:
	var step := 1.0 / 255.0

	return absf(first.r - second.r) <= step and absf(first.g - second.g) <= step \
		and absf(first.b - second.b) <= step and absf(first.a - second.a) <= step


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
