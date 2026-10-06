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
## 6. A new plane-1 chunk starts from the chunk below, and plane 0 shows as
##    a ghost under it (Phase 7c).
## 7. An undo entry of another plane or block changes nothing.
## 8. "Check world" sees the block over the files on disk.
## 9. A jump loads the block of a tile, and a selection knows its link.

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
	_a_new_upper_chunk_starts_from_the_chunk_below(world)
	_an_edit_of_another_plane_is_refused(world)
	_the_world_files_put_the_block_over_the_disk(world)
	_a_jump_loads_the_block_of_the_tile(world)
	_a_selection_knows_its_link_and_an_undo_clears_it(world)
	_a_sign_keeps_its_words_and_its_marker_shows_its_turn(world)
	_an_entity_kind_draws_its_model_turned(world)
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

	var whole := TerrainWorld.BLOCK_SIDE * TerrainWorld.BLOCK_SIDE

	_expect(world.chunks.chunk_coords().size() == whole - 1,
		"all chunks but the broken one load, found %d" % world.chunks.chunk_coords().size())
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


func _a_new_upper_chunk_starts_from_the_chunk_below(world: TerrainWorld) -> void:
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE
	var tiles: int = _Const.CHUNK_SIZE * _Const.CHUNK_SIZE

	world.move_block(Vector2i(1, 0), 1)

	var upper := world.chunks.get_chunk(Vector2i(1, 0))

	_expect(world.plane == 1 and upper.plane == 1, "the block is on plane 1")
	_expect(upper.heights[5 * side + 5] == 7 + TerrainWorld.NEW_PLANE_RISE,
		"a new plane-1 chunk has the heights below plus the rise")
	_expect(upper.floor_names == PackedStringArray([_Const.TILE_VOID_FLOOR]),
		"every tile of it is void")
	_expect(upper.flags.count(_Const.TILE_FLAG_BLOCKED) == tiles,
		"and Blocked")
	_expect(not world.has_unsaved_changes(), "it is not saved before an edit")
	_expect(world.ghost_count() == 2,
		"the two plane-0 files that read show below, %d" % world.ghost_count())


func _an_edit_of_another_plane_is_refused(world: TerrainWorld) -> void:
	# The edit of the save case was made on plane 0, block (0, 0).
	var corner := Vector2i(_Const.CHUNK_SIZE, 10)
	var before := world.chunks.get_corner(corner)

	_expect(not world.replay_edit(_edit_for_undo, true),
		"an edit of plane 0 does not replay on plane 1")
	_expect(world.chunks.get_corner(corner) == before, "and changes nothing")


func _the_world_files_put_the_block_over_the_disk(world: TerrainWorld) -> void:
	var tile := Vector2i(_Const.CHUNK_SIZE + 3, 3)
	var edit := TerrainEdit.for_world(world)

	edit.apply_floor(world.chunks, tile, "concrete")
	edit.apply_flags(world.chunks, tile, 0)

	var errors := PackedStringArray()
	var files := world.world_chunk_files(errors)
	var upper: Array[ChunkFile] = []

	for chunk: ChunkFile in files:
		if chunk.plane == 1:
			upper.append(chunk)

	_expect(errors.size() == 1, "the broken file is named")
	_expect(upper.size() == 1 and upper[0] == world.chunks.get_chunk(Vector2i(1, 0)),
		"only the edited plane-1 chunk joins, as it is in memory")


func _a_jump_loads_the_block_of_the_tile(world: TerrainWorld) -> void:
	var far := Vector2i(5, 5) * _Const.CHUNK_SIZE + Vector2i(3, 3)

	world.jump_to(far, 0)

	_expect(world.centre_chunk == Vector2i(5, 5) and world.plane == 0,
		"a jump loads the block and the plane of the tile")
	_expect(FileAccess.file_exists(_path_on(Vector2i(1, 0), 1)),
		"the edited plane-1 chunk was saved on the jump")


