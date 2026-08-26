class_name SummaryView
extends Window
## The character sheet, drawn from [SummaryState].
##
## ## A Window, because Godot has one
##
## The webclient's answer to a screen like this was a GoldenLayout pane, which
## meant a layout engine, a registration, a teardown path and a saved-config
## entry. Godot has `Window`: it floats, it is movable and resizable, the engine
## draws the chrome, and closing it is a signal. That is the native answer and
## it is most of the reason this file is short.
##
## ## It knows no panel names, and must not learn any
##
## Every section and every row comes from whatever `char_summary` contained.
## The server's contract is that adding a band is one file under
## `systems/summary/panel_defs/` — a panel table here would be the third place
## that fact lives and the first to go stale. So: iterate, never enumerate.
##
## The consequence worth stating, because it looks like a bug until you know:
## **a panel this client has never heard of renders correctly**, and a panel
## that stops being sent simply disappears. Neither needs an edit here.

const TITLE := "Character"

const PANEL_FONT_SIZE := 13
const ROW_FONT_SIZE := 12
const LABEL_COLOR := Color(0.62, 0.66, 0.72)

## Shown when the server has sent nothing yet. Distinguished from a character
## with empty panels, which is a real and different thing.
const NO_DATA_TEXT := "No character sheet yet."

var _state: SummaryState
var _body: VBoxContainer


func _init() -> void:
	title = TITLE
	size = Vector2i(360, 480)
	# The engine owns the close button; this is just what it does.
	close_requested.connect(hide)
	hide()

	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override("margin_left", 10)
	margin.add_theme_constant_override("margin_right", 10)
	margin.add_theme_constant_override("margin_top", 8)
	margin.add_theme_constant_override("margin_bottom", 8)
	add_child(margin)

	var scroller := ScrollContainer.new()
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	margin.add_child(scroller)

	_body = VBoxContainer.new()
	_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroller.add_child(_body)


## Bind to a model and follow it.
func bind(state: SummaryState) -> void:
	_state = state
	_state.changed.connect(_rebuild)
	_rebuild()


## Show or hide. The console wires this to a button.
func toggle() -> void:
	if visible:
		hide()
		return

	popup_centered()


func _rebuild() -> void:
	if _state == null:
		return

	for child: Node in _body.get_children():
		_body.remove_child(child)
		child.free()

	if not _state.has_data:
		_body.add_child(_row_label(NO_DATA_TEXT, LABEL_COLOR, ROW_FONT_SIZE))
		return

	for panel_key: String in _state.panel_keys():
		_add_panel(panel_key)


## One section: a heading, then the panel's rows.
##
## An EMPTY panel still draws its heading. A panel reporting nothing is a real
## state — the system behind it has nothing to say today — and silently omitting
## the section would make a temporarily-quiet band indistinguishable from one
## that was removed.
func _add_panel(panel_key: String) -> void:
	_body.add_child(_row_label(
		SummaryState.humanise(panel_key), Color.WHITE, PANEL_FONT_SIZE))

	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 12)
	_body.add_child(grid)

	for row: Array in _state.rows_for(panel_key):
		grid.add_child(_row_label(str(row[0]), LABEL_COLOR, ROW_FONT_SIZE))
		grid.add_child(_row_label(str(row[1]), Color.WHITE, ROW_FONT_SIZE))

	_body.add_child(HSeparator.new())


func _row_label(text: String, colour: Color, size_px: int) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", size_px)
	label.add_theme_color_override("font_color", colour)

	return label
