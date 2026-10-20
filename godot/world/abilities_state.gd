class_name AbilitiesState
extends RefCounted
## What you can do, from `char_abilities`: one row for each ability, with
## its state and the whole line that fires it.
##
## ## It knows no ability, and must not learn any
##
## Every row is whatever the server sent, in the order of the registry. A
## new aura is one file on the server, and a table of ability names here
## would be the first place that goes stale. The contract that
## [CombatOptionsState] answers for styles.
##
## ## Nothing here is set by a click
##
## The state of a row is whatever the LAST snapshot said. A click sends the
## command of the row and changes nothing locally. The republish of the
## server is what lights the row. A model that lit a row before the server
## answered would show an aura that the server refused, with nothing
## scheduled to put it right.
##
## ## The slot of a row is its index
##
## The server names no key. [AbilityKeys] maps a key to a slot, and
## [method row_at] gives the row in that slot. Thus, the first row answers
## the first key, whatever that key is on this client.
##
## **Every number in a parsed payload is a float.** None reaches this model
## today, and a `ready_at` on a later kind converts here, at the point of
## use, as [SkillsState] does it.
##
## Author: Nick Hobar
## Creation date: 10/20/2026

## Server-owned names, generated from blackout/systems/interface/statefeed/constants.py.
const _Const := preload("res://autoload/blackout_constants.gd")

## Fired when a snapshot lands, so a view redraws from one place.
signal changed

## True once char_abilities has arrived. Distinguishes "the server has said
## nothing yet" from a character that knows no ability, which is a real
## answer.
var has_data := false

## [{key, name, kind, state, command, reason, tip}] in the order of the
## server. `command` is empty on a locked row. `tip` is `{title, lines}`.
var rows: Array = []


## Fold one feed message into this model.
##
## Returns true when the payload was one of ours, so the console can route
## without restating the channel name in a second match.
func ingest(channel: String, payload: Dictionary) -> bool:
	if channel != _Const.CH_CHAR_ABILITIES:
		return false

	rows = _rows(payload.get("abilities", []))
	has_data = true

	changed.emit()

	return true


## Forget everything. Called when the socket drops, for the reason
## [method SkillsState.reset] gives.
func reset() -> void:
	has_data = false
	rows = []

	changed.emit()


## The row in one slot, or `{}` past the last row.
##
## Empty rather than null so a caller can `.get()` the result without a
## check first, the choice [method SkillsState.row_for] makes.
func row_at(slot: int) -> Dictionary:
	if slot < 0 or slot >= rows.size():
		return {}

	return rows[slot]


## The active row, or `{}` when no row is active.
func active_row() -> Dictionary:
	for row: Dictionary in rows:
		if str(row["state"]) == _Const.ABILITY_STATE_ACTIVE:
			return row

	return {}


func _rows(raw: Variant) -> Array:
	var read: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return read

	for entry: Variant in raw:
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		read.append({
			"key": str(entry.get("key", "")),
			"name": str(entry.get("name", "")),
			"kind": str(entry.get("kind", "")),
			"state": str(entry.get("state", "")),
			# The line a telnet player would type to fire this ability. The
			# SERVER names it; this client sends it verbatim.
			"command": str(entry.get("command", "")),
			"reason": str(entry.get("reason", "")),
			"tip": TipText.read(entry.get(_Const.TIP_KEY, {})),
		})

	return read
