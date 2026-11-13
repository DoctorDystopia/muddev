class_name MusicState
extends RefCounted
## The music of your character, from `char_music`: the area you stand in,
## and one row for each track with its state (DESIGN-0016).
##
## ## It knows no track, and must not learn any
##
## Every row is whatever the server sent, in the order of the track table.
## A new track is one row of `world/tables/music_tracks.json` on the
## server, and a table of track names here would be the first place that
## goes stale. The contract that [AbilitiesState] answers for abilities.
##
## ## The server owns the list, the client owns the play
##
## Nothing here says which track plays. [MusicPlayer] decides that from
## these rows, the mode in [ClientSettings], and its own random source.
## A locked row never plays, whatever the mode.
##
## ## The area is a server fact
##
## `area` is the first time the server tells the client where the
## character stands. The fog keeps its own read of the chunk data, because
## the fog is a look and the music follows the unlocks, which are the
## server's.
##
## Author: Nick Hobar
## Creation date: 11/08/2026

## Server-owned names, generated from blackout/systems/interface/statefeed/constants.py.
const _Const := preload("res://autoload/blackout_constants.gd")

## Fired when a snapshot lands, so a view and the player redraw from one
## place.
signal changed

## True once char_music has arrived. Distinguishes "the server has said
## nothing yet" from a world with no track, which is a real answer.
var has_data := false

## The key of the area that the character stands in. Empty off the tile
## world, and before the first snapshot.
var area := ""

## The rows, in the order of the server. Each one is `{key, name, area,
## state, hint}`. `hint` is empty on an unlocked row.
var rows: Array = []


## Fold one feed message into this model.
##
## Returns true when the payload was one of ours, so the console can route
## without restating the channel name in a second match.
func ingest(channel: String, payload: Dictionary) -> bool:
	if channel != _Const.CH_CHAR_MUSIC:
		return false

	area = str(payload.get(_Const.MUSIC_AREA_KEY, ""))
	rows = _rows(payload.get(_Const.MUSIC_ROWS_KEY, []))
	has_data = true

	changed.emit()

	return true


## Forget everything. Called when the socket drops, for the reason
## [method SkillsState.reset] gives. The player stops on the same signal.
func reset() -> void:
	has_data = false
	area = ""
	rows = []

	changed.emit()


## The row of one key, or `{}` for a key the server did not send.
##
## Empty rather than null so a caller can `.get()` the result without a
## check first, the choice [method AbilitiesState.row_at] makes.
func row_for(key: String) -> Dictionary:
	for row: Dictionary in rows:
		if str(row["key"]) == key:
			return row

	return {}


## Whether the server says the character holds the track. False for a key
## it did not send.
func is_unlocked(key: String) -> bool:
	var row := row_for(key)

	return not row.is_empty() and str(row["state"]) == _Const.MUSIC_STATE_UNLOCKED


## Every unlocked row, in table order.
func unlocked_rows() -> Array:
	var found: Array = []

	for row: Dictionary in rows:
		if str(row["state"]) == _Const.MUSIC_STATE_UNLOCKED:
			found.append(row)

	return found


## Every unlocked row of one area, in table order.
func unlocked_rows_in(area_key: String) -> Array:
	var found: Array = []

	for row: Dictionary in unlocked_rows():
		if str(row["area"]) == area_key:
			found.append(row)

	return found


## How many rows are unlocked.
func unlocked_count() -> int:
	return unlocked_rows().size()


func _rows(raw: Variant) -> Array:
	var read: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return read

	for entry: Variant in raw:
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		read.append({
			"key": str(entry.get(_Const.MUSIC_ROW_KEY, "")),
			"name": str(entry.get(_Const.MUSIC_ROW_NAME, "")),
			"area": str(entry.get(_Const.MUSIC_ROW_AREA, "")),
			"state": str(entry.get(_Const.MUSIC_ROW_STATE, "")),
			"hint": str(entry.get(_Const.MUSIC_ROW_HINT, "")),
		})

	return read
