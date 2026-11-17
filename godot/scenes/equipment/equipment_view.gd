class_name EquipmentView
extends VBoxContainer
## The paper doll, drawn from [InventoryState].
##
## It was the bottom half of [InventoryView] until 09/21/2026, a flat row of
## twelve squares under the carried grid. It is a panel of its own because the
## reference interface gives worn gear a tab of its own, and because a row of
## squares said nothing about what a body wears where. [DollLayout] owns the
## shape.
##
## Presentation and gesture only, the same line every pane on this screen
## draws. Every command it sends was named by the server, on the row's own
## `actions`.
##
## ## Nothing here can be dragged
##
## Both halves of the bag used to sit in one pane, so a drag from a carried
## square to a worn frame was an `equip` and the reverse was an `unequip`. A
## [TabContainer] draws one tab, so neither endpoint can see the other any
## more, and [method InventorySlotCell._can_drop_data] already refuses a worn
## frame as a source for a worn frame.
##
## **The gesture that replaced it is the left click**, and it costs nothing:
## the server puts `Equip` first on a carried wearable's actions and `Unequip`
## first on a worn one, so one click does what the drag did. This pane
## therefore never connects `dropped`, because nothing can emit it.
##
## ## The rig button
##
## A button under the doll opens the Augmentation Rig (11/09/2026). The
## buttons under the OSRS Worn Equipment tab work the same way. It sends
## [code]RIG_COMMAND[/code], the `rig` that a telnet player types. The server
## spells it, and the server opens the pop-up. Every character has the
## command, so the button is always there.
##
## Author: Nick Hobar
## Creation date: 09/21/2026

## Emitted with a whole command a telnet player could have typed.
signal command_requested(command: String)

const _Const := preload("res://autoload/blackout_constants.gd")
const SlotCell := preload("res://scenes/inventory/slot_cell.gd")

## The text and the tip of the rig button.
const RIG_BUTTON_TEXT := "Augmentation Rig"
const RIG_BUTTON_TIP := "Open your Augmentation Rig"

## Floor on the doll, in pixels. The same rule as the carried grid's floor: in
## a pane the player can drag down to nothing, an EXPAND_FILL scroller resolves
## to zero and the doll disappears while the heading above it still draws.
const MIN_DOLL_HEIGHT := 200

## Heading for the leftover strip. Named rather than silent, because a slot in
## it is a slot [DollLayout] has not been taught yet.
const OVERFLOW_HEADING := "Other"

var _state: InventoryState
var _heading: Label
var _doll: VBoxContainer
var _overflow_heading: Label
var _overflow: GridContainer
var _rig_button: Button

## The full text of the cell under the mouse. See [HoverBar].
var _bar: HoverBar

## `[kind, key]` of the cell under the mouse, or `[]`. A key and not the cell,
## because a rebuild frees every cell.
var _hover_key: Array = []

## The picture of each worn item. One render target for the whole doll, and
## one picture for each item, made one time. See [ItemStage].
var _stage: ItemStage

## What the player set. Held only to hand to each cell. See [AmountPrompt].
var _settings: ClientSettings


## Built in _init, not _ready.
##
## The console makes this pane, binds it, and only then hands it to
## [PanelView], which adds it to the tree. `_ready` does not run until a node
## ENTERS one, so a pane built there would take its first `bind` with every
## widget still null. [InventorySlotCell] documents the same rule.
func _init() -> void:
	_heading = Label.new()
	_heading.theme_type_variation = &"SectionHeading"
	add_child(_heading)

	var scroller := ScrollContainer.new()
	scroller.custom_minimum_size = Vector2(0, MIN_DOLL_HEIGHT)
	scroller.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	add_child(scroller)

	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroller.add_child(column)

	_doll = VBoxContainer.new()
	_doll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.add_child(_doll)

	# Hidden with its strip, so a doll that places every slot shows no empty
	# heading. See [constant DollLayout.OVERFLOW_COLUMNS].
	_overflow_heading = Label.new()
	_overflow_heading.theme_type_variation = &"SectionHeading"
	_overflow_heading.text = OVERFLOW_HEADING
	column.add_child(_overflow_heading)

	_overflow = GridContainer.new()
	_overflow.columns = DollLayout.OVERFLOW_COLUMNS
	_overflow.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.add_child(_overflow)

	# Under the scroller. The scroller holds the doll, so the button stays
	# in view.
	_build_rig_button()

	_bar = HoverBar.new()
	add_child(_bar)

	# The stage renders only when a picture changes. See [ItemStage].
	_stage = ItemStage.new()
	add_child(_stage)


