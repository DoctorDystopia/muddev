class_name PopupView
extends Control
## The pop-up over the world pane, drawn from [PopupState]: the bank, a shop,
## a crafting station, and every EvMenu node.
##
## ## Why a Control over the pane, and not a Window
##
## [SummaryView] records the answer: a native `Window` on the web is an embedded
## subwindow that cannot move beside the game and has no keyboard route to it.
## So this is what [ChooseOption] is: a full-pane Control that OWNS the pane's
## clicks while it shows. A click beside the box must not walk the player to
## the tile under it, and the SubViewportContainer below forwards every mouse
## event it gets into the 3D world.
##
## ## It closes when the SERVER says so
##
## The close button and Escape send the server's `close_command`. The box goes
## away when the closed snapshot arrives, not on the click — the rule
## [PopupState] states for every click.
##
## ## It rebuilds wholesale, and keeps the scroll
##
## Every snapshot rebuilds every slot, for the reason [InventoryView] gives. A
## withdraw sends a snapshot, so a rebuild that forgot the scroll position
## would jump a long vault to the top after every click. The position of each
## grid survives a rebuild of the same pop-up.
##
## ## The player moves it and sizes it
##
## The box floats in the pane. A drag on the title bar moves it, and a drag on
## the grip in its bottom-right corner sizes it. The grid reflows its columns
## to the new width. The rect survives a close and a reopen, and it stays
## inside the pane when the pane itself changes size. This is presentation
## only, so the server never hears of it.
##
## ## One grid, and a side panel
##
## The inventory pane beside the world is the player's bag, so a pop-up draws
## no copy of it. The server puts Deposit or Sell first on each bag row while
## the pop-up is open. The side of the box shows [TimerPanel] when the server
## sends timers: the curing chamber's slots, with a bar for each.

## Emitted with a whole command a telnet player could have typed.
signal command_requested(command: String)

## Emitted when the menu's text box had the keyboard and is about to hide. The
## console gives the keyboard back to the game input, as it does when the find
## bar closes. Without this, focus falls to nothing, and the next letter the
## player types walks them.
signal keyboard_released

## How far the box stays inside the pane, in pixels.
const EDGE_MARGIN := 16.0

## The first size of the box, as a part of the pane. The player's own size
## replaces it after the first drag.
const DEFAULT_FRACTION := Vector2(0.8, 0.85)

## The smallest box a drag can make, in pixels. The box's own minimum size wins
## when it is larger.
const MIN_BOX_SIZE := Vector2(260, 180)

## The resize grip in the box's bottom-right corner, in pixels.
const GRIP_SIZE := 14.0
const GRIP_COLOR := Color(1, 1, 1, 0.35)

## The gap between two slots of a grid, for the column count. Godot's
## GridContainer default.
const SLOT_GAP := 4.0

## How much of the width each grid takes, the first against the rest. The
## server sends one grid today. A second grid is presentation, so it is kept.
const WIDE_RATIO := 3.0
const NARROW_RATIO := 2.0

## What a drag does: move the box, or size it.
const DRAG_NONE := ""
const DRAG_MOVE := "move"
const DRAG_SIZE := "size"

## The dim over the world behind the box.
const BACKDROP_COLOR := Color(0, 0, 0, 0.35)

const CLOSE_TEXT := "Close"
const QUANTITY_TEXT := "Quantity:"
const EMPTY_GRID_TEXT := "Nothing here."

var _state: PopupState
var _meshes: MeshResolver

var _box: PanelContainer
var _grip: Control
var _title: Label
var _status: Label
var _grids: HBoxContainer
var _timers: TimerPanel

## The player's box, in pane pixels, or an empty rect before the first drag.
var _box_rect := Rect2()

## One of the DRAG_* values.
var _drag := DRAG_NONE

## The EvMenu half: the node text and one button for each choice in one
## scroll, and a text box under it.
var _menu_body: VBoxContainer
var _menu_scroll: ScrollContainer
var _menu_text: RichTextLabel
var _menu_options: VBoxContainer
var _menu_input: LineEdit
var _quantity: HBoxContainer
var _footer: HBoxContainer
var _stage: ItemStage

## The full text of the slot under the mouse. See [HoverBar].
var _bar: HoverBar

## `[grid_index, slot]` of the slot under the mouse, or `[]`. A key and not
## the slot, for the reason [InventoryView] gives: a rebuild frees every slot.
var _hover_key: Array = []

## grid index -> ScrollContainer, for the scroll that survives a rebuild.
var _scrollers: Array = []

## The key of the pop-up the scroll positions belong to.
var _shown_key := ""


