extends Node
## Tests for the templates of the Build tab (DESIGN-0013 Phase S5):
## [StructureTemplate], [StructurePlace], [TileSelection], the protect
## filter of [TerrainBrushes], and the Select and Place gestures of
## [TemplateInput].
##
##     godot --headless --path godot res://tests/test_structure_template.tscn
##
## Needs nothing running and no editor. The cases:
##
## 1. The fixture of the Python test reads, and writes back byte for byte.
## 2. Four turns, and two mirrors, give each template back: the fixture and
##    each template of the world.
## 3. A turn and a mirror move the tiles, the wall bits, and the objects as
##    the table of section 6.6 says.
## 4. The reader refuses a bad template, with a reason.
## 5. A capture and a copy at another place give the same facts.
## 6. A copy levels the ground to the base, and blends a ring around it.
## 7. The plan refuses, and warns, for each reason of the class comment.
## 8. Delete keeps the ground and empties a plane above. Undo gives it back.
## 9. A move may overlap the tiles that it clears.
## 10. "Protect structures" keeps the corners of a structure.
## 11. A click inside a room selects the room, its level, and its roof.
## 12. The Select and the Place gestures drive a world, one undo entry each.

const _Const := preload("res://autoload/blackout_constants.gd")

## The fixture that the Python name check also reads.
const FIXTURE := "../blackout/world/tests/fixtures/structures/fixture_stall.json"

var _failures := 0


func _ready() -> void:
	_the_fixture_reads_and_writes_back()
	_four_turns_and_two_mirrors_give_it_back()
	_a_turn_and_a_mirror_move_each_fact()
	_the_reader_refuses_a_bad_template()
	_a_copy_gives_the_facts_of_its_capture()
	_a_capture_covers_ground_and_floors_only()
	_a_copy_levels_and_blends_the_ground()
	_the_plan_refuses_with_a_reason()
	_the_plan_warns_with_a_reason()
	_delete_keeps_the_ground_and_empties_the_planes_above()
	_a_move_may_overlap_the_tiles_it_clears()
	_protect_keeps_the_corners_of_a_structure()
	_a_click_in_a_room_selects_its_level_and_roof()
	_the_select_and_place_gestures_drive_a_world()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: structure_template")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


## Plane to a set of the 3 x 3 blank chunks around chunk (0, 0). A plane
## above starts void and Blocked, as a new upper chunk does.
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


func _fixture_text() -> String:
	return FileAccess.get_file_as_string("res://" + FIXTURE).replace("\r\n", "\n")


func _fixture() -> StructureTemplate:
	return StructureTemplate.parse_text(_fixture_text())


## A 4 x 3 room at (10, 10) in brick, a level over it, a gable roof over the
## level, a crate inside, and stairs. The room is the structure of most
## cases.
func _house(sets: Dictionary) -> Rect2i:
	var rect := Rect2i(10, 10, 4, 3)
	var options := StructureTools.RoomOptions.new()
	var roof := StructureTools.RoofOptions.new()
	var edit := TerrainEdit.new()

	options.floor_name = "concrete"
	options.wall_style = "brick"
	StructureTools.room(sets[0], edit, rect, options, false)
	StructureTools.level_above(sets, edit, 0, StructureTools.rect_tiles(rect), "", false)
	StructureTools.roof(sets, edit, 1, rect, roof, false)
	StructureTools.decor(sets[0], edit, Vector2i(12, 11), StructureTools.decor_kinds()[0], 1,
		false)
	StructureTools.stairs(sets, edit, 0, Vector2i(10, 10), StructureTools.climb_pairs().keys()[0],
		"", false)

	return rect


# ─── The file ───────────────────────────────────────────────────────────────

func _the_fixture_reads_and_writes_back() -> void:
	var template := _fixture()

	_expect(template.error.is_empty(), "the fixture reads: " + template.error)
	_expect(template.to_text() == _fixture_text(), "the fixture writes back byte for byte")
	_expect(template.layers.size() == 2 and template.objects.size() == 3,
		"the fixture has two planes and three objects")


