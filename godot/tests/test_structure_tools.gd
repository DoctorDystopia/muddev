extends Node
## Tests for the Build tools of the terrain editor: [StructureTools] and
## [RoomFill] (DESIGN-0013 Phases S1 and S2).
##
##     godot --headless --path godot res://tests/test_structure_tools.tscn
##
## Needs nothing running and no editor. The plugin only routes the mouse to
## these classes, so these cases cover every rule that a Build tool applies:
##
## 1. A wall line keeps to one axis, takes the side that is not void, and a
##    removal clears both sides.
## 2. A room levels the ground, paints the floor and the area, walls the
##    inner border, and blocks the ring outside when asked.
## 3. A doorway clears the wall on both sides of the edge.
## 4. A level above floors the plane above, flat at one plane rise.
## 5. Stairs place a climb pair, and floor a void landing. A second click
##    stacks no second pair.
## 6. The fill of a closed room stops at its walls, and an open one does not.
## 7. One gesture is one undo entry, over two planes.
## 8. A roof meets the walls at one plane rise, is Blocked, refuses a floor
##    above, and Shift takes it away. [RoofShapes] has its own test.
## 9. A wall line and a room put their wall style on each new wall. The
##    Wall style brush paints only the tiles with a wall. A save writes the
##    styles in format 2 (DESIGN-0013 Phase S3).
## 10. A tile holds one decor. A place replaces it, and Shift removes it.
##     Decor stands on a Blocked tile, but not on a void tile. The object
##     list can hide decor (DESIGN-0013 Phase S4).

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_a_wall_line_keeps_to_one_axis()
	_a_wall_line_takes_the_side_that_is_not_void()
	_a_removal_clears_both_sides()
	_a_room_walls_its_inner_border()
	_a_room_levels_the_ground_to_its_highest_corner()
	_a_room_blocks_the_ring_outside()
	_a_doorway_opens_both_sides()
	_a_level_above_is_flat_at_one_rise()
	_a_level_above_refuses_the_top_plane()
	_stairs_place_a_climb_pair_and_floor_the_landing()
	_every_up_climb_has_a_down_twin()
	_a_closed_room_fills_and_an_open_one_does_not()
	_one_gesture_undoes_on_both_planes()
	_live_check_names_a_wall_on_void()
	_a_roof_meets_the_walls_at_one_rise()
	_a_roof_refuses_a_floor_above()
	_shift_takes_the_roof_away()
	_a_roof_covers_only_a_rectangle_room()
	_a_wall_line_and_a_room_put_their_style_on_each_wall()
	_the_style_brush_paints_only_walls()
	_a_ray_at_a_wall_picks_the_tile_of_the_wall()
	_every_decor_kind_is_decor()
	_decor_places_replaces_and_removes()
	_decor_stands_on_blocked_but_not_on_void()
	_the_object_list_can_hide_decor()
	_the_build_gestures_drive_a_world()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: structure_tools")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


## Plane to a set of the 3 x 3 blank chunks around chunk (0, 0). Plane 1
## starts void and Blocked, as a new upper chunk does.
func _planes() -> Dictionary:
	var sets := {}

	for plane: int in range(_Const.TILE_GROUND_PLANE, _Const.CHUNK_PLANE_MAX + 1):
		var chunks := ChunkSet.new()

		chunks.plane = plane

		for dy: int in range(-1, 2):
			for dx: int in range(-1, 2):
				var ground := ChunkFile.blank(dx, dy)

				chunks.add(ground if plane == 0 else TerrainWorld.upper_chunk(ground, plane))

		sets[plane] = chunks

	return sets


func _wall_bits(chunks: ChunkSet, tile: Vector2i) -> int:
	return chunks.get_flags(tile) & _Const.TILE_FLAGS_WALLS


# ─── Wall line ──────────────────────────────────────────────────────────────

func _a_wall_line_keeps_to_one_axis() -> void:
	var chunks: ChunkSet = _planes()[0]
	var edit := TerrainEdit.new()

	# A drag 4 east and 1 north keeps to the line along x.
	StructureTools.wall_line(chunks, edit, Vector2i(2, 5), Vector2i(6, 6), false)

	for x: int in range(2, 6):
		_expect(_wall_bits(chunks, Vector2i(x, 5)) == _Const.TILE_FLAG_WALL_SOUTH,
			"tile (%d, 5) has the wall on its south edge" % x)

	_expect(_wall_bits(chunks, Vector2i(6, 5)) == 0, "the line stops at its end corner")
	_expect(_wall_bits(chunks, Vector2i(2, 6)) == 0, "and does not step north")
	_expect(edit.size() == 4, "four edges, four changes")


