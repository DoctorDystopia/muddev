class_name TerrainEdit
extends RefCounted
## One undoable edit of the terrain: every change of one brush stroke or one
## Build gesture.
##
## The plugin records each change here as it applies it. At the end of the
## stroke, the edit goes into the editor history as one entry. Undo applies
## each `before`, and redo applies each `after`.
##
## Only the FIRST `before` of a key is kept. A stroke raises one corner many
## times, and undo must return it to its height before the stroke.
##
## A change keeps a floor, an area, and a wall style as a NAME, not as an
## index. An index belongs to the name list of one chunk, and
## [method ChunkSet.set_floor] may add a name.
##
## ## Keys
##
## A change keys on (x, y, plane). The x and y name a world corner or a
## world tile. The plane is the plane of its [ChunkSet]
## ([member ChunkSet.plane]). One Build gesture writes several planes: a
## room on plane 0 and its level on plane 1 (DESIGN-0013 Phase S0). The edit
## replays each change into the set of its own plane. Thus a change of the
## edited plane does not move an undo.
##
## The edit still records its block. [method TerrainWorld.replay_edit]
## refuses it on another block, because its tiles are not loaded there.

const LAYER_HEIGHTS := "heights"
const LAYER_FLAGS := "flags"
const LAYER_FLOORS := "floors"
const LAYER_AREAS := "areas"
const LAYER_WALL_STYLES := "walls"

## Layer name to `{Vector3i(x, y, plane): [before, after]}`. A height key is
## a world corner. A tile layer key is a world tile.
var _layers := {}

## Each object change, in order:
## `[added (bool), tile, kind, rotation, text, plane]`.
var _objects: Array = []

## The centre chunk of the block of this edit.
var centre := Vector2i.ZERO


## A new edit of the block that `world` shows now.
static func for_world(world: TerrainWorld) -> TerrainEdit:
	var edit := TerrainEdit.new()

	edit.centre = world.centre_chunk

	return edit


func is_empty() -> bool:
	return _layers.is_empty() and _objects.is_empty()


## The number of changed corners and tiles, and object changes.
func size() -> int:
	var total := _objects.size()

	for layer: String in _layers:
		total += _layers[layer].size()

	return total


## The chunks that this edit touches, as (cx, cy, plane). The world rebuilds
## their meshes.
func chunk_keys() -> Array[Vector3i]:
	var found := {}

	for layer: String in _layers:
		for key: Vector3i in _layers[layer]:
			var at := Vector2i(key.x, key.y)

			if layer == LAYER_HEIGHTS:
				for owner: Vector2i in ChunkSet.corner_owners(at):
					found[Vector3i(owner.x, owner.y, key.z)] = true
			else:
				var home := ChunkSet.chunk_of_tile(at)

				found[Vector3i(home.x, home.y, key.z)] = true

	for change: Array in _objects:
		var home := ChunkSet.chunk_of_tile(change[1])

		found[Vector3i(home.x, home.y, change[5])] = true

	var keys: Array[Vector3i] = []

	keys.assign(found.keys())

	return keys


## The tiles that this edit touches, as (x, y, plane): each changed tile and
## each tile of an object change. A height change touches no tile here.
func tiles() -> Array[Vector3i]:
	var found := {}

	for layer: String in _layers:
		if layer != LAYER_HEIGHTS:
			for key: Vector3i in _layers[layer]:
				found[key] = true

	for change: Array in _objects:
		found[Vector3i(change[1].x, change[1].y, change[5])] = true

	var touched: Array[Vector3i] = []

	touched.assign(found.keys())

	return touched


## The planes that this edit touches.
func planes() -> Array[int]:
	var found := {}

	for key: Vector3i in chunk_keys():
		found[key.z] = true

	var touched: Array[int] = []

	touched.assign(found.keys())

	return touched


# ─── Recording ──────────────────────────────────────────────────────────────

