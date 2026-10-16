@tool
class_name WallPalette
extends RefCounted
## What each wall style LOOKS like: one colour and one height for each name.
##
## The wall style names are server facts, in `blackout/world/wall_styles.py`,
## exported as [code]TILE_WALL_STYLES[/code]. The client owns the colours
## and the heights (DESIGN-0013 section 6.4). [WallMeshBuilder] reads them.
## The client and the editor both draw the walls through that class.
##
## The height left the server on 10/13/2026. No server rule reads it: a
## wall blocks a step at any height, and sight does not read it. It is a
## look, and it sits beside the colour.
##
## ## The look file, and the fallback
##
## The design is `res://world/look/terrain_palette.json`, and the Look tab
## of the terrain editor writes it ([TerrainPalette]). Each reader asks the
## file first. The tables below are the fallback. A wall style with no row
## anywhere draws in the colour and at the height of the default style.
## Thus, a new wall style needs no client edit.
##
## ## The guard
##
## `test_client_constants.py` reads [constant COLORS] as TEXT, and the look
## file as JSON, and fails if a key names no wall style. Move or rename
## this file, or [constant COLORS], only together with
## `_WALL_PALETTE_SOURCES` in that test.

const _Const := preload("res://autoload/blackout_constants.gd")

## Wall style name to the colour of the sides of its walls.
const COLORS := {
	"plain": Color("7b7870"),
	"concrete": Color("a3a098"),
	"brick": Color("8c4f3c"),
	"sheet_metal": Color("6a7176"),
	"chain_link": Color("8e9398"),
	"rubble": Color("6e6660"),
}

## Wall style name to the height of a wall with nothing above it, in height
## steps. Sixteen steps are one tile. A wall under a floor of the plane
## above meets that floor at any height. `plain` is 0.75 units tall, and
## `rubble` is a low ruin wall.
const HEIGHTS := {
	"plain": 12,
	"concrete": 24,
	"brick": 24,
	"sheet_metal": 20,
	"chain_link": 18,
	"rubble": 6,
}

## How much lighter the top of a wall is than its sides. The line of a wall
## then reads from the camera above.
const TOP_LIGHTEN := 0.25


## The colour of the sides of a wall of `style`: the look file, then
## [constant COLORS]. A style with no row draws in the colour of the default
## style.
static func side_color(style: String) -> Color:
	var hex := TerrainPalette.wall_hex(style)

	if not hex.is_empty():
		return Color.html(hex)

	if COLORS.has(style):
		return COLORS[style]

	return side_color_default()


## The colour of the sides of a wall of the default style.
static func side_color_default() -> Color:
	var hex := TerrainPalette.wall_hex(_Const.TILE_DEFAULT_WALL_STYLE)

	if not hex.is_empty():
		return Color.html(hex)

	return COLORS[_Const.TILE_DEFAULT_WALL_STYLE]


## The colour of the top of a wall of `style`.
static func top_color(style: String) -> Color:
	return side_color(style).lightened(top_lighten())


## How much lighter the top of a wall is: the look file, then
## [constant TOP_LIGHTEN].
static func top_lighten() -> float:
	var amount := TerrainPalette.wall_top_lighten()

	return amount if amount >= 0.0 else TOP_LIGHTEN


## The height of a wall of `style` with nothing above it, in height steps:
## the look file, then [constant HEIGHTS]. A style with no row anywhere
## takes the height of the default style.
static func height_steps(style: String) -> int:
	var height := TerrainPalette.wall_height(style)

	if height >= 0:
		return height

	if HEIGHTS.has(style):
		return HEIGHTS[style]

	if style == _Const.TILE_DEFAULT_WALL_STYLE:
		return HEIGHTS[_Const.TILE_DEFAULT_WALL_STYLE]

	return height_steps(_Const.TILE_DEFAULT_WALL_STYLE)
