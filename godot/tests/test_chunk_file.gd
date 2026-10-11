extends Node
## The GDScript half of the chunk file parity test.
##
##     godot --headless --path godot res://tests/test_chunk_file.tscn
##
## Needs nothing running. It reads the fixtures that the Python test reads,
## in `blackout/systems/core/tilegrid/tests/fixtures/`, and proves three
## things. `blackout/systems/core/tilegrid/tests/test_chunkfile.py` proves the
## same three for the Python reader:
##
## 1. Each fixture reads and writes back byte for byte.
## 2. The [method ChunkFile.semantic_digest] of each fixture is the digest in
##    `digests.json`.
## 3. Every bad file in the list below is refused.
##
## A Python guard reads this file as TEXT and compares the names in the
## `_refuses("...")` calls with `INVALID_CASES`. Keep each name as a string
## literal in the call, or the guard cannot see it.

const _Const := preload("res://autoload/blackout_constants.gd")

const FIXTURES_FROM_GAME := "systems/core/tilegrid/tests/fixtures"
const DIGEST_FILE := "digests.json"
const BASE_FIXTURE := "chunk_-1_2_p0.json"

var _failures := 0
var _base := {}


func _ready() -> void:
	var digests := _read_digests()

	_expect(digests.size() > 0, "the digest file names at least one fixture")

	for fixture_name: String in digests:
		_fixture_reads_back_and_matches_its_digest(fixture_name, digests[fixture_name])

	_base = JSON.parse_string(_fixture_text(BASE_FIXTURE))
	_every_invalid_case_is_refused()
	_the_wall_cases_differ_from_a_good_file_only_in_their_fault()
	_the_writer_picks_the_format_from_the_wall_styles()
	_an_integral_float_counts_as_an_int()
	_objects_are_local_and_the_reader_adds_the_offset()
	_the_file_name_follows_the_template()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: chunk_file")
	get_tree().quit(0)


func _fixture_reads_back_and_matches_its_digest(fixture_name: String,
		digest: String) -> void:
	var text := _fixture_text(fixture_name)
	var chunk := ChunkFile.parse_text(text)

	_expect(chunk.error.is_empty(), "%s reads with no error: %s"
		% [fixture_name, chunk.error])

	if not chunk.error.is_empty():
		return

	_expect(chunk.to_text() == text, "%s writes back byte for byte" % fixture_name)
	_expect(chunk.semantic_digest() == digest,
		"%s has the committed digest" % fixture_name)
	_expect(chunk.file_name() == fixture_name, "%s names its own chunk" % fixture_name)


