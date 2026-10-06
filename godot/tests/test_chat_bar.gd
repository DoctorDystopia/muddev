extends Node
## Unit tests for ChatBar and ChatModeButton -- the buttons of the chat
## interface.
##
##     godot --headless --path godot res://tests/test_chat_bar.tscn
##
## Needs nothing running. Builds each view in code with real models. The
## menus are filled and chosen through the same methods that a click calls,
## so no window has to open.

const Const := preload("res://autoload/blackout_constants.gd")

const SAY := {"key": "say", "label": "Say", "type": "say", "prefix": "say "}
const REPLY := {"key": "reply", "label": "Reply", "type": "page",
	"prefix": "page/reply "}
const PUBLIC := {"key": "channel:public", "label": "Public", "type": "channel",
	"prefix": "@channel Public = "}

var _failures := 0
var _bar: ChatBar
var _tabs: ChatTabs
var _modes: ChatModes


func _ready() -> void:
	_one_button_for_each_tab()
	_a_click_opens_the_tab()
	_a_move_elsewhere_lights_the_button()
	_an_unread_tab_shows_the_dot()
	_the_menu_offers_the_modes_of_the_tab()
	_all_offers_every_mode()
	_a_mode_item_sets_the_chat_mode()
	_show_in_all_flips_the_filter()
	_nothing_takes_the_keyboard()
	_the_mode_button_follows_the_model()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: chat_bar")
	get_tree().quit(0)


func _fresh() -> void:
	if _bar != null:
		_bar.queue_free()

	_tabs = ChatTabs.new()
	_modes = ChatModes.new()
	_modes.ingest(Const.CH_CHAR_CHAT,
		{"speaker": "Nick", "modes": [SAY, REPLY, PUBLIC]})
	_bar = ChatBar.new()
	add_child(_bar)
	_bar.bind(_tabs, _modes)


func _index_named(tab_name: String) -> int:
	for index: int in _tabs.count():
		if _tabs.name_of(index) == tab_name:
			return index

	return -1


func _menu_texts() -> Array[String]:
	var texts: Array[String] = []
	var menu := _bar.menu()

	for item: int in menu.item_count:
		texts.append(menu.get_item_text(item))

	return texts


func _mode_item(label: String) -> String:
	return ChatBar.MODE_ITEM_FORMAT % label


func _one_button_for_each_tab() -> void:
	_fresh()

	for index: int in _tabs.count():
		_expect(_bar.button_at(index).text == _tabs.name_of(index),
			"button %d reads %s" % [index, _tabs.name_of(index)])


func _a_click_opens_the_tab() -> void:
	_fresh()
	_bar.button_at(2).pressed.emit()

	_expect(_tabs.active == 2, "a click on a button opens its tab")


func _a_move_elsewhere_lights_the_button() -> void:
	# Ctrl+Tab moves the model, not the button.
	_fresh()
	_tabs.select(4)

	_expect(_bar.button_at(4).button_pressed, "the open tab's button is lit")
	_expect(not _bar.button_at(0).button_pressed, "and the old one is not")


func _an_unread_tab_shows_the_dot() -> void:
	_fresh()
	var combat := _index_named("Combat")
	_tabs.note(combat)

	_expect(_bar.button_at(combat).text.ends_with(ChatBar.UNREAD_MARK),
		"an unread tab shows the dot")

	_tabs.select(combat)
	_expect(not _bar.button_at(combat).text.ends_with(ChatBar.UNREAD_MARK),
		"and opening it clears the dot")


func _the_menu_offers_the_modes_of_the_tab() -> void:
	_fresh()
	_bar.fill_menu(_index_named("Private"))
	var texts := _menu_texts()

	_expect(texts.has(_mode_item(REPLY["label"])), "Private offers Reply")
	_expect(not texts.has(_mode_item(SAY["label"])), "and not Say")
	_expect(texts.has(ChatBar.SHOW_IN_ALL_LABEL), "and the filter")

	_bar.fill_menu(_index_named("Game"))
	_expect(_menu_texts().has(_mode_item(ChatModes.COMMAND_LABEL)),
		"Game offers Command")

	_bar.fill_menu(_index_named("Combat"))
	_expect(_menu_texts() == [ChatBar.SHOW_IN_ALL_LABEL],
		"Combat, with no mode, offers the filter only")


func _all_offers_every_mode() -> void:
	_fresh()
	_bar.fill_menu(ChatTabs.FALLBACK_TAB)
	var texts := _menu_texts()

	for row: Dictionary in [SAY, REPLY, PUBLIC]:
		_expect(texts.has(_mode_item(row["label"])),
			"All offers %s" % row["label"])

	_expect(not texts.has(ChatBar.SHOW_IN_ALL_LABEL),
		"and no filter, because All cannot hide from itself")


func _a_mode_item_sets_the_chat_mode() -> void:
	_fresh()
	_bar.fill_menu(_index_named("Channel"))
	var texts := _menu_texts()
	var id := _bar.menu().get_item_id(texts.find(_mode_item(PUBLIC["label"])))

	_bar.choose(id)

	_expect(_modes.active_key() == PUBLIC["key"], "the item sets the chat mode")

	_bar.fill_menu(_index_named("Channel"))
	_expect(_bar.menu().is_item_checked(texts.find(_mode_item(PUBLIC["label"]))),
		"and the menu then marks it")


func _show_in_all_flips_the_filter() -> void:
	_fresh()
	var combat := _index_named("Combat")

	_bar.fill_menu(combat)
	_expect(_bar.menu().is_item_checked(0), "Show in All starts checked")

	_bar.choose(ChatBar.SHOW_IN_ALL_ID)
	_expect(_tabs.is_hidden_from_all(combat), "the item hides the tab from All")

	_bar.fill_menu(combat)
	_expect(not _bar.menu().is_item_checked(0), "and the menu then shows it off")

	_bar.choose(ChatBar.SHOW_IN_ALL_ID)
	_expect(not _tabs.is_hidden_from_all(combat), "a second click shows it again")


## Focus IS the mode in this client. A button that took the keyboard would
## turn the next letter into a walk.
func _nothing_takes_the_keyboard() -> void:
	_fresh()

	_expect(_bar.focus_mode == Control.FOCUS_NONE, "the bar refuses focus")

	for index: int in _tabs.count():
		_expect(_bar.button_at(index).focus_mode == Control.FOCUS_NONE,
			"button %d refuses focus" % index)

	var button := ChatModeButton.new()
	_expect(button.focus_mode == Control.FOCUS_NONE,
		"and so does the mode button")
	button.free()


func _the_mode_button_follows_the_model() -> void:
	var modes := ChatModes.new()
	var button := ChatModeButton.new()
	add_child(button)
	button.bind(modes)

	_expect(not button.visible, "before the payload, the mode button hides")

	modes.ingest(Const.CH_CHAR_CHAT, {"speaker": "Nick", "modes": [SAY, PUBLIC]})
	_expect(button.visible and button.text == modes.prompt(),
		"the payload shows it, with the prompt")
	_expect(button.fill_menu() == 3, "its menu lists Command and each mode")
	_expect(button.menu().get_item_text(0) == ChatModes.COMMAND_LABEL,
		"with Command first")

	button.menu().id_pressed.emit(button.menu().get_item_id(2))
	_expect(modes.active_key() == PUBLIC["key"], "an item sets the mode")
	_expect(button.text.contains(PUBLIC["label"]), "and the button follows")

	button.queue_free()


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
