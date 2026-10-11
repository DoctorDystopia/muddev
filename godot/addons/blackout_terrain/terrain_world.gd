@tool
class_name TerrainWorld
extends Node3D
## The terrain that the editor shows: a 4 x 4 block of chunks around
## [member centre_chunk], on every plane. The world chunk files are its store.
##
## A block with an even side has no middle chunk. Thus the centre chunk is
## the south-west chunk of the middle four. The block reaches
## [constant BLOCK_BELOW] chunks west and south of it, and two east and north.
##
## The scene holds no terrain data (DESIGN-0011 section 6.3). Every mesh here
## is made at load and has no owner, so a scene save stores none of it. The
## chunk files are the only store. The plugin saves them on Ctrl+S.
##
## ## Why the neighbours load
##
## A brush at a chunk edge writes the shared corners to both chunks. Thus the
## neighbours load with the centre, and the author edits across a seam
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
## ## Planes (Phase 7c, DESIGN-0013 Phase S0)
##
## The block holds every plane at one time: one [ChunkSet] for each plane,
## from [method chunks_on]. A room on plane 0 and its level on plane 1 are
## one Build gesture, and one undo entry. [member plane] picks the plane to
## edit, and [member chunks] is its set. A change of [member plane] reads no
## file and saves nothing. It keeps every unsaved edit and the undo history.
##
## The planes below the edited plane show as a dim ghost, so the author
## builds a floor over the ground. [member upper_planes] picks how the planes
## above show. A plane other than the edited one shows only its chunks that
## exist: a file, or an edit.
##
## A plane-1 chunk with no file starts from the chunk below: its heights plus
## [constant NEW_PLANE_RISE], every tile void and Blocked, and the areas of
## the chunk below (Nick, 09/26/2026). A floor paint on a void tile clears
## Blocked ([method TerrainBrushes.flags_after_floor]). Like a blank chunk of
## plane 0, a new chunk is saved only after an edit. Until then,
## [method refresh_new_chunks] makes it again from the chunk below, so a
## sculpt of the ground moves the new chunks above it.
##
## A new chunk on any plane then takes each corner that it shares with a
## neighbour that exists. A file or an edit exists. Outside the block, only a
## file counts. Thus the first edit of a new chunk saves no seam fault.
##
## ## Selection, links, and water
##
## [member selected] is the object that the Select tool picked. A tall beacon
## marks it, or the tile of a finding of "Check world". The links show where
## each transition and each climb leads. [WaterMeshBuilder] draws the water
## surface, [WallMeshBuilder] draws the walls, and [PropMeshBuilder] draws
## the ladders, the stairs, and the hatches, as in the client. A nose on the
## front of each object marker shows its rotation.
##
## A wall meets the plane above when that tile of the plane above has a
## floor (DESIGN-0013 section 6.3). Thus a redraw of a chunk also redraws the
## chunk under it. [member walls_down] draws every wall low, so the author
## sees into a room.
##
## ## The structure workbench (DESIGN-0013 Phase S6)
##
## `structure_workbench.tscn` holds this node with [member chunk_directory]
## set to [constant WORKBENCH_DIRECTORY]. The author builds a template there,
## on flat blank ground, away from the world. Every tool works as in the
## world, and a save writes only the scratch files. [method writes_world]
## tells the two apart. [method clear_workbench] deletes the scratch files,
## and it refuses the world chunk directory.
##
## ## Models
##
## [TerrainModels] stands the real model of each object that has one: the
## entity that the kind stands up, or its scenery. The model turns with the
## object, as in the game. Its marker then draws no box, so the model shows.
## The nose and the label stay. [member show_models] turns the models off.

signal block_loaded
signal plane_changed
signal chunks_saved(names: PackedStringArray)

const _Const := preload("res://autoload/blackout_constants.gd")

## How the planes above the edited plane show.
enum UpperPlanes { HIDDEN, GHOST, SOLID }

## How many chunks are on each side of the block.
const BLOCK_SIDE := 4

## How many chunks the block reaches west and south of the centre chunk.
## The block reaches `BLOCK_SIDE - 1 - BLOCK_BELOW` chunks east and north.
const BLOCK_BELOW := 1

## The height steps between a plane and a new chunk of the plane above: two
## tiles (Nick, 09/26/2026). The Build tools use the same rise for a level.
const NEW_PLANE_RISE := 32

