@tool
class_name TerrainDock
extends VBoxContainer
## The panel of the terrain editor. Three strips sit above the tabs, and
## the status box sits below them.
##
## - **The file strip**: Save, with the count of changed chunks, Revert, the
##   scene switch, and in the workbench the clear.
## - **The block strip**: the centre chunk, the plane, Load, four pan
##   buttons, "Go to tile", and "Walls down".
## - **The paint values**: the floor, the area, and the wall style that the
##   tools of the Paint tab and of the Build tab write ([PaintValues]).
##
## The tabs:
##
## - **Paint**: the tool row, and the options of the current tool.
## - **Build**: the structure tools ([BuildPanel], DESIGN-0013). While this
##   tab shows, the mouse in the 3D view drives the Build tools.
## - **Objects**: the selected object and its fields, a filter, and every
##   object of the block.
## - **World**: the block report, the marks to show with their legend, and
##   "Check world" with its findings. The state of the tile sync is here too.
## - **Look**: the colours of the ground, the water, the walls, and the
##   props. The wall heights, and the fog and the light of each area
##   (`look_panel.gd`). Each change writes a look file and redraws the block.
## - **Tables**: the rows of the areas, the floor types, the wall styles,
##   and the decor kinds (`tables_panel.gd`, 10/14/2026). New, save, rename,
##   and remove a row. "New" beside a list of the paint values opens it.
##
## The plugin reads the choices from here. This panel changes no terrain
## itself: each control sends a signal, and the plugin acts.
##
## The lists of floor types, areas, wall styles, and object kinds come from
## [TileTables]. A change on the Tables tab reaches every list at once
## ([method refresh_tables]). The flags come from the generated constants.
##
## ## The noise settings
##
## The seed, the frequency, and the amplitude persist in [constant CONFIG_PATH]
## beside this script, so every author gets the same noise from the same
## seed. They are not in the chunk file: the file stores the baked integer
## heights, and the server cannot run Godot's noise. Every other choice
## persists in the session file, outside the repo (`terrain_session.gd`).

signal load_requested(centre: Vector2i, plane: int)
signal plane_requested(plane: int)
signal tile_requested(tile: Vector2i)
signal save_requested
signal revert_requested
signal noise_fill_requested
signal overlays_changed
signal selection_action(action: String)
signal selection_edited(kind: String, rotation: int, text: String, look: Dictionary)
signal object_chosen(thing: Dictionary)
signal check_requested
signal finding_chosen(finding: Dictionary)
signal tab_changed
signal tool_changed
signal clear_workbench_asked
signal switch_scene_requested

const _Const := preload("res://autoload/blackout_constants.gd")
const _Fields := preload("res://addons/blackout_terrain/terrain_fields.gd")
const _Session := preload("res://addons/blackout_terrain/terrain_session.gd")
const _ToolRow := preload("res://addons/blackout_terrain/tool_row.gd")
const _LookPanel := preload("res://addons/blackout_terrain/look_panel.gd")
const _TablesPanel := preload("res://addons/blackout_terrain/tables_panel.gd")

const CONFIG_PATH := "res://addons/blackout_terrain/terrain_editor.cfg"
const _CONFIG_SECTION := "noise"
const _SECTION := "paint_tab"

## The names of [enum TerrainWorld.UpperPlanes], in its order.
const UPPER_PLANE_NAMES := ["Hidden", "Ghost", "Solid"]

## The height of the status box under the tabs, in pixels: about six lines.
const STATUS_HEIGHT := 120.0

## The colour of a note in the findings list. A note fails no test.
const NOTE_COLOR := Color(0.6, 0.75, 1.0)

## The colour of the block report with a load error or a seam fault.
const WARNING_COLOR := Color(1.0, 0.75, 0.4)

## The radius step of the bracket keys, in tiles.
const RADIUS_STEP := 0.5

enum Tool { RAISE, LOWER, FLATTEN, SMOOTH, RAMP, NOISE, FLOOR, FLAGS, AREA, OBJECT, SELECT }

const TOOL_NAMES := ["Raise", "Lower", "Flatten", "Smooth", "Ramp", "Noise",
	"Floor", "Flags", "Area", "Object", "Pick object"]

const TOOL_TIPS := [
	"Drag to raise the ground. Shift lowers.",
	"Drag to lower the ground.",
	"Drag to level the ground to the height under the first press.",
	"Drag to smooth the ground.",
	"Click the start corner, then the end corner.",
	"Drag to add noise from the seed below.",
	"Drag to paint the Floor of the strip. Shift picks the floor under the mouse.",
	"Drag to set the checked flags. Shift clears them.",
	"Drag to paint the Area of the strip. Shift picks the area under the mouse.",
	"Click to place the Object. Shift removes the last object on the tile.",
	"Click an object. Click again for the next one on the tile. Drag it to move it.",
]