func _four_turns_and_two_mirrors_give_it_back() -> void:
	var templates: Array[StructureTemplate] = [_fixture()]
	var directory := StructureTemplate.world_directory()

	for template_key: String in StructureTemplate.list_keys(directory):
		templates.append(StructureTemplate.read_file(StructureTemplate.path_for(directory,
			template_key)))

	for template: StructureTemplate in templates:
		var text := template.to_text()
		var turned := template.turned().turned().turned().turned()

		_expect(template.error.is_empty(), "%s reads: %s" % [template.key, template.error])
		_expect(turned.to_text() == text, "four turns give %s back" % template.key)
		_expect(template.mirrored().mirrored().to_text() == text,
			"two mirrors give %s back" % template.key)
		_expect(template.turned().to_text() != text, "one turn changes %s" % template.key)


func _a_turn_and_a_mirror_move_each_fact() -> void:
	var template := _fixture()
	var turned := template.turned()
	var mirrored := template.mirrored()
	var crate: Dictionary = template.objects[0]
	var north := _Const.TILE_FLAG_WALL_NORTH
	var south := _Const.TILE_FLAG_WALL_SOUTH
	var west := _Const.TILE_FLAG_WALL_WEST

	_expect(turned.size == Vector2i(2, 3), "a turn swaps W and H: %s" % turned.size)
	# Tile (0, 0) has S and W. A turn moves it to (0, 2), with W and N.
	_expect(turned.layers[0].flags[turned.tile_index(Vector2i(0, 2))] == west | north,
		"a turn moves each wall bit one edge clockwise")
	_expect(turned.objects[0]["x"] == crate["y"]
		and turned.objects[0]["y"] == template.size.x - 1 - crate["x"]
		and turned.objects[0]["rotation"] == crate["rotation"] + 1,
		"a turn moves an object and adds one to its rotation: %s" % [turned.objects[0]])
	_expect(turned.layers[0].heights[turned.corner_index(Vector2i(0, 0))]
		== template.layers[0].heights[template.corner_index(Vector2i(3, 0))],
		"corner (3, 0) goes to (0, 0)")
	_expect(mirrored.layers[0].flags[0] == south | west,
		"a mirror moves tile (2, 0) with S and E to (0, 0), with S and W")
	_expect(mirrored.objects[0]["rotation"] == 3, "a mirror turns rotation 1 to 3")


func _the_reader_refuses_a_bad_template() -> void:
	var cases := {
		"an object on a tile with no cover":
			['"x":1,"y":0,"plane":0', '"x":0,"y":0,"plane":1'],
		"a plane with no cover": ['[0,1,1],\n        [0,1,1]', '[0,0,0],\n        [0,0,0]'],
		"an index past its name list": ['[0,1,0]', '[0,3,0]'],
		"a format that is not 1": ['"format": 1', '"format": 2'],
		"a key that is not a name": ['"fixture_stall"', '"Fixture Stall"'],
		"an object kind that is not a name": ['"crate"', '"Crate"'],
	}

	for what: String in cases:
		var swap: Array = cases[what]
		var text := _fixture_text()

		_expect(text.contains(swap[0]), "the bad case %s finds its text" % what)

		var template := StructureTemplate.parse_text(text.replace(swap[0], swap[1]))

		_expect(not template.error.is_empty(), "the reader refuses " + what)


# ─── Capture and copy ───────────────────────────────────────────────────────

## The keys of the room at `rect` of [method _house], selected with a click
## on every plane.
func _house_selection(sets: Dictionary, rect: Rect2i) -> TileSelection:
	var selection := TileSelection.new()

	selection.change_room(sets, 0, rect.position + Vector2i.ONE, true, false)

	return selection


func _a_copy_gives_the_facts_of_its_capture() -> void:
	var sets := _planes()
	var rect := _house(sets)
	var selection := _house_selection(sets, rect)
	var template := StructureTemplate.capture(sets, selection.keys, 0, "house")
	var origin := Vector2i(40, 30)
	var result := StructurePlace.place(sets, TerrainEdit.new(), template, origin, 0,
		StructurePlace.Options.new())

	_expect(template.error.is_empty() and result["problem"].is_empty(),
		"the house copies: %s %s" % [template.error, result["problem"]])
	_expect(result["keys"].size() == selection.size(),
		"the copy writes each tile that the capture took")

	var offset := origin - template.origin

	for at: Vector3i in selection.keys:
		_expect_same_tile(sets[at.z], Vector2i(at.x, at.y), offset)


