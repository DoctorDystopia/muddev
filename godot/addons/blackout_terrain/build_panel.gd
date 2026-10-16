@tool
class_name BuildPanel
extends VBoxContainer
## The Build tab of the terrain editor (DESIGN-0013 section 6.7): the tool
## row and the options of the current tool. The structure editor is this
## tab.
##
## This panel changes no terrain. [BuildInput] reads the choices from here
## on each gesture. The climb kinds come from the generated constants. The
## decor kinds and the roof floors come from [TileTables]. Thus, a row of
## the Tables tab reaches this panel at once ([method refill_tables]).
##
## The floor, the area, and the wall style come from [member values], the
## paint values strip of the dock. The Paint tab reads the same strip, so
## a pick from either tab lands in one place.
##
## The panel shows only the options of the current tool. Each option names
## the tools that use it, and a tool change hides the rest. The hint line
## names the state of the hidden ones.
##
## The template list comes from the files of `blackout/world/structures/`,
## after the row of the clipboard (DESIGN-0013 section 6.6). "Reload
## templates" reads the directory again.
##
## The choices persist in the session file (`terrain_session.gd`), outside
## the repo.

## Any choice changed. The plugin draws the hint line again.
signal changed

## The "Walls down" box changed, by a click or by the V key.
signal walls_down_toggled(down: bool)

## "Save as template" with the key in the box.
signal save_template_requested(template_key: String)

## "Reload templates": read the template directory again.
signal reload_templates_requested

const _Const := preload("res://autoload/blackout_constants.gd")
const _Fields := preload("res://addons/blackout_terrain/terrain_fields.gd")
const _Session := preload("res://addons/blackout_terrain/terrain_session.gd")
const _ToolRow := preload("res://addons/blackout_terrain/tool_row.gd")
const _PaintValues := preload("res://addons/blackout_terrain/paint_values.gd")

## The order of the tool row. The session file stores the name of a tool,
## so a new tool may go anywhere.
enum Tool { WALL_LINE, ROOM, DOORWAY, LEVEL_ABOVE, LADDER, STAIRS, ROOF, WALL_STYLE,
	DECOR, SELECT, PLACE }

const TOOL_NAMES := ["Wall line", "Room", "Doorway", "Level above", "Ladder", "Stairs",
	"Roof", "Wall style", "Decor", "Select tiles", "Place"]

## The tooltip of each tool: its gesture and its Shift.
const TOOL_TIPS := [
	"Drag along tile edges, on one axis. Shift removes the walls under the line.",
	"Drag a rectangle: level ground, the floor, the area, and walls on the border. "
		+ "Shift removes the walls in the rectangle.",
	"Click a wall edge. The wall goes from both sides. Shift puts it back.",
	"Click inside a closed room, or drag a rectangle. The plane above gets a floor. "
		+ "Shift sets the tiles back to void.",
	"Click a tile. The ladder goes straight up: its twin stands on the same tile "
		+ "of the plane above. R turns it. Shift removes the pair.",
	"Click the tile at the foot. The flight rises over the tiles in front, and its "
		+ "twin stands past the top step on the plane above. R turns it. "
		+ "Shift removes the pair.",
	"Click inside a closed room, or drag a rectangle. The plane above gets the roof. "
		+ "Shift removes it.",
	"Drag the brush ring over walls. Shift paints the default style.",
	"Click a tile. R turns the next one. Shift removes the decor on the tile.",
	"Drag a rectangle, or click inside a room. Ctrl adds. Shift takes tiles out.",
	"Click to place a copy of the template. R turns it, F mirrors it. "
		+ "Alt replaces the objects on its tiles.",
]

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
const KEEP := _PaintValues.KEEP

## The names of [enum StructureTools.Base], in its order.
const BASE_NAMES := ["Highest corner", "Lowest corner", "Average corner"]

## The lowest roof pitch and overhang, and the overhang and the blend ring
## that a new session starts with.
const PITCH_MIN := 1
const OVERHANG_MIN := 0
const OVERHANG_DEFAULT := 1
const BLEND_DEFAULT := 1

const _SECTION := "build"

## The floor, the area, and the wall style. The dock puts this strip above
## the tabs. A test reads the panel alone, and the strip then has no parent.
var values := _PaintValues.new()

## False in a test: a change of a choice then writes no session file.
var persist := true:
	set(on):
		persist = on
		values.persist = on

var _tools := _ToolRow.new()
var _level := _Fields.check("Level the ground", true,
	"The Room tool levels the ground under the room to the Level to rule.")