## The colour factor of the ghost of another plane.
const GHOST_SHADE := Color(0.45, 0.45, 0.5)

## The chunk directory of the structure workbench (DESIGN-0013 Phase S6). It
## is outside the repo, so git never sees a scratch chunk.
const WORKBENCH_DIRECTORY := "user://structure_workbench"

## The file name pattern of a chunk file: the prefix and the suffix.
const CHUNK_FILE_PREFIX := "chunk_"
const CHUNK_FILE_SUFFIX := ".json"

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

## The edited plane. A change reads and saves nothing. See the class comment.
@export_range(0, 3) var plane := 0:
	get:
		return _plane
	set(value):
		move_block(_centre, value)

## Where the chunk files are: an OS path, or a `user://` or `res://` path.
## Empty means the world chunk directory, `blackout/world/chunks/`. A test
## sets a scratch directory here. The structure workbench sets
## [constant WORKBENCH_DIRECTORY].
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
		_redraw()

## Draw where each transition and each climb leads.
@export var show_links := true:
	set(value):
		show_links = value

		if is_inside_tree():
			_rebuild_links()

## Draw the model of each object that has one. See the class comment.
@export var show_models := true:
	set(value):
		show_models = value
		_redraw()

## Draw the planes below the edited plane, dim.
@export var show_lower_planes := true:
	set(value):
		show_lower_planes = value
		_redraw()

## How the planes above the edited plane show.
@export var upper_planes := UpperPlanes.HIDDEN:
	set(value):
		upper_planes = value
		_redraw()

## Draw every wall low, so the author sees into a room. The walls of the
## game do not change.
@export var walls_down := false:
	set(value):
		walls_down = value
		_redraw()

## The set of the edited plane.
var chunks: ChunkSet:
	get:
		return _planes[_plane]

## Each chunk file of the block that exists but does not read, with the reason.
var load_errors := PackedStringArray()

## The object that the Select tool picked: `{tile, kind, rotation, text}`, or
## empty.
var selected := {}

var _centre := Vector2i.ZERO
var _plane := 0

## One [ChunkSet] for each plane, indexed by plane.
var _planes: Array[ChunkSet] = []

## (cx, cy, plane) of each chunk of the block that came from a file, or that
## a save wrote. A chunk with no key here is new.
var _from_file := {}

## (cx, cy, plane) of a chunk next to the block, to its file as read, or to
## null for no file. [method _seal] reads each one time for each load.
var _outside := {}

## True after the first load. Before it, a move only records the block.
var _block_ready := false

## (cx, cy, plane) to `{ground, water, walls, props, ...}` nodes. A view of
## the edited plane also has flags, areas, border, objects, and models.
var _views := {}

var _ground_material: StandardMaterial3D
var _ghost_material: StandardMaterial3D
var _overlay_material: StandardMaterial3D
var _ring: MeshInstance3D
var _marks: MeshInstance3D
var _outline: MeshInstance3D
var _beacon: MeshInstance3D
var _block_outline: MeshInstance3D
var _links: Node3D

## The model source. Made on the first draw with [member show_models] on.
var _models: TerrainModels

## Chunks to redraw on the next frame, as (cx, cy, plane). A brush dab queues
## its chunks here, so many dabs in one frame cost one redraw.
var _pending := {}


func _init() -> void:
	for each_plane: int in _plane_range():
		_planes.append(_new_set(each_plane))


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
	_marks = MeshInstance3D.new()
	_marks.material_override = _overlay_material
	add_child(_marks)
	_outline = MeshInstance3D.new()
	_outline.material_override = _overlay_material
	add_child(_outline)
	_beacon = _make_beacon()
	add_child(_beacon)
	load_block()


func _exit_tree() -> void:
	if _models != null:
		_models.release()
		_models = null


static func _plane_range() -> Array:
	return range(_Const.TILE_GROUND_PLANE, _Const.CHUNK_PLANE_MAX + 1)


static func _new_set(on_plane: int) -> ChunkSet:
	var chunk_set := ChunkSet.new()

	chunk_set.plane = on_plane

	return chunk_set


# ─── Planes ─────────────────────────────────────────────────────────────────

## The set of `on_plane`, or null for a plane out of range.
func chunks_on(on_plane: int) -> ChunkSet:
	if on_plane < _Const.TILE_GROUND_PLANE or on_plane > _Const.CHUNK_PLANE_MAX:
		return null

	return _planes[on_plane]


