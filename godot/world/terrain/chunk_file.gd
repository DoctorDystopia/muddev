class_name ChunkFile
extends RefCounted
## One chunk file: read it, check it, and write it in the one canonical layout.
##
## The GDScript twin of `blackout/systems/core/tilegrid/chunkfile.py`. That
## module's docstring defines format 1. DESIGN-0011 section 6.2 is the design.
## The Godot editor (Phase 3) writes chunk files through [method to_text], and
## the client (Phase 5) reads them through [method parse_text].
##
## ## The parity test
##
## `test_chunk_file.tscn` reads the same fixtures as the Python test. It
## writes each one back byte for byte, matches the committed digest of
## [method semantic_dump], and refuses the same list of bad files. A Python
## guard fails if the two lists of bad files differ.
##
## ## No exceptions in GDScript
##
## A read always returns a ChunkFile. A bad file sets [member error], and the
## caller must check it. The first refusal wins, as in the Python reader.
##
## ## Every JSON number is a float here
##
## Godot's JSON parser cannot tell 3 from 3.0. So an integral float counts as
## an int, and the Python reader accepts the same.

const _Const := preload("res://autoload/blackout_constants.gd")

## The keys of a chunk file, in the order that the writer writes them.
const KEYS := ["format", "chunk", "plane", "size", "floor_names", "area_names",
	"heights", "floors", "flags", "areas", "objects"]

## The keys of one object, in the order that the writer writes them.
const OBJECT_KEYS := ["kind", "x", "y", "rotation"]

const _INDENT := "  "
const _ROW_INDENT := "    "

## Where the fixtures and the world live, from the Godot project root. The
## game directory is a sibling of `godot/`.
const GAME_DIRECTORY_FROM_PROJECT := "../blackout"

var cx := 0
var cy := 0
var plane := 0
var floor_names := PackedStringArray()
var area_names := PackedStringArray()

## Flat grids, row 0 first. Row 0 is the south edge, and item 0 of a row is
## the west edge, the same order as the Python lists.
var heights := PackedInt32Array()
var floors := PackedInt32Array()
var flags := PackedInt32Array()
var areas := PackedInt32Array()

## Each object is `{kind, x, y, rotation}`, at LOCAL tile coordinates.
var objects: Array[Dictionary] = []

## Empty for a good file. Otherwise the first reason the file was refused.
var error := ""

var _name_regex := RegEx.create_from_string(_Const.CHUNK_NAME_PATTERN)


# ─── A new chunk ─────────────────────────────────────────────────────────────

## A new, flat chunk: every corner at height 0, every tile on the default
## floor type and in the default area, no flags, and no objects. The terrain
## editor makes a chunk with this, where no chunk file exists yet.
static func blank(chunk_x: int, chunk_y: int, chunk_plane: int = 0) -> ChunkFile:
	var result := ChunkFile.new()
	var corners: int = _Const.CHUNK_CORNERS_PER_SIDE * _Const.CHUNK_CORNERS_PER_SIDE
	var tiles: int = _Const.CHUNK_SIZE * _Const.CHUNK_SIZE

	result.cx = chunk_x
	result.cy = chunk_y
	result.plane = chunk_plane
	result.floor_names = PackedStringArray([_Const.TILE_DEFAULT_FLOOR])
	result.area_names = PackedStringArray([_Const.TILE_DEFAULT_AREA])
	result.heights.resize(corners)
	result.floors.resize(tiles)
	result.flags.resize(tiles)
	result.areas.resize(tiles)

	return result


## Remove each floor name and area name that no tile uses, and renumber the
## grids. The editor calls this before a save, so a painted-over name does not
## stay in the file. The order of the names that stay does not change. If no
## tile uses any name, the first name stays, because a list may not be empty.
func compact_names() -> void:
	floor_names = _compacted(floor_names, floors)
	area_names = _compacted(area_names, areas)


## Return the used names of `names`, and renumber `grid` in place to match.
static func _compacted(names: PackedStringArray,
		grid: PackedInt32Array) -> PackedStringArray:
	var used := {}

	for index: int in grid:
		used[index] = true

	var kept := PackedStringArray()
	var renumber := {}

	for index: int in names.size():
		if used.has(index) or (used.is_empty() and index == 0):
			renumber[index] = kept.size()
			kept.append(names[index])

	for tile: int in grid.size():
		grid[tile] = renumber[grid[tile]]

	return kept


