@tool
extends VBoxContainer
## The Look tab of the terrain editor: the colours of the ground, the
## water, the walls, and the props, the height of each wall style, and the
## fog and the light of each area. Each control writes a look file under
## `res://world/look/` ([TerrainPalette], [AreaLook]), and the block then
## draws again, so the author sees each change on the ground.
##
## The server names the floor types, the wall styles, and the areas. The
## lists here come from [TileTables]. Thus, a new row of the Tables tab gets
## its picker at once ([method refill_tables]), with no edit here. A row
## with no colour in the file shows the fallback colour of the client table.
##
## A drag of a picker sends many changes. A short timer joins them, so one
## drag writes the file and rebuilds the block a few times, not hundreds.
##
## "Preview the area light" applies the look of the chosen area to the sun
## and the environment of the editor scene. The game draws the same row
## through the same routine, [method AreaLook.apply_to].
##
## The shadow minimum is one field for every area, above the area list. It
## is no field of an area row, so "Reset area" keeps it.
##
## This panel makes no undo entry. The look file is the state, and the two
## Reset buttons give the fallback back.

## The terrain palette file changed.
signal palette_changed

## The light of one scenery key changed in the file.
signal light_changed(scenery: String)

## The look of one area changed in the file.
signal area_look_changed(area: String)

## The shadow minimum of every area changed in the file.
signal shadow_minimum_changed

## The preview went on for `area`, or off with "".
signal preview_changed(area: String)

## "Reset colours": the plugin asks, then calls [method reset_palette].
signal reset_requested

## "Reset area": the plugin asks, then calls [method reset_area].
signal area_reset_requested(area: String)

## The colours of the editor marks changed. They belong to the author, in
## the session file, and no look file.
signal marks_changed

const _Fields := preload("res://addons/blackout_terrain/terrain_fields.gd")
const _Session := preload("res://addons/blackout_terrain/terrain_session.gd")

const _MARKS_SECTION := "marks"

## Seconds after the last change before the file write.
const DEBOUNCE := 0.15

## The range of a wall height, in height steps.
const HEIGHT_MIN := 1.0
const HEIGHT_MAX := 64.0

## The range of the wall top lighten.
const LIGHTEN_MAX := 1.0
const LIGHTEN_STEP := 0.05

## The ranges of the area fields.
const FOG_MAX := 200.0
const ENERGY_MAX := 4.0
const ENERGY_STEP := 0.05
const ELEVATION_LIMIT := 90.0
const AZIMUTH_LIMIT := 180.0

## The step of the shadow minimum. Its range is 0 to 1.
const SHADOW_MINIMUM_STEP := 0.05

## The fields of a light, in the order of the tab, in the shape of
## [constant AREA_FIELDS]. An energy of zero gives no light.
const LIGHT_FIELDS := [
	[LightLook.FIELD_COLOR, "Light colour", "color"],
	[LightLook.FIELD_ENERGY, "Light energy (0 gives none)", [0.0, LightLook.ENERGY_MAX, ENERGY_STEP]],
	[LightLook.FIELD_RANGE, "Light range (tiles)", [0.0, LightLook.RANGE_MAX, 0.5]],
	[LightLook.FIELD_HEIGHT, "Bulb height (units)", [0.0, LightLook.HEIGHT_MAX, 0.05]],
]

## The fields of an area look, in the order of the tab: the field, the
## label, and the kind: "color" or a `[low, high, step]` range.
const AREA_FIELDS := [
	["fog_color", "Fog colour", "color"],
	["fog_begin", "Fog begins (tiles)", [0.0, FOG_MAX, 1.0]],
	["fog_end", "Fog ends (tiles)", [0.0, FOG_MAX, 1.0]],
	["sun_color", "Sun colour", "color"],
	["sun_energy", "Sun energy", [0.0, ENERGY_MAX, ENERGY_STEP]],
	["sun_elevation", "Sun elevation (degrees)", [-ELEVATION_LIMIT, ELEVATION_LIMIT, 1.0]],
	["sun_azimuth", "Sun azimuth (degrees)", [-AZIMUTH_LIMIT, AZIMUTH_LIMIT, 1.0]],
	["ambient_color", "Ambient colour", "color"],
	["ambient_energy", "Ambient energy", [0.0, ENERGY_MAX, ENERGY_STEP]],
]

