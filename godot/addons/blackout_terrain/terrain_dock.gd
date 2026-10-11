@tool
class_name TerrainDock
extends VBoxContainer
## The panel of the terrain editor, in four tabs:
##
## - **Paint**: the tool, the brush, the paint, and the noise.
## - **Objects**: the selected object and its buttons, and every object of
##   the block.
## - **World**: the block and its plane, load and save, the marks to show,
##   "Check world", the chunks changed since the last tile sync, and the
##   buttons of the structure workbench.
## - **Build**: the structure tools ([BuildPanel], DESIGN-0013). While this
##   tab shows, the mouse in the 3D view drives the Build tools.
##
## The plugin reads the choices from here. This panel changes no terrain
## itself: each button sends a signal, and the plugin acts.
##
## The lists of floor types, areas, object kinds, and flags come from the
## generated constants. A new row in `blackout/world/*.py` reaches this panel
## after `export_client_constants.py` runs, with no edit here.
##
## ## The noise settings
##
## The seed, the frequency, and the amplitude persist in [constant CONFIG_PATH]
## beside this script, so every author gets the same noise from the same
## seed. They are not in the chunk file: the file stores the baked integer
## heights, and the server cannot run Godot's noise. Undo covers a bad fill.

signal load_requested(centre: Vector2i, plane: int)
signal save_requested
signal noise_fill_requested
signal overlays_changed
signal selection_action(action: String)
signal object_chosen(thing: Dictionary)
signal check_requested
signal finding_chosen(finding: Dictionary)
signal tab_changed
signal clear_workbench_requested
signal switch_scene_requested

const _Const := preload("res://autoload/blackout_constants.gd")

const CONFIG_PATH := "res://addons/blackout_terrain/terrain_editor.cfg"
const _CONFIG_SECTION := "noise"

## The names of [enum TerrainWorld.UpperPlanes], in its order.
const UPPER_PLANE_NAMES := ["Hidden", "Ghost", "Solid"]

## The height of the status box under the tabs, in pixels: about six lines.
const STATUS_HEIGHT := 120.0

## The colour of a note in the findings list. A note fails no test.
const NOTE_COLOR := Color(0.6, 0.75, 1.0)

enum Tool { RAISE, LOWER, FLATTEN, SMOOTH, RAMP, NOISE, FLOOR, FLAGS, AREA, OBJECT, SELECT }

const TOOL_NAMES := ["Raise", "Lower", "Flatten", "Smooth", "Ramp", "Noise",
	"Floor", "Flags", "Area", "Object", "Select"]

## The tools that change heights, and so repeat while the button is held.
const SCULPT_TOOLS := [Tool.RAISE, Tool.LOWER, Tool.FLATTEN, Tool.SMOOTH,
	Tool.NOISE]

## The actions of the selection buttons, as [signal selection_action] sends
## them.
const ACTION_TURN := "turn"
const ACTION_DELETE := "delete"
const ACTION_SET_KIND := "set_kind"
const ACTION_SET_TEXT := "set_text"
const ACTION_FOLLOW := "follow"

## Flag bits and their names, in the order of the check boxes.
const FLAG_CHOICES := [
	["Blocked", _Const.TILE_FLAG_BLOCKED],
	["Water", _Const.TILE_FLAG_WATER],
	["Wall N", _Const.TILE_FLAG_WALL_NORTH],
	["Wall E", _Const.TILE_FLAG_WALL_EAST],
	["Wall S", _Const.TILE_FLAG_WALL_SOUTH],
	["Wall W", _Const.TILE_FLAG_WALL_WEST],
]

const HELP := "Left drag: apply. Shift: lower, clear flags, remove an object, " \
	+ "or pick a floor or area. Ramp: click the start, then the end. " \
	+ "Select: click an object, click again for the next one on the tile, " \
	+ "drag it to move it. Ctrl+S saves the chunk files. The Build tab names " \
	+ "its keys in the hint line at the bottom of the 3D view."

var _tabs := TabContainer.new()
var _page: VBoxContainer

