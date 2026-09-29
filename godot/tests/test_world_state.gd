extends Node
## Unit tests for WorldState on the tile world. Needs no server and no
## account. Each chunk payload below is the JSON of a real chunk file, parsed
## the way Godot parses the feed: every number arrives as a FLOAT.
##
##     godot --headless --path godot res://tests/test_world_state.tscn
##
## Exits 0 when every case passes, 1 on the first failure.

const _Const := preload("res://autoload/blackout_constants.gd")

## A tile of chunk (0, 0), and a blocked tile beside it.
const _HOME := Vector2i(5, 5)
const _BLOCKED := Vector2i(9, 9)

var _failures := 0


func _ready() -> void:
	_floats_become_ints()
	_a_chunk_lands_in_the_set()
	_a_bad_chunk_is_refused()
	_ground_waits_for_the_chunk_under_you()
	_a_move_frees_the_chunks_outside_the_block()
	_the_ground_height_is_read_from_the_chunk()
	_the_server_decides_what_a_near_tile_affords()
	_a_far_tile_walks_by_the_server_template()
	_the_hash_matches_the_browser()
	_the_plane_comes_from_the_room_z()
	_each_plane_keeps_its_own_chunks()
	_a_figure_stands_on_the_ground_of_its_plane()
	_a_move_frees_far_chunks_on_every_plane()
	_a_walk_records_its_goal_and_path()
	_a_step_drops_the_walked_tiles()
	_a_walk_whose_first_step_already_landed_starts_trimmed()
	_an_empty_goal_ends_the_walk()
	_a_walk_on_another_plane_is_not_on_this_one()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: world_state")
	get_tree().quit(0)


# ─── Cases ───────────────────────────────────────────────────────────────────

func _floats_become_ints() -> void:
	# The failure this guards against is silent: a cell keyed on 3.0 never
	# matches one written as 3, and nothing raises.
	var state := WorldState.new()

	state.ingest_room_info({"coords": [7.0, 2.0, _Const.TILE_WORLD_Z]})

	_expect(state.current_cell == Vector2i(7, 2), "current cell is an int vector")
	_expect(state.on_tile_world(), "the tile world z is recognised")

	state.ingest_room_info({})

	_expect(state.current_cell == Vector2i(7, 2),
		"a malformed room leaves the last one standing")


func _a_chunk_lands_in_the_set() -> void:
	var state := WorldState.new()
	var heard := [0]

	state.chunks_changed.connect(func() -> void: heard[0] += 1)

	var routed := state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(0, 0)))

	_expect(routed, "blackout_chunk is a WorldState channel")
	_expect(state.chunks.has_chunk(Vector2i(0, 0)), "the chunk is in the set")
	_expect(heard[0] == 1, "a new chunk says so one time")


func _a_bad_chunk_is_refused() -> void:
	var state := WorldState.new()
	var payload := _payload(ChunkFile.blank(0, 0))

	payload["chunk_file"]["format"] = 99.0

	_expect(not state.ingest_chunk(payload), "a bad chunk is refused")
	_expect(not state.last_chunk_error.is_empty(), "the reason is kept")
	_expect(state.chunks.chunk_coords().is_empty(), "the set is unchanged")


func _ground_waits_for_the_chunk_under_you() -> void:
	var state := WorldState.new()

	state.ingest_room_info({"coords": [5.0, 5.0, "oasis"]})

	_expect(not state.has_ground(), "an xyzgrid map has no ground")

	state.ingest_room_info({"coords": [5.0, 5.0, _Const.TILE_WORLD_Z]})

	_expect(not state.has_ground(), "no ground before the chunk lands")

	state.ingest_chunk(_payload(ChunkFile.blank(0, 0)))

	_expect(state.has_ground(), "ground once the chunk under you lands")


func _a_move_frees_the_chunks_outside_the_block() -> void:
	var state := WorldState.new()
	var far := Vector2i(_Const.CHUNK_STREAM_RADIUS + 2, 0)
	var heard := [0]

	state.ingest_chunk(_payload(ChunkFile.blank(0, 0)))
	state.ingest_chunk(_payload(ChunkFile.blank(far.x, far.y)))
	state.chunks_changed.connect(func() -> void: heard[0] += 1)
	state.ingest(_Const.CH_ROOM_INFO,
		{"coords": [5.0, 5.0, _Const.TILE_WORLD_Z]})

	_expect(state.chunks.has_chunk(Vector2i(0, 0)), "the home chunk stays")
	_expect(not state.chunks.has_chunk(far), "a chunk past the block goes")
	_expect(heard[0] == 1, "the free says so")
	_expect(WorldState.block_of(_HOME).size()
			== (_Const.CHUNK_STREAM_RADIUS * 2 + 1) ** 2,
		"the block is square, of the stream radius")


