@tool
class_name FigureOutfitBar
extends VBoxContainer
## The outfit bar of the figure workbench (DESIGN-0014 section 8.6, Phase
## W3): one cell for each slot. Each stand wears the outfit of the bar, so
## the author sees a full outfit on each body type and looks for clipping.
##
## A cell lists the items of its slot from the item catalog
## ([FigureCatalog]). It has two more choices: nothing, and the slot shape
## with no item.
##
## This bar changes no outfit itself. A cell sends a signal, and the plugin
## gives the choice to [method FigureWorkbench.wear]. The workbench empties
## each slot that the new item clears, and the bar then shows the result.
##
## The body type switch of section 8.6 is the list above this bar, in
## [FigureDock].
##
## ## The NPC defs (Phase W6)
##
## The list below the cells has each NPC def with an outfit. A picked NPC
## def dresses each stand in its outfit. The server owns that outfit, so
## the bar only shows it (decision 8). The list follows the outfit of the
## stands: it names an NPC def only while the stands wear its outfit.

signal slot_set(slot: String, asset_key: String)
signal cleared

## The author picked an NPC def of the list.
signal npc_chosen(key: String)

## The first two choices of each cell.
const NOTHING := "(nothing)"
const SLOT_SHAPE := "(the slot shape)"

const TITLE := "Outfit bar: one item for each slot"

## Two slots on each row: a label and a cell for each one. The bar is then
## half as high, and the tabs below it keep their room.
const COLUMNS := 4

## The first choice of the NPC list, with an NPC def and with none.
const NO_NPC := "(dress the figure as an NPC def)"
const NO_NPC_OUTFIT := "(no NPC def has an outfit)"

var _fold := CheckButton.new()
var _rows := VBoxContainer.new()
var _grid := GridContainer.new()
var _clear: Button
var _npcs := OptionButton.new()

## NPC def key -> its outfit.
var _npc_outfits := {}

## Slot -> the list of that slot.
var _cells := {}

## The cells that the bar shows, as one text.
var _shown := ""


func _init() -> void:
	_fold.text = TITLE
	_fold.button_pressed = true
	_fold.toggled.connect(func(shown: bool) -> void: _rows.visible = shown)
	add_child(_fold)
	_grid.columns = COLUMNS
	_rows.add_child(_grid)
	_clear = FigureFields.button("Take each item off", cleared.emit)
	_rows.add_child(_clear)
	_npcs.fit_to_longest_item = false
	_npcs.clip_text = true
	_npcs.item_selected.connect(func(index: int) -> void:
		if index > 0:
			npc_chosen.emit(_npcs.get_item_metadata(index)))
	_rows.add_child(_npcs)
	add_child(_rows)


## Give the bar one cell for each slot of a catalog. A bar with the same
## cells keeps them.
func set_catalog(catalog: FigureCatalog) -> void:
	var wanted := _signature(catalog)

	if wanted == _shown:
		return

	_shown = wanted
	_cells.clear()

	for child: Node in _grid.get_children():
		_grid.remove_child(child)
		child.queue_free()

	for slot: String in catalog.slot_keys():
		_cells[slot] = _new_cell(catalog, slot)
		_grid.add_child(FigureFields.cell_label(catalog.label_of(slot)))
		_grid.add_child(_cells[slot])

	_fill_npcs(catalog)


## Show an outfit: slot -> asset key. The bar sends no signal.
func set_outfit(outfit: Dictionary) -> void:
	for slot: String in _cells:
		var cell: OptionButton = _cells[slot]
		var wanted: String = outfit.get(slot, "")

		# A cell with no catalog yet has no row to select.
		if cell.item_count > 0:
			cell.select(0)

		for index in cell.item_count:
			if cell.get_item_metadata(index) == wanted:
				cell.select(index)

	if _npcs.item_count > 0:
		_npcs.select(0)

	for index in range(1, _npcs.item_count):
		if _npc_outfits[_npcs.get_item_metadata(index)] == outfit:
			_npcs.select(index)


## The key of the NPC def whose outfit the bar shows, or "".
func shown_npc() -> String:
	if _npcs.selected <= 0:
		return ""

	return _npcs.get_item_metadata(_npcs.selected)


## Fill the NPC list: one row for each NPC def of the catalog with an
## outfit. With none, the list says so, and the author cannot open it.
func _fill_npcs(catalog: FigureCatalog) -> void:
	var keys := catalog.npc_keys()

	_npc_outfits.clear()
	_npcs.clear()
	_npcs.add_item(NO_NPC_OUTFIT if keys.is_empty() else NO_NPC)
	_npcs.set_item_metadata(0, "")
	_npcs.disabled = keys.is_empty()

	for key: String in keys:
		_npc_outfits[key] = catalog.valid_outfit(catalog.npc_outfit(key))
		_npcs.add_item("%s (%s)" % [catalog.npc_name(key), key])
		_npcs.set_item_metadata(_npcs.item_count - 1, key)

	_npcs.select(0)


## The asset key that the cell of one slot shows, or "".
func shown_in(slot: String) -> String:
	if not _cells.has(slot) or _cells[slot].selected < 0:
		return ""

	return _cells[slot].get_item_metadata(_cells[slot].selected)


## The list of one slot: nothing, the slot shape, then each item by tier.
func _new_cell(catalog: FigureCatalog, slot: String) -> OptionButton:
	var cell := OptionButton.new()

	cell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	cell.fit_to_longest_item = false
	cell.clip_text = true
	cell.add_item(NOTHING)
	cell.set_item_metadata(0, "")
	cell.add_item(SLOT_SHAPE)
	cell.set_item_metadata(1, slot)

	for row: Dictionary in catalog.items_of(slot):
		cell.add_item(row["name"])
		cell.set_item_metadata(cell.item_count - 1, row["key"])

	cell.item_selected.connect(func(index: int) -> void:
		slot_set.emit(slot, cell.get_item_metadata(index)))

	return cell


## One text for the slots and the items of a catalog.
static func _signature(catalog: FigureCatalog) -> String:
	var lines := PackedStringArray()

	for slot: String in catalog.slot_keys():
		var keys := PackedStringArray()

		for row: Dictionary in catalog.items_of(slot):
			keys.append("%s=%s" % [row["key"], row["name"]])

		lines.append("%s|%s|%s" % [slot, catalog.label_of(slot), ",".join(keys)])

	for key: String in catalog.npc_keys():
		lines.append("npc|%s|%s|%s" % [key, catalog.npc_name(key), catalog.npc_outfit(key)])

	return "\n".join(lines)
