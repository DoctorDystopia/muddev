class_name InventorySlotCell
extends PanelContainer
## One frame in the inventory: a carried grid square, or an equipment slot.
##
## Both kinds are the same control because the server made them the same shape.
## `serialize_inventory` gives a carried row and a worn row identical fields and
## keeps "which frame does this sit in" in one `slot` field precisely so one
## drag implementation serves both grids — see [InventoryState] on why that
## field is polymorphic.
##
## ## Drag and drop is Godot's, not hand-rolled
##
## [method _get_drag_data], [method _can_drop_data] and [method _drop_data] are
## engine API. The browser pane had to track pointer-down, pointer-move,
## hit-test the release and hold a `pendingMove` guard against a staleness bug,
## because the DOM gave it nothing better. Godot owns the gesture, the preview
## and the hit-test, so none of that exists here — which is the single largest
## thing the engine buys on this screen.
##
## ## What this control decides, and what it refuses to
##
## It decides **nothing about the game**. Whether a drop is legal is
## [method InventoryState.can_equip], which compares two server-supplied values.
## What a click can do is the row's own `actions`, which are whole commands the
## server named. A left click selects the first action. This control turns a
## gesture into a request and emits it; the
## view sends it. There is no verb here, and there must never be one — the
## browser pane had a verb table once, it was wrong within a week, and a
## superuser walked off with a Foundry Furnace.

## A carried grid square. `key` is an int slot index.
const KIND_CARRIED := "carried"

## An equipment frame. `key` is a WieldLocation value string.
const KIND_EQUIPPED := "equipped"

## Emitted when a drag completes on this cell. The VIEW turns it into a command.
signal dropped(from_kind: String, from_key: Variant, to_kind: String, to_key: Variant)

## Emitted when the player picks one of the server's named actions.
signal action_chosen(command: String)

## Emitted when the mouse enters and leaves this cell. The VIEW owns the
## [HoverBar] and reads [method hover_text] from the cell.
signal hovered
signal unhovered

const COLOR_EMPTY := Color(1, 1, 1, 0.25)
const COLOR_FILLED := Color(1, 1, 1, 0.9)

## Separates the hover bar's parts without hiding where one fact ends.
const HOVER_SEPARATOR := "  -  "

## How tall the item's picture is, in pixels.
const ART_HEIGHT := 36

## The cell's size, in pixels: a touch wider than tall, so a two-line name
## fits beside no count line. The count sits in the corner, over the art.
const CELL_SIZE := Vector2(94, 0)

var kind := KIND_CARRIED
var key: Variant = 0

var _state: InventoryState
var _row: Dictionary = {}
var _title: ItemNameLabel
var _count: StackCountLabel
var _menu: PopupMenu

## True after this cell starts a drag. Its left-button release does not act.
var _skip_left_release := false

## The item's picture: one rectangle of [ItemStage]'s shared render target.
##
## A TextureRect and not a viewport of its own -- see [ItemStage] on why forty
## render targets for forty thumbnails is the build to avoid.
var _art: TextureRect

## What the player set, or null. Read for one fact only: how big they left the
## amount box. Given by the view, because a cell is made and freed per snapshot
## and has no route to the console.
var _settings: ClientSettings


## Built in _init, not _ready.
##
## The view binds a cell before adding it to the tree -- it makes the whole
## grid, then swaps it in -- and _ready does not run until a node ENTERS the
## tree. Building here means a cell is drawable the moment it exists, which is
## what lets the view construct and bind in one pass.
func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_PASS
	custom_minimum_size = CELL_SIZE
	mouse_entered.connect(hovered.emit)
	mouse_exited.connect(unhovered.emit)

	var column := VBoxContainer.new()
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(column)

	# ABOVE the labels: the picture is what a player scans for and the name is
	# what they confirm with, so the art gets the top of the cell and the text
	# stays a caption.
	_art = TextureRect.new()
	_art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_art.custom_minimum_size = Vector2(0, ART_HEIGHT)
	_art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	column.add_child(_art)

	_title = ItemNameLabel.new()
	column.add_child(_title)

	# AFTER the column, so the count draws over the art and not under it.
	_count = StackCountLabel.new()
	add_child(_count)

	_menu = PopupMenu.new()
	_menu.id_pressed.connect(_on_menu_id)
	add_child(_menu)


