@tool
class_name BuildPanel
extends VBoxContainer
## The Build tab of the terrain editor (DESIGN-0013 section 6.7): the tool
## and its options. The structure editor is this tab.
##
## This panel changes no terrain. [BuildInput] reads the choices from here
## on each gesture. The lists of floor types, areas, wall styles, and climb
## kinds come from the generated constants. Thus, a new row of
## `blackout/world/*.py` reaches this panel with no edit here.
##
## The template list comes from the files of `blackout/world/structures/`,
## after the row of the clipboard (DESIGN-0013 section 6.6). "Reload the
## templates" reads the directory again.
##
## The options persist in [constant TerrainDock.CONFIG_PATH], in their own
## section, as the noise settings do.

## Any choice changed. The plugin draws the hint line again.
signal changed

## The "Walls down" box changed, by a click or by the V key.
signal walls_down_toggled(down: bool)

## "Save the selection as a template" with the key in the box.
signal save_template_requested(template_key: String)

## "Reload the templates": read the template directory again.
signal reload_templates_requested

const _Const := preload("res://autoload/blackout_constants.gd")

## A new tool goes at the end: the settings file stores the index of a tool.
enum Tool { WALL_LINE, ROOM, DOORWAY, LEVEL_ABOVE, STAIRS, ROOF, WALL_STYLE, DECOR,
	SELECT, PLACE }

const TOOL_NAMES := ["Wall line", "Room", "Doorway", "Level above", "Stairs", "Roof",
	"Wall style", "Decor", "Select", "Place"]

## The first row of the template list: the template that Ctrl+C made.
const CLIPBOARD := "(clipboard)"

## The direction that the front of an object faces at each rotation:
## quarter turns clockwise from above, from north.
const FACING_NAMES := ["north", "east", "south", "west"]

## The radius of the Wall style brush, in tiles. Under one tile, the brush
## paints the tile under the mouse only.
const BRUSH_MIN := 0.0
const BRUSH_MAX := 8.0
const BRUSH_STEP := 0.5
const BRUSH_DEFAULT := 1.0

## The first row of the floor and area lists: keep what the tile has.
const KEEP := "(keep)"

## The names of [enum StructureTools.Base], in its order.
const BASE_NAMES := ["Highest corner", "Lowest corner", "Average corner"]

const _CONFIG_SECTION := "build"

var _tool := OptionButton.new()
var _floor := OptionButton.new()
var _area := OptionButton.new()
var _level := CheckBox.new()
var _base := OptionButton.new()
var _block := CheckBox.new()
var _climb := OptionButton.new()
var _roof_shape := OptionButton.new()
var _pitch := SpinBox.new()
var _overhang := SpinBox.new()
var _roof_floor := OptionButton.new()
var _wall_style := OptionButton.new()
var _brush := SpinBox.new()
var _decor := OptionButton.new()
var _every_plane := CheckBox.new()
var _template := OptionButton.new()
var _template_key := LineEdit.new()
var _blend := SpinBox.new()
var _place_areas := CheckBox.new()
var _walls_down := CheckBox.new()

## Quarter turns of the roof: the ridge of a gable, the low edge of a shed.
## R and Shift+R change it, and the hint line names it.
var _turn := 0

## The rotation of the next decor. R and Shift+R change it while the Decor
## tool is on.
var _decor_turn := 0

## True while the saved settings load, so the load writes nothing back.
var _loading := false

## False in a test: a change of a choice then writes no settings file. The
## file is in git, and a test run must not change the choices of the author.
var persist := true


func _init() -> void:
	name = "Build"
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_fill(_tool, TOOL_NAMES)
	_row("Tool", _tool)
	_fill(_floor, [KEEP] + Array(_Const.TILE_FLOOR_TYPES))
	_row("Floor (keep: the floor of each tile, or of the tile below)", _floor)
	_fill(_area, [KEEP] + Array(_Const.TILE_AREAS))
	_row("Area (an interior area gives a room its own light and text)", _area)
	_add_wall_style_rows()
	_level.text = "Level ground under a room"
	_level.button_pressed = true
	add_child(_level)
	_fill(_base, BASE_NAMES)
	_row("Level to (the Room tool and the Place tool)", _base)
	_block.text = "Block outside (a dungeon room)"
	add_child(_block)
	_fill(_climb, StructureTools.climb_pairs().keys())
	_row("Climb (the Stairs tool places it and its twin above)", _climb)
	_add_roof_rows()
	_fill(_decor, StructureTools.decor_kinds())
	_row("Decor (the Decor tool places it. R turns the next one)", _decor)
	_add_template_rows()
	_walls_down.text = "Walls down (V)"
	add_child(_walls_down)
	_load_settings()
	_connect_controls()


