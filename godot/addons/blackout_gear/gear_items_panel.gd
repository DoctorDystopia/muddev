@tool
class_name GearItemsPanel
extends VBoxContainer
## The item list of the Gear dock (DESIGN-0014 section 22): the item
## catalog with its filters. The first zone of the dock.
##
## The list has one row for each slot shape, then one row for each item of
## the item catalog ([FigureCatalog]). A row says what the figure shows
## ([FigureOutfit]). That is the served model, the worn look, the slot
## shape, or the family shape. The slot filter keeps one slot. The second filter
## keeps the rows with no worn look (use case 5). The text filter keeps the
## rows with the typed text, with no regard to the case.
##
## A picked row dresses each stand in that item, so the author sees what a
## player sees (use case 6). The plugin does that. This panel only sends
## the row.

signal row_chosen(key: String, slot: String)

const ROW_LIST_HEIGHT := 200.0

## The first choice of the slot filter.
const EACH_SLOT := "(each slot)"

## What a row says about its look, by the source of [FigureOutfit].
const SOURCE_TEXT := {
	FigureOutfit.SOURCE_MODEL: "served model",
	FigureOutfit.SOURCE_LOOK: "worn look",
	FigureOutfit.SOURCE_SLOT_SHAPE: "slot shape",
	FigureOutfit.SOURCE_FAMILY: "family shape",
	FigureOutfit.SOURCE_NOTHING: "nothing",
}

const SLOT_SHAPE_ROW := "[slot shape] %s"

const HELP := "Pick a row to dress each figure in it. A row with no worn look " \
	+ "shows the slot shape of its slot. Give it a look below, then change its parts."

var _slot_filter := OptionButton.new()
var _missing_only := CheckBox.new()
var _text_filter := LineEdit.new()
var _rows := ItemList.new()

var _catalog: FigureCatalog
var _rig: FigureRig
var _looks := {}
var _models: FigureModels
var _selected := ""

## The rows of the list, as one text.
var _shown_rows := ""


func _init() -> void:
	_slot_filter.item_selected.connect(func(_index: int) -> void: _fill_rows())
	_missing_only.text = "Only the rows with no worn look"
	_missing_only.toggled.connect(func(_on: bool) -> void: _fill_rows())
	_text_filter.placeholder_text = "Keep the rows with this text"
	_text_filter.clear_button_enabled = true
	_text_filter.text_changed.connect(func(_text: String) -> void: _fill_rows())
	_rows.custom_minimum_size.y = ROW_LIST_HEIGHT
	_rows.item_selected.connect(func(row: int) -> void:
		select_row(_rows.get_item_metadata(row))
		row_chosen.emit(_selected, selected_slot()))
	add_child(FigureFields.label(HELP))
	add_child(FigureFields.label("Slot of the rows"))
	add_child(_slot_filter)
	add_child(_missing_only)
	add_child(_text_filter)
	add_child(FigureFields.label("Rows (name, slot, what the figure shows)"))
	add_child(_rows)


## Show a catalog.
##
## - `rig` gives the slot table, for what the figure shows.
## - `looks` is key -> [FigureLook], for each worn look of the store.
## - `models` gives the served models. With none, no row shows one.
func set_content(catalog: FigureCatalog, rig: FigureRig, looks: Dictionary,
		models: FigureModels = null) -> void:
	_catalog = catalog
	_rig = rig
	_looks = looks
	_models = models

	if not _is_row(_selected):
		_selected = ""

	_fill_filter()
	_fill_rows()


## The key of the selected row: an item key, or a slot for a slot shape row.
## "" for no row.
func selected_key() -> String:
	return _selected


## The slot of the selected row, or "".
func selected_slot() -> String:
	return _slot_of(_selected)


## The text of the filter above the list.
func filter_text() -> String:
	return _text_filter.text.strip_edges().to_lower()


## Select a row by its key. The panel sends no signal. A row that the filter
## hides takes the filter off.
func select_row(key: String) -> void:
	if not _is_row(key):
		key = ""

	if key == _selected:
		return

	_selected = key

	if not key.is_empty() and not key in _row_keys():
		_slot_filter.select(0)
		_missing_only.set_pressed_no_signal(false)
		_text_filter.text = ""

	_fill_rows()


