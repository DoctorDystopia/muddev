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
## ## A drag inside one grid, from the server's template
##
## A slot drags only when the view gives it a key with [method bind_drag]. Only
## the bank vault does this today. A drop goes on another slot of the grid, or
## on a tab button. The view then fills the server's template with the two
## keys. [PopupState] owns the fill, so this control holds no verb. No drag
## goes from one grid to another.
##
## The left click fires on the RELEASE, as in [InventorySlotCell]. A click that
## fired on the press would withdraw the item that the player meant to drag.

## Emitted with a whole command a telnet player could have typed.
signal command_requested(command: String)

## Emitted when a slot of the same grid is dropped on this one.
signal dropped_on(source_key: String, target_key: String)

## The key of the drag data. A tab button reads it too.
const DRAG_DATA_KEY := "popup_drag_key"

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

## The border width of a buff card, in pixels. A card row has a `rarity` field.
const RARITY_BORDER_WIDTH := 2

var _row: Dictionary = {}
var _art: TextureRect
var _title: ItemNameLabel
var _detail: Label
var _count: StackCountLabel
var _menu: PopupMenu

## What the player set, or null. Read for one fact only: how big they left the
## amount box. Given by the view, because a slot is made and freed per snapshot.
var _settings: ClientSettings

## The key a drag names this slot by, or "" for a slot that does not drag.
var _drag_key := ""

## True after a drag starts, so the release that ends the gesture sends
## nothing.
var _skip_left_release := false


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


## Give this slot the player's settings, for the amount box it may open.
##
## Separate from [method bind] and never required, for the reason
## [method InventorySlotCell.bind_settings] gives.
func bind_settings(settings: ClientSettings) -> void:
	_settings = settings


## Show one row, or an empty frame for `{}`.
func bind(row_data: Dictionary) -> void:
	_row = row_data

	var occupied := not _row.is_empty()
	modulate = COLOR_FILLED if occupied else COLOR_EMPTY

	if occupied and not bool(_row.get("enabled", true)):
		modulate = COLOR_DISABLED

	if not occupied:
		_title.text = ""
		_detail.text = ""
		_count.show_quantity(0)
		tooltip_text = ""
		_show_rarity("")
		return

	_title.text = str(_row.get("name", ""))
	_detail.text = str(_row.get("detail", ""))
	_detail.visible = not _detail.text.is_empty()
	_count.show_quantity(int(_row.get("quantity", 1)))
	tooltip_text = _tooltip()
	_show_rarity(str(_row.get("rarity", "")))


## The colour of the card rarity: the border of the slot and the detail line.
## A row with no `rarity`, or a key the palette does not know, draws as before.
func _show_rarity(rarity: String) -> void:
	if not RarityPalette.has_color(rarity):
		remove_theme_stylebox_override("panel")
		_detail.remove_theme_color_override("font_color")
		return

	var colour := RarityPalette.color_for(rarity)
	add_theme_stylebox_override("panel", _rarity_panel(colour))
	_detail.add_theme_color_override("font_color", colour)


## A copy of the theme panel with a border in `colour`. A theme panel that is
## not flat gives a clear box with the border only.
func _rarity_panel(colour: Color) -> StyleBoxFlat:
	var base := get_theme_stylebox("panel", "PanelContainer")
	var panel: StyleBoxFlat

	if base is StyleBoxFlat:
		panel = (base as StyleBoxFlat).duplicate()
	else:
		panel = StyleBoxFlat.new()
		panel.bg_color = Color.TRANSPARENT

	panel.set_border_width_all(RARITY_BORDER_WIDTH)
	panel.border_color = colour

	return panel


## The colour of the rarity border, for tests. Clear when the slot shows none.
func rarity_border_color() -> Color:
	var panel := get_theme_stylebox("panel")

	if not has_theme_stylebox_override("panel") or not (panel is StyleBoxFlat):
		return Color.TRANSPARENT

	return (panel as StyleBoxFlat).border_color


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

	if click.button_index == MOUSE_BUTTON_LEFT:
		if click.pressed:
			_skip_left_release = false
		elif _skip_left_release:
			_skip_left_release = false
		else:
			activate()

		accept_event()
		return

	if click.button_index == MOUSE_BUTTON_RIGHT and click.pressed:
		_open_menu()
		accept_event()


## Let this slot drag, under `key`. "" turns the drag off.
func bind_drag(key: String) -> void:
	_drag_key = key


## The key a drag names this slot by. For tests.
func drag_key() -> String:
	return _drag_key


# ─── Drag and drop, all of it Godot's ────────────────────────────────────────

func _get_drag_data(_at: Vector2) -> Variant:
	if _drag_key.is_empty():
		return null

	_skip_left_release = true
	var preview := Label.new()
	preview.text = str(_row.get("name", ""))
	preview.theme_type_variation = &"CellTitle"
	set_drag_preview(preview)

	return {DRAG_DATA_KEY: _drag_key}


func _can_drop_data(_at: Vector2, data: Variant) -> bool:
	if _drag_key.is_empty() or typeof(data) != TYPE_DICTIONARY:
		return false

	var source := str(data.get(DRAG_DATA_KEY, ""))

	return not source.is_empty() and source != _drag_key


func _drop_data(_at: Vector2, data: Variant) -> void:
	dropped_on.emit(str(data.get(DRAG_DATA_KEY, "")), _drag_key)


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


## Send one action. A prompted action asks first, for an amount or for a line
## of text. [method TextPrompt.perform] reads the prompt BEFORE the empty
## command, because a prompted action has an empty command on purpose.
func _perform(action: Dictionary) -> void:
	TextPrompt.perform(self, action, command_requested.emit, _settings)


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
