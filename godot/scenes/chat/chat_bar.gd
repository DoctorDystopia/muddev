class_name ChatBar
extends HBoxContainer
## The row of tab buttons along the bottom of the log box, as in the OSRS chat
## interface.
##
## - A left-click shows only the lines of that tab.
## - A right-click opens the options of the tab: "Set chat mode" for each mode
##   whose lines the tab shows, and "Show in All".
##
## Nick chose these gestures on 09/29/2026. The bar reads and writes two
## models, [ChatTabs] and [ChatModes], and holds no state of its own. The
## console saves both models to the settings file.
##
## ## No button takes the keyboard
##
## **Focus IS the mode in this client.** The console reads movement keys only
## when the input does not have the keyboard. A button that took focus on a
## click would turn the next letter the player types into a walk.

## Drawn on a tab that has lines the player has not looked at.
##
## A DOT and not a count. A count invites reading the number instead of opening
## the tab, and the buffer is capped anyway, so the number would go on being
## wrong in a way nobody could see.
const UNREAD_MARK := " •"

## The text of one mode item in the right-click menu.
const MODE_ITEM_FORMAT := "Set chat mode: %s"

## The text of the filter item in the right-click menu.
const SHOW_IN_ALL_LABEL := "Show in All"

## The tooltip of each button.
const BUTTON_TOOLTIP := "Click: show only these lines. Right-click: chat mode and filter."

## The menu id of the filter item. The mode items use ids from 0, one for each
## mode, so this id sits far above them.
const SHOW_IN_ALL_ID := 1000

var _tabs: ChatTabs
var _modes: ChatModes
var _buttons: Array[Button] = []
var _menu: PopupMenu

## The tab whose menu is open.
var _menu_tab := -1

## Menu id -> mode key, for the mode items of the open menu.
var _menu_keys: Array[String] = []


func _init() -> void:
	focus_mode = Control.FOCUS_NONE


## Build one button for each tab, and bind to the two models.
func bind(tabs: ChatTabs, modes: ChatModes) -> void:
	_tabs = tabs
	_modes = modes

	var group := ButtonGroup.new()

	for index: int in _tabs.count():
		var button := Button.new()
		button.toggle_mode = true
		button.button_group = group
		button.focus_mode = Control.FOCUS_NONE
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.tooltip_text = BUTTON_TOOLTIP
		button.pressed.connect(_tabs.select.bind(index))
		button.gui_input.connect(_on_button_input.bind(index))
		_buttons.append(button)
		add_child(button)

	_menu = PopupMenu.new()
	_menu.id_pressed.connect(_on_menu_id)
	add_child(_menu)

	_tabs.unread_changed.connect(_retitle)
	_tabs.active_changed.connect(_on_active_changed)
	_retitle()
	_on_active_changed(_tabs.active)


## One button. For a test, and for nothing else.
func button_at(index: int) -> Button:
	return _buttons[index]


## Fill the right-click menu of one tab, and give the number of items.
##
## Split from the popup, so a test can read the items with no window.
func fill_menu(index: int) -> int:
	_menu.clear()
	_menu_keys.clear()
	_menu_tab = index

	if _tabs.offers_command_mode(index):
		_add_mode_item(ChatModes.COMMAND_KEY)

	for row: Dictionary in _modes.modes_for_types(_tabs.types_of(index)):
		_add_mode_item(str(row["key"]))

	if index != ChatTabs.FALLBACK_TAB:
		if _menu.item_count > 0:
			_menu.add_separator()

		_menu.add_check_item(SHOW_IN_ALL_LABEL, SHOW_IN_ALL_ID)
		_menu.set_item_checked(_menu.item_count - 1,
			not _tabs.is_hidden_from_all(index))

	return _menu.item_count


## The menu. For a test, and for nothing else.
func menu() -> PopupMenu:
	return _menu


## Act on one menu id, as a click on the item does.
func choose(id: int) -> void:
	_on_menu_id(id)


func _add_mode_item(key: String) -> void:
	var id := _menu_keys.size()

	_menu_keys.append(key)
	_menu.add_radio_check_item(MODE_ITEM_FORMAT % _modes.label_of(key), id)
	_menu.set_item_checked(_menu.item_count - 1, key == _modes.active_key())


func _on_button_input(event: InputEvent, index: int) -> void:
	var click := event as InputEventMouseButton

	if click == null or not click.pressed:
		return

	if click.button_index != MOUSE_BUTTON_RIGHT:
		return

	_buttons[index].accept_event()

	if fill_menu(index) == 0:
		return

	_menu.position = Vector2i(get_global_mouse_position())
	_menu.reset_size()
	_menu.popup()


func _on_menu_id(id: int) -> void:
	if id == SHOW_IN_ALL_ID:
		var hidden := _tabs.is_hidden_from_all(_menu_tab)
		_tabs.set_hidden_from_all(_menu_tab, not hidden)
		return

	if id >= 0 and id < _menu_keys.size():
		_modes.select(_menu_keys[id])


## Light the button of the open tab. `button_pressed` and not
## `set_pressed_no_signal`, because only the first unlights the others of the
## group. The bar listens to `pressed`, which this does not emit.
func _on_active_changed(index: int) -> void:
	_buttons[index].button_pressed = true


## Redraw the titles, marks and all.
##
## Titles rather than icons: an icon means a texture to author, ship and theme
## for two states, where the mark is one character the button font already
## has.
func _retitle() -> void:
	for index: int in _buttons.size():
		var title := _tabs.name_of(index)

		if _tabs.is_unread(index):
			title += UNREAD_MARK

		_buttons[index].text = title