## The same names as INVALID_CASES in test_chunkfile.py. The Python guard
## compares the two lists.
func _every_invalid_case_is_refused() -> void:
	_refuses("not_json", Callable())
	_refuses("missing_key", func(d: Dictionary) -> void: d.erase("objects"))
	_refuses("unknown_key", func(d: Dictionary) -> void: d["seed"] = 7)
	_refuses("wrong_format", func(d: Dictionary) -> void:
		d["format"] = _Const.CHUNK_FORMAT_VERSION + 1)
	_refuses("wrong_size", func(d: Dictionary) -> void:
		@warning_ignore("integer_division")
		d["size"] = _Const.CHUNK_SIZE / 2)
	_refuses("chunk_not_pair", func(d: Dictionary) -> void: d["chunk"] = [0])
	_refuses("plane_too_high", func(d: Dictionary) -> void:
		d["plane"] = _Const.CHUNK_PLANE_MAX + 1)
	_refuses("plane_negative", func(d: Dictionary) -> void: d["plane"] = -1)
	_refuses("bool_as_int", func(d: Dictionary) -> void: d["plane"] = true)
	_refuses("fractional_number", func(d: Dictionary) -> void:
		d["plane"] = 0.5)
	_refuses("floor_names_empty", func(d: Dictionary) -> void:
		d["floor_names"] = [])
	_refuses("bad_name", func(d: Dictionary) -> void:
		d["floor_names"] = ["Sand", "asphalt", "rubble"])
	_refuses("name_line_break", func(d: Dictionary) -> void:
		d["floor_names"] = ["sand\n", "asphalt", "rubble"])
	_refuses("duplicate_name", func(d: Dictionary) -> void:
		d["floor_names"] = ["sand", "sand", "rubble"])
	_refuses("short_height_rows", func(d: Dictionary) -> void:
		d["heights"].pop_back())
	_refuses("short_row", func(d: Dictionary) -> void: d["floors"][0].pop_back())
	_refuses("height_out_of_range", func(d: Dictionary) -> void:
		d["heights"][0][0] = _Const.CHUNK_HEIGHT_MAX + 1)
	_refuses("floor_index_past_names", func(d: Dictionary) -> void:
		d["floors"][0][0] = 3)
	_refuses("area_index_past_names", func(d: Dictionary) -> void:
		d["areas"][0][0] = 2)
	_refuses("unknown_flag_bit", func(d: Dictionary) -> void:
		d["flags"][0][0] = _Const.TILE_FLAGS_ALL + 1)
	_refuses("negative_flag", func(d: Dictionary) -> void: d["flags"][0][0] = -1)
	_refuses("object_extra_key", func(d: Dictionary) -> void:
		d["objects"][0]["facing"] = 1)
	_refuses("object_missing_rotation", func(d: Dictionary) -> void:
		d["objects"][0].erase("rotation"))
	_refuses("object_outside_chunk", func(d: Dictionary) -> void:
		d["objects"][0]["x"] = _Const.CHUNK_SIZE)
	_refuses("object_bad_rotation", func(d: Dictionary) -> void:
		d["objects"][0]["rotation"] = _Const.CHUNK_ROTATION_COUNT)
	_refuses("object_bad_kind", func(d: Dictionary) -> void:
		d["objects"][0]["kind"] = "Bad Kind")
	_refuses("object_empty_text", func(d: Dictionary) -> void:
		d["objects"][0]["text"] = "")
	_refuses("object_text_not_string", func(d: Dictionary) -> void:
		d["objects"][0]["text"] = 7)
	_refuses("object_text_quote", func(d: Dictionary) -> void:
		d["objects"][0]["text"] = 'Say "hi"')
	_refuses("object_text_markup", func(d: Dictionary) -> void:
		d["objects"][0]["text"] = "|rRed")
	_refuses("object_text_edge_space", func(d: Dictionary) -> void:
		d["objects"][0]["text"] = "Bank ")
	_refuses("object_text_line_break", func(d: Dictionary) -> void:
		d["objects"][0]["text"] = "Bank\n")
	_refuses("object_text_too_long", func(d: Dictionary) -> void:
		d["objects"][0]["text"] = "x".repeat(_Const.CHUNK_TEXT_MAX_CHARS + 1))
	# Format 2, the wall styles (DESIGN-0013 section 6.4).
	_refuses("format_one_with_walls", func(d: Dictionary) -> void:
		_with_walls(d, ["brick"], 0)
		d["format"] = _Const.CHUNK_FORMAT_PLAIN_WALLS)
	_refuses("format_two_without_walls", func(d: Dictionary) -> void:
		d["format"] = _Const.CHUNK_FORMAT_VERSION)
	_refuses("wall_names_empty", func(d: Dictionary) -> void:
		_with_walls(d, [], 0))
	_refuses("wall_index_past_names", func(d: Dictionary) -> void:
		_with_walls(d, ["brick"], 1))
	_refuses("walls_all_default", func(d: Dictionary) -> void:
		_with_walls(d, [_Const.TILE_DEFAULT_WALL_STYLE, "brick"], 0))


## Make `data` a file of format 2 with the wall styles `names`. The first
## tile gets index `cell`. Every other tile gets index 0. The Python
## `_with_walls` makes the same change.
static func _with_walls(data: Dictionary, names: Array, cell: int) -> void:
	var walls := []

	for row: int in _Const.CHUNK_SIZE:
		var values := []

		values.resize(_Const.CHUNK_SIZE)
		values.fill(0)
		walls.append(values)

	walls[0][0] = cell
	data["format"] = _Const.CHUNK_FORMAT_VERSION
	data["wall_names"] = names.duplicate()
	data["walls"] = walls


## A wall case that the reader refuses for another reason proves nothing.
## The same change with a legal index reads.
func _the_wall_cases_differ_from_a_good_file_only_in_their_fault() -> void:
	var data: Dictionary = _base.duplicate(true)

	_with_walls(data, ["brick"], 0)

	var chunk := ChunkFile.from_dict(data)

	_expect(chunk.error.is_empty() and chunk.wall_style_name(0, 0) == "brick",
		"a file of format 2 with one style reads: %s" % chunk.error)

	data = _base.duplicate(true)
	_with_walls(data, [_Const.TILE_DEFAULT_WALL_STYLE, "brick"], 1)
	chunk = ChunkFile.from_dict(data)
	_expect(chunk.error.is_empty() and chunk.wall_style_name(0, 0) == "brick"
		and chunk.wall_style_name(1, 0) == _Const.TILE_DEFAULT_WALL_STYLE,
		"each tile reads its own wall style")


