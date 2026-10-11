@tool
class_name StructureTemplate
extends RefCounted
## A template of the Build tab (DESIGN-0013 section 6.6): a saved structure
## that the Place tool writes as a copy. Read it, write it, capture it from
## the tile selection, turn it, and mirror it.
##
## A template is a copy, not a link (decision 1). The Place tool writes plain
## facts into the chunk files. Nothing links a template copy to its template,
## so an edit of the template changes no structure in the world.
##
## ## The file
##
## One file holds one template, `blackout/world/structures/<key>.json`. The
## server never loads it. `world/tests/test_structure_templates.py` checks
## each name in it against the tables of the server. The canonical text is
## the layout of a chunk file: one grid row on each line, row 0 first. Row 0
## is the south edge, and item 0 of a row is the west edge.
##
## ```text
## format       STRUCTURE_FORMAT_VERSION
## key          the template key, the same as the file name
## size         [W, H] tiles
## floor_names, area_names, wall_names
## planes       [{plane, cover, heights, floors, flags, areas, walls}, ...]
## objects      [{kind, x, y, plane, rotation, text}, ...]
## ```
##
## - `plane` is relative: 0 is the plane where the Place tool writes it. The
##   planes go up, and each plane holds at least one covered tile.
## - `cover` is 1 on a tile that the template owns. The Place tool writes only
##   a covered tile. The other tiles of the footprint keep their facts.
## - `heights` is (W + 1) x (H + 1) corners, in height steps above the base:
##   the lowest corner of a covered tile of plane 0.
## - An object stands on a covered tile. `text` is optional, as in a chunk
##   file.
##
## ## Cover
##
## [method capture] covers each selected tile of the ground plane, and each
## selected tile of a plane above that is not void. A void tile of a plane
## above is air, and a copy of air would cut a hole in a structure there.
##
## ## No exceptions in GDScript
##
## A read always returns a template. A bad file sets [member error], and the
## caller must check it. The first refusal wins.

const _Const := preload("res://autoload/blackout_constants.gd")

## The keys of a template file, in the order that the writer writes them.
const KEYS := ["format", "key", "size", "floor_names", "area_names", "wall_names",
	"planes", "objects"]

## The keys of one plane, in the order that the writer writes them.
const PLANE_KEYS := ["plane", "cover", "heights", "floors", "flags", "areas", "walls"]

## The keys of one object, in the order that the writer writes them. The
## writer writes [constant ChunkFile.OBJECT_TEXT_KEY] last, only when it has
## words.
const OBJECT_KEYS := ["kind", "x", "y", "plane", "rotation"]

## The largest side of a template, in tiles: the side of the block. A larger
## footprint cannot fit in the editor.
const SIDE_MAX: int = _Const.CHUNK_SIZE * TerrainWorld.BLOCK_SIDE

## The largest relative height: the full range of a corner.
const RELATIVE_HEIGHT_MAX: int = _Const.CHUNK_HEIGHT_MAX - _Const.CHUNK_HEIGHT_MIN

## Where the templates live, from the Godot project root, as for the chunk
## files.
const GAME_DIRECTORY_FROM_PROJECT := "../blackout"

## The wall bits after a quarter turn clockwise: N to E, E to S, S to W, and
## W to N. And after a mirror on the east-west axis: E and W swap.
const _TURN_BITS := [
	[_Const.TILE_FLAG_WALL_NORTH, _Const.TILE_FLAG_WALL_EAST],
	[_Const.TILE_FLAG_WALL_EAST, _Const.TILE_FLAG_WALL_SOUTH],
	[_Const.TILE_FLAG_WALL_SOUTH, _Const.TILE_FLAG_WALL_WEST],
	[_Const.TILE_FLAG_WALL_WEST, _Const.TILE_FLAG_WALL_NORTH],
]
const _MIRROR_BITS := [
	[_Const.TILE_FLAG_WALL_EAST, _Const.TILE_FLAG_WALL_WEST],
	[_Const.TILE_FLAG_WALL_WEST, _Const.TILE_FLAG_WALL_EAST],
]

const _INDENT := "  "


