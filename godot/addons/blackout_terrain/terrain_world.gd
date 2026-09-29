@tool
class_name TerrainWorld
extends Node3D
## The terrain that the editor shows: a 3 x 3 block of chunks of one plane
## around [member centre_chunk], read from and written to the world chunk
## files.
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
##
## ## Planes (Phase 7c)
##
## [member plane] picks the plane to edit. The planes below it show as a dim
## ghost, so the author builds a floor over the ground. A plane-1 chunk with
## no file starts from the chunk below: its heights plus
## [constant NEW_PLANE_RISE], every tile void and Blocked, and the areas of
## the chunk below (Nick, 09/26/2026). A floor paint on a void tile clears
## Blocked ([method TerrainBrushes.flags_after_floor]). Like a blank chunk of
## plane 0, a new chunk is saved only after an edit.
##
## ## Selection, links, and water
##
## [member selected] is the object that the Select tool picked. A tall beacon
## marks it, or the tile of a finding of "Check world". The links show where
## each transition and each climb leads. [WaterMeshBuilder] draws the water
## surface, [WallMeshBuilder] draws the walls, and [PropMeshBuilder] draws
## the ladders, the stairs, and the hatches, as in the client. A nose on the
## front of each object marker shows its rotation.

signal block_loaded
signal chunks_saved(names: PackedStringArray)

const _Const := preload("res://autoload/blackout_constants.gd")

## How many chunks the block reaches from the centre in each direction.
const BLOCK_REACH := 1

## The height steps between a plane and a new chunk of the plane above: two
## tiles (Nick, 09/26/2026).
const NEW_PLANE_RISE := 32

## The colour factor of the ghost of a lower plane.
const GHOST_SHADE := Color(0.45, 0.45, 0.5)

## The beacon over a selected object or a finding.
const BEACON_SIZE := Vector3(0.12, 4.0, 0.12)
const BEACON_COLOR := Color(1.0, 0.3, 1.0)

## The nose of an object marker shows its front. These give the side of the
## nose over the side of the marker, the colour, and the node name.
const MARKER_NOSE_SCALE := 0.4
const MARKER_NOSE_COLOR := Color(1.0, 1.0, 1.0)
const MARKER_NOSE_NODE := "Nose"

## The chunk at the centre of the block. A move saves the changed chunks of
## the old block first, so no edit is lost.
@export var centre_chunk := Vector2i.ZERO:
	get:
		return _centre
	set(value):
		move_block(value, _plane)

## The plane of every chunk in the block. A change saves first, as a move.
@export_range(0, 3) var plane := 0:
	get:
		return _plane
	set(value):
		move_block(_centre, value)

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

## Draw where each transition and each climb leads.
@export var show_links := true:
	set(value):
		show_links = value

		if is_inside_tree():
			_rebuild_links()

## Draw the planes below the edited plane, dim.
@export var show_lower_planes := true:
	set(value):
		show_lower_planes = value

		if _ghosts != null:
			_ghosts.visible = value

var chunks := ChunkSet.new()

## Each chunk file of the block that exists but does not read, with the reason.
var load_errors := PackedStringArray()

## The object that the Select tool picked: `{tile, kind, rotation, text}`, or
## empty.
var selected := {}

var _centre := Vector2i.ZERO
var _plane := 0

## Chunk coordinate to `{ground, water, flags, areas, border, objects}` nodes.
var _views := {}

var _ground_material: StandardMaterial3D
var _ghost_material: StandardMaterial3D
var _overlay_material: StandardMaterial3D
var _ring: MeshInstance3D
var _beacon: MeshInstance3D
var _block_outline: MeshInstance3D
var _ghosts: Node3D
var _links: Node3D

## Chunks to redraw on the next frame. A brush dab queues its chunks here, so
## many dabs in one frame cost one redraw.
var _pending := {}


func _ready() -> void:
	_ground_material = StandardMaterial3D.new()
	_ground_material.vertex_color_use_as_albedo = true
	_ground_material.roughness = 1.0
	_ghost_material = _ground_material.duplicate()
	_ghost_material.albedo_color = GHOST_SHADE
	_overlay_material = TerrainOverlay.material()
	_ring = MeshInstance3D.new()
	_ring.material_override = _overlay_material
	add_child(_ring)
	_beacon = _make_beacon()
	add_child(_beacon)
	load_block()


# ─── Loading and saving ─────────────────────────────────────────────────────

