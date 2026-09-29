extends Node
## The GDScript half of the content check parity, and the water surface.
##
##     godot --headless --path godot res://tests/test_terrain_checks.tscn
##
## [TerrainChecks] reads the fixture world of
## `blackout/world/tests/fixtures/checks/` and must give the findings of its
## `expected.json`. The Python `world/tests/test_tile_checks.py` compares the
## same files with the same list. Change the fixture only through
## `world/tests/check_fixture_builder.py`.
##
## Exits 0 when every case passes, 1 on the first failure.

const _Const := preload("res://autoload/blackout_constants.gd")

const _EXPECTED_FILE := "expected.json"

var _failures := 0


func _ready() -> void:
	_the_fixture_world_gives_the_expected_findings()
	_an_empty_world_has_no_respawn_point()
	_every_rule_is_a_generated_name()
	_water_draws_on_water_tiles_only()
	_the_water_surface_meets_the_highest_corner()
	_the_fixture_stamp_matches_the_fixture_files()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: terrain_checks")
	get_tree().quit(0)


# ─── Cases ───────────────────────────────────────────────────────────────────

func _the_fixture_world_gives_the_expected_findings() -> void:
	var directory := _fixture_directory()
	var files: Array[ChunkFile] = []

	for file_name: String in DirAccess.get_files_at(directory):
		if file_name.begins_with("chunk_"):
			var chunk := ChunkFile.read_file(directory.path_join(file_name))

			_expect(chunk.error.is_empty(), "fixture %s reads" % file_name)
			files.append(chunk)

	var found := TerrainChecks.check_world(files)
	var got: Array[String] = []

	for finding: Dictionary in found:
		got.append(_row_key([finding["rule"], finding["x"], finding["y"],
			finding["plane"]]))

	var expected: Array[String] = []
	var text := FileAccess.get_file_as_string(directory.path_join(_EXPECTED_FILE))

	for row: Array in JSON.parse_string(text.replace("\r\n", "\n")):
		expected.append(_row_key(row))

	_expect(got == expected, "the findings match expected.json:\n  got %s\n  want %s"
		% [got, expected])

	for finding: Dictionary in found:
		_expect(not str(finding["message"]).is_empty(), "a finding has a message")


func _an_empty_world_has_no_respawn_point() -> void:
	var found := TerrainChecks.check_world([])

	_expect(found.size() == 1 and found[0]["rule"] == _Const.TILE_CHECK_RESPAWN_COUNT,
		"an empty world has one finding: no respawn point")


func _every_rule_is_a_generated_name() -> void:
	var twin_rules := [_Const.TILE_CHECK_UNKNOWN_KIND,
		_Const.TILE_CHECK_OBJECT_UNWALKABLE, _Const.TILE_CHECK_TRANSITION_LANDING,
		_Const.TILE_CHECK_CLIMB_LANDING, _Const.TILE_CHECK_VOID_OPEN,
		_Const.TILE_CHECK_RESPAWN_COUNT, _Const.TILE_CHECK_SIGN_TEXT]

	for rule: String in twin_rules:
		_expect(_Const.TILE_CHECK_RULES.has(rule), "%s is in TILE_CHECK_RULES" % rule)

	_expect(_Const.TILE_CHECK_RULES.size() == twin_rules.size(),
		"this twin checks every rule of tile_checks.py")


func _water_draws_on_water_tiles_only() -> void:
	var chunk := ChunkFile.blank(0, 0)

	_expect(WaterMeshBuilder.build(chunk).get_surface_count() == 0,
		"a chunk with no water has no surface")

	chunk.flags[3] = _Const.TILE_FLAG_WATER
	chunk.flags[70] = _Const.TILE_FLAG_WATER | _Const.TILE_FLAG_BLOCKED

	var mesh := WaterMeshBuilder.build(chunk)
	var arrays := mesh.surface_get_arrays(0)
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]

	_expect(vertices.size() == 2 * 2 * 3, "two water tiles give four triangles")

	for start: int in range(0, vertices.size(), 3):
		var a := vertices[start]
		var normal := (vertices[start + 2] - a).cross(vertices[start + 1] - a)

		_expect(normal.y > 0.0, "a water triangle faces up")


func _the_water_surface_meets_the_highest_corner() -> void:
	var chunk := ChunkFile.blank(0, 0)
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE

	# Tile (2, 2): one corner raised to 5, the bed lowered to -4 elsewhere.
	chunk.heights[2 * side + 2] = -4
	chunk.heights[2 * side + 3] = -4
	chunk.heights[3 * side + 2] = -4
	chunk.heights[3 * side + 3] = 5
	chunk.flags[2 * _Const.CHUNK_SIZE + 2] = _Const.TILE_FLAG_WATER

	_expect(WaterMeshBuilder.surface_steps(chunk, 2, 2) == 5,
		"the surface is at the highest corner")

	var vertices: PackedVector3Array = WaterMeshBuilder.build(chunk) \
		.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	var want := 5 * ChunkMeshBuilder.HEIGHT_STEP + WaterMeshBuilder.LIFT

	_expect(is_equal_approx(vertices[0].y, want), "and it is flat at that height")


func _the_fixture_stamp_matches_the_fixture_files() -> void:
	# The Python syncstamp wrote this stamp. The same digest here means no
	# change: the two languages hash a chunk file the same way.
	var directory := _fixture_directory()
	var stamped: Variant = TerrainSyncState.read_stamp(directory.path_join("sync_stamp.json"))

	_expect(stamped is Dictionary and stamped.size() == 2, "the fixture stamp reads")
	_expect(TerrainSyncState.changed_files(directory, stamped).is_empty(),
		"no fixture file differs from the Python stamp")

	var partial: Dictionary = stamped.duplicate()

	partial.erase("chunk_0_0_p1.json")
	partial["chunk_9_9_p0.json"] = "0"

	var found := TerrainSyncState.changed_files(directory, partial)

	_expect(str(found) == str([["chunk_0_0_p1.json", "new"],
		["chunk_9_9_p0.json", "removed"]]), "a new file and a removed file are named")


# ─── Helpers ─────────────────────────────────────────────────────────────────

func _fixture_directory() -> String:
	var project := ProjectSettings.globalize_path("res://")
	var game := project.path_join(ChunkFile.GAME_DIRECTORY_FROM_PROJECT)

	return game.path_join(TerrainChecks.FIXTURES_FROM_GAME).simplify_path()


## A row as text. JSON gives every number as a float, so each is made an int.
static func _row_key(row: Array) -> String:
	return "%s %d %d %d" % [row[0], int(row[1]), int(row[2]), int(row[3])]


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
