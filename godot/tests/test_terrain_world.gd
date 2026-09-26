extends Node
## A smoke test of [TerrainWorld], the node that the terrain editor edits.
##
##     godot --headless --path godot res://tests/test_terrain_world.tscn
##
## It runs the node in a real scene tree, against a scratch directory under
## `user://`. It never reads or writes `blackout/world/chunks/`. It proves:
##
## 1. The block loads the files that exist and makes blank chunks for the rest.
## 2. A file that does not read stays out of the block, and a save never
##    overwrites it.
## 3. A save writes each changed chunk as a legal chunk file, with its seams
##    closed.
## 4. Undo through [method TerrainWorld.replay_edit] restores the heights.
## 5. A move of the block saves the changes first.

const _Const := preload("res://autoload/blackout_constants.gd")

const _BROKEN_TEXT := "{}"

var _failures := 0
var _scratch := ""

## The edit of the save case, which the undo case reverses.
var _edit_for_undo: TerrainEdit


func _ready() -> void:
	_scratch = ProjectSettings.globalize_path("user://terrain_world_test_%d"
		% Time.get_ticks_usec())
	DirAccess.make_dir_recursive_absolute(_scratch)
	_write_existing_files()

	var world := TerrainWorld.new()

	world.chunk_directory = _scratch
	add_child(world)

	_the_block_loads_what_exists(world)
	_a_save_writes_legal_files_and_skips_the_broken_one(world)
	_undo_restores_the_heights(world)
	_a_move_saves_first(world)
	_remove_scratch()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: terrain_world")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _path(chunk_coord: Vector2i) -> String:
	var file_name := _Const.CHUNK_FILE_TEMPLATE.format(
		{"cx": chunk_coord.x, "cy": chunk_coord.y, "plane": 0})

	return _scratch.path_join(file_name)


## Chunk 1,0 exists with one raised corner. Chunk 0,1 exists and is broken.
func _write_existing_files() -> void:
	var east := ChunkFile.blank(1, 0)

	east.heights[5 * _Const.CHUNK_CORNERS_PER_SIDE + 5] = 7
	east.write_file(_path(Vector2i(1, 0)))

	var broken := FileAccess.open(_path(Vector2i(0, 1)), FileAccess.WRITE)

	broken.store_string(_BROKEN_TEXT)
	broken.close()


func _the_block_loads_what_exists(world: TerrainWorld) -> void:
	var size: int = _Const.CHUNK_SIZE

	_expect(world.chunks.chunk_coords().size() == 8,
		"eight of nine chunks load, found %d" % world.chunks.chunk_coords().size())
	_expect(world.load_errors.size() == 1, "one file does not read")
	_expect(not world.chunks.has_chunk(Vector2i(0, 1)), "the broken chunk stays out")
	_expect(world.chunks.get_corner(Vector2i(size + 5, 5)) == 7,
		"the existing file is read")
	_expect(not world.has_unsaved_changes(), "a fresh block has no changes")


func _a_save_writes_legal_files_and_skips_the_broken_one(world: TerrainWorld) -> void:
	var size: int = _Const.CHUNK_SIZE
	var edit := TerrainEdit.new()
	var seam := Vector2(size - 0.5, 10.0)

	edit.apply_heights(world.chunks, TerrainBrushes.raise(world.chunks, seam, 2.0, 3))
	world.replay_edit(edit, true)

	var saved := world.save_block()
	var west := ChunkFile.read_file(_path(Vector2i(0, 0)))
	var east := ChunkFile.read_file(_path(Vector2i(1, 0)))
	var reread := ChunkSet.new()

	reread.add(west)
	reread.add(east)

	_expect(saved.size() == 2, "the two chunks at the seam are saved, %d" % saved.size())
	_expect(west.error.is_empty() and east.error.is_empty(), "both files read back")
	_expect(reread.seam_mismatches().is_empty(), "the saved seam is closed")
	_expect(FileAccess.get_file_as_string(_path(Vector2i(0, 1))) == _BROKEN_TEXT,
		"the broken file is not overwritten")
	_expect(not world.has_unsaved_changes(), "a save leaves no changes")
	_edit_for_undo = edit


func _undo_restores_the_heights(world: TerrainWorld) -> void:
	var corner := Vector2i(_Const.CHUNK_SIZE, 10)
	var raised := world.chunks.get_corner(corner)

	world.replay_edit(_edit_for_undo, false)

	_expect(raised == 3, "the seam corner was raised to 3")
	_expect(world.chunks.get_corner(corner) == 0, "undo lowers it to 0")
	_expect(world.has_unsaved_changes(), "undo leaves changes to save")


func _a_move_saves_first(world: TerrainWorld) -> void:
	world.centre_chunk = Vector2i(5, 5)

	var west := ChunkFile.read_file(_path(Vector2i(0, 0)))
	var corner_index := 10 * _Const.CHUNK_CORNERS_PER_SIDE + _Const.CHUNK_SIZE

	_expect(west.heights[corner_index] == 0, "the undone height was saved on the move")
	_expect(world.chunks.has_chunk(Vector2i(5, 5)), "the new block is loaded")


func _remove_scratch() -> void:
	for file_name: String in DirAccess.get_files_at(_scratch):
		DirAccess.remove_absolute(_scratch.path_join(file_name))

	DirAccess.remove_absolute(_scratch)