## False in a test: the panel then writes no look file, and only sends its
## signals.
var writes_files := true

## False in a test: the mark colours then read and write no session file.
var persist := true

var _mark_pickers := {}
var _marks_timer := Timer.new()

var _floor_grid: GridContainer
var _wall_grid: GridContainer
var _floor_pickers := {}
var _cliff := ColorPickerButton.new()
var _water := ColorPickerButton.new()
var _prop_pickers := {}
var _wall_pickers := {}
var _wall_heights := {}
var _lighten := SpinBox.new()
var _light_key := OptionButton.new()
var _light_controls := {}
var _shadow_minimum := SpinBox.new()
var _area := OptionButton.new()
var _area_controls := {}
var _preview := CheckBox.new()
var _palette_timer := Timer.new()
var _light_timer := Timer.new()
var _shadow_timer := Timer.new()
var _area_timer := Timer.new()

## True while [method refresh] fills the controls, so they send nothing.
var _filling := false


func _init() -> void:
	name = "Look"
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_build_floor_rows()
	_build_wall_rows()
	_build_prop_rows()
	add_child(_Fields.button("Reset colours", reset_requested.emit,
		"Take every colour and height out of the look file. Each one then "
		+ "shows the fallback of the client table."))
	_build_light_rows()
	_build_area_rows()
	_build_mark_rows()
	_build_timers()
	refresh()


# ─── Reading ────────────────────────────────────────────────────────────────

## The area of the area section.
func area() -> String:
	return _Fields.text_of(_area)


## The look of the area fields, as [AreaLook] holds a look.
func area_look() -> Dictionary:
	var look := {}

	for row: Array in AREA_FIELDS:
		var control: Control = _area_controls[row[0]]

		if row[2] is String:
			look[row[0]] = (control as ColorPickerButton).color
		else:
			look[row[0]] = (control as SpinBox).value

	return look


## The shadow minimum of the field, for every area.
func shadow_minimum() -> float:
	return _shadow_minimum.value


func preview_on() -> bool:
	return _preview.button_pressed


## The scenery key of the light section.
func light_scenery() -> String:
	return _Fields.text_of(_light_key)


## The light of the light fields, as [LightLook] holds a row.
func light_row() -> Dictionary:
	var light := {}

	for row: Array in LIGHT_FIELDS:
		var control: Control = _light_controls[row[0]]

		if row[2] is String:
			light[row[0]] = (control as ColorPickerButton).color
		else:
			light[row[0]] = (control as SpinBox).value

	return light


# ─── Writing ────────────────────────────────────────────────────────────────

## Fill each control from the look files and the fallback tables.
func refresh() -> void:
	_filling = true

	for floor_name: String in _floor_pickers:
		_floor_pickers[floor_name].color = FloorPalette.color_of(floor_name)

	_cliff.color = FloorPalette.cliff()
	_water.color = FloorPalette.water()

	for prop: String in _prop_pickers:
		_prop_pickers[prop].color = FloorPalette.prop(prop)

	for style: String in _wall_pickers:
		_wall_pickers[style].color = WallPalette.side_color(style)
		_wall_heights[style].value = WallPalette.height_steps(style)

	_lighten.value = WallPalette.top_lighten()
	_shadow_minimum.value = AreaLook.shadow_minimum()
	_show_light()
	_show_area()

	for key: String in _mark_pickers:
		_mark_pickers[key].color = _mark_color(key)

	_filling = false


## The colour of a mark key, or of a category key, as the overlay draws it.
static func _mark_color(key: String) -> Color:
	if key.begins_with(TerrainOverlay.CATEGORY_KEY):
		return TerrainOverlay.category_color(key.trim_prefix(TerrainOverlay.CATEGORY_KEY))

	return TerrainOverlay.mark(key)


## Give the overlay the mark colours of the session file. The dock calls it
## one time at start.
func load_marks() -> void:
	if not persist:
		return

	var colors := {}

	for key: String in _mark_pickers:
		var saved: Variant = _Session.read(_MARKS_SECTION, key, "")

		if typeof(saved) == TYPE_STRING and Color.html_is_valid(saved):
			colors[key] = Color.html(saved)

	TerrainOverlay.set_marks(colors)
	refresh()


