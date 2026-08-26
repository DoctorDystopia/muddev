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
## server named. This control turns a gesture into a request and emits it; the
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

const COLOR_EMPTY := Color(1, 1, 1, 0.25)
const COLOR_FILLED := Color(1, 1, 1, 0.9)
const COLOR_LABEL := Color(0.75, 0.78, 0.82)

## Widest an item name may draw before it is clipped, in characters. Frames are
## small and a long name would push the grid around.
const NAME_CLIP := 14

var kind := KIND_CARRIED
var key: Variant = 0

var _state: InventoryState
var _row: Dictionary = {}
var _title: Label
var _detail: Label
var _menu: PopupMenu


## Built in _init, not _ready.
##
## The view binds a cell before adding it to the tree -- it makes the whole
## grid, then swaps it in -- and _ready does not run until a node ENTERS the
## tree. Building here means a cell is drawable the moment it exists, which is
## what lets the view construct and bind in one pass.
func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_PASS
	custom_minimum_size = Vector2(96, 52)

	var column := VBoxContainer.new()
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(column)

	_title = Label.new()
	_title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_title.add_theme_font_size_override("font_size", 11)
	column.add_child(_title)

	_detail = Label.new()
	_detail.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_detail.add_theme_font_size_override("font_size", 10)
	_detail.add_theme_color_override("font_color", COLOR_LABEL)
	column.add_child(_detail)

	_menu = PopupMenu.new()
	_menu.id_pressed.connect(_on_menu_id)
	add_child(_menu)


## Point this cell at a model and a frame, and draw it.
func bind(state: InventoryState, cell_kind: String, cell_key: Variant,
		label: String = "") -> void:
	_state = state
	kind = cell_kind
	key = cell_key
	_redraw(label)


func _redraw(label: String) -> void:
	_row = _current_row()

	var occupied := not _row.is_empty()
	modulate = COLOR_FILLED if occupied else COLOR_EMPTY

	if occupied:
		_title.text = _clip(str(_row.get("name", "")))
		_detail.text = _quantity_text()
		tooltip_text = _tooltip()
		return

	# An empty EQUIPMENT frame still names itself: the paper doll has to read
	# as a doll rather than as a row of blank squares. An empty CARRIED square
	# is just a square.
	_title.text = label
	_detail.text = ""
	tooltip_text = label


func _current_row() -> Dictionary:
	if _state == null:
		return {}

	if kind == KIND_CARRIED:
		return _state.carried_at(int(key))

	return _state.equipped_at(str(key))


func _quantity_text() -> String:
	var quantity := int(_row.get("quantity", 1))

	if quantity > 1:
		return "x%d" % quantity

	return ""


func _tooltip() -> String:
	var parts: PackedStringArray = [str(_row.get("name", ""))]
	var quantity := int(_row.get("quantity", 1))

	if quantity > 1:
		parts.append("x%d" % quantity)

	return " ".join(parts)


func _clip(text: String) -> String:
	if text.length() <= NAME_CLIP:
		return text

	return text.substr(0, NAME_CLIP - 1) + "…"


# ─── Drag and drop, all of it Godot's ────────────────────────────────────────

func _get_drag_data(_at: Vector2) -> Variant:
	if _row.is_empty():
		return null

	set_drag_preview(_preview())

	return {"kind": kind, "key": key, "row": _row}


## What the cursor carries. A label rather than the cell itself, because
## reparenting a live cell into the drag layer would empty the grid square the
## drag started from.
func _preview() -> Control:
	var preview := Label.new()
	preview.text = _clip(str(_row.get("name", "")))
	preview.add_theme_font_size_override("font_size", 11)

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

	if not click.pressed or click.button_index != MOUSE_BUTTON_RIGHT:
		return

	_open_menu()
	accept_event()


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
	var command := str(action.get("command", ""))

	# An empty command is the server declining, exactly as an empty tile action
	# is. Never substituted into, never guessed at.
	if command.is_empty():
		return

	action_chosen.emit(command)
