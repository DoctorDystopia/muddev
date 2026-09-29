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
	# The pane holds no copy of the ground, so it has to be TOLD.
	_fresh()

	_expect(_state.chunks_changed.is_connected(_map.queue_redraw),
		"a chunk arriving redraws the pane")
	_expect(_state.room_changed.is_connected(_map.queue_redraw),
		"and so does a step to another tile")
	_expect(_state.walk_changed.is_connected(_map.queue_redraw),
		"and so does a change of the walk")
	_expect(_roster.changed.is_connected(_map.queue_redraw),
		"and so does an entity message")


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
