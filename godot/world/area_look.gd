class_name AreaLook
extends RefCounted
## The fog and the light of each area: one row for each area, and a fallback.
##
## DESIGN-0011 section 6.7 sets the rules. Fog is a look, so the client owns
## this table. The server says which area the player is in. This file says what
## that area looks like. 117 HD's `environments.json` uses the same split.
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
## this file as TEXT. It fails when a key names no area. An area with no row is
## fine, because it gets [constant FALLBACK]. Thus, new content never needs a
## client edit. Keep each row key at one tab of indent, on its own line, with
## its opening brace. The test finds the keys by that shape.
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
## A RefCounted with only static members. Nothing makes an instance of it.

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

## One row for each area. The first values are proposals, for Nick to tune.
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


## The look of one area. An area with no row gets [constant FALLBACK].
static func look_for(area: String) -> Dictionary:
	var row: Dictionary = LOOKS.get(area, FALLBACK)

	return row.duplicate()


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