## The hint line of each Paint tool. `%s` takes the values of the moment.
const TOOL_HINTS := [
	"Raise: drag to raise the ground. Shift lowers. Radius %.1f tiles, strength %d steps.",
	"Lower: drag to lower the ground. Radius %.1f tiles, strength %d steps.",
	"Flatten: drag to level the ground to the height under the first press. Radius %.1f tiles.",
	"Smooth: drag to smooth the ground. Radius %.1f tiles.",
	"Ramp: click the start corner, then the end corner. The ramp is %.1f tiles wide.",
	"Noise: drag to add noise. Radius %.1f tiles, amplitude %d steps.",
	"Floor: drag to paint %s. Shift picks the floor under the mouse.",
	"Flags: drag to set the checked flags. Shift clears them. Radius %.1f tiles.",
	"Area: drag to paint %s. Shift picks the area under the mouse.",
	"Object: click to place a %s at rotation %d. Shift removes the last object on the tile.",
	"Pick object: click an object. Click again for the next one. Drag it to move it.",
]

## The second line of every Paint hint: the keys of every tab.
const KEYS_HINT := "Plane %d. Page Up and Page Down change it. V: walls down. " \
	+ "[ and ]: radius. 1 to 9 and 0: tools. Esc: cancel. Ctrl+S saves."

## What the Floor and Area brushes say with "(keep)" chosen.
const KEEP_HINT := "%s: pick a floor in the strip first. (keep) paints nothing."

## The tools that change heights, and so repeat while the button is held.
const SCULPT_TOOLS := [Tool.RAISE, Tool.LOWER, Tool.FLATTEN, Tool.SMOOTH,
	Tool.NOISE]

## The tools that use the brush radius.
const RADIUS_TOOLS := [Tool.RAISE, Tool.LOWER, Tool.FLATTEN, Tool.SMOOTH, Tool.RAMP,
	Tool.NOISE, Tool.FLOOR, Tool.FLAGS, Tool.AREA]

## The tools that use the brush shape. The Ramp uses the radius as a width,
## so it has no shape.
const SHAPE_TOOLS := [Tool.RAISE, Tool.LOWER, Tool.FLATTEN, Tool.SMOOTH,
	Tool.NOISE, Tool.FLOOR, Tool.FLAGS, Tool.AREA]

## The tools that "Protect structures" guards.
const PROTECT_TOOLS := [Tool.RAISE, Tool.LOWER, Tool.FLATTEN, Tool.SMOOTH, Tool.RAMP,
	Tool.NOISE]

## The actions of the selection buttons, as [signal selection_action] sends
## them.
const ACTION_TURN := "turn"
const ACTION_TURN_BACK := "turn_back"
const ACTION_DELETE := "delete"
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

## The marks of the overlay in the legend, by key of [TerrainOverlay].
const MARK_LEGEND := ["blocked", "water", "wall", "border", "locked"]

## False in a test: the dock and the Build tab then write no session file.
var persist := true:
	set(on):
		persist = on
		_build.persist = on
		_look.persist = on

var _tabs := TabContainer.new()
var _page: VBoxContainer

# The file strip
var _save := Button.new()
var _revert := Button.new()
var _switch_scene := Button.new()
var _clear_workbench := Button.new()

# The block strip
var _centre_x := SpinBox.new()
var _centre_y := SpinBox.new()
var _plane := SpinBox.new()
var _go_x := SpinBox.new()
var _go_y := SpinBox.new()

# The Paint tab
var _tools := _ToolRow.new()
var _radius := SpinBox.new()
var _shape := OptionButton.new()
var _strength := SpinBox.new()
var _kind := OptionButton.new()
var _rotation := SpinBox.new()
var _text := LineEdit.new()
var _variant := OptionButton.new()
var _flag_boxes: Array[CheckBox] = []
var _seed := SpinBox.new()
var _frequency := SpinBox.new()
var _amplitude := SpinBox.new()
var _protect := CheckBox.new()
var _options: Array[Dictionary] = []

# The Objects tab
var _selection := Label.new()
var _selection_buttons: Array[Button] = []
var _follow := Button.new()
var _sel_kind := OptionButton.new()
var _sel_rotation := SpinBox.new()
var _sel_text := LineEdit.new()
var _sel_variant := OptionButton.new()
var _sel_scale := SpinBox.new()
var _sel_turn: HBoxContainer
var _sel_offset: HBoxContainer
var _sel_rows: Array[Control] = []

## The variant keys of the model of a kind: `func(kind: String) ->
## PackedStringArray`. The plugin gives it, from the served tree of the
## repo. Empty until then, so each Variant list offers Base and Any only.
var variants_for: Callable = func(_kind: String) -> PackedStringArray:
	return PackedStringArray()

## The first two rows of a Variant list: the base model, and the auto
## variant. [method _variant_choice] turns a row back into the look value.
const VARIANT_BASE := "Base"
const VARIANT_ANY := "Any (by tile)"
var _filter := LineEdit.new()
var _objects := ItemList.new()
var _show_decor := CheckBox.new()

## The rows of the last [method set_objects], before the decor filter.
var _object_rows: Array[Dictionary] = []

## True while [method set_selection] fills the fields, so they send nothing.
var _filling := false

# The World tab
var _block_report := Label.new()
var _show_flags := CheckBox.new()
var _show_areas := CheckBox.new()
var _show_links := CheckBox.new()
var _show_lower := CheckBox.new()
var _upper := OptionButton.new()
var _findings_label: Label
var _legend := HFlowContainer.new()
var _findings := ItemList.new()
var _sync_state := Label.new()

