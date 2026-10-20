@tool
class_name FloorPalette
extends RefCounted
## What each floor type LOOKS like: one colour for each name, and the
## colours of the cliff, the water, and the primitive props.
##
## The floor type names are server facts, in `blackout/world/floor_types.py`,
## exported as [code]TILE_FLOOR_TYPES[/code]. The colours are the client's own.
## DESIGN-0011 section 6.8: colour comes from the floor type, through one
## palette, with no photo texture on the ground.
##
## ## The look file, and the fallback
##
## Since 10/13/2026 the design is `res://world/look/terrain_palette.json`,
## and the Look tab of the terrain editor writes it ([TerrainPalette]).
## Each reader here asks the file first. The tables below are the fallback:
## the colour of a row that the file does not have, and the start of a new
## file. Thus a new floor type needs no edit here, and a missing file draws
## as before.
##
## ## The guard
##
## `test_client_constants.py` reads [constant COLORS] as TEXT, and the look
## file as JSON, and fails if a key names no floor type. A key that names
## nothing is dead configuration. A floor type with no key is fine:
## [method color_of] gives it a stable hue from its name.
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
	"roof_sheet_metal": Color("7a6f66"),
	"roof_tile": Color("8e5a44"),
	"roof_concrete": Color("85847e"),
}

## The colour of a cliff face: a triangle steeper than the walk limit, on any
## floor type. [ChunkMeshBuilder] picks it. The rule is the server's
## [code]TILE_WALK_LIMIT[/code].
const CLIFF_COLOR := Color("5e5249")

## The colour of the water surface on a tile with the water flag, on any floor
## type. [WaterMeshBuilder] picks it. Opaque, not see-through: an alpha
## material costs a shader compile on the web, and the low-poly look draws
## water as a flat colour (DESIGN-0011 debt 8, 09/26/2026).
const WATER_COLOR := Color("3d6f86")

## The colours of the primitive scenery and decor of [PropMeshBuilder]: a
## ladder, a flight of stairs, a hatch, a crate, a table, and a lamp post.
## Plain shapes until the kinds get art. The keys are
## [constant TerrainPalette.PROP_KEYS].
const PROP_COLORS := {
	"ladder": Color("8a5a36"),
	"stairs": Color("8f8b82"),
	"hatch": Color("2b2622"),
	"hatch_frame": Color("6b5a48"),
	"crate": Color("7a5a3a"),
	"crate_lid": Color("5e4430"),
	"table": Color("6f6b63"),
	"lamp_post": Color("3d4147"),
	"lamp": Color("ffd27a"),
	"oil_lamp": Color("b08a4a"),
	"oil_lamp_glass": Color("ffe0a0"),
	"torch": Color("4a4a4e"),
	"torch_flame": Color("ff9a3a"),
}

## How much lighter the top face of a primitive is than its sides, so its
## shape reads from the camera above.
const PROP_TOP_LIGHTEN := 0.15

## The saturation and the value of a hashed fallback colour.
const FALLBACK_SATURATION := 0.35
const FALLBACK_VALUE := 0.55

## How far one face may move from its floor colour, as a fraction of the
## value. This makes the facets of flat ground visible. A position hash picks
## the amount, so every client draws the same facets.
const FACET_SHADE := 0.05


## The colour of a floor type: the look file, then [constant COLORS]. A
## name with no row gets a stable hashed hue.
static func color_of(floor_name: String) -> Color:
	var hex := TerrainPalette.floor_hex(floor_name)

	if not hex.is_empty():
		return Color.html(hex)

	if COLORS.has(floor_name):
		return COLORS[floor_name]

	var hue := float(floor_name.hash() % 360) / 360.0

	return Color.from_hsv(absf(hue), FALLBACK_SATURATION, FALLBACK_VALUE)


## The colour of a cliff face: the look file, then [constant CLIFF_COLOR].
static func cliff() -> Color:
	return LookFile.color_of(TerrainPalette.cliff_hex(), CLIFF_COLOR)


## The colour of the water: the look file, then [constant WATER_COLOR].
static func water() -> Color:
	return LookFile.color_of(TerrainPalette.water_hex(), WATER_COLOR)


## The colour of a primitive prop: the look file, then
## [constant PROP_COLORS]. A key with no row draws magenta, as a missing
## colour does.
static func prop(key: String) -> Color:
	return LookFile.color_of(TerrainPalette.prop_hex(key),
		PROP_COLORS.get(key, MeshPalette.MISSING_COLOR))


## `base`, made lighter or darker by `amount` in -1..1 times [constant FACET_SHADE].
static func shade(base: Color, amount: float) -> Color:
	var factor := 1.0 + amount * FACET_SHADE

	return Color(base.r * factor, base.g * factor, base.b * factor, base.a)