## "Reset marks": every mark back to its default colour.
func reset_marks() -> void:
	TerrainOverlay.set_marks({})
	_write_marks()
	refresh()


## "Reset colours", after the confirmation of the plugin.
func reset_palette() -> void:
	if writes_files:
		TerrainPalette.reset()

	refresh()
	palette_changed.emit()


## "Reset area", after the confirmation of the plugin.
func reset_area(reset: String) -> void:
	if writes_files:
		AreaLook.reset_look(reset)

	refresh()
	area_look_changed.emit(reset)


## "Reset light": the scenery key of the light section goes back to its
## fallback light, or to none. It is one row, so the button asks nothing.
func reset_light() -> void:
	var scenery := light_scenery()

	if writes_files:
		LightLook.reset_light(scenery)

	refresh()
	light_changed.emit(scenery)


# ─── Building ───────────────────────────────────────────────────────────────

## Build the pickers of the floor types and of the wall styles again, and
## fill the area list again, after a change on the Tables tab. The area
## choice follows `rename`, `{table, old, new}`.
func refill_tables(rename := {}) -> void:
	_fill_floor_grid()
	_fill_wall_grid()
	_Fields.refill(_light_key, Array(TileTables.scenery_keys()))
	_Fields.refill(_area, Array(TileTables.keys(TileTables.AREAS)),
		_Fields.follow_of(rename, TileTables.AREAS))
	refresh()


func _build_floor_rows() -> void:
	_floor_grid = _grid("Floors", 2)
	_fill_floor_grid()


## One picker for each floor type of [TileTables], then the cliff and the
## water.
func _fill_floor_grid() -> void:
	_clear(_floor_grid)
	_floor_pickers.clear()

	for floor_name: String in TileTables.keys(TileTables.FLOOR_TYPES):
		_floor_pickers[floor_name] = _picker(_floor_grid, floor_name)

	_cliff = _picker(_floor_grid, "cliff face")
	_water = _picker(_floor_grid, "water")


func _build_wall_rows() -> void:
	_wall_grid = _grid("Walls: colour, and height in steps (16 are one tile)", 3)
	_fill_wall_grid()
	_Fields.spin(_lighten, 0.0, LIGHTEN_MAX, LIGHTEN_STEP, 0.0)
	_lighten.value_changed.connect(func(_value: float) -> void: _palette_touched())
	_Fields.row(self, "Wall top lighten", _lighten,
		"How much lighter the top of a wall is than its sides.")


## A picker and a height field for each wall style of [TileTables].
func _fill_wall_grid() -> void:
	_clear(_wall_grid)
	_wall_pickers.clear()
	_wall_heights.clear()

	for style: String in TileTables.keys(TileTables.WALL_STYLES):
		var height := SpinBox.new()

		_wall_pickers[style] = _picker(_wall_grid, style)
		_Fields.spin(height, HEIGHT_MIN, HEIGHT_MAX, 1.0, HEIGHT_MIN)
		height.value_changed.connect(func(_value: float) -> void: _palette_touched())
		_wall_grid.add_child(height)
		_wall_heights[style] = height


## Free every child of `grid`.
static func _clear(grid: GridContainer) -> void:
	for child: Node in grid.get_children():
		grid.remove_child(child)
		child.queue_free()


func _build_prop_rows() -> void:
	var grid := _grid("Props: the plain shapes of a climb and of decor", 2)

	for prop: String in TerrainPalette.PROP_KEYS:
		_prop_pickers[prop] = _picker(grid, prop)


## The light of a scenery key: the key list, then one control for each
## field of [constant LIGHT_FIELDS].
func _build_light_rows() -> void:
	_Fields.fill(_light_key, Array(TileTables.scenery_keys()))
	_light_key.item_selected.connect(func(_index: int) -> void: _show_light())
	_Fields.row(self, "Light: the scenery that gives it", _light_key,
		"The scenery key whose light the fields below edit. A lamp post is one.")

	for row: Array in LIGHT_FIELDS:
		var control: Control

		if row[2] is String:
			control = ColorPickerButton.new()
			control.edit_alpha = false
			control.color_changed.connect(func(_color: Color) -> void: _light_touched())
		else:
			var field := SpinBox.new()

			_Fields.spin(field, row[2][0], row[2][1], row[2][2], 0.0)
			field.value_changed.connect(func(_value: float) -> void: _light_touched())
			control = field

		_light_controls[row[0]] = control
		_Fields.row(self, row[1], control)

	add_child(_Fields.button("Reset light", reset_light,
		"Take the light of the scenery key out of the look file. It then gives "
		+ "its fallback light, or none."))