func _a_wall_line_takes_the_side_that_is_not_void() -> void:
	var chunks: ChunkSet = _planes()[1]
	var edit := TerrainEdit.new()
	var floor_tile := Vector2i(3, 2)

	# Only the tile south of the line has a floor.
	StructureTools.paint_floor(chunks, edit, floor_tile, "concrete")
	StructureTools.wall_line(chunks, edit, Vector2i(3, 3), Vector2i(4, 3), false)

	_expect(_wall_bits(chunks, floor_tile) == _Const.TILE_FLAG_WALL_NORTH,
		"the wall goes on the floor tile, not on the void")
	_expect(_wall_bits(chunks, Vector2i(3, 3)) == 0, "the void tile keeps no wall")


func _a_removal_clears_both_sides() -> void:
	var chunks: ChunkSet = _planes()[0]
	var edit := TerrainEdit.new()

	chunks.set_flags(Vector2i(4, 4), _Const.TILE_FLAG_WALL_WEST)
	chunks.set_flags(Vector2i(3, 4), _Const.TILE_FLAG_WALL_EAST)
	StructureTools.wall_line(chunks, edit, Vector2i(4, 4), Vector2i(4, 5), true)

	_expect(_wall_bits(chunks, Vector2i(4, 4)) == 0 and _wall_bits(chunks, Vector2i(3, 4)) == 0,
		"Shift clears the wall on both sides of the edge")


# ─── Room ───────────────────────────────────────────────────────────────────

func _options(floor_name: String, area_name: String) -> StructureTools.RoomOptions:
	var options := StructureTools.RoomOptions.new()

	options.floor_name = floor_name
	options.area_name = area_name

	return options


func _a_room_walls_its_inner_border() -> void:
	var chunks: ChunkSet = _planes()[0]
	var edit := TerrainEdit.new()
	var rect := Rect2i(10, 10, 3, 2)
	var area: String = _Const.TILE_AREAS[_Const.TILE_AREAS.size() - 1]

	StructureTools.room(chunks, edit, rect, _options("concrete", area), false)

	var want := {
		Vector2i(10, 10): _Const.TILE_FLAG_WALL_SOUTH | _Const.TILE_FLAG_WALL_WEST,
		Vector2i(11, 10): _Const.TILE_FLAG_WALL_SOUTH,
		Vector2i(12, 10): _Const.TILE_FLAG_WALL_SOUTH | _Const.TILE_FLAG_WALL_EAST,
		Vector2i(10, 11): _Const.TILE_FLAG_WALL_NORTH | _Const.TILE_FLAG_WALL_WEST,
		Vector2i(11, 11): _Const.TILE_FLAG_WALL_NORTH,
		Vector2i(12, 11): _Const.TILE_FLAG_WALL_NORTH | _Const.TILE_FLAG_WALL_EAST,
	}

	for tile: Vector2i in want:
		_expect(_wall_bits(chunks, tile) == want[tile], "room wall bits of %s" % tile)
		_expect(chunks.get_floor(tile) == "concrete", "room floor of %s" % tile)
		_expect(chunks.get_area(tile) == area, "room area of %s" % tile)

	_expect(_wall_bits(chunks, Vector2i(9, 10)) == 0, "no wall outside the room")

	var cleared := TerrainEdit.new()

	StructureTools.room(chunks, cleared, rect, _options("", ""), true)
	_expect(_wall_bits(chunks, Vector2i(10, 10)) == 0, "Shift removes the room walls")


func _a_room_levels_the_ground_to_its_highest_corner() -> void:
	var chunks: ChunkSet = _planes()[0]
	var edit := TerrainEdit.new()
	var rect := Rect2i(20, 20, 2, 2)

	chunks.set_corner(Vector2i(21, 21), 9)
	chunks.set_corner(Vector2i(20, 20), -3)
	StructureTools.room(chunks, edit, rect, _options("", ""), false)

	for corner: Vector2i in StructureTools.rect_corners(rect):
		_expect(chunks.get_corner(corner) == 9, "corner %s levels to 9" % corner)

	var options := _options("", "")

	options.base = StructureTools.Base.LOWEST
	chunks.set_corner(Vector2i(20, 20), -3)
	StructureTools.room(chunks, TerrainEdit.new(), rect, options, false)
	_expect(chunks.get_corner(Vector2i(22, 22)) == -3, "the lowest rule levels to -3")


func _a_room_blocks_the_ring_outside() -> void:
	var chunks: ChunkSet = _planes()[0]
	var options := _options("", "")
	var rect := Rect2i(30, 30, 2, 2)
	var neighbour := Vector2i(33, 30)

	# A wall bit marks a tile of another room. It stays open.
	chunks.set_flags(Vector2i(29, 30), _Const.TILE_FLAG_WALL_EAST)
	options.block_outside = true
	StructureTools.room(chunks, TerrainEdit.new(), rect, options, false)

	_expect(chunks.get_flags(Vector2i(32, 31)) & _Const.TILE_FLAG_BLOCKED != 0,
		"the ring tile east of the room is Blocked")
	_expect(chunks.get_flags(Vector2i(29, 29)) & _Const.TILE_FLAG_BLOCKED != 0,
		"the ring corner is Blocked")
	_expect(chunks.get_flags(Vector2i(29, 30)) & _Const.TILE_FLAG_BLOCKED == 0,
		"a ring tile with a wall stays open")
	_expect(chunks.get_flags(neighbour) == 0, "a tile past the ring stays open")
	_expect(chunks.get_flags(Vector2i(30, 30)) & _Const.TILE_FLAG_BLOCKED == 0,
		"the room stays open")