var _tool := OptionButton.new()
var _radius := SpinBox.new()
var _strength := SpinBox.new()
var _floor := OptionButton.new()
var _area := OptionButton.new()
var _kind := OptionButton.new()
var _rotation := SpinBox.new()
var _text := LineEdit.new()
var _flag_boxes: Array[CheckBox] = []
var _seed := SpinBox.new()
var _frequency := SpinBox.new()
var _amplitude := SpinBox.new()
var _protect := CheckBox.new()

var _selection := Label.new()
var _selection_buttons: Array[Button] = []
var _follow := Button.new()
var _objects := ItemList.new()
var _show_decor := CheckBox.new()

## The rows of the last [method set_objects], before the decor filter.
var _object_rows: Array[Dictionary] = []

var _centre_x := SpinBox.new()
var _centre_y := SpinBox.new()
var _plane := SpinBox.new()
var _show_flags := CheckBox.new()
var _show_areas := CheckBox.new()
var _show_links := CheckBox.new()
var _show_lower := CheckBox.new()
var _upper := OptionButton.new()
var _build := BuildPanel.new()
var _build_page: Control
var _findings := ItemList.new()
var _sync_state := Label.new()
var _switch_scene := Button.new()
var _clear_workbench := Button.new()
var _confirm_clear := ConfirmationDialog.new()
var _status := Label.new()


func _init() -> void:
	name = "Terrain"
	_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_tabs.tab_changed.connect(func(_tab: int) -> void: tab_changed.emit())
	add_child(_tabs)
	_page = _new_page("Paint")
	_build_tool_rows()
	_build_paint_rows()
	_build_noise_rows()
	_page = _new_page("Objects")
	_build_object_rows()
	_page = _new_page("World")
	_build_block_rows()
	_build_check_rows()
	_page = _new_page("Build")
	_build_page = _page.get_parent()
	_page.add_child(_build)
	_build_status_box()
	_load_noise_settings()


# ─── Reading the choices ────────────────────────────────────────────────────

func current_tool() -> int:
	return _tool.selected


func tool_name() -> String:
	return TOOL_NAMES[_tool.selected]


func radius() -> float:
	return _radius.value


func strength() -> int:
	return int(_strength.value)


func floor_name() -> String:
	return _floor.get_item_text(_floor.selected)


func area_name() -> String:
	return _area.get_item_text(_area.selected)


func kind() -> String:
	return _kind.get_item_text(_kind.selected)


func object_rotation() -> int:
	return int(_rotation.value)


## The words of a new sign, with no space at either end.
func object_text() -> String:
	return _text.text.strip_edges()


## The OR of every checked flag.
func flag_bits() -> int:
	var bits := 0

	for index: int in _flag_boxes.size():
		if _flag_boxes[index].button_pressed:
			bits |= FLAG_CHOICES[index][1]

	return bits


## True when a sculpt skips the corners of a structure (DESIGN-0013 section
## 6.7).
func protect_structures() -> bool:
	return _protect.button_pressed


func noise_amplitude() -> int:
	return int(_amplitude.value)


## A noise from the current settings.
func make_noise() -> FastNoiseLite:
	var noise := FastNoiseLite.new()

	noise.seed = int(_seed.value)
	noise.frequency = _frequency.value

	return noise


func show_flags() -> bool:
	return _show_flags.button_pressed


func show_areas() -> bool:
	return _show_areas.button_pressed


func show_links() -> bool:
	return _show_links.button_pressed


func show_lower_planes() -> bool:
	return _show_lower.button_pressed


## How the planes above the edited plane show: a [enum TerrainWorld.UpperPlanes].
func upper_planes() -> int:
	return _upper.selected


func build_panel() -> BuildPanel:
	return _build


## True while the Build tab shows.
func build_active() -> bool:
	return _tabs.get_current_tab_control() == _build_page


# ─── Writing the state ──────────────────────────────────────────────────────

## Select `name` in the floor list, for the pick with Shift.
func pick_floor(picked: String) -> void:
	_select_text(_floor, picked)