## Plane to [ChunkSet], for [method TerrainEdit.replay_planes].
func plane_sets() -> Dictionary:
	var sets := {}

	for chunk_set: ChunkSet in _planes:
		sets[chunk_set.plane] = chunk_set

	return sets


## True when the chunk at `chunk_coord` of `on_plane` is a file or an edit.
func chunk_exists(chunk_coord: Vector2i, on_plane: int) -> bool:
	var key := Vector3i(chunk_coord.x, chunk_coord.y, on_plane)

	return _from_file.has(key) or _planes[on_plane].is_dirty(chunk_coord)


## Make each new chunk above the ground again from the chunk below it, as it
## is now. A chunk with a file or an edit keeps its data.
func refresh_new_chunks() -> void:
	for on_plane: int in range(_Const.TILE_GROUND_PLANE + 1, _Const.CHUNK_PLANE_MAX + 1):
		var chunk_set := _planes[on_plane]

		for coord: Vector2i in chunk_set.chunk_coords():
			if not chunk_exists(coord, on_plane):
				chunk_set.add(upper_chunk(_below(coord, on_plane), on_plane))

		_seal_new_chunks(on_plane)


func _set_plane(new_plane: int) -> void:
	if new_plane == _plane:
		return

	_plane = new_plane
	selected = {}
	refresh_new_chunks()
	rebuild_all()
	plane_changed.emit()


# ─── Loading and saving ─────────────────────────────────────────────────────

## Move the block to `centre`, and edit `new_plane`. A move to another centre
## saves the changed chunks of the old block first, and loads the new one. A
## change of the plane only loads nothing. See the class comment.
func move_block(centre: Vector2i, new_plane: int) -> void:
	var clamped := clampi(new_plane, _Const.TILE_GROUND_PLANE, _Const.CHUNK_PLANE_MAX)

	if centre == _centre and _block_ready:
		_set_plane(clamped)
		return

	if is_inside_tree() and has_unsaved_changes():
		save_block()

	_centre = centre
	_plane = clamped
	selected = {}

	if is_inside_tree():
		load_block()


## Every chunk coordinate of the block.
func block_coords() -> Array[Vector2i]:
	var coords: Array[Vector2i] = []
	var low := block_low()

	for dy: int in BLOCK_SIDE:
		for dx: int in BLOCK_SIDE:
			coords.append(low + Vector2i(dx, dy))

	return coords


## The south-west chunk of the block.
func block_low() -> Vector2i:
	return _centre - Vector2i.ONE * BLOCK_BELOW


## True when `tile` is in the loaded block.
func block_has_tile(tile: Vector2i) -> bool:
	var offset := ChunkSet.chunk_of_tile(tile) - block_low()

	return offset.x >= 0 and offset.x < BLOCK_SIDE \
		and offset.y >= 0 and offset.y < BLOCK_SIDE


## The path of a chunk file. `on_plane` -1 means the edited plane.
func chunk_path(chunk_coord: Vector2i, on_plane: int = -1) -> String:
	var file_plane := _plane if on_plane < 0 else on_plane
	var file_name := _Const.CHUNK_FILE_TEMPLATE.format(
		{"cx": chunk_coord.x, "cy": chunk_coord.y, "plane": file_plane})

	return directory().path_join(file_name)


## The chunk directory as an OS path. See [member chunk_directory].
func directory() -> String:
	if chunk_directory.is_empty():
		return ChunkFile.world_directory()

	return ProjectSettings.globalize_path(chunk_directory)


## True when this node edits the world chunk files. False for the structure
## workbench and for a test.
func writes_world() -> bool:
	return same_directory(directory(), ChunkFile.world_directory())


## True when the OS paths `first` and `second` name one directory. Windows
## does not read the case of a path, so the test does not either.
static func same_directory(first: String, second: String) -> bool:
	return _directory_key(first) == _directory_key(second)


static func _directory_key(path: String) -> String:
	var key := path.replace("\\", "/").simplify_path().trim_suffix("/")

	if OS.get_name() == "Windows":
		key = key.to_lower()

	return key


static func _is_chunk_file(file_name: String) -> bool:
	return file_name.begins_with(CHUNK_FILE_PREFIX) and file_name.ends_with(CHUNK_FILE_SUFFIX)