# ─── Reading ─────────────────────────────────────────────────────────────────

## Parse and check the text of a chunk file. Check [member error] after.
static func parse_text(text: String) -> ChunkFile:
	var parser := JSON.new()
	var status := parser.parse(text)

	if status != OK:
		var refused := ChunkFile.new()

		refused.error = "not JSON: %s" % parser.get_error_message()

		return refused

	return from_dict(parser.data)


## Read and check one chunk file from an OS path. Check [member error] after.
static func read_file(path: String) -> ChunkFile:
	var text := FileAccess.get_file_as_string(path)

	if text.is_empty():
		var refused := ChunkFile.new()

		refused.error = "cannot read %s" % path

		return refused

	return parse_text(text)


## Check a parsed chunk file. Check [member error] after.
##
## The same rules as `chunkfile.from_dict`, in the same order:
##
## 1. The keys, the format, the size, the chunk, and the plane.
## 2. The two name lists.
## 3. Each grid: its shape, its range, and its indexes.
## 4. The objects.
static func from_dict(data: Variant) -> ChunkFile:
	var result := ChunkFile.new()

	if not (data is Dictionary):
		result.error = "a chunk file must hold one JSON object"
		return result

	result._read_header(data)
	result.floor_names = result._names(data.get("floor_names"), "floor_names")
	result.area_names = result._names(data.get("area_names"), "area_names")
	result.heights = result._grid(data.get("heights"),
		_Const.CHUNK_CORNERS_PER_SIDE, _Const.CHUNK_HEIGHT_MIN,
		_Const.CHUNK_HEIGHT_MAX, "heights")
	result.floors = result._grid(data.get("floors"), _Const.CHUNK_SIZE, 0,
		result.floor_names.size() - 1, "floors")
	result.flags = result._grid(data.get("flags"), _Const.CHUNK_SIZE, 0,
		_Const.TILE_FLAGS_ALL, "flags")
	result._check_flag_bits()
	result.areas = result._grid(data.get("areas"), _Const.CHUNK_SIZE, 0,
		result.area_names.size() - 1, "areas")
	result._read_objects(data.get("objects"))

	return result


func _fail(message: String) -> void:
	if error.is_empty():
		error = message


## Return `value` as an int, or refuse it. An integral float counts.
func _as_int(value: Variant, what: String) -> int:
	if value is int:
		return value

	if value is float and value == floorf(value):
		return int(value)

	_fail("%s must be an integer, not %s" % [what, str(value)])

	return 0


func _int_in(value: Variant, low: int, high: int, what: String) -> int:
	var number := _as_int(value, what)

	if number < low or number > high:
		_fail("%s is %d, outside %d..%d" % [what, number, low, high])

	return number


func _read_header(data: Dictionary) -> void:
	var keys := data.keys()
	var expected := KEYS.duplicate()

	keys.sort()
	expected.sort()

	if keys != expected:
		_fail("keys wrong: %s" % str(keys))
		return

	if _as_int(data["format"], "format") != _Const.CHUNK_FORMAT_VERSION:
		_fail("format is not %d" % _Const.CHUNK_FORMAT_VERSION)

	if _as_int(data["size"], "size") != _Const.CHUNK_SIZE:
		_fail("size is not %d" % _Const.CHUNK_SIZE)

	var chunk: Variant = data["chunk"]

	if not (chunk is Array) or chunk.size() != 2:
		_fail("chunk must be [cx, cy]")
		return

	cx = _as_int(chunk[0], "chunk x")
	cy = _as_int(chunk[1], "chunk y")
	plane = _int_in(data["plane"], 0, _Const.CHUNK_PLANE_MAX, "plane")


func _names(value: Variant, what: String) -> PackedStringArray:
	var names := PackedStringArray()

	if not (value is Array) or value.is_empty():
		_fail("%s must be a list with at least one name" % what)
		return names

	for name: Variant in value:
		if not (name is String) or _name_regex.search(name) == null:
			_fail("%s holds %s, which is not a name" % [what, str(name)])
			return names

		if names.has(name):
			_fail("%s holds a name two times" % what)

		names.append(name)

	return names


