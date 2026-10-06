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
	_a_move_is_announced_once()
	_cycling_wraps_both_ways()
	_an_untagged_line_reaches_game()
	_a_hidden_tab_keeps_its_lines_out_of_all()
	_all_cannot_be_hidden_from_itself()
	_hidden_keys_round_trip_and_ignore_strangers()
	_every_tab_key_is_unique()

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


func _a_move_is_announced_once() -> void:
	var tabs := ChatTabs.new()
	var seen: Array[int] = []
	tabs.active_changed.connect(func(index: int): seen.append(index))

	tabs.select(3)
	tabs.select(3)

	_expect(seen == [3], "a move fires active_changed once, with the tab")


## Ctrl+Tab in the console. It exists because the buttons refuse focus.
func _cycling_wraps_both_ways() -> void:
	var tabs := ChatTabs.new()
	var last := tabs.count() - 1

	tabs.cycle(true)
	_expect(tabs.active == 1, "forward moves one tab")

	tabs.select(last)
	tabs.cycle(true)
	_expect(tabs.active == 0, "and wraps past the end")

	tabs.cycle(false)
	_expect(tabs.active == last, "backward wraps the other way")


## Game is the OSRS Game tab: everything that is not chat or combat. An
## untagged line is general, so it belongs there.
func _an_untagged_line_reaches_game() -> void:
	var tabs := ChatTabs.new()
	var found := tabs.tabs_for("")
	var names: Array[String] = []

	for index: int in found:
		names.append(tabs.name_of(index))

	_expect(names.has("Game"), "an untagged line reaches Game")


func _a_hidden_tab_keeps_its_lines_out_of_all() -> void:
	var tabs := ChatTabs.new()
	var combat := _index_named(tabs, "Combat")
	var fired := {"n": 0}
	tabs.filter_changed.connect(func(): fired["n"] += 1)

	_expect(tabs.set_hidden_from_all(combat, true), "Combat can be hidden")
	_expect(fired["n"] == 1, "and the change is announced")
	_expect(tabs.tabs_for(Const.MSG_COMBAT) == PackedInt32Array([combat]),
		"a combat line then reaches Combat only")
	_expect(not tabs.shows_in_all(Const.MSG_VITALS),
		"and so does every other type that Combat claims")
	_expect(tabs.shows_in_all(Const.MSG_SAY),
		"while a type of another tab still reaches All")
	_expect(tabs.shows_in_all("a_type_invented_next_month"),
		"and a type that no tab claims still reaches All")
	_expect(not tabs.set_hidden_from_all(combat, true),
		"hiding it again changes nothing")

	tabs.set_hidden_from_all(combat, false)
	_expect(tabs.tabs_for(Const.MSG_COMBAT).has(ChatTabs.FALLBACK_TAB),
		"shown again, a combat line reaches All")


func _all_cannot_be_hidden_from_itself() -> void:
	var tabs := ChatTabs.new()

	_expect(not tabs.set_hidden_from_all(ChatTabs.FALLBACK_TAB, true),
		"All refuses to hide from All")
	_expect(tabs.hidden_keys().is_empty(), "and nothing is hidden")


## The settings file keeps the hidden tabs by key. A file from another build
## can name a tab that is gone, and that must not break the strip.
func _hidden_keys_round_trip_and_ignore_strangers() -> void:
	var tabs := ChatTabs.new()
	var game := _index_named(tabs, "Game")

	tabs.set_hidden_from_all(game, true)
	var kept := tabs.hidden_keys()

	var fresh := ChatTabs.new()
	fresh.set_hidden_keys(kept + PackedStringArray(["a_tab_long_gone", "all"]))

	_expect(fresh.is_hidden_from_all(game), "a kept key hides its tab again")
	_expect(fresh.hidden_keys() == kept,
		"and a key that names no tab, or names All, is ignored")


func _every_tab_key_is_unique() -> void:
	var tabs := ChatTabs.new()
	var keys := {}

	for index: int in tabs.count():
		keys[tabs.key_of(index)] = true

	_expect(keys.size() == tabs.count(), "every tab has its own key")


func _index_named(tabs: ChatTabs, tab_name: String) -> int:
	for index: int in tabs.count():
		if tabs.name_of(index) == tab_name:
			return index

	return -1


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
