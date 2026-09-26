extends Node
## Tests for the data half of the terrain editor: [ChunkSet], [TerrainBrushes],
## [TerrainEdit], and [method ChunkFile.compact_names].
##
##     godot --headless --path godot res://tests/test_terrain_editing.tscn
##
## Needs nothing running and no editor. The plugin itself only routes mouse
## input to these classes, so these cases cover every rule that it applies:
##
## 1. A shared corner is written to every chunk that stores it.
## 2. A corner with an owner that is not loaded is never written.
## 3. Each brush changes what it says, and only that.
## 4. A noise fill of two neighbours at two times leaves no step at the seam.
## 5. Undo returns every value to the value before the stroke.
## 6. A pick finds the tile under the mouse, on a hill too.

const _Const := preload("res://autoload/blackout_constants.gd")

const _NOISE_SEED := 1337
const _NOISE_AMPLITUDE := 40

var _failures := 0


func _ready() -> void:
	_chunk_addressing_handles_negative_coordinates()
	_a_shared_corner_has_every_owner()
	_a_corner_is_written_to_every_owner()
	_a_corner_with_an_unloaded_owner_is_not_editable()
	_a_new_floor_name_joins_the_chunk_list()
	_height_at_reads_the_drawn_surface()
	_raise_changes_the_circle_only()
	_flatten_moves_toward_the_target_by_the_strength()
	_smooth_leaves_flat_ground_alone_and_cuts_a_spike()
	_ramp_runs_from_one_height_to_the_other()
	_noise_fills_meet_at_the_seam()
	_undo_restores_the_state_before_the_stroke()
	_undo_removes_a_placed_object()
	_compact_names_drops_unused_names()
	_a_ray_from_above_hits_the_tile_under_it()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: terrain_editing")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


## A set of the 3 x 3 chunks around `centre`, all blank.
func _block(centre: Vector2i) -> ChunkSet:
	var chunks := ChunkSet.new()

	for dy: int in range(-1, 2):
		for dx: int in range(-1, 2):
			chunks.add(ChunkFile.blank(centre.x + dx, centre.y + dy))

	return chunks


func _noise() -> FastNoiseLite:
	var noise := FastNoiseLite.new()

	noise.seed = _NOISE_SEED
	noise.frequency = 0.03

	return noise


func _chunk_addressing_handles_negative_coordinates() -> void:
	var size: int = _Const.CHUNK_SIZE

	_expect(ChunkSet.chunk_of_tile(Vector2i(0, 0)) == Vector2i(0, 0), "tile 0,0")
	_expect(ChunkSet.chunk_of_tile(Vector2i(-1, -1)) == Vector2i(-1, -1),
		"tile -1,-1 is in chunk -1,-1")
	_expect(ChunkSet.chunk_of_tile(Vector2i(-size, size)) == Vector2i(-1, 1),
		"tile -64,64 is in chunk -1,1")
	_expect(ChunkSet.local_of(Vector2i(-1, 5), Vector2i(-1, 0))
		== Vector2i(size - 1, 5), "tile -1,5 is local 63,5")


func _a_shared_corner_has_every_owner() -> void:
	var size: int = _Const.CHUNK_SIZE

	_expect(ChunkSet.corner_owners(Vector2i(5, 5)).size() == 1, "inner corner")
	_expect(ChunkSet.corner_owners(Vector2i(size, 5)).size() == 2, "edge corner")
	_expect(ChunkSet.corner_owners(Vector2i(0, 0)).size() == 4, "chunk corner")


func _a_corner_is_written_to_every_owner() -> void:
	var chunks := _block(Vector2i(0, 0))
	var corner := Vector2i(0, 0)

	chunks.set_corner(corner, 9)

	for owner_chunk: Vector2i in ChunkSet.corner_owners(corner):
		var local := ChunkSet.local_of(corner, owner_chunk)
		var chunk := chunks.get_chunk(owner_chunk)
		var stored := chunk.heights[local.y * _Const.CHUNK_CORNERS_PER_SIDE + local.x]

		_expect(stored == 9, "owner %s stores the new height" % owner_chunk)

	_expect(chunks.dirty_coords().size() == 4, "all four owners are dirty")
	_expect(chunks.seam_mismatches().is_empty(), "no seam opens")


