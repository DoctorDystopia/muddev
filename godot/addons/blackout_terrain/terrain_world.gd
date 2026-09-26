@tool
class_name TerrainWorld
extends Node3D
## The terrain that the editor shows: a 3 x 3 block of chunks around
## [member centre_chunk], read from and written to the world chunk files.
##
## The scene holds no terrain data (DESIGN-0011 section 6.3). Every mesh here
## is made at load and has no owner, so a scene save stores none of it. The
## chunk files are the only store. The plugin saves them on Ctrl+S.
##
## ## Why the neighbours load
##
## A brush at a chunk edge writes the shared corners to both chunks. Thus the
## eight neighbours load with the centre, and the author edits across a seam
## as if no seam were there. Only the outer edge of the block is locked: its
## corners also belong to chunks that are not loaded. The border of the block
## shows red. Move [member centre_chunk] to edit past it.
##
## ## A file that does not read
##
## A chunk file that exists but does not read stays out of the block, and
## [member load_errors] names it. The editor never draws a blank chunk in its
## place. A blank chunk there would overwrite the file on the next save.

signal block_loaded
signal chunks_saved(names: PackedStringArray)

const _Const := preload("res://autoload/blackout_constants.gd")

## How many chunks the block reaches from the centre in each direction.
const BLOCK_REACH := 1

## The chunk at the centre of the block. A move saves the changed chunks of
## the old block first, so no edit is lost.
@export var centre_chunk := Vector2i.ZERO:
	set(value):
		if is_inside_tree() and has_unsaved_changes():
			save_block()

		centre_chunk = value

		if is_inside_tree():
			load_block()

## The plane of every chunk in the block.
@export_range(0, 3) var plane := 0

## Where the chunk files are, as an OS path. Empty means the world chunk
## directory, `blackout/world/chunks/`. A test sets a scratch directory here.
@export var chunk_directory := ""

## Draw the walk flags and the walls.
@export var show_flags := true:
	set(value):
		show_flags = value
		_refresh_visibility()

## Draw the area tint. It is built only while it shows: it costs one height
## read for each tile corner.
@export var show_areas := false:
	set(value):
		show_areas = value

		if is_inside_tree():
			rebuild_all()

var chunks := ChunkSet.new()

## Each chunk file of the block that exists but does not read, with the reason.
var load_errors := PackedStringArray()

## Chunk coordinate to `{ground, flags, areas, border, objects}` nodes.
var _views := {}

var _ground_material: StandardMaterial3D
var _overlay_material: StandardMaterial3D
var _ring: MeshInstance3D
var _block_outline: MeshInstance3D

## Chunks to redraw on the next frame. A brush dab queues its chunks here, so
## many dabs in one frame cost one redraw.
var _pending := {}


func _ready() -> void:
	_ground_material = StandardMaterial3D.new()
	_ground_material.vertex_color_use_as_albedo = true
	_ground_material.roughness = 1.0
	_overlay_material = TerrainOverlay.material()
	_ring = MeshInstance3D.new()
	_ring.material_override = _overlay_material
	add_child(_ring)
	load_block()


# ─── Loading and saving ─────────────────────────────────────────────────────

## Every chunk coordinate of the block.
func block_coords() -> Array[Vector2i]:
	var coords: Array[Vector2i] = []

	for dy: int in range(-BLOCK_REACH, BLOCK_REACH + 1):
		for dx: int in range(-BLOCK_REACH, BLOCK_REACH + 1):
			coords.append(centre_chunk + Vector2i(dx, dy))

	return coords


func chunk_path(chunk_coord: Vector2i) -> String:
	var file_name := _Const.CHUNK_FILE_TEMPLATE.format(
		{"cx": chunk_coord.x, "cy": chunk_coord.y, "plane": plane})

	return directory().path_join(file_name)


func directory() -> String:
	if chunk_directory.is_empty():
		return ChunkFile.world_directory()

	return chunk_directory


## Read the block from disk. Unsaved changes are lost. The setter of
## [member centre_chunk] saves them first.
func load_block() -> void:
	chunks = ChunkSet.new()
	load_errors = PackedStringArray()

	for coord: Vector2i in block_coords():
		var chunk := _read_or_blank(coord)

		if chunk != null:
			chunks.add(chunk)

	rebuild_all()
	block_loaded.emit()


func _read_or_blank(coord: Vector2i) -> ChunkFile:
	var path := chunk_path(coord)

	if not FileAccess.file_exists(path):
		return ChunkFile.blank(coord.x, coord.y, plane)

	var chunk := ChunkFile.read_file(path)

	if not chunk.error.is_empty():
		load_errors.append("%s: %s" % [path.get_file(), chunk.error])
		return null

	return chunk


func has_unsaved_changes() -> bool:
	return not chunks.dirty_coords().is_empty()


## Write every changed chunk to its file. Returns the names of the files.
func save_block() -> PackedStringArray:
	var saved := PackedStringArray()

	DirAccess.make_dir_recursive_absolute(directory())

	for coord: Vector2i in chunks.dirty_coords():
		var chunk := chunks.get_chunk(coord)
		var path := chunk_path(coord)

		chunk.compact_names()

		if chunk.write_file(path) == OK:
			chunks.mark_clean(coord)
			saved.append(path.get_file())
		else:
			push_error("Terrain: cannot write %s" % path)

	chunks_saved.emit(saved)

	return saved


