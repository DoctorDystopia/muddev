class_name LayoutEditor
extends Control
## The layout editor: a mode in which the player moves, sizes, hides, fades
## and scales each HUD element, and keeps layouts by name.
##
## ## A mode, and the Options pane is the way in
##
## Outside this mode the layout is locked. No grip hangs on the log or the
## control panel, so a drag in the world never moves a box by accident. The
## "Edit layout" button in Options opens the mode. "Done" and Escape close it.
##
## While the mode is open, this control covers the whole console and takes
## every click and every key. A click in the world does not walk, and a letter
## does not move the player. [method _unhandled_key_input] takes the keys
## before the console does, because Godot gives unhandled input to a child
## before its parent.
##
## ## A frame over each element
##
## Each HUD element gets a frame with its name. A drag on the frame moves the
## element. A drag on a grip sizes it. A click selects it, and the bar at the
## top shows its settings: Shown, Opacity and Scale. A hidden element keeps a
## faint frame, so the player can find it and show it again.
##
## A drag snaps to the pane edges and to the other elements. Shift turns the
## snap off. See [method HudLayout.snap_move].
##
## ## Nothing here keeps a rect
##
## The frames follow [signal HudArranger.placed]. A drag asks the arranger to
## put the element at a rect, and the frame moves when the arranger has placed
## it. Thus a frame shows where the element IS, after each clamp.
##
## Author: Nick Hobar
## Creation date: 09/29/2026

signal opened
signal closed

## The shade over the game while the mode is open.
const DIM_COLOR := Color(0.0, 0.0, 0.0, 0.3)

## A frame: its fill, its line, and the line of a hidden element.
const FRAME_FILL := Color(1.0, 1.0, 1.0, 0.08)
const FRAME_LINE := Color(1.0, 1.0, 1.0, 0.85)
const FRAME_LINE_FAINT := Color(1.0, 1.0, 1.0, 0.35)

## The line of the selected frame. The red accent of `ui/blackout_theme.tres`.
const SELECTED_LINE := Color(0.9, 0.15, 0.13, 1.0)

const LINE_WIDTH := 1.0
const SELECTED_LINE_WIDTH := 2.0

## How far the name of an element sits inside its frame, in pixels.
const TITLE_MARGIN := 4.0

## The backdrop behind the name of an element. The name sits over the content
## of the element, and a light line of content made the name unreadable.
const TITLE_BACKDROP := Color(0.0, 0.0, 0.0, 0.75)
const TITLE_PADDING := 2.0

## What the empty preset list says.
const NO_PRESETS := "No presets"

## The smallest widths of the controls on the bar, in pixels.
const SLIDER_WIDTH := 110.0
const PRESET_WIDTH := 150.0

## The step of the opacity and the scale sliders.
const SLIDER_STEP := 0.05

## A part, as a percentage.
const PERCENT := 100.0

const TOOLBAR_TITLE := "Edit layout"
const HINT := "Click an element to select it. Drag it to move it. Drag an edge to size it. Hold Shift to stop the snap."

## The notes after the name of an element.
const NOTE_HIDDEN := "hidden"
const NOTE_OFF := "off in Options"
const NOTE_FILLED := "fills the room while the 3D world is off"

## What the bar says after a preset action.
const STATUS_SAVED := "Saved \"%s\"."
const STATUS_LOADED := "Loaded \"%s\"."
const STATUS_DELETED := "Deleted \"%s\"."
const STATUS_NO_NAME := "Type a name first."
const STATUS_FULL := "You have %d presets. Delete one first."

var _arranger: HudArranger
var _settings: ClientSettings

## key -> the frame Control, the name Label, and the ResizeGrips.
var _frames := {}
var _titles := {}
var _grips := {}

## The key of the selected element, or empty.
var _selected := ""

## The key of the element that a frame drag moves, or empty.
var _drag_key := ""

## The footprint of the element when the drag started, and the offset from
## the press. A drag applies the whole offset to the start rect.
var _drag_start := Rect2()
var _drag_offset := Vector2.ZERO

var _toolbar: PanelContainer

## True after the player drags the bar. The bar then stays where they put it.
var _toolbar_moved := false

