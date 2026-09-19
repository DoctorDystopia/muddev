class_name StackCountLabel
extends Label
## The stack count in the top-right corner of a slot, as OSRS draws it.
##
## A direct child of the slot's PanelContainer, beside the column of art and
## name. A PanelContainer gives each child the whole cell, so the label spans
## the cell and its alignment puts the text in the corner. The art stays
## where it is, and the count costs the cell no height.
##
## Both [InventorySlotCell] and [PopupSlot] use it, so the two grids draw a
## count the same way.

## A stack of one shows no count. OSRS does the same.
const HIDDEN_BELOW := 2


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	theme_type_variation = &"CellCount"
	horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	vertical_alignment = VERTICAL_ALIGNMENT_TOP
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	size_flags_vertical = Control.SIZE_EXPAND_FILL


## Show the count of one row, or nothing for a single item or an empty slot.
func show_quantity(quantity: int) -> void:
	text = count_text(quantity)


## "x40" for a stack, "" for one item. Static, so a tooltip can use the same
## words.
static func count_text(quantity: int) -> String:
	if quantity < HIDDEN_BELOW:
		return ""

	return "x%d" % quantity
