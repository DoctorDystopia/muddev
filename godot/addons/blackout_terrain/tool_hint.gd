@tool
class_name ToolHint
extends RefCounted
## The hint line at the bottom of the 3D view, and the size readout beside
## the cursor, for the Build tools (DESIGN-0013 section 6.7). The plugin
## calls [method draw] from `_forward_3d_draw_over_viewport`.
##
## The hint line names the tool, its gesture, each modifier, and the state of
## each toggle. The Sims hides its roof controls behind a key that players do
## not find. Nothing here is hidden.

## The size of the text, in pixels.
const FONT_SIZE := 15

## The space around the text of the hint line, in pixels.
const PADDING := 8.0

## The offset of the readout from the cursor, in pixels.
const READOUT_OFFSET := Vector2(18.0, -12.0)

const BAR_COLOR := Color(0.0, 0.0, 0.0, 0.65)
const TEXT_COLOR := Color(1.0, 1.0, 1.0)
const READOUT_COLOR := Color(0.6, 1.0, 0.7)


## Draw `hint` at the bottom of `overlay`, and `readout` beside `mouse` when
## it has text.
static func draw(overlay: Control, hint: String, readout: String, mouse: Vector2) -> void:
	var font := ThemeDB.fallback_font
	var lines := hint.split("\n")
	var line_height := font.get_height(FONT_SIZE)
	var bar_height := line_height * lines.size() + PADDING * 2.0
	var top := overlay.size.y - bar_height

	overlay.draw_rect(Rect2(0.0, top, overlay.size.x, bar_height), BAR_COLOR)

	for index: int in lines.size():
		var baseline := top + PADDING + line_height * index + font.get_ascent(FONT_SIZE)

		overlay.draw_string(font, Vector2(PADDING, baseline), lines[index],
			HORIZONTAL_ALIGNMENT_LEFT, overlay.size.x - PADDING * 2.0, FONT_SIZE, TEXT_COLOR)

	if readout.is_empty():
		return

	var at := mouse + READOUT_OFFSET
	var width := font.get_string_size(readout, HORIZONTAL_ALIGNMENT_LEFT, -1.0,
		FONT_SIZE).x

	overlay.draw_rect(Rect2(at - Vector2(4.0, font.get_ascent(FONT_SIZE) + 2.0),
		Vector2(width + 8.0, line_height + 4.0)), BAR_COLOR)
	overlay.draw_string(font, at, readout, HORIZONTAL_ALIGNMENT_LEFT, -1.0, FONT_SIZE,
		READOUT_COLOR)
