@tool
class_name AreaLook
extends RefCounted
## The fog and the light of each area: one row for each area, and a fallback.
##
## DESIGN-0011 section 6.7 sets the rules. Fog is a look, so the client owns
## this table. The server says which area the player is in. This file says what
## that area looks like. 117 HD's `environments.json` uses the same split.
##
## ## The look file, and the fallback
##
## Since 10/13/2026 the design is `res://world/look/area_looks.json`, and
## the Look tab of the terrain editor writes it, with a preview of the
## light in the editor. [method look_for] asks the file first, then
## [constant LOOKS], then [constant FALLBACK]. The tables here are the
## fallback and the start of a new file.
##
## ## The area of the player
##
## The `areas` layer of the chunk file gives the area of each tile.
## [method WorldState.area_at] reads it for the tile of the player. Each key
## here is a row of `blackout/world/areas.py`. Those rows still carry the old
## map names (handoff debt 9).
##
## ## The guard
##
## `blackout/systems/interface/statefeed/tests/test_client_constants.py` reads
## this file as TEXT, and the look file as JSON. It fails when a key names
## no area. An area with no row is fine, because it gets [constant FALLBACK].
## Thus, new content never needs a client edit. Keep each row key at one tab
## of indent, on its own line, with its opening brace. The test finds the
## keys by that shape.
##
## ## The fields
##
## Every row holds every field of [constant FALLBACK], and `test_area_look`
## asserts it. Distances are in tiles. One tile is one world unit.
##
## | Field | Meaning |
## |---|---|
## | `fog_color` | The fog, and the background behind it |
## | `fog_begin` | Tiles past the player where the fog starts |
## | `fog_end` | Tiles past the player where the fog hides everything |
## | `sun_color`, `sun_energy` | The one sun |
## | `sun_elevation` | Degrees above the horizon |
## | `sun_azimuth` | Degrees about the vertical axis. Zero is the scene default |
## | `ambient_color`, `ambient_energy` | The light that has no direction |
##
## ## The shadow minimum
##
## The share of the sun that still reaches a place in full shadow (Nick,
## 10/20/2026). It is one number for every area, beside the area rows of
## the look file. A hidden roof keeps its shadow ([TerrainView]), so the
## inside of every structure is in full shadow. The shadow minimum sets how
## dark that shadow is. It makes the shadow lighter, and the open ground
## stays as it is. The ambient energy makes the open ground lighter too.
##
## [method apply_to] writes it to the sun as
## [member Light3D.shadow_opacity], which is its other share. It is not a
## field of a look, so a blend does not move it.
##
## A RefCounted with only static members. Nothing makes an instance of it.

const PATH := LookFile.DIRECTORY + "/area_looks.json"

const KEY_AREAS := "areas"

## The key of the shadow minimum in the look file.
const KEY_SHADOW_MINIMUM := "shadow_minimum"

## The shadow minimum when the look file has none. 0 gives the full shadow,
## and 1 gives no shadow.
const SHADOW_MINIMUM_DEFAULT := 0.3

## The fields that hold a colour. The file stores them as hex text.
const COLOR_FIELDS := ["fog_color", "sun_color", "ambient_color"]

## The look of an area that has no row. It is also the look before the first
## chunk arrives.
##
## The values match `world.tscn` before 09/24/2026: a dark blue void and a sun
## 60 degrees up. A player in an area with no row thus sees the old client,
## with fog added.
const FALLBACK := {
	"fog_color": Color("0b0f14"),
	"fog_begin": 14.0,
	"fog_end": 30.0,
	"sun_color": Color(1.0, 1.0, 1.0),
	"sun_energy": 1.0,
	"sun_elevation": 60.0,
	"sun_azimuth": 0.0,
	"ambient_color": Color(0.35, 0.42, 0.5),
	"ambient_energy": 0.6,
}