func pick_area(picked: String) -> void:
	_select_text(_area, picked)


func set_block(centre: Vector2i, plane: int) -> void:
	_centre_x.set_value_no_signal(centre.x)
	_centre_y.set_value_no_signal(centre.y)
	_plane.set_value_no_signal(plane)


func set_status(text: String) -> void:
	_status.text = text


## Fill the object list with `{tile, kind, rotation, text}` rows. With "Show
## decor" off, the list leaves out each decor row, so a busy shop does not
## flood it (DESIGN-0013 section 6.5).
func set_objects(things: Array[Dictionary]) -> void:
	_object_rows = things
	_objects.clear()

	for thing: Dictionary in listed_objects(things, _show_decor.button_pressed):
		var line := "%s  %s  r%d" % [thing["kind"], thing["tile"], thing["rotation"]]

		if not thing["text"].is_empty():
			line += "  \"%s\"" % thing["text"]

		var row := _objects.add_item(line)

		_objects.set_item_metadata(row, thing)
		_objects.set_item_custom_fg_color(row, TerrainOverlay.kind_color(thing["kind"]))


## The rows of `things` that the object list shows: every row, or every row
## that is not decor.
static func listed_objects(things: Array[Dictionary],
		show_decor: bool) -> Array[Dictionary]:
	if show_decor:
		return things

	var listed: Array[Dictionary] = []

	for thing: Dictionary in things:
		if _Const.OBJECT_KINDS.get(thing["kind"], "") != _Const.OBJECT_CATEGORY_DECOR:
			listed.append(thing)

	return listed


## Show the selected object, and whether it leads anywhere.
func set_selection(selected: Dictionary, link_end: Dictionary) -> void:
	for button: Button in _selection_buttons:
		button.disabled = selected.is_empty()

	_follow.disabled = link_end.is_empty()

	if selected.is_empty():
		_selection.text = "Nothing selected. Use the Select tool, or pick a row."
		return

	var lines := ["%s at %s, rotation %d" % [selected["kind"], selected["tile"],
		selected["rotation"]]]

	if not selected["text"].is_empty():
		lines.append("Text: \"%s\"" % selected["text"])

	if not link_end.is_empty():
		lines.append("Leads to %s on plane %d" % [link_end["tile"], link_end["plane"]])

	_selection.text = "\n".join(lines)


## Fill the findings list. `errors` are chunk files that do not read.
func set_findings(findings: Array[Dictionary], errors: PackedStringArray) -> void:
	_findings.clear()

	for error: String in errors:
		_findings.add_item("unreadable: " + error)

	for finding: Dictionary in findings:
		var row := _findings.add_item(TerrainChecks.describe(finding))

		_findings.set_item_metadata(row, finding)

		if TerrainChecks.is_note(finding):
			_findings.set_item_custom_fg_color(row, NOTE_COLOR)

	if findings.is_empty() and errors.is_empty():
		_findings.add_item("No finding. The world passes every check.")


func set_sync_state(text: String) -> void:
	_sync_state.text = text


## Show the buttons for the structure workbench (`on`), or for the world.
func set_workbench(on: bool) -> void:
	_switch_scene.text = "Open the terrain editor" if on else "Open the structure workbench"
	_clear_workbench.disabled = not on


func select_tool(tool_index: int) -> void:
	_tool.select(tool_index)


# ─── Building the panel ─────────────────────────────────────────────────────

## The status sits under the tabs in a box of a fixed height, with its own
## scroll bar. A long report, for example one line for each seam fault, then
## cannot push the tabs off the dock.
func _build_status_box() -> void:
	var box := ScrollContainer.new()

	box.custom_minimum_size.y = STATUS_HEIGHT
	box.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_child(_status)
	add_child(box)


func _new_page(title: String) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	var page := VBoxContainer.new()

	scroll.name = title
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(page)
	_tabs.add_child(scroll)

	return page