## One plane of a template. Every grid is flat, row 0 first.
class Layer:
	## The plane, relative to the plane of the Place tool.
	var plane := 0

	## 1 on a covered tile, else 0. W x H.
	var cover := PackedInt32Array()

	## Height steps above the base. (W + 1) x (H + 1).
	var heights := PackedInt32Array()

	## Indexes into the name lists of the template. W x H each.
	var floors := PackedInt32Array()
	var flags := PackedInt32Array()
	var areas := PackedInt32Array()
	var walls := PackedInt32Array()

	## The grids of a W x H plane, all 0.
	static func sized(on_plane: int, size: Vector2i) -> Layer:
		var layer := Layer.new()
		var tiles := size.x * size.y

		layer.plane = on_plane
		layer.heights.resize((size.x + 1) * (size.y + 1))
		layer.cover.resize(tiles)
		layer.floors.resize(tiles)
		layer.flags.resize(tiles)
		layer.areas.resize(tiles)
		layer.walls.resize(tiles)

		return layer

	func cover_count() -> int:
		var count := 0

		for mark: int in cover:
			count += mark

		return count


var key := ""

## W x H tiles.
var size := Vector2i.ZERO

var floor_names := PackedStringArray()
var area_names := PackedStringArray()
var wall_names := PackedStringArray()

## One layer for each plane with cover, lowest first. The first is plane 0.
var layers: Array[Layer] = []

## Each object as `{kind, x, y, plane, rotation, text}`, at template tiles.
var objects: Array[Dictionary] = []

## Empty for a good template. Otherwise the first reason it was refused.
var error := ""

## The world tile of the south-west tile at [method capture]. The file does
## not hold it. The readout of a move gives the distance from it.
var origin := Vector2i.ZERO

## The plane of plane 0 at [method capture]. The file does not hold it. A
## move writes its copy on this plane, so a selection with no cover on the
## edited plane does not drop to the edited plane.
var base_plane := 0

var _name_regex := RegEx.create_from_string(_Const.CHUNK_NAME_PATTERN)


# ─── Addressing ─────────────────────────────────────────────────────────────

func tile_index(tile: Vector2i) -> int:
	return tile.y * size.x + tile.x


func corner_index(corner: Vector2i) -> int:
	return corner.y * (size.x + 1) + corner.x


## The highest relative plane.
func top_plane() -> int:
	return layers[layers.size() - 1].plane if not layers.is_empty() else 0


## The layer of relative plane `on_plane`, or null.
func layer_on(on_plane: int) -> Layer:
	for layer: Layer in layers:
		if layer.plane == on_plane:
			return layer

	return null


## Every covered tile of `layer`, south row first.
func covered_tiles(layer: Layer) -> Array[Vector2i]:
	var found: Array[Vector2i] = []

	for y: int in size.y:
		for x: int in size.x:
			if layer.cover[y * size.x + x] == 1:
				found.append(Vector2i(x, y))

	return found


## Every corner of a covered tile of `layer`, once each.
func covered_corners(layer: Layer) -> Array[Vector2i]:
	return StructureTools.tile_corners(covered_tiles(layer))


## The objects that stand on `tile` of relative plane `on_plane`.
func objects_at(tile: Vector2i, on_plane: int) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	for thing: Dictionary in objects:
		if thing["x"] == tile.x and thing["y"] == tile.y and thing["plane"] == on_plane:
			found.append(thing)

	return found


## The number of covered tiles on every plane.
func cover_count() -> int:
	var count := 0

	for layer: Layer in layers:
		count += layer.cover_count()

	return count


# ─── Files ──────────────────────────────────────────────────────────────────

## The world template directory, as an OS path.
static func world_directory() -> String:
	var project := ProjectSettings.globalize_path("res://")
	var game := project.path_join(GAME_DIRECTORY_FROM_PROJECT)

	return game.path_join(_Const.STRUCTURE_DIRECTORY).simplify_path()


## The path of the template `template_key` in `directory`.
static func path_for(directory: String, template_key: String) -> String:
	return directory.path_join(template_key + _Const.STRUCTURE_FILE_SUFFIX)