var _build := BuildPanel.new()
var _build_page: Control
var _look := _LookPanel.new()
var _tables := _TablesPanel.new()
var _tables_page: Control
var _confirm := ConfirmationDialog.new()
var _confirm_action := Callable()
var _status := Label.new()


func _init() -> void:
	name = "Terrain"
	_build_file_strip()
	_build_block_strip()
	add_child(_build.values)
	_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_tabs.tab_changed.connect(func(_tab: int) -> void: tab_changed.emit())
	add_child(_tabs)
	_page = _new_page("Paint")
	_build_paint_tab()
	_page = _new_page("Build")
	_build_page = _page.get_parent()
	_page.add_child(_build)
	_page = _new_page("Objects")
	_build_object_rows()
	_page = _new_page("World")
	_build_world_tab()
	_page = _new_page("Look")
	_page.add_child(_look)
	_page = _new_page("Tables")
	_tables_page = _page.get_parent()
	_page.add_child(_tables)
	_build.values.new_row_requested.connect(show_new_row)
	_build_status_box()
	_confirm.confirmed.connect(func() -> void:
		if _confirm_action.is_valid():
			_confirm_action.call())
	add_child(_confirm)
	_load_noise_settings()
	_load_session()
	_show_tool_options()


# ─── Reading the choices ────────────────────────────────────────────────────

func current_tool() -> int:
	return _tools.current_tool()


func tool_name() -> String:
	return TOOL_NAMES[current_tool()]


func radius() -> float:
	return _radius.value


## The shape of the brush of the current tool: a [enum TerrainBrushes.Shape].
## A tool with no shape, the Ramp for example, gives a circle.
func brush_shape() -> int:
	if current_tool() in SHAPE_TOOLS:
		return _shape.selected

	return TerrainBrushes.Shape.CIRCLE


func strength() -> int:
	return int(_strength.value)


## The floor to paint, or "" with "(keep)" chosen.
func floor_name() -> String:
	return _build.values.floor_name()


## The area to paint, or "" with "(keep)" chosen.
func area_name() -> String:
	return _build.values.area_name()


func kind() -> String:
	return _Fields.text_of(_kind)


func object_rotation() -> int:
	return int(_rotation.value)


## The words of a new sign, with no space at either end.
func object_text() -> String:
	return _text.text.strip_edges()


## The look of a new object: its variant choice, or `{}` for the base.
func object_look() -> Dictionary:
	return _look_with_variant({}, _variant)


## Fill a Variant list for `kind`: Base, Any, then each variant of the
## model of the kind. A list that has the chosen row keeps it.
func _refill_variants(list: OptionButton, kind: String) -> void:
	var names := [VARIANT_BASE, VARIANT_ANY]

	names.append_array(variants_for.call(kind))
	_Fields.refill(list, names)


## `look` with the variant of a Variant list in it, or with none for Base.
static func _look_with_variant(look: Dictionary, list: OptionButton) -> Dictionary:
	var out := look.duplicate(true)
	var choice := _Fields.text_of(list)

	out.erase(_Const.LOOK_VARIANT_KEY)

	if choice == VARIANT_ANY:
		out[_Const.LOOK_VARIANT_KEY] = _Const.LOOK_VARIANT_ANY
	elif choice != VARIANT_BASE and not choice.is_empty():
		out[_Const.LOOK_VARIANT_KEY] = choice

	return out


## The row of a Variant list for the variant of a look.
static func _variant_row(look: Dictionary) -> String:
	var choice: String = look.get(_Const.LOOK_VARIANT_KEY, "")

	if choice.is_empty():
		return VARIANT_BASE

	if choice == _Const.LOOK_VARIANT_ANY:
		return VARIANT_ANY

	return choice


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


## The Look tab: the colours, the wall heights, and the area looks.
func look_panel() -> Control:
	return _look


## The Tables tab: the rows of the four server tables.
func tables_panel() -> Control:
	return _tables


## Show the Tables tab on `table` with an empty form: a "New" button of the
## paint values strip.
func show_new_row(table: String) -> void:
	_tabs.current_tab = _tables_page.get_index()
	_tables.start_new_row(table)


## Fill every list of the server tables again, after a change on the
## Tables tab. A choice follows `rename`, `{table, old, new}`. The Tables
## tab selects `select`, when it is not empty.
func refresh_tables(rename := {}, select := "") -> void:
	var follow := _Fields.follow_of(rename, TileTables.DECOR_KINDS)

	_build.refill_tables(rename)
	_look.refill_tables(rename)
	_tables.refresh(rename, select)
	_Fields.refill(_kind, TileTables.object_kinds().keys(), follow)
	_Fields.refill(_sel_kind, TileTables.object_kinds().keys(), follow)
	_refill_variants(_variant, kind())
	_refill_variants(_sel_variant, _Fields.text_of(_sel_kind))


## True while the Build tab shows.
func build_active() -> bool:
	return _tabs.get_current_tab_control() == _build_page