func _build_tool_rows() -> void:
	for tool_label: String in TOOL_NAMES:
		_tool.add_item(tool_label)

	_row("Tool", _tool)
	_spin(_radius, 0.0, 32.0, 0.5, 3.0)
	_row("Radius (tiles)", _radius)
	_spin(_strength, 1.0, 64.0, 1.0, 1.0)
	_row("Strength (steps)", _strength)


func _build_paint_rows() -> void:
	_fill(_floor, _Const.TILE_FLOOR_TYPES)
	_row("Floor (void: no floor, sets Blocked)", _floor)
	_fill(_area, _Const.TILE_AREAS)
	_row("Area", _area)
	_fill(_kind, _Const.OBJECT_KINDS.keys())
	_row("Object", _kind)
	_spin(_rotation, 0.0, _Const.CHUNK_ROTATION_COUNT - 1, 1.0, 0.0)
	_row("Rotation (quarter turns clockwise, 0 faces north)", _rotation)
	_text.max_length = _Const.CHUNK_TEXT_MAX_CHARS
	_text.placeholder_text = "The words of a new %s" % _Const.OBJECT_SIGNPOST_KIND
	_row("Sign text (a sign kind only)", _text)

	var flags := HFlowContainer.new()

	for choice: Array in FLAG_CHOICES:
		var box := CheckBox.new()

		box.text = choice[0]
		flags.add_child(box)
		_flag_boxes.append(box)

	_flag_boxes[0].button_pressed = true
	_row("Flags", flags)
	_protect.text = "Protect structures (a sculpt skips each corner of a wall " \
		+ "and of a tile under a floor)"
	_page.add_child(_protect)


func _build_noise_rows() -> void:
	_spin(_seed, 0.0, 2147483647.0, 1.0, 0.0)
	_row("Noise seed", _seed)
	_spin(_frequency, 0.001, 0.5, 0.001, 0.02)
	_row("Noise frequency", _frequency)
	_spin(_amplitude, 1.0, 512.0, 1.0, 32.0)
	_row("Noise amplitude (steps)", _amplitude)

	for spin: SpinBox in [_seed, _frequency, _amplitude]:
		spin.value_changed.connect(_on_noise_changed)

	_button("Fill the centre chunk with noise", noise_fill_requested.emit)

	var help := Label.new()

	help.text = HELP
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_page.add_child(help)


func _build_object_rows() -> void:
	_selection.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_page.add_child(_selection)

	var buttons := HFlowContainer.new()

	for pair: Array in [["Turn", ACTION_TURN], ["Delete", ACTION_DELETE],
			["Set kind to the Object choice", ACTION_SET_KIND],
			["Set text to the Sign text", ACTION_SET_TEXT]]:
		var button := Button.new()

		button.text = pair[0]
		button.pressed.connect(selection_action.emit.bind(pair[1]))
		buttons.add_child(button)
		_selection_buttons.append(button)

	_follow.text = "Follow link"
	_follow.tooltip_text = "Load the block where this transition or climb leads."
	_follow.pressed.connect(selection_action.emit.bind(ACTION_FOLLOW))
	buttons.add_child(_follow)
	_page.add_child(buttons)
	_objects.custom_minimum_size = Vector2(0, 260)
	_objects.item_selected.connect(func(row: int) -> void:
		object_chosen.emit(_objects.get_item_metadata(row)))
	_row("Objects in the block", _objects)
	_show_decor.text = "Show decor in the list"
	_show_decor.button_pressed = true
	_show_decor.toggled.connect(func(_pressed: bool) -> void:
		set_objects(_object_rows))
	_page.add_child(_show_decor)
	set_selection({}, {})


