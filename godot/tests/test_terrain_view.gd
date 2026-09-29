extends Node
## Unit tests for TerrainView: the ground of the tile world follows the chunk
## set of [WorldState].
##
##     godot --headless --path godot res://tests/test_terrain_view.tscn
##
## Exits 0 when every case passes, 1 on the first failure.

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


## A resolver with art for every key, and no fetch. The real one needs the
## served manifest.
class _FakeResolver extends MeshResolver:
	## Keys with no art yet. [method resolve_scenery] answers null for them.
	var pending := {}

	func _init() -> void:
		super(ModelRegistry.new(), "")

	func resolve_scenery(asset_key: String) -> Node3D:
		if asset_key.is_empty() or pending.has(asset_key):
			return null

		var model := MeshInstance3D.new()
		var box := BoxMesh.new()

		box.size = Vector3(1.0, 0.2, 1.0)
		model.mesh = box
		model.name = asset_key

		return model


func _ready() -> void:
	_each_chunk_gets_one_mesh()
	_a_chunk_sent_again_is_built_again()
	_a_freed_chunk_loses_its_mesh()
	_the_mesh_is_the_mesh_of_the_builder()
	_each_plane_gets_its_own_mesh()
	_roofs_hide_the_planes_above_the_player()
	_a_climb_shows_the_plane_it_reaches()
	_the_chunk_under_the_player_builds_first()
	_a_chunk_with_walls_gets_a_walls_layer()
	_a_climb_draws_a_primitive_and_asks_for_no_model()
	_a_transition_gets_the_teleporter()
	_a_kind_with_no_scenery_stands_nothing()
	_scenery_stands_when_its_art_arrives()
	_a_model_yaw_faces_the_way_a_step_faces()

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


func _a_chunk_with_walls_gets_a_walls_layer() -> void:
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]
	var walled := ChunkFile.blank(0, 0)

	walled.flags[3] = _Const.TILE_FLAG_WALL_NORTH
	state.ingest(_Const.CH_TILE_CHUNK, _payload(walled))
	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(1, 0)))
	view.flush()

	_expect(view.chunk_node(Vector2i(0, 0), 0).has_node("Walls"),
		"a chunk with a wall flag draws its walls")
	_expect(not view.chunk_node(Vector2i(1, 0), 0).has_node("Walls"),
		"a chunk with no wall has no walls layer")
	view.queue_free()


func _a_climb_draws_a_primitive_and_asks_for_no_model() -> void:
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]
	var resolver := _FakeResolver.new()
	var climbing := ChunkFile.blank(0, 0)

	climbing.objects.append({"kind": _a_primitive_kind(), "x": 3, "y": 3,
		"rotation": 2})
	view.bind_meshes(resolver)
	state.ingest(_Const.CH_TILE_CHUNK, _payload(climbing))
	state.ingest(_Const.CH_TILE_CHUNK, _payload(ChunkFile.blank(1, 0)))
	view.flush()

	_expect(view.chunk_node(Vector2i(0, 0), 0).has_node(TerrainView.PROPS_NODE),
		"a chunk with a climb draws its primitive")
	_expect(not view.chunk_node(Vector2i(1, 0), 0).has_node(TerrainView.PROPS_NODE),
		"a chunk with no primitive has no props layer")
	# The fake resolver has art for every key. A model here would draw the
	# climb two times.
	_expect(view.scenery_of(Vector2i.ZERO, 0).is_empty(),
		"a primitive asks the resolver for no model")
	view.queue_free()
	resolver.free()


