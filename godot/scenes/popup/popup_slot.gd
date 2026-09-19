class_name PopupSlot
extends PanelContainer
## One slot in a pop-up grid: a vault item, a carried item, or an empty frame.
##
## ## Left click does the first thing; right click asks
##
## The OSRS bank rule, and the same rule as the world pane's [ChooseOption]: a
## left click sends the row's FIRST action, and a right click lists them all.
## The server orders the actions, and it puts the active quantity mode first —
## so "Withdraw 5" is what a left click means after the player picks 5, and
## this control never learns what 5 is.
##
## ## It decides nothing about the game
##
## Every command is one the server named on the row. A prompted action (the X
## entries) asks for its amount through [AmountPrompt] and substitutes through
## [ServerAction]. There is no verb here, the contract [InventorySlotCell]
## states for the bag.
##
## No drag and drop. A pop-up moves items with commands the server names, and a
## drag between two grids would be a command this client composed.

## Emitted with a whole command a telnet player could have typed.
signal command_requested(command: String)

## Emitted when the mouse enters and leaves this slot. The VIEW owns the
## [HoverBar] and reads [method hover_text] from the slot.
signal hovered
signal unhovered

const COLOR_EMPTY := Color(1, 1, 1, 0.25)
const COLOR_FILLED := Color(1, 1, 1, 0.9)

## A slot the server marks `enabled: false`: a recipe you cannot make yet, a
## ware you cannot afford. Dimmer than filled, brighter than empty, and still
## clickable, because the server answers a click with the reason.
const COLOR_DISABLED := Color(1, 1, 1, 0.5)

## Between the name and the click action in the one-line [method hover_text].
## The tooltip has room for two lines, so it puts them on two.
const HOVER_SEPARATOR := "  -  "

## The slot's width, in pixels. The content sets the height. The view reads
## the width to decide how many columns fit.
const SLOT_SIZE := Vector2(88, 0)
const ART_HEIGHT := 34

var _row: Dictionary = {}
var _art: TextureRect
var _title: ItemNameLabel
var _detail: Label
var _count: StackCountLabel
var _menu: PopupMenu


## Built in _init, not _ready, for the reason [InventorySlotCell] gives: the
## view builds and binds a whole grid before any of it enters the tree.
func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	custom_minimum_size = SLOT_SIZE
	mouse_entered.connect(hovered.emit)
	mouse_exited.connect(unhovered.emit)

	var column := VBoxContainer.new()
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(column)

	_art = TextureRect.new()
	_art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_art.custom_minimum_size = Vector2(0, ART_HEIGHT)
	_art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	column.add_child(_art)

	_title = ItemNameLabel.new()
	column.add_child(_title)

	_detail = Label.new()
	_detail.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_detail.theme_type_variation = &"CellDetail"
	column.add_child(_detail)

	# AFTER the column, so the count draws over the art. See [StackCountLabel].
	_count = StackCountLabel.new()
	add_child(_count)

	_menu = PopupMenu.new()
	_menu.id_pressed.connect(_on_menu_id)
	add_child(_menu)


## Show one row, or an empty frame for `{}`.
func bind(row: Dictionary) -> void:
	_row = row

	var occupied := not _row.is_empty()
	modulate = COLOR_FILLED if occupied else COLOR_EMPTY

	if occupied and not bool(_row.get("enabled", true)):
		modulate = COLOR_DISABLED

	if not occupied:
		_title.text = ""
		_detail.text = ""
		_count.show_quantity(0)
		tooltip_text = ""
		return

	_title.text = str(_row.get("name", ""))
	_detail.text = str(_row.get("detail", ""))
	_detail.visible = not _detail.text.is_empty()
	_count.show_quantity(int(_row.get("quantity", 1)))
	tooltip_text = _tooltip()


## The row this slot shows, or `{}`. Read by the view to decide what to draw.
func row() -> Dictionary:
	return _row


func show_art(texture: AtlasTexture) -> void:
	_art.texture = texture


## The labels of the right-click list, in order. For tests.
func menu_labels() -> PackedStringArray:
	var labels := PackedStringArray()

	for action: Dictionary in _row.get("actions", []):
		labels.append(str(action.get("label", "")))

	return labels


## Do what a left click does. Public so a test can click with no mouse.
func activate() -> void:
	var action := PopupState.default_action(_row)

	if action.is_empty():
		return

	_perform(action)


func _gui_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return

	var click := event as InputEventMouseButton

	if not click.pressed:
		return

	if click.button_index == MOUSE_BUTTON_LEFT:
		activate()
		accept_event()
		return

	if click.button_index == MOUSE_BUTTON_RIGHT:
		_open_menu()
		accept_event()


## Offer exactly what the server offered, in the order it offered it. A slot
## with no actions opens nothing rather than an empty menu.
func _open_menu() -> void:
	var actions: Array = _row.get("actions", [])

	if actions.is_empty():
		return

	_menu.clear()

	for index: int in range(actions.size()):
		var action: Dictionary = actions[index]
		_menu.add_item(str(action.get("label", "")), index)

	_menu.position = Vector2i(get_global_mouse_position())
	_menu.reset_size()
	_menu.popup()


func _on_menu_id(index: int) -> void:
	var actions: Array = _row.get("actions", [])

	if index < 0 or index >= actions.size():
		return

	_perform(actions[index])


## Send one action, asking first when it is a prompted one.
##
## The prompt is checked BEFORE the empty-command guard, because a prompted
## action is shipped with an empty command on purpose.
func _perform(action: Dictionary) -> void:
	var prompt := ServerAction.prompt(action)

	if not prompt.is_empty():
		AmountPrompt.ask(self, action, prompt, command_requested.emit)
		return

	var command := ServerAction.command(action)

	if command.is_empty():
		return

	command_requested.emit(command)


## The count this slot draws in its corner. For tests.
func count_text() -> String:
	return _count.text


## The line under the name: the server's `detail`, a price or a skill gate.
## For tests.
func detail_text() -> String:
	return _detail.text


## What the [HoverBar] shows while the mouse is on this slot: the tooltip's
## parts on one line. An empty slot gives "".
func hover_text() -> String:
	return HOVER_SEPARATOR.join(_description())


func _tooltip() -> String:
	return "\n".join(_description())


## The name, the count, and what a left click will do. OSRS prints the last
## part at the top of the screen. This client prints it in the tooltip and in
## the hover bar.
func _description() -> PackedStringArray:
	var parts := PackedStringArray()

	if _row.is_empty():
		return parts

	parts.append(str(_row.get("name", "")))
	var count := StackCountLabel.count_text(int(_row.get("quantity", 1)))

	if not count.is_empty():
		parts[0] += " %s" % count

	var detail := str(_row.get("detail", ""))

	if not detail.is_empty():
		parts.append(detail)

	# The server's `info`: what a recipe needs, what is missing. One part per
	# line, so the tooltip stacks them and the hover bar strings them along.
	for line: String in str(_row.get("info", "")).split("\n", false):
		parts.append(line)

	var action := PopupState.default_action(_row)

	if not action.is_empty():
		parts.append("Click: %s" % str(action.get("label", "")))

	return parts
