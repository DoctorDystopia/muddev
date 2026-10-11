class_name PopupTabButton
extends Button
## One tab button above a pop-up grid: a bank tab, or the "+" that makes one.
##
## ## It draws what the server sent
##
## A tab with an `asset` shows that mesh. A tab with no asset shows its
## `label`. The server decides which: a named tab sends its name and no asset,
## and the main tab sends "All". So this control never asks what a tab is.
##
## ## Left click does the first thing, right click asks
##
## The rule of [PopupSlot]. The server puts View first, so a left click views
## the tab. Rename asks for text through [TextPrompt].
##
## ## It takes a drop
##
## A vault slot dropped here asks the view to send the server's move template,
## with the `drop_key` of this tab as the target. The "+" is a tab with no
## actions. Its key is the new-tab word. It takes a drop, and a click on it
## does nothing.

## Emitted with a whole command a telnet player could have typed.
signal command_requested(command: String)

## Emitted when a vault slot is dropped on this tab.
signal dropped(source_key: String, drop_key: String)

## The size of a tab button, in pixels. Room for one small mesh.
const BUTTON_SIZE := Vector2(44, 40)

var _tab: Dictionary = {}
var _menu: PopupMenu


func _init() -> void:
	custom_minimum_size = BUTTON_SIZE
	toggle_mode = true
	expand_icon = true
	icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
	focus_mode = Control.FOCUS_NONE

	_menu = PopupMenu.new()
	_menu.id_pressed.connect(_on_menu_id)
	add_child(_menu)


## Show one tab. `art` is the mesh texture, or null for a tab with no asset.
func bind(tab_data: Dictionary, art: Texture2D) -> void:
	_tab = tab_data
	set_pressed_no_signal(bool(tab_data.get("active", false)))
	tooltip_text = str(tab_data.get("title", ""))

	if art != null:
		icon = art
		text = ""
		return

	icon = null
	text = str(tab_data.get("label", ""))


## The tab this button shows. For tests.
func tab() -> Dictionary:
	return _tab


## Do what a left click does. Public so a test can click with no mouse.
func activate() -> void:
	var action := PopupState.default_action(_tab)

	if not action.is_empty():
		TextPrompt.perform(self, action, command_requested.emit)


## The labels of the right-click list, in order. For tests.
func menu_labels() -> PackedStringArray:
	var labels := PackedStringArray()

	for action: Dictionary in _tab.get("actions", []):
		labels.append(str(action.get("label", "")))

	return labels


## Do what the right-click entry at `index` does. For tests.
func choose(index: int) -> void:
	_on_menu_id(index)


func _gui_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return

	var click := event as InputEventMouseButton

	if not click.pressed:
		return

	if click.button_index == MOUSE_BUTTON_RIGHT:
		_open_menu()
		accept_event()


## The left click. The button shows the snapshot again at once. The next
## snapshot of the server lights the tab that the player now views.
func _pressed() -> void:
	set_pressed_no_signal(bool(_tab.get("active", false)))
	activate()


func _open_menu() -> void:
	var actions: Array = _tab.get("actions", [])

	if actions.is_empty():
		return

	_menu.clear()

	for index: int in range(actions.size()):
		_menu.add_item(str((actions[index] as Dictionary).get("label", "")), index)

	_menu.position = Vector2i(get_global_mouse_position())
	_menu.reset_size()
	_menu.popup()


func _on_menu_id(index: int) -> void:
	var actions: Array = _tab.get("actions", [])

	if index < 0 or index >= actions.size():
		return

	TextPrompt.perform(self, actions[index], command_requested.emit)


func _can_drop_data(_at: Vector2, data: Variant) -> bool:
	if typeof(data) != TYPE_DICTIONARY:
		return false

	var source := str(data.get(PopupSlot.DRAG_DATA_KEY, ""))

	return not source.is_empty() and not str(_tab.get("drop_key", "")).is_empty()


func _drop_data(_at: Vector2, data: Variant) -> void:
	dropped.emit(str(data.get(PopupSlot.DRAG_DATA_KEY, "")), str(_tab.get("drop_key", "")))
