extends Node
## Unit tests for MinimapView.
##
##     godot --headless --path godot res://tests/test_minimap_view.tscn
##
## Needs nothing running. Feeds a real [WorldState] the payloads the server
## sends and asks the pane where things are.
##
## Drawing is not tested -- there is nothing to read a canvas back from
## headless -- but every piece of MATHS behind the drawing is, because that is
## where a minimap goes wrong: a map upside down against the 3D pane, or a
## click that walks the player to the wrong tile.

const Const := preload("res://autoload/blackout_constants.gd")

## A three-by-three island whose coordinates deliberately do NOT start at the
## origin: xygrid coordinates are the map's own and nothing promises they do.
const ORIGIN_X := 4
const ORIGIN_Y := 7
const SPAN := 2

var _failures := 0
var _state: WorldState
var _map: MinimapView


func _ready() -> void:
	_the_cell_under_a_point_round_trips()
	_north_is_up()
	_a_click_sends_the_command_the_server_named()
	_a_cell_the_server_declined_sends_nothing()
	_the_pane_redraws_when_the_world_changes()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: minimap_view")
	get_tree().quit(0)


## A bound pane over a small map, sized so the maths has room to work.
func _fresh() -> void:
	if _map != null:
		_map.queue_free()

	_state = WorldState.new()
	_map = MinimapView.new()
	_map.size = Vector2(160, 160)
	add_child(_map)
	_map.bind(_state, null)

	var nodes: Array = []

	for dy: int in SPAN + 1:
		for dx: int in SPAN + 1:
			nodes.append({
				"x": float(ORIGIN_X + dx),
				"y": float(ORIGIN_Y + dy),
				"room_kind": "Bank",
			})

	_state.ingest(Const.CH_MAP, {
		"z": "oasis",
		"chunk_index": 0.0,
		"chunk_count": 1.0,
		"nodes": nodes,
		"links": [],
	})
	_state.ingest(Const.CH_ROOM_INFO, {
		"coords": [float(ORIGIN_X), float(ORIGIN_Y), "oasis"],
		"exits": {},
		"tile_actions": {},
	})


## Every cell must map to a point that maps back to the same cell.
##
## This is the whole of click-to-walk: the pane converts a cell to pixels to
## draw it and pixels back to a cell to act on it, and the two directions
## disagreeing is a map you can see but cannot click accurately.
func _the_cell_under_a_point_round_trips() -> void:
	_fresh()

	for dy: int in SPAN + 1:
		for dx: int in SPAN + 1:
			var cell := Vector2i(ORIGIN_X + dx, ORIGIN_Y + dy)
			var point := _centre_of(cell)

			if _map._to_cell(point) != cell:
				_fail("%s round-trips through its own centre" % cell)
				return

	_pass("every cell round-trips through its own drawn centre")


## Grid Y grows NORTHWARD and screen Y grows downward.
##
## Without the flip the minimap reads upside down against both the 3D pane --
## which makes the same correction with `-z` -- and the text map.
func _north_is_up() -> void:
	_fresh()

	var south := _centre_of(Vector2i(ORIGIN_X, ORIGIN_Y))
	var north := _centre_of(Vector2i(ORIGIN_X, ORIGIN_Y + SPAN))

	_expect(north.y < south.y, "a higher grid Y is drawn further up the pane")

	var west := _centre_of(Vector2i(ORIGIN_X, ORIGIN_Y))
	var east := _centre_of(Vector2i(ORIGIN_X + SPAN, ORIGIN_Y))

	_expect(east.x > west.x, "and a higher grid X further to the right")


func _a_click_sends_the_command_the_server_named() -> void:
	# Verbatim, and composed nowhere. Same contract as a clicked tile in the 3D
	# pane, because it is literally the same WorldState lookup.
	_fresh()

	var target := Vector2i(ORIGIN_X + 2, ORIGIN_Y + 1)
	var key := "%d:%d" % [target.x, target.y]

	_state.ingest(Const.CH_ROOM_INFO, {
		"coords": [float(ORIGIN_X), float(ORIGIN_Y), "oasis"],
		"exits": {},
		"tile_actions": {key: {"command": "goto (6,8)", "kind": "walk"}},
	})

	var sent: Array[String] = []
	_map.command_requested.connect(func(line): sent.append(line))

	_map._walk_to(target)

	_expect(sent.size() == 1 and sent[0] == "goto (6,8)",
		"the command reaches the console exactly as the server wrote it")


func _a_cell_the_server_declined_sends_nothing() -> void:
	# An empty command is the server saying no, and a cell it never mentioned
	# affords nothing. Neither is an error and neither is this pane's decision.
	_fresh()

	var sent: Array[String] = []
	_map.command_requested.connect(func(line): sent.append(line))

	_map._walk_to(Vector2i(ORIGIN_X + 1, ORIGIN_Y + 1))
	_expect(sent.is_empty(), "a cell with no action sends nothing")

	_map._walk_to(Vector2i(-40, -40))
	_expect(sent.is_empty(), "and neither does one off the map")


func _the_pane_redraws_when_the_world_changes() -> void:
	# The pane holds no copy of the map, so it has to be TOLD. Both signals
	# matter: the map arriving, and the player moving within it.
	_fresh()

	_expect(_state.map_ready.is_connected(_map._on_map_ready),
		"a completed map redraws the pane")
	_expect(_state.room_changed.is_connected(_map.queue_redraw),
		"and so does stepping to another room")


## The centre of a cell's drawn square, in pane coordinates.
func _centre_of(cell: Vector2i) -> Vector2:
	var level := _map._level()
	var bounds := _map._bounds(level)
	var cell_px := _map._cell_pixels(bounds)
	var origin := _map._origin(bounds, cell_px)

	return _map._to_pixels(cell, bounds, cell_px, origin) \
		+ Vector2.ONE * cell_px * 0.5


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