## The hint line of the Paint tool of the moment, for the 3D view. `plane`
## is the edited plane.
func paint_hint(plane: int) -> String:
	var line: String = TOOL_HINTS[current_tool()]

	match current_tool():
		Tool.RAISE, Tool.LOWER:
			line = line % [radius(), strength()]
		Tool.FLATTEN, Tool.SMOOTH, Tool.RAMP, Tool.FLAGS:
			line = line % radius()
		Tool.NOISE:
			line = line % [radius(), noise_amplitude()]
		Tool.FLOOR, Tool.AREA:
			line = _paint_value_hint()
		Tool.OBJECT:
			line = line % [kind(), object_rotation()]

	return line + "\n" + KEYS_HINT % plane


## The hint of the Floor brush or the Area brush: the value, or the
## "(keep)" warning.
func _paint_value_hint() -> String:
	var is_floor := current_tool() == Tool.FLOOR
	var value := floor_name() if is_floor else area_name()

	if value.is_empty():
		return KEEP_HINT % tool_name()

	return TOOL_HINTS[current_tool()] % value


# ─── Writing the state ──────────────────────────────────────────────────────

## Select `picked` in the floor list, for the pick with Shift.
func pick_floor(picked: String) -> void:
	_build.values.pick_floor(picked)


func pick_area(picked: String) -> void:
	_build.values.pick_area(picked)


func set_block(centre: Vector2i, plane: int) -> void:
	_centre_x.set_value_no_signal(centre.x)
	_centre_y.set_value_no_signal(centre.y)
	_plane.set_value_no_signal(plane)


func set_status(text: String) -> void:
	_status.text = text


## The report of the block on the World tab: the load errors and the seam
## faults. It stays until the next load, so a stroke cannot replace it.
func set_block_report(lines: PackedStringArray, warn: bool) -> void:
	_block_report.text = "\n".join(lines)

	if warn:
		_block_report.add_theme_color_override("font_color", WARNING_COLOR)
	else:
		_block_report.remove_theme_color_override("font_color")


## Show the count of changed chunk files on the Save button.
func set_unsaved(count: int) -> void:
	_save.text = "Save" if count == 0 else "Save (%d changed)" % count
	_revert.disabled = count == 0


## Fill the object list with `{tile, kind, rotation, text}` rows. With "Show
## decor" off, the list leaves out each decor row, so a busy shop does not
## flood it (DESIGN-0013 section 6.5). The filter keeps the rows with its
## text.
func set_objects(things: Array[Dictionary]) -> void:
	_object_rows = things
	_objects.clear()

	for thing: Dictionary in listed_objects(things, _show_decor.button_pressed,
			_filter.text):
		var line := describe_object(thing)
		var row := _objects.add_item(line)

		_objects.set_item_metadata(row, thing)
		_objects.set_item_tooltip(row, line)
		_objects.set_item_custom_fg_color(row, TerrainOverlay.kind_color(thing["kind"]))


## One row of the object list. A look shows as its text, so a filter on
## a variant key or on "scale" finds the row.
static func describe_object(thing: Dictionary) -> String:
	var line := "%s  %s  r%d" % [thing["kind"], thing["tile"], thing["rotation"]]

	if not thing["text"].is_empty():
		line += "  \"%s\"" % thing["text"]

	var look: Dictionary = thing.get("look", {})

	if not look.is_empty():
		line += "  " + ChunkFile.look_text(look)

	return line


## The rows of `things` that the object list shows: every row, or every row
## that is not decor, with the text of `filter` in it.
static func listed_objects(things: Array[Dictionary], show_decor: bool,
		filter := "") -> Array[Dictionary]:
	var listed: Array[Dictionary] = []
	var wanted := filter.strip_edges().to_lower()

	for thing: Dictionary in things:
		if not show_decor and StructureTools.is_decor(thing["kind"]):
			continue

		if not wanted.is_empty() and not wanted in describe_object(thing).to_lower():
			continue

		listed.append(thing)

	return listed


## Show the selected object, and whether it leads anywhere. The fields take
## its kind, its rotation, and its text, and send nothing.
func set_selection(selected: Dictionary, link_end: Dictionary) -> void:
	for button: Button in _selection_buttons:
		button.disabled = selected.is_empty()

	for control: Control in _sel_rows:
		control.visible = not selected.is_empty()

	_follow.disabled = link_end.is_empty()

	if selected.is_empty():
		_selection.text = "Nothing selected. Use Pick object on the Paint tab, or click a row."
		return

	_selection.text = "%s at %s" % [selected["kind"], selected["tile"]]

	if not link_end.is_empty():
		_selection.text += ". Leads to %s on plane %d" % [link_end["tile"], link_end["plane"]]

	var look: Dictionary = selected.get("look", {})

	_filling = true
	_Fields.select_text(_sel_kind, selected["kind"])
	_sel_rotation.set_value_no_signal(selected["rotation"])
	_sel_text.text = selected["text"]
	_sel_text.editable = TerrainChecks.takes_text(selected["kind"])
	_refill_variants(_sel_variant, selected["kind"])
	_Fields.select_text(_sel_variant, _variant_row(look))
	_sel_scale.set_value_no_signal(look.get(_Const.LOOK_SCALE_KEY, _Const.LOOK_SCALE_UNIT))
	_Fields.set_axes(_sel_turn, look.get(_Const.LOOK_TURN_KEY, [0, 0, 0]))
	_Fields.set_axes(_sel_offset, look.get(_Const.LOOK_OFFSET_KEY, [0, 0, 0]))
	_filling = false


