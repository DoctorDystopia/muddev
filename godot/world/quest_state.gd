class_name QuestState
extends RefCounted
## The observer's quest log, from `char_quests`.
##
## ## It knows no quest keys and must not learn any
##
## Every row comes from whatever the server sent. Adding a quest is one file
## under `systems/quests/content/`, and a table of quest names here would be
## the place that goes stale first. So: iterate, never enumerate — the same
## contract [SummaryState] answers for panels.
##
## ## Objectives are numbers, not sentences
##
## The server sends `{key, description, current, required, counted, done}`
## rather than the rendered `[x] Rats culled 3/5` the telnet screen prints. That
## is what lets the pane draw a progress bar, and it is why this model does no
## formatting: what a client does with two integers is the view's business.
##
## `required` is 1 for a one-shot objective rather than absent, so a view can
## draw the same bar for both without a branch; `counted` is what says whether
## to show a fraction or a tickbox.
##
## **Every number in a parsed payload is a float.** `JSON.parse_string` returns
## `{"current": 3.0}` always, and `"%d/%d"` on a float is not what it looks
## like. Converted here, at the point of use, exactly as [WorldState] and
## [CharState] do it.

## Server-owned names, generated from blackout/systems/statefeed/constants.py.
const _Const := preload("res://autoload/blackout_constants.gd")

## Fired when the log lands, so a view redraws from one place.
signal changed

## True once char_quests has arrived. Distinguishes "the server has said
## nothing yet" from "you have taken no quests", which look identical and are
## not the same thing to a player who has just logged in.
var has_data := false

## [{key, title, step, step_description, objectives}, ...]
var active: Array = []

## [{key, title}, ...]
var completed: Array = []


## Fold one feed message into this model.
##
## Returns true when the payload was one of ours, so the console can route
## without restating the channel name in a second match.
func ingest(channel: String, payload: Dictionary) -> bool:
	if channel != _Const.CH_CHAR_QUESTS:
		return false

	active = _quests(payload.get("active", []))
	completed = _titles(payload.get("completed", []))
	has_data = true

	changed.emit()

	return true


## Forget everything. Called when the socket drops.
##
## The same reason [CharState] clears: a websocket close ends the Evennia
## Session, so a quest log still showing three objectives beside a dead socket
## is describing a character nobody is puppeting.
func reset() -> void:
	has_data = false
	active = []
	completed = []

	changed.emit()


## How far through one quest's current step the player is, as 0.0 to 1.0.
##
## Here rather than in the view because it is arithmetic on the payload, and a
## second pane that wanted the same number would otherwise write it again.
## Zero objectives is a step that asks for nothing, which reads as complete.
static func step_fraction(quest: Dictionary) -> float:
	var objectives: Array = quest.get("objectives", [])

	if objectives.is_empty():
		return 1.0

	var done := 0

	for objective: Dictionary in objectives:
		if bool(objective.get("done", false)):
			done += 1

	return float(done) / float(objectives.size())


func _quests(raw: Variant) -> Array:
	var rows: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return rows

	for entry: Variant in raw:
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		rows.append({
			"key": str(entry.get("key", "")),
			"title": str(entry.get("title", "")),
			"step": str(entry.get("step", "")),
			"step_description": str(entry.get("step_description", "")),
			"objectives": _objectives(entry.get("objectives", [])),
		})

	return rows


func _objectives(raw: Variant) -> Array:
	var rows: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return rows

	for entry: Variant in raw:
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		# `required` is floored at 1, so nothing downstream divides by zero.
		# The server never sends 0 -- a one-shot objective is normalised to 1
		# there -- but a view that trusted it and was wrong would show a bar
		# that is either blank or NaN, and neither says which.
		rows.append({
			"key": str(entry.get("key", "")),
			"description": str(entry.get("description", "")),
			"current": int(entry.get("current", 0)),
			"required": maxi(1, int(entry.get("required", 1))),
			"counted": bool(entry.get("counted", false)),
			"done": bool(entry.get("done", false)),
		})

	return rows


func _titles(raw: Variant) -> Array:
	var rows: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return rows

	for entry: Variant in raw:
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		rows.append({
			"key": str(entry.get("key", "")),
			"title": str(entry.get("title", "")),
		})

	return rows