func _a_corner_with_an_unloaded_owner_is_not_editable() -> void:
	var size: int = _Const.CHUNK_SIZE
	var chunks := _block(Vector2i(0, 0))
	var outer := Vector2i(2 * size, 10)

	_expect(chunks.corner_is_editable(Vector2i(size, 10)), "an inner seam is editable")
	_expect(not chunks.corner_is_editable(outer), "the outer edge is not")

	var changes := TerrainBrushes.raise(chunks, Vector2(outer) - Vector2(0.5, 0.5),
		2.0, 1)

	_expect(not changes.has(outer), "a brush skips a corner it cannot edit")


func _a_new_floor_name_joins_the_chunk_list() -> void:
	var chunks := _block(Vector2i(0, 0))
	var tile := Vector2i(3, 4)

	chunks.set_floor(tile, "asphalt")

	_expect(chunks.get_floor(tile) == "asphalt", "the tile reads the new floor")
	_expect(chunks.get_chunk(Vector2i(0, 0)).floor_names.has("asphalt"),
		"the name joined the list of the chunk")


func _height_at_reads_the_drawn_surface() -> void:
	var chunks := _block(Vector2i(0, 0))

	chunks.set_corner(Vector2i(10, 10), 16)

	var corner_height := chunks.height_at(Vector2(9.5, 9.5))
	var far_height := chunks.height_at(Vector2(30.0, 30.0))
	var unloaded := chunks.height_at(Vector2(1000.0, 0.0))

	_expect(is_equal_approx(corner_height, 16.0), "the raised corner reads 16")
	_expect(is_zero_approx(far_height), "flat ground reads 0")
	_expect(is_nan(unloaded), "an unloaded chunk reads NAN")


func _raise_changes_the_circle_only() -> void:
	var chunks := _block(Vector2i(0, 0))
	var centre := Vector2(20.0, 20.0)
	var changes := TerrainBrushes.raise(chunks, centre, 3.0, 2)
	var outside := 0

	for corner: Vector2i in changes:
		if TerrainBrushes.corner_point(corner).distance_to(centre) > 3.0:
			outside += 1

		_expect(changes[corner] == 2, "corner %s rises by 2" % corner)

	_expect(changes.size() > 0, "raise changes some corners")
	_expect(outside == 0, "raise changes no corner outside the circle")


func _flatten_moves_toward_the_target_by_the_strength() -> void:
	var chunks := _block(Vector2i(0, 0))
	var corner := Vector2i(20, 20)

	chunks.set_corner(corner, 10)

	var changes := TerrainBrushes.flatten(chunks, TerrainBrushes.corner_point(corner),
		1.0, 4, 3)

	_expect(changes.get(corner) == 7, "10 moves 3 steps toward 4")


func _smooth_leaves_flat_ground_alone_and_cuts_a_spike() -> void:
	var chunks := _block(Vector2i(0, 0))
	var corner := Vector2i(20, 20)
	var flat := TerrainBrushes.smooth(chunks, Vector2(20.0, 20.0), 3.0)

	_expect(flat.is_empty(), "smooth changes nothing on flat ground")

	chunks.set_corner(corner, 18)

	var spike := TerrainBrushes.smooth(chunks, TerrainBrushes.corner_point(corner), 1.0)

	_expect(spike.get(corner) == 2, "a spike of 18 becomes the mean, 2")


func _ramp_runs_from_one_height_to_the_other() -> void:
	var chunks := _block(Vector2i(0, 0))
	var start := TerrainBrushes.corner_point(Vector2i(10, 10))
	var end := TerrainBrushes.corner_point(Vector2i(30, 10))
	var changes := TerrainBrushes.ramp(chunks, start, end, 2.0, 0, 20)

	_expect(changes.get(Vector2i(30, 10)) == 20, "the far end is at 20")
	_expect(changes.get(Vector2i(20, 10)) == 10, "the middle is at 10")
	_expect(not changes.has(Vector2i(20, 14)), "a corner off the ramp stays")


func _noise_fills_meet_at_the_seam() -> void:
	var size: int = _Const.CHUNK_SIZE
	var noise := _noise()
	var first := _block(Vector2i(0, 0))
	var west_fill := TerrainBrushes.noise_fill(first, Vector2i(0, 0), noise,
		_NOISE_AMPLITUDE)
	var second := _block(Vector2i(1, 0))
	var east_fill := TerrainBrushes.noise_fill(second, Vector2i(1, 0), noise,
		_NOISE_AMPLITUDE)
	var differ := 0

	for j: int in size + 1:
		var corner := Vector2i(size, j)

		if west_fill.get(corner, 0) != east_fill.get(corner, 0):
			differ += 1

	_expect(west_fill.size() > 0, "the fill changes corners")
	_expect(differ == 0, "two fills agree on the shared edge, %d differ" % differ)


