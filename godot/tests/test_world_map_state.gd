extends Node
## Unit tests for WorldMapState, the world map in the client.
##
##     godot --headless --path godot res://tests/test_world_map_state.tscn
##
## Needs nothing running. The payloads are hand-built in the shape of
## `statefeed/worldmap.py`, with every number a FLOAT.

const Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_the_index_gives_the_planes_and_the_bounds()
	_a_summary_paints_its_tiles_north_up()
	_a_summary_before_the_index_is_painted_when_the_index_lands()
	_icons_come_from_the_objects_with_a_map_icon()
	_labels_are_kept_for_each_plane()
	_the_two_channels_fire_their_signals()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: world_map_state")
	get_tree().quit(0)


func _the_index_gives_the_planes_and_the_bounds() -> void:
	var map := WorldMapState.new()
	var size: int = Const.CHUNK_SIZE

	map.ingest_index(_index([[-1, 0, 0], [1, 1, 0], [0, 0, 1]]))

	_expect(map.has_data(), "an index gives data")
	_expect(map.planes == [0, 1], "the planes, lowest first")
	_expect(map.bounds(0) == Rect2i(Vector2i(-size, 0), Vector2i(3, 2) * size),
		"the bounds cover every chunk of the plane")
	_expect(map.image(0).get_size() == Vector2i(3, 2) * size,
		"the image has one pixel for each tile")
	_expect(map.image(2) == null, "a plane with no chunk has no image")


func _a_summary_paints_its_tiles_north_up() -> void:
	var map := WorldMapState.new()
	var size: int = Const.CHUNK_SIZE
	var water_class := _class_of("water_bed", true)
	var tiles := _tiles(_class_of("sand", false))

	# The south-west tile is water. Row 0 of the image is north.
	tiles[0] = Const.WORLD_MAP_ALPHABET[water_class]
	map.ingest_index(_index([[0, 0, 0]]))
	map.ingest_summary(_summary(0, 0, 0, tiles))

	var image := map.image(0)
	var south_west := image.get_pixel(0, size - 1)
	var north_west := image.get_pixel(0, 0)

	_expect(_near(south_west, MapRaster.tile_colour("water_bed", true)),
		"the south-west tile is on the bottom row")
	_expect(_near(north_west, MapRaster.tile_colour("sand", false)),
		"a sand tile shows the sand colour")


func _a_summary_before_the_index_is_painted_when_the_index_lands() -> void:
	var map := WorldMapState.new()

	map.ingest_summary(_summary(0, 0, 0, _tiles(_class_of("sand", false))))
	map.ingest_index(_index([[0, 0, 0]]))

	_expect(_near(map.image(0).get_pixel(5, 5),
		MapRaster.tile_colour("sand", false)), "a waiting summary is painted")


func _icons_come_from_the_objects_with_a_map_icon() -> void:
	var map := WorldMapState.new()
	var facility := _kind_of(Const.OBJECT_CATEGORY_FACILITY)
	var npc := _kind_of(Const.OBJECT_CATEGORY_NPC)
	var summary := _summary(0, 0, 0, _tiles(0))

	summary["objects"] = [
		{"kind": facility, "x": 3.0, "y": 4.0},
		{"kind": npc, "x": 5.0, "y": 6.0},
	]
	map.ingest_index(_index([[0, 0, 0]]))
	map.ingest_summary(summary)

	var icons := map.icons(0)

	_expect(icons.size() == 1, "an NPC spawn has no map icon")
	_expect(icons[0]["tile"] == Vector2i(3, 4)
		and icons[0]["category"] == Const.OBJECT_CATEGORY_FACILITY,
		"a facility has its icon on its tile")


func _labels_are_kept_for_each_plane() -> void:
	var map := WorldMapState.new()
	var index := _index([[0, 0, 0], [0, 0, 1]])

	index["labels"] = [
		{"text": "Oasis", "x": 5.0, "y": 5.0, "plane": 0.0},
		{"text": "Loft", "x": 2.0, "y": 2.0, "plane": 1.0},
	]
	map.ingest_index(index)

	_expect(map.labels_of(1).size() == 1 and map.labels_of(1)[0]["text"] == "Loft",
		"the labels of one plane")


func _the_two_channels_fire_their_signals() -> void:
	var map := WorldMapState.new()
	var heard: Array[String] = []

	map.index_arrived.connect(func(): heard.append("index"))
	map.plane_changed.connect(func(plane): heard.append("plane %d" % plane))

	_expect(map.ingest(Const.CH_WORLD_MAP, _index([[0, 0, 0]])),
		"the index channel is taken")
	_expect(map.ingest(Const.CH_WORLD_MAP_CHUNK, _summary(0, 0, 0, _tiles(0))),
		"the summary channel is taken")
	_expect(not map.ingest(Const.CH_ROOM_INFO, {}), "another channel is not")
	_expect(heard == ["index", "plane 0"], "each fires its signal")


func _index(chunks: Array) -> Dictionary:
	var planes := {}
	var floats: Array = []

	for entry: Array in chunks:
		planes[entry[2]] = true
		floats.append([float(entry[0]), float(entry[1]), float(entry[2])])

	return {"planes": planes.keys().map(func(p): return float(p)),
		"chunks": floats, "labels": []}


func _summary(cx: int, cy: int, plane: int, tiles: String) -> Dictionary:
	return {"chunk": [float(cx), float(cy)], "plane": float(plane),
		"tiles": tiles, "objects": []}


func _tiles(tile_class: int) -> String:
	var size: int = Const.CHUNK_SIZE

	return Const.WORLD_MAP_ALPHABET[tile_class].repeat(size * size)


func _class_of(floor_name: String, unwalkable: bool) -> int:
	return Const.TILE_FLOOR_TYPES.find(floor_name) * 2 + int(unwalkable)


func _kind_of(category: String) -> String:
	for kind: String in Const.OBJECT_KINDS:
		if Const.OBJECT_KINDS[kind] == category:
			return kind

	return ""


## Two colours within one step of an 8-bit channel. An image stores 8 bits.
func _near(first: Color, second: Color) -> bool:
	var step := 1.0 / 255.0

	return absf(first.r - second.r) <= step and absf(first.g - second.g) <= step \
		and absf(first.b - second.b) <= step and absf(first.a - second.a) <= step


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