## Move the block to `centre` on `new_plane`, and load it. The changed chunks
## of the old block are saved first. One load, not two, for a jump that
## changes both.
func move_block(centre: Vector2i, new_plane: int) -> void:
	if is_inside_tree() and has_unsaved_changes():
		save_block()

	_centre = centre
	_plane = clampi(new_plane, _Const.TILE_GROUND_PLANE, _Const.CHUNK_PLANE_MAX)
	selected = {}

	if is_inside_tree():
		load_block()


## Every chunk coordinate of the block.
func block_coords() -> Array[Vector2i]:
	var coords: Array[Vector2i] = []

	for dy: int in range(-BLOCK_REACH, BLOCK_REACH + 1):
		for dx: int in range(-BLOCK_REACH, BLOCK_REACH + 1):
			coords.append(_centre + Vector2i(dx, dy))

	return coords


## True when `tile` is in the loaded block.
func block_has_tile(tile: Vector2i) -> bool:
	var home := ChunkSet.chunk_of_tile(tile)

	return absi(home.x - _centre.x) <= BLOCK_REACH \
		and absi(home.y - _centre.y) <= BLOCK_REACH


## The path of a chunk file. `on_plane` -1 means the edited plane.
func chunk_path(chunk_coord: Vector2i, on_plane: int = -1) -> String:
	var file_plane := _plane if on_plane < 0 else on_plane
	var file_name := _Const.CHUNK_FILE_TEMPLATE.format(
		{"cx": chunk_coord.x, "cy": chunk_coord.y, "plane": file_plane})

	return directory().path_join(file_name)


func directory() -> String:
	if chunk_directory.is_empty():
		return ChunkFile.world_directory()

	return chunk_directory


## Read the block from disk. Unsaved changes are lost. [method move_block]
## saves them first.
func load_block() -> void:
	chunks = ChunkSet.new()
	load_errors = PackedStringArray()

	for coord: Vector2i in block_coords():
		var chunk := _read_or_new(coord)

		if chunk != null:
			chunks.add(chunk)

	rebuild_all()
	_rebuild_ghosts()
	block_loaded.emit()


func _read_or_new(coord: Vector2i) -> ChunkFile:
	var path := chunk_path(coord)

	if not FileAccess.file_exists(path):
		return new_chunk(coord, _plane)

	var chunk := ChunkFile.read_file(path)

	if not chunk.error.is_empty():
		load_errors.append("%s: %s" % [path.get_file(), chunk.error])
		return null

	return chunk


## The chunk that the editor starts where no file exists. Plane 0 is flat and
## blank. A plane above starts from the chunk below it.
func new_chunk(coord: Vector2i, on_plane: int) -> ChunkFile:
	if on_plane <= _Const.TILE_GROUND_PLANE:
		return ChunkFile.blank(coord.x, coord.y, on_plane)

	return upper_chunk(_chunk_on(coord, on_plane - 1), on_plane)


## The chunk file of `coord` on `on_plane`, or the chunk the editor would
## start there. A file that does not read counts as missing.
func _chunk_on(coord: Vector2i, on_plane: int) -> ChunkFile:
	var path := chunk_path(coord, on_plane)

	if FileAccess.file_exists(path):
		var chunk := ChunkFile.read_file(path)

		if chunk.error.is_empty():
			return chunk

	return new_chunk(coord, on_plane)


## A new chunk over `below`, on `on_plane`: the heights of `below` plus
## [constant NEW_PLANE_RISE], every tile void and Blocked, and the areas of
## `below`, so the fog does not change on a climb.
static func upper_chunk(below: ChunkFile, on_plane: int) -> ChunkFile:
	var chunk := ChunkFile.blank(below.cx, below.cy, on_plane)

	for index: int in chunk.heights.size():
		chunk.heights[index] = clampi(below.heights[index] + NEW_PLANE_RISE,
			_Const.CHUNK_HEIGHT_MIN, _Const.CHUNK_HEIGHT_MAX)

	chunk.floor_names = PackedStringArray([_Const.TILE_VOID_FLOOR])
	chunk.flags.fill(_Const.TILE_FLAG_BLOCKED)
	chunk.area_names = below.area_names.duplicate()
	chunk.areas = below.areas.duplicate()

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


## Every chunk of the world, of every plane, as the author has it now: the
## files on disk, with each chunk of the block in place of its file. A new
## chunk of the block counts only after an edit, as for a save. For "Check
## world". Each file that does not read goes into `errors`.
func world_chunk_files(errors: PackedStringArray) -> Array[ChunkFile]:
	var found := {}

	for file_name: String in DirAccess.get_files_at(directory()):
		if not (file_name.begins_with("chunk_") and file_name.ends_with(".json")):
			continue

		var chunk := ChunkFile.read_file(directory().path_join(file_name))

		if chunk.error.is_empty():
			found[Vector3i(chunk.cx, chunk.cy, chunk.plane)] = chunk
		else:
			errors.append("%s: %s" % [file_name, chunk.error])

	for coord: Vector2i in chunks.chunk_coords():
		var key := Vector3i(coord.x, coord.y, _plane)

		if found.has(key) or chunks.dirty_coords().has(coord):
			found[key] = chunks.get_chunk(coord)

	var files: Array[ChunkFile] = []

	files.assign(found.values())

	return files


