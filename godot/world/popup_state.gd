class_name PopupState
extends RefCounted
## The one pop-up the server has open over the world pane, from `char_popup`:
## the bank today, the shop and the crafting stations next.
##
## ## It knows no pop-up, no grid and no verb
##
## A pop-up is a title, a status line, grids of item slots, a quantity row and
## a close command, and every one of those is whatever the server sent. Adding
## a shop is one Python file on the server and no edit here. A table of pop-up
## names in this file would be the first thing to go stale, the contract
## [CombatOptionsState] states for styles.
##
## ## Nothing here is set by a click
##
## A click sends a command and changes nothing locally. The server's next
## snapshot is what moves an item out of the vault, lights a new quantity
## button, or closes the box. A model that closed itself on a click would hide
## a pop-up the server still holds open, with nothing scheduled to show it
## again.
##
## ## A snapshot, and it must stay one
##
## Every message replaces everything, for the reason [InventoryState] gives.
## The closed state arrives as a snapshot too, with `open` false.
##
## **Every number in a parsed payload is a float.** Converted here, at the point
## of use, exactly as [InventoryState] does it.

const _Const := preload("res://autoload/blackout_constants.gd")

## Fired when a snapshot lands, so a view redraws from one place.
signal changed

## True while the server holds a pop-up open.
var is_open := false

## The server's stable name for the open pop-up, for example "bank". Read by
## tests. A view must never branch on it.
var key := ""

var title := ""
var status := ""

## [{key, title, slots_total, items}] in display order. `items` is indexed:
## slot (int) -> row, and only occupied slots appear.
var grids: Array = []

## [{label, command, template, input, active}] — the 1 / 5 / 10 / X / All row.
var quantity: Array = []

## [{label, command}] — the buttons under the grids, for what the pop-up
## affords as a whole: stop a craft, collect a cure.
var footer: Array = []

## An EvMenu node, when the pop-up is a menu: the node text as BBCode the
## server escaped, the choices as [{key, label, command}], and the text box as
## {label}, or {} when the node reads no typed text. All empty for a grid.
##
## The wire field is `choices`, never `options`: Evennia reserves `options`
## as a keyword of msg(), and the socket drops it before it leaves.
var text := ""
var choices: Array = []
var input: Dictionary = {}

## The side panel of a station whose work ends later, or {}:
## {title, total, slots}, each slot {name, ready, remaining, duration}.
## `remaining` is seconds at the moment the snapshot landed.
var timers: Dictionary = {}

## When the snapshot landed, in msec, for counting `remaining` down between
## snapshots. See [method seconds_left].
var received_msec := 0

## The whole line the close button sends.
var close_command := ""


## Fold one feed message into this model.
##
## Returns true when the payload was one of ours, so the console can route
## without restating the channel name in a second match.
func ingest(channel: String, payload: Dictionary) -> bool:
	if channel != _Const.CH_CHAR_POPUP:
		return false

	is_open = bool(payload.get("open", false))
	key = str(payload.get("key", ""))
	title = str(payload.get("title", ""))
	status = str(payload.get("status", ""))
	grids = _grids(payload.get("grids", []))
	quantity = _buttons(payload.get("quantity", []))
	footer = _buttons(payload.get("actions", []))
	text = str(payload.get("text", ""))
	choices = _buttons(payload.get("choices", []))
	input = _input(payload.get("input", {}))
	timers = _timers(payload.get("timers", {}))
	received_msec = Time.get_ticks_msec()
	close_command = str(payload.get("close_command", ""))

	changed.emit()

	return true


## Forget everything. Called when the socket drops: a new session is a new
## character, and it opens nothing until the server says so.
func reset() -> void:
	is_open = false
	key = ""
	title = ""
	status = ""
	grids = []
	quantity = []
	footer = []
	text = ""
	choices = []
	input = {}
	timers = {}
	close_command = ""

	changed.emit()


## True when the pop-up is an EvMenu node rather than item grids.
func is_menu() -> bool:
	return not text.is_empty() or not choices.is_empty()


## True when the pop-up has a side panel of timed slots.
func has_timers() -> bool:
	return not timers.is_empty()


