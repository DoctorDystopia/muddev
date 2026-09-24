class_name InventoryView
extends VBoxContainer
## The carried grid, drawn from [InventoryState].
##
## Presentation and gesture only. Every command it sends was named by the
## server: the row's own `actions` for a click, and
## [method InventoryState.swap_command] for a drag — which is the one command
## composed anywhere in this client, because a drag knows two endpoints and
## nothing else does.
##
## ## The paper doll left on 09/21/2026
##
## It was the bottom half of this pane, a flat row of twelve squares under the
## grid. It is [EquipmentView] now, in a tab of its own, and that file carries
## what the move cost: a drag from a carried square to a worn frame, which one
## left click does instead.
##
## ## Built in code, not in a .tscn
##
## The grid is `slots_total` cells, and that number comes from the server.
## Laying it out in a scene file would mean a fixed 32 squares that breaks when
## the handler grows.
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
const COLUMNS := 4

## Floor on the carried grid, in pixels: roughly two rows of cells.
const MIN_GRID_HEIGHT := 160

var _state: InventoryState
var _heading: Label
var _grid: GridContainer

## The full text of the cell under the mouse. See [HoverBar].
var _bar: HoverBar

## `[kind, key]` of the cell under the mouse, or `[]`.
##
## A key and not the cell, because a rebuild frees every cell. The mouse did
## not move, so the cell at the same key is the one under it now.
var _hover_key: Array = []

## Where every item's picture is drawn. One render target for the whole bag;
## see [ItemStage].
var _stage: ItemStage

## Where meshes come from. The CONSOLE owns it, so the room and the bag share
## one model cache and a `.glb` is fetched once for both.
var _meshes: MeshResolver

## What the player set. Held only to hand to each cell, which reads one fact
## from it: how big they left the amount box. See [AmountPrompt].
var _settings: ClientSettings


func _ready() -> void:
	_heading = Label.new()
	_heading.theme_type_variation = &"SectionHeading"
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

	_bar = HoverBar.new()
	add_child(_bar)

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


## Give the pane the player's settings, for the boxes its cells open.
##
## No redraw and no `changed` hookup: nothing the pane DRAWS comes from here.
## The one fact read is the amount box's size, and it is read when a box opens.
func bind_settings(settings: ClientSettings) -> void:
	_settings = settings


func _rebuild() -> void:
	if _state == null:
		return

	_heading.text = _heading_text()

	# Kept BEFORE the fill. Godot can send mouse_exited from an old cell as
	# _fill removes it, and that clears _hover_key.
	var hovered_key := _hover_key

	# Indices are allocated HERE and the layout is the stage's: one index per
	# cell, in the order the cells were made.
	var carried := _carried_cells()

	_stage.reserve(carried.size())
	_dress(carried)
	_fill(_grid, carried)
	_restore_hover(hovered_key, carried)


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


## Draw each occupied cell's item onto the stage and hand it its rectangle.
##
## An EMPTY cell is given no texture at all rather than a blank one: the stage
## has nothing at that index, so its rectangle is transparent either way, and
## not asking says so.
func _dress(cells: Array) -> void:
	for index: int in cells.size():
		var cell: InventorySlotCell = cells[index]
		var row := cell.row()

		if row.is_empty():
			continue

		_stage.place(index, str(row.get("asset", "")),
			str(row.get("family", "")), _meshes)
		cell.show_art(_stage.texture_for(index))


func _cell() -> InventorySlotCell:
	var cell := SlotCell.new()
	cell.bind_settings(_settings)
	cell.dropped.connect(_on_dropped)
	cell.action_chosen.connect(_on_action_chosen)
	cell.hovered.connect(_on_cell_hovered.bind(cell))
	cell.unhovered.connect(_on_cell_unhovered.bind(cell))

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


## The one legal gesture in this pane, and where its command comes from.
##
## A swap is the ONE command composed anywhere in this client, because it takes
## two endpoints and only the drag knows them -- see
## [method InventoryState.swap_command].
##
## There were THREE gestures until 09/21/2026. A carried square dragged to a
## worn frame was an `equip`, and the reverse was an `unequip`, and both looked
## the command up in the row's own `actions` rather than spelling a verb here.
## The doll moved to a tab of its own, so neither endpoint can see the other
## any more: the gestures are unreachable rather than removed, and the left
## click that replaced them is the server's first action either way. See
## [EquipmentView].
func _command_for(from_kind: String, from_key: Variant,
		to_kind: String, to_key: Variant) -> String:
	if from_kind == SlotCell.KIND_CARRIED and to_kind == SlotCell.KIND_CARRIED:
		return _state.swap_command(int(from_key), int(to_key))

	return ""


func _on_action_chosen(command: String) -> void:
	command_requested.emit(command)


# ─── The hover bar ───────────────────────────────────────────────────────────

func _on_cell_hovered(cell: InventorySlotCell) -> void:
	_hover_key = [cell.kind, cell.key]
	_bar.show_text(cell.hover_text())


## Clears only when the cell that leaves is the one the bar names. Godot sends
## the exit of the old cell before the entry of the new one, but a stale exit
## from a freed cell must not clear a newer entry.
func _on_cell_unhovered(cell: InventorySlotCell) -> void:
	if _hover_key != [cell.kind, cell.key]:
		return

	_hover_key = []
	_bar.clear()


## Point the bar at the new cell under the mouse after a rebuild.
##
## Without this, a drop or a swap under the mouse leaves the bar on the OLD
## row. Godot sends no mouse_entered to the new cell until the mouse moves.
func _restore_hover(hovered_key: Array, cells: Array) -> void:
	_hover_key = []
	_bar.clear()

	if hovered_key.is_empty():
		return

	for cell: InventorySlotCell in cells:
		if [cell.kind, cell.key] == hovered_key:
			_on_cell_hovered(cell)
			return
