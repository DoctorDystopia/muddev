class_name SummaryState
extends RefCounted
## The observer's dossier, panel by panel, from `char_summary`.
##
## ## Nothing here knows what a panel is
##
## `panels` is an OPEN dictionary — `{"vitals": {...}, "skills": {...}}` — and
## the server's whole design contract is that adding a band is **one new file**
## under `systems/summary/panel_defs/`. `payloads.py` says so explicitly, and
## says why it is not a field per panel: that would make it two files, with the
## payload module the one nobody remembers to edit.
##
## A client that named its panels would be the third place that fact lives, and
## the first to go stale. So this model stores what arrived and offers it back
## in the order it arrived; [SummaryView] draws whatever that turns out to be.
## **A panel added to the server tomorrow appears in this client with no edit
## here and none in the view.**
##
## The cost, which `payloads.py` also states, is that a client cannot rely on
## any given key being present — a panel legitimately reports nothing when the
## system behind it has nothing to say. Every accessor here is written for that.
##
## ## Order is the server's
##
## `PANEL_REGISTRY` decides the order panels are rendered in for the text
## screen, and Godot's `JSON.parse_string` preserves document order in the
## dictionary it returns. So iterating `panels` gives the same order the text
## dossier uses, and the two screens agree without either of them saying so.

const _Const := preload("res://autoload/blackout_constants.gd")

signal changed

## panel key -> that panel's data dictionary, in the server's order.
var panels: Dictionary = {}

## False until a payload has arrived, so an empty sheet is not drawn as a
## character with nothing in it.
var has_data := false


## Fold one `char_summary` message in, replacing everything.
##
## Returns true when the channel was ours, matching [CharState.ingest] and
## [InventoryState.ingest] so the console routes all three the same way.
func ingest(channel: String, payload: Dictionary) -> bool:
	if channel != _Const.CH_CHAR_SUMMARY:
		return false

	panels = _clean(payload.get("panels", {}))
	has_data = true

	changed.emit()

	return true


## The panel keys, in the order the server sent them.
func panel_keys() -> Array:
	return panels.keys()


## One panel's rows as [[label, value], ...], ready to draw.
##
## Values are rendered to display strings HERE rather than in the view, so the
## view stays a layout concern and the rendering has one place and one test.
## An unknown key returns an empty array — never null, so a caller can iterate
## the result without checking first.
func rows_for(panel_key: String) -> Array:
	var data: Dictionary = panels.get(panel_key, {})
	var rows: Array = []

	for field: Variant in data:
		rows.append([humanise(str(field)), render_value(data[field])])

	return rows


## Turn a snake_case field name into something readable.
##
## Presentation, and deliberately mechanical: the alternative is a client-side
## table of pretty names for fields the server owns, which is exactly the
## duplication this whole model avoids. A field named badly on the server reads
## badly here, and that is the right place to fix it.
static func humanise(field: String) -> String:
	return field.replace("_", " ").capitalize()


## Render one JSON value as display text.
##
## Handles what a panel can actually contain: `summary_data` promises every
## value survives `json.dumps`, so that is scalars, arrays and nested
## dictionaries. Nesting is rendered one level deep and inline — a panel deep
## enough to need more structure than that is a panel that should have been
## split on the server.
static func render_value(value: Variant) -> String:
	match typeof(value):
		TYPE_BOOL:
			return "yes" if value else "no"

		TYPE_FLOAT:
			# Every number in a parsed payload is a float. Integral ones are
			# printed as ints, because "Combat level 42.0" is wrong on a screen
			# a player reads, and a genuinely fractional value keeps its point.
			if is_equal_approx(value, roundf(value)):
				return str(int(value))

			return str(value)

		TYPE_ARRAY:
			var parts: PackedStringArray = []

			for entry: Variant in value:
				parts.append(render_value(entry))

			return ", ".join(parts)

		TYPE_DICTIONARY:
			var pairs: PackedStringArray = []

			for key: Variant in value:
				pairs.append("%s %s" % [humanise(str(key)),
					render_value(value[key])])

			return "  ".join(pairs)

		TYPE_NIL:
			return ""

	return str(value)


## Keep only the panels that are actually dictionaries.
##
## A panel whose `data()` raised contributes an empty dict server-side, which is
## fine and draws as an empty section. Anything that is not a dictionary at all
## is malformed and is dropped rather than raised on — a dossier is a read-only
## screen, and refusing to draw the rest of it because one band is broken helps
## nobody.
func _clean(raw: Variant) -> Dictionary:
	var cleaned: Dictionary = {}

	if typeof(raw) != TYPE_DICTIONARY:
		return cleaned

	for key: Variant in raw:
		if typeof(raw[key]) == TYPE_DICTIONARY:
			cleaned[str(key)] = raw[key]

	return cleaned