# ─── Doorway ────────────────────────────────────────────────────────────────

func _a_doorway_opens_both_sides() -> void:
	var chunks: ChunkSet = _planes()[0]
	var edit := TerrainEdit.new()
	var edge := StructureTools.edge_at(Vector2(5.0, 5.4))

	_expect(edge == [Vector2i(5, 5), _Const.TILE_FLAG_WALL_NORTH],
		"a point near the north edge picks it")

	chunks.set_flags(Vector2i(5, 5), _Const.TILE_FLAG_WALL_NORTH)
	chunks.set_flags(Vector2i(5, 6), _Const.TILE_FLAG_WALL_SOUTH)

	_expect(StructureTools.doorway(chunks, edit, edge[0], edge[1], false).is_empty(),
		"the doorway opens")
	_expect(_wall_bits(chunks, Vector2i(5, 5)) == 0 and _wall_bits(chunks, Vector2i(5, 6)) == 0,
		"both sides of the edge lose the wall")
	_expect(not StructureTools.doorway(chunks, TerrainEdit.new(), edge[0], edge[1],
		false).is_empty(), "a doorway with no wall there names the problem")

	StructureTools.doorway(chunks, edit, edge[0], edge[1], true)
	_expect(_wall_bits(chunks, Vector2i(5, 5)) == _Const.TILE_FLAG_WALL_NORTH,
		"Shift puts the wall back on the clicked side")


# ─── Level above and Stairs ─────────────────────────────────────────────────

func _a_level_above_is_flat_at_one_rise() -> void:
	var sets := _planes()
	var ground: ChunkSet = sets[0]
	var above: ChunkSet = sets[1]
	var tiles: Array[Vector2i] = [Vector2i(2, 2), Vector2i(3, 2)]
	var edit := TerrainEdit.new()

	ground.set_corner(Vector2i(3, 3), 5)
	ground.set_floor(Vector2i(2, 2), "gravel")

	_expect(StructureTools.level_above(sets, edit, 0, tiles, "", false).is_empty(),
		"the level is built")

	for corner: Vector2i in StructureTools.tile_corners(tiles):
		_expect(above.get_corner(corner) == 5 + TerrainWorld.NEW_PLANE_RISE,
			"corner %s of plane 1 is flat at the highest corner plus one rise" % corner)

	_expect(above.get_floor(Vector2i(2, 2)) == "gravel", "an empty floor takes the floor below")
	_expect(above.get_flags(Vector2i(3, 2)) & _Const.TILE_FLAG_BLOCKED == 0,
		"a floored tile is open")

	StructureTools.level_above(sets, TerrainEdit.new(), 0, tiles, "", true)
	_expect(above.get_floor(Vector2i(2, 2)) == _Const.TILE_VOID_FLOOR
		and above.get_flags(Vector2i(2, 2)) == _Const.TILE_FLAG_BLOCKED,
		"Shift sets the level back to void and Blocked")


func _a_level_above_refuses_the_top_plane() -> void:
	var tiles: Array[Vector2i] = [Vector2i(1, 1)]
	var top: int = _Const.CHUNK_PLANE_MAX

	_expect(not StructureTools.level_above(_planes(), TerrainEdit.new(), top, tiles,
		"", false).is_empty(), "no level goes above the top plane")


func _stairs_place_a_climb_pair_and_floor_the_landing() -> void:
	var sets := _planes()
	var tile := Vector2i(7, 7)
	var pairs := StructureTools.climb_pairs()
	var up_kind: String = pairs.keys()[0]

	_expect(StructureTools.stairs(sets, TerrainEdit.new(), 0, tile, up_kind, "concrete",
		false).is_empty(), "the stairs are placed")
	_expect(sets[0].objects_at(tile)[0]["kind"] == up_kind, "the way up stands on plane 0")
	_expect(sets[1].objects_at(tile)[0]["kind"] == pairs[up_kind],
		"its twin stands on plane 1")
	_expect(sets[1].get_floor(tile) == "concrete"
		and sets[1].get_flags(tile) & _Const.TILE_FLAG_BLOCKED == 0,
		"the void landing gets an open floor")

	var again := TerrainEdit.new()

	_expect(not StructureTools.stairs(sets, again, 0, tile, up_kind, "", false).is_empty()
		and again.is_empty(), "a second click refuses, and stacks no second pair")
	_expect(sets[0].objects_at(tile).size() == 1 and sets[1].objects_at(tile).size() == 1,
		"one pair stands")

	StructureTools.stairs(sets, TerrainEdit.new(), 0, tile, up_kind, "", true)
	_expect(sets[0].objects_at(tile).is_empty() and sets[1].objects_at(tile).is_empty(),
		"Shift removes the pair")


