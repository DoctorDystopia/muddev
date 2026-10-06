class_name ChatView
extends Control
## The game log: one RichTextLabel for each tab, and one of them shows.
##
## Presentation only. What a line IS comes from the server as a routing tag
## on the `text` outputfunc. Which tab shows it is [ChatTabs]. The buttons
## that pick a tab are [ChatBar], along the bottom of the log box, as in the
## OSRS chat interface. This file decides how the log LOOKS and nothing else.
##
## ## One RichTextLabel per tab, appended to. Not one, re-rendered on switch.
##
## Godot's own documentation says that a console-sized log stutters when code
## assigns its `text` property, because that parses every line of BBCode
## again. It prescribes `append_text`, which parses only the fragment, plus
## `threaded`. A design that rendered the buffer again on each tab switch would
## do the expensive thing on the most frequent interaction.
##
## Append-per-tab also keeps the scroll position of each tab: a switch to
## Combat and back must not send the player to the bottom of a log that they
## were reading.
##
## ## All is drawn again on a filter change, and only then
##
## "Hide from All" must also clear the lines that All already shows. The view
## keeps the source of each All line, capped at [constant MAX_LINES], and
## draws All again from it when the filter changes. A filter change is rare,
## so the one full parse costs nothing that a player feels.

## Emitted when the visible log changes, so whatever searches it can rebind.
## Ctrl+F must follow the tab the player is looking at.
signal active_log_changed(pane: RichTextLabel)

## How many paragraphs a tab keeps before it starts dropping the oldest.
##
## A cap PER TAB rather than one shared budget: the tabs hold different amounts
## of the same conversation, and a shared cap would let a fight in Combat evict
## the room description in Game.
##
## `remove_paragraph(0, true)` is the only way to bound a RichTextLabel -- there
## is no max-lines property. The second argument is load-bearing; see
## [method ChatView._trim].
const MAX_LINES := 2000

var _tabs: ChatTabs

## tab index -> its log. Parallel to ChatTabs by construction: both are built
## from DEFAULT_TABS in the same pass.
var _logs: Array[RichTextLabel] = []

## Every line that reached the view, as [bbcode, message_type], the oldest
## first. What All is drawn again from when the filter changes.
var _history: Array = []


func _init() -> void:
	# Not text entry. Focus IS the mode in this client, so a log that took
	# the keyboard on a click would turn the next letter into a walk. Each
	# log takes focus on a click only, to allow a text selection.
	focus_mode = Control.FOCUS_NONE


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

	_tabs.active_changed.connect(_on_active_changed)
	_tabs.filter_changed.connect(_redraw_all)

	_show(_tabs.active)


## Put one line where it belongs.
##
## `message_type` is what arrived in the outputfunc's kwargs, and is an empty
## string for the many lines nothing tags. [method ChatTabs.tabs_for] resolves
## that; this file never decides what an untagged line means.
func append(bbcode: String, message_type: String) -> void:
	if _tabs == null:
		return

	_history.append([bbcode, message_type])

	if _history.size() > MAX_LINES:
		_history.pop_front()

	for index: int in _tabs.tabs_for(message_type):
		var pane := _logs[index]
		pane.append_text(bbcode + "\n")
		_trim(pane)
		_tabs.note(index)


## The log the player is looking at. What Ctrl+F searches.
func active_log() -> RichTextLabel:
	if _logs.is_empty():
		return null

	return _logs[clampi(_tabs.active, 0, _logs.size() - 1)]


## The log of one tab. For a test, and for nothing else.
func log_at(index: int) -> RichTextLabel:
	return _logs[index]


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
	pane.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

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
##
## ## `no_invalidate` is the whole fix for the stuttering log
##
## `remove_paragraph(paragraph)` defaults to `no_invalidate = false`, and that
## sets the label's first invalid line back to 0. Every paragraph the log holds
## is then shaped again. Above, `threaded` moves that work to a thread, so the
## label reports the height it has shaped SO FAR -- and the scrollbar collapses
## and grows back on every line the server sends.
##
## Measured in Godot 4.7.1 with 2000 paragraphs: the scroll range fell from
## 46000 to 3933 on every frame that appended a line. With `true` it stayed at
## 46000 and never moved. The player sees this as a log that jumps and stutters
## on each command, and only after enough lines to reach [constant MAX_LINES].
##
## `true` is correct here because the removal is at the TOP, off screen. The
## paragraphs that stay keep their shaped text, and only their vertical offsets
## move up.
func _trim(pane: RichTextLabel) -> void:
	while pane.get_paragraph_count() > MAX_LINES:
		pane.remove_paragraph(0, true)


func _on_active_changed(index: int) -> void:
	_show(index)
	active_log_changed.emit(active_log())


## Show the log of one tab and hide the others. A hidden log keeps its text
## and its scroll position.
func _show(index: int) -> void:
	for at: int in _logs.size():
		_logs[at].visible = at == index


## Draw All again from the history, with the filter as it is now.
##
## One `append_text` of the joined lines, so the log parses one time.
func _redraw_all() -> void:
	var pane := _logs[ChatTabs.FALLBACK_TAB]
	var lines := PackedStringArray()

	for entry: Array in _history:
		if _tabs.shows_in_all(entry[1]):
			lines.append(entry[0] + "\n")

	pane.clear()
	pane.append_text("".join(lines))
	_trim(pane)
