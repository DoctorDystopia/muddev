class_name TerrainView
extends Node3D
## The ground of the tile world: one mesh for each chunk that the client holds,
## on every plane.
##
## DESIGN-0011 section 6.6, Phase 5. The chunks come from [WorldState], which
## keeps the block around the player. This node only draws them. It builds a
## mesh for a new chunk, builds it again when the server sends a chunk again
## (after a resync), and frees the mesh of a chunk that left the block.
##
## [ChunkMeshBuilder] draws the ground, the same class that the terrain editor
## uses. Thus, what an author sees in the editor is what a player sees.
##
## The material is the one of the editor: vertex colour from the floor type,
## and a rough surface. The flat shading comes from the mesh, which gives each
## triangle its own normal (DESIGN-0011 section 6.8).
##
## ## Planes (Phase 7b)
##
## Each plane stores its own absolute heights, so a plane-1 chunk draws at its
## own heights with no offset. A void tile has no triangle, so the plane below
## shows through it. With "Hide roofs" on (the default, [ClientSettings]),
## every plane above the plane of the player is hidden, as in OSRS.
##
## A chunk with a water tile also gets a "Water" child: the flat surface of
## [WaterMeshBuilder].
##
## ## One build for each frame
##
## One chunk mesh costs about 18 ms. Nine chunks on each of four planes would
## stop the client for more than half a second. Thus [method sync] only queues
## the builds, and each frame builds [constant BUILDS_PER_FRAME] of them. The
## chunk under the player builds first: its own plane first, then the nearest
## chunk. [method flush] builds the whole queue at once, for a test.

## Chunk meshes built in one frame.
const BUILDS_PER_FRAME := 1

## The world model, bound by the world pane.
var _state: WorldState

## Key (Vector3i: cx, cy, plane) -> the MeshInstance3D that draws it.
var _nodes := {}

## Key -> the ChunkFile that its mesh shows. A chunk that the server sends
## again is a new ChunkFile, so a changed object here means "build again".
var _built := {}

## Keys to build, first key first.
var _queue: Array[Vector3i] = []

## Hide every plane above the plane of the player.
var _hide_roofs := true

var _material: StandardMaterial3D


func _init() -> void:
	_material = StandardMaterial3D.new()
	_material.vertex_color_use_as_albedo = true
	_material.roughness = 1.0


## Draw the chunks of this model, now and each time they change.
func bind(state: WorldState) -> void:
	_state = state
	_state.chunks_changed.connect(sync)
	_state.room_changed.connect(_on_room_changed)
	sync()


## Hide or show the planes above the plane of the player.
func set_hide_roofs(hidden: bool) -> void:
	_hide_roofs = hidden
	_refresh_visibility()


## Make the meshes match the chunk sets: free the meshes of chunks that went,
## and queue a build for each chunk that is new or was sent again.
func sync() -> void:
	if _state == null:
		return

	var present := _present_chunks()

	for key: Vector3i in _nodes.keys():
		if not present.has(key):
			_free(key)

	_queue = _queue.filter(func(key: Vector3i) -> bool: return present.has(key))

	for key: Vector3i in present:
		if _built.get(key) != present[key] and not _queue.has(key):
			_queue.append(key)

	_sort_queue()


## Build every queued chunk now.
func flush() -> void:
	while not _queue.is_empty():
		_build_next()


## How many chunk meshes this node draws. For a test.
func chunk_count() -> int:
	return _nodes.size()


## The mesh node of one chunk, or null. For a test.
func chunk_node(chunk_coord: Vector2i, plane: int) -> MeshInstance3D:
	return _nodes.get(Vector3i(chunk_coord.x, chunk_coord.y, plane))


func _process(_delta: float) -> void:
	for _count: int in BUILDS_PER_FRAME:
		if _queue.is_empty():
			return

		_build_next()


## Key -> ChunkFile of every chunk of every plane in the model.
func _present_chunks() -> Dictionary:
	var present := {}

	for plane: int in _state.planes_held():
		var plane_set := _state.plane_chunks(plane)

		for coord: Vector2i in plane_set.chunk_coords():
			present[Vector3i(coord.x, coord.y, plane)] = plane_set.get_chunk(coord)

	return present


## The plane of the player first, then the nearest chunk.
func _sort_queue() -> void:
	var own := _state.current_plane
	var home := ChunkSet.chunk_of_tile(_state.current_cell)

	_queue.sort_custom(func(a: Vector3i, b: Vector3i) -> bool:
		var a_rank := _rank(a, own, home)
		var b_rank := _rank(b, own, home)

		return a_rank < b_rank)


static func _rank(key: Vector3i, own: int, home: Vector2i) -> int:
	var other_plane := 0 if key.z == own else 1
	var distance := maxi(absi(key.x - home.x), absi(key.y - home.y))

	return other_plane * 1000 + distance * 10 + key.z


func _build_next() -> void:
	var key: Vector3i = _queue.pop_front()
	var chunk := _state.plane_chunks(key.z).get_chunk(Vector2i(key.x, key.y))

	if chunk != null:
		_build(key, chunk)


func _build(key: Vector3i, chunk: ChunkFile) -> void:
	_free(key)

	var node := MeshInstance3D.new()

	node.name = "Chunk_%d_%d_p%d" % [key.x, key.y, key.z]
	node.mesh = ChunkMeshBuilder.build(chunk)
	node.material_override = _material
	node.visible = _plane_shows(key.z)

	# The water surface is a child, so it hides with the roof of its plane.
	var water := WaterMeshBuilder.build(chunk)

	if water.get_surface_count() > 0:
		var surface := MeshInstance3D.new()

		surface.name = "Water"
		surface.mesh = water
		surface.material_override = _material
		node.add_child(surface)

	add_child(node)
	_nodes[key] = node
	_built[key] = chunk


func _free(key: Vector3i) -> void:
	var node: Node = _nodes.get(key)

	if node != null:
		remove_child(node)
		node.queue_free()

	_nodes.erase(key)
	_built.erase(key)


func _on_room_changed() -> void:
	_refresh_visibility()
	_sort_queue()


func _refresh_visibility() -> void:
	for key: Vector3i in _nodes:
		_nodes[key].visible = _plane_shows(key.z)


## False for a plane above the player while roofs hide. Off the tile world,
## every plane shows.
func _plane_shows(plane: int) -> bool:
	if not _hide_roofs or _state == null or _state.current_plane < 0:
		return true

	return plane <= _state.current_plane