## The key of each template file in `directory`, sorted. An empty list when
## the directory does not exist.
static func list_keys(directory: String) -> PackedStringArray:
	var found := PackedStringArray()

	if not DirAccess.dir_exists_absolute(directory):
		return found

	for file_name: String in DirAccess.get_files_at(directory):
		if file_name.ends_with(_Const.STRUCTURE_FILE_SUFFIX):
			found.append(file_name.trim_suffix(_Const.STRUCTURE_FILE_SUFFIX))

	found.sort()

	return found


## Why `template_key` cannot name a template, or "" when it can.
static func key_problem(template_key: String) -> String:
	var pattern := RegEx.create_from_string(_Const.CHUNK_NAME_PATTERN)

	if not ChunkFile._whole_match(pattern, template_key):
		return "A template key uses only a-z, 0-9, and _. \"%s\" does not." % template_key

	return ""


## Read and check one template file. The key must be the file name. Check
## [member error] after.
static func read_file(path: String) -> StructureTemplate:
	var text := FileAccess.get_file_as_string(path)

	if text.is_empty():
		var refused := StructureTemplate.new()

		refused.error = "cannot read %s" % path
		return refused

	var template := parse_text(text)
	var stem := path.get_file().trim_suffix(_Const.STRUCTURE_FILE_SUFFIX)

	if template.error.is_empty() and template.key != stem:
		template.error = "the key %s is not the file name %s" % [template.key, stem]

	return template


## Write the canonical text to an OS path. Makes the directory.
func write_file(path: String) -> Error:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())

	var file := FileAccess.open(path, FileAccess.WRITE)

	if file == null:
		return FileAccess.get_open_error()

	file.store_string(to_text())

	return OK


# ─── Reading ────────────────────────────────────────────────────────────────

## Parse and check the text of a template. Check [member error] after.
static func parse_text(text: String) -> StructureTemplate:
	var parser := JSON.new()

	if parser.parse(text) != OK:
		var refused := StructureTemplate.new()

		refused.error = "not JSON: %s" % parser.get_error_message()
		return refused

	return from_dict(parser.data)


## Check a parsed template, in this order: the keys and the scalars, the
## name lists, the planes, and the objects.
static func from_dict(data: Variant) -> StructureTemplate:
	var result := StructureTemplate.new()

	if not (data is Dictionary):
		result.error = "a template must hold one JSON object"
		return result

	result._read_header(data)
	result.floor_names = result._names(data.get("floor_names"), "floor_names")
	result.area_names = result._names(data.get("area_names"), "area_names")
	result.wall_names = result._names(data.get("wall_names"), "wall_names")
	result._read_planes(data.get("planes"))
	result._read_objects(data.get("objects"))

	return result


func _fail(message: String) -> void:
	if error.is_empty():
		error = message


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

	if _as_int(data["format"], "format") != _Const.STRUCTURE_FORMAT_VERSION:
		_fail("format is not %d" % _Const.STRUCTURE_FORMAT_VERSION)

	key = str(data["key"])

	if not (data["key"] is String) or not ChunkFile._whole_match(_name_regex, key):
		_fail("key %s is not a name" % str(data["key"]))

	var sides: Variant = data["size"]

	if not (sides is Array) or sides.size() != 2:
		_fail("size must be [W, H]")
		return

	size = Vector2i(_int_in(sides[0], 1, SIDE_MAX, "size W"),
		_int_in(sides[1], 1, SIDE_MAX, "size H"))


func _names(value: Variant, what: String) -> PackedStringArray:
	var names := PackedStringArray()

	if not (value is Array) or value.is_empty():
		_fail("%s must be a list with at least one name" % what)
		return names

	for name: Variant in value:
		if not (name is String) or not ChunkFile._whole_match(_name_regex, name):
			_fail("%s holds %s, which is not a name" % [what, str(name)])
			return names

		if names.has(name):
			_fail("%s holds a name two times" % what)

		names.append(name)

	return names


func _read_planes(value: Variant) -> void:
	if not error.is_empty():
		return

	if not (value is Array) or value.is_empty():
		_fail("planes must be a list with at least one plane")
		return

	for index: int in value.size():
		var layer := _read_layer(value[index], index)

		if not error.is_empty():
			return

		if not layers.is_empty() and layer.plane <= layers[layers.size() - 1].plane:
			_fail("plane %d must be above the plane before it" % layer.plane)

		if layer.cover_count() == 0:
			_fail("plane %d covers no tile" % layer.plane)

		layers.append(layer)

	if layers[0].plane != 0:
		_fail("the first plane must be plane 0")


