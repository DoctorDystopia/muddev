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
	_each_plane_gets_its_own_mesh()
	_roofs_hide_the_planes_above_the_player()
	_a_climb_shows_the_plane_it_reaches()
	_the_chunk_under_the_player_builds_first()

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
	view.flush()

	_expect(view.chunk_count() == 2, "two chunks give two meshes")
	view.queue_free()


func _a_chunk_sent_again_is_built_again() -> void:
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]

	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(0, 0)))
	view.flush()

	var first: Node = view.get_child(0)

	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(0, 0)))
	view.flush()

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
	view.flush()
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
	view.flush()

	var node: MeshInstance3D = view.get_child(0)
	var drawn_mesh: ArrayMesh = node.mesh
	var drawn: int = drawn_mesh.surface_get_array_len(0)
	var built: int = ChunkMeshBuilder.build(chunk).surface_get_array_len(0)

	_expect(drawn == built, "the drawn ground has the vertices of the builder")
	view.queue_free()


func _each_plane_gets_its_own_mesh() -> void:
	# Phase 7b. Two chunks at one (cx, cy) on two planes are two meshes. The
	# plane-1 chunk does not replace the plane-0 chunk.
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]

	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(0, 0)))
	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(0, 0, 1)))
	view.flush()

	_expect(view.chunk_count() == 2, "two planes over one chunk give two meshes")
	_expect(view.chunk_node(Vector2i.ZERO, 0) != view.chunk_node(Vector2i.ZERO, 1),
		"each plane has its own node")
	view.queue_free()


func _roofs_hide_the_planes_above_the_player() -> void:
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]

	state.ingest(_Const.CH_ROOM_INFO, {"coords": [5.0, 5.0, _Const.TILE_WORLD_Z]})
	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(0, 0)))
	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(0, 0, 1)))
	view.flush()

	_expect(view.chunk_node(Vector2i.ZERO, 0).visible, "the plane of the player shows")
	_expect(not view.chunk_node(Vector2i.ZERO, 1).visible,
		"the plane above hides by default")

	view.set_hide_roofs(false)

	_expect(view.chunk_node(Vector2i.ZERO, 1).visible,
		"with Hide roofs off, the plane above shows")
	view.queue_free()


func _a_climb_shows_the_plane_it_reaches() -> void:
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]
	var upper_z := WorldState.plane_z(1)

	state.ingest(_Const.CH_ROOM_INFO, {"coords": [5.0, 5.0, _Const.TILE_WORLD_Z]})
	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(0, 0)))
	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(0, 0, 1)))
	view.flush()
	state.ingest(_Const.CH_ROOM_INFO, {"coords": [5.0, 5.0, upper_z]})

	_expect(view.chunk_node(Vector2i.ZERO, 1).visible, "a climb shows plane 1")
	_expect(view.chunk_node(Vector2i.ZERO, 0).visible, "and the ground below")
	view.queue_free()


func _the_chunk_under_the_player_builds_first() -> void:
	# One build for each frame. The chunk under the player, on its plane,
	# must not wait behind the other planes.
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]
	var home := Vector2i(1, 1) * _Const.CHUNK_SIZE + Vector2i(5, 5)

	state.ingest(_Const.CH_ROOM_INFO, {"coords": [float(home.x), float(home.y),
		WorldState.plane_z(1)]})

	for plane: int in [0, 1]:
		for coord: Vector2i in WorldState.block_of(home):
			state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(coord.x,
				coord.y, plane)))

	_expect(view.chunk_count() == 0, "nothing builds before a frame")

	view._process(0.0)

	_expect(view.chunk_count() == TerrainView.BUILDS_PER_FRAME,
		"one frame builds one chunk")
	_expect(view.chunk_node(Vector2i(1, 1), 1) != null,
		"the first is the chunk under the player, on its plane")
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