## The Stairs tool lists the up kinds. Each must have its down twin, so a new
## climb kind of the server reaches the tool with no edit.
func _every_up_climb_has_a_down_twin() -> void:
	var pairs := StructureTools.climb_pairs()

	_expect(not pairs.is_empty(), "the server names at least one climb pair")

	for kind: String in _Const.OBJECT_KIND_CLIMBS:
		if _Const.OBJECT_KIND_CLIMBS[kind] == [_Const.CLIMB_UP]:
			_expect(pairs.has(kind), "%s has a twin that leads down" % kind)


# ─── Fill and undo ──────────────────────────────────────────────────────────

func _a_closed_room_fills_and_an_open_one_does_not() -> void:
	var chunks: ChunkSet = _planes()[0]
	var rect := Rect2i(40, 40, 4, 3)

	StructureTools.room(chunks, TerrainEdit.new(), rect, _options("", ""), false)

	var closed := RoomFill.fill(chunks, Vector2i(41, 41))

	_expect(closed["closed"] and closed["tiles"].size() == 12,
		"the fill of a 4 x 3 room finds its 12 tiles")

	StructureTools.doorway(chunks, TerrainEdit.new(), Vector2i(40, 41),
		_Const.TILE_FLAG_WALL_WEST, false)

	var open := RoomFill.fill(chunks, Vector2i(41, 41), 50)

	_expect(not open["closed"] and open["tiles"].size() == 50,
		"a doorway lets the fill out, and it stops at the limit")


func _one_gesture_undoes_on_both_planes() -> void:
	var sets := _planes()
	var edit := TerrainEdit.new()
	var rect := Rect2i(50, 50, 2, 2)
	var tiles := StructureTools.rect_tiles(rect)

	StructureTools.room(sets[0], edit, rect, _options("concrete", ""), false)
	StructureTools.level_above(sets, edit, 0, tiles, "", false)

	_expect(edit.planes().size() == 2, "one edit holds both planes")

	edit.replay_planes(sets, false)

	_expect(sets[0].get_floor(Vector2i(50, 50)) == _Const.TILE_DEFAULT_FLOOR
		and _wall_bits(sets[0], Vector2i(50, 50)) == 0, "undo clears the room")
	_expect(sets[1].get_floor(Vector2i(50, 50)) == _Const.TILE_VOID_FLOOR,
		"and the level above")


func _live_check_names_a_wall_on_void() -> void:
	var sets := _planes()
	var edit := TerrainEdit.new()

	# Both sides of the line are void on plane 1.
	StructureTools.wall_line(sets[1], edit, Vector2i(3, 3), Vector2i(4, 3), false)

	var found := TerrainChecks.check_tiles(sets, edit.tiles())

	_expect(found.size() == 1 and found[0]["rule"] == _Const.TILE_CHECK_WALL_ON_VOID,
		"the live check names the wall on a void tile")


# ─── Wall styles ────────────────────────────────────────────────────────────

func _a_wall_line_and_a_room_put_their_style_on_each_wall() -> void:
	var chunks: ChunkSet = _planes()[0]
	var edit := TerrainEdit.new()
	var options := _options("", "")

	StructureTools.wall_line(chunks, edit, Vector2i(2, 5), Vector2i(4, 5), false, "brick")
	_expect(chunks.get_wall_style(Vector2i(2, 5)) == "brick"
		and chunks.get_wall_style(Vector2i(3, 5)) == "brick",
		"a wall line puts its style on each tile of the line")

	StructureTools.wall_line(chunks, edit, Vector2i(2, 5), Vector2i(4, 5), true, "concrete")
	_expect(chunks.get_wall_style(Vector2i(2, 5)) == "brick",
		"a removal keeps the style")

	options.wall_style = "sheet_metal"
	StructureTools.room(chunks, edit, Rect2i(10, 10, 3, 3), options, false)
	_expect(chunks.get_wall_style(Vector2i(10, 10)) == "sheet_metal",
		"a room puts its style on a border tile")
	_expect(chunks.get_wall_style(Vector2i(11, 11)) == _Const.TILE_DEFAULT_WALL_STYLE,
		"and not on a tile inside with no wall")


