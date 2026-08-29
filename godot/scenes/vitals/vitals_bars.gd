class_name VitalsBars
extends VBoxContainer
## The observer's own resources, as bars.
##
## Presentation only. Every number it draws lives on [CharState]; this file
## decides how it LOOKS, which is the same line the whole client is built on.
##
## ## Bars, not orbs, and top-left
##
## The reference interface puts hitpoints, prayer, run energy and special attack
## in four data orbs around the minimap. Blackout takes the minimap and leaves
## the orbs: an orb is a dial, a bar is a quantity, and the thing a player needs
## to read mid-fight is how much of the quantity is left. Top-left of the world
## pane rather than over the character's head, and separate from the minimap --
## the arrangement World of Warcraft's player frame uses.
##
## ## Two homes, and it is not gold-plating
##
## The console places this control in one of two slots: over the world pane when
## the world is drawn, and in a strip above the log when it is not. A player who
## turns the 3D panes off on a struggling machine must not lose their hit points
## with them -- it is the one number a MUD player cannot play without, and it was
## exactly what would have happened had the bars simply been parented to the
## pane they overlay.
##
## ## Adding a resource is one row
##
## [constant BARS] names the CharState properties each bar reads rather than
## switching on a key, so this file has no branch per resource and gains none.
## The cost is that the names are strings the compiler does not check, which is
## what `test_vitals_bars.gd` exists to cover: **a row naming a property
## CharState does not have is a bug**, and it is caught rather than drawn as an
## empty bar.
##
## Augmentation is the next row, and it is deliberately not written yet. The
## design is a stub -- the vault does not yet name the resource, say how it
## regenerates, or settle whether it is a bar at all -- and `char_vitals` ships
## no field for it. A row here would be a client table waiting on a decision
## nobody has taken.

## Bar geometry. Presentation, so it lives here.
const BAR_WIDTH := 132
const BAR_HEIGHT := 14
const ROW_SEPARATION := 3

## Shown before a resource has ever arrived, so an empty bar at login does not
## read as being dead. Distinguished from a real zero by the maximum, which is
## zero only when the server has said nothing.
const NO_DATA_TEXT := "--/--"

## Where a bar changes colour, as fractions of its maximum, and what it changes
## to. Semantic rather than decorative -- they encode a threshold a player acts
## on -- which is why they are here beside the code that tests the fraction and
## not in the theme.
const COLOR_HEALTHY := Color("4caf50")
const COLOR_HURT := Color("d4a017")
const COLOR_CRITICAL := Color("c0392b")
const COLOR_IDLE := Color(0.55, 0.55, 0.55)
const HURT_BELOW := 0.6
const CRITICAL_BELOW := 0.3

## One row per resource. **Adding a resource is one row here and one field on
## `char_vitals`.**
##
## `current` and `maximum` are CharState PROPERTY NAMES, read with `get()`. A
## key the view switched on would be a dispatch chain growing by one branch per
## resource, which is the shape this codebase replaces with a table everywhere
## else it appears.
##
## `graded` says whether the bar changes colour as it empties. Hit points do,
## because the colour is a warning. A resource that is merely a budget should
## not, and would carry its own `colour` instead.
const BARS: Array = [
	{
		"label": "HP",
		"current": "hp",
		"maximum": "max_hp",
		"graded": true,
	},
]

var _state: CharState

## Parallel to BARS by construction; both are built in one pass.
var _fills: Array[ProgressBar] = []
var _labels: Array[Label] = []


func _init() -> void:
	add_theme_constant_override("separation", ROW_SEPARATION)

	# Nothing here is clickable, and a bar that swallowed a click over the
	# world pane would eat a move the player meant for the tile behind it.
	mouse_filter = Control.MOUSE_FILTER_IGNORE

	for row: Dictionary in BARS:
		_add_row(str(row.get("label", "")))


## Bind to a model and follow it.
##
## Takes the model rather than reaching for a singleton, so this can be opened
## on its own with a hand-built state -- which is what makes it testable without
## a running server, the same as every other view in this client.
func bind(state: CharState) -> void:
	_state = state
	_state.changed.connect(_redraw)
	_redraw()


func _add_row(label_text: String) -> void:
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(row)

	var name_label := Label.new()
	name_label.text = label_text
	name_label.theme_type_variation = &"RowKey"
	name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(name_label)

	var fill := ProgressBar.new()
	fill.custom_minimum_size = Vector2(BAR_WIDTH, BAR_HEIGHT)
	fill.max_value = 1.0
	fill.step = 0.001
	fill.value = 0.0
	fill.show_percentage = false
	fill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(fill)
	_fills.append(fill)

	var reading := Label.new()
	reading.text = NO_DATA_TEXT
	reading.theme_type_variation = &"RowValue"
	reading.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(reading)
	_labels.append(reading)


func _redraw() -> void:
	if _state == null:
		return

	for index: int in BARS.size():
		_redraw_row(index)


func _redraw_row(index: int) -> void:
	var row: Dictionary = BARS[index]
	var current := int(_state.get(str(row.get("current", ""))))
	var maximum := int(_state.get(str(row.get("maximum", ""))))
	var fill := _fills[index]
	var reading := _labels[index]

	# A maximum of zero is "the server has not said", not "you have none". The
	# two look identical on a bar and are not the same thing to a player who
	# has just logged in.
	if maximum <= 0:
		fill.value = 0.0
		fill.modulate = COLOR_IDLE
		reading.text = NO_DATA_TEXT
		return

	var fraction := clampf(float(current) / float(maximum), 0.0, 1.0)

	fill.value = fraction * fill.max_value
	fill.modulate = _colour_for(row, fraction)
	reading.text = "%d/%d" % [current, maximum]


func _colour_for(row: Dictionary, fraction: float) -> Color:
	if not bool(row.get("graded", false)):
		return row.get("colour", COLOR_HEALTHY)

	if fraction < CRITICAL_BELOW:
		return COLOR_CRITICAL

	if fraction < HURT_BELOW:
		return COLOR_HURT

	return COLOR_HEALTHY
