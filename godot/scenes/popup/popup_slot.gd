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
## ## A drag, and two kinds of drop
##
## A slot drags only when the view gives it a key with [method bind_drag]. A
## drop then takes one of two paths:
##
## - **The drop table of the row** (11/09/2026). The row names the whole
##   command for each drag key that it takes, from any grid. The rig sends
##   one on each socket and each augment.
##   [method PopupState.row_drop] reads it. A drag key with no entry is no
##   drop, so a socket refuses an augment that does not fit it.
## - **The template of the grid** (10/08/2026). The bank vault takes a drop
##   from its own grid. The view fills the server's template with the two
##   keys, and [PopupState] owns the fill.
##
## Neither path holds a verb. During a drag, a border marks each slot whose
## drop table takes the drag.
##
## The left click fires on the RELEASE, as in [InventorySlotCell]. A click that
## fired on the press would withdraw the item that the player meant to drag.
##
## ## No line makes a slot wider than [constant SLOT_SIZE] (11/09/2026)
##
## [PopupView] counts its columns from [constant SLOT_SIZE]. A Label gives its
## whole text as its minimum width, and a GridContainer makes each column as
## wide as its widest cell. Thus, one long detail line made a whole column wide,
## and the grid went past the right edge of the box. The rig showed this: a
## locked augment said "Guard: Melee needs Augmentation level 20." under its
## name. The detail line clips and ends in an ellipsis, as the name does. The
## full line is in the tooltip and in [HoverBar].

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

## The border of a slot that takes the drag in progress. The accent of the XP
## HUD: a "go" colour, not the red accent of an error.
const DROP_HINT_COLOR := Color("5dcaa5")

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

## True when the grid of this slot sends drag templates: the bank vault. Then
## a drop of another slot of the grid fills a template.
var _takes_template := false

## True while the slot shows the border of a drop that it takes.
var _hinted := false

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
	# The clip drops the minimum width of the label to zero. See the class notes.
	_detail.clip_text = true
	_detail.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	# Centered under the name. See [ItemNameLabel].
	_detail.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
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
	add_theme_stylebox_override("panel", _bordered_panel(colour))
	_detail.add_theme_color_override("font_color", colour)


## A copy of the theme panel with a border in `colour`. A theme panel that is
## not flat gives a clear box with the border only.
func _bordered_panel(colour: Color) -> StyleBoxFlat:
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


## Let this slot drag, under `key`. "" turns the drag off. `takes_template`
## is true for a grid that sends drag templates, the bank vault.
func bind_drag(key: String, takes_template: bool = false) -> void:
	_drag_key = key
	_takes_template = takes_template


## The key a drag names this slot by. For tests.
func drag_key() -> String:
	return _drag_key


## Show the border when this slot takes the drop of `data`, and hide it
## otherwise. The notification calls it with the data of the drag in
## progress. Public so that a test can start a drag with no mouse.
func show_drop_hint_for(data: Variant) -> void:
	var takes := not PopupState.row_drop(_row, _drag_source(data)).is_empty()

	if takes == _hinted:
		return

	_hinted = takes

	if takes:
		add_theme_stylebox_override("panel", _bordered_panel(DROP_HINT_COLOR))
	else:
		_show_rarity(str(_row.get("rarity", "")))


## True while the slot shows the drop border. For tests.
func drop_hinted() -> bool:
	return _hinted


# ─── Drag and drop, all of it Godot's ────────────────────────────────────────

## Every node in the viewport gets the start and the end of a drag. A slot
## that a snapshot builds during a drag asks for the drag when it enters the
## tree. A drop sends a command, and the next snapshot builds new slots.
func _notification(what: int) -> void:
	match what:
		NOTIFICATION_DRAG_BEGIN, NOTIFICATION_ENTER_TREE:
			show_drop_hint_for(_viewport_drag_data())
		NOTIFICATION_DRAG_END:
			show_drop_hint_for(null)


## The data of the drag in progress, or null for no drag.
func _viewport_drag_data() -> Variant:
	var viewport := get_viewport()

	if viewport == null:
		return null

	return viewport.gui_get_drag_data()


## The drag key that a drag carries, or "" for a drag of something else: an
## item of the bag, for example.
static func _drag_source(data: Variant) -> String:
	if typeof(data) != TYPE_DICTIONARY:
		return ""

	return str((data as Dictionary).get(DRAG_DATA_KEY, ""))


func _get_drag_data(_at: Vector2) -> Variant:
	if _drag_key.is_empty():
		return null

	_skip_left_release = true
	var preview := Label.new()
	preview.text = str(_row.get("name", ""))
	preview.theme_type_variation = &"CellTitle"
	set_drag_preview(preview)

	return {DRAG_DATA_KEY: _drag_key}


## The drop table of the row first, then the template of the grid. A drop of
## a slot on itself is never a template drop.
func _can_drop_data(_at: Vector2, data: Variant) -> bool:
	var source := _drag_source(data)

	if source.is_empty():
		return false

	if not PopupState.row_drop(_row, source).is_empty():
		return true

	return _takes_template and not _drag_key.is_empty() and source != _drag_key


func _drop_data(_at: Vector2, data: Variant) -> void:
	var source := _drag_source(data)
	var command := PopupState.row_drop(_row, source)

	if not command.is_empty():
		command_requested.emit(command)
		return

	dropped_on.emit(source, _drag_key)


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