## `side` rows of `side` ints in low..high, as one flat array.
func _grid(value: Variant, side: int, low: int, high: int,
		what: String) -> PackedInt32Array:
	var flat := PackedInt32Array()

	if not (value is Array) or value.size() != side:
		_fail("%s must hold %d rows" % [what, side])
		return flat

	for row_index: int in side:
		var row: Variant = value[row_index]

		if not (row is Array) or row.size() != side:
			_fail("%s row %d must hold %d values" % [what, row_index, side])
			return flat

		for column: int in side:
			var label := "%s[%d][%d]" % [what, row_index, column]

			flat.append(_int_in(row[column], low, high, label))

	return flat


## Refuse a bit that no reader knows. The range check in [method _grid]
## covers it while the bits are contiguous. This keeps it true if they stop
## being contiguous.
func _check_flag_bits() -> void:
	for index: int in flags.size():
		if flags[index] & ~_Const.TILE_FLAGS_ALL:
			_fail("flags tile %d holds an unknown bit" % index)
			return


func _read_objects(value: Variant) -> void:
	if not (value is Array):
		_fail("objects must be a list")
		return

	var last: int = _Const.CHUNK_SIZE - 1
	var expected := OBJECT_KEYS.duplicate()

	expected.sort()

	for index: int in value.size():
		var item: Variant = value[index]

		if not (item is Dictionary):
			_fail("object %d must be an object" % index)
			return

		var keys: Array = item.keys()

		keys.sort()

		if keys != expected:
			_fail("object %d must have exactly the keys %s" % [index, OBJECT_KEYS])
			return

		var kind: Variant = item["kind"]

		if not (kind is String) or _name_regex.search(kind) == null:
			_fail("object %d has the kind %s" % [index, str(kind)])
			return

		objects.append({
			"kind": kind,
			"x": _int_in(item["x"], 0, last, "object %d x" % index),
			"y": _int_in(item["y"], 0, last, "object %d y" % index),
			"rotation": _int_in(item["rotation"], 0,
				_Const.CHUNK_ROTATION_COUNT - 1, "object %d rotation" % index),
		})


# ─── Meaning ─────────────────────────────────────────────────────────────────

## (southwest, southeast, northwest, northeast) of a local tile.
func corner_heights(lx: int, ly: int) -> PackedInt32Array:
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE
	var south := ly * side + lx
	var north := south + side

	return PackedInt32Array([heights[south], heights[south + 1],
		heights[north], heights[north + 1]])


## The gameplay height of a tile: its lowest corner. The Python
## `tile_height` uses the same rule.
func tile_height(lx: int, ly: int) -> int:
	var corners := corner_heights(lx, ly)
	var lowest := corners[0]

	for corner: int in corners:
		lowest = mini(lowest, corner)

	return lowest


func floor_name(lx: int, ly: int) -> String:
	return floor_names[floors[ly * _Const.CHUNK_SIZE + lx]]


func area_name(lx: int, ly: int) -> String:
	return area_names[areas[ly * _Const.CHUNK_SIZE + lx]]


## Each object as `{kind, x, y, rotation}` at WORLD tile coordinates.
func global_objects() -> Array[Dictionary]:
	var placed: Array[Dictionary] = []
	var origin_x := cx * _Const.CHUNK_SIZE
	var origin_y := cy * _Const.CHUNK_SIZE

	for thing: Dictionary in objects:
		placed.append({"kind": thing["kind"], "x": origin_x + thing["x"],
			"y": origin_y + thing["y"], "rotation": thing["rotation"]})

	return placed


## The file name that this chunk must have.
func file_name() -> String:
	return _Const.CHUNK_FILE_TEMPLATE.format(
		{"cx": cx, "cy": cy, "plane": plane})


## The world chunk directory, as an OS path. The editor writes there.
static func world_directory() -> String:
	var project := ProjectSettings.globalize_path("res://")
	var game := project.path_join(GAME_DIRECTORY_FROM_PROJECT)

	return game.path_join(_Const.CHUNK_DIRECTORY).simplify_path()


# ─── Writing ─────────────────────────────────────────────────────────────────

