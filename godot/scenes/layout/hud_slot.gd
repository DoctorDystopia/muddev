class_name HudSlot
extends RefCounted
## One HUD element that the player can place: its control, and where it sits
## before the player moves it.
##
## A slot is data. [HudArranger] places the control, and [LayoutEditor] draws
## a frame over it. Neither of them knows what the control holds. A new HUD
## element is thus one row in the `HUD_ELEMENTS` table of the console, and one
## control.
##
## Author: Nick Hobar
## Creation date: 09/29/2026

## The fields of a row in the console's table. See [method from_row].
const ROW_TITLE := "title"
const ROW_ANCHOR := "anchor"
const ROW_OFFSET := "offset"
const ROW_SIZE := "size"
const ROW_SHARE := "share"
const ROW_MIN_SIZE := "min_size"
const ROW_EDGES := "edges"
const ROW_CAN_HIDE := "can_hide"
const ROW_FADE_BACKGROUND := "fade_background"
const ROW_MIN_OPACITY := "min_opacity"

## The key of the element in the saved layout. Never shown to the player.
var key: String

## The name of the element in the layout editor.
var title: String

## The control that the arranger moves, sizes, scales and fades.
var control: Control

## Where the element sits before the player moves it. See [HudLayout].
var default_anchor := Vector2.ZERO
var default_offset := Vector2.ZERO

## The size before the player sizes it. Zero takes the minimum of the control.
var default_size := Vector2.ZERO

## The largest part of the room, on each axis, that the shipped size takes.
## Zero on an axis sets no limit. A size that suits a 1920 x 1080 window
## covered the minimap in a 1280 x 720 window.
var default_share := Vector2.ZERO

## The shipped rect, for an element whose place depends on other elements.
## Called with the pane size. It replaces the anchor, the offset and the size
## until the player moves the element. See the world hover bar.
var default_rect := Callable()

## The floor on the size. The minimum of the control wins when it is larger.
var min_size := Vector2.ZERO

## The edges that the player can drag, as [ResizeGrips] bits. Zero makes an
## element that moves but does not change size.
var resize_edges := ResizeGrips.ALL_EDGES

## False for an element that the player must not hide. The control panel holds
## Options, and the log holds the input.
var can_hide := true

## True to fade only the background of the element, and not its text. The log
## and the control panel fade this way, so a clear log is still a log that the
## player can read.
var fade_background := false

## The lowest opacity. An element that fades as a whole needs a floor, or the
## player makes it invisible and cannot find it. Hide does that job.
var min_opacity := HudLayout.MIN_OPACITY


func _init(slot_key: String, slot_title: String, slot_control: Control) -> void:
	key = slot_key
	title = slot_title
	control = slot_control


## A slot from one row of a table. A field that the row leaves out keeps its
## default.
static func from_row(slot_key: String, row: Dictionary, slot_control: Control) -> HudSlot:
	var slot := HudSlot.new(slot_key, str(row.get(ROW_TITLE, slot_key)), slot_control)
	slot.default_anchor = row.get(ROW_ANCHOR, slot.default_anchor)
	slot.default_offset = row.get(ROW_OFFSET, slot.default_offset)
	slot.default_size = row.get(ROW_SIZE, slot.default_size)
	slot.default_share = row.get(ROW_SHARE, slot.default_share)
	slot.min_size = row.get(ROW_MIN_SIZE, slot.min_size)
	slot.resize_edges = row.get(ROW_EDGES, slot.resize_edges)
	slot.can_hide = row.get(ROW_CAN_HIDE, slot.can_hide)
	slot.fade_background = row.get(ROW_FADE_BACKGROUND, slot.fade_background)
	slot.min_opacity = row.get(ROW_MIN_OPACITY, slot.min_opacity)

	return slot