func _the_style_brush_paints_only_walls() -> void:
	var chunks: ChunkSet = _planes()[0]
	var edit := TerrainEdit.new()
	var walled := Vector2i(5, 5)
	var open := Vector2i(6, 5)
	var tiles: Array[Vector2i] = [walled, open]

	chunks.set_flags(walled, _Const.TILE_FLAG_WALL_EAST)

	_expect(StructureTools.paint_wall_style(chunks, edit, tiles, "brick") == 1,
		"the brush counts one wall tile")
	_expect(chunks.get_wall_style(walled) == "brick", "the wall tile takes the style")
	_expect(chunks.get_wall_style(open) == _Const.TILE_DEFAULT_WALL_STYLE,
		"a tile with no wall keeps its style")
	_expect(StructureTools.paint_wall_style(chunks, edit, tiles, "brick") == 0,
		"a second dab changes nothing")

	edit.replay(chunks, false)
	_expect(chunks.get_wall_style(walled) == _Const.TILE_DEFAULT_WALL_STYLE,
		"undo gives the wall its style back")


## Alt and a click sample the wall under the mouse. The ground pick goes
## through a wall and meets the ground past it. Thus, the sample needs the
## wall march (Nick, 10/09/2026: Alt on a brick wall gave plain).
func _a_ray_at_a_wall_picks_the_tile_of_the_wall() -> void:
	var chunks: ChunkSet = _planes()[0]
	var wall := Vector2i(5, 5)
	var origin := Vector3(5.0, 0.5, 0.0)
	var low_ray := Vector3(0.0, -0.05, -1.0)

	chunks.set_flags(wall, _Const.TILE_FLAG_WALL_SOUTH)
	chunks.set_wall_style(wall, "brick")

	var ground: Vector3 = TerrainPicking.ray_hit(chunks, origin, low_ray)

	_expect(ChunkSet.tile_at(TerrainPicking.tile_point(ground)) != wall,
		"the ground pick goes through the wall")
	_expect(TerrainPicking.wall_hit(chunks, origin, low_ray) == wall,
		"the wall pick stops at the slab of the wall")
	_expect(TerrainPicking.wall_hit(chunks, Vector3(5.0, 3.0, 0.0),
		Vector3(0.0, -0.2, -1.0)) == null, "a ray over the wall top meets no wall")
	_expect(TerrainPicking.wall_hit(chunks, Vector3(5.0, 0.5, -1.0),
		Vector3(0.0, -0.05, -1.0), null, true) == null,
		"with walls down, a ray over the low slab meets no wall")


# ─── The gestures, with no editor ───────────────────────────────────────────

## [BuildInput] turns a press, a drag, and a release into one undo entry. A
## world in a scratch directory under `user://` stands in for the editor.
## A gable over a 4 x 3 room with an overhang of one tile, ridge east-west.
func _gable(overhang: int) -> StructureTools.RoofOptions:
	var options := StructureTools.RoofOptions.new()

	options.shape = RoofShapes.Shape.GABLE
	options.pitch = 4
	options.overhang = overhang
	options.turn = 0
	options.floor_name = _Const.TILE_ROOF_FLOOR_TYPES[0]

	return options


func _a_roof_meets_the_walls_at_one_rise() -> void:
	var sets := _planes()
	var ground: ChunkSet = sets[0]
	var above: ChunkSet = sets[1]
	var rect := Rect2i(2, 2, 4, 3)
	var options := _gable(1)
	var base := 6
	var eave := base + TerrainWorld.NEW_PLANE_RISE

	ground.set_corner(Vector2i(5, 4), base)

	_expect(StructureTools.roof(sets, TerrainEdit.new(), 0, rect, options, false).is_empty(),
		"the roof is built")

	for tile: Vector2i in StructureTools.rect_tiles(rect.grow(1)):
		_expect(above.get_floor(tile) == options.floor_name
			and above.get_flags(tile) & _Const.TILE_FLAG_BLOCKED,
			"roof tile %s has the roof floor and Blocked" % tile)

	# The south wall line of the room is corner row 2, one tile in from the
	# outer eave at row 1.
	_expect(above.get_corner(Vector2i(2, 2)) == eave,
		"the roof meets the wall line at one rise above the highest corner")
	_expect(above.get_corner(Vector2i(2, 1)) == eave - options.pitch * options.overhang,
		"the overhang hangs one pitch lower")
	_expect(above.get_corner(Vector2i(4, 3)) > eave, "the ridge is above the eave")
	_expect(ground.get_floor(Vector2i(3, 3)) == _Const.TILE_DEFAULT_FLOOR,
		"a roof changes nothing on the plane of the room")


