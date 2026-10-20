@tool
class_name LightLook
extends RefCounted
## The light of a scenery key: what a lamp gives off. One look file,
## `lights.json`, and one reader. [TileLights] bakes each light into the
## ground, the walls, and the props, and [FigureLights] stands a real light
## on the nearest ones.
##
## The server names the scenery of each object kind
## ([method TileTables.scenery_of]). A light is a look of that scenery, so
## the client owns it, as it owns the colour of a floor type. Nothing in a
## placement carries a light: an author who tunes 200 lamps one by one is
## the sign that the row is wrong. A served model with a
## `KHR_lights_punctual` light of its own keeps it, and the row here adds
## the bake.
##
## The file holds:
##
## | Key | Holds |
## |---|---|
## | `lights` | Scenery key to `{color, energy, range, height}` |
##
## `color` is a hex colour. `energy` scales it. `range` is how far the light
## reaches, in tiles. `height` is how high the bulb stands over the ground
## of its tile, in world units. The look of the object scales the height
## with the shape.
##
## [constant LIGHTS] is the fallback: the row of a key with no row in the
## file. A key in neither gives no light. The Look tab of the terrain editor
## writes the file through [method save_light] and [method reset_light].

const PATH := LookFile.DIRECTORY + "/lights.json"

const KEY_LIGHTS := "lights"
const FIELD_COLOR := "color"
const FIELD_ENERGY := "energy"
const FIELD_RANGE := "range"
const FIELD_HEIGHT := "height"

## The fields of a light row, in the order of the Look tab.
const FIELDS := [FIELD_COLOR, FIELD_ENERGY, FIELD_RANGE, FIELD_HEIGHT]

## The fallback light of each scenery key. The lamp post primitive hangs its
## lamp at [constant PropMeshBuilder.LAMP_HEIGHT] less the arm. The oil
## lamp is small and warm, and its glass stands low. The torch burns
## orange at the top of its pole.
const LIGHTS := {
	"lamp_post": {FIELD_COLOR: Color("ffd27a"), FIELD_ENERGY: 1.0, FIELD_RANGE: 5.0,
		FIELD_HEIGHT: 1.65},
	"oil_lamp": {FIELD_COLOR: Color("ffcf80"), FIELD_ENERGY: 0.6, FIELD_RANGE: 3.0,
		FIELD_HEIGHT: 0.25},
	"torch": {FIELD_COLOR: Color("ff9a3a"), FIELD_ENERGY: 0.9, FIELD_RANGE: 4.0,
		FIELD_HEIGHT: 1.3},
}

## The row of a new light on the Look tab.
const DEFAULT := {FIELD_COLOR: Color("ffd27a"), FIELD_ENERGY: 1.0, FIELD_RANGE: 5.0,
	FIELD_HEIGHT: 1.5}

## The bounds of a field. A range of 0 and an energy of 0 give no light.
const ENERGY_MAX := 8.0
const RANGE_MAX := 24.0
const HEIGHT_MAX := 8.0


static func data() -> Dictionary:
	return LookFile.read(PATH)


# ─── Reading ────────────────────────────────────────────────────────────────

## The light of a scenery key: the file row, then [constant LIGHTS]. An empty
## dictionary for a key with no light. Each field is present and typed: the
## colour is a Color, and the numbers are floats.
static func light_of(scenery: String) -> Dictionary:
	var row := _file_row(scenery)
	var base: Dictionary = LIGHTS.get(scenery, {})

	if row.is_empty() and base.is_empty():
		return {}

	var light := {}

	for field: String in FIELDS:
		light[field] = _field_of(row, field, base.get(field, DEFAULT[field]))

	return light


## True when the scenery key gives light. It has a row, with an energy and a
## range over zero.
static func gives_light(scenery: String) -> bool:
	return is_lit(light_of(scenery))


## True when a row of [method light_of] gives light. An energy of zero turns
## the fallback light of a key off. So does a range of zero.
static func is_lit(light: Dictionary) -> bool:
	if light.is_empty():
		return false

	return light[FIELD_ENERGY] > 0.0 and light[FIELD_RANGE] > 0.0


## True when the look file has a row for the scenery key.
static func has_file_row(scenery: String) -> bool:
	return not _file_row(scenery).is_empty()


## Every scenery key with a light: the file rows, then the fallback rows.
static func keys() -> PackedStringArray:
	var found := PackedStringArray()
	var rows: Variant = data().get(KEY_LIGHTS, {})

	if typeof(rows) == TYPE_DICTIONARY:
		for key: String in rows:
			found.append(key)

	for key: String in LIGHTS:
		if not found.has(key):
			found.append(key)

	return found


## The colour of a light times its energy: what the bake adds to a surface
## right under the bulb.
static func glow_of(light: Dictionary) -> Color:
	var color: Color = light[FIELD_COLOR]
	var energy: float = light[FIELD_ENERGY]

	return Color(color.r * energy, color.g * energy, color.b * energy, 1.0)


# ─── Writing ────────────────────────────────────────────────────────────────

## Write the light of a scenery key into the look file. The Look tab calls
## it after each change.
static func save_light(scenery: String, light: Dictionary) -> Error:
	var content := data().duplicate(true)
	var rows := _rows_of(content)
	var row := {}

	for field: String in FIELDS:
		var value: Variant = light.get(field, DEFAULT[field])

		row[field] = LookFile.hex_of(value) if value is Color else float(value)

	rows[scenery] = row
	content["format"] = LookFile.FORMAT
	content[KEY_LIGHTS] = rows

	return LookFile.write(PATH, content)


## Take the row of a scenery key out of the look file. The key then gives
## its fallback light, or none.
static func reset_light(scenery: String) -> Error:
	var content := data().duplicate(true)
	var rows := _rows_of(content)

	rows.erase(scenery)
	content["format"] = LookFile.FORMAT
	content[KEY_LIGHTS] = rows

	return LookFile.write(PATH, content)


static func _rows_of(content: Dictionary) -> Dictionary:
	var rows: Variant = content.get(KEY_LIGHTS, {})

	return rows if typeof(rows) == TYPE_DICTIONARY else {}


static func _file_row(scenery: String) -> Dictionary:
	var row: Variant = _rows_of(data()).get(scenery, {})

	return row if typeof(row) == TYPE_DICTIONARY else {}


## A field of a file row, typed, or `fallback` for a field that is missing
## or malformed.
static func _field_of(row: Dictionary, field: String, fallback: Variant) -> Variant:
	var value: Variant = row.get(field)

	if fallback is Color:
		return LookFile.color_of(value, fallback)

	if typeof(value) in [TYPE_INT, TYPE_FLOAT]:
		return maxf(float(value), 0.0)

	return float(fallback)