func _read_layer(value: Variant, index: int) -> Layer:
	var layer := Layer.new()

	if not (value is Dictionary):
		_fail("planes[%d] must be an object" % index)
		return layer

	var keys: Array = value.keys()
	var expected := PLANE_KEYS.duplicate()

	keys.sort()
	expected.sort()

	if keys != expected:
		_fail("planes[%d] keys wrong: %s" % [index, str(keys)])
		return layer

	layer.plane = _int_in(value["plane"], 0, _Const.CHUNK_PLANE_MAX, "plane")
	layer.cover = _grid(value["cover"], size, 0, 1, "cover")
	layer.heights = _grid(value["heights"], size + Vector2i.ONE, -RELATIVE_HEIGHT_MAX,
		RELATIVE_HEIGHT_MAX, "heights")
	layer.floors = _grid(value["floors"], size, 0, floor_names.size() - 1, "floors")
	layer.flags = _grid(value["flags"], size, 0, _Const.TILE_FLAGS_ALL, "flags")
	layer.areas = _grid(value["areas"], size, 0, area_names.size() - 1, "areas")
	layer.walls = _grid(value["walls"], size, 0, wall_names.size() - 1, "walls")

	return layer


## `shape.y` rows of `shape.x` ints in low..high, as one flat array.
func _grid(value: Variant, shape: Vector2i, low: int, high: int,
		what: String) -> PackedInt32Array:
	var flat := PackedInt32Array()

	if not (value is Array) or value.size() != shape.y:
		_fail("%s must hold %d rows" % [what, shape.y])
		return flat

	for row_index: int in shape.y:
		var row: Variant = value[row_index]

		if not (row is Array) or row.size() != shape.x:
			_fail("%s row %d must hold %d values" % [what, row_index, shape.x])
			return flat

		for column: int in shape.x:
			flat.append(_int_in(row[column], low, high,
				"%s[%d][%d]" % [what, row_index, column]))

	return flat


func _read_objects(value: Variant) -> void:
	if not error.is_empty():
		return

	if not (value is Array):
		_fail("objects must be a list")
		return

	for index: int in value.size():
		var thing := _read_object(value[index], index)

		if not error.is_empty():
			return

		objects.append(thing)


func _read_object(item: Variant, index: int) -> Dictionary:
	if not (item is Dictionary):
		_fail("object %d must be an object" % index)
		return {}

	var keys: Array = item.keys()
	var expected := OBJECT_KEYS.duplicate()

	keys.erase(ChunkFile.OBJECT_TEXT_KEY)
	keys.sort()
	expected.sort()

	if keys != expected:
		_fail("object %d must have exactly the keys %s, and may have %s"
			% [index, OBJECT_KEYS, ChunkFile.OBJECT_TEXT_KEY])
		return {}

	var thing := {
		"kind": str(item["kind"]),
		"x": _int_in(item["x"], 0, size.x - 1, "object %d x" % index),
		"y": _int_in(item["y"], 0, size.y - 1, "object %d y" % index),
		"plane": _as_int(item["plane"], "object %d plane" % index),
		"rotation": _int_in(item["rotation"], 0, _Const.CHUNK_ROTATION_COUNT - 1,
			"object %d rotation" % index),
		"text": _object_text(item, index),
	}

	_check_object_place(thing, item["kind"], index)

	return thing


## The kind is a name, and the object stands on a covered tile of a plane
## of the template.
func _check_object_place(thing: Dictionary, kind: Variant, index: int) -> void:
	if not (kind is String) or not ChunkFile._whole_match(_name_regex, kind):
		_fail("object %d has the kind %s" % [index, str(kind)])
		return

	var layer := layer_on(thing["plane"])

	if layer == null:
		_fail("object %d stands on plane %d, which the template has not" % [index,
			thing["plane"]])
		return

	if error.is_empty() and layer.cover[tile_index(Vector2i(thing["x"], thing["y"]))] != 1:
		_fail("object %d stands on a tile that the template does not cover" % index)