func _expect_same_tile(chunks: ChunkSet, tile: Vector2i, offset: Vector2i) -> void:
	var there := tile + offset
	var what := "tile %s of plane %d and its copy" % [tile, chunks.plane]

	_expect(chunks.get_floor(there) == chunks.get_floor(tile)
		and chunks.get_flags(there) == chunks.get_flags(tile)
		and chunks.get_wall_style(there) == chunks.get_wall_style(tile)
		and chunks.objects_at(there) == chunks.objects_at(tile), what + " agree")

	for corner: Vector2i in StructureTools.tile_corners([tile]):
		_expect(chunks.get_corner(corner + offset) == chunks.get_corner(corner),
			what + " agree at corner %s" % corner)


func _a_capture_covers_ground_and_floors_only() -> void:
	var sets := _planes()
	var selection := TileSelection.new()
	var planes: Array[int] = [0, 1]

	sets[0].set_corner(Vector2i(3, 3), 5)
	sets[1].set_floor(Vector2i(2, 2), "concrete")
	selection.change_rect(Rect2i(2, 2, 2, 2), planes, false)

	var template := StructureTemplate.capture(sets, selection.keys, 0, "pad")

	_expect(template.layers[0].cover_count() == 4, "each ground tile is covered")
	_expect(template.layers[1].cover_count() == 1, "only the floor of plane 1 is covered")
	_expect(template.layers[0].heights[template.corner_index(Vector2i(1, 1))] == 5,
		"a height is above the lowest covered corner")

	var air := TileSelection.new()

	air.change_rect(Rect2i(5, 5, 1, 1), [1] as Array[int], false)
	_expect(not StructureTemplate.capture(sets, air.keys, 1, "air").error.is_empty(),
		"a selection of void alone gives no template")


func _a_copy_levels_and_blends_the_ground() -> void:
	var sets := _planes()
	var ground: ChunkSet = sets[0]
	var template := _fixture()
	var options := StructurePlace.Options.new()
	var origin := Vector2i(20, 20)
	var far := Vector2i(19, 19)

	ground.set_corner(origin + Vector2i(1, 1), 8)
	ground.set_corner(far, 20)
	options.blend = 1
	StructurePlace.place(sets, TerrainEdit.new(), template, origin, 0, options)

	_expect(ground.get_corner(origin) == 8, "the base is the highest covered corner")
	_expect(ground.get_corner(origin + Vector2i(3, 0)) == 9,
		"a covered corner is the base plus its relative height")
	_expect(ground.get_corner(far) == 8 + roundi((20 - 8) / 2.0),
		"a ring corner moves half of the way to the base")
	_expect(ground.get_corner(far - Vector2i.ONE) == 0, "a corner past the ring stays")
	_expect(sets[1].get_corner(origin + Vector2i(1, 0)) == 8 + 32,
		"a plane above is above the same base")


func _the_plan_refuses_with_a_reason() -> void:
	var sets := _planes()
	var template := _fixture()
	var options := StructurePlace.Options.new()
	var origin := Vector2i(20, 20)

	sets[0].add_object(origin, StructureTools.decor_kinds()[0], 0)
	_expect("Alt" in StructurePlace.plan(sets, template, origin, 0, options)["problem"],
		"an object on a covered tile refuses, and names Alt")
	options.replace = true
	_expect(StructurePlace.plan(sets, template, origin, 0, options)["problem"].is_empty(),
		"Alt replaces it")

	sets[1].set_floor(origin + Vector2i(1, 0), "concrete")
	_expect("plane 1" in StructurePlace.plan(sets, template, origin, 0,
		options)["problem"].to_lower(), "a floor on a covered tile above refuses")
	_expect("top plane" in StructurePlace.plan(sets, template, Vector2i(5, 5),
		_Const.CHUNK_PLANE_MAX, options)["problem"], "a copy above the top plane refuses")
	_expect("locked edge" in StructurePlace.plan(sets, template, Vector2i(126, 5), 0,
		options)["problem"], "a copy on the edge of the block refuses")

	var edit := TerrainEdit.new()

	StructurePlace.place(sets, edit, template, origin, 0, StructurePlace.Options.new())
	_expect(edit.is_empty(), "a refusal writes nothing")