var _preset_list: OptionButton
var _load_button: Button
var _delete_button: Button
var _preset_name: LineEdit
var _status: Label
var _hint: Label
var _element_row: HBoxContainer
var _element_title: Label
var _shown_check: CheckBox
var _opacity_slider: HSlider
var _opacity_value: Label
var _scale_slider: HSlider
var _scale_value: Label

## Set while values go INTO the controls, so their signals do not write back.
var _syncing := false


func _init() -> void:
	visible = false
	mouse_filter = Control.MOUSE_FILTER_STOP
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_build_toolbar()
	resized.connect(_place_toolbar)


## Give the editor the arranger that it edits, and the settings that keep the
## presets. One frame for each element of the arranger.
func bind(arranger: HudArranger, settings: ClientSettings) -> void:
	_arranger = arranger
	_settings = settings

	# All the frames first, then all the grips. A frame made after a grip
	# would cover that grip where the two elements meet.
	for slot: HudSlot in _arranger.slots():
		_build_frame(slot)

	for slot: HudSlot in _arranger.slots():
		_build_grips(slot)

	move_child(_toolbar, get_child_count() - 1)
	_arranger.placed.connect(_sync)
	_refresh_presets()
	_sync()


## Open the mode. The keyboard leaves the game input.
func open() -> void:
	if visible:
		return

	visible = true
	get_viewport().gui_release_focus()
	_refresh_presets()
	_sync()
	_place_toolbar()
	opened.emit()


## Close the mode, and write the layout now.
func close() -> void:
	if not visible:
		return

	visible = false
	_drag_key = ""
	_arranger.save_now()
	closed.emit()


func is_open() -> bool:
	return visible


## The key of the selected element, or empty. For tests.
func selected() -> String:
	return _selected


## Select `key`, or nothing with an empty key.
func select(key: String) -> void:
	_selected = key

	for frame: Control in _frames.values():
		frame.queue_redraw()

	_sync_element_row()


## One whole move of `key` by `offset`, as a drag on its frame gives. Public
## so a test can drag with no mouse. The mouse takes the same path.
func drag_element(key: String, offset: Vector2) -> void:
	_start(key)
	_move(key, offset)


## One whole drag of the grip of `edges` on `key`. For tests.
func size_element(key: String, edges: int, offset: Vector2) -> void:
	var grips: ResizeGrips = _grips.get(key, null)

	if grips != null:
		grips.drag(edges, offset)


## Keep the current layout as `preset_name`. Returns false when the settings
## refuse it.
func save_preset(preset_name: String) -> bool:
	var clean_name := preset_name.strip_edges()

	if clean_name.is_empty():
		_status.text = STATUS_NO_NAME
		return false

	if not _settings.save_layout_preset(clean_name, _arranger.layout()):
		_status.text = STATUS_FULL % ClientSettings.MAX_LAYOUT_PRESETS
		return false

	_status.text = STATUS_SAVED % clean_name
	_preset_name.clear()
	_refresh_presets(clean_name)

	return true


## Make the preset `preset_name` the layout. The arranger follows
## [signal ClientSettings.layout_replaced].
func load_preset(preset_name: String) -> void:
	if _settings.apply_layout_preset(preset_name):
		_status.text = STATUS_LOADED % preset_name


func delete_preset(preset_name: String) -> void:
	if preset_name.is_empty():
		return

	_settings.delete_layout_preset(preset_name)
	_status.text = STATUS_DELETED % preset_name
	_refresh_presets()


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), DIM_COLOR)


## A click on no frame selects nothing.
func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and (event as InputEventMouseButton).pressed:
		select("")
		accept_event()


## Escape closes the mode, even from the preset name box.
func _input(event: InputEvent) -> void:
	if not visible or not (event is InputEventKey):
		return

	var key_event := event as InputEventKey

	if key_event.pressed and not key_event.echo and key_event.keycode == KEY_ESCAPE:
		close()
		get_viewport().set_input_as_handled()


## Every other key stops here while the mode is open, so no key walks the
## player behind the editor.
func _unhandled_key_input(_event: InputEvent) -> void:
	if visible:
		get_viewport().set_input_as_handled()


