class_name ChatTabs
extends RefCounted
## Which tab a line of game text belongs in, and which tabs have unread lines.
##
## Pure rules and a little state; it holds no text. The lines themselves live in
## the [RichTextLabel]s [ChatView] builds, because Godot's own advice for a
## console-sized log is to `append_text` each new fragment rather than reassign
## the whole thing -- so a model that also kept a copy would be storing every
## line twice to save nothing.
##
## ## The tab table is the CLIENT's, and that is the whole ownership story
##
## The server says what a line IS -- `char.msg(text=(line, {"type": "combat"}))`
## -- and the vocabulary it may use is generated into
## `autoload/blackout_constants.gd` as `MSG_*`. It says nothing about tabs, and
## it must not: there is no server fact naming a tab, and a `char_tabs` channel
## would be the client asking the game to hold its layout.
##
## The consequence is worth stating because it looks like a bug until you know
## it: **a type no tab claims is not lost.** [constant FALLBACK_TAB] shows
## everything, it is where the player starts, and a message type added on the
## server tomorrow appears there with no edit here. That is the same
## degradation an item with no art gets from the mesh ladder.
##
## ## Untagged is normal
##
## Evennia's own EvMenu nodes, `page`, and a good deal of its error prose carry
## no tag at all. An untagged line is read as [constant Const.MSG_GENERAL]
## rather than dropped -- see [method tabs_for].

## Server-owned names, generated from blackout/systems/statefeed/constants.py.
## Preloaded, not autoloaded -- the generated file declares no `extends Node`.
const Const := preload("res://autoload/blackout_constants.gd")

## The tab every line reaches, and the one the client opens on.
##
## Index 0 by construction: it is the fallback, and a fallback that was not
## first would be one a new player had to find.
const FALLBACK_TAB := 0

## The tabs, and what each shows. **One row per tab; adding one is one row.**
##
## `types` empty means "everything", which is what makes the first row the
## fallback without a special case anywhere else.
##
## Every name on the right is a generated constant and never a literal. A
## literal here is the failure mode the whole generated-constants pipeline
## exists to stop: the dead `"Pole clearing"` room kind reached two clients that
## way and rendered a fallback colour in both for two days.
##
## `Const.MSG_MAP` is deliberately in NO tab. Once the minimap draws from
## `blackout_map` the server stops sending the ASCII map to this client at all,
## and until then it falls to All -- which is exactly where it goes today.
const DEFAULT_TABS: Array = [
	{
		"name": "All",
		"types": [],
	},
	{
		"name": "Combat",
		"types": [Const.MSG_COMBAT, Const.MSG_VITALS, Const.MSG_PROGRESSION],
	},
	{
		"name": "Chat",
		"types": [Const.MSG_SAY, Const.MSG_WHISPER, Const.MSG_POSE,
			Const.MSG_CHANNEL],
	},
	{
		"name": "Log",
		"types": [Const.MSG_LOOK, Const.MSG_MOVE, Const.MSG_TELEPORT,
			Const.MSG_ROOM, Const.MSG_INVENTORY, Const.MSG_CRAFTING,
			Const.MSG_GATHERING, Const.MSG_QUEST, Const.MSG_COMMERCE,
			Const.MSG_DIALOGUE],
	},
	{
		"name": "System",
		"types": [Const.MSG_SYSTEM, Const.MSG_HELP, Const.MSG_EXAMINE],
	},
]

## Emitted when an unread mark appears or is cleared, so the view can redraw the
## tab strip without polling it every frame.
signal unread_changed

## Which tab the player is looking at. Lines that land here are read, not
## unread; see [method note].
var active := FALLBACK_TAB

## tab index -> true. Absent means read. A DICTIONARY of the unread ones rather
## than an array of flags, so "is anything unread" is `is_empty()` and a tab
## added to the table needs no parallel array kept in step with it.
var _unread: Dictionary = {}


## How many tabs there are.
func count() -> int:
	return DEFAULT_TABS.size()


## One tab's display name.
func name_of(index: int) -> String:
	if index < 0 or index >= DEFAULT_TABS.size():
		return ""

	return str(DEFAULT_TABS[index].get("name", ""))


## Which tabs show a line of this type, in tab order.
##
## `message_type` is what arrived in the `text` outputfunc's kwargs, which is
## an empty string for the many lines nothing tags. Empty is resolved to
## `MSG_GENERAL` HERE rather than on the server: a default applied at the sender
## would make "nobody has tagged this yet" indistinguishable from "this line is
## genuinely general", and the first is a thing worth being able to find.
func tabs_for(message_type: String) -> PackedInt32Array:
	var kind := message_type

	if kind.is_empty():
		kind = Const.MSG_GENERAL

	var found := PackedInt32Array()

	for index: int in DEFAULT_TABS.size():
		var types: Array = DEFAULT_TABS[index].get("types", [])

		# An empty list is the fallback tab and takes everything.
		if types.is_empty() or types.has(kind):
			found.append(index)

	return found


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

	return moved or was_unread


## Forget every unread mark. Used when the log is cleared.
func clear_unread() -> void:
	if _unread.is_empty():
		return

	_unread.clear()
	unread_changed.emit()