func _the_plan_warns_with_a_reason() -> void:
	var sets := _planes()
	var template := _fixture()
	var options := StructurePlace.Options.new()

	sets[0].set_corner(Vector2i(31, 30), 60)
	_expect("levelling" in StructurePlace.plan(sets, template, Vector2i(30, 30), 0,
		options)["warning"], "a levelling of more than one rise warns")

	sets[0].set_flags(Vector2i(44, 40), _Const.TILE_FLAG_WALL_WEST)

	var near := StructurePlace.plan(sets, template, Vector2i(41, 40), 0, options)

	_expect(near["problem"].is_empty() and "blend ring" in near["warning"],
		"a blend ring that reaches a wall warns: %s" % near["warning"])
	options.blend = 0
	_expect(StructurePlace.plan(sets, template, Vector2i(41, 40), 0,
		options)["warning"].is_empty(), "with no blend ring, it does not")


# ─── Delete and move ────────────────────────────────────────────────────────

func _delete_keeps_the_ground_and_empties_the_planes_above() -> void:
	var sets := _planes()
	var rect := _house(sets)
	var selection := _house_selection(sets, rect)
	var edit := TerrainEdit.new()
	var inside := Vector2i(12, 11)

	_expect(StructurePlace.clear(sets, edit, selection.keys) > 0, "the delete changes tiles")
	_expect(sets[0].get_floor(inside) == "concrete", "the ground keeps its floor")
	_expect(sets[0].get_flags(rect.position) & _Const.TILE_FLAGS_WALLS == 0
		and sets[0].get_wall_style(rect.position) == _Const.TILE_DEFAULT_WALL_STYLE,
		"the ground loses its walls and its wall style")
	_expect(sets[0].objects_at(inside).is_empty(), "the decor goes")
	_expect(sets[1].get_floor(inside) == _Const.TILE_VOID_FLOOR
		and sets[1].get_flags(inside) == _Const.TILE_FLAG_BLOCKED,
		"a plane above goes back to void and Blocked")
	_expect(sets[2].get_floor(rect.position - Vector2i.ONE) == _Const.TILE_VOID_FLOOR,
		"the roof overhang goes too")

	edit.replay_planes(sets, false)
	_expect(sets[1].get_floor(inside) != _Const.TILE_VOID_FLOOR
		and not sets[0].objects_at(inside).is_empty(), "undo gives the house back")


func _a_move_may_overlap_the_tiles_it_clears() -> void:
	var sets := _planes()
	var rect := _house(sets)
	var selection := _house_selection(sets, rect)
	var template := StructureTemplate.capture(sets, selection.keys, 0, "house")
	var origin := template.origin + Vector2i(2, 0)
	var options := StructurePlace.Options.new()

	_expect(not StructurePlace.plan(sets, template, origin, 0, options)["problem"].is_empty(),
		"a copy over the house refuses")
	_expect(StructurePlace.plan(sets, template, origin, 0, options,
		selection.keys)["problem"].is_empty(), "a move over its own tiles does not")

	var edit := TerrainEdit.new()

	StructurePlace.clear(sets, edit, selection.keys)

	var result := StructurePlace.place(sets, edit, template, origin, 0, options,
		selection.keys)

	_expect(result["problem"].is_empty(), "the move writes: " + result["problem"])
	_expect(sets[0].get_flags(rect.position) & _Const.TILE_FLAGS_WALLS == 0,
		"the old west wall is gone")
	_expect(sets[0].get_flags(rect.position + Vector2i(2, 0)) & _Const.TILE_FLAG_WALL_WEST,
		"the new west wall stands two tiles east")


func _protect_keeps_the_corners_of_a_structure() -> void:
	var sets := _planes()
	var rect := _house(sets)
	var changes := TerrainBrushes.raise(sets[0], Vector2(rect.position) - Vector2(2, 0), 3.0, 4)
	var kept := TerrainBrushes.protect(changes, sets[0], sets[1])

	_expect(kept.size() < changes.size(), "the filter takes corners out")

	for corner: Vector2i in changes:
		var walled := false

		for tile: Vector2i in TerrainBrushes.corner_tiles(corner):
			walled = walled or TerrainBrushes.is_structure_tile(sets[0], sets[1], tile)

		_expect(kept.has(corner) != walled, "corner %s: kept unless it touches the house"
			% corner)