## The server row this cell is currently showing, or an empty dictionary.
##
## Read by the view to decide whether there is anything to draw on the stage.
## Exposed rather than recomputed there: the cell already resolved which row it
## holds, and asking the state a second time would be a second place that knows
## how a carried index and a worn slot differ.
func row() -> Dictionary:
	return _row


## Give this cell its picture. Called by the view, which owns the stage.
##
## Null is a normal argument: a cell with no art shows its labels alone, which
## is what every cell did before the stage existed and what an empty frame still
## does.
func show_art(texture: AtlasTexture) -> void:
	_art.texture = texture


## The picture this cell is showing, or null. For tests and for the view.
func art_texture() -> AtlasTexture:
	return _art.texture as AtlasTexture


## Point this cell at a model and a frame, and draw it.
func bind(state: InventoryState, cell_kind: String, cell_key: Variant,
		label: String = "") -> void:
	_state = state
	kind = cell_kind
	key = cell_key
	_redraw(label)


## Give this cell the player's settings, for the amount box it may open.
##
## Separate from [method bind] and never required: the view calls it on every
## cell it makes, and a test that never opens a box does not have to supply a
## profile to write to.
func bind_settings(settings: ClientSettings) -> void:
	_settings = settings


func _redraw(label: String) -> void:
	_row = _current_row()

	var occupied := not _row.is_empty()
	modulate = COLOR_FILLED if occupied else COLOR_EMPTY

	if occupied:
		_title.text = str(_row.get("name", ""))
		_count.show_quantity(int(_row.get("quantity", 1)))
		tooltip_text = _tooltip()
		return

	# An empty EQUIPMENT frame still names itself: the paper doll has to read
	# as a doll rather than as a row of blank squares. An empty CARRIED square
	# is just a square.
	_title.text = label
	_count.show_quantity(0)
	tooltip_text = label


func _current_row() -> Dictionary:
	if _state == null:
		return {}

	if kind == KIND_CARRIED:
		return _state.carried_at(int(key))

	return _state.equipped_at(str(key))


## The name, the count, the server's `detail`, and the default action.
func _tooltip() -> String:
	return "\n".join(_description())


## The one-line form for the [HoverBar].
func hover_text() -> String:
	return HOVER_SEPARATOR.join(_description())


## The item's name, its count, and the left-click action it gives to the
## player. The server names the action. This control joins that action to the
## item's already-sent name, as [ChooseOption] does for a world entity.
func _description() -> PackedStringArray:
	var parts: PackedStringArray = [str(_row.get("name", ""))]
	var count := StackCountLabel.count_text(int(_row.get("quantity", 1)))
	var detail := str(_row.get("detail", ""))

	if not count.is_empty():
		parts[0] += " %s" % count

	if not detail.is_empty():
		parts.append(detail)

	var action_text := _default_action_text()

	if not action_text.is_empty():
		parts.append("Click: %s" % action_text)

	return parts


## The default action's server label, followed by this row's server name.
func _default_action_text() -> String:
	var action := _default_action()

	if action.is_empty():
		return ""

	var label := str(action.get("label", "")).strip_edges()

	if label.is_empty():
		var command := str(action.get("command", "")).strip_edges()
		label = command.split(" ")[0]

	if label.is_empty():
		return ""

	var item_name := str(_row.get("name", "")).strip_edges()

	return label + " " + item_name


## The count this cell draws in its corner. For tests.
func count_text() -> String:
	return _count.text