func _build_frame(slot: HudSlot) -> void:
	var frame := Control.new()
	frame.mouse_filter = Control.MOUSE_FILTER_STOP
	frame.mouse_default_cursor_shape = Control.CURSOR_MOVE
	frame.clip_contents = true
	frame.draw.connect(_draw_frame.bind(frame, slot.key))
	frame.gui_input.connect(_on_frame_input.bind(slot.key))
	add_child(frame)

	var title := Label.new()
	title.theme_type_variation = &"RowValue"
	title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	title.position = Vector2.ONE * TITLE_MARGIN
	frame.add_child(title)

	# The frame draws the backdrop of the name, so a longer name redraws it.
	title.resized.connect(frame.queue_redraw)

	_frames[slot.key] = frame
	_titles[slot.key] = title


func _build_grips(slot: HudSlot) -> void:
	var grips := ResizeGrips.new(self, _frames[slot.key], slot.resize_edges, false)
	grips.drag_started.connect(_start.bind(slot.key))
	grips.dragged.connect(_on_grip_dragged.bind(slot.key))
	_grips[slot.key] = grips


## Move every frame to the footprint of its element, and write each name.
func _sync() -> void:
	if _arranger == null:
		return

	var origin := _pane_origin()

	for slot: HudSlot in _arranger.slots():
		var key := slot.key
		var frame: Control = _frames[key]
		var rect := _arranger.footprint(key)
		var filled := _arranger.is_filled(key)

		frame.visible = rect.has_area()
		frame.position = rect.position + origin
		frame.size = rect.size
		frame.mouse_default_cursor_shape = Control.CURSOR_ARROW if filled else Control.CURSOR_MOVE
		(_grips[key] as ResizeGrips).set_shown(not filled)
		(_titles[key] as Label).text = _title_for(slot)
		frame.queue_redraw()

	_sync_element_row()


## Where the pane starts, in the pixels of this control.
func _pane_origin() -> Vector2:
	var pane := _arranger.pane()

	if pane == null or not pane.is_inside_tree() or not is_inside_tree():
		return Vector2.ZERO

	return pane.global_position - global_position


## The name of an element, and a note for each reason it is not as it looks.
func _title_for(slot: HudSlot) -> String:
	var notes: PackedStringArray = []

	if not _arranger.is_shown(slot.key):
		notes.append(NOTE_HIDDEN)

	if _arranger.is_gated_off(slot.key):
		notes.append(NOTE_OFF)

	if _arranger.is_filled(slot.key):
		notes.append(NOTE_FILLED)

	if notes.is_empty():
		return slot.title

	return "%s (%s)" % [slot.title, ", ".join(notes)]


func _draw_frame(frame: Control, key: String) -> void:
	var rect := Rect2(Vector2.ZERO, frame.size)
	var is_selected := key == _selected
	var line := FRAME_LINE if _arranger.is_drawn(key) else FRAME_LINE_FAINT

	var title: Label = _titles[key]
	var padding := Vector2.ONE * TITLE_PADDING

	frame.draw_rect(rect, FRAME_FILL)
	frame.draw_rect(Rect2(title.position - padding, title.size + padding * 2.0),
		TITLE_BACKDROP)
	frame.draw_rect(rect, SELECTED_LINE if is_selected else line, false,
		SELECTED_LINE_WIDTH if is_selected else LINE_WIDTH)


## A left press on a frame selects the element and starts a move. The motion
## counts only while the left button is down, so the frame never moves under
## a mouse that only passes over it.
func _on_frame_input(event: InputEvent, key: String) -> void:
	if event is InputEventMouseButton:
		var click := event as InputEventMouseButton

		if click.button_index != MOUSE_BUTTON_LEFT:
			return

		if click.pressed:
			_start(key)
			_drag_key = key
		else:
			_drag_key = ""

		accept_event()
		return

	if not (event is InputEventMouseMotion) or _drag_key != key:
		return

	var motion := event as InputEventMouseMotion

	if motion.button_mask & MOUSE_BUTTON_MASK_LEFT == 0:
		_drag_key = ""
		return

	_move(key, _drag_offset + motion.relative)
	accept_event()


## The start of a move or a size: select the element, and keep its rect.
func _start(key: String) -> void:
	select(key)
	_drag_start = _arranger.footprint(key)
	_drag_offset = Vector2.ZERO