func _a_roof_refuses_a_floor_above() -> void:
	var sets := _planes()
	var above: ChunkSet = sets[1]
	var edit := TerrainEdit.new()
	var level: Array[Vector2i] = [Vector2i(3, 3)]

	StructureTools.level_above(sets, TerrainEdit.new(), 0, level, "", false)

	var problem := StructureTools.roof(sets, edit, 0, Rect2i(2, 2, 4, 3), _gable(1), false)

	_expect("plane 1" in problem.to_lower(), "the refusal names the plane: " + problem)
	_expect(edit.is_empty(), "a refusal changes nothing")
	_expect(not above.get_floor(Vector2i(2, 2)) in _Const.TILE_ROOF_FLOOR_TYPES,
		"no roof tile is written")

	var plan := StructureTools.roof_plan(sets, 0, Rect2i(2, 2, 4, 3), _gable(1))

	_expect(not plan["problem"].is_empty() and not plan["heights"].is_empty(),
		"a refused plan keeps its heights, so the outline draws it in red")
	_expect(not StructureTools.roof(sets, edit, _Const.CHUNK_PLANE_MAX,
		Rect2i(2, 2, 2, 2), _gable(0), false).is_empty(), "no roof goes above the top plane")


func _shift_takes_the_roof_away() -> void:
	var sets := _planes()
	var above: ChunkSet = sets[1]
	var rect := Rect2i(2, 2, 4, 3)

	StructureTools.roof(sets, TerrainEdit.new(), 0, rect, _gable(1), false)
	_expect(StructureTools.roof(sets, TerrainEdit.new(), 0, rect, _gable(1), true).is_empty(),
		"Shift removes the roof")

	for tile: Vector2i in StructureTools.rect_tiles(rect.grow(1)):
		_expect(above.get_floor(tile) == _Const.TILE_VOID_FLOOR
			and above.get_flags(tile) == _Const.TILE_FLAG_BLOCKED,
			"tile %s is void and Blocked again" % tile)

	_expect(not StructureTools.roof(sets, TerrainEdit.new(), 0, rect, _gable(1),
		true).is_empty(), "a second removal finds no roof and says so")


func _a_roof_covers_only_a_rectangle_room() -> void:
	var square: Array[Vector2i] = [Vector2i(0, 0), Vector2i(1, 0), Vector2i(0, 1),
		Vector2i(1, 1)]
	var bent: Array[Vector2i] = [Vector2i(0, 0), Vector2i(1, 0), Vector2i(0, 1)]
	var found := StructureTools.fill_rect({"tiles": square, "closed": true})

	_expect(found["problem"].is_empty() and found["rect"] == Rect2i(0, 0, 2, 2),
		"a full rectangle is a roof rectangle")
	_expect(not StructureTools.fill_rect({"tiles": bent, "closed": true})["problem"].is_empty(),
		"an L-shaped room asks for a drag")
	_expect(not StructureTools.fill_rect({"tiles": square, "closed": false})["problem"].is_empty(),
		"an open fill is no room")


# ─── Decor ──────────────────────────────────────────────────────────────────

func _every_decor_kind_is_decor() -> void:
	var kinds := StructureTools.decor_kinds()

	_expect(not kinds.is_empty(), "the server names some decor")

	for kind: String in kinds:
		_expect(_Const.OBJECT_KINDS[kind] == _Const.OBJECT_CATEGORY_DECOR,
			"%s is of the decor category" % kind)


func _decor_places_replaces_and_removes() -> void:
	var chunks: ChunkSet = _planes()[0]
	var kinds := StructureTools.decor_kinds()
	var tile := Vector2i(2, 2)
	var edit := TerrainEdit.new()

	StructureTools.decor(chunks, edit, tile, kinds[0], 0, false)
	StructureTools.decor(chunks, edit, tile, kinds[-1], 3, false)

	var found := chunks.objects_at(tile)

	_expect(found.size() == 1 and found[0]["kind"] == kinds[-1]
		and found[0]["rotation"] == 3, "a tile holds one decor: %s" % [found])

	var again := TerrainEdit.new()

	StructureTools.decor(chunks, again, tile, kinds[-1], 3, false)
	_expect(again.is_empty(), "the same decor again changes nothing")

	edit.replay(chunks, false)
	_expect(chunks.objects_at(tile).is_empty(), "the undo takes the place and the swap back")
	edit.replay(chunks, true)

	var remove := TerrainEdit.new()

	StructureTools.decor(chunks, remove, tile, "", 0, true)
	_expect(chunks.objects_at(tile).is_empty(), "Shift removes the decor")
	_expect(not StructureTools.decor(chunks, remove, tile, "", 0, true).is_empty(),
		"a removal from a bare tile names its problem")


func _decor_stands_on_blocked_but_not_on_void() -> void:
	var sets := _planes()
	var ground: ChunkSet = sets[0]
	var upper: ChunkSet = sets[1]
	var kind: String = StructureTools.decor_kinds()[0]
	var tile := Vector2i(6, 6)
	var edit := TerrainEdit.new()

	ground.set_flags(tile, _Const.TILE_FLAG_BLOCKED)
	_expect(StructureTools.decor(ground, edit, tile, kind, 0, false).is_empty(),
		"decor stands on a Blocked tile")
	_expect(TerrainChecks.check_tiles(sets, edit.tiles()).is_empty(),
		"and the live check finds nothing")
	_expect(not StructureTools.decor(upper, edit, tile, kind, 0, false).is_empty()
		and upper.objects_at(tile).is_empty(), "a void tile refuses decor")


