class_name CombatOptionsState
extends RefCounted
## How you fight, from `char_combat`: the wielded weapon, its styles, which one
## is active, the attack speed and the combat level.
##
## ## It knows no weapon and no style, and must not learn any
##
## Every row is whatever the server sent, in the weapon's own order. Adding a
## weapon is one ItemDef, and a table of style names here would be the first
## place that goes stale — the contract [SkillsState] answers for skills.
##
## ## Nothing here is set by a click
##
## The active style is whatever the LAST snapshot said. A click sends
## `combatoptions <style>` and changes nothing locally; the server's republish
## is what lights the new style. A model that flipped `active` optimistically
## would show a style the server refused — the weapon swapped out between the
## click and the command — with nothing scheduled to put it right.
##
## **Every number in a parsed payload is a float.** Converted here, at the point
## of use, exactly as [SkillsState] does it.

## Server-owned names, generated from blackout/systems/interface/statefeed/constants.py.
const _Const := preload("res://autoload/blackout_constants.gd")

## Fired when a snapshot lands, so a view redraws from one place.
signal changed

## True once char_combat has arrived. Distinguishes "the server has said
## nothing yet" from bare hands, which is a real answer.
var has_data := false

## The wielded item's key, or the server's name for bare hands.
var weapon_name := ""

## True when an item is wielded. False is bare hands.
var armed := false

var combat_level := 0
var attack_speed_ticks := 0

## Seconds, from the SERVER. The tick length is not exported, so dividing by a
## copy of it here would be a second owner of the tick.
var attack_speed_seconds := 0.0

## [{key, name, attack_type, weapon_style, boosts, xp_skills, active, command}]
## in the weapon's order. `command` is empty on a row that cannot be picked.
var styles: Array = []

## The PvP flag, as the LAST snapshot said. A click changes nothing here: the
## server's republish moves it, for the reason a style row gives.
var pvp_enabled := false

## The whole line that flips the flag — `pvp on` or `pvp off`. The SERVER
## names it; this client sends it verbatim. Empty from a server that sends no
## `pvp` block, which the view reads as "no toggle".
var pvp_command := ""


## Fold one feed message into this model.
##
## Returns true when the payload was one of ours, so the console can route
## without restating the channel name in a second match.
func ingest(channel: String, payload: Dictionary) -> bool:
	if channel != _Const.CH_CHAR_COMBAT:
		return false

	weapon_name = str(payload.get("weapon_name", ""))
	armed = bool(payload.get("armed", false))
	combat_level = int(payload.get("combat_level", 0))
	attack_speed_ticks = int(payload.get("attack_speed_ticks", 0))
	attack_speed_seconds = float(payload.get("attack_speed_seconds", 0.0))
	styles = _rows(payload.get("styles", []))
	_read_pvp(payload.get("pvp", {}))
	has_data = true

	changed.emit()

	return true


## Forget everything. Called when the socket drops, for the reason
## [method SkillsState.reset] gives.
func reset() -> void:
	has_data = false
	weapon_name = ""
	armed = false
	combat_level = 0
	attack_speed_ticks = 0
	attack_speed_seconds = 0.0
	styles = []
	pvp_enabled = false
	pvp_command = ""

	changed.emit()


## The active style's row, or `{}` when no row is active.
##
## Empty rather than null so a caller can `.get()` the result without checking
## first — the same choice [method SkillsState.row_for] makes.
func active_style() -> Dictionary:
	for row: Dictionary in styles:
		if row["active"]:
			return row

	return {}


## True when at least one style can be picked. False for bare hands.
func has_choice() -> bool:
	for row: Dictionary in styles:
		if not str(row["command"]).is_empty():
			return true

	return false


## Read the `{enabled, command}` block. Anything that is not a dictionary is
## the same as no block at all.
func _read_pvp(raw: Variant) -> void:
	pvp_enabled = false
	pvp_command = ""

	if typeof(raw) != TYPE_DICTIONARY:
		return

	pvp_enabled = bool(raw.get("enabled", false))
	pvp_command = str(raw.get("command", ""))


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
			"attack_type": str(entry.get("attack_type", "")),
			"weapon_style": str(entry.get("weapon_style", "")),
			"boosts": _skills(entry.get("boosts", [])),
			"xp_skills": _skills(entry.get("xp_skills", [])),
			"active": bool(entry.get("active", false)),
			# The line a telnet player would type to pick this style. The
			# SERVER names it; this client sends it verbatim.
			"command": str(entry.get("command", "")),
		})

	return rows


## Boost and XP entries share a shape; `amount` is 0 on an XP entry.
func _skills(raw: Variant) -> Array:
	var entries: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return entries

	for entry: Variant in raw:
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		entries.append({
			"skill_key": str(entry.get("skill_key", "")),
			"name": str(entry.get("name", "")),
			"amount": int(entry.get("amount", 0)),
		})

	return entries
