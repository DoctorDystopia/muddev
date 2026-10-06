class_name HudElements
extends RefCounted
## The HUD elements that the player can place, and where each one ships.
##
## One row for each element. A key is the name of the element in the saved
## layout, so a key never changes after it ships: a renamed key loses the
## place that each player gave the element. The title is what the layout
## editor shows, and a title can change at any time.
##
## The console gives each key its control. See `HUD_ELEMENTS` there.
##
## ## The shipped layout
##
## The layout that `console.tscn` had before the layout editor, with two
## fixes. The vitals hold the top left. The minimap holds the top right, and
## the XP drops sit to its left. The log and the control panel hang from the
## two bottom corners. The hover bar has no row geometry: it fills the gap
## between the two docks, so the console gives it a rect function. See
## [member HudSlot.default_rect].
##
## The two fixes, found by `smoke_console` on 09/29/2026:
##
## - The XP drops ended 76 pixels under the minimap. They now end one
##   [constant HudLayout.GAP] to its left.
## - The control panel took 68% of the height, and covered the bottom of the
##   minimap in a 1280 x 720 and a 1366 x 768 window. It now takes 58%.
##
## Author: Nick Hobar
## Creation date: 09/29/2026

const LOG := "log"
const PANEL := "panel"
const MINIMAP := "minimap"
const XP := "xp"
const VITALS := "vitals"
const HOVER := "hover"

## The floor on each dock, before the minimum of its content. The content
## usually wins: a [TabContainer] gives the widest minimum of its tabs.
const DOCK_MIN_SIZE := Vector2(180.0, 80.0)

## The lowest opacity of an element that fades as a whole.
const WHOLE_FADE_FLOOR := 0.2

## key -> row. The row fields are the `ROW_*` constants of [HudSlot].
const ROWS := {
	LOG: {
		HudSlot.ROW_TITLE: "Game log",
		HudSlot.ROW_ANCHOR: Vector2(0.0, 1.0),
		HudSlot.ROW_OFFSET: Vector2(8.0, -8.0),
		HudSlot.ROW_SIZE: Vector2(520.0, 420.0),
		HudSlot.ROW_SHARE: Vector2(0.3, 0.5),
		HudSlot.ROW_MIN_SIZE: DOCK_MIN_SIZE,
		HudSlot.ROW_CAN_HIDE: false,
		HudSlot.ROW_FADE_BACKGROUND: true,
	},
	PANEL: {
		HudSlot.ROW_TITLE: "Control panel",
		HudSlot.ROW_ANCHOR: Vector2(1.0, 1.0),
		HudSlot.ROW_OFFSET: Vector2(-8.0, -8.0),
		HudSlot.ROW_SIZE: Vector2(460.0, 660.0),
		HudSlot.ROW_SHARE: Vector2(0.36, 0.58),
		HudSlot.ROW_MIN_SIZE: DOCK_MIN_SIZE,
		HudSlot.ROW_CAN_HIDE: false,
		HudSlot.ROW_FADE_BACKGROUND: true,
	},
	MINIMAP: {
		HudSlot.ROW_TITLE: "Minimap",
		HudSlot.ROW_ANCHOR: Vector2(1.0, 0.0),
		HudSlot.ROW_OFFSET: Vector2(-8.0, 8.0),
		HudSlot.ROW_SIZE: Vector2(242.0, 274.0),
		HudSlot.ROW_MIN_OPACITY: WHOLE_FADE_FLOOR,
	},
	XP: {
		HudSlot.ROW_TITLE: "XP drops",
		HudSlot.ROW_ANCHOR: Vector2(1.0, 0.0),
		HudSlot.ROW_OFFSET: Vector2(-258.0, 8.0),
		HudSlot.ROW_SIZE: Vector2(420.0, 212.0),
		HudSlot.ROW_MIN_OPACITY: WHOLE_FADE_FLOOR,
	},
	VITALS: {
		HudSlot.ROW_TITLE: "Vitals",
		HudSlot.ROW_ANCHOR: Vector2(0.0, 0.0),
		HudSlot.ROW_OFFSET: Vector2(8.0, 8.0),
		HudSlot.ROW_SIZE: Vector2(240.0, 64.0),
		HudSlot.ROW_MIN_OPACITY: WHOLE_FADE_FLOOR,
	},
	HOVER: {
		HudSlot.ROW_TITLE: "Hover text",
		HudSlot.ROW_EDGES: ResizeGrips.LEFT | ResizeGrips.RIGHT,
		HudSlot.ROW_MIN_OPACITY: WHOLE_FADE_FLOOR,
	},
}