# ─── The structure workbench ────────────────────────────────────────────────

## Delete every chunk file of a scratch directory, and load the block again:
## flat, blank ground. Unsaved edits go too. Returns the number of files
## deleted, or -1 with no change when this node edits the world: the world
## chunk files are never scratch.
func clear_workbench() -> int:
	if writes_world():
		push_error("Terrain: the world chunk files are not a workbench. Nothing deleted.")
		return -1

	var deleted := 0

	if DirAccess.dir_exists_absolute(directory()):
		for file_name: String in DirAccess.get_files_at(directory()):
			if _is_chunk_file(file_name) \
					and DirAccess.remove_absolute(directory().path_join(file_name)) == OK:
				deleted += 1

	selected = {}

	if is_inside_tree():
		load_block()

	return deleted


## Read the block from disk, every plane. Unsaved changes are lost.
## [method move_block] saves them first.
func load_block() -> void:
	load_errors = PackedStringArray()
	_from_file.clear()
	_outside.clear()

	# The ground first: a new chunk above starts from the chunk below.
	for on_plane: int in _plane_range():
		_planes[on_plane] = _new_set(on_plane)

		for coord: Vector2i in block_coords():
			var chunk := _read_or_new(coord, on_plane)

			if chunk != null:
				_planes[on_plane].add(chunk)

		_seal_new_chunks(on_plane)

	_block_ready = true
	rebuild_all()
	block_loaded.emit()


func _read_or_new(coord: Vector2i, on_plane: int) -> ChunkFile:
	var path := chunk_path(coord, on_plane)

	if not FileAccess.file_exists(path):
		return new_chunk(coord, on_plane)

	var chunk := ChunkFile.read_file(path)

	if not chunk.error.is_empty():
		load_errors.append("%s: %s" % [path.get_file(), chunk.error])
		return null

	_from_file[Vector3i(coord.x, coord.y, on_plane)] = true

	return chunk


## The chunk that the editor starts where no file exists. Plane 0 is flat and
## blank. A plane above starts from the chunk below it, as it is in memory.
func new_chunk(coord: Vector2i, on_plane: int) -> ChunkFile:
	if on_plane <= _Const.TILE_GROUND_PLANE:
		return ChunkFile.blank(coord.x, coord.y, on_plane)

	return upper_chunk(_below(coord, on_plane), on_plane)


## The chunk under `coord` of `on_plane`. A chunk below that does not read
## counts as new.
func _below(coord: Vector2i, on_plane: int) -> ChunkFile:
	var below := _planes[on_plane - 1].get_chunk(coord)

	if below != null:
		return below

	return new_chunk(coord, on_plane - 1)


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


# ─── Seams of a new chunk ───────────────────────────────────────────────────

## Give each new chunk of `on_plane` the shared corners of each neighbour that
## exists. A new chunk follows the chunk below it. A saved neighbour on the
## same plane does not. Without this step, the first edit of the new chunk
## saves a seam fault, and `test_chunkfile.py` fails (10/09/2026).
func _seal_new_chunks(on_plane: int) -> void:
	var chunk_set := _planes[on_plane]

	for coord: Vector2i in chunk_set.chunk_coords():
		if not chunk_exists(coord, on_plane):
			_seal(chunk_set.get_chunk(coord), on_plane)


## Copy into `chunk` each corner that it shares with a neighbour that exists.
## The eight neighbours count, the corner ones too.
func _seal(chunk: ChunkFile, on_plane: int) -> void:
	var coord := Vector2i(chunk.cx, chunk.cy)

	for dy: int in [-1, 0, 1]:
		for dx: int in [-1, 0, 1]:
			var step := Vector2i(dx, dy)

			if step == Vector2i.ZERO:
				continue

			var neighbour := _existing_neighbour(coord + step, on_plane)

			if neighbour != null:
				copy_shared_corners(chunk, neighbour, step)


## Copy the corners that `chunk` shares with `neighbour`, which is `step`
## chunks away. A side neighbour shares one edge. A corner neighbour shares
## one corner.
static func copy_shared_corners(chunk: ChunkFile, neighbour: ChunkFile,
		step: Vector2i) -> void:
	var size: int = _Const.CHUNK_SIZE
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE
	var low := (step * size).max(Vector2i.ZERO)
	var high := (step * size + Vector2i(size, size)).min(Vector2i(size, size))

	for y: int in range(low.y, high.y + 1):
		for x: int in range(low.x, high.x + 1):
			var there := Vector2i(x, y) - step * size

			chunk.heights[y * side + x] = neighbour.heights[there.y * side + there.x]