func _init() -> void:
	visible = false
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	resized.connect(_place_box)

	var backdrop := ColorRect.new()
	backdrop.color = BACKDROP_COLOR
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	backdrop.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(backdrop)

	_box = PanelContainer.new()
	_box.theme_type_variation = &"PopupBox"
	_box.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_box)

	var margin := MarginContainer.new()
	margin.theme_type_variation = &"PaneMargin"
	_box.add_child(margin)

	var column := VBoxContainer.new()
	margin.add_child(column)

	column.add_child(_header())

	_status = Label.new()
	_status.theme_type_variation = &"RowValue"
	column.add_child(_status)

	column.add_child(_body())

	_bar = HoverBar.new()
	column.add_child(_bar)

	_quantity = HBoxContainer.new()
	column.add_child(_quantity)

	_footer = HBoxContainer.new()
	column.add_child(_footer)

	_grip = _build_grip()
	add_child(_grip)

	# A child of this control, so it stops rendering whenever the box is
	# hidden. See [ItemStage] on one render target for every slot.
	_stage = ItemStage.new()
	add_child(_stage)


## Bind to a model and a mesh source, and follow them.
func bind(state: PopupState, resolver: MeshResolver) -> void:
	_state = state
	_meshes = resolver
	_state.changed.connect(_rebuild)

	if _meshes != null:
		_meshes.refreshed.connect(func(_key: String): _rebuild())

	_rebuild()


## The slot controls of one grid, in slot order. For tests.
func slots_in(grid_index: int) -> Array:
	var found: Array = []

	if grid_index < 0 or grid_index >= _scrollers.size():
		return found

	var scroller: ScrollContainer = _scrollers[grid_index]

	for child: Node in scroller.get_child(0).get_children():
		if child is PopupSlot:
			found.append(child)

	return found


## The columns of one grid now. For tests.
func columns_in(grid_index: int) -> int:
	if grid_index < 0 or grid_index >= _scrollers.size():
		return 0

	var scroller: ScrollContainer = _scrollers[grid_index]

	return (scroller.get_child(0) as GridContainer).columns


## The footer buttons, in order. For tests.
func footer_buttons() -> Array:
	var found: Array = []

	for child: Node in _footer.get_children():
		if child is Button:
			found.append(child)

	return found


## The quantity buttons, in order. For tests.
func quantity_buttons() -> Array:
	var found: Array = []

	for child: Node in _quantity.get_children():
		if child is Button:
			found.append(child)

	return found


## Ask the server to close. Public so a test can press it with no mouse.
func request_close() -> void:
	if _state == null or _state.close_command.is_empty():
		return

	command_requested.emit(_state.close_command)


func title_text() -> String:
	return _title.text


func status_text() -> String:
	return _status.text


func hover_bar_text() -> String:
	return _bar.text


## The side panel. For tests.
func timer_panel() -> TimerPanel:
	return _timers


## The box's rect in the pane. For tests.
func box_rect() -> Rect2:
	return Rect2(_box.position, _box.size)


## Size the box as a drag on the grip would. Public so a test can size it with
## no mouse.
func resize_box(new_size: Vector2) -> void:
	_box_rect = Rect2(_box.position, new_size)
	_place_box()


## Move the box as a drag on the title bar would. For tests.
func move_box(new_position: Vector2) -> void:
	_box_rect = Rect2(new_position, _box.size)
	_place_box()


# ─── Input ───────────────────────────────────────────────────────────────────

## Escape asks to close, from anywhere, while the box shows. A number key
## picks the menu choice with that key, as typing it would.
func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return

	if event.is_action_pressed("ui_cancel"):
		request_close()
		get_viewport().set_input_as_handled()
		return

	var command := _option_for_key(event)

	if command.is_empty():
		return

	command_requested.emit(command)
	get_viewport().set_input_as_handled()


## The choice command a key press names, or "". Only a plain press of a key
## that types one character counts, so Ctrl+1 and a held key do nothing.
func _option_for_key(event: InputEvent) -> String:
	if not (event is InputEventKey) or _state == null:
		return ""

	var key := event as InputEventKey

	if not key.pressed or key.echo or key.ctrl_pressed or key.alt_pressed:
		return ""

	if key.unicode == 0:
		return ""

	return _state.option_command(char(key.unicode))


## The text the menu's box would send, as if typed. For tests.
func submit_menu_input(typed: String) -> void:
	_on_menu_input(typed)


## The choice buttons, in order. For tests.
func menu_option_buttons() -> Array:
	var found: Array = []

	for child: Node in _menu_options.get_children():
		if child is Button:
			found.append(child)

	return found