func _object_text(item: Dictionary, index: int) -> String:
	if not item.has(ChunkFile.OBJECT_TEXT_KEY):
		return ""

	var text: Variant = item[ChunkFile.OBJECT_TEXT_KEY]

	if not (text is String):
		_fail("object %d has the text %s, which is not a string" % [index, str(text)])
		return ""

	var problem := ChunkFile.text_problem(text)

	if not problem.is_empty():
		_fail("object %d %s" % [index, problem])
		return ""

	return text


# ─── Writing ────────────────────────────────────────────────────────────────

## The canonical text. See the class comment.
func to_text() -> String:
	var lines := PackedStringArray([
		"{",
		'%s"format": %d,' % [_INDENT, _Const.STRUCTURE_FORMAT_VERSION],
		'%s"key": "%s",' % [_INDENT, key],
		'%s"size": [%d,%d],' % [_INDENT, size.x, size.y],
		'%s"floor_names": %s,' % [_INDENT, ChunkFile._name_list_text(floor_names)],
		'%s"area_names": %s,' % [_INDENT, ChunkFile._name_list_text(area_names)],
		'%s"wall_names": %s,' % [_INDENT, ChunkFile._name_list_text(wall_names)],
		'%s"planes": [' % _INDENT,
	])

	for index: int in layers.size():
		lines.append_array(_layer_lines(layers[index], index == layers.size() - 1))

	lines.append(_INDENT + "],")
	lines.append_array(_object_lines())
	lines.append("}")

	return "\n".join(lines) + "\n"


func _layer_lines(layer: Layer, last: bool) -> PackedStringArray:
	var inner := _INDENT.repeat(3)
	var lines := PackedStringArray([_INDENT.repeat(2) + "{",
		'%s"plane": %d,' % [inner, layer.plane]])
	var grids := [["cover", layer.cover, size], ["heights", layer.heights,
		size + Vector2i.ONE], ["floors", layer.floors, size], ["flags", layer.flags, size],
		["areas", layer.areas, size], ["walls", layer.walls, size]]

	for index: int in grids.size():
		var grid: Array = grids[index]

		lines.append_array(_grid_lines(grid[0], grid[1], grid[2],
			index == grids.size() - 1))

	lines.append(_INDENT.repeat(2) + ("}" if last else "},"))

	return lines


func _grid_lines(grid_key: String, flat: PackedInt32Array, shape: Vector2i,
		last: bool) -> PackedStringArray:
	var lines := PackedStringArray(['%s"%s": [' % [_INDENT.repeat(3), grid_key]])

	for row_index: int in shape.y:
		var row := flat.slice(row_index * shape.x, (row_index + 1) * shape.x)
		var comma := "," if row_index < shape.y - 1 else ""

		lines.append(_INDENT.repeat(4) + ChunkFile._row_text(row) + comma)

	lines.append(_INDENT.repeat(3) + ("]" if last else "],"))

	return lines


func _object_lines() -> PackedStringArray:
	if objects.is_empty():
		return PackedStringArray(['%s"objects": []' % _INDENT])

	var lines := PackedStringArray(['%s"objects": [' % _INDENT])

	for index: int in objects.size():
		var thing: Dictionary = objects[index]
		var comma := "," if index < objects.size() - 1 else ""
		var text: String = thing["text"]
		var words := "" if text.is_empty() \
			else ',"%s":"%s"' % [ChunkFile.OBJECT_TEXT_KEY, text]

		lines.append(_INDENT.repeat(2)
			+ '{"kind":"%s","x":%d,"y":%d,"plane":%d,"rotation":%d%s}' % [thing["kind"],
				thing["x"], thing["y"], thing["plane"], thing["rotation"], words]
			+ comma)

	lines.append(_INDENT + "]")

	return lines


# ─── Capture ────────────────────────────────────────────────────────────────