# ─── Drawing ────────────────────────────────────────────────────────────────

func rebuild_all() -> void:
	for coord: Vector2i in _views.keys():
		_free_view(coord)

	for coord: Vector2i in chunks.chunk_coords():
		rebuild(coord)

	_rebuild_block_outline()
	_rebuild_links()


## The outer edge of the block, in the colour of a locked border.
func _rebuild_block_outline() -> void:
	if _block_outline != null:
		_block_outline.queue_free()

	var size: int = _Const.CHUNK_SIZE
	var low := (_centre - Vector2i.ONE * BLOCK_REACH) * size
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
		"water": _mesh_node(WaterMeshBuilder.build(chunk), _ground_material),
		"walls": _mesh_node(WallMeshBuilder.build(chunk), _ground_material),
		"props": _mesh_node(PropMeshBuilder.build(chunk), _ground_material),
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
	_rebuild_links()
	_check_selection()


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


## The marker of one object: a box in the colour of its kind, a nose on the
## front face, and a label. A box looks the same at every quarter turn, so
## the nose shows the rotation. At rotation 0 it points north, as the front of
## a scenery model and of a [PropMeshBuilder] shape.
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
	node.add_child(_marker_nose())
	label.text = _marker_text(thing)
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = Vector3.UP * TerrainOverlay.MARKER_SIZE * 1.4
	label.pixel_size = 0.004
	node.add_child(label)

	return node


## The nose of a marker: a small box that sticks out of its front face.
static func _marker_nose() -> MeshInstance3D:
	var nose := MeshInstance3D.new()
	var box := BoxMesh.new()
	var paint := StandardMaterial3D.new()
	var size := TerrainOverlay.MARKER_SIZE * MARKER_NOSE_SCALE

	box.size = Vector3.ONE * size
	paint.albedo_color = MARKER_NOSE_COLOR
	paint.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	nose.name = MARKER_NOSE_NODE
	nose.mesh = box
	nose.material_override = paint
	nose.position = Vector3.FORWARD * (TerrainOverlay.MARKER_SIZE + size) * 0.5

	return nose


## The label of a marker: the kind, and the words of a sign.
static func _marker_text(thing: Dictionary) -> String:
	var text: String = thing.get("text", "")

	if text.is_empty():
		return thing["kind"]

	return "%s\n\"%s\"" % [thing["kind"], text]


## The object markers of one chunk of the block, or an empty list. For a
## test.
func markers_of(chunk_coord: Vector2i) -> Array[Node]:
	var view: Dictionary = _views.get(chunk_coord, {})

	if view.is_empty():
		return []

	return view["objects"].get_children()


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


# ─── The planes below ───────────────────────────────────────────────────────

## Draw each chunk file of each plane below the edited plane, dim. Only files
## that exist: a plane that is not built yet shows nothing.
func _rebuild_ghosts() -> void:
	if _ghosts != null:
		_ghosts.queue_free()

	_ghosts = Node3D.new()
	_ghosts.visible = show_lower_planes
	add_child(_ghosts)

	for lower: int in range(_Const.TILE_GROUND_PLANE, _plane):
		for coord: Vector2i in block_coords():
			_add_ghost(coord, lower)


func _add_ghost(coord: Vector2i, lower: int) -> void:
	var path := chunk_path(coord, lower)

	if not FileAccess.file_exists(path):
		return

	var chunk := ChunkFile.read_file(path)

	if not chunk.error.is_empty():
		return

	# One holder for each chunk, so a new layer does not change the count.
	var holder := Node3D.new()

	_ghosts.add_child(holder)

	for mesh: ArrayMesh in [ChunkMeshBuilder.build(chunk), WaterMeshBuilder.build(chunk),
			WallMeshBuilder.build(chunk), PropMeshBuilder.build(chunk)]:
		var node := MeshInstance3D.new()

		node.mesh = mesh
		node.material_override = _ghost_material
		holder.add_child(node)


## How many ghost chunks show. For a test.
func ghost_count() -> int:
	if _ghosts == null:
		return 0

	return _ghosts.get_child_count()


# ─── Links ──────────────────────────────────────────────────────────────────

