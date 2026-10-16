@tool
extends HFlowContainer
## The paint values strip above the tabs: the floor, the area, and the wall
## style that the tools of the Paint tab and of the Build tab write.
##
## One list for each value, in one place. Before, the Paint tab and the
## Build tab each had a Floor list and an Area list, and a pick with Shift
## wrote one while a pick with Alt wrote the other. Now a pick from any tab
## lands here.
##
## "(keep)" is a row of the Floor list and of the Area list. A Build tool
## then keeps the floor or the area of each tile. The Floor brush and the
## Area brush of the Paint tab paint nothing with it, and the hint line says
## so.
##
## The lists come from [TileTables]. A "New" button beside each list opens
## the Tables tab on its table (10/14/2026), and [method refill] takes the
## new row after the write.
##
## The choices persist in the session file (`terrain_session.gd`).

## A value changed.
signal changed

## A "New" button: open the Tables tab on `table`.
signal new_row_requested(table: String)

const _Fields := preload("res://addons/blackout_terrain/terrain_fields.gd")
const _Session := preload("res://addons/blackout_terrain/terrain_session.gd")

## The first row of the floor and area lists: keep what the tile has.
const KEEP := "(keep)"

const _SECTION := "paint"

## False in a test: a change then writes no session file.
var persist := true

var _floor := OptionButton.new()
var _area := OptionButton.new()
var _wall_style := OptionButton.new()


func _init() -> void:
	refill()
	_add("Floor", _floor, TileTables.FLOOR_TYPES, "The floor that the Floor brush, "
		+ "the Room, and the Place tool paint. (keep) leaves the floor of each tile.")
	_add("Area", _area, TileTables.AREAS, "The area that the Area brush and the Room "
		+ "paint. An interior area gives a room its own light and text. (keep) leaves "
		+ "the area of each tile.")
	_add("Wall", _wall_style, TileTables.WALL_STYLES, "The wall style of the Wall line, "
		+ "the Room, and the Wall style brush.")
	_load()

	for list: OptionButton in [_floor, _area, _wall_style]:
		list.item_selected.connect(func(_index: int) -> void: _on_changed())


# ─── Reading ────────────────────────────────────────────────────────────────

## The row of the Floor list, [constant KEEP] included.
func floor_choice() -> String:
	return _Fields.text_of(_floor)


## The floor to paint, or "" to keep the floor of each tile.
func floor_name() -> String:
	return _name(_floor)


func area_choice() -> String:
	return _Fields.text_of(_area)


## The area to paint, or "" to keep the area of each tile.
func area_name() -> String:
	return _name(_area)


func wall_style() -> String:
	return _Fields.text_of(_wall_style)


# ─── Writing ────────────────────────────────────────────────────────────────

## Take the values of a tile: Alt and a click, or Shift and a click. An
## empty text leaves its list as it is.
func sample(floor_type: String, area: String, style: String) -> void:
	_Fields.select_text(_floor, floor_type)
	_Fields.select_text(_area, area)
	_Fields.select_text(_wall_style, style)
	_on_changed()


func pick_floor(floor_type: String) -> void:
	_Fields.select_text(_floor, floor_type)
	_on_changed()


func pick_area(area: String) -> void:
	_Fields.select_text(_area, area)
	_on_changed()


## Fill the three lists from [TileTables] again, and keep each choice. A
## choice follows `rename`, `{table, old, new}`. A choice whose row went
## gives the first row.
func refill(rename := {}) -> void:
	_Fields.refill(_floor, [KEEP] + Array(TileTables.keys(TileTables.FLOOR_TYPES)),
		_Fields.follow_of(rename, TileTables.FLOOR_TYPES))
	_Fields.refill(_area, [KEEP] + Array(TileTables.keys(TileTables.AREAS)),
		_Fields.follow_of(rename, TileTables.AREAS))
	_Fields.refill(_wall_style, Array(TileTables.keys(TileTables.WALL_STYLES)),
		_Fields.follow_of(rename, TileTables.WALL_STYLES))

	if is_inside_tree():
		_on_changed()


# ─── Building ───────────────────────────────────────────────────────────────

func _add(label_text: String, list: OptionButton, table: String, tip: String) -> void:
	var pair := HBoxContainer.new()
	var label := Label.new()

	label.text = label_text
	label.tooltip_text = tip
	list.tooltip_text = tip
	pair.add_child(label)
	pair.add_child(list)
	pair.add_child(_Fields.button("New", new_row_requested.emit.bind(table),
		"Make a new row of this list on the Tables tab."))
	add_child(pair)


static func _name(list: OptionButton) -> String:
	var text := _Fields.text_of(list)

	return "" if text == KEEP else text


func _on_changed() -> void:
	if persist:
		_Session.write(_SECTION, {"floor": floor_choice(), "area": area_choice(),
			"wall_style": wall_style()})

	changed.emit()


func _load() -> void:
	if not persist:
		return

	_Fields.select_text(_floor, _Session.read(_SECTION, "floor", KEEP))
	_Fields.select_text(_area, _Session.read(_SECTION, "area", KEEP))
	_Fields.select_text(_wall_style, _Session.read(_SECTION, "wall_style", ""))
