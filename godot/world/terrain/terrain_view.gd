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
## [WaterMeshBuilder]. A chunk with a wall flag gets a "Walls" child: the slabs
## of [WallMeshBuilder]. A chunk with a ladder, stairs, or a hatch gets a
## "Props" child: the plain shapes of [PropMeshBuilder], until they get art.
##
## ## Scenery
##
## A chunk object whose kind stands nothing up on the server is not an entity,
## so no `room_players` row draws it. The server names a model for such a kind
## in [code]OBJECT_KIND_SCENERY[/code], and this node stands that model on the
## tile, in a "Scenery" child. The transition pad is the first. The pick
## ignores scenery, as it ignores the ground mesh: a click on the pad is a
## click on its tile.
##
## Scenery takes the policy of [method MeshResolver.resolve_scenery]: no art,
## no model. The first ask starts a fetch, and [signal MeshResolver.refreshed]
## stands the model when it arrives.
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

## How much of a tile a scenery model covers. The same value as the tile props
## of the xyzgrid maps: the transition pad reads as a pad only when it reaches
## the edges of its tile.
const SCENERY_SCALE := 0.9

## The name of the scenery child of a chunk node.
const SCENERY_NODE := "Scenery"

## The name of the child that draws the primitive scenery of a chunk.
const PROPS_NODE := "Props"

const _Const := preload("res://autoload/blackout_constants.gd")

## The world model, bound by the world pane.
var _state: WorldState

## The mesh source of the scenery, bound by the world pane. Null in a test and
## in the terrain editor: then no scenery draws.
var _meshes: MeshResolver

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


## Stand scenery models on the tiles of their objects, now and on each build.
func bind_meshes(resolver: MeshResolver) -> void:
	_meshes = resolver
	_meshes.refreshed.connect(_on_art_arrived)

	for key: Vector3i in _nodes:
		_place_scenery(key)


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


## The scenery models of one chunk, or an empty list. For a test.
func scenery_of(chunk_coord: Vector2i, plane: int) -> Array[Node]:
	var node := chunk_node(chunk_coord, plane)

	if node == null or not node.has_node(SCENERY_NODE):
		return []

	return node.get_node(SCENERY_NODE).get_children()


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

	# The water and the walls are children, so they hide with the roof of
	# their plane.
	_add_layer(node, "Water", WaterMeshBuilder.build(chunk))
	_add_layer(node, "Walls", WallMeshBuilder.build(chunk))
	_add_layer(node, PROPS_NODE, PropMeshBuilder.build(chunk))

	add_child(node)
	_nodes[key] = node
	_built[key] = chunk
	_place_scenery(key)


## Add `mesh` as a child of a chunk node, when it has a surface.
func _add_layer(node: MeshInstance3D, layer_name: String, mesh: ArrayMesh) -> void:
	if mesh.get_surface_count() == 0:
		return

	var layer := MeshInstance3D.new()

	layer.name = layer_name
	layer.mesh = mesh
	layer.material_override = _material
	node.add_child(layer)


## Stand the scenery of one built chunk again, in a new "Scenery" child.
func _place_scenery(key: Vector3i) -> void:
	var node: Node = _nodes.get(key)

	if node == null or _meshes == null:
		return

	var old := node.get_node_or_null(SCENERY_NODE)

	if old != null:
		node.remove_child(old)
		old.queue_free()

	var holder := Node3D.new()
	var chunk: ChunkFile = _built[key]

	holder.name = SCENERY_NODE
	node.add_child(holder)

	for thing: Dictionary in chunk.objects:
		var asset_key: String = _Const.OBJECT_KIND_SCENERY.get(thing["kind"], "")

		# The "Props" child draws a primitive. No model record has its key.
		if asset_key in _Const.SCENERY_PRIMITIVES:
			continue

		var model := _meshes.resolve_scenery(asset_key)

		if model != null:
			holder.add_child(model)
			_stand(model, chunk, thing)


## Put a scenery model on the ground of its tile, turned as its object.
##
## A normalised model fills the unit box on its LONGEST axis only. The pad is
## far flatter than it is wide, so the scaled copy is measured to rest it ON
## the ground, not through it.
static func _stand(model: Node3D, chunk: ChunkFile, thing: Dictionary) -> void:
	var lx: int = thing["x"]
	var ly: int = thing["y"]
	var world_x := chunk.cx * _Const.CHUNK_SIZE + lx
	var world_y := chunk.cy * _Const.CHUNK_SIZE + ly
	var ground := ChunkMeshBuilder.surface_height(chunk, lx + 0.5, ly + 0.5) \
		* ChunkMeshBuilder.HEIGHT_STEP

	model.scale = Vector3.ONE * SCENERY_SCALE

	var bounds := ModelLoader.bounds_of(model)

	model.position = Vector3(world_x * ChunkMeshBuilder.TILE_SIZE,
		ground - bounds.position.y * SCENERY_SCALE,
		-world_y * ChunkMeshBuilder.TILE_SIZE)
	model.rotation.y = -int(thing["rotation"]) * PI * 0.5


## Art for a scenery key arrived: stand it on every chunk that names it.
func _on_art_arrived(asset_key: String) -> void:
	for key: Vector3i in _nodes:
		var chunk: ChunkFile = _built[key]

		for thing: Dictionary in chunk.objects:
			if _Const.OBJECT_KIND_SCENERY.get(thing["kind"], "") == asset_key:
				_place_scenery(key)
				break


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