# ─── Drag and drop, all of it Godot's ────────────────────────────────────────

func _get_drag_data(_at: Vector2) -> Variant:
	if _row.is_empty():
		return null

	_skip_left_release = true
	set_drag_preview(_preview())

	return {"kind": kind, "key": key, "row": _row}


## What the cursor carries. A label rather than the cell itself, because
## reparenting a live cell into the drag layer would empty the grid square the
## drag started from.
##
## The full name on one line. The preview is not in a grid, so it has no width
## to fit.
##
## Godot puts the preview in the drag layer of the viewport, not under the
## console root. The project setting `gui/theme/custom` gives it the theme.
func _preview() -> Control:
	var preview := Label.new()
	preview.text = str(_row.get("name", ""))
	preview.theme_type_variation = &"CellTitle"

	return preview


func _can_drop_data(_at: Vector2, data: Variant) -> bool:
	if typeof(data) != TYPE_DICTIONARY or _state == null:
		return false

	var from_kind := str(data.get("kind", ""))
	var row: Dictionary = data.get("row", {})

	# Onto a carried square: anything goes. A worn item dropped here is an
	# unequip, and two carried items are a swap; the server validates both.
	if kind == KIND_CARRIED:
		return true

	# Onto an equipment frame: only from the bag, and only if the SERVER says
	# this item belongs in this slot. That comparison is two server-supplied
	# values, not a rule invented here.
	if from_kind != KIND_CARRIED:
		return false

	return _state.can_equip(row, str(key))


func _drop_data(_at: Vector2, data: Variant) -> void:
	dropped.emit(str(data.get("kind", "")), data.get("key"), kind, key)


# ─── The server's own actions ────────────────────────────────────────────────

func _gui_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return

	var click := event as InputEventMouseButton

	if click.button_index == MOUSE_BUTTON_LEFT:
		if click.pressed:
			_skip_left_release = false
			return

		if _skip_left_release:
			_skip_left_release = false
			return

		activate()
		accept_event()
		return

	if click.pressed and click.button_index == MOUSE_BUTTON_RIGHT:
		_open_menu()
		accept_event()


## Do the server's first action. Public so a test can click without a window.
func activate() -> void:
	var action := _default_action()

	if action.is_empty():
		return

	_perform(action)


## The first action is the default action. The server orders the list.
func _default_action() -> Dictionary:
	if _state == null or _row.is_empty():
		return {}

	var actions := _state.actions_for(_row)

	if actions.is_empty():
		return {}

	return actions[0]


## Offer exactly what the server offered, in the order it offered it.
##
## A cell with no actions opens nothing rather than an empty menu — the server
## saying an item affords nothing is the same shape as an entity with an empty
## `interact`, and both mean "do not offer this".
func _open_menu() -> void:
	if _state == null or _row.is_empty():
		return

	var actions := _state.actions_for(_row)

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
	var actions := _state.actions_for(_row)

	if index < 0 or index >= actions.size():
		return

	var action: Dictionary = actions[index]
	_perform(action)


## Send one action, asking for an amount when the server requires one.
func _perform(action: Dictionary) -> void:
	var prompt := _state.action_prompt(action)

	# Checked BEFORE the empty-command guard below, because a prompted action
	# is deliberately shipped with an empty command — that is what makes it do
	# nothing on a client that never learned to ask. This one asks.
	if not prompt.is_empty():
		_ask_amount(action, prompt)
		return

	var command := _state.action_command(action)

	# An empty command is the server declining, exactly as an empty tile action
	# is. Never substituted into, never guessed at.
	if command.is_empty():
		return

	action_chosen.emit(command)


## Ask for the one value the server left blank, then send. The box is
## [AmountPrompt], shared with the pop-up.
func _ask_amount(action: Dictionary, prompt: Dictionary) -> void:
	AmountPrompt.ask(self, action, prompt, action_chosen.emit, _settings)
