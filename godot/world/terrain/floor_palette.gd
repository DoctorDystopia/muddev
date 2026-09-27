class_name FloorPalette
extends RefCounted
## What each floor type LOOKS like: one colour for each name.
##
## The floor type names are server facts, in `blackout/world/floor_types.py`,
## exported as [code]TILE_FLOOR_TYPES[/code]. The colours are the client's own.
## DESIGN-0011 section 6.8: colour comes from the floor type, through one
## palette, with no photo texture on the ground.
##
## ## The guard, and the fallback
##
## `test_client_constants.py` reads [constant COLORS] as TEXT and fails if a
## key names no floor type. A key that names nothing is dead configuration.
## A floor type with no key is fine: [method color_of] gives it a stable hue
## from its name, so a new floor type needs no client edit.
##
## Move or rename this file, or [constant COLORS], only together with
## `_FLOOR_PALETTE_SOURCES` in that test.

## Floor type name to colour. Muted, so the fog and the sun set the mood.
const COLORS := {
	"sand": Color("c2a06b"),
	"dirt": Color("8a6a4a"),
	"gravel": Color("8d8a82"),
	"rubble": Color("6e6660"),
	"asphalt": Color("3a3c40"),
	"concrete": Color("9a9a94"),
	"grass": Color("6f8a4a"),
	"water_bed": Color("4f6a6e"),
}

## The colour of a cliff face: a triangle steeper than the walk limit, on any
## floor type. [ChunkMeshBuilder] picks it. A look, for Nick to tune
## (DESIGN-0011 Phase 6, 09/26/2026). The rule is the server's
## [code]TILE_WALK_LIMIT[/code].
const CLIFF_COLOR := Color("5e5249")

## The colour of the water surface on a tile with the water flag, on any floor
## type. [WaterMeshBuilder] picks it. Opaque, not see-through: an alpha
## material costs a shader compile on the web, and the low-poly look draws
## water as a flat colour (DESIGN-0011 debt 8, 09/26/2026). A look, for Nick
## to tune.
const WATER_COLOR := Color("3d6f86")

## The saturation and the value of a hashed fallback colour.
const FALLBACK_SATURATION := 0.35
const FALLBACK_VALUE := 0.55

## How far one face may move from its floor colour, as a fraction of the
## value. This makes the facets of flat ground visible. A position hash picks
## the amount, so every client draws the same facets.
const FACET_SHADE := 0.05


## The colour of a floor type. A name with no row gets a stable hashed hue.
static func color_of(floor_name: String) -> Color:
	if COLORS.has(floor_name):
		return COLORS[floor_name]

	var hue := float(floor_name.hash() % 360) / 360.0

	return Color.from_hsv(absf(hue), FALLBACK_SATURATION, FALLBACK_VALUE)


## `base`, made lighter or darker by `amount` in -1..1 times [constant FACET_SHADE].
static func shade(base: Color, amount: float) -> Color:
	var factor := 1.0 + amount * FACET_SHADE

	return Color(base.r * factor, base.g * factor, base.b * factor, base.a)