## The canonical text. The Python `to_text` writes the same bytes.
func to_text() -> String:
	var size: int = _Const.CHUNK_SIZE
	var lines := PackedStringArray([
		"{",
		'%s"format": %d,' % [_INDENT, _Const.CHUNK_FORMAT_VERSION],
		'%s"chunk": [%d,%d],' % [_INDENT, cx, cy],
		'%s"plane": %d,' % [_INDENT, plane],
		'%s"size": %d,' % [_INDENT, size],
		'%s"floor_names": %s,' % [_INDENT, _name_list_text(floor_names)],
		'%s"area_names": %s,' % [_INDENT, _name_list_text(area_names)],
	])

	lines.append_array(_grid_lines("heights", heights,
		_Const.CHUNK_CORNERS_PER_SIDE))
	lines.append_array(_grid_lines("floors", floors, size))
	lines.append_array(_grid_lines("flags", flags, size))
	lines.append_array(_grid_lines("areas", areas, size))
	lines.append_array(_object_lines())
	lines.append("}")

	return "\n".join(lines) + "\n"


## Write the canonical text to an OS path.
func write_file(path: String) -> Error:
	var file := FileAccess.open(path, FileAccess.WRITE)

	if file == null:
		return FileAccess.get_open_error()

	file.store_string(to_text())

	return OK


func _grid_lines(key: String, flat: PackedInt32Array,
		side: int) -> PackedStringArray:
	var lines := PackedStringArray(['%s"%s": [' % [_INDENT, key]])

	for row_index: int in side:
		var row := flat.slice(row_index * side, (row_index + 1) * side)
		var comma := "," if row_index < side - 1 else ""

		lines.append(_ROW_INDENT + _row_text(row) + comma)

	lines.append(_INDENT + "],")

	return lines


func _object_lines() -> PackedStringArray:
	if objects.is_empty():
		return PackedStringArray(['%s"objects": []' % _INDENT])

	var lines := PackedStringArray(['%s"objects": [' % _INDENT])

	for index: int in objects.size():
		var thing: Dictionary = objects[index]
		var comma := "," if index < objects.size() - 1 else ""

		lines.append(_ROW_INDENT
			+ '{"kind":"%s","x":%d,"y":%d,"rotation":%d}' % [thing["kind"],
				thing["x"], thing["y"], thing["rotation"]]
			+ comma)

	lines.append(_INDENT + "]")

	return lines


static func _row_text(row: PackedInt32Array) -> String:
	var parts := PackedStringArray()

	for value: int in row:
		parts.append(str(value))

	return "[" + ",".join(parts) + "]"


static func _name_list_text(names: PackedStringArray) -> String:
	var quoted := PackedStringArray()

	for name: String in names:
		quoted.append('"%s"' % name)

	return "[" + ",".join(quoted) + "]"


# ─── Parity ──────────────────────────────────────────────────────────────────

## What this chunk file MEANS, one fact on each line. The Python
## `semantic_dump` writes the same text for the same file. See its docstring
## for the layout.
func semantic_dump() -> String:
	var size: int = _Const.CHUNK_SIZE
	var origin_x := cx * size
	var origin_y := cy * size
	var lines := PackedStringArray([
		"chunk %d %d plane %d" % [cx, cy, plane],
		"floors " + " ".join(floor_names),
		"areas " + " ".join(area_names),
	])

	for ly: int in size:
		for lx: int in size:
			var corners := corner_heights(lx, ly)

			lines.append("tile %d %d %d %d %d %d %d %d %s %s" % [
				origin_x + lx, origin_y + ly,
				corners[0], corners[1], corners[2], corners[3],
				tile_height(lx, ly), flags[ly * size + lx],
				floor_name(lx, ly), area_name(lx, ly)])

	for thing: Dictionary in global_objects():
		lines.append("object %s %d %d %d" % [thing["kind"], thing["x"],
			thing["y"], thing["rotation"]])

	return "\n".join(lines) + "\n"


## The SHA-256 hex digest of [method semantic_dump].
func semantic_digest() -> String:
	var context := HashingContext.new()

	context.start(HashingContext.HASH_SHA256)
	context.update(semantic_dump().to_utf8_buffer())

	return context.finish().hex_encode()