func _undo_restores_the_state_before_the_stroke() -> void:
	var chunks := _block(Vector2i(0, 0))
	var edit := TerrainEdit.new()
	var centre := Vector2(0.0, 0.0)

	edit.apply_heights(chunks, TerrainBrushes.raise(chunks, centre, 2.0, 1))
	edit.apply_heights(chunks, TerrainBrushes.raise(chunks, centre, 2.0, 1))
	edit.apply_flags(chunks, Vector2i(1, 1), _Const.TILE_FLAG_WATER)
	edit.apply_floor(chunks, Vector2i(1, 1), "gravel")
	edit.apply_area(chunks, Vector2i(-1, -1), "azm_plains")

	_expect(chunks.get_corner(Vector2i(0, 0)) == 2, "two dabs raise by 2")

	edit.replay(chunks, false)

	_expect(chunks.get_corner(Vector2i(0, 0)) == 0, "undo lowers to 0")
	_expect(chunks.get_flags(Vector2i(1, 1)) == 0, "undo clears the flag")
	_expect(chunks.get_floor(Vector2i(1, 1)) == _Const.TILE_DEFAULT_FLOOR,
		"undo restores the floor")
	_expect(chunks.get_area(Vector2i(-1, -1)) == _Const.TILE_DEFAULT_AREA,
		"undo restores the area")
	_expect(chunks.seam_mismatches().is_empty(), "undo opens no seam")

	edit.replay(chunks, true)

	_expect(chunks.get_corner(Vector2i(0, 0)) == 2, "redo raises to 2 again")
	_expect(chunks.get_floor(Vector2i(1, 1)) == "gravel", "redo paints again")


func _undo_removes_a_placed_object() -> void:
	var chunks := _block(Vector2i(0, 0))
	var edit := TerrainEdit.new()
	var tile := Vector2i(-3, 7)

	edit.add_object(chunks, tile, "bank", 1)

	_expect(chunks.objects_at(tile).size() == 1, "the object is placed")

	edit.replay(chunks, false)

	_expect(chunks.objects_at(tile).is_empty(), "undo removes it")

	edit.replay(chunks, true)

	_expect(chunks.objects_at(tile).size() == 1, "redo places it again")


func _compact_names_drops_unused_names() -> void:
	var chunk := ChunkFile.blank(0, 0)

	chunk.floor_names = PackedStringArray(["sand", "dirt", "gravel"])
	chunk.floors.fill(2)
	chunk.floors[0] = 0
	chunk.compact_names()

	_expect(chunk.floor_names == PackedStringArray(["sand", "gravel"]),
		"dirt goes, the order stays")
	_expect(chunk.floors[0] == 0 and chunk.floors[1] == 1,
		"the grid is renumbered")

	var reread := ChunkFile.parse_text(chunk.to_text())

	_expect(reread.error.is_empty(), "the compacted chunk is a legal file")


func _a_ray_from_above_hits_the_tile_under_it() -> void:
	var chunks := _block(Vector2i(0, 0))
	var tile := Vector2i(12, 20)

	for corner: Vector2i in TerrainBrushes.corners_in_circle(Vector2(tile), 4.0):
		chunks.set_corner(corner, 48)

	var above := Vector3(tile.x, 40.0, -tile.y)
	var slanted := Vector3(tile.x - 10.0, 40.0, -tile.y)
	var target := Vector3(tile.x, 3.0, -tile.y)
	var straight: Variant = TerrainPicking.ray_hit(chunks, above, Vector3.DOWN)
	var angled: Variant = TerrainPicking.ray_hit(chunks, slanted, target - slanted)
	var missed: Variant = TerrainPicking.ray_hit(chunks, above, Vector3.UP)

	_expect(straight != null and ChunkSet.tile_at(TerrainPicking.tile_point(straight))
		== tile, "a ray straight down hits the tile under it")
	_expect(straight != null and is_equal_approx(straight.y, 3.0),
		"it hits the top of the hill, 48 steps is 3 units")
	_expect(angled != null and ChunkSet.tile_at(TerrainPicking.tile_point(angled))
		== tile, "a slanted ray hits the hill top, not the ground behind it")
	_expect(missed == null, "a ray up hits nothing")
