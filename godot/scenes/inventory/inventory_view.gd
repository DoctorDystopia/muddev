class_name InventoryView
extends VBoxContainer
## The carried grid and the paper doll, drawn from [InventoryState].
##
## Presentation and gesture only. Every command it sends was named by the
## server: the row's own `actions` for a click, and
## [method InventoryState.swap_command] for a drag — which is the one command
## composed anywhere in this client, because a drag knows two endpoints and
## nothing else does.
##
## ## Built in code, not in a .tscn
##
## The grid is `slots_total` cells and the doll is one cell per entry in
## `equip_slots`, and BOTH numbers come from the server. Laying them out in a
## scene file would mean either a fixed 32 squares that breaks when the handler
## grows, or a scene that has to be edited whenever a wield location is added —
## the exact edit `equip_slots` ships to avoid.
##
## ## It rebuilds wholesale
##
## `char_items_list` is a snapshot, so this throws every cell away and makes
## them again. That is affordable — a couple of hundred controls on a channel
## that fires when your bag changes — and it is the only approach that cannot
## desync from a snapshot. Diffing cells against a payload that is already the
## whole truth would be inventing a delta protocol on the client side, which is
## precisely what the server refused to do for good reasons.

## Emitted with a whole command a telnet player could have typed.
signal command_requested(command: String)

const SlotCell := preload("res://scenes/inventory/slot_cell.gd")

## Grid width in cells. Presentation: the server says how MANY slots there are,
## never how they are arranged.
const COLUMNS := 8

const HEADING_FONT_SIZE := 12

## Floor on the carried grid, in pixels: roughly two rows of cells.
const MIN_GRID_HEIGHT := 120

var _state: InventoryState
var _heading: Label
var _grid: GridContainer
var _doll: HBoxContainer

## Where every item's picture is drawn. One render target for the whole bag;
## see [ItemStage].
var _stage: ItemStage

## Where meshes come from. The CONSOLE owns it, so the room and the bag share
## one model cache and a `.glb` is fetched once for both.
var _meshes: MeshResolver


func _ready() -> void:
	_heading = Label.new()
	_heading.add_theme_font_size_override("font_size", HEADING_FONT_SIZE)
	add_child(_heading)

	# A minimum height, not just EXPAND_FILL. Inside a VSplitContainer the
	# whole pane can be dragged down to nothing, and an EXPAND_FILL scroller in
	# a short column resolves to zero -- the grid then vanishes while the
	# heading and the paper doll below it still draw, which reads as "the bag
	# is broken" rather than "the pane is small". A floor of two rows means
	# shrinking the pane scrolls the grid instead of deleting it.
	var scroller := ScrollContainer.new()
	scroller.custom_minimum_size = Vector2(0, MIN_GRID_HEIGHT)
	scroller.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	add_child(scroller)

	_grid = GridContainer.new()
	_grid.columns = COLUMNS
	_grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroller.add_child(_grid)

	var doll_heading := Label.new()
	doll_heading.text = "Worn"
	doll_heading.add_theme_font_size_override("font_size", HEADING_FONT_SIZE)
	add_child(doll_heading)

	_doll = HBoxContainer.new()
	add_child(_doll)

	# A child of this pane so it is hidden with it -- the stage stops rendering
	# when not visible, which is what makes text-only mode actually free.
	_stage = ItemStage.new()
	add_child(_stage)


## Bind to a model and a mesh source, and follow them.
func bind(state: InventoryState, resolver: MeshResolver) -> void:
	_state = state
	_meshes = resolver
	_state.changed.connect(_rebuild)

	# Art that arrives after the bag was drawn redraws it, the same way the
	# world pane redraws a room when a model lands. Without it an item fetched
	# on the first snapshot would show its family shape until the bag next
	# changed.
	if _meshes != null:
		_meshes.refreshed.connect(func(_key: String): _rebuild())

	_rebuild()


func _rebuild() -> void:
	if _state == null:
		return

	_heading.text = _heading_text()

	# Indices are allocated HERE and the layout is the stage's: carried slots
	# first, then worn frames, so the two halves cannot claim the same pixels.
	var carried := _carried_cells()
	var worn := _equipment_cells()

	_stage.reserve(carried.size() + worn.size())
	_dress(carried, 0)
	_dress(worn, carried.size())

	_fill(_grid, carried)
	_fill(_doll, worn)