## One row for each area: the start of the look file.
const LOOKS := {
	# The town at the water. A warm sand haze under a high sun, like the
	# Necropolis reference.
	"oasis": {
		"fog_color": Color("b89572"),
		"fog_begin": 14.0,
		"fog_end": 32.0,
		"sun_color": Color("ffe2b0"),
		"sun_energy": 1.1,
		"sun_elevation": 55.0,
		"sun_azimuth": 30.0,
		"ambient_color": Color("7a6a5a"),
		"ambient_energy": 0.6,
	},
	# The dry ring around the town. More dust and a lower sun, so the haze is
	# more orange and the view is shorter.
	"oasis_outskirts": {
		"fog_color": Color("a8744a"),
		"fog_begin": 10.0,
		"fog_end": 26.0,
		"sun_color": Color("ffc98a"),
		"sun_energy": 1.0,
		"sun_elevation": 40.0,
		"sun_azimuth": 45.0,
		"ambient_color": Color("6a5040"),
		"ambient_energy": 0.6,
	},
	# Open plains under an overcast sky. A cool grey-green haze and a weak sun,
	# so the copper clearings show against the ground.
	"azm_plains": {
		"fog_color": Color("7d8a86"),
		"fog_begin": 12.0,
		"fog_end": 30.0,
		"sun_color": Color("dfe8e0"),
		"sun_energy": 0.8,
		"sun_elevation": 50.0,
		"sun_azimuth": -30.0,
		"ambient_color": Color("4f5c5e"),
		"ambient_energy": 0.7,
	},
}

## The fields that turn in a circle. A blend takes the short way around, so a
## sun at 350 degrees moves to 10 degrees through 0, not through 180.
const _ANGLE_FIELDS := ["sun_azimuth"]


## The look of one area: the look file, then [constant LOOKS], then
## [constant FALLBACK]. A row of the file with a field missing takes that
## field from the table row, or from the fallback.
static func look_for(area: String) -> Dictionary:
	var base: Dictionary = LOOKS.get(area, FALLBACK)
	var row := _file_row(area)
	var look := {}

	for field: String in FALLBACK:
		look[field] = _field_of(row, field, base[field])

	return look


## True when the look file has a row for `area`.
static func has_file_row(area: String) -> bool:
	return not _file_row(area).is_empty()


## Write the look of `area` into the look file. The Look tab of the terrain
## editor calls it after each change.
static func save_look(area: String, look: Dictionary) -> Error:
	var content := LookFile.read(PATH).duplicate(true)
	var areas: Variant = content.get(KEY_AREAS, {})
	var row := {}

	if typeof(areas) != TYPE_DICTIONARY:
		areas = {}

	for field: String in FALLBACK:
		var value: Variant = look.get(field, FALLBACK[field])

		row[field] = LookFile.stored_of(value)

	areas[area] = row
	content["format"] = LookFile.FORMAT
	content[KEY_AREAS] = areas

	return LookFile.write(PATH, content)


## Take the row of `area` out of the look file. The area then draws its
## table row, or the fallback.
static func reset_look(area: String) -> Error:
	var content := LookFile.read(PATH).duplicate(true)
	var areas: Variant = content.get(KEY_AREAS, {})

	if typeof(areas) == TYPE_DICTIONARY:
		areas.erase(area)

	content["format"] = LookFile.FORMAT
	content[KEY_AREAS] = areas

	return LookFile.write(PATH, content)


## The shadow minimum of every area, from 0 to 1: the look file, then
## [constant SHADOW_MINIMUM_DEFAULT].
static func shadow_minimum() -> float:
	var value: Variant = LookFile.read(PATH).get(KEY_SHADOW_MINIMUM)
	var is_number := typeof(value) in [TYPE_INT, TYPE_FLOAT]

	if not is_number:
		return SHADOW_MINIMUM_DEFAULT

	return clampf(float(value), 0.0, 1.0)