# ─── Reading the choices ────────────────────────────────────────────────────

func current_tool() -> int:
	return _tool.selected


func tool_name() -> String:
	return TOOL_NAMES[_tool.selected]


## The floor of the options, or "" to keep.
func floor_name() -> String:
	return _choice(_floor)


## The area of the options, or "" to keep.
func area_name() -> String:
	return _choice(_area)


func climb_kind() -> String:
	if _climb.item_count == 0:
		return ""

	return _climb.get_item_text(_climb.selected)


func walls_down() -> bool:
	return _walls_down.button_pressed


## The decor kind of the Decor tool, or "" when the server names none.
func decor_kind() -> String:
	if _decor.item_count == 0:
		return ""

	return _decor.get_item_text(_decor.selected)


## The rotation of the next decor.
func decor_turn() -> int:
	return _decor_turn


## The decor of the options in words, for the hint line.
func decor_summary() -> String:
	return "%s, front to the %s" % [decor_kind(), FACING_NAMES[_decor_turn]]


## The wall style of the Wall line, the Room, and the Wall style brush.
func wall_style() -> String:
	return _wall_style.get_item_text(_wall_style.selected)


## The radius of the Wall style brush, in tiles.
func brush_radius() -> float:
	return _brush.value


## True when the Select tool takes the edited plane and each plane above.
func every_plane() -> bool:
	return _every_plane.button_pressed


## The row of the template list: a template key, or [constant CLIPBOARD].
func template_choice() -> String:
	if _template.item_count == 0:
		return CLIPBOARD

	return _template.get_item_text(_template.selected)


## The key in the "Template key" box, with no space at either end.
func template_key() -> String:
	return _template_key.text.strip_edges()


func place_options() -> StructurePlace.Options:
	var options := StructurePlace.Options.new()

	options.base = _base.selected as StructureTools.Base
	options.blend = int(_blend.value)
	options.areas = _place_areas.button_pressed

	return options


## The Place options in words, for the hint line.
func place_summary() -> String:
	var areas := "the areas of the template" if _place_areas.button_pressed \
		else "the areas of the ground"

	return "level to the %s, blend ring %d, %s" % [BASE_NAMES[_base.selected].to_lower(),
		int(_blend.value), areas]


func roof_options() -> StructureTools.RoofOptions:
	var options := StructureTools.RoofOptions.new()

	options.shape = _roof_shape.selected as RoofShapes.Shape
	options.pitch = int(_pitch.value)
	options.overhang = int(_overhang.value)
	options.turn = _turn
	options.floor_name = _roof_floor.get_item_text(_roof_floor.selected)

	return options


## The roof options in words, for the hint line.
func roof_summary() -> String:
	var options := roof_options()
	var words := [RoofShapes.SHAPE_NAMES[options.shape], "pitch %d" % options.pitch,
		"overhang %d" % options.overhang]
	var turn := RoofShapes.turn_name(options.shape, options.turn)

	if not turn.is_empty():
		words.append(turn)

	words.append(options.floor_name)

	return ", ".join(words)


func room_options() -> StructureTools.RoomOptions:
	var options := StructureTools.RoomOptions.new()

	options.floor_name = floor_name()
	options.area_name = area_name()
	options.level_ground = _level.button_pressed
	options.base = _base.selected as StructureTools.Base
	options.block_outside = _block.button_pressed
	options.wall_style = wall_style()

	return options


# ─── Writing the choices ────────────────────────────────────────────────────

## Take the floor, the area, and the wall style of a tile into the options:
## Alt and a click. `decor` is the decor of the tile, `{kind, rotation}`, or
## empty to keep the decor choice.
func sample(floor_type: String, area: String, style: String,
		decor: Dictionary = {}) -> void:
	TerrainDock._select_text(_floor, floor_type)
	TerrainDock._select_text(_area, area)
	TerrainDock._select_text(_wall_style, style)

	if not decor.is_empty():
		TerrainDock._select_text(_decor, decor["kind"])
		_decor_turn = posmod(decor["rotation"], FACING_NAMES.size())

	_on_changed()


func set_walls_down(down: bool) -> void:
	_walls_down.button_pressed = down


## Turn the roof by `steps` quarter turns clockwise: R and Shift+R.
func turn_roof(steps: int) -> void:
	_turn = posmod(_turn + steps, RoofShapes.TURNS)
	_on_changed()


