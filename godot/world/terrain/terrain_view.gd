class_name TerrainView
extends Node3D
## The ground of the tile world: one mesh for each chunk that the client holds.
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

## The world model, bound by the world pane.
var _state: WorldState

## Chunk coordinate (Vector2i) -> the MeshInstance3D that draws it.
var _nodes := {}

## Chunk coordinate (Vector2i) -> the ChunkFile that its mesh shows. A chunk
## that the server sends again is a new ChunkFile, so a changed object here
## means "build again".
var _built := {}

var _material: StandardMaterial3D


func _init() -> void:
	_material = StandardMaterial3D.new()
	_material.vertex_color_use_as_albedo = true
	_material.roughness = 1.0


## Draw the chunks of this model, now and each time they change.
func bind(state: WorldState) -> void:
	_state = state
	_state.chunks_changed.connect(sync)
	sync()


## Make the meshes match the chunk set: free the meshes of chunks that went,
## and build a mesh for each chunk that is new or was sent again.
func sync() -> void:
	if _state == null:
		return

	var chunks := _state.chunks
	var present := chunks.chunk_coords()

	for coord: Vector2i in _nodes.keys():
		if not present.has(coord):
			_free(coord)

	for coord: Vector2i in present:
		var chunk := chunks.get_chunk(coord)

		if _built.get(coord) != chunk:
			_build(coord, chunk)


## How many chunk meshes this node draws. For a test.
func chunk_count() -> int:
	return _nodes.size()


func _build(coord: Vector2i, chunk: ChunkFile) -> void:
	_free(coord)

	var node := MeshInstance3D.new()

	node.name = "Chunk_%d_%d" % [coord.x, coord.y]
	node.mesh = ChunkMeshBuilder.build(chunk)
	node.material_override = _material
	add_child(node)
	_nodes[coord] = node
	_built[coord] = chunk


func _free(coord: Vector2i) -> void:
	var node: Node = _nodes.get(coord)

	if node != null:
		remove_child(node)
		node.queue_free()

	_nodes.erase(coord)
	_built.erase(coord)
