class_name PanelView
extends TabContainer
## The control panel: everything about YOU, one tab at a time.
##
## Inventory, the character sheet, settings and client help, in the column
## beside the 3D world. It replaced three floating [Window]s on 08/28/2026.
##
## ## Why the windows went
##
## A Godot `Window` is the native answer on the desktop and a poor one on the
## web, which is the primary target: a web export is one `<canvas>`, so a Window
## is an EMBEDDED subwindow drawn inside the game area rather than an OS window
## that can be moved beside it. It could not leave the canvas, it remembered
## neither position nor size, and there was no keyboard route to any of the
## three. A tab strip is smaller, reachable, and the shape the reference
## interface uses.
##
## ## It holds no state and knows nothing about what is in a tab
##
## Each body is a Control the console built and bound to a model. This file
## adds, titles and selects; it never reads a payload. That is the same line
## [ChatView] draws, one column over.
##
## ## Tabs are addressed by TITLE
##
## Not by index. An index is a number two files have to agree on, and they
## agree until somebody inserts a tab -- at which point the HUD's Character
## button opens Options and nothing errors. The title is the thing that is
## already displayed, so a mismatch is visible rather than silent.

## The tabs this client has. **Adding one is a constant here and one
## `add_panel` call in the console.**
##
## The Inventory body is authored in `console.tscn` because its position in the
## layout is; the other three are built in code because their contents are.
## Both routes land in the same strip, and the order is the order they arrive.
const TAB_INVENTORY := "Inventory"
const TAB_CHARACTER := "Character"
## Beside Character rather than inside it. The skills band left the dossier on
## 08/28/2026 for a channel and a screen of its own; see [SkillsView].
const TAB_SKILLS := "Skills"
const TAB_QUESTS := "Quests"
const TAB_OPTIONS := "Options"
const TAB_HELP := "Help"

## Returned by [method _index_of] when no tab carries that title.
const NOT_FOUND := -1


func _init() -> void:
	_refuse_focus()


## Keep the keyboard where it was when a tab is clicked.
##
## **Focus IS the mode in this client** -- console.gd grabs the input on ready
## and [method Console._unhandled_key_input] only runs when the input does not
## have it, so anything that silently takes focus turns the next letter the
## player types into a movement command. A tab strip is not text entry and has
## no business doing that: filtering a log is not leaving the input.
##
## The internal [TabBar] is what receives the click, so it needs the setting as
## well as the container -- setting only the container leaves the strip
## focusable and the bug in place.
func _refuse_focus() -> void:
	focus_mode = Control.FOCUS_NONE

	var bar := get_tab_bar()

	if bar != null:
		bar.focus_mode = Control.FOCUS_NONE


## Add one body under one title.
##
## The body is reparented into this container, so the caller does not add it to
## the tree itself -- a Control added anywhere else and then moved would flicker
## through one frame at its old position.
func add_panel(title: String, body: Control) -> void:
	body.name = title
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(body)
	set_tab_title(get_tab_count() - 1, title)


## Bring one tab to the front. A title nothing carries is ignored.
##
## Ignored rather than pushed: the caller is a button, the miss is a
## programming error rather than a player one, and moving the player to an
## arbitrary tab would be a worse answer than doing nothing.
func select_panel(title: String) -> void:
	var index := _index_of(title)

	if index == NOT_FOUND:
		push_warning("PanelView: no tab titled %s" % title)
		return

	current_tab = index


## Show or hide one tab without destroying what is in it.
##
## `set_tab_hidden` and not `visible`: a TabContainer owns its children's
## visibility -- it shows exactly one -- so hiding a body directly fights the
## container and the tab stays in the strip pointing at nothing.
func set_panel_hidden(title: String, hidden: bool) -> void:
	var index := _index_of(title)

	if index == NOT_FOUND:
		return

	set_tab_hidden(index, hidden)


func _index_of(title: String) -> int:
	for index: int in get_tab_count():
		if get_tab_title(index) == title:
			return index

	return NOT_FOUND