## What the figure shows for one row: a SOURCE_* of [FigureOutfit].
func source_of(key: String) -> String:
	if _catalog == null or _rig == null or not _is_row(key):
		return FigureOutfit.SOURCE_NOTHING

	return FigureOutfit.source_of(_rig, _slot_of(key), key, _looks, _models)


## One line for the selected row: the item, its slot, and what the figure
## shows for it (requirement A8). "" for no row.
func item_line() -> String:
	if _selected.is_empty():
		return ""

	var slot := _slot_of(_selected)

	if _selected == slot:
		return "The slot shape of %s: %s." % [slot, _slot_shape_state(slot)]

	return "%s, slot %s: the figure shows the %s." % [_catalog.item(_selected)["name"],
		slot, SOURCE_TEXT[source_of(_selected)]]


## True for a key that is a slot shape row.
func is_slot_row(key: String) -> bool:
	return _catalog != null and _catalog.has_slot(key)


# ─── The rows ───────────────────────────────────────────────────────────────

## True for a key that can be a row: a slot or an item of the catalog.
func _is_row(key: String) -> bool:
	return _catalog != null and (_catalog.has_slot(key) or _catalog.has_item(key))


func _slot_of(key: String) -> String:
	if _catalog == null:
		return ""

	return key if _catalog.has_slot(key) else _catalog.slot_of(key)


func _fill_filter() -> void:
	var names: Array = [EACH_SLOT]

	if _catalog != null:
		names.append_array(Array(_catalog.slot_keys()))

	FigureFields.fill(_slot_filter, names)

	if _slot_filter.selected < 0:
		_slot_filter.select(0)


## The keys of the rows that the filter keeps: each slot shape, then each
## item, slot by slot.
func _row_keys() -> PackedStringArray:
	var keys := PackedStringArray()
	var items := PackedStringArray()

	if _catalog == null:
		return keys

	for slot: String in _catalog.slot_keys():
		if _slot_filter.selected > 0 and FigureFields.text_of(_slot_filter) != slot:
			continue

		keys.append(slot)

		for row: Dictionary in _catalog.items_of(slot):
			items.append(row["key"])

	keys.append_array(items)

	var kept := PackedStringArray()
	var text := filter_text()

	for key: String in keys:
		if _missing_only.button_pressed and _looks.has(key):
			continue

		if text.is_empty() or _row_text(key).to_lower().contains(text):
			kept.append(key)

	return kept


## Fill the list. A list with the same rows stays, so a drag of a part does
## not move the scroll bar.
func _fill_rows() -> void:
	var keys := _row_keys()
	var lines := PackedStringArray()

	for key: String in keys:
		lines.append(_row_text(key))

	if "\n".join(lines) != _shown_rows:
		_shown_rows = "\n".join(lines)
		_rows.clear()

		for index in keys.size():
			_rows.add_item(lines[index])
			_rows.set_item_metadata(index, keys[index])

	_rows.deselect_all()

	for index in keys.size():
		if keys[index] == _selected:
			_rows.select(index)


func _row_text(key: String) -> String:
	if _catalog.has_slot(key):
		return "%s   %s" % [SLOT_SHAPE_ROW % _catalog.label_of(key), _slot_shape_state(key)]

	return "%s   %s   %s%s" % [_catalog.item(key)["name"], _catalog.slot_of(key),
		SOURCE_TEXT[source_of(key)], _tier_text(key)]


## What a row says after its source when its look is a tier, or "".
func _tier_text(key: String) -> String:
	var look: FigureLook = _looks.get(key)

	if look == null or look.base().is_empty():
		return ""

	return ", a tier of %s" % look.base()


## What a slot shape row says: a slot with no slot shape shows the family
## shape of each item.
func _slot_shape_state(slot: String) -> String:
	return "has a look" if _looks.has(slot) else "none, so the family shape draws"
