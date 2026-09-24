class_name DollLayout
extends RefCounted
## Where each equipment frame sits on the paper doll.
##
## A CLIENT fact, in the same way [MapPalette]'s colours are. The server says
## which wield locations exist and in what order to READ them
## (`SLOT_DISPLAY_ORDER`, which reaches us as the `equip_slots` frame list). It
## does not say that the head goes above the chest. That is a picture, and a
## picture belongs here.
##
## The shape is OSRS's Worn Equipment tab, which is the reference the whole
## screen follows:
##
## ```
##             head
##     back    neck    ammo
##     main    body    off
##          two hands
##             legs
##   ring L    feet    ring R
## ```
##
## ## Twelve frames into eleven OSRS squares
##
## OSRS has one weapon square and one shield square. Blackout has three hand
## slots, because `two_hands` is a slot of its own rather than a property of
## whatever sits in `main_hand`. So the two-hander gets a row to itself, and
## [constant WIDE_SLOT] names it.
##
## [EquipmentView] draws that row only while the slot is occupied. That is a
## presentation choice and not a rule about the game: the view asks whether the
## slot holds anything, never what kind of thing it holds. An empty two-hand
## frame is a square that can never be filled while a one-hander is worn, and a
## doll with a permanent dead square across the middle of it reads as a bug.
##
## ## A row shorter than the doll spans the doll
##
## That is the whole grammar of the table, and it is why there is no "which row
## is the wide one" index to keep in step with [constant ROWS]. A row of one
## entry is one frame the full width of the pane.
##
## ## A slot this table forgets still draws
##
## [constant OVERFLOW_COLUMNS] is the fallback, and it is the half of the
## asymmetry that lets the server add a wield location with no edit here: an
## unplaced frame lands in a strip under the doll. The other half is a drift
## guard in `test_client_constants.py`, which fails when a name in this table
## matches no `WieldLocation` -- because a key that names nothing is a square
## the player can never fill.
##
## Author: Nick Hobar
## Creation date: 09/21/2026

## A gap in the grid: no frame, no square, just space.
const GAP := ""

## The wide slot, drawn only while it is occupied. See the class notes.
const WIDE_SLOT := "two_hands"

## How many columns the doll has at its widest.
const COLUMNS := 3

## How many columns the leftover strip uses, for a slot [constant ROWS] does
## not place. Wider than the doll, because the case it exists for is new
## content and the cheapest thing to read is a plain strip.
const OVERFLOW_COLUMNS := 4

## The doll, row by row. Every entry is a `WieldLocation` value or
## [constant GAP], and a row with fewer than [constant COLUMNS] entries spans
## the width.
const ROWS: Array = [
	[GAP, "head", GAP],
	["back", "neck", "ammo"],
	["main_hand", "body", "off_hand"],
	["two_hands", GAP, GAP],
	[GAP, "legs", GAP],
	["main_hand_finger", "feet", "off_hand_finger"],
]


## Every slot this table places, in reading order.
##
## The view asks for this rather than walking [constant ROWS] itself, so
## "placed" has one definition: without it, a slot could be drawn twice, once
## in its own square and once in the leftover strip.
static func placed_slots() -> PackedStringArray:
	var placed := PackedStringArray()

	for row: Array in ROWS:
		for slot: String in row:
			if slot != GAP:
				placed.append(slot)

	return placed


## True when this table has a square for that slot.
static func places(slot: String) -> bool:
	return placed_slots().has(slot)


## True when that row is one frame across the whole width.
static func spans_width(row: Array) -> bool:
	return row.size() < COLUMNS
