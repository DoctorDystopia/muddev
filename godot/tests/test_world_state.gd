extends Node
## Unit tests for WorldState, plus WorldView's link geometry. Needs no server
## and no account -- the payloads below are hand-built in the exact shape
## Godot's JSON parser produces, which is the whole point: every number arrives
## as a FLOAT.
##
##     godot --headless --path godot res://tests/test_world_state.tscn
##
## Exits 0 when every case passes, 1 on the first failure.

var _failures := 0


func _ready() -> void:
	_floats_become_ints()
	_a_map_is_not_ready_until_every_chunk_arrives()
	_chunk_zero_restarts_a_level()
	_degenerate_links_are_dropped()
	_room_info_without_coords_is_ignored()
	_a_link_runs_along_its_own_span()
	_the_hash_matches_the_browser()
	_the_server_decides_what_a_tile_affords()

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

	state.ingest_map_chunk(_chunk("oasis", 0.0, 1.0, [_node(2.0, 3.0, "Bank")], []))

	var level: WorldState.Level = state.levels["oasis"]

	_expect(level.cells[0] == Vector2i(2, 3), "cell is an int vector")

	state.ingest_room_info({"coords": [7.0, 2.0, "oasis"]})

	_expect(state.current_cell == Vector2i(7, 2), "current cell is an int vector")
	_expect(state.current_z == "oasis", "current z is the map name")


func _a_map_is_not_ready_until_every_chunk_arrives() -> void:
	var state := WorldState.new()

	var first := state.ingest_map_chunk(
		_chunk("oasis", 0.0, 2.0, [_node(0.0, 0.0, "Oasis")], [[[0.0, 0.0], [1.0, 0.0]]])
	)

	_expect(first.is_empty(), "an incomplete map reports nothing to draw")

	var second := state.ingest_map_chunk(
		_chunk("oasis", 1.0, 2.0, [_node(1.0, 0.0, "Oasis")], [])
	)

	_expect(second == "oasis", "the last chunk names the map to draw")

	var level: WorldState.Level = state.levels["oasis"]

	_expect(level.cells.size() == 2, "nodes accumulate across chunks")
	_expect(level.links.size() == 1, "links ride on chunk zero alone")


func _chunk_zero_restarts_a_level() -> void:
	# A resync re-sends the whole map. Appending would double every tile, and
	# the duplicates would z-fight rather than announce themselves.
	var state := WorldState.new()
	var payload := _chunk("oasis", 0.0, 1.0, [_node(0.0, 0.0, "Oasis")], [])

	state.ingest_map_chunk(payload)
	state.ingest_map_chunk(payload)

	var level: WorldState.Level = state.levels["oasis"]

	_expect(level.cells.size() == 1, "a re-sent map replaces rather than appends")


func _degenerate_links_are_dropped() -> void:
	# Basis.looking_at cannot build a basis from a zero-length span, and a
	# self-link would be invisible anyway.
	var state := WorldState.new()

	state.ingest_map_chunk(
		_chunk("oasis", 0.0, 1.0, [], [[[1.0, 1.0], [1.0, 1.0]]])
	)

	var level: WorldState.Level = state.levels["oasis"]

	_expect(level.links.is_empty(), "a link to itself is discarded")


func _room_info_without_coords_is_ignored() -> void:
	var state := WorldState.new()

	state.ingest_room_info({"coords": [4.0, 4.0, "oasis"]})
	state.ingest_room_info({})

	_expect(state.current_cell == Vector2i(4, 4), "a malformed room leaves the last one standing")


func _a_link_runs_along_its_own_span() -> void:
	# The regression that produced this test: Basis.scaled applies its scale in
	# the PARENT frame, so every east-west link was drawn 0.1 long and
	# span-length wide -- a bar lying across the map at right angles to the
	# link it stood for. Nothing errored. Only the picture was wrong.
	var east := WorldView.link_transform(Vector3.ZERO, Vector3(3.0, 0.0, 0.0))

	_expect(is_equal_approx(east.basis.z.length(), 3.0), "a link is as long as its span")
	_expect(
		absf(east.basis.z.normalized().dot(Vector3.RIGHT)) > 0.99,
		"an east-west link runs east-west"
	)
	_expect(
		is_equal_approx(east.basis.x.length(), WorldView.LINK_WIDTH),
		"a link keeps its width whichever way it runs"
	)
	_expect(
		east.origin.is_equal_approx(Vector3(1.5, WorldView.TILE_HEIGHT * 0.5, 0.0)),
		"a link sits at the midpoint of its span"
	)

	var north := WorldView.link_transform(Vector3.ZERO, Vector3(0.0, 0.0, -2.0))

	_expect(is_equal_approx(north.basis.z.length(), 2.0), "the same holds north-south")
	_expect(
		is_equal_approx(north.basis.x.length(), WorldView.LINK_WIDTH),
		"a north-south link keeps its width too"
	)


