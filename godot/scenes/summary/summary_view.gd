class_name SummaryView
extends Control
## The character sheet, drawn from [SummaryState].
##
## ## A tab, and it used to be a Window
##
## The webclient's answer to a screen like this was a GoldenLayout pane -- a
## layout engine, a registration, a teardown path and a saved-config entry.
## Godot's `Window` replaced all of that and was right on the desktop; on the
## web it is an embedded subwindow inside the game canvas that cannot be moved
## beside the game, remembers no position, and has no keyboard route to it. It
## is a body in [PanelView] now, and what is left here is what was always the
## point: iterate the panels, name none of them.
##
## ## It knows no panel names, and must not learn any
##
## Every section and every row comes from whatever `char_summary` contained.
## The server's contract is that adding a band is one file under
## `systems/interface/summary/panel_defs/` — a panel table here would be the third place
## that fact lives and the first to go stale. So: iterate, never enumerate.
##
## The consequence worth stating, because it looks like a bug until you know:
## **a panel this client has never heard of renders correctly**, and a panel
## that stops being sent simply disappears. Neither needs an edit here.

## Shown when the server has sent nothing yet. Distinguished from a character
## with empty panels, which is a real and different thing.
const NO_DATA_TEXT := "No character sheet yet."

var _state: SummaryState
var _body: VBoxContainer


func _init() -> void:
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.theme_type_variation = &"PaneMargin"
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


func _rebuild() -> void:
	if _state == null:
		return

	for child: Node in _body.get_children():
		_body.remove_child(child)
		child.free()

	if not _state.has_data:
		_body.add_child(_row_label(NO_DATA_TEXT, &"RowKey"))
		return

	for panel_key: String in _state.panel_keys():
		_add_panel(panel_key)


## One section: a heading, the panel's scalar rows, then a boxed group per
## nested-dictionary field.
##
## An EMPTY panel still draws its heading. A panel reporting nothing is a real
## state — the system behind it has nothing to say today — and silently omitting
## the section would make a temporarily-quiet band indistinguishable from one
## that was removed. A panel with no scalar rows (Combat Readiness's Bonuses
## group, alone, would count) skips the empty grid rather than drawing one
## with nothing in it.
func _add_panel(panel_key: String) -> void:
	_body.add_child(_row_label(
		SummaryState.humanise(panel_key), &"PanelHeading"))

	var rows := _state.rows_for(panel_key)

	if not rows.is_empty():
		_body.add_child(_grid(rows))

	for group: Dictionary in _state.groups_for(panel_key):
		_add_group(group)

	_body.add_child(HSeparator.new())


## A plain two-column grid of rows, the shape every panel used before groups
## existed and still the shape a group's own rows use.
func _grid(rows: Array) -> GridContainer:
	var grid := GridContainer.new()
	grid.columns = 2
	grid.theme_type_variation = &"FormGrid"

	for row: Array in rows:
		grid.add_child(_row_label(str(row[0]), &"RowKey"))
		grid.add_child(_value_label(row))

	return grid


## A nested-dictionary field, boxed so its rows read as one cluster of related
## numbers -- "Bonuses" -- rather than seven more lines in the panel's own
## table with no visual break from what precedes them.
func _add_group(group: Dictionary) -> void:
	var box := PanelContainer.new()
	box.theme_type_variation = &"BonusGroup"
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var column := VBoxContainer.new()
	column.theme_type_variation = &"FormColumn"
	box.add_child(column)

	column.add_child(_row_label(str(group.get("label", "")), &"SectionHeading"))
	column.add_child(_grid(group.get("rows", [])))

	_body.add_child(box)


## A row's value label, in the "this reads as a penalty" colour when the row
## says so. The flag travels WITH the row rather than being re-derived from
## the rendered string, so a value that happens to render with a leading "-"
## for a reason that is not "this is a negative number" can never trip it.
func _value_label(row: Array) -> Label:
	var negative := row.size() > 2 and bool(row[2])
	var variation := &"RowValueNegative" if negative else &"RowValue"

	return _row_label(str(row[1]), variation)


## One label, styled by NAMING a variation rather than by carrying a size and a
## colour of its own.
##
## The three names this passes -- PanelHeading, RowKey, RowValue -- are declared
## in `ui/blackout_theme.tres` and asserted to exist by `test_theme.gd`, which
## reads this file as text. A name with no entry in the theme is a bug and is
## caught; an entry nobody names is merely unused.
func _row_label(text: String, variation: StringName) -> Label:
	var label := Label.new()
	label.text = text
	label.theme_type_variation = variation

	return label
