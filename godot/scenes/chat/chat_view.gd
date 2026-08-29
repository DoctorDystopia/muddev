class_name ChatView
extends TabContainer
## The game log, split into tabs by what each line is about.
##
## Presentation and gesture only. What a line IS comes from the server as a
## routing tag on the `text` outputfunc; which tab shows it is [ChatTabs]; this
## file decides how it LOOKS and nothing else.
##
## ## A TabContainer, because Godot has one
##
## It draws the strip, shows one child at a time, reports a click, and titles
## each tab. The webclient's equivalent was `message_routing.js` plus a
## GoldenLayout pane per destination plus a per-player regex table; here the
## engine is the whole layout and the routing is one dictionary lookup.
##
## ## One RichTextLabel per tab, appended to. Not one, re-rendered on switch.
##
## This is forced by the platform rather than chosen. Godot's own documentation
## says a console-sized log stutters when its `text` property is reassigned,
## because that reparses every line of BBCode, and prescribes `append_text` --
## which parses only the fragment -- plus `threaded` to keep the parse off the
## main thread. A design that re-rendered the buffer on tab switch would do the
## expensive thing on the one interaction the player performs most.
##
## Append-per-tab also keeps each tab's scroll position for free, which is the
## difference between a tab strip and an annoying one: switching to Combat and
## back must not send the player to the bottom of a log they were reading.
##
## The cost is that a line matching two tabs is parsed twice and stored twice.
## In practice that is All plus at most one other, and [constant MAX_LINES] caps
## what any of them keeps.

## Emitted when the visible log changes, so whatever searches it can rebind.
## Ctrl+F must follow the tab the player is looking at.
signal active_log_changed(pane: RichTextLabel)

## How many paragraphs a tab keeps before it starts dropping the oldest.
##
## A cap PER TAB rather than one shared budget: the tabs hold different amounts
## of the same conversation, and a shared cap would let a fight in Combat evict
## the room description in Log.
##
## `remove_paragraph(0)` is the only way to bound a RichTextLabel -- there is no
## max-lines property -- and it is cheap because it removes a parsed item rather
## than reparsing what is left.
const MAX_LINES := 2000

## Drawn on a tab that has lines the player has not looked at.
##
## A DOT and not a count. A count invites reading the number instead of opening
## the tab, and the buffer above is capped anyway, so the number would go on
## being wrong in a way nobody could see.
const UNREAD_MARK := " •"

var _tabs: ChatTabs

## tab index -> its log. Parallel to ChatTabs by construction: both are built
## from DEFAULT_TABS in the same pass.
var _logs: Array[RichTextLabel] = []


func _init() -> void:
	# The strip is the only reason this is a TabContainer; the engine draws it.
	clip_tabs = false
	_refuse_focus()


## Bind to the routing model and build one log per tab.
##
## Takes the model rather than making one, so this scene can be opened on its
## own with a hand-built ChatTabs -- the same arrangement every other pane in
## this client uses, and what makes it testable without a server.
func bind(tabs: ChatTabs) -> void:
	_tabs = tabs

	for index: int in _tabs.count():
		var pane := _build_log()
		pane.name = _tabs.name_of(index)
		_logs.append(pane)
		add_child(pane)

	tab_changed.connect(_on_tab_changed)
	_tabs.unread_changed.connect(_retitle)

	current_tab = _tabs.active
	_retitle()
	active_log_changed.emit(active_log())



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


## Move to the next or previous tab, wrapping.
##
## Ctrl+Tab, bound in the console. It exists because the strip refuses focus
## above: without a key route, filtering the log would be mouse-only, and the
## one thing this client's input model guarantees is that a player never has to
## take their hands off the keyboard mid-fight.
func cycle(forward: bool) -> void:
	if _logs.size() < 2:
		return

	var step := 1 if forward else -1

	current_tab = wrapi(current_tab + step, 0, _logs.size())


## Put one line where it belongs.
##
## `message_type` is what arrived in the outputfunc's kwargs, and is an empty
## string for the many lines nothing tags. [method ChatTabs.tabs_for] resolves
## that; this file never decides what an untagged line means.
func append(bbcode: String, message_type: String) -> void:
	if _tabs == null:
		return

	for index: int in _tabs.tabs_for(message_type):
		var pane := _logs[index]
		pane.append_text(bbcode + "\n")
		_trim(pane)
		_tabs.note(index)


## The log the player is looking at. What Ctrl+F searches.
func active_log() -> RichTextLabel:
	if _logs.is_empty():
		return null

	return _logs[clampi(current_tab, 0, _logs.size() - 1)]


## Apply the player's chosen text size to every tab.
##
## RichTextLabel keeps a font size PER STYLE, so setting only `font_size` leaves
## bold and italic text at the default and the log ends up ragged. That was
## found once already, in console.gd, and is the reason this loops.
func apply_font_size(size_px: int) -> void:
	for pane: RichTextLabel in _logs:
		for style: String in ["normal_font_size", "bold_font_size",
				"italics_font_size", "mono_font_size"]:
			pane.add_theme_font_size_override(style, size_px)


func _build_log() -> RichTextLabel:
	var pane := RichTextLabel.new()

	# The font, the colour and the line spacing are the theme's; see the
	# ChatLog variation in ui/blackout_theme.tres. The monospace face is
	# load-bearing -- the dossier and every section rule in the game are drawn
	# with box characters -- which is why it is named there rather than left to
	# whatever the platform picks.
	pane.theme_type_variation = &"ChatLog"
	pane.bbcode_enabled = true
	pane.scroll_following = true
	pane.selection_enabled = true
	pane.focus_mode = Control.FOCUS_CLICK

	# Godot's documented answer to a large console log: parsing still costs
	# what it costs, but it stops blocking the frame, so a burst of combat
	# lines cannot stutter the world pane beside it.
	pane.threaded = true

	return pane


## Drop the oldest paragraphs once a log is over its cap.
##
## A WHILE and not an if: a single append can add several paragraphs when the
## server sends a block of text, so trimming one per call would let a log drift
## permanently over the cap.
func _trim(pane: RichTextLabel) -> void:
	while pane.get_paragraph_count() > MAX_LINES:
		pane.remove_paragraph(0)


func _on_tab_changed(index: int) -> void:
	_tabs.select(index)
	_retitle()
	active_log_changed.emit(active_log())


## Redraw the strip's titles, marks and all.
##
## Titles rather than icons: an icon means a texture to author, ship and theme
## for two states, where the mark is one character the tab font already has.
func _retitle() -> void:
	if _tabs == null:
		return

	for index: int in _tabs.count():
		var title := _tabs.name_of(index)

		if _tabs.is_unread(index):
			title += UNREAD_MARK

		set_tab_title(index, title)