func _a_transition_gets_the_teleporter() -> void:
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]
	var resolver := _FakeResolver.new()
	var chunk := ChunkFile.blank(0, 0)
	var kind := _a_scenery_kind()

	chunk.objects.append({"kind": kind, "x": 4, "y": 6, "rotation": 1})
	view.bind_meshes(resolver)
	state.ingest(_Const.CH_TILE_CHUNK, _payload(chunk))
	view.flush()

	var scenery := view.scenery_of(Vector2i.ZERO, 0)

	_expect(scenery.size() == 1, "a transition stands one scenery model")

	if scenery.size() == 1:
		var model: Node3D = scenery[0]

		_expect(model.name == _Const.OBJECT_KIND_SCENERY[kind],
			"the model is the one that the server names")
		_expect(is_equal_approx(model.position.x, 4.0)
				and is_equal_approx(model.position.z, -6.0),
			"it stands on the centre of its tile")
		_expect(model.position.y > 0.0, "it rests on the ground, not through it")
		_expect(is_equal_approx(model.rotation.y, TerrainView.model_yaw(1)),
			"it turns by the rotation of its object")

	view.queue_free()
	resolver.free()


func _a_kind_with_no_scenery_stands_nothing() -> void:
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]
	var resolver := _FakeResolver.new()
	var chunk := ChunkFile.blank(0, 0)

	chunk.objects.append({"kind": "respawn_point", "x": 1, "y": 1, "rotation": 0})
	view.bind_meshes(resolver)
	state.ingest(_Const.CH_TILE_CHUNK, _payload(chunk))
	view.flush()

	_expect(view.scenery_of(Vector2i.ZERO, 0).is_empty(),
		"a kind with no scenery row stands nothing")
	view.queue_free()
	resolver.free()


func _scenery_stands_when_its_art_arrives() -> void:
	var fixture := _bound()
	var state: WorldState = fixture[0]
	var view: TerrainView = fixture[1]
	var resolver := _FakeResolver.new()
	var chunk := ChunkFile.blank(0, 0)
	var kind := _a_scenery_kind()
	var asset_key: String = _Const.OBJECT_KIND_SCENERY[kind]

	resolver.pending[asset_key] = true
	chunk.objects.append({"kind": kind, "x": 2, "y": 2, "rotation": 0})
	view.bind_meshes(resolver)
	state.ingest(_Const.CH_TILE_CHUNK, _payload(chunk))
	view.flush()

	_expect(view.scenery_of(Vector2i.ZERO, 0).is_empty(),
		"no art yet, no model")

	resolver.pending.clear()
	resolver.refreshed.emit(asset_key)

	_expect(view.scenery_of(Vector2i.ZERO, 0).size() == 1,
		"the model stands when its art arrives")
	view.queue_free()
	resolver.free()


# ─── Private helpers ─────────────────────────────────────────────────────────

## The first kind whose scenery is a primitive.
func _a_primitive_kind() -> String:
	for kind: String in _Const.OBJECT_KIND_SCENERY:
		if _Const.OBJECT_KIND_SCENERY[kind] in _Const.SCENERY_PRIMITIVES:
			return kind

	_expect(false, "some kind shows a primitive")

	return ""


## The first transition kind that names a scenery model.
func _a_scenery_kind() -> String:
	for kind: String in _Const.OBJECT_KIND_SCENERY:
		if _Const.OBJECT_KINDS[kind] == _Const.OBJECT_CATEGORY_TRANSITION:
			return kind

	return ""

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


## Rotation 0 faces north, and each quarter turn goes clockwise from above. A
## served model faces +Z, as a walking figure does, so each rotation must give
## the yaw of a step in its direction.
func _a_model_yaw_faces_the_way_a_step_faces() -> void:
	var steps := [Vector2i(0, 1), Vector2i(1, 0), Vector2i(0, -1), Vector2i(-1, 0)]

	for rotation: int in _Const.CHUNK_ROTATION_COUNT:
		var step_yaw := WorldView.yaw_towards(Vector2i.ZERO, steps[rotation], 0.0)

		_expect(is_equal_approx(TerrainView.model_yaw(rotation), step_yaw),
			"rotation %d faces the way a step %s faces" % [rotation, steps[rotation]])