## Write the shadow minimum of every area into the look file. The Look tab
## of the terrain editor calls it after each change. The area rows stay as
## they are.
static func save_shadow_minimum(value: float) -> Error:
	var content := LookFile.read(PATH).duplicate(true)

	content["format"] = LookFile.FORMAT
	content[KEY_SHADOW_MINIMUM] = clampf(value, 0.0, 1.0)

	return LookFile.write(PATH, content)


## Write `look` to an environment and a sun. [AreaEnvironment] and the
## preview of the terrain editor share it, so the two cannot draw one row
## differently. The fog distances are not here: they move with the camera,
## and [method fog_depth] gives them.
static func apply_to(environment: Environment, sun: DirectionalLight3D,
		look: Dictionary) -> void:
	var fog_color: Color = look["fog_color"]

	environment.fog_light_color = fog_color
	environment.background_color = fog_color
	environment.ambient_light_color = look["ambient_color"]
	environment.ambient_light_energy = look["ambient_energy"]

	if sun == null:
		return

	var elevation := deg_to_rad(float(look["sun_elevation"]))
	var azimuth := deg_to_rad(float(look["sun_azimuth"]))

	sun.light_color = look["sun_color"]
	sun.light_energy = look["sun_energy"]
	# The opacity is the share of the sun that a shadow stops.
	sun.shadow_opacity = 1.0 - shadow_minimum()
	# A light shines down its own -Z. A negative pitch points it at the ground,
	# and the yaw turns it about the vertical axis.
	sun.rotation = Vector3(-elevation, azimuth, 0.0)


## A look part of the way from one look to another.
##
## `weight` 0 gives `from`, and 1 gives `to`. The routine blends each field of
## [constant FALLBACK]. It lerps a colour in RGB and an angle the short way.
static func blend(from: Dictionary, to: Dictionary, weight: float) -> Dictionary:
	var clamped := clampf(weight, 0.0, 1.0)
	var result: Dictionary = {}

	for field: String in FALLBACK:
		result[field] = _blend_field(field, from[field], to[field], clamped)

	return result


## Where the depth fog begins and ends, measured from the camera.
##
## Godot measures depth fog from the camera, but the table measures from the
## player. The camera is `arm_length` from the player, so this adds that length
## to both. The result is exact straight ahead and a little long at the sides.
## DESIGN-0011 section 6.7 accepts that error for Phase 0.
static func fog_depth(look: Dictionary, arm_length: float) -> Vector2:
	var begin: float = arm_length + float(look["fog_begin"])
	var end: float = arm_length + float(look["fog_end"])

	return Vector2(begin, end)


## The row of `area` in the look file, or an empty dictionary.
static func _file_row(area: String) -> Dictionary:
	var areas: Variant = LookFile.read(PATH).get(KEY_AREAS, {})

	if typeof(areas) != TYPE_DICTIONARY:
		return {}

	var row: Variant = areas.get(area, {})

	return row if typeof(row) == TYPE_DICTIONARY else {}


## One field of a file row as the look holds it: a colour from hex text, a
## number as a float. `fallback` for a field that is missing or wrong.
static func _field_of(row: Dictionary, field: String, fallback: Variant) -> Variant:
	if not row.has(field):
		return fallback

	if field in COLOR_FIELDS:
		return LookFile.color_of(row[field], fallback)

	var value: Variant = row[field]

	return float(value) if typeof(value) in [TYPE_INT, TYPE_FLOAT] else fallback


static func _blend_field(field: String, from: Variant, to: Variant,
		weight: float) -> Variant:
	if from is Color:
		var from_color: Color = from

		return from_color.lerp(to, weight)

	if field in _ANGLE_FIELDS:
		var from_radians := deg_to_rad(float(from))
		var to_radians := deg_to_rad(float(to))
		var blended := lerp_angle(from_radians, to_radians, weight)

		return rad_to_deg(blended)

	return lerpf(float(from), float(to), weight)