func _move(key: String, offset: Vector2) -> void:
	_drag_offset = offset

	if _arranger.is_filled(key):
		return

	var pane := _arranger.pane_size()
	var rect := HudLayout.clamp_into(
		Rect2(_drag_start.position + offset, _drag_start.size), pane)

	if _snaps():
		rect = HudLayout.clamp_into(
			HudLayout.snap_move(rect, _arranger.others(key), pane), pane)

	_arranger.set_rect(key, rect)


func _on_grip_dragged(edges: int, offset: Vector2, key: String) -> void:
	if _arranger.is_filled(key):
		return

	var pane := _arranger.pane_size()
	var smallest := _arranger.smallest_footprint(key)
	var rect := ResizeGrips.dragged_rect(_drag_start, edges, offset, smallest,
		Rect2(Vector2.ZERO, pane))

	if _snaps():
		rect = HudLayout.snap_edges(rect, edges, _arranger.others(key), pane, smallest)

	_arranger.set_rect(key, HudLayout.clamp_into(rect, pane))


## True unless the player holds Shift.
func _snaps() -> bool:
	return not Input.is_key_pressed(KEY_SHIFT)


func _build_toolbar() -> void:
	_toolbar = PanelContainer.new()
	_toolbar.theme_type_variation = &"PopupBox"
	_toolbar.mouse_filter = Control.MOUSE_FILTER_STOP
	_toolbar.minimum_size_changed.connect(_place_toolbar)
	add_child(_toolbar)

	var margin := MarginContainer.new()
	margin.theme_type_variation = &"PaneMargin"
	_toolbar.add_child(margin)

	var column := VBoxContainer.new()
	margin.add_child(column)

	column.add_child(_build_layout_row())

	_hint = Label.new()
	_hint.text = HINT
	column.add_child(_hint)

	_element_row = _build_element_row()
	column.add_child(_element_row)


## The title, which is also the handle that moves the bar, and the preset
## controls.
func _build_layout_row() -> HBoxContainer:
	var row := HBoxContainer.new()

	var handle := Label.new()
	handle.text = TOOLBAR_TITLE
	handle.theme_type_variation = &"FormHeading"
	handle.mouse_filter = Control.MOUSE_FILTER_STOP
	handle.mouse_default_cursor_shape = Control.CURSOR_MOVE
	handle.gui_input.connect(_on_handle_input)
	row.add_child(handle)

	_preset_list = OptionButton.new()
	_preset_list.custom_minimum_size.x = PRESET_WIDTH
	row.add_child(_preset_list)

	_load_button = _button(row, "Load", func() -> void: load_preset(_chosen_preset()))
	_delete_button = _button(row, "Delete", func() -> void: delete_preset(_chosen_preset()))

	_preset_name = LineEdit.new()
	_preset_name.placeholder_text = "New preset name"
	_preset_name.max_length = ClientSettings.MAX_PRESET_NAME
	_preset_name.custom_minimum_size.x = PRESET_WIDTH
	_preset_name.text_submitted.connect(func(text: String) -> void: save_preset(text))
	row.add_child(_preset_name)

	_button(row, "Save", func() -> void: save_preset(_name_to_save()))
	_button(row, "Reset all", func() -> void: _arranger.reset_all())
	_button(row, "Done", close)

	_status = Label.new()
	row.add_child(_status)

	return row


## The name, the Shown box, the two sliders and the reset of the selected
## element.
func _build_element_row() -> HBoxContainer:
	var row := HBoxContainer.new()
	row.visible = false

	_element_title = Label.new()
	_element_title.theme_type_variation = &"RowKey"
	row.add_child(_element_title)

	_shown_check = CheckBox.new()
	_shown_check.text = "Shown"
	_shown_check.toggled.connect(_on_shown_toggled)
	row.add_child(_shown_check)

	_opacity_slider = _slider(row, "Opacity", HudLayout.MIN_OPACITY, HudLayout.MAX_OPACITY)
	_opacity_value = _value_label(row)
	_opacity_slider.value_changed.connect(_on_opacity_changed)

	_scale_slider = _slider(row, "Scale", HudLayout.MIN_SCALE, HudLayout.MAX_SCALE)
	_scale_value = _value_label(row)
	_scale_slider.value_changed.connect(_on_scale_changed)

	_button(row, "Reset element", func() -> void: _arranger.reset_element(_selected))

	return row