func _the_hash_matches_the_browser() -> void:
	# Expected values computed by running blackout3d.js's hashString algorithm
	# directly. Most room kinds are not in the colour table, so this number
	# colours most of the world -- if the two panes disagree here, a screenshot
	# comparison stops being able to tell a bug from a difference.
	var vectors := {
		"Oasis": 75961771,
		"Oasis Outskirts": 101684281,
		"Trade Town Sector 1": 313616919,
		"20743": 47660536,
	}

	for text: String in vectors:
		_expect(
			MapPalette.stable_hash(text) == vectors[text],
			"stable_hash(%s) matches blackout3d.js" % text
		)

	# RGB computed from the browser's own setHSL(hue, 0.42, 0.42). Godot has no
	# from_hsl, so this is what catches feeding those numbers to from_hsv and
	# getting a plausible-looking wrong colour.
	var colours := {
		"Oasis": Color(0.5964, 0.2436, 0.41412),
		"Trade Town Sector 1": Color(0.5964, 0.47292, 0.2436),
	}

	for kind: String in colours:
		_expect(
			MapPalette.kind_colour(kind).is_equal_approx(colours[kind]),
			"kind_colour(%s) matches blackout3d.js" % kind
		)

	_expect(
		MapPalette.kind_colour("Bank") == MapPalette.ROOM_KIND_COLORS["Bank"],
		"a listed room kind uses its authored colour"
	)


## The client reads the server's answer and does not compute one.
##
## Replaces ten cases that asserted a grid-delta -> direction-name table. That
## table is gone: it could not express a one-way exit or a diagonal link, and
## the browser pane deleted it on 08/23/2026. What is worth testing now is not
## which way is north -- the server says -- but the ABSENT/EMPTY distinction,
## which is the part that was nearly lost when the browser pane was rewritten.
func _the_server_decides_what_a_tile_affords() -> void:
	var state := WorldState.new()

	state.ingest_map_chunk(_chunk("oasis", 0.0, 1.0, [
		_node(2.0, 2.0, "Oasis", "goto (2,2)"),
		_node(2.0, 3.0, "Oasis", "goto (2,3)"),
		_node(3.0, 3.0, "Oasis", "goto (3,3)"),
		_node(9.0, 9.0, "Oasis", "goto (9,9)"),
	], []))

	# The observer stands on (2,2). North is a real exit; east is a wall the
	# server marks with an EMPTY command; (9,9) is far away and carries only
	# its own node `goto`.
	state.ingest_room_info({
		"coords": [2.0, 2.0, "oasis"],
		"exits": {"north": 1.0},
		"tile_actions": {
			"2:3": {"command": "north", "kind": "step"},
			"3:2": {"command": "", "kind": "none"},
			"2:2": {"command": "look", "kind": "look"},
		},
		"cancel_action": {"command": "goto", "kind": "cancel"},
	})

	_expect(
		state.tile_action(Vector2i(2, 3)).get("command", "") == "north",
		"a near tile sends the command the server named"
	)
	_expect(
		state.tile_action(Vector2i(2, 2)).get("command", "") == "look",
		"your own tile looks"
	)

	# EMPTY is not ABSENT. The server saying "no" must not fall through to the
	# node's goto and walk the player the long way around a visible wall.
	_expect(
		state.tile_action(Vector2i(3, 2)).is_empty(),
		"an empty command is refused, not fallen through"
	)

	# ABSENT falls through to the node's own walk.
	_expect(
		state.tile_action(Vector2i(9, 9)).get("command", "") == "goto (9,9)",
		"a distant node falls through to its own goto"
	)

	# A cell no node occupies affords nothing at all.
	_expect(
		state.tile_action(Vector2i(40, 40)).is_empty(),
		"a cell with no node affords nothing"
	)

	# Diagonals are deliberately ABSENT from tile_actions, so a diagonal
	# neighbour falls through to its node's goto and routes through the
	# pathfinder. Refusing these was the original bug -- the tiles nearest the
	# player were the only ones that could not be clicked.
	_expect(
		state.tile_action(Vector2i(3, 3)).get("command", "") == "goto (3,3)",
		"a diagonal neighbour routes through the pathfinder, not refused"
	)

	_expect(
		state.current_cancel_action.get("command", "") == "goto",
		"cancel_action is kept for whoever adds walk tracking"
	)


# ─── Private helpers ─────────────────────────────────────────────────────────

func _chunk(z: String, index: float, count: float, nodes: Array, links: Array) -> Dictionary:
	var wire_links: Array = []

	for pair: Array in links:
		wire_links.append({"from": pair[0], "to": pair[1]})

	return {
		"z": z,
		"chunk_index": index,
		"chunk_count": count,
		"nodes": nodes,
		"links": wire_links,
	}


## One map node, in the shape mapexport._node_entries emits.
##
## `action` is the pathfinder walk to this node. Omitted rather than sent empty
## when a node affords nothing, which is what the server does.
func _node(x: float, y: float, kind: String, walk := "") -> Dictionary:
	var entry := {"x": x, "y": y, "room_kind": kind}

	if not walk.is_empty():
		entry["action"] = {"command": walk, "kind": "walk"}

	return entry


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