func menu_text() -> String:
	return _menu_text.text


func menu_input_shown() -> bool:
	return _menu_input.visible


# ─── Building ────────────────────────────────────────────────────────────────

## The title bar: the title, the close button, and the handle a drag moves the
## box by.
func _header() -> Control:
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_STOP
	row.mouse_default_cursor_shape = Control.CURSOR_MOVE
	row.gui_input.connect(_on_header_input)

	_title = Label.new()
	_title.theme_type_variation = &"PanelHeading"
	_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(_title)

	var close := Button.new()
	close.text = CLOSE_TEXT
	close.pressed.connect(request_close)
	row.add_child(close)

	return row


## The grids or the menu, and the side panel beside them.
func _body() -> Control:
	var row := HBoxContainer.new()
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL

	_grids = HBoxContainer.new()
	_grids.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(_grids)

	row.add_child(_build_menu_body())

	_timers = TimerPanel.new()
	row.add_child(_timers)

	return row


func _rebuild() -> void:
	if _state == null:
		return

	# Asked BEFORE anything hides, while the box can still say it has focus.
	var had_keyboard := _menu_input.has_focus()

	visible = _state.is_open

	if not _state.is_open:
		_clear_closed()
		_release_keyboard(had_keyboard)
		return

	var kept := _scroll_positions()

	# Kept BEFORE the build, for the reason [InventoryView] gives. A different
	# pop-up has different grids, so its hover starts empty.
	var hovered_key := _hover_key if _state.key == _shown_key else []

	_title.text = _state.title
	_status.text = _state.status
	_status.visible = not _state.status.is_empty()
	_build_grids()
	_timers.show_timers(_state)
	_build_quantity()
	_build_footer()
	_build_menu()
	_release_keyboard(had_keyboard and not _menu_input.visible)
	_restore_scroll(kept)
	_restore_hover(hovered_key)
	_shown_key = _state.key

	# Deferred: the first open, and a pane that changed size while the box was
	# hidden, both need the layout pass that sizes this control.
	_place_box.call_deferred()


func _clear_closed() -> void:
	_shown_key = ""
	_clear(_grids)
	_clear(_quantity)
	_clear(_footer)
	_clear(_menu_options)
	_menu_text.text = ""
	_scrollers = []
	_stage.reserve(0)
	_restore_hover([])
	_timers.show_timers(_state)


## One column per grid: a heading and a scrolling grid of slots.
##
## Stage indices run across all grids in order, so no two slots claim the same
## pixels of the one render target.
func _build_grids() -> void:
	_clear(_grids)
	_scrollers = []

	var total := 0

	for entry: Dictionary in _state.grids:
		total += int(entry["slots_total"])

	_stage.reserve(total)

	var first_index := 0

	for grid_index: int in range(_state.grids.size()):
		var entry: Dictionary = _state.grids[grid_index]
		_grids.add_child(_grid_column(grid_index, entry, first_index))
		first_index += int(entry["slots_total"])


func _grid_column(grid_index: int, entry: Dictionary, first_index: int) -> Control:
	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.size_flags_stretch_ratio = WIDE_RATIO if grid_index == 0 else NARROW_RATIO

	var heading := Label.new()
	heading.theme_type_variation = &"SectionHeading"
	heading.text = str(entry["title"])
	column.add_child(heading)

	var scroller := ScrollContainer.new()
	scroller.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(scroller)
	_scrollers.append(scroller)

	var grid := GridContainer.new()
	grid.columns = _columns_for(scroller.size.x)
	scroller.add_child(grid)
	scroller.resized.connect(_reflow.bind(scroller, grid))

	var slots_total := int(entry["slots_total"])

	if slots_total == 0:
		var empty := Label.new()
		empty.text = EMPTY_GRID_TEXT
		grid.add_child(empty)
		return column

	for slot: int in range(slots_total):
		grid.add_child(_slot(grid_index, slot, first_index + slot))

	return column


## As many columns as the width fits, and at least one.
static func _columns_for(width: float) -> int:
	var pitch := PopupSlot.SLOT_SIZE.x + SLOT_GAP

	return maxi(1, floori((width + SLOT_GAP) / pitch))


## Fit the columns to the scroller after a resize: of the box, or of the pane.
func _reflow(scroller: ScrollContainer, grid: GridContainer) -> void:
	var wanted := _columns_for(scroller.size.x)

	if grid.columns != wanted:
		grid.columns = wanted