## Fill the findings list. `errors` are chunk files that do not read.
func set_findings(findings: Array[Dictionary], errors: PackedStringArray) -> void:
	_findings.clear()
	_findings_label.text = "Findings (click one to go there)"

	for error: String in errors:
		_findings.add_item("unreadable: " + error)

	for finding: Dictionary in findings:
		var line := TerrainChecks.describe(finding)
		var row := _findings.add_item(line)

		_findings.set_item_metadata(row, finding)
		_findings.set_item_tooltip(row, line)

		if TerrainChecks.is_note(finding):
			_findings.set_item_custom_fg_color(row, NOTE_COLOR)

	if findings.is_empty() and errors.is_empty():
		_findings.add_item("No finding. The world passes every check.")


## An edit landed after the last check. The list stays, and its label says
## that the rows can be old.
func mark_findings_stale() -> void:
	if _findings.item_count > 0:
		_findings_label.text = "Findings (changed since the last check)"


func set_sync_state(text: String) -> void:
	_sync_state.text = text


## Show the buttons for the structure workbench (`on`), or for the world.
func set_workbench(on: bool) -> void:
	_switch_scene.text = "Open world" if on else "Open workbench"
	_switch_scene.tooltip_text = "Open the terrain editor on the world chunk files." if on \
		else "Open the structure workbench: the editor on scratch chunk files."
	_clear_workbench.visible = on


func select_tool(tool_index: int) -> void:
	_tools.select_tool(tool_index)
	_show_tool_options()


## Pick a Paint tool as a click on its button does: a number key.
func pick_tool(tool_index: int) -> void:
	_tools.pick_tool(tool_index)


## Step the brush radius: [ and ].
func step_radius(steps: int) -> void:
	_radius.value = _radius.value + steps * RADIUS_STEP


## Ask `text`, and run `action` on Yes.
func confirm(text: String, action: Callable) -> void:
	_confirm.dialog_text = text
	_confirm_action = action
	_confirm.popup_centered()


# ─── The strips ─────────────────────────────────────────────────────────────

func _build_file_strip() -> void:
	var strip := HFlowContainer.new()

	_save.text = "Save"
	_save.tooltip_text = "Write each changed chunk file. Ctrl+S does the same."
	_save.pressed.connect(save_requested.emit)
	strip.add_child(_save)
	_revert.text = "Revert"
	_revert.tooltip_text = "Read the chunk files again, and drop each unsaved change."
	_revert.pressed.connect(revert_requested.emit)
	strip.add_child(_revert)
	_switch_scene.pressed.connect(switch_scene_requested.emit)
	strip.add_child(_switch_scene)
	_clear_workbench.text = "Clear workbench"
	_clear_workbench.tooltip_text = "Delete the scratch chunk files. The templates stay."
	_clear_workbench.pressed.connect(clear_workbench_asked.emit)
	strip.add_child(_clear_workbench)
	add_child(strip)
	set_workbench(false)
	set_unsaved(0)


func _build_block_strip() -> void:
	var strip := HFlowContainer.new()

	_pair(strip, "Chunk", _Fields.spin(_centre_x, -4096.0, 4096.0, 1.0, 0.0),
		"The centre chunk of the block: the south-west chunk of the middle four.")
	strip.add_child(_Fields.spin(_centre_y, -4096.0, 4096.0, 1.0, 0.0))
	strip.add_child(_Fields.button("Load", func() -> void:
		load_requested.emit(_centre(), int(_plane.value)),
		"Load the block around the chunk. A move saves the old block first."))
	_pan_buttons(strip)
	_pair(strip, "Plane", _Fields.spin(_plane, _Const.TILE_GROUND_PLANE,
		_Const.CHUNK_PLANE_MAX, 1.0, 0.0), "The edited plane. 0 is the ground.")
	_plane.value_changed.connect(func(value: float) -> void:
		plane_requested.emit(int(value)))
	_pair(strip, "Go to tile", _Fields.spin(_go_x, -65536.0, 65536.0, 1.0, 0.0),
		"Load the block of the tile, and put the beacon on it.")
	strip.add_child(_Fields.spin(_go_y, -65536.0, 65536.0, 1.0, 0.0))
	strip.add_child(_Fields.button("Go", func() -> void:
		tile_requested.emit(Vector2i(int(_go_x.value), int(_go_y.value)))))
	strip.add_child(_build.walls_down_box())
	add_child(strip)


## Four buttons that move the block one chunk. North is +y.
func _pan_buttons(strip: HFlowContainer) -> void:
	for pair: Array in [["W", Vector2i(-1, 0)], ["E", Vector2i(1, 0)],
			["N", Vector2i(0, 1)], ["S", Vector2i(0, -1)]]:
		var step: Vector2i = pair[1]

		strip.add_child(_Fields.button(pair[0], func() -> void:
			load_requested.emit(_centre() + step, int(_plane.value)),
			"Move the block one chunk to the %s." % pair[0]))


