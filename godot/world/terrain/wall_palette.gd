class_name WallPalette
extends RefCounted
## What each wall style LOOKS like: one colour for each name.
##
## The wall style names are server facts, in `blackout/world/wall_styles.py`,
## exported as [code]TILE_WALL_STYLES[/code]. The height of each style is a
## server fact too ([code]TILE_WALL_STYLE_HEIGHTS[/code]). The client owns the
## colours (DESIGN-0013 section 6.4). [WallMeshBuilder] reads them. The client
## and the editor both draw the walls through that class.
##
## ## The guard, and the fallback
##
## `test_client_constants.py` reads [constant COLORS] as TEXT and fails if a
## key names no wall style. A key that names nothing is dead configuration.
## A wall style with no key is fine: it draws in the colour of the default
## style. Thus, a new wall style needs no client edit.
##
## Move or rename this file, or [constant COLORS], only together with
## `_WALL_PALETTE_SOURCES` in that test.

const _Const := preload("res://autoload/blackout_constants.gd")

## Wall style name to the colour of the sides of its walls. A look, for Nick
## to tune.
const COLORS := {
	"plain": Color("7b7870"),
	"concrete": Color("a3a098"),
	"brick": Color("8c4f3c"),
	"sheet_metal": Color("6a7176"),
	"chain_link": Color("8e9398"),
	"rubble": Color("6e6660"),
}

## How much lighter the top of a wall is than its sides. The line of a wall
## then reads from the camera above.
const TOP_LIGHTEN := 0.25


## The colour of the sides of a wall of `style`. A style with no row draws in
## the colour of the default style.
static func side_color(style: String) -> Color:
	if COLORS.has(style):
		return COLORS[style]

	return COLORS[_Const.TILE_DEFAULT_WALL_STYLE]


## The colour of the top of a wall of `style`.
static func top_color(style: String) -> Color:
	return side_color(style).lightened(TOP_LIGHTEN)