## A file of format 1 reads the default style on every tile, and the writer
## picks the format from the styles of the tiles.
func _the_writer_picks_the_format_from_the_wall_styles() -> void:
	var chunk := ChunkFile.from_dict(_base.duplicate(true))

	_expect(chunk.wall_style_name(17, 42) == _Const.TILE_DEFAULT_WALL_STYLE,
		"a file of format 1 reads the default wall style")
	_expect(JSON.parse_string(chunk.to_text())["format"]
		== _Const.CHUNK_FORMAT_PLAIN_WALLS, "plain walls write format 1")

	chunk.wall_names = PackedStringArray([_Const.TILE_DEFAULT_WALL_STYLE, "brick"])
	_expect(JSON.parse_string(chunk.to_text())["format"]
		== _Const.CHUNK_FORMAT_PLAIN_WALLS, "an unused style name writes format 1")

	chunk.walls[5] = 1

	var text := chunk.to_text()

	_expect(JSON.parse_string(text)["format"] == _Const.CHUNK_FORMAT_VERSION,
		"a tile with a style writes format 2")
	_expect(ChunkFile.parse_text(text).wall_style_name(5, 0) == "brick",
		"format 2 reads back its style")

	chunk.compact_names()
	_expect(chunk.wall_names.size() == 2, "compact_names keeps the used styles")

	chunk.walls[5] = 0
	chunk.compact_names()
	_expect(chunk.wall_names == PackedStringArray([_Const.TILE_DEFAULT_WALL_STYLE]),
		"compact_names drops an unused style")


func _refuses(case_name: String, mutate: Callable) -> void:
	var chunk: ChunkFile

	if mutate.is_null():
		chunk = ChunkFile.parse_text("{ not json")
	else:
		var data: Dictionary = _base.duplicate(true)

		mutate.call(data)
		chunk = ChunkFile.from_dict(data)

	_expect(not chunk.error.is_empty(), "%s is refused" % case_name)


## Godot's JSON parser returns every number as a float, so this is the
## everyday path. The Python reader accepts 0.0 too.
func _an_integral_float_counts_as_an_int() -> void:
	var data: Dictionary = _base.duplicate(true)

	data["plane"] = 0.0

	var chunk := ChunkFile.from_dict(data)

	_expect(chunk.error.is_empty() and chunk.plane == 0, "0.0 reads as plane 0")


func _objects_are_local_and_the_reader_adds_the_offset() -> void:
	var chunk := ChunkFile.from_dict(_base.duplicate(true))
	var local: Dictionary = chunk.objects[0]
	var placed: Dictionary = chunk.global_objects()[0]
	var size: int = _Const.CHUNK_SIZE

	_expect(placed["x"] == chunk.cx * size + local["x"],
		"a world x is the chunk origin plus the local x")
	_expect(placed["y"] == chunk.cy * size + local["y"],
		"a world y is the chunk origin plus the local y")


func _the_file_name_follows_the_template() -> void:
	var chunk := ChunkFile.new()

	chunk.cx = -3
	chunk.cy = 4
	chunk.plane = 1

	_expect(chunk.file_name() == "chunk_-3_4_p1.json",
		"the file name is chunk_<cx>_<cy>_p<plane>.json")


# ─── Helpers ─────────────────────────────────────────────────────────────────

func _fixture_directory() -> String:
	var project := ProjectSettings.globalize_path("res://")
	var game := project.path_join(ChunkFile.GAME_DIRECTORY_FROM_PROJECT)

	return game.path_join(FIXTURES_FROM_GAME).simplify_path()


## The committed text, with any CRLF made LF, as the Python test reads it.
func _fixture_text(fixture_name: String) -> String:
	var path := _fixture_directory().path_join(fixture_name)
	var text := FileAccess.get_file_as_string(path)

	return text.replace("\r\n", "\n")


func _read_digests() -> Dictionary:
	var parsed: Variant = JSON.parse_string(_fixture_text(DIGEST_FILE))

	if parsed is Dictionary:
		return parsed

	return {}


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