func _a_selection_knows_its_link_and_an_undo_clears_it(world: TerrainWorld) -> void:
	var base := Vector2i(5, 5) * _Const.CHUNK_SIZE
	var gate := base + Vector2i(1, 1)
	var ladder := base + Vector2i(2, 2)
	var edit := TerrainEdit.for_world(world)
	var gate_kind: String = _Const.OBJECT_KIND_TARGETS.keys()[0]
	var target: Array = _Const.OBJECT_KIND_TARGETS[gate_kind]

	edit.add_object(world.chunks, gate, gate_kind, 0)
	edit.add_object(world.chunks, ladder, "ladder_up", 0)
	world.select(gate, gate_kind, 0)

	_expect(world.selected_link_end() == {"tile": Vector2i(target[0], target[1]),
		"plane": 0}, "a transition leads to its target")

	world.select(ladder, "ladder_up", 0)

	_expect(world.selected_link_end() == {"tile": ladder, "plane": 1},
		"a ladder up leads to the same tile of plane 1")

	world.replay_edit(edit, false)

	_expect(world.selected.is_empty(), "an undo that removes the object clears it")


func _a_sign_keeps_its_words_and_its_marker_shows_its_turn(world: TerrainWorld) -> void:
	var chunk_coord := Vector2i(5, 5)
	var tile := chunk_coord * _Const.CHUNK_SIZE + Vector2i(3, 3)
	var kind: String = _Const.OBJECT_SIGNPOST_KIND
	var words := "Oasis Market"
	var edit := TerrainEdit.for_world(world)

	edit.add_object(world.chunks, tile, kind, 1, words)
	world.rebuild_many(edit.chunk_coords())
	world.select(tile, kind, 1, words)
	world.rebuild_many(edit.chunk_coords())

	_expect(world.selected.get("text", "") == words,
		"the selection of a sign keeps its words over a redraw")
	_expect(world.chunks.objects_at(tile)[0]["text"] == words,
		"the chunk holds the words")

	var markers := world.markers_of(chunk_coord)

	_expect(markers.size() == 1, "one marker stands for the sign")

	if markers.size() == 1:
		var marker: Node3D = markers[0]
		var label: Label3D = marker.get_child(1)
		var nose: Node3D = marker.get_node(TerrainWorld.MARKER_NOSE_NODE)
		var facing := marker.basis * nose.position

		_expect(words in label.text, "the marker label shows the words")
		_expect(facing.x > 0.0 and absf(facing.z) < 0.001,
			"at rotation 1 the nose points east")

	world.replay_edit(edit, false)

	_expect(world.chunks.objects_at(tile).is_empty(), "an undo removes the sign")


## The editor draws the model of an entity kind, turned as its object, and
## the marker draws no box over it. A primitive draws no model. The kind is
## the first entity kind that the server names, so a new kind needs no edit.
func _an_entity_kind_draws_its_model_turned(world: TerrainWorld) -> void:
	var chunk_coord := Vector2i(5, 5)
	var tile := chunk_coord * _Const.CHUNK_SIZE + Vector2i(6, 6)
	var ladder := tile + Vector2i(2, 0)
	var kind: String = _Const.OBJECT_KIND_PREVIEW.keys()[0]
	var turn := 3
	var edit := TerrainEdit.for_world(world)

	edit.add_object(world.chunks, tile, kind, turn)
	edit.add_object(world.chunks, ladder, "ladder_up", 0)
	world.rebuild_many(edit.chunk_coords())

	var models := world.models_of(chunk_coord)

	_expect(models.size() == 1, "one model for the entity kind, none for a ladder")

	if models.size() == 1:
		var model: Node3D = models[0]

		_expect(is_equal_approx(model.rotation.y, TerrainView.model_yaw(turn)),
			"the model turns as its object")

	var boxes := 0

	for marker: MeshInstance3D in world.markers_of(chunk_coord):
		if marker.mesh != null:
			boxes += 1

	_expect(boxes == 1, "only the ladder marker keeps its box")

	world.show_models = false
	_expect(world.models_of(chunk_coord).is_empty(), "Show models off draws none")
	world.show_models = true
	world.replay_edit(edit, false)


func _path_on(chunk_coord: Vector2i, plane: int) -> String:
	var file_name := _Const.CHUNK_FILE_TEMPLATE.format(
		{"cx": chunk_coord.x, "cy": chunk_coord.y, "plane": plane})

	return _scratch.path_join(file_name)


func _remove_scratch() -> void:
	for file_name: String in DirAccess.get_files_at(_scratch):
		DirAccess.remove_absolute(_scratch.path_join(file_name))

	DirAccess.remove_absolute(_scratch)