func _button(row: HBoxContainer, text: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.pressed.connect(action)
	row.add_child(button)

	return button


func _slider(row: HBoxContainer, text: String, lowest: float, highest: float) -> HSlider:
	var label := Label.new()
	label.text = text
	row.add_child(label)

	var slider := HSlider.new()
	slider.min_value = lowest
	slider.max_value = highest
	slider.step = SLIDER_STEP
	slider.custom_minimum_size.x = SLIDER_WIDTH
	slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(slider)

	return slider


func _value_label(row: HBoxContainer) -> Label:
	var label := Label.new()
	label.theme_type_variation = &"RowValue"
	row.add_child(label)

	return label


## Show the settings of the selected element on the bar, or the hint when
## nothing is selected.
func _sync_element_row() -> void:
	var slot: HudSlot = null

	if _arranger != null and not _selected.is_empty():
		slot = _arranger.slot(_selected)

	_element_row.visible = slot != null
	_hint.visible = slot == null

	if slot == null:
		return

	_syncing = true
	_element_title.text = slot.title
	_shown_check.button_pressed = _arranger.is_shown(slot.key)
	_shown_check.disabled = not slot.can_hide
	_opacity_slider.min_value = slot.min_opacity
	_opacity_slider.value = _arranger.opacity(slot.key)
	_opacity_value.text = _percent(_arranger.opacity(slot.key))
	_scale_slider.value = _arranger.element_scale(slot.key)
	_scale_value.text = _percent(_arranger.element_scale(slot.key))
	_syncing = false


func _percent(value: float) -> String:
	return "%d%%" % roundi(value * PERCENT)


func _on_shown_toggled(shown: bool) -> void:
	if not _syncing and not _selected.is_empty():
		_arranger.set_shown(_selected, shown)


func _on_opacity_changed(value: float) -> void:
	if not _syncing and not _selected.is_empty():
		_arranger.set_opacity(_selected, value)


func _on_scale_changed(value: float) -> void:
	if not _syncing and not _selected.is_empty():
		_arranger.set_element_scale(_selected, value)


## Fill the preset list from the settings, and select `wanted` when it is in
## the list.
func _refresh_presets(wanted: String = "") -> void:
	if _settings == null:
		return

	var keep := wanted if not wanted.is_empty() else _chosen_preset()
	var names := _settings.layout_preset_names()

	_preset_list.clear()

	for preset_name: String in names:
		_preset_list.add_item(preset_name)

	var index := names.find(keep)
	var empty := names.is_empty()

	if index < 0 and not empty:
		index = 0

	# An empty OptionButton draws only its arrow. The disabled row says why.
	if empty:
		_preset_list.add_item(NO_PRESETS)
		index = 0

	_preset_list.select(index)

	_preset_list.disabled = empty
	_load_button.disabled = empty
	_delete_button.disabled = empty


func _chosen_preset() -> String:
	if _preset_list.selected < 0 or _preset_list.disabled:
		return ""

	return _preset_list.get_item_text(_preset_list.selected)


## The name that Save uses: the typed name, or the chosen preset when the box
## is empty. Save with an empty box thus writes over the chosen preset.
func _name_to_save() -> String:
	var typed := _preset_name.text.strip_edges()

	return typed if not typed.is_empty() else _chosen_preset()


## A drag on the title moves the bar, so the bar never hides an element.
func _on_handle_input(event: InputEvent) -> void:
	if not (event is InputEventMouseMotion):
		return

	var motion := event as InputEventMouseMotion

	if motion.button_mask & MOUSE_BUTTON_MASK_LEFT == 0:
		return

	_toolbar.position += motion.relative
	_toolbar_moved = true
	_place_toolbar()


## Size the bar to its content, and keep it on the screen. Until the player
## drags it, the bar sits at the centre of the screen. The shipped layout
## keeps the centre clear, and the top centre held the XP drops.
func _place_toolbar() -> void:
	if _toolbar == null:
		return

	var bar_size := _toolbar.get_combined_minimum_size()
	_toolbar.size = bar_size

	if not _toolbar_moved:
		_toolbar.position = (size - bar_size) / 2.0

	_toolbar.position = _toolbar.position.clamp(Vector2.ZERO,
		(size - bar_size).max(Vector2.ZERO))