## Record and apply `{corner: height}`, the result of a [TerrainBrushes] call.
func apply_heights(chunks: ChunkSet, changes: Dictionary) -> void:
	for corner: Vector2i in changes:
		_note(LAYER_HEIGHTS, _key(corner, chunks), chunks.get_corner(corner),
			changes[corner])
		chunks.set_corner(corner, changes[corner])


func apply_flags(chunks: ChunkSet, tile: Vector2i, flags: int) -> void:
	_note(LAYER_FLAGS, _key(tile, chunks), chunks.get_flags(tile), flags)
	chunks.set_flags(tile, flags)


func apply_floor(chunks: ChunkSet, tile: Vector2i, floor_name: String) -> void:
	_note(LAYER_FLOORS, _key(tile, chunks), chunks.get_floor(tile), floor_name)
	chunks.set_floor(tile, floor_name)


func apply_area(chunks: ChunkSet, tile: Vector2i, area_name: String) -> void:
	_note(LAYER_AREAS, _key(tile, chunks), chunks.get_area(tile), area_name)
	chunks.set_area(tile, area_name)


func apply_wall_style(chunks: ChunkSet, tile: Vector2i, style: String) -> void:
	_note(LAYER_WALL_STYLES, _key(tile, chunks), chunks.get_wall_style(tile), style)
	chunks.set_wall_style(tile, style)


func add_object(chunks: ChunkSet, tile: Vector2i, kind: String,
		rotation: int, text: String = "") -> void:
	_objects.append([true, tile, kind, rotation, text, chunks.plane])
	chunks.add_object(tile, kind, rotation, text)


func remove_object(chunks: ChunkSet, tile: Vector2i, kind: String,
		rotation: int, text: String = "") -> void:
	if chunks.remove_object(tile, kind, rotation, text):
		_objects.append([false, tile, kind, rotation, text, chunks.plane])


static func _key(at: Vector2i, chunks: ChunkSet) -> Vector3i:
	return Vector3i(at.x, at.y, chunks.plane)


func _note(layer: String, key: Vector3i, before: Variant, after: Variant) -> void:
	if not _layers.has(layer):
		_layers[layer] = {}

	var changes: Dictionary = _layers[layer]

	if changes.has(key):
		changes[key][1] = after
	else:
		changes[key] = [before, after]


# ─── Undo and redo ──────────────────────────────────────────────────────────

## Apply every `after` (redo) or every `before` (undo) to one set. The replay
## skips each change of another plane. For an edit of one plane, as in a test.
func replay(chunks: ChunkSet, forward: bool) -> void:
	replay_planes({chunks.plane: chunks}, forward)


## Apply every `after` (redo) or every `before` (undo). `sets` maps a plane to
## its [ChunkSet]. The replay skips a change of a plane with no set.
func replay_planes(sets: Dictionary, forward: bool) -> void:
	var side := 1 if forward else 0

	for layer: String in _layers:
		var changes: Dictionary = _layers[layer]

		for key: Vector3i in changes:
			var chunks: ChunkSet = sets.get(key.z)

			if chunks != null:
				_write(chunks, layer, Vector2i(key.x, key.y), changes[key][side])

	_replay_objects(sets, forward)


func _write(chunks: ChunkSet, layer: String, at: Vector2i, value: Variant) -> void:
	match layer:
		LAYER_HEIGHTS:
			chunks.set_corner(at, value)
		LAYER_FLAGS:
			chunks.set_flags(at, value)
		LAYER_FLOORS:
			chunks.set_floor(at, value)
		LAYER_AREAS:
			chunks.set_area(at, value)
		LAYER_WALL_STYLES:
			chunks.set_wall_style(at, value)


## Objects replay in order for redo, and in reverse with each change undone
## for undo.
func _replay_objects(sets: Dictionary, forward: bool) -> void:
	var order := _objects.duplicate()

	if not forward:
		order.reverse()

	for change: Array in order:
		var chunks: ChunkSet = sets.get(change[5])

		if chunks == null:
			continue

		if change[0] == forward:
			chunks.add_object(change[1], change[2], change[3], change[4])
		else:
			chunks.remove_object(change[1], change[2], change[3], change[4])