## A template of the tiles of `keys`, a set of Vector3i(x, y, plane), from
## `base_plane` up. `sets` maps a plane to its [ChunkSet]. Check
## [member error] after: a selection that covers no tile gives no template.
## See "Cover" in the class comment.
static func capture(sets: Dictionary, keys: Dictionary, base_plane: int,
		template_key: String) -> StructureTemplate:
	var result := StructureTemplate.new()
	var covered := _covered_keys(sets, keys, base_plane)

	result.key = template_key

	if covered.is_empty():
		result.error = "The tile selection covers no tile on plane %d or above." \
			% base_plane
		return result

	var bounds := _bounds(covered)
	var low_plane := _lowest_plane(covered)

	result.size = bounds.size
	result.origin = bounds.position
	result.base_plane = low_plane
	result._capture_layers(sets, covered, bounds, low_plane)
	result._capture_objects(sets, bounds, low_plane)

	return result


## Each key of `keys` on `base_plane` or above that a template covers.
static func _covered_keys(sets: Dictionary, keys: Dictionary, base_plane: int) -> Dictionary:
	var covered := {}

	for at: Vector3i in keys:
		var chunks: ChunkSet = sets.get(at.z)

		if at.z < base_plane or chunks == null or not chunks.has_tile(Vector2i(at.x, at.y)):
			continue

		if at.z == _Const.TILE_GROUND_PLANE \
				or chunks.get_floor(Vector2i(at.x, at.y)) != _Const.TILE_VOID_FLOOR:
			covered[at] = true

	return covered


static func _bounds(covered: Dictionary) -> Rect2i:
	var first: Vector3i = covered.keys()[0]
	var low := Vector2i(first.x, first.y)
	var high := low

	for at: Vector3i in covered:
		low = low.min(Vector2i(at.x, at.y))
		high = high.max(Vector2i(at.x, at.y))

	return Rect2i(low, high - low + Vector2i.ONE)


static func _lowest_plane(covered: Dictionary) -> int:
	var lowest: int = _Const.CHUNK_PLANE_MAX

	for at: Vector3i in covered:
		lowest = mini(lowest, at.z)

	return lowest


## One layer for each plane with cover. Heights are above the lowest corner
## of a covered tile of the lowest plane.
func _capture_layers(sets: Dictionary, covered: Dictionary, bounds: Rect2i,
		low_plane: int) -> void:
	var base := 0

	for on_plane: int in range(low_plane, _Const.CHUNK_PLANE_MAX + 1):
		var chunks: ChunkSet = sets.get(on_plane)

		if chunks == null:
			continue

		var layer := Layer.sized(on_plane - low_plane, size)

		for at: Vector3i in covered:
			if at.z == on_plane:
				layer.cover[tile_index(Vector2i(at.x, at.y) - bounds.position)] = 1

		if layer.cover_count() == 0:
			continue

		if layers.is_empty():
			base = _lowest_covered_corner(chunks, layer, bounds.position)

		_capture_layer(chunks, layer, bounds.position, base)
		layers.append(layer)


func _lowest_covered_corner(chunks: ChunkSet, layer: Layer, origin: Vector2i) -> int:
	var heights: Array[int] = []

	for corner: Vector2i in covered_corners(layer):
		heights.append(chunks.get_corner(origin + corner))

	return heights.min()


## The heights and the tile facts of every tile of the bounds, covered or
## not, so the file shows the ground around a covered tile.
func _capture_layer(chunks: ChunkSet, layer: Layer, origin: Vector2i, base: int) -> void:
	for j: int in size.y + 1:
		for i: int in size.x + 1:
			layer.heights[corner_index(Vector2i(i, j))] = \
				chunks.get_corner(origin + Vector2i(i, j)) - base

	for y: int in size.y:
		for x: int in size.x:
			var tile := origin + Vector2i(x, y)
			var index := tile_index(Vector2i(x, y))

			layer.floors[index] = ChunkSet._name_index(floor_names, chunks.get_floor(tile))
			layer.flags[index] = chunks.get_flags(tile)
			layer.areas[index] = ChunkSet._name_index(area_names, chunks.get_area(tile))
			layer.walls[index] = ChunkSet._name_index(wall_names, chunks.get_wall_style(tile))