func _slot(grid_index: int, slot: int, stage_index: int) -> PopupSlot:
	var cell := PopupSlot.new()
	var row := _state.row_at(grid_index, slot)
	cell.bind(row)
	cell.command_requested.connect(command_requested.emit)
	cell.hovered.connect(_on_slot_hovered.bind(cell, grid_index, slot))
	cell.unhovered.connect(_on_slot_unhovered.bind(grid_index, slot))

	if not row.is_empty():
		_stage.place(stage_index, str(row.get("asset", "")),
			str(row.get("family", "")), _meshes)
		cell.show_art(_stage.texture_for(stage_index))

	return cell


## The 1 / 5 / 10 / X / All row. The active button is drawn pressed, from the
## snapshot, and a press sends and changes nothing else.
func _build_quantity() -> void:
	_clear(_quantity)

	if _state.quantity.is_empty():
		return

	var label := Label.new()
	label.text = QUANTITY_TEXT
	_quantity.add_child(label)

	for button_data: Dictionary in _state.quantity:
		_quantity.add_child(_quantity_button(button_data))


func _quantity_button(button_data: Dictionary) -> Button:
	var button := Button.new()
	button.text = str(button_data.get("label", ""))
	button.toggle_mode = true
	button.button_pressed = bool(button_data.get("active", false))
	button.pressed.connect(func() -> void:
		# Put the look back to the snapshot at once. The server's next
		# snapshot is what lights a new mode.
		button.set_pressed_no_signal(bool(button_data.get("active", false)))
		_send_action(button_data)
	)

	return button


## The EvMenu half. Hidden for a grid pop-up.
##
## The text is a RichTextLabel with the log's own theme variation, because a
## node is game text: the same BBCode the log shows, with the same mono font
## that the menu's tables line up in.
##
## The text and the choices share ONE scroll. The text takes the height of its
## content and the choices follow it. A long node thus scrolls down to its
## choices, and many choices cannot squeeze the text to nothing. Two areas that
## split the height did both.
func _build_menu_body() -> Control:
	_menu_body = VBoxContainer.new()
	_menu_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_menu_body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_menu_body.visible = false

	_menu_scroll = ScrollContainer.new()
	_menu_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_menu_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_menu_body.add_child(_menu_scroll)

	var content := VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_menu_scroll.add_child(content)

	_menu_text = RichTextLabel.new()
	_menu_text.theme_type_variation = &"ChatLog"
	_menu_text.bbcode_enabled = true
	_menu_text.fit_content = true
	_menu_text.scroll_active = false
	_menu_text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_child(_menu_text)

	_menu_options = VBoxContainer.new()
	content.add_child(_menu_options)

	_menu_input = LineEdit.new()
	_menu_input.text_submitted.connect(_on_menu_input)
	_menu_body.add_child(_menu_input)

	return _menu_body


func _build_menu() -> void:
	var is_menu := _state.is_menu()
	_menu_body.visible = is_menu
	_grids.visible = not is_menu
	_clear(_menu_options)
	_menu_text.text = _state.text
	# A new node starts at its top. Each node is a new screen, not the same
	# list after a click, so it has no scroll to keep.
	_menu_scroll.set_deferred("scroll_vertical", 0)

	for option: Dictionary in _state.choices:
		var button := Button.new()
		button.text = "%s  %s" % [str(option.get("key", "")), str(option.get("label", ""))]
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.pressed.connect(_send_action.bind(option))
		_menu_options.add_child(button)

	var asks := not _state.input.is_empty()
	_menu_input.visible = asks
	_menu_input.placeholder_text = str(_state.input.get("label", ""))

	if asks:
		_menu_input.clear()
		_menu_input.grab_focus.call_deferred()


func _release_keyboard(released: bool) -> void:
	if released:
		keyboard_released.emit()


## Send what the player typed, verbatim: a quantity prompt reads it as its
## answer, the way it reads a telnet line. Empty text sends nothing.
func _on_menu_input(typed: String) -> void:
	var line := typed.strip_edges()
	_menu_input.clear()

	if line.is_empty():
		return

	command_requested.emit(line)


## The buttons under the grids: whatever the server offers for the pop-up as
## a whole. Plain buttons, each sending its whole command.
func _build_footer() -> void:
	_clear(_footer)

	for button_data: Dictionary in _state.footer:
		var button := Button.new()
		button.text = str(button_data.get("label", ""))
		button.pressed.connect(_send_action.bind(button_data))
		_footer.add_child(button)


## Send one action the server named, asking first when it is prompted.
func _send_action(action: Dictionary) -> void:
	var prompt := ServerAction.prompt(action)

	if not prompt.is_empty():
		AmountPrompt.ask(self, action, prompt, command_requested.emit)
		return

	var command := ServerAction.command(action)

	if command.is_empty():
		return

	command_requested.emit(command)


