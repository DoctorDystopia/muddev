class_name ChatTabs
extends RefCounted
## Which tab a line of game text belongs in, which tab is open, which tabs
## have unread lines, and which tabs the player hid from All.
##
## Pure rules and a little state. It holds no text. The lines live in the
## [RichTextLabel]s that [ChatView] builds, because Godot's own advice for a
## console-sized log is to `append_text` each new fragment and not to assign
## the whole text again.
##
## ## The tab table is the CLIENT's, and that is the whole ownership story
##
## The server says what a line IS -- `char.msg(text=(line, {"type": "combat"}))`
## -- and the vocabulary it may use is generated into
## `autoload/blackout_constants.gd` as `MSG_*`. It says nothing about tabs, and
## it must not: no server fact names a tab.
##
## **A type that no tab claims is not lost.** [constant FALLBACK_TAB] shows
## everything, it is where the player starts, and a message type added on the
## server tomorrow appears there with no edit here.
##
## ## The strip is the OSRS chat interface (09/29/2026)
##
## All, Game, Combat, Local, Private, Channel, along the bottom of the log.
## Nick chose this set, with Combat kept from the old strip. Local is the OSRS
## Public tab: `say` and `pose` in the room. Nick renamed it on 09/29/2026,
## because the default Evennia channel is also named Public. A right-click on
## a button can hide the lines of that tab from All. See [ChatBar].
##
## ## Untagged is normal
##
## Evennia's own EvMenu nodes and much of its error prose carry no tag. An
## untagged line reads as [constant Const.MSG_GENERAL], which Game claims. See
## [method tabs_for].

## Server-owned names, generated from blackout/systems/interface/statefeed/constants.py.
## Preloaded, not autoloaded -- the generated file declares no `extends Node`.
const Const := preload("res://autoload/blackout_constants.gd")

## The tab every line reaches, and the one the client opens on.
##
## Index 0 by construction: it is the fallback, and a fallback that was not
## first would be one a new player had to find.
const FALLBACK_TAB := 0

## The tabs, and what each shows. **One row per tab. A new tab is one row.**
##
## `key` stays the same across builds, because the settings file keeps the
## tabs that the player hid from All by key. `name` is the button text.
##
## `types` empty means "everything", which is what makes the first row the
## fallback without a special case anywhere else.
##
## `command_mode` puts the Command chat mode, the line sent as it is, in the
## right-click menu of the tab. The other modes come from the server, and
## each goes on the tab that shows its message type. See [ChatModes].
##
## Every name in `types` is a generated constant and never a literal.
## `Const.MSG_MAP` is in NO tab, so it reaches All only.
const DEFAULT_TABS: Array = [
	{
		"key": "all",
		"name": "All",
		"types": [],
		"command_mode": true,
	},
	{
		"key": "game",
		"name": "Game",
		"types": [Const.MSG_GENERAL, Const.MSG_SYSTEM, Const.MSG_LOOK,
			Const.MSG_MOVE, Const.MSG_TELEPORT, Const.MSG_ROOM,
			Const.MSG_INVENTORY, Const.MSG_CRAFTING, Const.MSG_GATHERING,
			Const.MSG_QUEST, Const.MSG_COMMERCE, Const.MSG_DIALOGUE,
			Const.MSG_MENU, Const.MSG_HELP, Const.MSG_EXAMINE],
		"command_mode": true,
	},
	{
		"key": "combat",
		"name": "Combat",
		"types": [Const.MSG_COMBAT, Const.MSG_VITALS, Const.MSG_PROGRESSION],
	},
	{
		"key": "local",
		"name": "Local",
		"types": [Const.MSG_SAY, Const.MSG_POSE],
	},
	{
		"key": "private",
		"name": "Private",
		"types": [Const.MSG_WHISPER, Const.MSG_PAGE],
	},
	{
		"key": "channel",
		"name": "Channel",
		"types": [Const.MSG_CHANNEL],
	},
]

## Emitted when an unread mark appears or is cleared, so the view can redraw the
## tab strip without polling it every frame.
signal unread_changed

## Emitted when the player opens a different tab.
signal active_changed(index: int)

## Emitted when a tab is hidden from All or shown in All again.
signal filter_changed

## Which tab the player is looking at. Lines that land here are read, not
## unread; see [method note].
var active := FALLBACK_TAB

## tab index -> true. Absent means read. A DICTIONARY of the unread ones rather
## than an array of flags, so "is anything unread" is `is_empty()` and a tab
## added to the table needs no parallel array kept in step with it.
var _unread: Dictionary = {}

## tab index -> true, for each tab hidden from All.
var _hidden: Dictionary = {}