## Turn the next decor by `steps` quarter turns clockwise: R and Shift+R.
func turn_decor(steps: int) -> void:
	_decor_turn = posmod(_decor_turn + steps, FACING_NAMES.size())
	_on_changed()


## Step the pitch by `steps`, inside its range: [ and ].
func step_pitch(steps: int) -> void:
	_pitch.value = _pitch.value + steps


## Step the radius of the Wall style brush by `steps`, inside its range: [
## and ].
func step_brush(steps: int) -> void:
	_brush.value = _brush.value + steps * BRUSH_STEP


## Pick a tool, and save nothing. It sends no [signal changed]. A test and
## the keys of [TemplateInput] use it.
func select_tool(tool_index: int) -> void:
	_tool.select(tool_index)


## Fill the template list: [constant CLIPBOARD], then `keys`. Keeps the row
## of the same name, or picks `chosen` when it is not empty.
func set_template_keys(keys: PackedStringArray, chosen: String = "") -> void:
	var keep := template_choice() if chosen.is_empty() else chosen

	_template.clear()
	_fill(_template, [CLIPBOARD] + Array(keys))
	TerrainDock._select_text(_template, keep)


## Pick the row `choice` of the template list, and save nothing.
func choose_template(choice: String) -> void:
	TerrainDock._select_text(_template, choice)


func set_every_plane(on: bool) -> void:
	_every_plane.button_pressed = on


# ─── Building the panel ─────────────────────────────────────────────────────

func _add_wall_style_rows() -> void:
	_fill(_wall_style, Array(_Const.TILE_WALL_STYLES))
	_row("Wall style (the Wall line, the Room, and the Wall style brush use it)",
		_wall_style)
	_brush.min_value = BRUSH_MIN
	_brush.max_value = BRUSH_MAX
	_brush.step = BRUSH_STEP
	_brush.value = BRUSH_DEFAULT
	_row("Wall style brush radius, tiles ([ and ])", _brush)


func _add_roof_rows() -> void:
	_fill(_roof_shape, RoofShapes.SHAPE_NAMES)
	_roof_shape.select(RoofShapes.Shape.GABLE)
	_row("Roof shape (R turns the ridge or the low edge)", _roof_shape)
	_pitch.min_value = 1
	_pitch.max_value = RoofShapes.PITCH_MAX
	_pitch.value = RoofShapes.PITCH_DEFAULT
	_row("Roof pitch, height steps for each tile ([ and ])", _pitch)
	_overhang.min_value = 0
	_overhang.max_value = RoofShapes.OVERHANG_MAX
	_overhang.value = 1
	_row("Roof overhang, tiles past each wall", _overhang)
	_fill(_roof_floor, Array(_Const.TILE_ROOF_FLOOR_TYPES))
	_row("Roof floor", _roof_floor)


func _add_template_rows() -> void:
	_every_plane.text = "Select every plane (this plane and each plane above)"
	_every_plane.button_pressed = true
	add_child(_every_plane)
	set_template_keys(StructureTemplate.list_keys(StructureTemplate.world_directory()))
	_row("Template (the Place tool places it. R turns, F mirrors)", _template)
	_button("Reload the templates", reload_templates_requested.emit)
	_template_key.placeholder_text = "a key: a-z, 0-9, and _"
	_row("Template key", _template_key)
	_button("Save the selection as a template", func() -> void:
		save_template_requested.emit(template_key()))
	_blend.min_value = 0
	_blend.max_value = StructurePlace.BLEND_MAX
	_blend.value = 1
	_row("Blend ring, tiles around a template copy", _blend)
	_place_areas.text = "Place the areas of the template"
	_place_areas.button_pressed = true
	add_child(_place_areas)


func _button(text: String, action: Callable) -> void:
	var button := Button.new()

	button.text = text
	button.pressed.connect(action)
	add_child(button)


func _row(label_text: String, control: Control) -> void:
	var label := Label.new()

	label.text = label_text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(label)
	add_child(control)


static func _fill(list: OptionButton, names: Array) -> void:
	for item: String in names:
		list.add_item(item)


static func _choice(list: OptionButton) -> String:
	var text := list.get_item_text(list.selected)

	return "" if text == KEEP else text


func _connect_controls() -> void:
	for list: OptionButton in [_tool, _floor, _area, _base, _climb, _roof_shape,
			_roof_floor, _wall_style, _decor, _template]:
		list.item_selected.connect(func(_index: int) -> void: _on_changed())

	for spin: SpinBox in [_pitch, _overhang, _brush, _blend]:
		spin.value_changed.connect(func(_value: float) -> void: _on_changed())

	for box: CheckBox in [_level, _block, _every_plane, _place_areas]:
		box.toggled.connect(func(_pressed: bool) -> void: _on_changed())

	_walls_down.toggled.connect(func(pressed: bool) -> void:
		walls_down_toggled.emit(pressed)
		_on_changed())