func _centre() -> Vector2i:
	return Vector2i(int(_centre_x.value), int(_centre_y.value))


## A label and a control side by side in a strip.
func _pair(strip: Container, label_text: String, control: Control, tip: String) -> void:
	var label := Label.new()

	label.text = label_text
	label.tooltip_text = tip
	control.tooltip_text = tip
	strip.add_child(label)
	strip.add_child(control)


# ─── The Paint tab ──────────────────────────────────────────────────────────

func _build_paint_tab() -> void:
	_tools.set_tools(TOOL_NAMES, TOOL_TIPS)
	_tools.tool_changed.connect(func(_index: int) -> void:
		_show_tool_options()
		_save_session()
		tool_changed.emit())
	_page.add_child(_tools)
	_option_row(RADIUS_TOOLS, "Radius ([ and ])",
		_Fields.spin(_radius, 0.0, 32.0, RADIUS_STEP, 3.0), "Tiles.")
	_Fields.fill(_shape, TerrainBrushes.SHAPE_NAMES)
	_option_row(SHAPE_TOOLS, "Shape", _shape,
		"A square has a side of twice the radius, on the tile edges.")
	_option_row(SCULPT_TOOLS, "Strength", _Fields.spin(_strength, 1.0, 64.0, 1.0, 1.0),
		"Height steps for each dab.")
	_build_object_option_rows()
	_build_flag_rows()
	_protect.text = "Protect structures"
	_protect.tooltip_text = "A sculpt skips each corner of a wall and of a tile under a floor."
	_page.add_child(_protect)
	_option(PROTECT_TOOLS, [_protect])
	_build_noise_rows()


func _build_object_option_rows() -> void:
	_Fields.fill(_kind, TileTables.object_kinds().keys())
	_option_row([Tool.OBJECT], "Object", _kind, "The kind that a click places.")
	_option_row([Tool.OBJECT], "Rotation", _Fields.spin(_rotation, 0.0,
		_Const.CHUNK_ROTATION_COUNT - 1, 1.0, 0.0),
		"Quarter turns clockwise. 0 faces north.")
	_text.max_length = _Const.CHUNK_TEXT_MAX_CHARS
	_text.placeholder_text = "The words of a new %s" % _Const.OBJECT_SIGNPOST_KIND
	_option_row([Tool.OBJECT], "Sign text", _text, "A sign kind takes these words.")
	_refill_variants(_variant, kind())
	_kind.item_selected.connect(func(_index: int) -> void: _refill_variants(_variant, kind()))
	_option_row([Tool.OBJECT], "Variant", _variant,
		"The model that a new object draws: the base, any variant by a hash of the tile, "
		+ "or one variant. The Objects tab edits the rest of the look.")


func _build_flag_rows() -> void:
	var flags := HFlowContainer.new()

	for choice: Array in FLAG_CHOICES:
		var box := CheckBox.new()

		box.text = choice[0]
		flags.add_child(box)
		_flag_boxes.append(box)

	_flag_boxes[0].button_pressed = true
	_option_row([Tool.FLAGS], "Flags", flags, "The Flags brush sets these. Shift clears them.")


func _build_noise_rows() -> void:
	_option_row([Tool.NOISE], "Noise seed",
		_Fields.spin(_seed, 0.0, 2147483647.0, 1.0, 0.0),
		"Shared with every author, in terrain_editor.cfg.")
	_option_row([Tool.NOISE], "Noise frequency",
		_Fields.spin(_frequency, 0.001, 0.5, 0.001, 0.02), "Lower is wider hills.")
	_option_row([Tool.NOISE], "Noise amplitude",
		_Fields.spin(_amplitude, 1.0, 512.0, 1.0, 32.0), "Height steps.")

	for spin: SpinBox in [_seed, _frequency, _amplitude]:
		spin.value_changed.connect(_on_noise_changed)

	var fill := _Fields.button("Fill centre chunk", noise_fill_requested.emit,
		"Fill the centre chunk with noise from the seed.")

	_page.add_child(fill)
	_option([Tool.NOISE], [fill])


## Register `controls` as the options of `tools`.
func _option(tools: Array, controls: Array) -> void:
	_options.append({"controls": controls, "tools": tools})


func _option_row(tools: Array, label_text: String, control: Control, tip := "") -> void:
	var label := _Fields.row(_page, label_text, control, tip)

	_option(tools, [label, control])


func _show_tool_options() -> void:
	var tool_index := current_tool()

	for option: Dictionary in _options:
		var shown: bool = tool_index in option["tools"]

		for control: Control in option["controls"]:
			control.visible = shown


# ─── The Objects tab ────────────────────────────────────────────────────────