func _build_area_rows() -> void:
	_Fields.spin(_shadow_minimum, 0.0, 1.0, SHADOW_MINIMUM_STEP,
		AreaLook.SHADOW_MINIMUM_DEFAULT)
	_shadow_minimum.value_changed.connect(func(_value: float) -> void: _shadow_touched())
	_Fields.row(self, "Shadow minimum (every area)", _shadow_minimum,
		"The share of the sun that reaches a place in full shadow, for example "
		+ "the inside of a structure. 0 gives a full shadow, and 1 gives no shadow.")

	_Fields.fill(_area, Array(TileTables.keys(TileTables.AREAS)))
	_area.item_selected.connect(func(_index: int) -> void: _show_area())
	_Fields.row(self, "Area: the fog and the light", _area,
		"The area whose look the fields below edit.")

	for row: Array in AREA_FIELDS:
		var control: Control

		if row[2] is String:
			control = ColorPickerButton.new()
			control.edit_alpha = false
			control.color_changed.connect(func(_color: Color) -> void: _area_touched())
		else:
			var field := SpinBox.new()

			_Fields.spin(field, row[2][0], row[2][1], row[2][2], 0.0)
			field.value_changed.connect(func(_value: float) -> void: _area_touched())
			control = field

		_area_controls[row[0]] = control
		_Fields.row(self, row[1], control)

	_preview.text = "Preview the area light"
	_preview.tooltip_text = "Apply the fog and the light of the area to the editor scene."
	_preview.toggled.connect(func(on: bool) -> void:
		preview_changed.emit(area() if on else ""))
	add_child(_preview)
	add_child(_Fields.button("Reset area", func() -> void:
		area_reset_requested.emit(area()),
		"Take the area out of the look file. It then shows the fallback look."))


## The colours of the marks of the editor: the overlay, the Build outlines,
## the beacon, and the ghost planes. A player never sees them, so they are
## no look file. They persist in the session file.
func _build_mark_rows() -> void:
	var grid := _grid("Editor marks: yours, in the session file", 2)

	for key: String in TerrainOverlay.MARK_DEFAULTS:
		_mark_pickers[key] = _mark_picker(grid, key, TerrainOverlay.MARK_NAMES[key])

	for category: String in TerrainOverlay.CATEGORY_COLORS:
		_mark_pickers[TerrainOverlay.CATEGORY_KEY + category] = _mark_picker(grid,
			TerrainOverlay.CATEGORY_KEY + category, "marker: " + category)

	add_child(_Fields.button("Reset marks", reset_marks,
		"Every mark back to its default colour."))


func _mark_picker(grid: GridContainer, key: String, label_text: String) -> ColorPickerButton:
	var picker := _picker(grid, label_text)

	picker.edit_alpha = not key.begins_with(TerrainOverlay.CATEGORY_KEY)
	picker.color_changed.disconnect(picker.color_changed.get_connections()[0]["callable"])
	picker.color_changed.connect(func(_color: Color) -> void: _marks_touched())

	return picker


func _build_timers() -> void:
	for timer: Timer in [_palette_timer, _light_timer, _shadow_timer, _area_timer,
			_marks_timer]:
		timer.one_shot = true
		timer.wait_time = DEBOUNCE
		add_child(timer)

	_palette_timer.timeout.connect(_write_palette)
	_light_timer.timeout.connect(_write_light)
	_shadow_timer.timeout.connect(_write_shadow_minimum)
	_area_timer.timeout.connect(_write_area)
	_marks_timer.timeout.connect(_write_marks)


## A grid of `columns` under a label.
func _grid(title: String, columns: int) -> GridContainer:
	var grid := GridContainer.new()

	grid.columns = columns
	_Fields.row(self, title, grid)

	return grid