func _a_click_in_a_room_selects_its_level_and_roof() -> void:
	var sets := _planes()
	var rect := _house(sets)
	var selection := _house_selection(sets, rect)
	var roof := rect.grow(1)

	_expect(selection.size() == rect.get_area() * 2 + roof.get_area(),
		"the room, its level, and its roof with the overhang: %d" % selection.size())
	_expect(selection.plane_span() == Vector2i(0, 2), "planes 0 to 2")

	var only := TileSelection.new()

	only.change_room(sets, 0, rect.position, false, false)
	_expect(only.size() == rect.get_area(), "on this plane only, the room alone")

	only.change_rect(Rect2i(rect.position, Vector2i(2, 1)), [0] as Array[int], true)
	_expect(only.size() == rect.get_area() - 2, "Shift takes tiles out")


# ─── The gestures, with no editor ───────────────────────────────────────────

func _the_select_and_place_gestures_drive_a_world() -> void:
	var scratch := ProjectSettings.globalize_path("user://structure_template_%d"
		% Time.get_ticks_usec())
	var world := TerrainWorld.new()
	var panel := BuildPanel.new()
	var input := BuildInput.new()
	var labels: Array[String] = []

	panel.persist = false
	world.chunk_directory = scratch.path_join("chunks")
	add_child(world)
	input.world = world
	input.panel = panel
	input.templates.template_directory = scratch.path_join("structures")
	input.commit = func(_edit: TerrainEdit, label: String) -> void: labels.append(label)
	panel.set_every_plane(true)

	var options := StructureTools.RoomOptions.new()

	options.wall_style = "brick"
	StructureTools.room(world.chunks, TerrainEdit.new(), Rect2i(3, 3, 4, 3), options, false)

	_select_copy_and_paste(input, panel, world, labels)
	_move_and_delete(input, panel, world, labels)
	_save_and_place_a_template(input, panel, world, labels)
	_a_move_keeps_its_planes(input, panel, world)
	_another_tool_ends_a_move(input, panel)

	world.queue_free()
	panel.free()
	_remove_scratch(scratch)


func _select_copy_and_paste(input: BuildInput, panel: BuildPanel, world: TerrainWorld,
		labels: Array[String]) -> void:
	panel.select_tool(BuildPanel.Tool.SELECT)
	input.on_press(Vector2(4.0, 4.0), false, false)
	input.on_release()
	_expect(input.templates.selection.size() == 12, "a click selects the 4 x 3 room")
	_expect("Selection: 12 tiles" in input.hint(), "the hint counts the selection")

	_expect(input.on_key(_ctrl_key(KEY_C)), "Ctrl+C is a key of the Select tool")
	_expect(input.on_key(_ctrl_key(KEY_V)), "Ctrl+V is a key of the Select tool")
	_expect(panel.current_tool() == BuildPanel.Tool.PLACE
		and panel.template_choice() == BuildPanel.CLIPBOARD, "Ctrl+V places the clipboard")

	input.on_motion(Vector2(21.0, 21.0), false)
	_expect(input.readout().begins_with("4 x 3 tiles"), "the readout gives the size")
	input.on_key(_key(KEY_R))
	input.on_motion(Vector2(21.0, 21.0), false)
	_expect(input.readout().begins_with("3 x 4 tiles"), "R turns the outline")
	input.on_key(_shift_key(KEY_R))
	input.on_press(Vector2(21.0, 21.0), false, false)
	_expect(labels.back() == "Place clipboard", "a click places a copy: %s" % [labels])
	_expect(world.chunks.get_wall_style(Vector2i(19, 20)) == "brick",
		"the copy has the wall style")

	input.on_key(_key(KEY_ESCAPE))
	_expect(panel.current_tool() == BuildPanel.Tool.SELECT, "Esc ends the Place tool")


