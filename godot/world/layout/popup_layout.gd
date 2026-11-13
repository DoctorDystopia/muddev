class_name PopupLayout
extends RefCounted
## Where each slot of a laid-out pop-up grid sits. The body doll of the
## Augmentation Rig is the one layout today (11/09/2026).
##
## A CLIENT fact, as [DollLayout] is for worn gear. The server names the
## layout of a grid (`layout`) and the place of each row (`place`). It does not
## say that the head socket goes above the body socket. That is a picture, and
## a picture belongs here.
##
## The rig doll faces the player, as the paper doll does. Thus the right arm
## sits on the left of the screen, where the paper doll draws the main hand:
##
## ```
##                 head
##              neural code
##   right arm     body      left arm
##   right leg   skeleton    left leg
## ```
##
## ## A layout or a place that this table does not know still draws
##
## A layout key with no entry in [constant LAYOUTS] draws the plain grid. A row
## whose place the doll does not hold goes in a plain block under the doll.
## Thus the server can add a socket with no edit here. The other half of the
## rule is a drift guard in `test_client_constants.py`. It fails when a place
## in this table names no socket, because that square can never fill.
##
## Author: Nick Hobar
## Creation date: 11/09/2026

const _Const := preload("res://autoload/blackout_constants.gd")

## A gap in the doll: no slot, only space the width of a slot.
const GAP := ""

## The columns of every doll. Each row of a doll has this many entries.
const COLUMNS := 3

## The body doll of the rig, row by row. Each entry is a socket key of
## `systems/gameplay/augmentation/constants.py`, or [constant GAP].
const RIG_ROWS: Array = [
	[GAP, "neural_code", GAP],
	[GAP, "head", GAP],
	["right_arm", "body", "left_arm"],
	[GAP, "skeleton", GAP],
	["right_leg", GAP, "left_leg"],
]

## Layout key -> the rows of its doll. The key comes from the generated
## constants. Thus a rename on the server cannot leave a dead entry.
const LAYOUTS: Dictionary = {
	_Const.POPUP_LAYOUT_RIG: RIG_ROWS,
}


## The rows of the doll for a layout key, or `[]` for a plain grid.
static func rows_for(layout: String) -> Array:
	return LAYOUTS.get(layout, [])


## True when a doll has a square for that place.
static func places(rows: Array, place: String) -> bool:
	if place == GAP:
		return false

	for line: Array in rows:
		if line.has(place):
			return true

	return false
