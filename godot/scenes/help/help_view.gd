class_name HelpView
extends Control
## What this client does that a telnet session does not.
##
## Deliberately NOT a copy of the game's own `help`. That command is the
## server's, it is authored beside the commands it documents, and duplicating
## any of it here would be a second copy going stale -- the same rule that keeps
## verbs and panel names out of this client. This window covers the CLIENT:
## which gestures exist and which keys do what, none of which the server knows.
##
## ## Why the text wraps at any width
##
## The player sizes this pane, and the interface scale changes its width too.
## So the code assumes no width, and no text has a line break of its own.
##
## - Both halves of a row are labels that wrap. Neither has a fixed minimum
##   width. The old second column had a minimum of 250 px. With the first
##   column, it was wider than a narrow pane, and the pane clipped the right
##   edge.
## - A [ScrollContainer] with no horizontal scroll still counts the width of
##   its content in its own minimum. Thus, a fixed width here also held the
##   control panel open.
## - Both halves share the row width by a stretch ratio, not by pixels. Every
##   row has the same split, so the columns line up.
## - A pane too narrow for two columns stacks each row: the name, then its
##   text. See [constant STACK_BELOW_EMS].
## - A `\n` in an entry is a paragraph break. It follows a full stop. A break
##   in the middle of a sentence cannot adapt to the width.

## The row width, in heights of the font, under which a row stacks its two
## halves. Side by side, the text column would be too narrow to read.
const STACK_BELOW_EMS := 22.0

## How a row side by side shares its width. A ratio and not pixels, for the
## reason in the class comment.
const NAME_SHARE := 2.0
const TEXT_SHARE := 3.0

## Two stacked rows have a gap that is this many times larger than the gap of
## two rows side by side. The eye then sees where an entry ends.
const STACKED_GAP_FACTOR := 2

## The theme type that owns the gaps. The other forms use it too.
const GAP_TYPE := &"FormGrid"

## Rows are [what, does]. Presentation, and the only place in the client that
## describes the client -- the game's own `help` covers everything else.
const ENTRIES := [
	["Up / Down", "Walk the command history. A half-typed line is kept."],
	["Ctrl+F", "Find in the log. Enter steps, Escape closes."],
	["Ctrl+Tab", "Next chat tab. Shift for the previous one."],
	["Escape / Enter", "Give the keyboard to the map, or back to the input."],
	["WASD + QEZC", "Hold to walk. W and D together walk northeast. Also HJKL + YUBN.\n"
			+ "In Options, \"WASD follows the camera\" makes W walk where the camera looks."],
	["R", "Run on or off: two tiles each tick. Also the Run button on the minimap."],
	["Click a tile", "Walk there, if the server offered a way."],
	["Click an NPC or item", "Whatever the server named: attack, get, cut."],
	["Click an item", "Its first action: equip, eat, deposit, sell."],
	["Drag an item", "Swap two squares in the bag."],
	["Right-click an item", "Its own actions, as the server listed them."],
	["Right-click the world", "Choose Option: every verb a thing affords."],
	["Middle-drag / Wheel", "Orbit and zoom the world view."],
	["Edit layout", "In Options. Move, size, hide, fade and scale each part of the screen. "
			+ "Save a layout by name, and load it again. Esc or Done closes it."],
	["Equipment tab", "What you are wearing. Click a frame to take it off."],
	["Combat tab", "Your weapon and its styles. Click one to fight that way."],
	["Character tab", "Your sheet, panel by panel."],
	["Quests tab", "What you have taken, and how far through it you are."],
	["Options tab", "Text size, interface scale, which panes are drawn."],
	["automap on", "The server stops printing the area map into the log for this client, "
			+ "because the minimap above draws it. This puts it back; "
			+ "the Options tab has buttons for it."],
	["Chat buttons", "Under the log. Click one to show only those lines. "
			+ "A dot means you missed something. Ctrl+Tab walks them."],
	["Right-click a chat button", "Set the chat mode of that tab, or hide its lines from All."],
	["Chat mode", "The name in front of the input. Click it to pick where a typed "
			+ "line goes. In a chat mode, start a line with / to send a command."],
	["help", "The GAME's help, which is a different and larger thing."],
]

var _rows: VBoxContainer

## Whether the rows are stacked now. `_arranged` is false until the first pass.
## That pass always sets the gaps, because `_init` cannot read the theme. After
## it, a pass that changes nothing returns early.
var _stacked := false
var _arranged := false


func _init() -> void:
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.theme_type_variation = &"PaneMargin"
	add_child(margin)

	var scroller := ScrollContainer.new()
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	margin.add_child(scroller)

	# The width that the scroller gives these rows is the width a row has,
	# after the scroll bar. Thus, the rows are what to measure.
	_rows = VBoxContainer.new()
	_rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_rows.resized.connect(_arrange)
	scroller.add_child(_rows)

	for entry: Array in ENTRIES:
		_rows.add_child(_row(str(entry[0]), str(entry[1])))


## One entry: its name and its text. [method _arrange] sets the box to side by
## side or to stacked.
func _row(what: String, does: String) -> BoxContainer:
	var row := BoxContainer.new()
	row.add_child(_cell(what, NAME_SHARE))
	row.add_child(_cell(does, TEXT_SHARE))
	return row


## A label that wraps at the width it gets. Its minimum width stays at the
## floor of the engine, so it never makes the row wider than the pane.
func _cell(text: String, share: float) -> Label:
	var cell := Label.new()
	cell.text = text
	cell.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	cell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	cell.size_flags_stretch_ratio = share
	return cell


## Stack the rows or set them side by side, by the width that they have now.
func _arrange() -> void:
	var stacked := _rows.size.x < _stack_width()
	if _arranged and stacked == _stacked:
		return

	_arranged = true
	_stacked = stacked
	var row_gap := _rows.get_theme_constant("v_separation", GAP_TYPE)
	var column_gap := _rows.get_theme_constant("h_separation", GAP_TYPE)

	if stacked:
		_rows.add_theme_constant_override("separation", row_gap * STACKED_GAP_FACTOR)
		column_gap = 0
	else:
		_rows.add_theme_constant_override("separation", row_gap)

	for row: BoxContainer in _rows.get_children():
		row.vertical = stacked
		row.add_theme_constant_override("separation", column_gap)


## The row width, in pixels, under which the rows stack. It follows the font of
## the labels, so a change of the theme font moves it too.
func _stack_width() -> float:
	var font_size := _rows.get_theme_font_size("font_size", "Label")
	return STACK_BELOW_EMS * font_size