# ─── Drawing ────────────────────────────────────────────────────────────────

func rebuild_all() -> void:
	for coord: Vector2i in _views.keys():
		_free_view(coord)

	for coord: Vector2i in chunks.chunk_coords():
		rebuild(coord)

	_rebuild_block_outline()


## The outer edge of the block, in the colour of a locked border.
func _rebuild_block_outline() -> void:
	if _block_outline != null:
		_block_outline.queue_free()

	var size: int = _Const.CHUNK_SIZE
	var low := (centre_chunk - Vector2i.ONE * BLOCK_REACH) * size
	var tiles := (2 * BLOCK_REACH + 1) * size

	_block_outline = _mesh_node(TerrainOverlay.outline_mesh(chunks, low, tiles,
		TerrainOverlay.COLOR_LOCKED), _overlay_material)


## Rebuild the ground and the marks of one chunk.
func rebuild(chunk_coord: Vector2i) -> void:
	var chunk := chunks.get_chunk(chunk_coord)

	if chunk == null:
		return

	_free_view(chunk_coord)

	var view := {
		"ground": _mesh_node(ChunkMeshBuilder.build(chunk), _ground_material),
		"flags": _mesh_node(TerrainOverlay.flag_mesh(chunks, chunk_coord),
			_overlay_material),
		"areas": _mesh_node(_area_mesh_if_shown(chunk_coord), _overlay_material),
		"border": _mesh_node(TerrainOverlay.outline_mesh(chunks,
			chunk_coord * _Const.CHUNK_SIZE, _Const.CHUNK_SIZE,
			TerrainOverlay.COLOR_BORDER), _overlay_material),
		"objects": _object_markers(chunk),
	}

	_views[chunk_coord] = view
	_refresh_visibility()


func _area_mesh_if_shown(chunk_coord: Vector2i) -> ArrayMesh:
	if not show_areas:
		return null

	return TerrainOverlay.area_mesh(chunks, chunk_coord)


## Redraw these chunks on the next frame.
func queue_rebuild(coords: Array[Vector2i]) -> void:
	for coord: Vector2i in coords:
		_pending[coord] = true


func _process(_delta: float) -> void:
	if _pending.is_empty():
		return

	var coords: Array[Vector2i] = []

	coords.assign(_pending.keys())
	_pending.clear()
	rebuild_many(coords)


func rebuild_many(coords: Array[Vector2i]) -> void:
	for coord: Vector2i in coords:
		rebuild(coord)

	_rebuild_block_outline()


func _mesh_node(mesh: ArrayMesh, material: Material) -> MeshInstance3D:
	var node := MeshInstance3D.new()

	node.mesh = mesh
	node.material_override = material
	add_child(node)

	return node


func _object_markers(chunk: ChunkFile) -> Node3D:
	var holder := Node3D.new()

	add_child(holder)

	for thing: Dictionary in chunk.global_objects():
		holder.add_child(_marker(thing))

	return holder


func _marker(thing: Dictionary) -> Node3D:
	var point := Vector2(thing["x"], thing["y"])
	var base := TerrainOverlay.ground_point(chunks, point, 0.0)
	var box := BoxMesh.new()
	var paint := StandardMaterial3D.new()
	var node := MeshInstance3D.new()
	var label := Label3D.new()

	box.size = Vector3.ONE * TerrainOverlay.MARKER_SIZE
	paint.albedo_color = TerrainOverlay.kind_color(thing["kind"])
	node.mesh = box
	node.material_override = paint
	node.position = base + Vector3.UP * TerrainOverlay.MARKER_SIZE * 0.5
	node.rotation.y = -thing["rotation"] * PI * 0.5
	label.text = thing["kind"]
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = Vector3.UP * TerrainOverlay.MARKER_SIZE * 1.4
	label.pixel_size = 0.004
	node.add_child(label)

	return node


func _free_view(chunk_coord: Vector2i) -> void:
	var view: Dictionary = _views.get(chunk_coord, {})

	for node: Node in view.values():
		node.queue_free()

	_views.erase(chunk_coord)


func _refresh_visibility() -> void:
	for view: Dictionary in _views.values():
		view["flags"].visible = show_flags


## Show the brush ring at `centre`, a point in tile space, or hide it.
func show_ring(centre: Variant, radius: float) -> void:
	if _ring == null:
		return

	if centre == null:
		_ring.visible = false
		return

	_ring.mesh = TerrainOverlay.ring_mesh(chunks, centre, radius)
	_ring.visible = true


# ─── Undo and redo ──────────────────────────────────────────────────────────

## Apply an edit forward (redo) or back (undo), and redraw what it touched.
## The editor history calls this.
func replay_edit(edit: TerrainEdit, forward: bool) -> void:
	edit.replay(chunks, forward)
	rebuild_many(edit.chunk_coords())
