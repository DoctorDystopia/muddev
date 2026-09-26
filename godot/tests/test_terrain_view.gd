extends Node
## Unit tests for TerrainView: the ground of the tile world follows the chunk
## set of [WorldState].
##
##     godot --headless --path godot res://tests/test_terrain_view.tscn
##
## Exits 0 when every case passes, 1 on the first failure.

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_each_chunk_gets_one_mesh()
	_a_chunk_sent_again_is_built_again()
	_a_freed_chunk_loses_its_mesh()
	_the_mesh_is_the_mesh_of_the_builder()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: terrain_view")
	get_tree().quit(0)


# ─── Cases ───────────────────────────────────────────────────────────────────

func _each_chunk_gets_one_mesh() -> void:
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]

	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(0, 0)))
	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(1, 0)))

	_expect(view.chunk_count() == 2, "two chunks give two meshes")
	view.queue_free()


func _a_chunk_sent_again_is_built_again() -> void:
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]

	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(0, 0)))

	var first: Node = view.get_child(0)

	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(0, 0)))

	_expect(view.chunk_count() == 1, "a chunk sent again is still one mesh")
	_expect(view.get_child(0) != first, "and that mesh is new")
	view.queue_free()


func _a_freed_chunk_loses_its_mesh() -> void:
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]
	var far := Vector2i(_Const.CHUNK_STREAM_RADIUS + 2, 0)

	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(0, 0)))
	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(far.x, far.y)))
	state.ingest(_Const.CH_ROOM_INFO, {"coords": [5.0, 5.0, _Const.TILE_WORLD_Z]})

	_expect(view.chunk_count() == 1, "a chunk past the block loses its mesh")
	view.queue_free()


func _the_mesh_is_the_mesh_of_the_builder() -> void:
	# What the author sees in the editor is what the player sees: one class
	# draws both.
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]
	var chunk := ChunkFile.blank(0, 0)

	state.ingest(_Const.CH_TILE_CHUNK, _payload(chunk))

	var node: MeshInstance3D = view.get_child(0)
	var drawn_mesh: ArrayMesh = node.mesh
	var drawn: int = drawn_mesh.surface_get_array_len(0)
	var built: int = ChunkMeshBuilder.build(chunk).surface_get_array_len(0)

	_expect(drawn == built, "the drawn ground has the vertices of the builder")
	view.queue_free()


# ─── Private helpers ─────────────────────────────────────────────────────────

## A new state and a view bound to it, in the tree.
func _bound() -> Array:
	var state := WorldState.new()
	var view := TerrainView.new()

	add_child(view)
	view.bind(state)

	return [state, view]


func _payload(chunk: ChunkFile) -> Dictionary:
	return {"chunk_file": JSON.parse_string(chunk.to_text())}


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
