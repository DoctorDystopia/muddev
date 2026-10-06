class_name ChatModeButton
extends Button
## The chat mode in front of the input: `Nick [Public]:`, as OSRS shows the
## name of the player before the chat line.
##
## A click opens a menu of every mode, Command first. The menu writes
## [ChatModes] and nothing else. The button hides until the server sends the
## modes, so the login screen shows no mode.
##
## It never takes the keyboard, for the reason [ChatBar] gives.

## The tooltip of the button.
const TOOLTIP := "Where a typed line goes. Start a line with / to send it as a command."

var _modes: ChatModes
var _menu: PopupMenu

## Menu id -> mode key.
var _menu_keys: Array[String] = []


func _init() -> void:
	flat = true
	focus_mode = Control.FOCUS_NONE
	tooltip_text = TOOLTIP
	visible = false


## Bind to the model, and follow it.
func bind(modes: ChatModes) -> void:
	_modes = modes

	_menu = PopupMenu.new()
	_menu.id_pressed.connect(_on_menu_id)
	add_child(_menu)

	pressed.connect(_open_menu)
	_modes.changed.connect(_refresh)
	_refresh()


## Fill the menu, and give the number of items. Split from the popup, so a
## test can read the items with no window.
func fill_menu() -> int:
	_menu.clear()
	_menu_keys.clear()
	_add_item(ChatModes.COMMAND_KEY)

	for row: Dictionary in _modes.modes:
		_add_item(str(row["key"]))

	return _menu.item_count


## The menu. For a test, and for nothing else.
func menu() -> PopupMenu:
	return _menu


func _add_item(key: String) -> void:
	var id := _menu_keys.size()

	_menu_keys.append(key)
	_menu.add_radio_check_item(_modes.label_of(key), id)
	_menu.set_item_checked(_menu.item_count - 1, key == _modes.active_key())


func _open_menu() -> void:
	fill_menu()
	_menu.position = Vector2i(get_global_mouse_position())
	_menu.reset_size()
	_menu.popup()


func _on_menu_id(id: int) -> void:
	if id >= 0 and id < _menu_keys.size():
		_modes.select(_menu_keys[id])


func _refresh() -> void:
	visible = _modes.has_data
	text = _modes.prompt()
