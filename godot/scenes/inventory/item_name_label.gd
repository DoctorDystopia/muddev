class_name ItemNameLabel
extends Label
## An item's name under its picture: up to two lines, then an ellipsis.
##
## ## Why the engine cuts the name, and not a character count
##
## The bag and the pop-up used to cut a name at 14 and 11 characters. A count
## is correct at one font size only, and it cut names that had room to fit.
## Godot wraps on the drawn width and puts the ellipsis on the last visible
## line, so the name uses all of the space the cell has. The full name is in
## the tooltip and in [HoverBar].
##
## ## Why the height is set by hand
##
## A Label with autowrap AND an overrun behavior reports a minimum height of
## one pixel. Without a floor, the VBoxContainer gives the name no rows at all.
## The floor is two lines of the theme's font, so every cell in a grid has the
## same height, with a one-line name or with no name.

## Lines a name may take before the engine cuts it.
const MAX_LINES := 2


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	theme_type_variation = &"CellTitle"
	autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	max_lines_visible = MAX_LINES
	text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS


## Godot sends THEME_CHANGED when the label enters the tree, and again when the
## theme changes. Both are when the font size can change.
func _notification(what: int) -> void:
	if what != NOTIFICATION_THEME_CHANGED:
		return

	custom_minimum_size.y = height_of_lines(self, MAX_LINES)


## The height, in pixels, of `lines` lines of `label`'s own theme font.
##
## Static and shared with [HoverBar], which has the same one-pixel floor.
##
## Plain strings, not `&"..."`: `tests/test_theme.gd` reads every StringName
## literal in the client as a theme variation.
static func height_of_lines(label: Label, lines: int) -> float:
	var font := label.get_theme_font("font")
	var font_size := label.get_theme_font_size("font_size")
	var spacing := label.get_theme_constant("line_spacing")
	var line_height := font.get_height(font_size)

	return lines * line_height + (lines - 1) * spacing