func _build_block_rows() -> void:
	var centre := HBoxContainer.new()

	_spin(_centre_x, -4096.0, 4096.0, 1.0, 0.0)
	_spin(_centre_y, -4096.0, 4096.0, 1.0, 0.0)
	centre.add_child(_centre_x)
	centre.add_child(_centre_y)
	_row("Centre chunk (x, y)", centre)
	_spin(_plane, _Const.TILE_GROUND_PLANE, _Const.CHUNK_PLANE_MAX, 1.0, 0.0)
	_row("Plane (0 is the ground)", _plane)
	_button("Load block", func() -> void:
		load_requested.emit(Vector2i(int(_centre_x.value), int(_centre_y.value)),
			int(_plane.value)))
	_button("Save changed chunks", save_requested.emit)
	_build_workbench_rows()

	for pair: Array in [[_show_flags, "Show flags", true],
			[_show_areas, "Show areas", false], [_show_links, "Show links", true],
			[_show_lower, "Show the planes below", true]]:
		var box: CheckBox = pair[0]

		box.text = pair[1]
		box.button_pressed = pair[2]
		box.toggled.connect(func(_pressed: bool) -> void: overlays_changed.emit())
		_page.add_child(box)

	_fill(_upper, UPPER_PLANE_NAMES)
	_upper.item_selected.connect(func(_index: int) -> void: overlays_changed.emit())
	_row("The planes above the edited plane", _upper)


## The structure workbench (DESIGN-0013 Phase S6): one button opens the
## other scene, and one deletes the scratch chunk files after a confirmation.
func _build_workbench_rows() -> void:
	_switch_scene.pressed.connect(switch_scene_requested.emit)
	_page.add_child(_switch_scene)
	_clear_workbench.text = "Clear the structure workbench"
	_clear_workbench.tooltip_text = "Delete the scratch chunk files. The templates stay."
	_clear_workbench.pressed.connect(_confirm_clear.popup_centered)
	_page.add_child(_clear_workbench)
	_confirm_clear.dialog_text = "Delete every scratch chunk file of the structure " 		+ "workbench? The templates stay. Undo cannot bring the chunks back."
	_confirm_clear.confirmed.connect(clear_workbench_requested.emit)
	add_child(_confirm_clear)
	set_workbench(false)


func _build_check_rows() -> void:
	_button("Check world", check_requested.emit)
	_findings.custom_minimum_size = Vector2(0, 200)
	_findings.item_selected.connect(func(row: int) -> void:
		var finding: Variant = _findings.get_item_metadata(row)

		if finding is Dictionary:
			finding_chosen.emit(finding))
	_row("Findings (click one to go there)", _findings)
	_sync_state.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_row("Since the last tile sync", _sync_state)


func _row(label_text: String, control: Control) -> void:
	var label := Label.new()

	label.text = label_text
	_page.add_child(label)
	_page.add_child(control)


func _button(text: String, action: Callable) -> void:
	var button := Button.new()

	button.text = text
	button.pressed.connect(action)
	_page.add_child(button)


static func _spin(spin: SpinBox, low: float, high: float, step: float,
		value: float) -> void:
	spin.min_value = low
	spin.max_value = high
	spin.step = step
	spin.value = value
	spin.allow_greater = false
	spin.allow_lesser = false


static func _fill(list: OptionButton, names: Array) -> void:
	for item: String in names:
		list.add_item(item)


static func _select_text(list: OptionButton, text: String) -> void:
	for index: int in list.item_count:
		if list.get_item_text(index) == text:
			list.select(index)
			return


# ─── The noise settings file ────────────────────────────────────────────────

func _load_noise_settings() -> void:
	var config := ConfigFile.new()

	if config.load(CONFIG_PATH) != OK:
		return

	_seed.set_value_no_signal(config.get_value(_CONFIG_SECTION, "seed", _seed.value))
	_frequency.set_value_no_signal(
		config.get_value(_CONFIG_SECTION, "frequency", _frequency.value))
	_amplitude.set_value_no_signal(
		config.get_value(_CONFIG_SECTION, "amplitude", _amplitude.value))


## Keep every other section of the file: the Build settings live there too.
func _on_noise_changed(_value: float) -> void:
	var config := ConfigFile.new()

	config.load(CONFIG_PATH)
	config.set_value(_CONFIG_SECTION, "seed", int(_seed.value))
	config.set_value(_CONFIG_SECTION, "frequency", _frequency.value)
	config.set_value(_CONFIG_SECTION, "amplitude", int(_amplitude.value))
	config.save(CONFIG_PATH)