func _build_object_rows() -> void:
	_selection.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_page.add_child(_selection)
	_build_selection_fields()
	_build_selection_buttons()
	_filter.placeholder_text = "Filter the list"
	_filter.text_changed.connect(func(_text: String) -> void: set_objects(_object_rows))
	_page.add_child(_filter)
	_objects.custom_minimum_size = Vector2(0, 260)
	_objects.item_selected.connect(func(row: int) -> void:
		object_chosen.emit(_objects.get_item_metadata(row)))
	_Fields.row(_page, "Objects in the block", _objects)
	_show_decor.text = "Show decor"
	_show_decor.button_pressed = true
	_show_decor.toggled.connect(func(_pressed: bool) -> void:
		set_objects(_object_rows))
	_page.add_child(_show_decor)
	set_selection({}, {})


## The kind, the rotation, the text, and the look of the selected object. A
## change sends [signal selection_edited] at once.
func _build_selection_fields() -> void:
	_Fields.fill(_sel_kind, TileTables.object_kinds().keys())
	_sel_kind.item_selected.connect(func(_index: int) -> void:
		_refill_variants(_sel_variant, _Fields.text_of(_sel_kind))
		_send_selection())
	_sel_rows.append(_Fields.row(_page, "Kind", _sel_kind))
	_sel_rows.append(_sel_kind)
	_Fields.spin(_sel_rotation, 0.0, _Const.CHUNK_ROTATION_COUNT - 1, 1.0, 0.0)
	_sel_rotation.value_changed.connect(func(_value: float) -> void: _send_selection())
	_sel_rows.append(_Fields.row(_page, "Rotation", _sel_rotation,
		"Quarter turns clockwise. 0 faces north."))
	_sel_rows.append(_sel_rotation)
	_sel_text.max_length = _Const.CHUNK_TEXT_MAX_CHARS
	_sel_text.text_submitted.connect(func(_text: String) -> void: _send_selection())
	_sel_text.focus_exited.connect(_send_selection)
	_sel_rows.append(_Fields.row(_page, "Sign text", _sel_text,
		"The words of a sign. Enter applies them."))
	_sel_rows.append(_sel_text)
	_build_look_fields()


## The look of the selected object (10/16/2026): its variant, its scale in
## percent, its tilt in degrees, and its nudge in hundredths of a tile. A
## field at its default leaves its key out of the look.
func _build_look_fields() -> void:
	_sel_variant.item_selected.connect(func(_index: int) -> void: _send_selection())
	_sel_rows.append(_Fields.row(_page, "Variant", _sel_variant,
		"The model this object draws: the base, any variant by a hash of the tile, "
		+ "or one variant."))
	_sel_rows.append(_sel_variant)
	_Fields.spin(_sel_scale, _Const.LOOK_SCALE_MIN, _Const.LOOK_SCALE_MAX, 1.0,
		_Const.LOOK_SCALE_UNIT)
	_sel_scale.suffix = "%"
	_sel_scale.value_changed.connect(func(_value: float) -> void: _send_selection())
	_sel_rows.append(_Fields.row(_page, "Scale", _sel_scale,
		"Percent of the normal size. %d is the normal size." % _Const.LOOK_SCALE_UNIT))
	_sel_rows.append(_sel_scale)
	_sel_turn = _Fields.axes_row(_Const.LOOK_TURN_MAX, _send_selection)
	_sel_rows.append(_Fields.row(_page, "Tilt", _sel_turn,
		"Degrees on each axis, over the rotation. x leans forward, y turns, z leans to the side."))
	_sel_rows.append(_sel_turn)
	_sel_offset = _Fields.axes_row(_Const.LOOK_OFFSET_MAX, _send_selection)
	_sel_rows.append(_Fields.row(_page, "Nudge", _sel_offset,
		"Hundredths of a tile: x east, y up, z north. The nudge does not turn with the object."))
	_sel_rows.append(_sel_offset)


## The look that the fields show, with each key at its default left out.
func _selection_look() -> Dictionary:
	var look := _look_with_variant({}, _sel_variant)
	var scale := int(_sel_scale.value)
	var turn := _Fields.axes_of(_sel_turn)
	var offset := _Fields.axes_of(_sel_offset)

	if scale != _Const.LOOK_SCALE_UNIT:
		look[_Const.LOOK_SCALE_KEY] = scale

	if turn.any(func(number: int) -> bool: return number != 0):
		look[_Const.LOOK_TURN_KEY] = turn

	if offset.any(func(number: int) -> bool: return number != 0):
		look[_Const.LOOK_OFFSET_KEY] = offset

	return look


func _send_selection() -> void:
	if not _filling:
		selection_edited.emit(_Fields.text_of(_sel_kind), int(_sel_rotation.value),
			_sel_text.text.strip_edges(), _selection_look())


func _build_selection_buttons() -> void:
	var buttons := HFlowContainer.new()

	for row: Array in [["Turn", ACTION_TURN, "One quarter turn clockwise."],
			["Turn back", ACTION_TURN_BACK, "One quarter turn counter-clockwise."],
			["Delete", ACTION_DELETE, "Remove the object from its tile."]]:
		var button := _Fields.button(row[0], selection_action.emit.bind(row[1]), row[2])

		buttons.add_child(button)
		_selection_buttons.append(button)

	_follow.text = "Follow link"
	_follow.tooltip_text = "Load the block where this transition or climb leads."
	_follow.pressed.connect(selection_action.emit.bind(ACTION_FOLLOW))
	buttons.add_child(_follow)
	_page.add_child(buttons)


