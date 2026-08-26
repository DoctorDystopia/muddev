class_name HelpView
extends Window
## What this client does that a telnet session does not.
##
## Deliberately NOT a copy of the game's own `help`. That command is the
## server's, it is authored beside the commands it documents, and duplicating
## any of it here would be a second copy going stale -- the same rule that keeps
## verbs and panel names out of this client. This window covers the CLIENT:
## which gestures exist and which keys do what, none of which the server knows.

const TITLE := "Client help"

## Rows are [what, does]. Presentation, and the only place in the client that
## describes the client -- the game's own `help` covers everything else.
const ENTRIES := [
	["Up / Down", "Walk the command history. A half-typed line is kept."],
	["Ctrl+F", "Find in the log. Enter steps, Escape closes."],
	["Click a tile", "Walk there, if the server offered a way."],
	["Click an NPC or item", "Whatever the server named: attack, get, cut."],
	["Drag an item", "Swap, equip or unequip."],
	["Right-click an item", "Its own actions, as the server listed them."],
	["Right-drag / Wheel", "Orbit and zoom the world view."],
	["Character", "Your sheet, panel by panel."],
	["Options", "Text size and interface scale. Saved between runs."],
	["help", "The GAME's help, which is a different and larger thing."],
]


func _init() -> void:
	title = TITLE
	size = Vector2i(430, 340)
	close_requested.connect(hide)
	hide()

	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side: String in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 12)
	add_child(margin)

	var scroller := ScrollContainer.new()
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	margin.add_child(scroller)

	var grid := GridContainer.new()
	grid.columns = 2
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_theme_constant_override("h_separation", 14)
	grid.add_theme_constant_override("v_separation", 6)
	scroller.add_child(grid)

	for entry: Array in ENTRIES:
		var what := Label.new()
		what.text = str(entry[0])
		grid.add_child(what)

		var does := Label.new()
		does.text = str(entry[1])
		does.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		does.custom_minimum_size = Vector2(250, 0)
		does.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		grid.add_child(does)


func toggle() -> void:
	if visible:
		hide()
		return

	popup_centered()