var _base := OptionButton.new()
var _block := _Fields.check("Block outside", false,
	"Set Blocked on the ring of tiles around the room, for a dungeon.")
var _ladder := OptionButton.new()
var _stairs := OptionButton.new()
var _roof_shape := OptionButton.new()
var _pitch := SpinBox.new()
var _overhang := SpinBox.new()
var _roof_floor := OptionButton.new()
var _brush := SpinBox.new()
var _decor := OptionButton.new()
var _every_plane := _Fields.check("Select every plane", true,
	"A gesture takes the edited plane and each plane above it.")
var _template := OptionButton.new()
var _template_key := LineEdit.new()
var _blend := SpinBox.new()
var _place_areas := _Fields.check("Place the areas", true,
	"A copy takes the areas of the template. Off: it keeps the areas of the ground.")
var _walls_down := _Fields.check("Walls down (V)", false,
	"Draw each wall low, so you see into a room.")

## Each option: `{controls, tools}`. The controls show while the current
## tool is in `tools`.
var _options: Array[Dictionary] = []

## Quarter turns of the roof: the ridge of a gable, the low edge of a shed.
## R and Shift+R change it, and the hint line names it.
var _turn := 0

## The rotation of the next decor. R and Shift+R change it while the Decor
## tool is on.
var _decor_turn := 0

## The quarter turns of the next ladder or flight of stairs. R and Shift+R
## change it while the Ladder or the Stairs tool is on.
var _climb_turn := 0


func _init() -> void:
	name = "Build"
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_tools.set_tools(TOOL_NAMES, TOOL_TIPS)
	add_child(_tools)
	_add_room_rows()
	_add_climb_rows()
	_add_roof_rows()
	_add_wall_style_rows()
	_add_decor_rows()
	_add_select_rows()
	_add_place_rows()
	_load_settings()
	_connect_controls()
	_show_tool_options()


# ─── Reading the choices ────────────────────────────────────────────────────

func current_tool() -> int:
	return _tools.current_tool()


func tool_name() -> String:
	return TOOL_NAMES[current_tool()]


## The floor of the options, or "" to keep.
func floor_name() -> String:
	return values.floor_name()


## The area of the options, or "" to keep.
func area_name() -> String:
	return values.area_name()


## The up kind of the climb tool that is on: the Ladder list, else the
## Stairs list.
func climb_kind() -> String:
	if current_tool() == Tool.LADDER:
		return _Fields.text_of(_ladder)

	return _Fields.text_of(_stairs)


## The quarter turns of the next ladder or flight.
func climb_turn() -> int:
	return _climb_turn


## The climb of the options in words, for the hint line.
func climb_summary() -> String:
	var kind := climb_kind()
	var run := TileTables.climb_run(kind)

	if run == 0:
		return "%s, front to the %s" % [kind, FACING_NAMES[_climb_turn]]

	return "%s, rises %d tiles to the %s" % [kind, run, FACING_NAMES[_climb_turn]]


func walls_down() -> bool:
	return _walls_down.button_pressed


## The "Walls down" box. The dock puts it in the block strip, so it is on
## every tab.
func walls_down_box() -> CheckBox:
	return _walls_down


## The decor kind of the Decor tool, or "" when the server names none.
func decor_kind() -> String:
	return _Fields.text_of(_decor)


## The rotation of the next decor.
func decor_turn() -> int:
	return _decor_turn


## The decor of the options in words, for the hint line.
func decor_summary() -> String:
	return "%s, front to the %s" % [decor_kind(), FACING_NAMES[_decor_turn]]


## The wall style of the Wall line, the Room, and the Wall style brush.
func wall_style() -> String:
	return values.wall_style()


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

	return _Fields.text_of(_template)


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
	options.floor_name = _Fields.text_of(_roof_floor)

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
	values.sample(floor_type, area, style)

	if not decor.is_empty():
		_Fields.select_text(_decor, decor["kind"])
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


## Turn the next ladder or flight by `steps` quarter turns clockwise: R and
## Shift+R.
func turn_climb(steps: int) -> void:
	_climb_turn = posmod(_climb_turn + steps, FACING_NAMES.size())
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
	_tools.select_tool(tool_index)
	_show_tool_options()


## Pick a tool as a click on its button does: a number key.
func pick_tool(tool_index: int) -> void:
	_tools.pick_tool(tool_index)


## Fill the template list: [constant CLIPBOARD], then `keys`. Keeps the row
## of the same name, or picks `chosen` when it is not empty.
func set_template_keys(keys: PackedStringArray, chosen: String = "") -> void:
	var keep := template_choice() if chosen.is_empty() else chosen

	_template.clear()
	_Fields.fill(_template, [CLIPBOARD] + Array(keys))
	_Fields.select_text(_template, keep)


