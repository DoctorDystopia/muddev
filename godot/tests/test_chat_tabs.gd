extends Node
## Unit tests for ChatTabs -- the routing rules behind the chat tab strip.
##
##     godot --headless --path godot res://tests/test_chat_tabs.tscn
##
## Needs nothing running.

const Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_the_fallback_tab_takes_everything()
	_a_tagged_line_reaches_its_own_tab_as_well()
	_an_untagged_line_is_general_and_not_dropped()
	_a_type_no_tab_claims_still_reaches_the_player()
	_every_tab_names_only_generated_types()
	_unread_marks_the_tabs_you_are_not_looking_at()
	_selecting_a_tab_clears_its_mark()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: chat_tabs")
	get_tree().quit(0)


func _the_fallback_tab_takes_everything() -> void:
	# It is where the player starts, so it is what makes an unclaimed type a
	# degradation rather than a disappearance.
	var tabs := ChatTabs.new()

	for message_type: String in Const.MESSAGE_TYPES:
		var found := tabs.tabs_for(message_type)

		if not found.has(ChatTabs.FALLBACK_TAB):
			_fail("%s reaches the fallback tab" % message_type)
			return

	_pass("every declared type reaches the fallback tab")


func _a_tagged_line_reaches_its_own_tab_as_well() -> void:
	var tabs := ChatTabs.new()
	var found := tabs.tabs_for(Const.MSG_COMBAT)

	_expect(found.size() == 2, "a combat line lands in two tabs")
	_expect(found.has(ChatTabs.FALLBACK_TAB), "one of them is All")

	var other := found[0] if found[0] != ChatTabs.FALLBACK_TAB else found[1]
	_expect(tabs.name_of(other) == "Combat", "and the other is Combat")


func _an_untagged_line_is_general_and_not_dropped() -> void:
	# Evennia's own EvMenu nodes and error prose send no tag at all. Half the
	# game would vanish if this returned nothing.
	var tabs := ChatTabs.new()

	_expect(tabs.tabs_for("") == tabs.tabs_for(Const.MSG_GENERAL),
		"an untagged line routes exactly as a general one")
	_expect(not tabs.tabs_for("").is_empty(),
		"and reaches at least one tab")


func _a_type_no_tab_claims_still_reaches_the_player() -> void:
	# MSG_MAP is in no tab on purpose, and a type invented on the server
	# tomorrow is in none either. Both must still be readable.
	var tabs := ChatTabs.new()

	_expect(tabs.tabs_for(Const.MSG_MAP) == PackedInt32Array([ChatTabs.FALLBACK_TAB]),
		"an unclaimed type reaches the fallback tab and only that")
	_expect(tabs.tabs_for("a_type_invented_next_month").size() == 1,
		"and so does one this client has never heard of")


func _every_tab_names_only_generated_types() -> void:
	# The asymmetry, in the direction that is a bug: a tab naming a type the
	# server does not declare is a filter that can never match, and it looks
	# exactly like a quiet channel. The reverse -- a declared type in no tab --
	# is fine and is asserted above.
	var tabs := ChatTabs.new()
	var declared := Const.MESSAGE_TYPES

	for index: int in tabs.count():
		for message_type: String in ChatTabs.DEFAULT_TABS[index].get("types", []):
			if not declared.has(message_type):
				_fail("tab %s names the undeclared type %s"
					% [tabs.name_of(index), message_type])
				return

	_pass("every type named by a tab is one the server declares")


func _unread_marks_the_tabs_you_are_not_looking_at() -> void:
	var tabs := ChatTabs.new()
	var fired := {"n": 0}
	tabs.unread_changed.connect(func(): fired["n"] += 1)

	tabs.note(ChatTabs.FALLBACK_TAB)
	_expect(not tabs.is_unread(ChatTabs.FALLBACK_TAB),
		"the tab you are on is never marked")
	_expect(fired["n"] == 0, "and nothing is redrawn for it")

	tabs.note(1)
	_expect(tabs.is_unread(1), "another tab is marked")
	_expect(fired["n"] == 1, "and the strip is redrawn once")

	# Forty lines in a fight must not be forty redraws.
	tabs.note(1)
	tabs.note(1)
	_expect(fired["n"] == 1, "a tab already marked does not fire again")


func _selecting_a_tab_clears_its_mark() -> void:
	var tabs := ChatTabs.new()
	tabs.note(2)

	_expect(tabs.select(2), "moving to a marked tab reports a change")
	_expect(not tabs.is_unread(2), "and clears the mark")
	_expect(tabs.active == 2, "and moves the player there")
	_expect(not tabs.select(2), "reselecting the same clean tab changes nothing")
	_expect(not tabs.select(99), "an index off the end is refused")
	_expect(tabs.active == 2, "and does not move the player")


func _expect(passed: bool, what: String) -> void:
	if passed:
		_pass(what)
		return

	_fail(what)


func _pass(what: String) -> void:
	print("  ok   %s" % what)


func _fail(what: String) -> void:
	_failures += 1
	printerr("  FAIL %s" % what)
