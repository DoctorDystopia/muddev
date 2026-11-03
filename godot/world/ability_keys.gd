class_name AbilityKeys
extends RefCounted
## Which key fires which slot of the ability rail.
##
## ## The client owns the keys
##
## The server sends the rows of `char_abilities` in the order of its
## registry, and names no key. The slot of a row is its index. This table
## says which key presses which slot. Nick chose the number row at the
## start (10/20/2026): `1` to `0`, then `-` and `=`, twelve slots.
##
## ## A combination is one more row, not a branch
##
## Each row names a keycode and the modifiers that must be held. A later
## `Shift+1` is a row with `shift` true, and nothing else changes. The
## match asks the event for its modifiers, so a row with `shift` false
## does not fire when Shift is held. Thus, the two rows cannot both answer
## one press.
##
## ## The chat bar comes first
##
## The console asks this table only when the player is not typing, since
## the line edit takes every key while it has focus. Escape hands the
## keyboard to the map, as for the movement keys. See
## [method Console._unhandled_key_input].
##
## Author: Nick Hobar
## Creation date: 10/20/2026

const ROW_KEYCODE := "keycode"
const ROW_SHIFT := "shift"
const ROW_LABEL := "label"

## No slot answers the key.
const NO_SLOT := -1

## slot index -> row. The order is the order of the slots, so the first
## row is the first key.
const SLOTS: Array = [
	{ROW_KEYCODE: KEY_1, ROW_SHIFT: false, ROW_LABEL: "1"},
	{ROW_KEYCODE: KEY_2, ROW_SHIFT: false, ROW_LABEL: "2"},
	{ROW_KEYCODE: KEY_3, ROW_SHIFT: false, ROW_LABEL: "3"},
	{ROW_KEYCODE: KEY_4, ROW_SHIFT: false, ROW_LABEL: "4"},
	{ROW_KEYCODE: KEY_5, ROW_SHIFT: false, ROW_LABEL: "5"},
	{ROW_KEYCODE: KEY_6, ROW_SHIFT: false, ROW_LABEL: "6"},
	{ROW_KEYCODE: KEY_7, ROW_SHIFT: false, ROW_LABEL: "7"},
	{ROW_KEYCODE: KEY_8, ROW_SHIFT: false, ROW_LABEL: "8"},
	{ROW_KEYCODE: KEY_9, ROW_SHIFT: false, ROW_LABEL: "9"},
	{ROW_KEYCODE: KEY_0, ROW_SHIFT: false, ROW_LABEL: "0"},
	{ROW_KEYCODE: KEY_MINUS, ROW_SHIFT: false, ROW_LABEL: "-"},
	{ROW_KEYCODE: KEY_EQUAL, ROW_SHIFT: false, ROW_LABEL: "="},
]


## The key that fires the set row (DESIGN-0015, 10/30/2026): the quick
## prayer orb. The backtick, to the left of the number row. The set row is
## no slot, because its place in the list moves with the count of the
## abilities. [method is_set_key] answers it.
const SET_KEYCODE := KEY_QUOTELEFT
const SET_LABEL := "`"


## True when the press fires the set row. Shift, Ctrl, Alt and Meta all
## refuse it, as for a slot.
static func is_set_key(event: InputEventKey) -> bool:
	if event.ctrl_pressed or event.alt_pressed or event.meta_pressed or event.shift_pressed:
		return false

	return event.keycode == SET_KEYCODE


## The slot whose step dial one press turns, or [constant NO_SLOT]: Shift
## and the key of the slot (DESIGN-0015). A row of the table with `shift`
## true is a slot of its own, so it never answers here.
static func step_slot_for(event: InputEventKey) -> int:
	if event.ctrl_pressed or event.alt_pressed or event.meta_pressed:
		return NO_SLOT

	if not event.shift_pressed:
		return NO_SLOT

	for slot: int in SLOTS.size():
		var row: Dictionary = SLOTS[slot]

		if bool(row[ROW_SHIFT]):
			continue

		if event.keycode == row[ROW_KEYCODE]:
			return slot

	return NO_SLOT


## The slot that one key press fires, or [constant NO_SLOT].
##
## A press with Ctrl, Alt or Meta held answers no slot. Those belong to
## the window and the browser, as for the movement keys.
static func slot_for(event: InputEventKey) -> int:
	if event.ctrl_pressed or event.alt_pressed or event.meta_pressed:
		return NO_SLOT

	for slot: int in SLOTS.size():
		var row: Dictionary = SLOTS[slot]

		if event.keycode != row[ROW_KEYCODE]:
			continue

		if event.shift_pressed != bool(row[ROW_SHIFT]):
			continue

		return slot

	return NO_SLOT


## The label of one slot, for the corner of its button. Empty past the last
## key, for a row that no key fires.
static func label_for(slot: int) -> String:
	if slot < 0 or slot >= SLOTS.size():
		return ""

	return str(SLOTS[slot][ROW_LABEL])


## How many slots a key fires. A row past this count has a button and no
## key.
static func slot_count() -> int:
	return SLOTS.size()