## The neighbour at `coord` of `on_plane` when it is a file or an edit, else
## null. A chunk outside the block counts only as a file on disk.
func _existing_neighbour(coord: Vector2i, on_plane: int) -> ChunkFile:
	var block := Rect2i(block_low(), Vector2i(BLOCK_SIDE, BLOCK_SIDE))

	if block.has_point(coord):
		if chunk_exists(coord, on_plane):
			return _planes[on_plane].get_chunk(coord)

		return null

	var key := Vector3i(coord.x, coord.y, on_plane)

	if not _outside.has(key):
		_outside[key] = _read_outside(coord, on_plane)

	return _outside[key]


## The file at `coord` of `on_plane`, or null when none reads.
func _read_outside(coord: Vector2i, on_plane: int) -> ChunkFile:
	var path := chunk_path(coord, on_plane)

	if not FileAccess.file_exists(path):
		return null

	var chunk := ChunkFile.read_file(path)

	if not chunk.error.is_empty():
		return null

	return chunk


func has_unsaved_changes() -> bool:
	for chunk_set: ChunkSet in _planes:
		if not chunk_set.dirty_coords().is_empty():
			return true

	return false


## Write every changed chunk of every plane to its file. Returns the names of
## the files.
func save_block() -> PackedStringArray:
	var saved := PackedStringArray()

	DirAccess.make_dir_recursive_absolute(directory())

	for chunk_set: ChunkSet in _planes:
		for coord: Vector2i in chunk_set.dirty_coords():
			var chunk := chunk_set.get_chunk(coord)
			var path := chunk_path(coord, chunk_set.plane)

			chunk.compact_names()

			if chunk.write_file(path) == OK:
				chunk_set.mark_clean(coord)
				_from_file[Vector3i(coord.x, coord.y, chunk_set.plane)] = true
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
	var names := PackedStringArray()

	# A new structure workbench has no directory until its first save.
	if DirAccess.dir_exists_absolute(directory()):
		names = DirAccess.get_files_at(directory())

	for file_name: String in names:
		if not _is_chunk_file(file_name):
			continue

		var chunk := ChunkFile.read_file(directory().path_join(file_name))

		if chunk.error.is_empty():
			found[Vector3i(chunk.cx, chunk.cy, chunk.plane)] = chunk
		else:
			errors.append("%s: %s" % [file_name, chunk.error])

	for chunk_set: ChunkSet in _planes:
		for coord: Vector2i in chunk_set.chunk_coords():
			var key := Vector3i(coord.x, coord.y, chunk_set.plane)

			if found.has(key) or chunk_set.is_dirty(coord):
				found[key] = chunk_set.get_chunk(coord)

	var files: Array[ChunkFile] = []

	files.assign(found.values())

	return files


# ─── Drawing ────────────────────────────────────────────────────────────────

func _redraw() -> void:
	if is_inside_tree() and _block_ready:
		rebuild_all()


func rebuild_all() -> void:
	for key: Vector3i in _views.keys():
		_free_view(key)

	for chunk_set: ChunkSet in _planes:
		for coord: Vector2i in chunk_set.chunk_coords():
			_rebuild_key(Vector3i(coord.x, coord.y, chunk_set.plane))

	_rebuild_block_outline()
	_rebuild_links()


## The outer edge of the block, in the colour of a locked border.
func _rebuild_block_outline() -> void:
	if _block_outline != null:
		_block_outline.queue_free()

	var size: int = _Const.CHUNK_SIZE
	var low := block_low() * size
	var tiles := BLOCK_SIDE * size

	_block_outline = _mesh_node(TerrainOverlay.outline_mesh(chunks, low, tiles,
		TerrainOverlay.COLOR_LOCKED), _overlay_material)


## Rebuild the view of one chunk of one plane, as (cx, cy, plane).
func _rebuild_key(key: Vector3i) -> void:
	_free_view(key)

	var coord := Vector2i(key.x, key.y)
	var chunk := _planes[key.z].get_chunk(coord)

	if chunk == null:
		return

	if key.z == _plane:
		_views[key] = _edited_view(chunk, coord)
		_refresh_visibility()
		return

	var material := _plane_material(key.z)

	if material == null or not chunk_exists(coord, key.z):
		return

	_views[key] = _plain_view(chunk, key.z, material)