func _the_ground_height_is_read_from_the_chunk() -> void:
	var state := WorldState.new()
	var chunk := ChunkFile.blank(0, 0)
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE

	# Raise the four corners of the home tile by the same step.
	for corner: Vector2i in [_HOME, _HOME + Vector2i(1, 0), _HOME + Vector2i(0, 1),
			_HOME + Vector2i(1, 1)]:
		chunk.heights[corner.y * side + corner.x] = 8

	_expect(state.ground_y(_HOME) == null, "no height before the chunk lands")

	state.ingest_chunk(_payload(chunk))

	_expect(is_equal_approx(float(state.ground_y(_HOME)),
			8.0 * ChunkMeshBuilder.HEIGHT_STEP),
		"the height is the drawn ground, in world units")


## The client reads the server answer for a near tile, and does not compute
## one. The ABSENT/EMPTY distinction is the part worth keeping.
func _the_server_decides_what_a_near_tile_affords() -> void:
	var state := _standing_state()

	state.ingest_room_info({
		"coords": [5.0, 5.0, _Const.TILE_WORLD_Z],
		"tile_actions": {
			"5:6": {"command": "north", "kind": "step"},
			"6:5": {"command": "", "kind": "none"},
			"5:5": {"command": "look", "kind": "look"},
		},
		"cancel_action": {"command": "goto", "kind": "cancel"},
	})

	_expect(state.tile_action(Vector2i(5, 6)).get("command", "") == "north",
		"a near tile sends the command the server named")
	_expect(state.tile_action(_HOME).get("command", "") == "look",
		"your own tile looks")
	_expect(state.tile_action(Vector2i(6, 5)).is_empty(),
		"an empty command is refused, not fallen through")
	_expect(state.current_cancel_action.get("command", "") == "goto",
		"cancel_action is kept for whoever adds walk tracking")


func _a_far_tile_walks_by_the_server_template() -> void:
	var state := _standing_state()
	var far := Vector2i(30, 12)
	var expected := _Const.TILE_WALK_TEMPLATE \
		.replace("{x}", str(far.x)).replace("{y}", str(far.y))
	var walk := state.tile_action(far)

	_expect(walk.get("command", "") == expected,
		"a far walkable tile sends the walk the server spelled")
	_expect(walk.get("kind", "") == _Const.KIND_WALK, "and it is a walk")
	_expect(state.tile_action(_BLOCKED).is_empty(), "a blocked tile affords nothing")
	_expect(state.tile_action(Vector2i(-40, -40)).is_empty(),
		"a tile with no chunk affords nothing")

	state.ingest_room_info({"coords": [5.0, 5.0, "oasis"]})

	_expect(state.tile_action(far).is_empty(), "off the tile world, no walk")


func _the_hash_matches_the_browser() -> void:
	# Expected values come from the hashString algorithm of blackout3d.js.
	var vectors := {
		"Oasis": 75961771,
		"Oasis Outskirts": 101684281,
		"Trade Town Sector 1": 313616919,
		"20743": 47660536,
	}

	for text: String in vectors:
		_expect(StableHash.of(text) == vectors[text],
			"StableHash.of(%s) matches blackout3d.js" % text)


# ─── Private helpers ─────────────────────────────────────────────────────────

## A chunk file as the feed sends it: the JSON of its text, parsed by Godot.
func _the_plane_comes_from_the_room_z() -> void:
	# Phase 7b. The twin of `planes.plane_of_z` in Python.
	_expect(WorldState.plane_of_z(_Const.TILE_WORLD_Z) == 0, "the world Z is plane 0")
	_expect(WorldState.plane_of_z(_Const.TILE_WORLD_Z + "_p2") == 2,
		"the template gives plane 2")
	_expect(WorldState.plane_of_z(_Const.TILE_WORLD_Z + "_pool") == -1,
		"a pool Z is no plane")
	_expect(WorldState.plane_of_z(WorldState.plane_z(_Const.CHUNK_PLANE_MAX + 1)) == -1,
		"a plane past the top is no plane")

	var state := WorldState.new()

	state.ingest_room_info({"coords": [1.0, 1.0, WorldState.plane_z(1)]})

	_expect(state.current_plane == 1, "the room Z sets the plane")
	_expect(state.on_tile_world(), "plane 1 is on the tile world")


func _each_plane_keeps_its_own_chunks() -> void:
	var state := WorldState.new()
	var upper := ChunkFile.blank(0, 0, 1)

	upper.floors.fill(0)
	upper.floor_names = PackedStringArray([_Const.TILE_VOID_FLOOR])
	state.ingest_chunk(_payload(ChunkFile.blank(0, 0)))
	state.ingest_chunk(_payload(upper))
	state.ingest_room_info({"coords": [_HOME.x, _HOME.y, _Const.TILE_WORLD_Z]})

	_expect(str(state.planes_held()) == "[0, 1]", "both planes are held")
	_expect(state.chunks.get_floor(_HOME) == _Const.TILE_DEFAULT_FLOOR,
		"on plane 0 the reads see plane 0")

	state.ingest_room_info({"coords": [_HOME.x, _HOME.y, WorldState.plane_z(1)]})

	_expect(state.chunks.get_floor(_HOME) == _Const.TILE_VOID_FLOOR,
		"after a climb the reads see plane 1")