func _scroll_positions() -> Array:
	var kept: Array = []

	if _state.key != _shown_key:
		return kept

	for scroller: ScrollContainer in _scrollers:
		kept.append(scroller.scroll_vertical)

	return kept


## Deferred, because a new grid has no size until the next layout pass, and a
## ScrollContainer clamps a position its content cannot reach yet.
func _restore_scroll(kept: Array) -> void:
	for index: int in range(mini(kept.size(), _scrollers.size())):
		var scroller: ScrollContainer = _scrollers[index]
		scroller.set_deferred("scroll_vertical", kept[index])


# ─── Moving and sizing the box ───────────────────────────────────────────────

## Put the box at the player's rect, or at the default, kept inside the pane.
func _place_box() -> void:
	var pane := size

	# The grip is null while _init still builds the box.
	if _grip == null or pane.x <= 0.0 or pane.y <= 0.0:
		return

	var rect := _box_rect if _box_rect.has_area() else _default_rect(pane)
	var inset := Vector2.ONE * EDGE_MARGIN
	var room := (pane - inset * 2.0).max(Vector2.ONE)
	var smallest := MIN_BOX_SIZE.max(_box.get_combined_minimum_size()).min(room)

	rect.size = rect.size.clamp(smallest, room)
	rect.position = rect.position.clamp(inset, pane - rect.size - inset)

	_box.position = rect.position
	_box.size = rect.size
	_grip.position = rect.end - Vector2.ONE * GRIP_SIZE


static func _default_rect(pane: Vector2) -> Rect2:
	var box_size := pane * DEFAULT_FRACTION

	return Rect2((pane - box_size) / 2.0, box_size)


func _build_grip() -> Control:
	var grip := Control.new()
	grip.size = Vector2.ONE * GRIP_SIZE
	grip.mouse_filter = Control.MOUSE_FILTER_STOP
	grip.mouse_default_cursor_shape = Control.CURSOR_FDIAGSIZE
	grip.gui_input.connect(_on_grip_input)
	grip.draw.connect(_draw_grip.bind(grip))

	return grip


## A small triangle in the corner, the usual sign of a resize handle.
func _draw_grip(grip: Control) -> void:
	var corner := Vector2.ONE * GRIP_SIZE
	var points := PackedVector2Array(
		[Vector2(corner.x, 0), corner, Vector2(0, corner.y)])
	grip.draw_colored_polygon(points, GRIP_COLOR)


func _on_header_input(event: InputEvent) -> void:
	_follow_drag(event, DRAG_MOVE)


func _on_grip_input(event: InputEvent) -> void:
	_follow_drag(event, DRAG_SIZE)


## A left press starts the drag, motion moves it, and the release ends it.
## The control that took the press gets the motion until the release, so the
## drag follows the mouse off the title bar.
func _follow_drag(event: InputEvent, kind: String) -> void:
	if event is InputEventMouseButton:
		var click := event as InputEventMouseButton

		if click.button_index == MOUSE_BUTTON_LEFT:
			_drag = kind if click.pressed else DRAG_NONE
			accept_event()

		return

	if not (event is InputEventMouseMotion) or _drag != kind:
		return

	var motion := (event as InputEventMouseMotion).relative
	var rect := Rect2(_box.position, _box.size)

	if kind == DRAG_MOVE:
		rect.position += motion
	else:
		rect.size += motion

	_box_rect = rect
	_place_box()
	accept_event()


# ─── The hover bar ───────────────────────────────────────────────────────────

func _on_slot_hovered(cell: PopupSlot, grid_index: int, slot: int) -> void:
	_hover_key = [grid_index, slot]
	_bar.show_text(cell.hover_text())


## Clears only when the slot that leaves is the one the bar names, for the
## reason [InventoryView] gives.
func _on_slot_unhovered(grid_index: int, slot: int) -> void:
	if _hover_key != [grid_index, slot]:
		return

	_hover_key = []
	_bar.clear()


## Point the bar at the new slot under the mouse after a rebuild. A withdraw
## under the mouse must show the new count, not the count before the click.
func _restore_hover(hovered_key: Array) -> void:
	_hover_key = []
	_bar.clear()

	if hovered_key.is_empty():
		return

	var slots := slots_in(int(hovered_key[0]))
	var slot := int(hovered_key[1])

	if slot >= slots.size():
		return

	_on_slot_hovered(slots[slot], int(hovered_key[0]), slot)


## Freed with free(), not queue_free(), for the reason [InventoryView] gives.
func _clear(container: Node) -> void:
	for child: Node in container.get_children():
		container.remove_child(child)
		child.free()