func _heading_text() -> String:
	if not _state.has_data:
		# Distinguished from an empty bag on purpose. A player who has just
		# logged in has not been told anything yet, and drawing 32 empty
		# squares would say "you are carrying nothing", which may be false.
		return "Carried  --"

	return "Carried  %d/%d" % [_state.slots_used, _state.slots_total]


## One cell per carried slot, in slot order, including the empty ones.
##
## The server omits empty slots from `items` and tells us `slots_total`
## instead, so the frames are drawn from the COUNT and filled from the rows.
func _carried_cells() -> Array:
	var cells: Array = []

	if not _state.has_data:
		return cells

	for index: int in range(_state.slots_total):
		var cell := _cell()
		cell.bind(_state, SlotCell.KIND_CARRIED, index)
		cells.append(cell)

	return cells


## One cell per equipment frame, in the server's display order.
##
## Iterates `equip_slots` and never restates SLOT_DISPLAY_ORDER, so adding a
## wield location lights up a new frame with no edit here.
func _equipment_cells() -> Array:
	var cells: Array = []

	for frame: Dictionary in _state.equip_frames:
		var cell := _cell()
		cell.bind(_state, SlotCell.KIND_EQUIPPED,
			str(frame.get("slot", "")), str(frame.get("label", "")))
		cells.append(cell)

	return cells


## Draw each occupied cell's item onto the stage and hand it its rectangle.
##
## An EMPTY cell is given no texture at all rather than a blank one: the stage
## has nothing at that index, so its rectangle is transparent either way, and
## not asking says so.
func _dress(cells: Array, first_index: int) -> void:
	for offset: int in cells.size():
		var cell: InventorySlotCell = cells[offset]
		var row := cell.row()

		if row.is_empty():
			continue

		var index := first_index + offset

		_stage.place(index, str(row.get("asset", "")),
			str(row.get("family", "")), _meshes)
		cell.show_art(_stage.texture_for(index))


func _cell() -> InventorySlotCell:
	var cell := SlotCell.new()
	cell.dropped.connect(_on_dropped)
	cell.action_chosen.connect(_on_action_chosen)

	return cell


## Replace a container's children wholesale.
##
## Freed with free() rather than queue_free(): queue_free leaves the node in
## the tree until the end of the frame, so the replacement cells would be
## added alongside the old ones and the grid would briefly hold both. The
## browser pane hit the same thing with orphaned canvases and documented it.
func _fill(container: Node, cells: Array) -> void:
	for child: Node in container.get_children():
		container.remove_child(child)
		child.free()

	for cell: Control in cells:
		container.add_child(cell)


## Turn a completed drag into the command the server would name for it.
func _on_dropped(from_kind: String, from_key: Variant,
		to_kind: String, to_key: Variant) -> void:
	var command := _command_for(from_kind, from_key, to_kind, to_key)

	if command.is_empty():
		return

	command_requested.emit(command)


## The three legal gestures, and where each command comes from.
##
## Only the first is composed. The other two are LOOKED UP in the row's own
## `actions`, by matching the command the server already named for that verb —
## so this client cannot spell `equip` or `unequip` even if it wanted to.
func _command_for(from_kind: String, from_key: Variant,
		to_kind: String, to_key: Variant) -> String:
	if from_kind == SlotCell.KIND_CARRIED and to_kind == SlotCell.KIND_CARRIED:
		return _state.swap_command(int(from_key), int(to_key))

	if from_kind == SlotCell.KIND_CARRIED and to_kind == SlotCell.KIND_EQUIPPED:
		return _named_action(_state.carried_at(int(from_key)), "equip")

	if from_kind == SlotCell.KIND_EQUIPPED and to_kind == SlotCell.KIND_CARRIED:
		return _named_action(_state.equipped_at(str(from_key)), "unequip")

	return ""


## Find the command the server named for one verb on one row.
##
## Matches on the START of the command rather than on a label, because the
## label is display text and could be translated or reworded, while the command
## is the thing a telnet player would type. Returns "" when the server offered
## no such action, which is the server declining and is not an error.
func _named_action(row: Dictionary, verb: String) -> String:
	for action: Dictionary in _state.actions_for(row):
		var command := str(action.get("command", ""))

		if command.begins_with(verb + " ") or command == verb:
			return command

	return ""


func _on_action_chosen(command: String) -> void:
	command_requested.emit(command)