## Bind to a model and a mesh source, and follow them.
##
## The CONSOLE owns the mesh source. Thus, the room, the bag, and the doll
## share one model cache. The stage takes the source. Art that arrives late
## changes the picture in its frame. The doll does not build its frames again.
func bind(state: InventoryState, resolver: MeshResolver) -> void:
	_state = state
	_state.changed.connect(_rebuild)
	_stage.bind_meshes(resolver)
	_rebuild()


## Take the figure library. A frame then draws the worn look of its item,
## the look that the figure wears (10/17/2026). The stage follows the
## library. Thus, the arrival of the figure set changes each picture.
func bind_figures(library: FigureLibrary) -> void:
	_stage.bind_figures(library)


## Give the pane the player's settings, for the boxes its cells open.
##
## No redraw and no `changed` hookup: nothing the pane DRAWS comes from here.
func bind_settings(settings: ClientSettings) -> void:
	_settings = settings


## Every cell on the doll, in reading order. For tests.
func cells() -> Array:
	var found: Array = []

	for row: Node in _doll.get_children():
		for cell: Node in row.get_children():
			if cell is InventorySlotCell:
				found.append(cell)

	for cell: Node in _overflow.get_children():
		if cell is InventorySlotCell:
			found.append(cell)

	return found


## The cell drawing one slot, or null. For tests.
func cell_for(slot: String) -> InventorySlotCell:
	for cell: InventorySlotCell in cells():
		if str(cell.key) == slot:
			return cell

	return null


func hover_bar_text() -> String:
	return _bar.text


func _rebuild() -> void:
	if _state == null:
		return

	_heading.text = _heading_text()

	# Kept BEFORE the fill. Godot can send mouse_exited from an old cell as the
	# fill removes it, and that clears _hover_key.
	var hovered_key := _hover_key
	var frames := _frames_by_slot()

	_clear(_doll)
	_clear(_overflow)

	var placed := _build_doll(frames)
	var spare := _build_overflow()
	var drawn: Array = placed + spare

	_dress(drawn)
	_restore_hover(hovered_key, drawn)


func _heading_text() -> String:
	if not _state.has_data:
		# Distinguished from wearing nothing on purpose. A player who has just
		# logged in has not been told anything yet.
		return "Worn  --"

	return "Worn  %d/%d" % [_worn_count(), _state.equip_frames.size()]


## How many frames hold something. Counted off the FRAMES rather than off
## `equipped`, so a worn row for a slot the server no longer sends cannot make
## the heading read more than its own total.
func _worn_count() -> int:
	var worn := 0

	for frame: Dictionary in _state.equip_frames:
		if not _state.equipped_at(str(frame.get("slot", ""))).is_empty():
			worn += 1

	return worn


## slot value -> label, for every frame the server sent.
func _frames_by_slot() -> Dictionary:
	var frames: Dictionary = {}

	for frame: Dictionary in _state.equip_frames:
		frames[str(frame.get("slot", ""))] = str(frame.get("label", ""))

	return frames


## Lay out [constant DollLayout.ROWS], and give back the cells it made.
##
## A slot the SERVER did not send is a gap rather than an empty square: the
## table is the client's picture of a set the server owns, and drawing a frame
## it never named would be this pane inventing a wield location.
func _build_doll(frames: Dictionary) -> Array:
	var made: Array = []

	for row: Array in DollLayout.ROWS:
		var line := _row_for(row, frames, made)

		if line != null:
			_doll.add_child(line)

	return made


## One row of the doll, or null when there is nothing in it to draw.
func _row_for(row: Array, frames: Dictionary, made: Array) -> HBoxContainer:
	if not _row_is_drawn(row, frames):
		return null

	var line := HBoxContainer.new()
	line.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	for slot: String in row:
		line.add_child(_square(slot, frames, made))

	return line


