class_name EntityRoster
extends RefCounted
## The entities that the feed says are near the observer, one row per id.
##
## ## Why a model, not the pool
##
## Until 09/28/2026 the 3D pane read the four entity channels itself, and the
## rows lived only in [EntityPool]. The minimap could not draw a dot, because
## no model outside the 3D scene held a row (handoff debt "the minimap draws no
## entities"). This class is that model. The CONSOLE feeds it, as it feeds
## [WorldState], so the client parses each entity message one time for both
## panes.
##
## ## The pool keeps its own routes
##
## [EntityPool] animates an add, a batch, and a full replace in different
## ways. So this class re-emits each message as its own signal, and
## [WorldView] forwards each one to the same pool call as before. A pane that
## wants only the current rows, as the minimap does, connects [signal changed]
## and reads [method rows].
##
## ## One row per id
##
## The rule of [method EntityPool._index_of]: a later announcement of an id
## replaces the earlier one. The rows are keyed by id, so a duplicate cannot
## exist here.

const _Const := preload("res://autoload/blackout_constants.gd")

## `room_players`: the whole list, on arrival and on resync.
signal replaced(entities: Array)

## `room_players_delta`: one batch of arrivals and departures.
signal delta(added: Array, removed: Array)

## `room_add_player`: one arrival.
signal added(entity: Dictionary)

## `room_remove_player`: one departure.
signal removed(entity_id: int)

## After any of the four. The rows are already current when it fires.
signal changed

## int id -> the row as the feed sent it.
var _rows := {}


## Put one feed message into this model. Returns true when the channel is one
## of the four entity channels, so the console routes with no second list.
func ingest(channel: String, payload: Dictionary) -> bool:
	match channel:
		_Const.CH_ROOM_PLAYERS:
			var entities: Array = payload.get("entities", [])
			_replace(entities)
			replaced.emit(entities)

		_Const.CH_ROOM_PLAYERS_DELTA:
			var arrived: Array = payload.get("added", [])
			var departed: Array = payload.get("removed", [])
			_apply_delta(arrived, departed)
			delta.emit(arrived, departed)

		_Const.CH_PLAYER_ADD:
			var entity: Dictionary = payload.get("entity", {})
			_upsert(entity)
			added.emit(entity)

		_Const.CH_PLAYER_REMOVE:
			var entity_id := int(payload.get("entity_id", 0))
			_rows.erase(entity_id)
			removed.emit(entity_id)

		_:
			return false

	changed.emit()

	return true


## Every row, in no fixed order.
func rows() -> Array:
	return _rows.values()


## The row of one id, or an empty dictionary.
func row(entity_id: int) -> Dictionary:
	return _rows.get(entity_id, {})


## The tile of a row, from its `coords`, or null for a row with no usable
## coords. JSON gives floats, so this makes ints one time here.
static func tile_of(entity: Dictionary) -> Variant:
	var coords: Array = entity.get("coords", [])

	if coords.size() < 2:
		return null

	return Vector2i(int(coords[0]), int(coords[1]))


## The room Z of a row, or "" for a row with no Z.
static func z_of(entity: Dictionary) -> String:
	var coords: Array = entity.get("coords", [])

	if coords.size() < 3:
		return ""

	return str(coords[2])


func _replace(entities: Array) -> void:
	_rows.clear()

	for entity in entities:
		if entity is Dictionary:
			_upsert(entity)


func _apply_delta(arrived: Array, departed: Array) -> void:
	# int() on each id: JSON gives every number as a float.
	for entity_id in departed:
		_rows.erase(int(entity_id))

	for entity in arrived:
		if entity is Dictionary:
			_upsert(entity)


func _upsert(entity: Dictionary) -> void:
	if entity.is_empty():
		return

	_rows[int(entity.get("id", 0))] = entity
