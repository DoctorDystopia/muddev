class_name SkillsState
extends RefCounted
## The observer's whole skill roster, from `char_skills`.
##
## ## It knows no skill keys and must not learn any
##
## Every row comes from whatever the server sent. Adding a skill is one file
## under `systems/progression/skills/skill_defs/`, and a table of skill names
## here would be the place that goes stale first — the same contract
## [SummaryState] answers for panels and [QuestState] for quests.
##
## That extends to the ORDER and the GROUPING. The server sorts rows by
## (category, name) and ships `categories` beside them, so a grid can be
## grouped without this client deciding what comes first. A second opinion here
## would be the third place that fact lives.
##
## ## Why this is not a slice of `char_summary`
##
## Skills were a band on the dossier until 08/28/2026. Drawing a grid from that
## meant reaching into the summary payload and pulling one panel out **by
## name**, which is precisely what [SummaryState]'s contract forbids — the
## dossier is iterated, never enumerated. One screen, one channel.
##
## ## Every row is complete, so a click costs no round trip
##
## The server ships each skill's unlock ladder in the snapshot. It is static —
## what a recipe requires does not depend on who is asking — so the alternative
## was a request per click, for a few kilobytes across the entire roster.
##
## **Every number in a parsed payload is a float.** `JSON.parse_string` returns
## `{"level": 30.0}` always, and `"%d"` on a float is not what it looks like.
## Converted here, at the point of use, exactly as [QuestState] does it.

## Server-owned names, generated from blackout/systems/statefeed/constants.py.
const _Const := preload("res://autoload/blackout_constants.gd")

## Fired when the roster lands, so a view redraws from one place.
signal changed

## True once char_skills has arrived. Distinguishes "the server has said
## nothing yet" from a character with every skill at zero, which look identical
## in a grid and are not the same thing to a player who has just logged in.
var has_data := false

## [{key, name, category, level, current_xp, ...}, ...] in the server's order.
var skills: Array = []

## Category names, in the order their first row appears.
var categories: Array = []

var total_level := 0
var total_xp := 0

## The level cap, so a view can draw a meter against it without a constant of
## its own that could disagree with MAX_BASE_SKILL_LEVEL.
var max_level := 0

## The skill nearest its next level, or `{}` when every skill is capped.
##
## Empty rather than null: "every skill is capped" is a real state, and a client
## that had to tell null from absent from empty would be branching three ways
## on one fact.
var closest: Dictionary = {}


## Fold one feed message into this model.
##
## Returns true when the payload was one of ours, so the console can route
## without restating the channel name in a second match.
func ingest(channel: String, payload: Dictionary) -> bool:
	if channel != _Const.CH_CHAR_SKILLS:
		return false

	skills = _rows(payload.get("skills", []))
	categories = _categories(payload.get("categories", []))
	total_level = int(payload.get("total_level", 0))
	total_xp = int(payload.get("total_xp", 0))
	max_level = int(payload.get("max_level", 0))
	closest = _closest(payload.get("closest", {}))
	has_data = true

	changed.emit()

	return true


## Forget everything. Called when the socket drops.
##
## The same reason [QuestState] clears: a websocket close ends the Evennia
## Session, so a roster still showing levels beside a dead socket is describing
## a character nobody is puppeting.
func reset() -> void:
	has_data = false
	skills = []
	categories = []
	total_level = 0
	total_xp = 0
	max_level = 0
	closest = {}

	changed.emit()


## One skill's row, or `{}` when nothing carries that key.
##
## Empty rather than null so a caller can `.get()` the result without checking
## first — the same choice [SummaryState.rows_for] makes.
func row_for(skill_key: String) -> Dictionary:
	for row: Dictionary in skills:
		if str(row.get("key", "")) == skill_key:
			return row

	return {}


## Rows belonging to one category, in the server's order.
func rows_in(category: String) -> Array:
	var found: Array = []

	for row: Dictionary in skills:
		if str(row.get("category", "")) == category:
			found.append(row)

	return found


## How far one skill is through its current level, as 0.0 to 1.0.
##
## Here rather than in the view because it is arithmetic on the payload, and a
## second view wanting the same number would otherwise write it again.
##
## `needed_xp` is the threshold for THIS level and `current_xp` is progress into
## it — never the cumulative figure, which is `total_xp` and would give a bar
## that fills once and then stays full. A threshold of zero reads as complete
## rather than dividing.
static func level_fraction(row: Dictionary) -> float:
	var needed := int(row.get("needed_xp", 0))

	if needed <= 0:
		return 1.0

	var progress := float(int(row.get("current_xp", 0))) / float(needed)

	return clampf(progress, 0.0, 1.0)


func _rows(raw: Variant) -> Array:
	var rows: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return rows

	for entry: Variant in raw:
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		rows.append({
			"key": str(entry.get("key", "")),
			"name": str(entry.get("name", "")),
			"category": str(entry.get("category", "")),
			"description": str(entry.get("description", "")),
			"level": int(entry.get("level", 0)),
			"max_level": int(entry.get("max_level", 0)),
			"current_xp": int(entry.get("current_xp", 0)),
			"needed_xp": int(entry.get("needed_xp", 0)),
			"remaining_xp": int(entry.get("remaining_xp", 0)),
			"total_xp": int(entry.get("total_xp", 0)),
			"next_level_at": int(entry.get("next_level_at", 0)),
			"unlocked": bool(entry.get("unlocked", true)),
			# The line a telnet player would type to read this sheet. The
			# SERVER names it; this client sends it verbatim and never spells
			# a command of its own.
			"command": str(entry.get("command", "")),
			"unlocks": _sections(entry.get("unlocks", [])),
		})

	return rows


func _sections(raw: Variant) -> Array:
	var sections: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return sections

	for entry: Variant in raw:
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		sections.append({
			"title": str(entry.get("title", "")),
			"rows": _unlock_rows(entry.get("rows", [])),
		})

	return sections


func _unlock_rows(raw: Variant) -> Array:
	var rows: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return rows

	for entry: Variant in raw:
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		rows.append({
			"name": str(entry.get("name", "")),
			"level": int(entry.get("level", 0)),
			"note": str(entry.get("note", "")),
		})

	return rows


func _categories(raw: Variant) -> Array:
	var names: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return names

	for entry: Variant in raw:
		names.append(str(entry))

	return names


func _closest(raw: Variant) -> Dictionary:
	if typeof(raw) != TYPE_DICTIONARY or raw.is_empty():
		return {}

	return {
		"skill_key": str(raw.get("skill_key", "")),
		"level": int(raw.get("level", 0)),
		"current_xp": int(raw.get("current_xp", 0)),
		"needed_xp": int(raw.get("needed_xp", 0)),
		"remaining_xp": int(raw.get("remaining_xp", 0)),
	}