## The ground, the water, the walls, and the props of a chunk of another
## plane, in `material`.
func _plain_view(chunk: ChunkFile, on_plane: int, material: Material) -> Dictionary:
	var coord := Vector2i(chunk.cx, chunk.cy)

	return {
		"ground": _mesh_node(ChunkMeshBuilder.build(chunk), material),
		"water": _mesh_node(WaterMeshBuilder.build(chunk), material),
		"walls": _mesh_node(_walls_mesh(chunk, coord, on_plane), material),
		"props": _mesh_node(PropMeshBuilder.build(chunk), material),
	}


## The full view of a chunk of the edited plane: the meshes, the marks, and
## the objects.
func _edited_view(chunk: ChunkFile, coord: Vector2i) -> Dictionary:
	var view := {
		"ground": _mesh_node(ChunkMeshBuilder.build(chunk), _ground_material),
		"water": _mesh_node(WaterMeshBuilder.build(chunk), _ground_material),
		"walls": _mesh_node(_walls_mesh(chunk, coord, _plane), _ground_material),
		"props": _mesh_node(PropMeshBuilder.build(chunk), _ground_material),
		"flags": _mesh_node(TerrainOverlay.flag_mesh(chunks, coord),
			_overlay_material),
		"areas": _mesh_node(_area_mesh_if_shown(coord), _overlay_material),
		"border": _mesh_node(TerrainOverlay.outline_mesh(chunks,
			coord * _Const.CHUNK_SIZE, _Const.CHUNK_SIZE,
			TerrainOverlay.COLOR_BORDER), _overlay_material),
	}

	var nodes := _object_nodes(chunk)

	view["objects"] = nodes[0]
	view["models"] = nodes[1]

	return view


## The walls of a chunk: low with [member walls_down], else each wall meets
## the plane above where it has a floor.
func _walls_mesh(chunk: ChunkFile, coord: Vector2i, on_plane: int) -> ArrayMesh:
	if walls_down:
		return WallMeshBuilder.build(chunk, null, true)

	var above_set := chunks_on(on_plane + 1)
	var above: ChunkFile = null if above_set == null else above_set.get_chunk(coord)

	return WallMeshBuilder.build(chunk, above)


## The material of a plane other than the edited one, or null when it does
## not show.
func _plane_material(on_plane: int) -> Material:
	if on_plane < _plane:
		return _ghost_material if show_lower_planes else null

	match upper_planes:
		UpperPlanes.GHOST:
			return _ghost_material
		UpperPlanes.SOLID:
			return _ground_material

	return null


func _area_mesh_if_shown(chunk_coord: Vector2i) -> ArrayMesh:
	if not show_areas:
		return null

	return TerrainOverlay.area_mesh(chunks, chunk_coord)


## Redraw these chunks, as (cx, cy, plane), on the next frame.
func queue_rebuild(keys: Array[Vector3i]) -> void:
	for key: Vector3i in keys:
		_pending[key] = true


func _process(_delta: float) -> void:
	if _pending.is_empty():
		return

	var keys: Array[Vector3i] = []

	keys.assign(_pending.keys())
	_pending.clear()
	rebuild_many(keys)


## Redraw these chunks, as (cx, cy, plane), and the chunk under each: its
## walls meet the plane above.
func rebuild_many(keys: Array[Vector3i]) -> void:
	var all := {}

	for key: Vector3i in keys:
		all[key] = true

		if key.z > _Const.TILE_GROUND_PLANE:
			all[key - Vector3i(0, 0, 1)] = true

	for key: Vector3i in all:
		_rebuild_key(key)

	_rebuild_block_outline()
	_rebuild_links()
	_check_selection()


func _mesh_node(mesh: ArrayMesh, material: Material) -> MeshInstance3D:
	var node := MeshInstance3D.new()

	node.mesh = mesh
	node.material_override = material
	add_child(node)

	return node


## The marker holder and the model holder of one chunk. A marker of an
## object with a model draws no box.
func _object_nodes(chunk: ChunkFile) -> Array[Node3D]:
	var markers := Node3D.new()
	var models := Node3D.new()

	add_child(markers)
	add_child(models)

	for thing: Dictionary in chunk.global_objects():
		var model := _model_for(thing)
		var marker := _marker(thing)

		if model != null:
			models.add_child(model)
			marker.mesh = null

		markers.add_child(marker)

	return [markers, models]