func _rebuild_links() -> void:
	if _links != null:
		_links.queue_free()

	_links = Node3D.new()
	add_child(_links)

	if not show_links:
		return

	var linked: Array[Dictionary] = []

	for thing: Dictionary in objects_in_block():
		if TerrainOverlay.has_link(thing["kind"]):
			linked.append(thing)

	if linked.is_empty():
		return

	var lines := MeshInstance3D.new()

	lines.mesh = TerrainOverlay.link_mesh(chunks, linked, _plane)
	lines.material_override = _overlay_material
	_links.add_child(lines)

	for thing: Dictionary in linked:
		for label: Label3D in TerrainOverlay.link_labels(chunks, thing, _plane):
			_links.add_child(label)


# ─── Objects and the selection ──────────────────────────────────────────────

## Every object of the block as `{tile, kind, rotation, text}`, south row
## first.
func objects_in_block() -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	for coord: Vector2i in chunks.chunk_coords():
		for thing: Dictionary in chunks.get_chunk(coord).global_objects():
			found.append({"tile": Vector2i(thing["x"], thing["y"]),
				"kind": thing["kind"], "rotation": thing["rotation"],
				"text": thing["text"]})

	found.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		if a["tile"].y != b["tile"].y:
			return a["tile"].y < b["tile"].y

		return a["tile"].x < b["tile"].x)

	return found


## Select one object. The beacon marks its tile.
func select(tile: Vector2i, kind: String, rotation: int, text: String = "") -> void:
	selected = {"tile": tile, "kind": kind, "rotation": rotation, "text": text}
	show_beacon(tile)


func clear_selection() -> void:
	selected = {}
	show_beacon(null)


## Put the beacon on `tile` of the block, or hide it with null.
func show_beacon(tile: Variant) -> void:
	if _beacon == null:
		return

	if tile == null or not chunks.has_tile(tile):
		_beacon.visible = false
		return

	var base := TerrainOverlay.ground_point(chunks, Vector2(tile), 0.0)

	_beacon.position = base + Vector3.UP * BEACON_SIZE.y * 0.5
	_beacon.visible = true


## Clear a selection that an undo or a redo took away.
func _check_selection() -> void:
	if selected.is_empty():
		return

	for thing: Dictionary in chunks.objects_at(selected["tile"]):
		if thing["kind"] == selected["kind"] \
				and thing["rotation"] == selected["rotation"] \
				and thing["text"] == selected["text"]:
			return

	clear_selection()


## Load the block that holds `tile` of `on_plane`, if it is not the loaded
## one, and mark the tile. Selects the first object there, if any.
func jump_to(tile: Vector2i, on_plane: int) -> void:
	if on_plane != _plane or not block_has_tile(tile):
		move_block(ChunkSet.chunk_of_tile(tile), on_plane)

	var here := chunks.objects_at(tile)

	if here.is_empty():
		clear_selection()
		show_beacon(tile)
		return

	select(tile, here[0]["kind"], here[0]["rotation"], here[0]["text"])


## Where the selected object leads: `{tile, plane}`, or empty when it does
## not lead anywhere. A climb leads by its first way.
func selected_link_end() -> Dictionary:
	if selected.is_empty():
		return {}

	var kind: String = selected["kind"]
	var target: Array = _Const.OBJECT_KIND_TARGETS.get(kind, [])

	if not target.is_empty():
		return {"tile": Vector2i(target[0], target[1]), "plane": _plane}

	var ways: Array = _Const.OBJECT_KIND_CLIMBS.get(kind, [])

	if ways.is_empty():
		return {}

	return {"tile": selected["tile"],
		"plane": _plane + _Const.CLIMB_PLANE_STEPS[ways[0]]}


func _make_beacon() -> MeshInstance3D:
	var node := MeshInstance3D.new()
	var box := BoxMesh.new()
	var paint := StandardMaterial3D.new()

	box.size = BEACON_SIZE
	paint.albedo_color = BEACON_COLOR
	paint.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	node.mesh = box
	node.material_override = paint
	node.visible = false

	return node


# ─── Undo and redo ──────────────────────────────────────────────────────────

## Apply an edit forward (redo) or back (undo), and redraw what it touched.
## The editor history calls this. Returns false, and changes nothing, for an
## edit of another plane or another block: its tiles are not these chunks.
func replay_edit(edit: TerrainEdit, forward: bool) -> bool:
	if edit.plane != _plane or edit.centre != _centre:
		push_warning("Terrain: the undo entry belongs to plane %d, block %s. "
			% [edit.plane, edit.centre] + "Load that block to undo it.")
		return false

	edit.replay(chunks, forward)
	rebuild_many(edit.chunk_coords())

	return true
