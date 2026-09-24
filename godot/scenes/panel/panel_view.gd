class_name PanelView
extends TabContainer
## The control panel: everything about YOU, one tab at a time.
##
## Inventory, worn gear, the character sheet, settings and client help, in a box
## over the 3D world. It replaced three floating [Window]s on 08/28/2026, and
## the column it sat in became [PanelDock] on 09/21/2026.
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
##
## The title is also the NAME of the body node. The strip does not always show
## the title (see below), so [method _index_of] reads the node name.
##
## ## Every tab has an icon, and the label shows when it fits
##
## Eight text titles need about 640 pixels, and the shipped box is 560. The
## strip then showed scroll arrows, and a player could not see every tab. Now
## [method _refresh_labels] picks the first mode that fits the strip:
##
## 1. Every tab shows its icon and its label.
## 2. Every tab shows its icon, and the current tab also shows its label.
## 3. Every tab shows its icon only.
##
## A tooltip names each tab in every mode. The icons come from game-icons.net
## under CC BY 3.0. [method icon_credits] gives their authors to the Credits
## box.

## The tabs this client has. **Adding one is a constant here and one
## `add_panel` call in the console.**
##
## The Inventory body is authored in `console.tscn` because its position in the
## layout is; the others are built in code because their contents are. Both
## routes land in the same strip, and the order is the order they arrive.
const TAB_INVENTORY := "Inventory"
## The paper doll, modelled on OSRS's Worn Equipment tab. Beside Inventory
## because the two are halves of one bag; see [EquipmentView] on what a tab
## strip costs a drag between them, and what replaced it.
const TAB_EQUIPMENT := "Equipment"
## Your weapon and its styles, modelled on OSRS's Combat Options. Beside the
## inventory because a style is picked for the weapon worn there; see
## [CombatOptionsView].
const TAB_COMBAT := "Combat"
const TAB_CHARACTER := "Character"
## Beside Character rather than inside it. The skills band left the dossier on
## 08/28/2026 for a channel and a screen of its own; see [SkillsView].
const TAB_SKILLS := "Skills"
const TAB_QUESTS := "Quests"
const TAB_OPTIONS := "Options"
const TAB_HELP := "Help"

## Returned by [method _index_of] when no tab carries that title.
const NOT_FOUND := -1

## How wide an icon draws in the strip, in pixels. The SVG files import at
## twice this size, so they stay sharp at a UI scale of 2.
const ICON_SIZE := 20

## The label modes, in the order [method _refresh_labels] tries them.
const LABELS_ALL := "all"
const LABELS_CURRENT := "current"
const LABELS_NONE := "none"
const LABEL_MODES: Array[String] = [LABELS_ALL, LABELS_CURRENT, LABELS_NONE]

## The license of every icon in [constant TAB_ICONS].
const ICON_LICENSE := "CC BY 3.0"
const ICON_LICENSE_URL := "https://creativecommons.org/licenses/by/3.0/"
const ICON_PAGE := "https://game-icons.net/1x1/%s/%s.html"

## The icon of each tab: the file, and the game-icons.net author and name that
## it came from. A tab with no row shows its label in every mode.
const TAB_ICONS := {
	TAB_INVENTORY: ["res://ui/icons/inventory.svg", "delapouite", "backpack"],
	TAB_EQUIPMENT: ["res://ui/icons/equipment.svg", "lorc", "breastplate"],
	TAB_COMBAT: ["res://ui/icons/combat.svg", "lorc", "crossed-swords"],
	TAB_CHARACTER: ["res://ui/icons/character.svg", "lorc", "cowled"],
	TAB_SKILLS: ["res://ui/icons/skills.svg", "delapouite", "upgrade"],
	TAB_QUESTS: ["res://ui/icons/quests.svg", "lorc", "scroll-unfurled"],
	TAB_OPTIONS: ["res://ui/icons/options.svg", "lorc", "cog"],
	TAB_HELP: ["res://ui/icons/help.svg", "lorc", "uncertainty"],
}

## The label mode in use. See [method _refresh_labels].
var label_mode := LABELS_ALL


func _init() -> void:
	_refuse_focus()
	add_theme_constant_override("icon_max_width", ICON_SIZE)
	tab_changed.connect(func(_index: int): _refresh_labels())
	resized.connect(_refresh_labels)


func _ready() -> void:
	# The Inventory body comes from `console.tscn`, before any call to
	# add_panel. Its icon and tooltip go on here.
	for index: int in get_tab_count():
		_dress_tab(index)

	_refresh_labels()


## One row for the Credits box for each icon, in the shape [CreditsState]
## reads.
static func icon_credits() -> Array[Dictionary]:
	var credits: Array[Dictionary] = []

	for title: String in TAB_ICONS:
		var row: Array = TAB_ICONS[title]
		var author: String = row[1]

		credits.append({
			"title": "%s tab icon (%s)" % [title, row[2]],
			"author": author.capitalize(),
			"license": ICON_LICENSE,
			"license_url": ICON_LICENSE_URL,
			"url": ICON_PAGE % [author, row[2]],
			"confirmed": true,
		})

	return credits


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
	_dress_tab(get_tab_count() - 1)
	_refresh_labels()


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
	_refresh_labels()


## Give one tab its icon and its tooltip. The label is [method _refresh_labels]'s.
func _dress_tab(index: int) -> void:
	var title := _title_at(index)
	var row: Array = TAB_ICONS.get(title, [])

	if not row.is_empty():
		set_tab_icon(index, load(row[0]))

	get_tab_bar().set_tab_tooltip(index, title)


## Show every label that fits, and the icon for the rest.
##
## Runs on each resize, each tab change, and each tab added or hidden. The
## first mode in [constant LABEL_MODES] whose strip fits the width wins. The
## last mode always applies, so a narrow box shows icons and never arrows.
func _refresh_labels() -> void:
	var chosen := LABELS_NONE

	for mode: String in LABEL_MODES:
		if _strip_width(mode) <= size.x:
			chosen = mode
			break

	label_mode = chosen

	for index: int in get_tab_count():
		var shown := _label_shown(index, chosen)
		set_tab_title(index, _title_at(index) if shown else "")


## How wide the strip is in one mode, in pixels, from the theme's own parts.
func _strip_width(mode: String) -> float:
	var style := get_theme_stylebox("tab_selected")
	var font := get_theme_font("font")
	var font_size := get_theme_font_size("font_size")
	var gap := get_theme_constant("icon_separation")
	var total := 0.0

	for index: int in get_tab_count():
		if is_tab_hidden(index):
			continue

		var has_icon := TAB_ICONS.has(_title_at(index))
		var width := style.get_minimum_size().x

		if has_icon:
			width += ICON_SIZE

		if _label_shown(index, mode):
			width += font.get_string_size(
				_title_at(index), HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x

			if has_icon:
				width += gap

		total += width

	return total


## Whether one tab shows its label in one mode. A tab with no icon always
## does, because a blank tab names nothing.
func _label_shown(index: int, mode: String) -> bool:
	if not TAB_ICONS.has(_title_at(index)):
		return true

	if mode == LABELS_ALL:
		return true

	return mode == LABELS_CURRENT and index == current_tab


## The title of one tab, which is the name of its body node.
func _title_at(index: int) -> String:
	var body := get_tab_control(index)

	if body == null:
		return ""

	return String(body.name)


func _index_of(title: String) -> int:
	var body := get_node_or_null(NodePath(title))

	if body == null or not (body is Control):
		return NOT_FOUND

	return get_tab_idx_from_control(body)
