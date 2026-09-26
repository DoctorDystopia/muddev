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
## minimap goes wrong: a map upside down against the 3D pane, or a click that
## walks the player to the wrong tile.

const Const := preload("res://autoload/blackout_constants.gd")

## The tile of the player, in chunk (0, 0), and a blocked tile near it.
const HOME := Vector2i(20, 30)
const BLOCKED := Vector2i(22, 31)

var _failures := 0
var _state: WorldState
var _map: MinimapView


func _ready() -> void:
	_the_cell_under_a_point_round_trips()
	_north_is_up()
	_the_window_follows_the_player()
	_a_click_on_a_far_tile_walks_there()
	_a_blocked_or_missing_tile_sends_nothing()
	_a_blocked_tile_is_drawn_darker()
	_the_pane_redraws_when_the_world_changes()

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
	_map = MinimapView.new()
	_map.size = Vector2(164, 164)
	add_child(_map)
	_map.bind(_state)

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
func _the_cell_under_a_point_round_trips() -> void:
	_fresh()

	var radius := MinimapView.WINDOW_RADIUS

	for offset: Vector2i in [Vector2i.ZERO, Vector2i(radius, radius),
			Vector2i(-radius, -radius), Vector2i(3, -7)]:
		var cell := HOME + offset

		if _map._to_cell(_centre_of(cell)) != cell:
			_fail("%s round-trips through its own centre" % cell)
			return

	_pass("each cell round-trips through its own drawn centre")


## Grid Y grows NORTHWARD and screen Y grows downward.
func _north_is_up() -> void:
	_fresh()

	var south := _centre_of(HOME)
	var north := _centre_of(HOME + Vector2i(0, 3))
	var east := _centre_of(HOME + Vector2i(3, 0))

	_expect(north.y < south.y, "a higher grid Y is drawn further up the pane")
	_expect(east.x > south.x, "and a higher grid X further to the right")


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

	var open := MinimapView.tile_colour(_state.chunks, HOME)
	var blocked := MinimapView.tile_colour(_state.chunks, BLOCKED)
	var missing := MinimapView.tile_colour(_state.chunks, Vector2i(-40, -40))

	_expect(open == FloorPalette.color_of(_state.chunks.get_floor(HOME)),
		"an open tile shows its floor colour")
	_expect(blocked.v < open.v, "a blocked tile is darker")
	_expect(missing.a == 0.0, "a tile with no chunk is not drawn")


func _the_pane_redraws_when_the_world_changes() -> void:
	# The pane holds no copy of the ground, so it has to be TOLD.
	_fresh()

	_expect(_state.chunks_changed.is_connected(_map.queue_redraw),
		"a chunk arriving redraws the pane")
	_expect(_state.room_changed.is_connected(_map.queue_redraw),
		"and so does a step to another tile")


## The centre of the drawn square of a cell, in pane coordinates.
func _centre_of(cell: Vector2i) -> Vector2:
	var cell_px := _map._cell_pixels()
	var origin := _map._origin(cell_px)

	return _map._to_pixels(cell, cell_px, origin) + Vector2.ONE * cell_px * 0.5


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
