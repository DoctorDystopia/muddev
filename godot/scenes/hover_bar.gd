class_name HoverBar
extends Label
## One line that names what is under the mouse: an item in a grid, or a thing
## or a tile in the world pane.
##
## ## Why a bar, and not only a tooltip
##
## A tooltip waits for `gui/timers/tooltip_delay_sec` and then covers the grid.
## The bar changes the moment the mouse enters a cell, and it covers nothing.
## OSRS makes the same choice: the top-left text names what is under the mouse.
##
## The bar does not decide what it says. Each grid cell gives its own
## `hover_text()`, and [WorldView] emits `hover_text_changed`. The view that
## owns the bar passes that text here. The bar is only a place.
##
## ## Why the height is reserved
##
## The bar is empty when nothing is under the mouse. An empty line that
## collapses would move the grid up and down each time the mouse leaves a cell.

## The outline behind the text in the world pane, in pixels. The world has no
## panel behind the bar, and a light tile under light text makes it unreadable.
const OUTLINE_SIZE := 4
const OUTLINE_COLOR := Color(0, 0, 0, 0.85)


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	theme_type_variation = &"RowValue"
	clip_text = true
	text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS


func _notification(what: int) -> void:
	if what != NOTIFICATION_THEME_CHANGED:
		return

	custom_minimum_size.y = ItemNameLabel.height_of_lines(self, 1)


## Give the text an outline, for a bar that stands over the 3D world and not
## over a panel.
##
## Plain strings, not `&"..."`, for the reason [ItemNameLabel] gives.
func outline() -> void:
	add_theme_constant_override("outline_size", OUTLINE_SIZE)
	add_theme_color_override("font_outline_color", OUTLINE_COLOR)


## Show one text. An empty string clears the bar.
func show_text(value: String) -> void:
	text = value


func clear() -> void:
	text = ""