## Seconds left on one timer slot now, counted down from the snapshot. Never
## below zero. The server's next snapshot is what says `ready`. This only
## keeps the bar moving between two snapshots.
func seconds_left(slot: Dictionary, now_msec: int) -> float:
	var elapsed := float(now_msec - received_msec) / 1000.0

	return maxf(0.0, float(slot.get("remaining", 0.0)) - elapsed)


## The command a choice key sends, or "" when no choice has that key. For the
## number keys: pressing 1 is typing 1.
func option_command(option_key: String) -> String:
	for option: Dictionary in choices:
		if str(option.get("key", "")) == option_key:
			return str(option.get("command", ""))

	return ""


## The row in one slot of one grid, or an empty dictionary when it is free.
func row_at(grid_index: int, slot: int) -> Dictionary:
	if grid_index < 0 or grid_index >= grids.size():
		return {}

	var items: Dictionary = grids[grid_index]["items"]

	return items.get(slot, {})


## The action a LEFT click sends: the row's first. The server puts the active
## quantity mode there, so this client never decides what a click means.
## Empty when the row affords nothing.
static func default_action(row: Dictionary) -> Dictionary:
	var actions: Array = row.get("actions", [])

	if actions.is_empty():
		return {}

	return actions[0]


func _grids(raw: Variant) -> Array:
	var parsed: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return parsed

	for entry: Variant in raw:
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		parsed.append({
			"key": str(entry.get("key", "")),
			"title": str(entry.get("title", "")),
			"slots_total": int(entry.get("slots_total", 0)),
			"items": _index_rows(entry.get("items", [])),
		})

	return parsed


## Rows keyed by slot. The fields every row carries are converted here, in the
## shape [InventoryState] converts its own, so one slot control can draw both.
func _index_rows(raw: Variant) -> Dictionary:
	var indexed: Dictionary = {}

	if typeof(raw) != TYPE_ARRAY:
		return indexed

	for row: Variant in raw:
		if typeof(row) != TYPE_DICTIONARY:
			continue

		var copy: Dictionary = row.duplicate(true)
		copy["id"] = int(row.get("id", 0))
		copy["slot"] = int(row.get("slot", 0))
		copy["quantity"] = int(row.get("quantity", 1))
		copy["name"] = str(row.get("name", ""))
		copy["asset"] = str(row.get("asset", ""))
		copy["family"] = str(row.get("family", ""))
		copy["detail"] = str(row.get("detail", ""))
		copy["info"] = str(row.get("info", ""))
		# Absent means enabled, so a server that never sends it draws every
		# slot lit, as it did before the field existed.
		copy["enabled"] = bool(row.get("enabled", true))
		copy["actions"] = _actions(row.get("actions", []))
		indexed[copy["slot"]] = copy

	return indexed


func _actions(raw: Variant) -> Array:
	var actions: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return actions

	for entry: Variant in raw:
		if typeof(entry) == TYPE_DICTIONARY:
			actions.append(entry)

	return actions


## {title, total, slots} with every number converted, or {} for none.
func _timers(raw: Variant) -> Dictionary:
	if typeof(raw) != TYPE_DICTIONARY or raw.is_empty():
		return {}

	var slots: Array = []

	for entry: Variant in raw.get("slots", []):
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		slots.append({
			"name": str(entry.get("name", "")),
			"ready": bool(entry.get("ready", false)),
			"remaining": float(entry.get("remaining", 0.0)),
			"duration": float(entry.get("duration", 0.0)),
		})

	return {
		"title": str(raw.get("title", "")),
		"total": int(raw.get("total", slots.size())),
		"slots": slots,
	}


func _input(raw: Variant) -> Dictionary:
	if typeof(raw) != TYPE_DICTIONARY:
		return {}

	return {"label": str(raw.get("label", ""))} if not raw.is_empty() else {}


func _buttons(raw: Variant) -> Array:
	var buttons: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return buttons

	for entry: Variant in raw:
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		var button: Dictionary = entry.duplicate(true)
		button["label"] = str(entry.get("label", ""))
		button["command"] = str(entry.get("command", ""))
		button["active"] = bool(entry.get("active", false))
		buttons.append(button)

	return buttons
