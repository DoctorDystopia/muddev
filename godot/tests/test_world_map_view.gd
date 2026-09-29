extends Node
## Unit tests for WorldMapView: the maths of the pan, the zoom, and the planes.
##
##     godot --headless --path godot res://tests/test_world_map_view.tscn
##
## Needs nothing running. Drawing is not tested: headless, there is no canvas
## to read back. The maths that puts a tile on the screen is.

const Const := preload("res://autoload/blackout_constants.gd")

## Where the player stands: chunk (1, 0) of plane 0.
const HOME := Vector2i(70, 10)

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

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: world_map_view")
	get_tree().quit(0)


func _fresh() -> void:
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
	_view.bind(_map, _state)
	_view._canvas.size = Vector2(400, 300)


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
