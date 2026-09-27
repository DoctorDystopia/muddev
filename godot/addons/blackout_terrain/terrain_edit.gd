class_name TerrainEdit
extends RefCounted
## One undoable edit of the terrain: every change of one brush stroke.
##
## The plugin records each change here as it applies it. At the end of the
## stroke, the edit goes into the editor history as one entry. Undo applies
## each `before`, and redo applies each `after`.
##
## Only the FIRST `before` of a key is kept. A stroke raises one corner many
## times, and undo must return it to its height before the stroke.
##
## A floor and an area are stored as NAMES, not indexes. An index belongs to
## one chunk's name list, and [method ChunkSet.set_floor] may add a name.
##
## An edit keys on WORLD tiles, with no plane. Thus it records the plane and
## the block that it was made on, and [method TerrainWorld.replay_edit]
## refuses it on another. Without that, an undo after a change of plane
## wrote the old stroke into the new plane (found 09/26/2026).

const LAYER_HEIGHTS := "heights"
const LAYER_FLAGS := "flags"
const LAYER_FLOORS := "floors"
const LAYER_AREAS := "areas"

## Layer name to `{key: [before, after]}`. A height key is a world corner. A
## tile layer key is a world tile.
var _layers := {}

## Each object change, in order: `[added (bool), tile, kind, rotation]`.
var _objects: Array = []

## The plane and the centre chunk of the block that this edit was made on.
var plane := 0
var centre := Vector2i.ZERO


## A new edit of the block that `world` shows now.
static func for_world(world: TerrainWorld) -> TerrainEdit:
	var edit := TerrainEdit.new()

	edit.plane = world.plane
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


## The chunks that this edit touches. The plugin rebuilds their meshes.
func chunk_coords() -> Array[Vector2i]:
	var found := {}

	for layer: String in _layers:
		for key: Vector2i in _layers[layer]:
			if layer == LAYER_HEIGHTS:
				for owner: Vector2i in ChunkSet.corner_owners(key):
					found[owner] = true
			else:
				found[ChunkSet.chunk_of_tile(key)] = true

	for change: Array in _objects:
		found[ChunkSet.chunk_of_tile(change[1])] = true

	var coords: Array[Vector2i] = []

	coords.assign(found.keys())

	return coords


# ─── Recording ──────────────────────────────────────────────────────────────

## Record and apply `{corner: height}`, the result of a [TerrainBrushes] call.
func apply_heights(chunks: ChunkSet, changes: Dictionary) -> void:
	for corner: Vector2i in changes:
		_note(LAYER_HEIGHTS, corner, chunks.get_corner(corner), changes[corner])
		chunks.set_corner(corner, changes[corner])


func apply_flags(chunks: ChunkSet, tile: Vector2i, flags: int) -> void:
	_note(LAYER_FLAGS, tile, chunks.get_flags(tile), flags)
	chunks.set_flags(tile, flags)


func apply_floor(chunks: ChunkSet, tile: Vector2i, floor_name: String) -> void:
	_note(LAYER_FLOORS, tile, chunks.get_floor(tile), floor_name)
	chunks.set_floor(tile, floor_name)


func apply_area(chunks: ChunkSet, tile: Vector2i, area_name: String) -> void:
	_note(LAYER_AREAS, tile, chunks.get_area(tile), area_name)
	chunks.set_area(tile, area_name)


func add_object(chunks: ChunkSet, tile: Vector2i, kind: String,
		rotation: int) -> void:
	_objects.append([true, tile, kind, rotation])
	chunks.add_object(tile, kind, rotation)


func remove_object(chunks: ChunkSet, tile: Vector2i, kind: String,
		rotation: int) -> void:
	if chunks.remove_object(tile, kind, rotation):
		_objects.append([false, tile, kind, rotation])


func _note(layer: String, key: Vector2i, before: Variant, after: Variant) -> void:
	if not _layers.has(layer):
		_layers[layer] = {}

	var changes: Dictionary = _layers[layer]

	if changes.has(key):
		changes[key][1] = after
	else:
		changes[key] = [before, after]


# ─── Undo and redo ──────────────────────────────────────────────────────────

## Apply every `after` (redo) or every `before` (undo).
func replay(chunks: ChunkSet, forward: bool) -> void:
	var side := 1 if forward else 0

	for layer: String in _layers:
		var changes: Dictionary = _layers[layer]

		for key: Vector2i in changes:
			_write(chunks, layer, key, changes[key][side])

	_replay_objects(chunks, forward)


func _write(chunks: ChunkSet, layer: String, key: Vector2i, value: Variant) -> void:
	match layer:
		LAYER_HEIGHTS:
			chunks.set_corner(key, value)
		LAYER_FLAGS:
			chunks.set_flags(key, value)
		LAYER_FLOORS:
			chunks.set_floor(key, value)
		LAYER_AREAS:
			chunks.set_area(key, value)


## Objects replay in order for redo, and in reverse with each change undone
## for undo.
func _replay_objects(chunks: ChunkSet, forward: bool) -> void:
	var order := _objects.duplicate()

	if not forward:
		order.reverse()

	for change: Array in order:
		var adds: bool = change[0] == forward

		if adds:
			chunks.add_object(change[1], change[2], change[3])
		else:
			chunks.remove_object(change[1], change[2], change[3])
