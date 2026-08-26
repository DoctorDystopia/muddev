class_name CharState
extends RefCounted
## The observer's own state: who you are, how hurt you are, what you are doing.
##
## Assembled from three channels that the world pane deliberately does not
## touch, because none of them is about the world:
##
##     char_avatar  -- your entity_id and which mesh is you
##     char_vitals  -- hp / max_hp
##     char_status  -- in_combat, and a level per skill
##
## Exists for the same reason [WorldState] does: to keep the float boundary and
## the shape of the feed out of whatever draws them.
##
## **Every number in a parsed payload is a float.** `JSON.parse_string` returns
## `{"hp": 19.0}` always, and a `match` or a dictionary keyed on that will not
## match an int written as `19`. Converted here, at the point of use, rather
## than by walking whole payloads -- a blanket coercion would look correct and
## would silently corrupt the first genuinely fractional field the server grows.
##
## **`levels` is an OPEN dictionary and is never mirrored into fields.** The
## server's summary design is that adding a band is one new file under
## `systems/summary/panel_defs/`; a field per skill here would make it two, with
## this the file nobody remembers to edit. Read it by iteration.

## Server-owned names, generated from blackout/systems/statefeed/constants.py.
const _Const := preload("res://autoload/blackout_constants.gd")

## Fired when any of the three channels lands, so a HUD can redraw once rather
## than binding three signals and duplicating the redraw in each.
signal changed

## Your own entity id, from char_avatar.
##
## This is the field that makes a combat event recognisable as being about YOU.
## `blackout_combat` names attacker and target by id, and a client with no id of
## its own can only guess by name -- which breaks the moment two things in a
## room share one.
var entity_id := 0

## Which mesh you are, and which family it belongs to.
var asset := ""
var family := ""

var hp := 0
var max_hp := 0

var in_combat := false

## skill name -> level. Open by design; iterate, never mirror.
var levels: Dictionary = {}

## False until char_vitals has actually arrived, so a HUD can tell "no data
## yet" from "genuinely on zero hit points". Without it a client draws an empty
## bar at login and it reads as being dead.
var has_vitals := false


## Fold one feed message into this model.
##
## Returns true when the payload was one of ours, so a caller can route without
## restating the channel names in a second match.
func ingest(channel: String, payload: Dictionary) -> bool:
	match channel:
		_Const.CH_CHAR_AVATAR:
			entity_id = int(payload.get("entity_id", 0))
			asset = str(payload.get("asset", ""))
			family = str(payload.get("family", ""))

		_Const.CH_CHAR_VITALS:
			hp = int(payload.get("hp", 0))
			max_hp = int(payload.get("max_hp", 0))
			has_vitals = true

		_Const.CH_CHAR_STATUS:
			in_combat = bool(payload.get("in_combat", false))
			levels = _to_int_levels(payload.get("levels", {}))

		_:
			return false

	changed.emit()

	return true


## How hurt you are, from 0.0 to 1.0.
##
## Zero when max_hp is zero rather than dividing by it. A server that has not
## sent vitals yet, and a character with no maximum, both arrive here.
func health_fraction() -> float:
	if max_hp <= 0:
		return 0.0

	return clampf(float(hp) / float(max_hp), 0.0, 1.0)


## True when this event is about the observer rather than about someone else.
##
## Named rather than left as a bare `==` at each call site, because the failure
## mode is silent: an id of 0 means char_avatar has not arrived, and comparing
## against it would make every event with a missing target look like it was
## about you.
func is_me(other_id: int) -> bool:
	if entity_id == 0:
		return false

	return other_id == entity_id


## Convert a parsed levels dictionary to int values.
##
## The keys are skill names and stay strings; only the values cross the float
## boundary. Kept separate from `ingest` so the conversion has one place rather
## than being inlined into a branch.
func _to_int_levels(raw: Variant) -> Dictionary:
	var converted: Dictionary = {}

	if typeof(raw) != TYPE_DICTIONARY:
		return converted

	for skill: Variant in raw:
		converted[str(skill)] = int(raw[skill])

	return converted
