extends Node
## Unit tests for ChatView -- the logs of the chat interface.
##
##     godot --headless --path godot res://tests/test_chat_view.tscn
##
## Needs nothing running. Builds the view in code and hands it a real
## [ChatTabs], which is the same thing the console does.
##
## Rendering is not tested and is not meant to be: these are the behaviours a
## player would report as bugs -- a line in the wrong tab, a log that grows
## without bound, a find box searching a tab nobody is looking at, a hidden
## tab that still fills All.

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
	_only_the_active_log_shows()
	_the_view_never_takes_the_keyboard()
	_hiding_a_tab_clears_its_lines_from_all()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: chat_view")
	get_tree().quit(0)


## A fresh view, bound and in the tree.
func _fresh() -> void:
	if _view != null:
		_view.queue_free()

	_tabs = ChatTabs.new()
	_view = ChatView.new()
	add_child(_view)
	_view.bind(_tabs)


func _text_in(index: int) -> String:
	return _view.log_at(index).get_parsed_text()


func _index_named(tab_name: String) -> int:
	for index: int in _tabs.count():
		if _tabs.name_of(index) == tab_name:
			return index

	return -1


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

	var pane := _view.log_at(ChatTabs.FALLBACK_TAB)

	_expect(pane.get_paragraph_count() <= ChatView.MAX_LINES,
		"the log stops at the cap")

	var text := pane.get_parsed_text()
	_expect(not text.contains("line 0\n"), "the oldest line was dropped")
	_expect(text.contains("line %d" % (ChatView.MAX_LINES + 49)),
		"and the newest is still there")


func _a_line_marks_the_tabs_you_are_not_reading() -> void:
	_fresh()
	_view.append("You hit the raider.", Const.MSG_COMBAT)

	var combat := _index_named("Combat")

	_expect(_tabs.is_unread(combat), "a combat line marks Combat unread")
	_expect(not _tabs.is_unread(_tabs.active),
		"while the tab being read is not marked")

	_tabs.select(combat)
	_expect(not _tabs.is_unread(combat), "opening the tab clears the mark")


func _the_active_log_follows_the_tab() -> void:
	# Ctrl+F rebinds on this signal. If it did not follow, find would search a
	# log the player cannot see and count matches in it.
	_fresh()

	var seen: Array[RichTextLabel] = []
	_view.active_log_changed.connect(func(pane): seen.append(pane))

	_tabs.select(2)

	_expect(_view.active_log() == _view.log_at(2),
		"active_log names the visible tab")
	_expect(seen.size() == 1 and seen[0] == _view.log_at(2),
		"and the change was announced once, with that log")


func _only_the_active_log_shows() -> void:
	_fresh()
	_tabs.select(3)

	for index: int in _tabs.count():
		_expect(_view.log_at(index).visible == (index == 3),
			"tab %d shows only when it is open" % index)


## Focus IS the mode in this client: the console only reads movement keys when
## the input does NOT have the keyboard.
func _the_view_never_takes_the_keyboard() -> void:
	_fresh()

	_expect(_view.focus_mode == Control.FOCUS_NONE, "the view refuses focus")


## "Hide from All" also clears what All already shows, and "Show in All"
## brings it back. The view draws All again from its history to do this.
func _hiding_a_tab_clears_its_lines_from_all() -> void:
	_fresh()
	var combat := _index_named("Combat")

	_view.append("You hit the raider.", Const.MSG_COMBAT)
	_view.append("Bob says, hello.", Const.MSG_SAY)

	_tabs.set_hidden_from_all(combat, true)

	var all := _text_in(ChatTabs.FALLBACK_TAB)
	_expect(not all.contains("raider"), "a hidden tab's old line leaves All")
	_expect(all.contains("Bob says"), "while the other lines stay")
	_expect(_text_in(combat).contains("raider"), "and Combat keeps its line")

	_view.append("You hit the raider again.", Const.MSG_COMBAT)
	_expect(not _text_in(ChatTabs.FALLBACK_TAB).contains("again"),
		"a new line of the hidden tab stays out of All")

	_tabs.set_hidden_from_all(combat, false)
	all = _text_in(ChatTabs.FALLBACK_TAB)
	_expect(all.contains("raider again") and all.contains("Bob says"),
		"shown again, All has every line back, in order")
	_expect(all.find("You hit the raider.") < all.find("Bob says"),
		"and the order is the order they came in")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