func _the_object_list_can_hide_decor() -> void:
	var decor: String = StructureTools.decor_kinds()[0]
	var rows: Array[Dictionary] = [{"kind": decor}, {"kind": _Const.TILE_RESPAWN_KIND}]

	_expect(TerrainDock.listed_objects(rows, true).size() == 2, "the list shows decor")
	_expect(TerrainDock.listed_objects(rows, false).size() == 1,
		"and hides it when asked")


func _the_build_gestures_drive_a_world() -> void:
	var scratch := ProjectSettings.globalize_path("user://structure_tools_%d"
		% Time.get_ticks_usec())
	var world := TerrainWorld.new()
	var panel := BuildPanel.new()
	var input := BuildInput.new()
	var labels: Array[String] = []

	# The settings file is in git. A test must not change it.
	panel.persist = false
	# The panel loads the settings of the author. A roof floor there would
	# block the room, so the test sets the floor itself.
	panel.sample(BuildPanel.KEEP, "", "")
	world.chunk_directory = scratch
	add_child(world)
	input.world = world
	input.panel = panel
	input.commit = func(_edit: TerrainEdit, label: String) -> void: labels.append(label)

	_drag_a_room(input, panel, world)
	_click_a_level_and_stairs(input, panel, world)

	_expect(labels == ["Room 4 x 3", "Level above, 12 tiles", "Stairs"],
		"each gesture is one entry: %s" % [labels])

	input.on_key(_key(KEY_PAGEUP))
	_expect(world.plane == 1, "Page Up edits the plane above")

	_click_a_roof(input, panel, world)
	_expect(labels.size() == 4 and labels[3].ends_with("roof 4 x 3"),
		"the roof is one entry: %s" % [labels])

	input.on_key(_key(KEY_PAGEDOWN))
	_paint_a_wall_style(input, panel, world)
	_expect(labels.size() == 5 and labels[4].begins_with("Wall style"),
		"the stroke is one entry: %s" % [labels])
	_click_decor(input, panel, world)
	_expect(labels.size() == 6 and labels[5] == "Decor " + panel.decor_kind(),
		"the decor is one entry: %s" % [labels])
	_a_save_writes_the_styles_in_format_two(world)

	world.queue_free()
	panel.free()
	_remove_scratch(scratch)


## Drag the Wall style brush along the south wall of the room of
## [method _drag_a_room]. Esc then undoes a second stroke.
func _paint_a_wall_style(input: BuildInput, panel: BuildPanel, world: TerrainWorld) -> void:
	var south_wall := Vector2i(4, 3)

	panel.select_tool(BuildPanel.Tool.WALL_STYLE)
	panel.sample(world.chunks.get_floor(south_wall), world.chunks.get_area(south_wall),
		"brick")
	input.on_press(Vector2(3.0, 3.0), false, false)
	input.on_motion(Vector2(4.0, 3.0), false)
	_expect("brick" in input.hint(), "the hint names the wall style")
	input.on_release()

	_expect(world.chunks.get_wall_style(south_wall) == "brick",
		"the brush paints a wall under its ring")
	_expect(world.chunks.get_wall_style(Vector2i(3, 3)) == "brick",
		"and the corner of the room, inside the ring")
	_expect(world.chunks.get_wall_style(Vector2i(4, 4)) == _Const.TILE_DEFAULT_WALL_STYLE,
		"but no tile inside the room, which has no wall")

	input.on_press(Vector2(3.0, 3.0), true, false)
	_expect(world.chunks.get_wall_style(south_wall) == _Const.TILE_DEFAULT_WALL_STYLE,
		"Shift paints the default style")
	input.on_key(_key(KEY_ESCAPE))
	_expect(world.chunks.get_wall_style(south_wall) == "brick",
		"Esc undoes the stroke before the release")

	panel.sample(world.chunks.get_floor(south_wall), world.chunks.get_area(south_wall),
		_Const.TILE_DEFAULT_WALL_STYLE)
	input.on_press(Vector2(4.0, 9.0), false, true, south_wall)
	_expect(panel.wall_style() == "brick",
		"Alt samples the wall under the mouse, not the ground past it")