## How many tabs there are.
func count() -> int:
	return DEFAULT_TABS.size()


## One tab's display name.
func name_of(index: int) -> String:
	return str(_row(index).get("name", ""))


## One tab's settings key.
func key_of(index: int) -> String:
	return str(_row(index).get("key", ""))


## The message types that one tab shows. Empty for All, which shows all.
func types_of(index: int) -> Array:
	return _row(index).get("types", [])


## True when the right-click menu of the tab offers the Command chat mode.
func offers_command_mode(index: int) -> bool:
	return bool(_row(index).get("command_mode", false))


## Which tabs show a line of this type, in tab order.
##
## `message_type` is what arrived in the `text` outputfunc's kwargs, which is
## an empty string for the many lines nothing tags. Empty is resolved to
## `MSG_GENERAL` HERE rather than on the server: a default applied at the sender
## would make "nobody has tagged this yet" indistinguishable from "this line is
## genuinely general", and the first is a thing worth being able to find.
##
## All is left out when a tab that claims the type is hidden from All.
func tabs_for(message_type: String) -> PackedInt32Array:
	var kind := _resolved(message_type)
	var found := PackedInt32Array()

	if shows_in_all(kind):
		found.append(FALLBACK_TAB)

	for index: int in range(FALLBACK_TAB + 1, DEFAULT_TABS.size()):
		if types_of(index).has(kind):
			found.append(index)

	return found


## True when a line of this type reaches All. False when a tab that claims
## the type is hidden from All. A type that no tab claims always reaches All.
func shows_in_all(message_type: String) -> bool:
	var kind := _resolved(message_type)

	for index: int in _hidden:
		if types_of(index).has(kind):
			return false

	return true


## Record that a line landed in a tab.
##
## The ACTIVE tab is never marked: the player is looking at it, so there is
## nothing to tell them. Nor is a tab marked twice -- the signal fires on the
## transition only, so a fight that lands forty lines redraws the strip once.
func note(index: int) -> void:
	if index == active or _unread.has(index):
		return

	_unread[index] = true
	unread_changed.emit()


## Whether a tab has unread lines.
func is_unread(index: int) -> bool:
	return _unread.has(index)


## Move the player to a tab and clear its mark.
##
## Returns true when anything actually changed, so a view can skip a redraw on
## a click that reselected the tab already open.
func select(index: int) -> bool:
	if index < 0 or index >= DEFAULT_TABS.size():
		return false

	var was_unread := _unread.erase(index)
	var moved := index != active

	active = index

	if was_unread:
		unread_changed.emit()

	if moved:
		active_changed.emit(index)

	return moved or was_unread


## Move to the next or previous tab, wrapping. Ctrl+Tab in the console.
func cycle(forward: bool) -> void:
	var step := 1 if forward else -1

	select(wrapi(active + step, 0, DEFAULT_TABS.size()))


## Forget every unread mark. Used when the log is cleared.
func clear_unread() -> void:
	if _unread.is_empty():
		return

	_unread.clear()
	unread_changed.emit()


## Whether the lines of a tab are hidden from All.
func is_hidden_from_all(index: int) -> bool:
	return _hidden.has(index)


## Hide the lines of a tab from All, or show them again. All itself cannot be
## hidden from All. Returns true when the filter changed.
func set_hidden_from_all(index: int, hidden: bool) -> bool:
	if index <= FALLBACK_TAB or index >= DEFAULT_TABS.size():
		return false

	if hidden == _hidden.has(index):
		return false

	if hidden:
		_hidden[index] = true
	else:
		_hidden.erase(index)

	filter_changed.emit()

	return true


## The keys of the tabs hidden from All, for the settings file.
func hidden_keys() -> PackedStringArray:
	var keys := PackedStringArray()

	for index: int in DEFAULT_TABS.size():
		if _hidden.has(index):
			keys.append(key_of(index))

	return keys


## Hide exactly the tabs with these keys. A key that names no tab is ignored,
## so a settings file from another build cannot break the strip.
func set_hidden_keys(keys: PackedStringArray) -> void:
	var wanted := {}

	for index: int in range(FALLBACK_TAB + 1, DEFAULT_TABS.size()):
		if keys.has(key_of(index)):
			wanted[index] = true

	if wanted == _hidden:
		return

	_hidden = wanted
	filter_changed.emit()


func _row(index: int) -> Dictionary:
	if index < 0 or index >= DEFAULT_TABS.size():
		return {}

	return DEFAULT_TABS[index]


func _resolved(message_type: String) -> String:
	if message_type.is_empty():
		return Const.MSG_GENERAL

	return message_type
