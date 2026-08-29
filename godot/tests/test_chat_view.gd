extends Node
## Unit tests for ChatView -- the tab strip that draws the game log.
##
##     godot --headless --path godot res://tests/test_chat_view.tscn
##
## Needs nothing running. Builds the view in code and hands it a real
## [ChatTabs], which is the same thing the console does.
##
## Rendering is not tested and is not meant to be: these are the behaviours a
## player would report as bugs -- a line in the wrong tab, a log that grows
## without bound, a find box searching a tab nobody is looking at.

const Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0
var _view: ChatView
var _tabs: ChatTabs


func _ready() -> void:
	_a_line_reaches_every_tab_that_claims_it()
	_an_untagged_line_is_not_lost()
	_a_log_is_capped_and_it_is_the_oldest_that_goes()
	_a_line_marks_the_tabs_you_are_not_reading()
	_the_active_log_follows_the_tab()
	_the_strip_never_takes_the_keyboard()
	_ctrl_tab_walks_the_tabs_and_wraps()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: chat_view")
	get_tree().quit(0)


## A fresh view, bound and in the tree.
##
## In the tree because TabContainer does its child bookkeeping on entering it;
## a detached one reports `get_tab_count() == 0` and every assertion below
## would pass for the wrong reason.
func _fresh() -> void:
	if _view != null:
		_view.queue_free()

	_tabs = ChatTabs.new()
	_view = ChatView.new()
	add_child(_view)
	_view.bind(_tabs)


func _text_in(index: int) -> String:
	return (_view.get_child(index) as RichTextLabel).get_parsed_text()


func _a_line_reaches_every_tab_that_claims_it() -> void:
	_fresh()
	_view.append("You hit the raider.", Const.MSG_COMBAT)

	var combat := _tabs.tabs_for(Const.MSG_COMBAT)

	for index: int in combat:
		_expect(_text_in(index).contains("raider"),
			"a combat line reached tab %s" % _tabs.name_of(index))

	# And nowhere else. A line in two tabs is fine; a line in five is a filter
	# that has stopped filtering.
	for index: int in _tabs.count():
		if combat.has(index):
			continue

		_expect(not _text_in(index).contains("raider"),
			"and not tab %s" % _tabs.name_of(index))


func _an_untagged_line_is_not_lost() -> void:
	# Evennia's EvMenu nodes and most of its error prose send no tag at all.
	_fresh()
	_view.append("Choose an option.", "")

	_expect(_text_in(ChatTabs.FALLBACK_TAB).contains("Choose an option"),
		"an untagged line lands in the fallback tab")


func _a_log_is_capped_and_it_is_the_oldest_that_goes() -> void:
	# A MUD log runs for hours. Without this the client grows until it stops.
	_fresh()

	for n: int in ChatView.MAX_LINES + 50:
		_view.append("line %d" % n, Const.MSG_SYSTEM)

	var pane := _view.get_child(ChatTabs.FALLBACK_TAB) as RichTextLabel

	_expect(pane.get_paragraph_count() <= ChatView.MAX_LINES,
		"the log stops at the cap")

	var text := pane.get_parsed_text()
	_expect(not text.contains("line 0\n"), "the oldest line was dropped")
	_expect(text.contains("line %d" % (ChatView.MAX_LINES + 49)),
		"and the newest is still there")


func _a_line_marks_the_tabs_you_are_not_reading() -> void:
	_fresh()
	_view.append("You hit the raider.", Const.MSG_COMBAT)

	var combat := _tabs.tabs_for(Const.MSG_COMBAT)
	var other := -1

	for index: int in combat:
		if index != _tabs.active:
			other = index

	_expect(other != -1, "a combat line reached a tab that was not open")
	_expect(_tabs.is_unread(other), "and marked it unread")
	_expect(_view.get_tab_title(other).ends_with(ChatView.UNREAD_MARK),
		"and the strip says so")
	_expect(not _view.get_tab_title(_tabs.active).ends_with(ChatView.UNREAD_MARK),
		"while the tab being read is not marked")

	_view.current_tab = other
	_expect(not _view.get_tab_title(other).ends_with(ChatView.UNREAD_MARK),
		"opening the tab clears the mark")


func _the_active_log_follows_the_tab() -> void:
	# Ctrl+F rebinds on this signal. If it did not follow, find would search a
	# log the player cannot see and count matches in it.
	_fresh()

	var seen: Array[RichTextLabel] = []
	_view.active_log_changed.connect(func(pane): seen.append(pane))

	_view.current_tab = 2

	_expect(_view.active_log() == _view.get_child(2),
		"active_log names the visible tab")
	_expect(seen.size() == 1 and seen[0] == _view.get_child(2),
		"and the change was announced once, with that log")


## Focus IS the mode in this client: the console only reads movement keys when
## the input does NOT have the keyboard. A strip that took focus on click would
## turn the next letter the player typed into a walk.
func _the_strip_never_takes_the_keyboard() -> void:
	_fresh()

	_expect(_view.focus_mode == Control.FOCUS_NONE,
		"the container refuses focus")
	_expect(_view.get_tab_bar().focus_mode == Control.FOCUS_NONE,
		"and so does the tab bar, which is what actually gets clicked")


## The key route that has to exist BECAUSE of the case above.
func _ctrl_tab_walks_the_tabs_and_wraps() -> void:
	_fresh()
	var last := _tabs.count() - 1

	_view.cycle(true)
	_expect(_view.current_tab == 1, "forward moves one tab")

	_view.current_tab = last
	_view.cycle(true)
	_expect(_view.current_tab == 0, "and wraps past the end")

	_view.cycle(false)
	_expect(_view.current_tab == last, "backward wraps the other way")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