## A label and a colour picker in `grid`.
func _picker(grid: GridContainer, label_text: String) -> ColorPickerButton:
	var label := Label.new()
	var picker := ColorPickerButton.new()

	label.text = label_text
	picker.edit_alpha = false
	picker.custom_minimum_size.x = 80.0
	picker.color_changed.connect(func(_color: Color) -> void: _palette_touched())
	grid.add_child(label)
	grid.add_child(picker)

	return picker


# ─── The writes ─────────────────────────────────────────────────────────────

func _palette_touched() -> void:
	if not _filling and is_inside_tree():
		_palette_timer.start()


func _light_touched() -> void:
	if not _filling and is_inside_tree():
		_light_timer.start()


func _shadow_touched() -> void:
	if not _filling and is_inside_tree():
		_shadow_timer.start()


func _area_touched() -> void:
	if not _filling and is_inside_tree():
		_area_timer.start()


func _marks_touched() -> void:
	if not _filling and is_inside_tree():
		_marks_timer.start()


## Give the overlay the colours of the pickers, and keep them in the
## session file. A picker at its default colour leaves no row.
func _write_marks() -> void:
	var colors := {}
	var saved := {}

	for key: String in _mark_pickers:
		var color: Color = _mark_pickers[key].color

		saved[key] = ""

		if color != _default_mark(key):
			colors[key] = color
			saved[key] = color.to_html(true)

	TerrainOverlay.set_marks(colors)

	if persist:
		_Session.write(_MARKS_SECTION, saved)

	marks_changed.emit()


static func _default_mark(key: String) -> Color:
	if key.begins_with(TerrainOverlay.CATEGORY_KEY):
		return TerrainOverlay.CATEGORY_COLORS.get(key.trim_prefix(TerrainOverlay.CATEGORY_KEY),
			TerrainOverlay.COLOR_UNKNOWN_KIND)

	return TerrainOverlay.MARK_DEFAULTS[key]


## Write every colour and height of the tab into the palette file.
func _write_palette() -> void:
	if writes_files:
		var floors := {}
		var props := {}
		var walls := {}

		for floor_name: String in _floor_pickers:
			floors[floor_name] = _floor_pickers[floor_name].color

		for prop: String in _prop_pickers:
			props[prop] = _prop_pickers[prop].color

		for style: String in _wall_pickers:
			walls[style] = [_wall_pickers[style].color, int(_wall_heights[style].value)]

		TerrainPalette.save_palette(floors, _cliff.color, _water.color, props, walls,
			_lighten.value)

	palette_changed.emit()


func _write_light() -> void:
	if writes_files:
		LightLook.save_light(light_scenery(), light_row())

	light_changed.emit(light_scenery())


func _write_shadow_minimum() -> void:
	if writes_files:
		AreaLook.save_shadow_minimum(shadow_minimum())

	shadow_minimum_changed.emit()


func _write_area() -> void:
	if writes_files:
		AreaLook.save_look(area(), area_look())

	area_look_changed.emit(area())


## Fill the light fields from the light of the chosen scenery key. A key
## with no light shows the default row with an energy of zero.
func _show_light() -> void:
	var was_filling := _filling
	var light := LightLook.light_of(light_scenery())

	if light.is_empty():
		light = LightLook.DEFAULT.duplicate()
		light[LightLook.FIELD_ENERGY] = 0.0

	_filling = true

	for row: Array in LIGHT_FIELDS:
		var control: Control = _light_controls[row[0]]

		if row[2] is String:
			(control as ColorPickerButton).color = light[row[0]]
		else:
			(control as SpinBox).set_value_no_signal(light[row[0]])

	_filling = was_filling


## Fill the area fields from the look of the chosen area.
func _show_area() -> void:
	var was_filling := _filling
	var look := AreaLook.look_for(area())

	_filling = true

	for row: Array in AREA_FIELDS:
		var control: Control = _area_controls[row[0]]

		if row[2] is String:
			(control as ColorPickerButton).color = look[row[0]]
		else:
			(control as SpinBox).set_value_no_signal(look[row[0]])

	_filling = was_filling

	if _preview.button_pressed:
		preview_changed.emit(area())