## Each object on a covered tile, plane by plane, south row first.
func _capture_objects(sets: Dictionary, bounds: Rect2i, low_plane: int) -> void:
	for layer: Layer in layers:
		var chunks: ChunkSet = sets[low_plane + layer.plane]

		for tile: Vector2i in covered_tiles(layer):
			for thing: Dictionary in chunks.objects_at(bounds.position + tile):
				objects.append({"kind": thing["kind"], "x": tile.x, "y": tile.y,
					"plane": layer.plane, "rotation": thing["rotation"],
					"text": thing["text"]})


# ─── Turn and mirror ────────────────────────────────────────────────────────

## This template, a quarter turn clockwise from above. Tile (x, y) moves to
## (y, W - 1 - x), corner (i, j) to (j, W - i), each wall bit one edge
## clockwise, and each object rotation up by one. W and H swap.
func turned() -> StructureTemplate:
	var width := size.x

	return _remapped(Vector2i(size.y, size.x),
		func(tile: Vector2i) -> Vector2i: return Vector2i(tile.y, width - 1 - tile.x),
		func(corner: Vector2i) -> Vector2i: return Vector2i(corner.y, width - corner.x),
		_TURN_BITS,
		func(rotation: int) -> int: return (rotation + 1) % _Const.CHUNK_ROTATION_COUNT)


## This template, mirrored on the east-west axis. x moves to W - 1 - x, the
## east and west wall bits swap, and rotation r goes to (4 - r) mod 4. A
## mirror turns a model and does not mirror its mesh.
func mirrored() -> StructureTemplate:
	var width := size.x
	var count: int = _Const.CHUNK_ROTATION_COUNT

	return _remapped(size,
		func(tile: Vector2i) -> Vector2i: return Vector2i(width - 1 - tile.x, tile.y),
		func(corner: Vector2i) -> Vector2i: return Vector2i(width - corner.x, corner.y),
		_MIRROR_BITS,
		func(rotation: int) -> int: return (count - rotation) % count)


## A copy of this template with each tile, corner, wall bit, and object
## moved by the maps.
func _remapped(new_size: Vector2i, tile_map: Callable, corner_map: Callable,
		bit_pairs: Array, rotation_map: Callable) -> StructureTemplate:
	var result := StructureTemplate.new()

	result.key = key
	result.origin = origin
	result.base_plane = base_plane
	result.size = new_size
	result.floor_names = floor_names.duplicate()
	result.area_names = area_names.duplicate()
	result.wall_names = wall_names.duplicate()

	for layer: Layer in layers:
		result.layers.append(_remapped_layer(result, layer, tile_map, corner_map, bit_pairs))

	for thing: Dictionary in objects:
		var moved: Vector2i = tile_map.call(Vector2i(thing["x"], thing["y"]))

		result.objects.append({"kind": thing["kind"], "x": moved.x, "y": moved.y,
			"plane": thing["plane"], "rotation": rotation_map.call(thing["rotation"]),
			"text": thing["text"]})

	return result


func _remapped_layer(result: StructureTemplate, layer: Layer, tile_map: Callable,
		corner_map: Callable, bit_pairs: Array) -> Layer:
	var moved := Layer.sized(layer.plane, result.size)

	for j: int in size.y + 1:
		for i: int in size.x + 1:
			moved.heights[result.corner_index(corner_map.call(Vector2i(i, j)))] = \
				layer.heights[corner_index(Vector2i(i, j))]

	for y: int in size.y:
		for x: int in size.x:
			var from := tile_index(Vector2i(x, y))
			var to := result.tile_index(tile_map.call(Vector2i(x, y)))

			moved.cover[to] = layer.cover[from]
			moved.floors[to] = layer.floors[from]
			moved.flags[to] = moved_bits(layer.flags[from], bit_pairs)
			moved.areas[to] = layer.areas[from]
			moved.walls[to] = layer.walls[from]

	return moved


## `flags` with each wall bit moved by `bit_pairs`, `[from, to]` each. The
## other bits stay.
static func moved_bits(flags: int, bit_pairs: Array) -> int:
	var result := flags & ~_Const.TILE_FLAGS_WALLS
	var walls := flags & _Const.TILE_FLAGS_WALLS

	for pair: Array in bit_pairs:
		if walls & pair[0]:
			result |= pair[1]
			walls &= ~pair[0]

	return result | walls