func _on_changed() -> void:
	_save_settings()
	changed.emit()


# ─── The settings file ──────────────────────────────────────────────────────

func _load_settings() -> void:
	var config := ConfigFile.new()

	if config.load(TerrainDock.CONFIG_PATH) != OK:
		return

	_loading = true
	_tool.select(config.get_value(_CONFIG_SECTION, "tool", _tool.selected))
	TerrainDock._select_text(_floor, config.get_value(_CONFIG_SECTION, "floor", KEEP))
	TerrainDock._select_text(_area, config.get_value(_CONFIG_SECTION, "area", KEEP))
	_level.button_pressed = config.get_value(_CONFIG_SECTION, "level", true)
	_base.select(config.get_value(_CONFIG_SECTION, "base", 0))
	_block.button_pressed = config.get_value(_CONFIG_SECTION, "block_outside", false)
	TerrainDock._select_text(_climb, config.get_value(_CONFIG_SECTION, "climb", ""))
	_roof_shape.select(config.get_value(_CONFIG_SECTION, "roof_shape", _roof_shape.selected))
	_pitch.value = config.get_value(_CONFIG_SECTION, "roof_pitch", _pitch.value)
	_overhang.value = config.get_value(_CONFIG_SECTION, "roof_overhang", _overhang.value)
	_turn = config.get_value(_CONFIG_SECTION, "roof_turn", 0)
	TerrainDock._select_text(_roof_floor, config.get_value(_CONFIG_SECTION, "roof_floor", ""))
	TerrainDock._select_text(_wall_style, config.get_value(_CONFIG_SECTION, "wall_style", ""))
	_brush.value = config.get_value(_CONFIG_SECTION, "wall_style_brush", _brush.value)
	TerrainDock._select_text(_decor, config.get_value(_CONFIG_SECTION, "decor", ""))
	_decor_turn = config.get_value(_CONFIG_SECTION, "decor_turn", 0)
	_every_plane.button_pressed = config.get_value(_CONFIG_SECTION, "every_plane", true)
	TerrainDock._select_text(_template, config.get_value(_CONFIG_SECTION, "template", ""))
	_blend.value = config.get_value(_CONFIG_SECTION, "blend_ring", _blend.value)
	_place_areas.button_pressed = config.get_value(_CONFIG_SECTION, "place_areas", true)
	_loading = false


## Keep every other section of the file: the noise settings live there too.
func _save_settings() -> void:
	if _loading or not persist:
		return

	var config := ConfigFile.new()

	config.load(TerrainDock.CONFIG_PATH)
	config.set_value(_CONFIG_SECTION, "tool", _tool.selected)
	config.set_value(_CONFIG_SECTION, "floor", _floor.get_item_text(_floor.selected))
	config.set_value(_CONFIG_SECTION, "area", _area.get_item_text(_area.selected))
	config.set_value(_CONFIG_SECTION, "level", _level.button_pressed)
	config.set_value(_CONFIG_SECTION, "base", _base.selected)
	config.set_value(_CONFIG_SECTION, "block_outside", _block.button_pressed)
	config.set_value(_CONFIG_SECTION, "climb", climb_kind())
	config.set_value(_CONFIG_SECTION, "roof_shape", _roof_shape.selected)
	config.set_value(_CONFIG_SECTION, "roof_pitch", int(_pitch.value))
	config.set_value(_CONFIG_SECTION, "roof_overhang", int(_overhang.value))
	config.set_value(_CONFIG_SECTION, "roof_turn", _turn)
	config.set_value(_CONFIG_SECTION, "roof_floor",
		_roof_floor.get_item_text(_roof_floor.selected))
	config.set_value(_CONFIG_SECTION, "wall_style", wall_style())
	config.set_value(_CONFIG_SECTION, "wall_style_brush", _brush.value)
	config.set_value(_CONFIG_SECTION, "decor", decor_kind())
	config.set_value(_CONFIG_SECTION, "decor_turn", _decor_turn)
	config.set_value(_CONFIG_SECTION, "every_plane", _every_plane.button_pressed)
	config.set_value(_CONFIG_SECTION, "template", template_choice())
	config.set_value(_CONFIG_SECTION, "blend_ring", int(_blend.value))
	config.set_value(_CONFIG_SECTION, "place_areas", _place_areas.button_pressed)
	config.save(TerrainDock.CONFIG_PATH)