## Pick the row `choice` of the template list, and save nothing.
func choose_template(choice: String) -> void:
	_Fields.select_text(_template, choice)


## Fill the paint values, the roof floors, and the decor kinds again from
## [TileTables]. The plugin calls it after a change on the Tables tab. A
## choice follows `rename`, `{table, old, new}`.
func refill_tables(rename := {}) -> void:
	values.refill(rename)
	_Fields.refill(_roof_floor, Array(TileTables.roof_floor_types()),
		_Fields.follow_of(rename, TileTables.FLOOR_TYPES))
	_Fields.refill(_decor, StructureTools.decor_kinds(),
		_Fields.follow_of(rename, TileTables.DECOR_KINDS))
	_on_changed()


func set_every_plane(on: bool) -> void:
	_every_plane.button_pressed = on


# ─── Building the panel ─────────────────────────────────────────────────────

## Register `controls` as the options of `tools`.
func _option(tools: Array, controls: Array) -> void:
	_options.append({"controls": controls, "tools": tools})


## A labelled row that shows for `tools`.
func _option_row(tools: Array, label_text: String, control: Control, tip := "") -> void:
	var label := _Fields.row(self, label_text, control, tip)

	_option(tools, [label, control])


## A check box that shows for `tools`.
func _option_check(tools: Array, box: CheckBox) -> void:
	add_child(box)
	_option(tools, [box])


func _add_room_rows() -> void:
	_option_check([Tool.ROOM], _level)
	_Fields.fill(_base, BASE_NAMES)
	_option_row([Tool.ROOM, Tool.PLACE], "Level to", _base,
		"The corner that the levelled ground takes: the Room tool and the Place tool.")
	_option_check([Tool.ROOM], _block)


func _add_climb_rows() -> void:
	_Fields.fill(_ladder, StructureTools.ladder_pairs().keys())
	_option_row([Tool.LADDER], "Ladder (R turns)", _ladder,
		"The Ladder tool places this climb, and its twin on the same tile of the plane above.")
	_Fields.fill(_stairs, StructureTools.stairs_pairs().keys())
	_option_row([Tool.STAIRS], "Stairs (R turns)", _stairs,
		"The Stairs tool places this flight, and its twin past the top step on the plane above.")


func _add_roof_rows() -> void:
	_Fields.fill(_roof_shape, RoofShapes.SHAPE_NAMES)
	_roof_shape.select(RoofShapes.Shape.GABLE)
	_option_row([Tool.ROOF], "Roof shape", _roof_shape,
		"R turns the ridge of a gable or the low edge of a shed.")
	_Fields.spin(_pitch, PITCH_MIN, RoofShapes.PITCH_MAX, 1.0, RoofShapes.PITCH_DEFAULT)
	_option_row([Tool.ROOF], "Pitch ([ and ])", _pitch,
		"Height steps for each tile of roof.")
	_Fields.spin(_overhang, OVERHANG_MIN, RoofShapes.OVERHANG_MAX, 1.0, OVERHANG_DEFAULT)
	_option_row([Tool.ROOF], "Overhang", _overhang, "Tiles of roof past each wall.")
	_Fields.fill(_roof_floor, Array(TileTables.roof_floor_types()))
	_option_row([Tool.ROOF], "Roof floor", _roof_floor,
		"The floor type of the roof tiles on the plane above.")


func _add_wall_style_rows() -> void:
	_Fields.spin(_brush, BRUSH_MIN, BRUSH_MAX, BRUSH_STEP, BRUSH_DEFAULT)
	_option_row([Tool.WALL_STYLE], "Brush radius ([ and ])", _brush,
		"Tiles. Under one tile, the brush paints the tile under the mouse only.")


func _add_decor_rows() -> void:
	_Fields.fill(_decor, StructureTools.decor_kinds())
	_option_row([Tool.DECOR], "Decor (R turns)", _decor,
		"The Decor tool places this kind. R and Shift+R turn the next one.")


func _add_select_rows() -> void:
	_option_check([Tool.SELECT], _every_plane)
	_template_key.placeholder_text = "a key: a-z, 0-9, and _"
	_option_row([Tool.SELECT], "Template key", _template_key,
		"The key of the template that Save as template writes.")

	var save := _Fields.button("Save as template", func() -> void:
		save_template_requested.emit(template_key()),
		"Write the tile selection as a template file under blackout/world/structures/.")

	add_child(save)
	_option([Tool.SELECT], [save])


