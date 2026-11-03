@tool
class_name AugmentLook
extends RefCounted
## The glow of a lit augment: which parts of the figure glow, and in what
## colour. One look file, `augment_looks.json`, and one reader.
## [FigureGlow] writes the glow onto the figure.
##
## The server names what burns, as the `augments` list on the row of a
## character and on `char_avatar` (DESIGN-0015, 10/30/2026). A glow is a
## look of that fact, so the client owns it, as it owns the colour of a
## floor type. The file holds:
##
## | Key | Holds |
## |---|---|
## | `augments` | Augment key to `{parts, color}` |
##
## `parts` is a list of part names of the body look. `color` is a hex
## colour. [constant LOOKS] is the fallback: the row of a key with no row
## in the file. A key in neither draws no glow, and that is fine: a new
## augment on the server needs no client edit. A key in the file that
## names no augment is a bug, and `test_client_constants.py` of the server
## refuses it.
##
## Author: Nick Hobar
## Creation date: 10/30/2026

const PATH := LookFile.DIRECTORY + "/augment_looks.json"
const KEY_AUGMENTS := "augments"
const FIELD_PARTS := "parts"
const FIELD_COLOR := "color"

## The fallback glow of each augment key.
const LOOKS := {
	"reflex": {FIELD_PARTS: ["head"], FIELD_COLOR: Color("ffb347")},
	"surge": {FIELD_PARTS: ["upper_arm_l", "upper_arm_r", "lower_arm_l", "lower_arm_r"],
		FIELD_COLOR: Color("ff4d4d")},
	"plating": {FIELD_PARTS: ["chest", "upper_chest"], FIELD_COLOR: Color("4da6ff")},
}

## The colour of a row that names none.
const DEFAULT_COLOR := Color("ffffff")


static func data() -> Dictionary:
	return LookFile.read(PATH)


## The glow of an augment key: the file row, then [constant LOOKS]. An
## empty dictionary for a key with no glow. The parts are a
## PackedStringArray, and the colour is a Color.
static func look_of(augment: String) -> Dictionary:
	var row := _file_row(augment)
	var base: Dictionary = LOOKS.get(augment, {})

	if row.is_empty() and base.is_empty():
		return {}

	var parts: Variant = row.get(FIELD_PARTS, base.get(FIELD_PARTS, []))
	var color := LookFile.color_of(row.get(FIELD_COLOR),
		base.get(FIELD_COLOR, DEFAULT_COLOR))

	return {FIELD_PARTS: _names_of(parts), FIELD_COLOR: color}


## Every augment key with a glow: the file rows, then the fallback rows.
static func keys() -> PackedStringArray:
	var found := PackedStringArray()
	var rows: Variant = data().get(KEY_AUGMENTS, {})

	if typeof(rows) == TYPE_DICTIONARY:
		for key: String in rows:
			found.append(key)

	for key: String in LOOKS:
		if not found.has(key):
			found.append(key)

	return found


## The colour of each part that the lit augments glow, part name -> Color.
## A part that two augments name takes the colour of the later one in
## `augments`, the order of the rail.
static func part_colors(augments: Array) -> Dictionary:
	var colors := {}

	for augment: Variant in augments:
		var look := look_of(str(augment))

		if look.is_empty():
			continue

		for part: String in look[FIELD_PARTS]:
			colors[part] = look[FIELD_COLOR]

	return colors


static func _file_row(augment: String) -> Dictionary:
	var rows: Variant = data().get(KEY_AUGMENTS, {})

	if typeof(rows) != TYPE_DICTIONARY:
		return {}

	var row: Variant = rows.get(augment, {})

	return row if typeof(row) == TYPE_DICTIONARY else {}


static func _names_of(parts: Variant) -> PackedStringArray:
	var names := PackedStringArray()

	if typeof(parts) != TYPE_ARRAY:
		return names

	for part: Variant in parts:
		if typeof(part) == TYPE_STRING and not str(part).is_empty():
			names.append(str(part))

	return names