func _model_for(thing: Dictionary) -> Node3D:
	if not show_models:
		return null

	if _models == null:
		_models = TerrainModels.for_repo()

	return _models.stand(chunks, thing)


## The view of one chunk of the edited plane, or an empty Dictionary.
func _edited_view_of(chunk_coord: Vector2i) -> Dictionary:
	return _views.get(Vector3i(chunk_coord.x, chunk_coord.y, _plane), {})


## The models of one chunk of the block, or an empty list. For a test.
func models_of(chunk_coord: Vector2i) -> Array[Node]:
	var view := _edited_view_of(chunk_coord)

	if view.is_empty():
		return []

	return view["models"].get_children()


## The marker of one object: a box in the colour of its kind, a nose on the
## front face, and a label. A box looks the same at every quarter turn, so
## the nose shows the rotation. At rotation 0 it points north, as the front of
## a scenery model and of a [PropMeshBuilder] shape.
func _marker(thing: Dictionary) -> MeshInstance3D:
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
	var view := _edited_view_of(chunk_coord)

	if view.is_empty():
		return []

	return view["objects"].get_children()


## The wall mesh that one chunk of `on_plane` draws now, or null. For a test.
func walls_of(chunk_coord: Vector2i, on_plane: int) -> ArrayMesh:
	var view: Dictionary = _views.get(Vector3i(chunk_coord.x, chunk_coord.y, on_plane), {})

	if view.is_empty():
		return null

	return view["walls"].mesh


func _free_view(key: Vector3i) -> void:
	var view: Dictionary = _views.get(key, {})

	for node: Node in view.values():
		node.queue_free()

	_views.erase(key)


func _refresh_visibility() -> void:
	for view: Dictionary in _views.values():
		if view.has("flags"):
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


## Show the marks of a Build tool: `paths` as [method TerrainOverlay.path_mesh]
## takes them. An empty list hides them.
func show_marks(paths: Array, color: Color) -> void:
	if _marks == null:
		return

	_marks.visible = not paths.is_empty()

	if _marks.visible:
		_marks.mesh = TerrainOverlay.path_mesh(chunks, paths, color)


## Show the outline of a Build plan: the lattice of
## [method TerrainOverlay.lattice_mesh]. An empty `heights` hides it.
func show_outline(heights: Dictionary, color: Color) -> void:
	if _outline == null:
		return

	show_outline_layers([heights], color)


## Show the outline of several maps of [method show_outline] at one time:
## one for each plane of a template copy. An empty list hides it.
func show_outline_layers(layers: Array, color: Color) -> void:
	if _outline == null:
		return

	var corners := 0

	for heights: Dictionary in layers:
		corners += heights.size()

	_outline.visible = corners > 0

	if _outline.visible:
		_outline.mesh = TerrainOverlay.lattice_layers_mesh(layers, color)


## How many chunks of the other planes show. For a test.
func ghost_count() -> int:
	var count := 0

	for key: Vector3i in _views:
		if key.z != _plane:
			count += 1

	return count


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

## Every object of the edited plane of the block as
## `{tile, kind, rotation, text}`, south row first.
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
func select(tile: Vector2i, kind: String, turn: int, text: String = "") -> void:
	selected = {"tile": tile, "kind": kind, "rotation": turn, "text": text}
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


## Show the block and the plane of `tile` of `on_plane`, and mark the tile.
## A tile out of the block loads its block. Selects the first object there,
## if any.
func jump_to(tile: Vector2i, on_plane: int) -> void:
	if not block_has_tile(tile):
		move_block(ChunkSet.chunk_of_tile(tile), on_plane)
	else:
		move_block(_centre, on_plane)

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
## The editor history calls this. Each change goes into the set of its own
## plane, so the edited plane does not matter. Returns false, and changes
## nothing, for an edit of another block: its tiles are not these chunks.
func replay_edit(edit: TerrainEdit, forward: bool) -> bool:
	if edit.centre != _centre:
		push_warning("Terrain: the undo entry belongs to block %s. " % edit.centre
			+ "Load that block to undo it.")
		return false

	edit.replay_planes(plane_sets(), forward)
	rebuild_many(edit.chunk_keys())

	return true
