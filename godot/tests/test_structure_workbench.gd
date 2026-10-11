extends Node
## Tests for the structure workbench (DESIGN-0013 Phase S6): the terrain
## editor on a scratch chunk directory, for a template away from the world.
##
##     godot --headless --path godot res://tests/test_structure_workbench.tscn
##
## Needs nothing running and no editor. It never writes, and never deletes,
## a file of `blackout/world/chunks/` or of `blackout/world/structures/`.
## The scene of the workbench loads, but it does not go into the tree, so it
## reads no chunk file of the author. The cases:
##
## 1. The scene points at the scratch directory, and it does not write the
##    world.
## 2. A `user://` path resolves to an OS path. The path test ignores the
##    case, the slash, and a slash at the end.
## 3. A save writes only into the scratch directory.
## 4. A template saves from the workbench, and a copy of it places there.
## 5. "Clear the structure workbench" deletes only the chunk files, and loads
##    blank ground. A node with no chunk directory writes the world, and the
##    clear refuses such a node. No case calls the clear on the world: a
##    fault in the guard would then delete the world chunk files.
## 6. "Check world" there leaves out the rules of a whole world.

const _Const := preload("res://autoload/blackout_constants.gd")

const WORKBENCH_SCENE := "res://addons/blackout_terrain/structure_workbench.tscn"

## A file in the scratch directory that is not a chunk file. A clear keeps it.
const OTHER_FILE := "notes.txt"

var _failures := 0
var _scratch := ""


func _ready() -> void:
	_scratch = ProjectSettings.globalize_path("user://structure_workbench_test_%d"
		% Time.get_ticks_usec())

	_the_scene_points_at_the_scratch_directory()
	_a_path_resolves_and_compares()
	_the_workbench_builds_saves_and_clears()
	_the_check_leaves_out_the_world_rules()
	_remove_scratch(_scratch)

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: structure_workbench")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _the_scene_points_at_the_scratch_directory() -> void:
	var scene: PackedScene = load(WORKBENCH_SCENE)
	var root := scene.instantiate()
	var world := root.get_node("TerrainWorld") as TerrainWorld

	_expect(world != null, "the scene holds a TerrainWorld")

	if world != null:
		_expect(world.chunk_directory == TerrainWorld.WORKBENCH_DIRECTORY,
			"the scene uses the workbench directory")
		_expect(not world.writes_world(), "the workbench does not write the world")
		_expect(world.directory().begins_with(ProjectSettings.globalize_path("user://")),
			"the scratch files are outside the repo")

	root.free()


func _a_path_resolves_and_compares() -> void:
	var world := TerrainWorld.new()

	_expect(world.writes_world(), "an empty directory is the world")

	world.chunk_directory = "user://abc"
	_expect(world.directory() == ProjectSettings.globalize_path("user://abc"),
		"a user:// path resolves to an OS path")
	_expect(TerrainWorld.same_directory("C:/a/b/", "C:\\a\\b"),
		"a slash at the end and a back slash do not matter")
	_expect(TerrainWorld.same_directory("C:/a/c/../b", "C:/a/b"),
		"the test simplifies the path")
	_expect(not TerrainWorld.same_directory("C:/a/b", "C:/a/bc"),
		"two directories differ")

	if OS.get_name() == "Windows":
		_expect(TerrainWorld.same_directory("C:/A/B", "c:/a/b"),
			"Windows ignores the case")

	world.free()


func _the_workbench_builds_saves_and_clears() -> void:
	var world := TerrainWorld.new()
	var panel := BuildPanel.new()
	var input := BuildInput.new()
	var templates := _scratch.path_join("structures")

	panel.persist = false
	world.chunk_directory = _scratch.path_join("chunks")
	add_child(world)
	input.world = world
	input.panel = panel
	input.templates.template_directory = templates
	input.commit = func(_edit: TerrainEdit, _label: String) -> void: pass

	var saved := _build_and_save(world)

	_expect(saved.size() > 0 and FileAccess.file_exists(world.chunk_path(Vector2i.ZERO, 0)),
		"a save writes into the scratch directory: %s" % saved)
	_save_and_place_a_template(input, panel, world)
	_clear(world)

	world.queue_free()
	panel.free()


## A room with a level, saved. Returns the names of the saved files.
func _build_and_save(world: TerrainWorld) -> PackedStringArray:
	var edit := TerrainEdit.for_world(world)
	var options := StructureTools.RoomOptions.new()
	var room := Rect2i(4, 4, 3, 3)

	options.floor_name = "concrete"
	StructureTools.room(world.chunks, edit, room, options, false)
	StructureTools.level_above(world.plane_sets(), edit, 0, StructureTools.rect_tiles(room),
		"", false)

	return world.save_block()


func _save_and_place_a_template(input: BuildInput, panel: BuildPanel,
		world: TerrainWorld) -> void:
	panel.set_every_plane(true)
	panel.select_tool(BuildPanel.Tool.SELECT)
	input.on_press(Vector2(5.0, 5.0), false, false)
	input.on_release()

	var status := input.save_template("bench_room")

	_expect(status.begins_with("Saved"), "the template saves: " + status)

	var template := StructureTemplate.read_file(StructureTemplate.path_for(
		input.templates.directory(), "bench_room"))

	_expect(template.error.is_empty() and template.layers.size() == 2,
		"the file reads, with the room and its level: " + template.error)

	panel.select_tool(BuildPanel.Tool.PLACE)
	input.on_motion(Vector2(21.0, 21.0), false)
	input.on_press(Vector2(21.0, 21.0), false, false)
	_expect(world.chunks.get_floor(Vector2i(21, 21)) == "concrete"
		and world.chunks_on(1).get_floor(Vector2i(21, 21)) == "concrete",
		"a copy places in the workbench")


func _clear(world: TerrainWorld) -> void:
	var other := world.directory().path_join(OTHER_FILE)
	var file := FileAccess.open(other, FileAccess.WRITE)

	file.store_string("keep me")
	file.close()

	var deleted := world.clear_workbench()

	_expect(deleted >= 2, "the clear deletes the saved chunk files: %d" % deleted)
	_expect(FileAccess.file_exists(other), "the clear keeps a file that is not a chunk")
	_expect(not world.has_unsaved_changes(), "the unsaved copy goes too")
	_expect(world.chunks.get_floor(Vector2i(5, 5)) == _Const.TILE_DEFAULT_FLOOR
		and world.chunks.get_flags(Vector2i(4, 4)) & _Const.TILE_FLAGS_WALLS == 0,
		"the block is blank ground again")
	_expect(not world.chunk_exists(Vector2i.ZERO, 1), "the level above is gone")


func _the_check_leaves_out_the_world_rules() -> void:
	var found: Array[Dictionary] = [
		{"rule": _Const.TILE_CHECK_RESPAWN_COUNT, "x": 0, "y": 0, "plane": 0, "message": ""},
		{"rule": _Const.TILE_CHECK_UNREACHABLE, "x": 1, "y": 1, "plane": 0, "message": ""},
		{"rule": _Const.TILE_CHECK_WALL_ON_VOID, "x": 2, "y": 2, "plane": 1, "message": ""},
	]
	var kept := TerrainChecks.for_workbench(found)

	_expect(kept.size() == 1 and kept[0]["rule"] == _Const.TILE_CHECK_WALL_ON_VOID,
		"the workbench check keeps the rules of a structure only")


## Delete the scratch tree of this test: files first, then directories.
func _remove_scratch(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return

	for child: String in DirAccess.get_directories_at(path):
		_remove_scratch(path.path_join(child))

	for file_name: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(file_name))

	DirAccess.remove_absolute(path)