func _a_figure_stands_on_the_ground_of_its_plane() -> void:
	var state := WorldState.new()
	var upper := ChunkFile.blank(0, 0, 1)

	upper.heights.fill(32)
	state.ingest_chunk(_payload(ChunkFile.blank(0, 0)))
	state.ingest_chunk(_payload(upper))
	state.ingest_room_info({"coords": [_HOME.x, _HOME.y, _Const.TILE_WORLD_Z]})

	_expect(is_equal_approx(float(state.ground_y(_HOME)), 0.0),
		"the plane of the observer by default")
	_expect(is_equal_approx(float(state.ground_y(_HOME, 1)),
		32.0 * ChunkMeshBuilder.HEIGHT_STEP), "plane 1 at its own heights")


func _a_move_frees_far_chunks_on_every_plane() -> void:
	var state := WorldState.new()
	var far := Vector2i(_Const.CHUNK_STREAM_RADIUS + 2, 0)

	state.ingest_chunk(_payload(ChunkFile.blank(far.x, far.y, 1)))
	state.ingest(_Const.CH_ROOM_INFO, {"coords": [_HOME.x, _HOME.y, _Const.TILE_WORLD_Z]})

	_expect(not state.plane_chunks(1).has_chunk(far),
		"a plane-1 chunk past the block goes too")


# ─── The walk (09/28/2026) ───────────────────────────────────────────────────

func _a_walk_records_its_goal_and_path() -> void:
	var state := _standing_state()
	var fired: Array[bool] = []

	state.walk_changed.connect(func(): fired.append(true))
	state.ingest(_Const.CH_WALK, _walk([8, 5], [[6, 5], [7, 5], [8, 5]]))

	_expect(state.has_walk(), "a goal starts a walk")
	_expect(state.walk_goal == Vector2i(8, 5), "the goal is an int vector")
	_expect(state.walk_path == [Vector2i(6, 5), Vector2i(7, 5), Vector2i(8, 5)],
		"the path is kept in order")
	_expect(fired.size() == 1, "walk_changed fires")
	_expect(state.walk_on_current_plane(), "the walk is on the plane of the player")


func _a_step_drops_the_walked_tiles() -> void:
	var state := _standing_state()

	state.ingest(_Const.CH_WALK, _walk([8, 5], [[6, 5], [7, 5], [8, 5]]))
	state.ingest(_Const.CH_ROOM_INFO, {"coords": [7.0, 5.0, _Const.TILE_WORLD_Z]})

	_expect(state.walk_path == [Vector2i(8, 5)],
		"a step drops each tile up to the tile of the player")


func _a_walk_whose_first_step_already_landed_starts_trimmed() -> void:
	var state := _standing_state()

	state.ingest(_Const.CH_ROOM_INFO, {"coords": [6.0, 5.0, _Const.TILE_WORLD_Z]})
	state.ingest(_Const.CH_WALK, _walk([8, 5], [[6, 5], [7, 5], [8, 5]]))

	_expect(state.walk_path == [Vector2i(7, 5), Vector2i(8, 5)],
		"a walk that arrives after the first step starts past it")


func _an_empty_goal_ends_the_walk() -> void:
	var state := _standing_state()

	state.ingest(_Const.CH_WALK, _walk([8, 5], [[6, 5]]))
	state.ingest(_Const.CH_WALK, {"goal": [], "path": [], "z": ""})

	_expect(not state.has_walk(), "an empty goal ends the walk")
	_expect(state.walk_path.is_empty(), "and clears the path")


func _a_walk_on_another_plane_is_not_on_this_one() -> void:
	var state := _standing_state()
	var payload := _walk([8, 5], [[6, 5]])

	payload["z"] = WorldState.plane_z(1)
	state.ingest(_Const.CH_WALK, payload)

	_expect(state.has_walk() and not state.walk_on_current_plane(),
		"a walk on another plane draws no marker here")


func _walk(goal: Array, path: Array) -> Dictionary:
	var floats: Array = []

	for tile: Array in path:
		floats.append([float(tile[0]), float(tile[1])])

	return {"goal": [float(goal[0]), float(goal[1])], "path": floats,
		"z": _Const.TILE_WORLD_Z}


func _payload(chunk: ChunkFile) -> Dictionary:
	return {"chunk_file": JSON.parse_string(chunk.to_text())}


## A state on the home tile of chunk (0, 0), with one blocked tile.
func _standing_state() -> WorldState:
	var state := WorldState.new()
	var chunk := ChunkFile.blank(0, 0)

	chunk.flags[_BLOCKED.y * _Const.CHUNK_SIZE + _BLOCKED.x] = \
		_Const.TILE_FLAG_BLOCKED
	state.ingest_chunk(_payload(chunk))
	state.ingest_room_info({"coords": [5.0, 5.0, _Const.TILE_WORLD_Z]})

	return state


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
