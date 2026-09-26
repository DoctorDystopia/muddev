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