## R turns the next decor, and a click inside the room places it. Alt and a
## click on it then take its kind and its turn into the options. The panel
## starts at the turn of the settings file of the author, so each expected
## turn counts from that start.
func _click_decor(input: BuildInput, panel: BuildPanel, world: TerrainWorld) -> void:
	var tile := Vector2i(5, 4)
	var turn := (panel.decor_turn() + 1) % BuildPanel.FACING_NAMES.size()

	panel.select_tool(BuildPanel.Tool.DECOR)
	_expect(input.on_key(_key(KEY_R)), "R is a key of the Decor tool")
	_expect("front to the %s" % BuildPanel.FACING_NAMES[turn] in input.hint(),
		"the hint names the turn")
	input.on_press(Vector2(5.0, 4.0), false, false)

	var placed := StructureTools.decor_at(world.chunks, tile)

	_expect(placed.get("kind", "") == panel.decor_kind() and placed["rotation"] == turn,
		"a click places the decor at its turn: %s" % [placed])

	input.on_key(_shift_key(KEY_R))
	input.on_press(Vector2(5.0, 4.0), false, true)
	_expect(panel.decor_turn() == turn, "Alt takes the turn of the decor on the tile")


func _a_save_writes_the_styles_in_format_two(world: TerrainWorld) -> void:
	var saved := world.save_block()
	var path := world.chunk_path(Vector2i.ZERO, 0)
	var chunk := ChunkFile.read_file(path)

	_expect(saved.has(path.get_file()), "the save writes the chunk of the room")
	_expect(chunk.error.is_empty() and chunk.wall_style_name(4, 3) == "brick",
		"the file holds the wall style: %s" % chunk.error)
	_expect(JSON.parse_string(FileAccess.get_file_as_string(path))["format"]
		== _Const.CHUNK_FORMAT_VERSION, "a chunk with a wall style is format 2")


func _drag_a_room(input: BuildInput, panel: BuildPanel, world: TerrainWorld) -> void:
	panel.select_tool(BuildPanel.Tool.ROOM)
	input.on_press(Vector2(3.0, 3.0), false, false)
	input.on_motion(Vector2(6.2, 4.9), false)

	_expect(input.readout().begins_with("4 x 3 tiles"), "the readout gives the size")
	_expect("Room" in input.hint(), "the hint names the tool")

	input.on_release()

	_expect(_wall_bits(world.chunks, Vector2i(3, 3))
		== _Const.TILE_FLAG_WALL_SOUTH | _Const.TILE_FLAG_WALL_WEST,
		"the drag builds the room")

	input.on_press(Vector2(10.0, 10.0), false, false)
	input.on_key(_key(KEY_ESCAPE))
	_expect(not input.dragging(), "Esc cancels a drag")


func _click_a_level_and_stairs(input: BuildInput, panel: BuildPanel,
		world: TerrainWorld) -> void:
	panel.select_tool(BuildPanel.Tool.LEVEL_ABOVE)
	input.on_press(Vector2(4.0, 4.0), false, false)
	input.on_release()

	_expect(world.chunks_on(1).get_floor(Vector2i(5, 4)) != _Const.TILE_VOID_FLOOR,
		"a click inside the room floors the level above")

	panel.select_tool(BuildPanel.Tool.STAIRS)
	input.on_press(Vector2(4.0, 4.0), false, false)

	_expect(world.chunks_on(1).objects_at(Vector2i(4, 4)).size() == 1,
		"a click places the stairs and their twin above")


## On plane 1, a click inside the level roofs it on plane 2. R turns the
## ridge, and Shift+R turns it back.
func _click_a_roof(input: BuildInput, panel: BuildPanel, world: TerrainWorld) -> void:
	panel.select_tool(BuildPanel.Tool.ROOF)

	var before := panel.roof_summary()

	_expect(input.on_key(_key(KEY_R)), "R is the key of the Roof tool")
	_expect(panel.roof_summary() != before or panel.roof_options().shape
		in [RoofShapes.Shape.FLAT, RoofShapes.Shape.HIP, RoofShapes.Shape.PYRAMID],
		"R turns a roof that turns")
	input.on_key(_shift_key(KEY_R))
	_expect(panel.roof_summary() == before, "Shift+R turns it back")

	input.on_press(Vector2(4.0, 4.0), false, false)

	_expect("Roof:" in input.hint(), "the hint names the roof options")
	_expect(input.readout().begins_with("4 x 3 tiles"), "the click finds the 4 x 3 level")

	input.on_release()

	_expect(world.chunks_on(2).get_floor(Vector2i(4, 4)) in _Const.TILE_ROOF_FLOOR_TYPES,
		"a click inside the level roofs it on plane 2")


static func _shift_key(code: Key) -> InputEventKey:
	var event := _key(code)

	event.shift_pressed = true

	return event


static func _key(code: Key) -> InputEventKey:
	var event := InputEventKey.new()

	event.keycode = code
	event.pressed = true

	return event


## Delete a scratch tree of this test: files first, then directories. Each
## run would else leave one directory under `user://`.
func _remove_scratch(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return

	for child: String in DirAccess.get_directories_at(path):
		_remove_scratch(path.path_join(child))

	for file_name: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(file_name))

	DirAccess.remove_absolute(path)
