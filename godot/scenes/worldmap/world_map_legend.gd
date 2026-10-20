class_name WorldMapLegend
extends VBoxContainer
## The legend of the world map: one row for each map icon and each marker
## that the map draws (10/19/2026).
##
## ## What each row draws
##
## An icon row draws the map icon of one category through
## [method MapIcons.draw], the call that the map makes. Its words are the label
## that the server gives the category, `OBJECT_CATEGORY_LABELS`. A marker row
## draws its sample through the static draw calls of [WorldMapView]. Thus, a
## row cannot differ from what the map draws.
##
## ## Which rows
##
## One icon row for each category that has a map icon, in the order of
## `OBJECT_CATEGORIES`. A new category with a row in [constant MapIcons.ICONS]
## thus gets a legend row with no edit here. The walk path row shows only
## while Options draws the walk path.
##
## ## A click hides an icon (Nick, 10/19/2026)
##
## Each icon row has a check box, as the OSRS legend does. A click on the box,
## the sample, or the words emits [signal icon_toggled], and [WorldMapView]
## keeps the choice. The legend keeps no choice of its own:
## [method sync] sets each box from the choice that the view keeps.
##
## Author: Nick Hobar
## Creation date: 10/19/2026

## Emitted when the player shows or hides the map icons of one category.
signal icon_toggled(category: String, shown: bool)

const _Const := preload("res://autoload/blackout_constants.gd")

const ICONS_HEADING := "Map icons"
const MARKERS_HEADING := "Markers"
const SELF_TEXT := "You are here"
const FLAG_TEXT := "Destination"
const PATH_TEXT := "Walk path"
const ICON_TIP := "Show or hide these icons on the world map"

## The size of the sample at the start of each row, in pixels.
const SAMPLE_SIZE := Vector2(18, 18)

## The size of a map icon, the mark of the player, and the destination marker
## in a sample, in pixels.
const SAMPLE_ICON_PX := 12.0
const SAMPLE_SELF_PX := 9.0
const SAMPLE_FLAG_PX := 15.0

## Where the pole of the sample flag stands, as a part of the sample width.
const SAMPLE_FLAG_FOOT := 0.3

## How far the sample walk path bends up and down from the middle, in pixels.
const SAMPLE_PATH_BEND := 4.0

## category -> the CheckBox of its row.
var _boxes := {}

var _path_row: Control


func _init() -> void:
	name = "Legend"
	add_child(_heading(ICONS_HEADING))

	for category: String in _Const.OBJECT_CATEGORIES:
		if MapIcons.has_icon(category):
			add_child(_icon_row(category))

	add_child(_heading(MARKERS_HEADING))
	add_child(_row(SELF_TEXT, _draw_self_sample))
	add_child(_row(FLAG_TEXT, _draw_flag_sample))
	_path_row = _row(PATH_TEXT, _draw_path_sample)
	add_child(_path_row)


## The words of one category, from the server. A category with no label shows
## its key.
static func label_of(category: String) -> String:
	return str(_Const.OBJECT_CATEGORY_LABELS.get(category, category))


## Set each check box from the categories that the player hid. Show the walk
## path row only while the map draws the walk path. Emits nothing.
func sync(hidden: PackedStringArray, path_drawn: bool) -> void:
	for category: String in _boxes:
		var box: CheckBox = _boxes[category]

		box.set_pressed_no_signal(not hidden.has(category))

	_path_row.visible = path_drawn


## The categories with an icon row, in order. For tests.
func categories() -> Array[String]:
	var found: Array[String] = []

	for category: String in _boxes:
		found.append(category)

	return found


## The check box of the row of one category, or null. For tests.
func check_box(category: String) -> CheckBox:
	return _boxes.get(category, null)


## True when the walk path row shows. For tests.
func path_row_shown() -> bool:
	return _path_row.visible


# ─── Building ────────────────────────────────────────────────────────────────

func _heading(text: String) -> Label:
	var label := Label.new()

	label.theme_type_variation = &"SectionHeading"
	label.text = text

	return label


## The sample, the words, and the check box of one category. A click on the
## sample or the words reaches the row, and the row clicks the box.
func _icon_row(category: String) -> Control:
	var box := CheckBox.new()
	var row := _row(label_of(category), func(sample: Control) -> void:
		MapIcons.draw(sample, category, sample.size * 0.5, SAMPLE_ICON_PX))

	box.button_pressed = true
	box.focus_mode = Control.FOCUS_NONE
	box.toggled.connect(func(pressed: bool) -> void:
		icon_toggled.emit(category, pressed))
	row.add_child(box)
	row.tooltip_text = ICON_TIP
	row.mouse_filter = Control.MOUSE_FILTER_STOP
	row.gui_input.connect(_on_row_input.bind(row, box))
	_boxes[category] = box

	return row


## A row: a sample that `painter` draws, then the words. The words take the
## spare width, so the check boxes of the icon rows line up at the right.
func _row(text: String, painter: Callable) -> HBoxContainer:
	var row := HBoxContainer.new()
	var sample := Control.new()
	var words := Label.new()

	sample.custom_minimum_size = SAMPLE_SIZE
	sample.mouse_filter = Control.MOUSE_FILTER_IGNORE
	sample.draw.connect(painter.bind(sample))
	words.text = text
	words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(sample)
	row.add_child(words)

	return row


## A left press on the sample or the words of an icon row clicks its box.
func _on_row_input(event: InputEvent, row: Control, box: CheckBox) -> void:
	var click := event as InputEventMouseButton

	if click == null or click.button_index != MOUSE_BUTTON_LEFT or not click.pressed:
		return

	box.button_pressed = not box.button_pressed
	row.accept_event()


# ─── The marker samples ──────────────────────────────────────────────────────

func _draw_self_sample(sample: Control) -> void:
	WorldMapView.draw_self_mark(sample, sample.size * 0.5, SAMPLE_SELF_PX)


func _draw_flag_sample(sample: Control) -> void:
	var foot := Vector2(sample.size.x * SAMPLE_FLAG_FOOT, sample.size.y)

	WorldMapView.draw_flag(sample, foot, SAMPLE_FLAG_PX)


func _draw_path_sample(sample: Control) -> void:
	var middle := sample.size.y * 0.5
	var points := PackedVector2Array([
		Vector2(0, middle + SAMPLE_PATH_BEND),
		Vector2(sample.size.x * 0.5, middle - SAMPLE_PATH_BEND),
		Vector2(sample.size.x, middle + SAMPLE_PATH_BEND)])

	WorldMapView.draw_path(sample, points)