# ─── The World tab ──────────────────────────────────────────────────────────

func _build_world_tab() -> void:
	_block_report.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_Fields.row(_page, "Block", _block_report,
		"The load errors and the seam faults of the block. They stay until the next load.")

	for pair: Array in [[_show_flags, "Show flags", true],
			[_show_areas, "Show areas", false], [_show_links, "Show links", true],
			[_show_lower, "Show the planes below", true]]:
		var box: CheckBox = pair[0]

		box.text = pair[1]
		box.button_pressed = pair[2]
		box.toggled.connect(func(_pressed: bool) -> void: _on_overlays_changed())
		_page.add_child(box)

	_Fields.fill(_upper, UPPER_PLANE_NAMES)
	_upper.item_selected.connect(func(_index: int) -> void: _on_overlays_changed())
	_Fields.row(_page, "The planes above", _upper,
		"Hidden, a dim ghost, or solid.")
	_build_legend()
	_build_check_rows()


## The colours of the marks and of the object categories, as text in each
## colour.
func _build_legend() -> void:
	_Fields.row(_page, "Legend", _legend)
	refresh_legend()


## Fill the legend again: the Look tab changed a mark colour.
func refresh_legend() -> void:
	for child: Node in _legend.get_children():
		_legend.remove_child(child)
		child.queue_free()

	for key: String in MARK_LEGEND:
		_legend.add_child(_Fields.swatch(TerrainOverlay.MARK_NAMES[key],
			Color(TerrainOverlay.mark(key), 1.0)))

	for category: String in TerrainOverlay.CATEGORY_COLORS:
		_legend.add_child(_Fields.swatch(category, TerrainOverlay.category_color(category)))


func _build_check_rows() -> void:
	_page.add_child(_Fields.button("Check world", check_requested.emit,
		"Run the content rules of the server on the chunk files, with the unsaved block in place."))
	_findings.custom_minimum_size = Vector2(0, 200)
	_findings.item_selected.connect(func(row: int) -> void:
		var finding: Variant = _findings.get_item_metadata(row)

		if finding is Dictionary:
			finding_chosen.emit(finding))
	_findings_label = _Fields.row(_page, "Findings (click one to go there)", _findings)
	_sync_state.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_Fields.row(_page, "Since the last tile sync", _sync_state)


func _on_overlays_changed() -> void:
	_save_session()
	overlays_changed.emit()


# ─── The frame ──────────────────────────────────────────────────────────────

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


# ─── The noise settings file, and the session file ──────────────────────────

func _load_noise_settings() -> void:
	var config := ConfigFile.new()

	if config.load(CONFIG_PATH) != OK:
		return

	_seed.set_value_no_signal(config.get_value(_CONFIG_SECTION, "seed", _seed.value))
	_frequency.set_value_no_signal(
		config.get_value(_CONFIG_SECTION, "frequency", _frequency.value))
	_amplitude.set_value_no_signal(
		config.get_value(_CONFIG_SECTION, "amplitude", _amplitude.value))


## Keep every other section of the file.
func _on_noise_changed(_value: float) -> void:
	if not persist:
		return

	var config := ConfigFile.new()

	config.load(CONFIG_PATH)
	config.set_value(_CONFIG_SECTION, "seed", int(_seed.value))
	config.set_value(_CONFIG_SECTION, "frequency", _frequency.value)
	config.set_value(_CONFIG_SECTION, "amplitude", int(_amplitude.value))
	config.save(CONFIG_PATH)


func _load_session() -> void:
	if not persist:
		return

	_tools.select_tool(_Session.read(_SECTION, "tool", 0))
	_radius.value = _Session.read(_SECTION, "radius", _radius.value)
	_shape.select(_Session.read(_SECTION, "shape", TerrainBrushes.Shape.CIRCLE))
	_strength.value = _Session.read(_SECTION, "strength", int(_strength.value))
	_protect.button_pressed = _Session.read(_SECTION, "protect", false)
	_show_flags.button_pressed = _Session.read(_SECTION, "show_flags", true)
	_show_areas.button_pressed = _Session.read(_SECTION, "show_areas", false)
	_show_links.button_pressed = _Session.read(_SECTION, "show_links", true)
	_show_lower.button_pressed = _Session.read(_SECTION, "show_lower", true)
	_upper.select(_Session.read(_SECTION, "upper_planes", 0))

	for spin: SpinBox in [_radius, _strength]:
		spin.value_changed.connect(func(_value: float) -> void: _save_session())

	_protect.toggled.connect(func(_pressed: bool) -> void: _save_session())
	_shape.item_selected.connect(func(_index: int) -> void: _save_session())


func _save_session() -> void:
	if not persist:
		return

	_Session.write(_SECTION, {
		"tool": current_tool(),
		"radius": _radius.value,
		"shape": _shape.selected,
		"strength": int(_strength.value),
		"protect": _protect.button_pressed,
		"show_flags": _show_flags.button_pressed,
		"show_areas": _show_areas.button_pressed,
		"show_links": _show_links.button_pressed,
		"show_lower": _show_lower.button_pressed,
		"upper_planes": _upper.selected,
	})