## Whether a row has anything worth a line of pixels.
##
## Two cases say no. A row whose slots the server never sent is a row of gaps.
## And the wide row is the two-hander's, which is drawn only while it is worn --
## see [DollLayout] on why an empty one reads as a bug rather than as a slot.
func _row_is_drawn(row: Array, frames: Dictionary) -> bool:
	var drawn := false

	for slot: String in row:
		if slot == DollLayout.GAP or not frames.has(slot):
			continue

		if slot == DollLayout.WIDE_SLOT \
				and _state.equipped_at(slot).is_empty():
			continue

		drawn = true

	return drawn


## One square of a row: a frame the server sent, or empty space.
func _square(slot: String, frames: Dictionary, made: Array) -> Control:
	if slot == DollLayout.GAP or not frames.has(slot):
		return _spacer()

	var cell := _cell()
	cell.bind(_state, SlotCell.KIND_EQUIPPED, slot, str(frames[slot]))
	made.append(cell)

	return cell


## Every frame [DollLayout] does not place, in the server's own order.
func _build_overflow() -> Array:
	var made: Array = []

	for frame: Dictionary in _state.equip_frames:
		var slot := str(frame.get("slot", ""))

		if DollLayout.places(slot):
			continue

		var cell := _cell()
		cell.bind(_state, SlotCell.KIND_EQUIPPED, slot,
			str(frame.get("label", "")))
		_overflow.add_child(cell)
		made.append(cell)

	_overflow_heading.visible = not made.is_empty()

	return made


## An empty column, the width of a cell, so the doll's columns line up.
func _spacer() -> Control:
	var spacer := Control.new()
	spacer.custom_minimum_size = Vector2(InventorySlotCell.CELL_SIZE.x, 0)
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spacer.mouse_filter = Control.MOUSE_FILTER_IGNORE

	return spacer


## Give each occupied cell the picture of its item. The stage builds a
## picture at the first request and keeps it. See [method ItemStage.picture].
##
## An EMPTY cell gets no texture at all, because it shows no item.
func _dress(cells_made: Array) -> void:
	for cell: InventorySlotCell in cells_made:
		var row := cell.row()

		if row.is_empty():
			continue

		cell.show_art(_stage.picture(str(row.get("asset", "")),
			str(row.get("family", ""))))


func _cell() -> InventorySlotCell:
	var cell := SlotCell.new()
	cell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	cell.bind_settings(_settings)
	cell.action_chosen.connect(_on_action_chosen)
	cell.hovered.connect(_on_cell_hovered.bind(cell))
	cell.unhovered.connect(_on_cell_unhovered.bind(cell))

	return cell


## Replace a container's children wholesale.
##
## Freed with free() rather than queue_free(): queue_free leaves the node in the
## tree until the end of the frame, so the replacements would be added alongside
## the old ones and the doll would briefly hold both.
func _clear(container: Node) -> void:
	for child: Node in container.get_children():
		container.remove_child(child)
		child.free()


func _on_action_chosen(command: String) -> void:
	command_requested.emit(command)


# ─── The rig button ──────────────────────────────────────────────────────────

## No focus, as for the buttons of the minimap. A focused button would take
## the keys that move the player.
func _build_rig_button() -> void:
	_rig_button = Button.new()
	_rig_button.name = "Rig"
	_rig_button.text = RIG_BUTTON_TEXT
	_rig_button.tooltip_text = RIG_BUTTON_TIP
	_rig_button.focus_mode = Control.FOCUS_NONE
	_rig_button.pressed.connect(_on_rig_pressed)
	add_child(_rig_button)


## Ask the server for the rig. The server opens the pop-up, or sends the
## rig as text to a session with no pop-up.
func _on_rig_pressed() -> void:
	command_requested.emit(_Const.RIG_COMMAND)


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


## Point the bar at the new cell under the mouse after a rebuild. Godot sends
## no mouse_entered to the new cell until the mouse moves.
func _restore_hover(hovered_key: Array, cells_made: Array) -> void:
	_hover_key = []
	_bar.clear()

	if hovered_key.is_empty():
		return

	for cell: InventorySlotCell in cells_made:
		if [cell.kind, cell.key] == hovered_key:
			_on_cell_hovered(cell)
			return
