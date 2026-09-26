@tool
class_name TerrainDock
extends VBoxContainer
## The panel of the terrain editor: the tool, the brush, the paint, and the
## block. The plugin reads the choices from here. This panel changes no
## terrain itself.
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

signal load_requested(centre: Vector2i)
signal save_requested
signal noise_fill_requested
signal overlays_changed(show_flags: bool, show_areas: bool)

const _Const := preload("res://autoload/blackout_constants.gd")

const CONFIG_PATH := "res://addons/blackout_terrain/terrain_editor.cfg"
const _CONFIG_SECTION := "noise"

enum Tool { RAISE, LOWER, FLATTEN, SMOOTH, RAMP, NOISE, FLOOR, FLAGS, AREA, OBJECT }

const TOOL_NAMES := ["Raise", "Lower", "Flatten", "Smooth", "Ramp", "Noise",
	"Floor", "Flags", "Area", "Object"]

## The tools that change heights, and so repeat while the button is held.
const SCULPT_TOOLS := [Tool.RAISE, Tool.LOWER, Tool.FLATTEN, Tool.SMOOTH,
	Tool.NOISE]

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
	+ "Ctrl+S saves the chunk files."

var _tool := OptionButton.new()
var _radius := SpinBox.new()
var _strength := SpinBox.new()
var _floor := OptionButton.new()
var _area := OptionButton.new()
var _kind := OptionButton.new()
var _rotation := SpinBox.new()
var _flag_boxes: Array[CheckBox] = []
var _seed := SpinBox.new()
var _frequency := SpinBox.new()
var _amplitude := SpinBox.new()
var _centre_x := SpinBox.new()
var _centre_y := SpinBox.new()
var _show_flags := CheckBox.new()
var _show_areas := CheckBox.new()
var _status := Label.new()


func _init() -> void:
	name = "Terrain"
	_build_tool_rows()
	_build_paint_rows()
	_build_noise_rows()
	_build_block_rows()
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


## The OR of every checked flag.
func flag_bits() -> int:
	var bits := 0

	for index: int in _flag_boxes.size():
		if _flag_boxes[index].button_pressed:
			bits |= FLAG_CHOICES[index][1]

	return bits


func noise_amplitude() -> int:
	return int(_amplitude.value)


## A noise from the current settings.
func make_noise() -> FastNoiseLite:
	var noise := FastNoiseLite.new()

	noise.seed = int(_seed.value)
	noise.frequency = _frequency.value

	return noise


## Select `name` in the floor list, for the pick with Shift.
func pick_floor(picked: String) -> void:
	_select_text(_floor, picked)


func pick_area(picked: String) -> void:
	_select_text(_area, picked)


func set_centre(centre: Vector2i) -> void:
	_centre_x.set_value_no_signal(centre.x)
	_centre_y.set_value_no_signal(centre.y)


func set_status(text: String) -> void:
	_status.text = text


# ─── Building the panel ─────────────────────────────────────────────────────

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
	_row("Floor", _floor)
	_fill(_area, _Const.TILE_AREAS)
	_row("Area", _area)
	_fill(_kind, _Const.OBJECT_KINDS.keys())
	_row("Object", _kind)
	_spin(_rotation, 0.0, _Const.CHUNK_ROTATION_COUNT - 1, 1.0, 0.0)
	_row("Rotation (quarter turns)", _rotation)

	var flags := HFlowContainer.new()

	for choice: Array in FLAG_CHOICES:
		var box := CheckBox.new()

		box.text = choice[0]
		flags.add_child(box)
		_flag_boxes.append(box)

	_flag_boxes[0].button_pressed = true
	_row("Flags", flags)


func _build_noise_rows() -> void:
	_spin(_seed, 0.0, 2147483647.0, 1.0, 0.0)
	_row("Noise seed", _seed)
	_spin(_frequency, 0.001, 0.5, 0.001, 0.02)
	_row("Noise frequency", _frequency)
	_spin(_amplitude, 1.0, 512.0, 1.0, 32.0)
	_row("Noise amplitude (steps)", _amplitude)

	for spin: SpinBox in [_seed, _frequency, _amplitude]:
		spin.value_changed.connect(_on_noise_changed)

	var fill := Button.new()

	fill.text = "Fill the centre chunk with noise"
	fill.pressed.connect(func() -> void: noise_fill_requested.emit())
	add_child(fill)


func _build_block_rows() -> void:
	var centre := HBoxContainer.new()
	var load_button := Button.new()
	var save_button := Button.new()

	_spin(_centre_x, -4096.0, 4096.0, 1.0, 0.0)
	_spin(_centre_y, -4096.0, 4096.0, 1.0, 0.0)
	centre.add_child(_centre_x)
	centre.add_child(_centre_y)
	_row("Centre chunk (x, y)", centre)
	load_button.text = "Load block"
	load_button.pressed.connect(func() -> void:
		load_requested.emit(Vector2i(int(_centre_x.value), int(_centre_y.value))))
	save_button.text = "Save changed chunks"
	save_button.pressed.connect(func() -> void: save_requested.emit())
	add_child(load_button)
	add_child(save_button)
	_show_flags.text = "Show flags"
	_show_flags.button_pressed = true
	_show_areas.text = "Show areas"

	for box: CheckBox in [_show_flags, _show_areas]:
		box.toggled.connect(_on_overlay_toggled)
		add_child(box)

	var help := Label.new()

	help.text = HELP
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(help)
	add_child(_status)


func _row(label_text: String, control: Control) -> void:
	var label := Label.new()

	label.text = label_text
	add_child(label)
	add_child(control)


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


func _on_overlay_toggled(_pressed: bool) -> void:
	overlays_changed.emit(_show_flags.button_pressed, _show_areas.button_pressed)


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


func _on_noise_changed(_value: float) -> void:
	var config := ConfigFile.new()

	config.set_value(_CONFIG_SECTION, "seed", int(_seed.value))
	config.set_value(_CONFIG_SECTION, "frequency", _frequency.value)
	config.set_value(_CONFIG_SECTION, "amplitude", int(_amplitude.value))
	config.save(CONFIG_PATH)