func _add_place_rows() -> void:
	set_template_keys(StructureTemplate.list_keys(StructureTemplate.world_directory()))
	_option_row([Tool.PLACE], "Template (R turns, F mirrors)", _template,
		"The Place tool places this template. The first row is the clipboard.")

	var reload := _Fields.button("Reload templates", reload_templates_requested.emit,
		"Read the template directory again.")

	add_child(reload)
	_option([Tool.PLACE], [reload])
	_Fields.spin(_blend, 0.0, StructurePlace.BLEND_MAX, 1.0, BLEND_DEFAULT)
	_option_row([Tool.PLACE], "Blend ring", _blend,
		"Tiles around a copy whose corners move part of the way to its base.")
	_option_check([Tool.PLACE], _place_areas)


## Show the options of the current tool, and hide the rest.
func _show_tool_options() -> void:
	var tool_index := current_tool()

	for option: Dictionary in _options:
		var shown: bool = tool_index in option["tools"]

		for control: Control in option["controls"]:
			control.visible = shown


func _connect_controls() -> void:
	_tools.tool_changed.connect(func(_index: int) -> void:
		_show_tool_options()
		_on_changed())
	values.changed.connect(_on_changed)

	for list: OptionButton in [_base, _ladder, _stairs, _roof_shape, _roof_floor, _decor,
			_template]:
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


# ─── The session file ───────────────────────────────────────────────────────

## The index of the tool that the session file names, or the first tool. A
## file of before 10/16/2026 stores an index, and the order changed then.
## Thus an index reads as no name.
static func tool_index(saved: Variant) -> int:
	return maxi(TOOL_NAMES.find(saved), 0)


func _load_settings() -> void:
	if not persist:
		return

	_tools.select_tool(tool_index(_Session.read(_SECTION, "tool", "")))
	_level.button_pressed = _Session.read(_SECTION, "level", true)
	_base.select(_Session.read(_SECTION, "base", 0))
	_block.button_pressed = _Session.read(_SECTION, "block_outside", false)
	_Fields.select_text(_ladder, _Session.read(_SECTION, "ladder", ""))
	_Fields.select_text(_stairs, _Session.read(_SECTION, "stairs", ""))
	_climb_turn = posmod(_Session.read(_SECTION, "climb_turn", 0), FACING_NAMES.size())
	_roof_shape.select(_Session.read(_SECTION, "roof_shape", _roof_shape.selected))
	_pitch.value = _Session.read(_SECTION, "roof_pitch", int(_pitch.value))
	_overhang.value = _Session.read(_SECTION, "roof_overhang", int(_overhang.value))
	_turn = _Session.read(_SECTION, "roof_turn", 0)
	_Fields.select_text(_roof_floor, _Session.read(_SECTION, "roof_floor", ""))
	_brush.value = _Session.read(_SECTION, "wall_style_brush", _brush.value)
	_Fields.select_text(_decor, _Session.read(_SECTION, "decor", ""))
	_decor_turn = posmod(_Session.read(_SECTION, "decor_turn", 0), FACING_NAMES.size())
	_every_plane.button_pressed = _Session.read(_SECTION, "every_plane", true)
	_Fields.select_text(_template, _Session.read(_SECTION, "template", ""))
	_blend.value = _Session.read(_SECTION, "blend_ring", int(_blend.value))
	_place_areas.button_pressed = _Session.read(_SECTION, "place_areas", true)
	_walls_down.button_pressed = _Session.read(_SECTION, "walls_down", false)


func _save_settings() -> void:
	if not persist:
		return

	_Session.write(_SECTION, {
		"tool": tool_name(),
		"level": _level.button_pressed,
		"base": _base.selected,
		"block_outside": _block.button_pressed,
		"ladder": _Fields.text_of(_ladder),
		"stairs": _Fields.text_of(_stairs),
		"climb_turn": _climb_turn,
		"roof_shape": _roof_shape.selected,
		"roof_pitch": int(_pitch.value),
		"roof_overhang": int(_overhang.value),
		"roof_turn": _turn,
		"roof_floor": _Fields.text_of(_roof_floor),
		"wall_style_brush": _brush.value,
		"decor": decor_kind(),
		"decor_turn": _decor_turn,
		"every_plane": _every_plane.button_pressed,
		"template": template_choice(),
		"blend_ring": int(_blend.value),
		"place_areas": _place_areas.button_pressed,
		"walls_down": _walls_down.button_pressed,
	})