func _move_and_delete(input: BuildInput, panel: BuildPanel, world: TerrainWorld,
		labels: Array[String]) -> void:
	_expect(input.on_key(_key(KEY_M)), "M moves the selection")
	_expect(panel.current_tool() == BuildPanel.Tool.PLACE, "a move uses the Place tool")
	input.on_motion(Vector2(15.0, 4.0), false)
	_expect(input.readout().ends_with("moves (10, 0)"), "the readout gives the move: "
		+ input.readout())
	input.on_press(Vector2(15.0, 4.0), false, false)

	_expect(labels.back() == "Move, 12 tiles", "the move is one entry: %s" % [labels])
	_expect(world.chunks.get_flags(Vector2i(3, 3)) & _Const.TILE_FLAGS_WALLS == 0,
		"the old room has no wall")
	_expect(world.chunks.get_flags(Vector2i(13, 3)) & _Const.TILE_FLAG_WALL_WEST,
		"the room stands ten tiles east")
	_expect(input.templates.selection.keys.has(Vector3i(13, 3, 0)),
		"the selection follows the move")

	_expect(input.on_key(_key(KEY_DELETE)), "Delete is a key of the Select tool")
	# The label counts the tiles that changed. The two tiles in the middle of
	# the room have no wall.
	_expect(labels.back() == "Delete, 10 tiles", "the delete is one entry: %s" % [labels])
	_expect(world.chunks.get_flags(Vector2i(13, 3)) & _Const.TILE_FLAGS_WALLS == 0,
		"the delete takes the walls")


func _save_and_place_a_template(input: BuildInput, panel: BuildPanel, world: TerrainWorld,
		labels: Array[String]) -> void:
	var options := StructureTools.RoomOptions.new()

	StructureTools.room(world.chunks, TerrainEdit.new(), Rect2i(30, 3, 2, 2), options, false)
	input.on_press(Vector2(30.0, 3.0), false, false)
	input.on_release()

	_expect("key" in input.templates.save_template("Bad Key"), "a bad key names the rule")
	_expect(input.templates.save_template("shed").begins_with("Saved"), "the selection saves")
	_expect(panel.template_choice() == "shed", "the list picks the new template")
	_expect(StructureTemplate.read_file(StructureTemplate.path_for(
		input.templates.directory(), "shed")).error.is_empty(), "the file reads")

	panel.select_tool(BuildPanel.Tool.PLACE)
	input.on_motion(Vector2(40.0, 10.0), false)
	input.on_press(Vector2(40.0, 10.0), false, false)
	_expect(labels.back() == "Place shed", "the template places: %s" % [labels])
	input.on_press(Vector2(44.0, 10.0), false, false)
	_expect(labels.back() == "Place shed" and labels.size() >= 2
		and labels[labels.size() - 2] == "Place shed", "the tool stays on for the next copy")


## A level alone, with no cover on the edited plane, moves on its own plane.
## It must not drop to the edited plane.
func _a_move_keeps_its_planes(input: BuildInput, panel: BuildPanel,
		world: TerrainWorld) -> void:
	var level := Rect2i(50, 3, 2, 2)
	var landing := Vector2i(60, 3)

	StructureTools.level_above(world.plane_sets(), TerrainEdit.new(), 0,
		StructureTools.rect_tiles(level), "concrete", false)
	panel.select_tool(BuildPanel.Tool.SELECT)
	input.templates.selection.clear()
	input.templates.selection.change_rect(level, [1] as Array[int], false)
	input.on_key(_key(KEY_M))
	# The outline puts its centre under the mouse. Thus a 2 x 2 template
	# starts one tile south-west of the mouse.
	input.on_motion(Vector2(landing + Vector2i.ONE), false)
	input.on_press(Vector2(landing + Vector2i.ONE), false, false)

	_expect(world.chunks_on(1).get_floor(landing) == "concrete",
		"the level lands on plane 1")
	_expect(world.chunks_on(0).get_floor(landing) != "concrete",
		"plane 0 under it keeps its ground")
	_expect(world.chunks_on(1).get_floor(level.position) == _Const.TILE_VOID_FLOOR,
		"the old level is void")


## A pick of another tool ends a move. A later Place click then writes the
## template of the list, and clears no old tile.
func _another_tool_ends_a_move(input: BuildInput, panel: BuildPanel) -> void:
	panel.select_tool(BuildPanel.Tool.SELECT)
	input.templates.selection.change_rect(Rect2i(30, 3, 2, 2), [0] as Array[int], false)
	input.on_key(_key(KEY_M))
	_expect(input.templates.moving(), "M starts a move")

	panel.select_tool(BuildPanel.Tool.ROOM)
	input.on_panel_changed()
	_expect(not input.templates.moving(), "another tool ends the move")


static func _ctrl_key(code: Key) -> InputEventKey:
	var event := _key(code)

	event.ctrl_pressed = true

	return event


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
