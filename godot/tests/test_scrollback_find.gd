extends Node
## Unit tests for ScrollbackFind.
##
##     godot --headless --path godot res://tests/test_scrollback_find.tscn

const LOG := "You attack the Mutant Raider.\nThe raider hits you for 4.\nThe RAIDER dies."

var _failures := 0


func _ready() -> void:
	_it_finds_every_occurrence_regardless_of_case()
	_it_cycles_forward_and_wraps()
	_it_cycles_backward_and_wraps()
	_overlapping_matches_step_past_themselves()
	_an_empty_query_clears_rather_than_matching_everything()
	_no_matches_is_a_state_not_an_error()
	_status_text_says_what_a_player_needs()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: scrollback_find")
	get_tree().quit(0)


func _it_finds_every_occurrence_regardless_of_case() -> void:
	# Players type `raider`; the log says `Mutant Raider` and `RAIDER`.
	var find := ScrollbackFind.new()

	_expect(find.search(LOG, "raider") == 3, "all three cases are found")
	_expect(find.current() == LOG.to_lower().find("raider"),
		"and the first match is selected")


func _it_cycles_forward_and_wraps() -> void:
	# A find that stops dead at the end makes a player wonder if it is broken.
	var find := ScrollbackFind.new()
	find.search(LOG, "raider")

	var first := find.current()
	find.next()
	find.next()

	_expect(find.current_number() == 3, "next reaches the last match")
	_expect(find.next() == first, "and wraps to the first")


func _it_cycles_backward_and_wraps() -> void:
	var find := ScrollbackFind.new()
	find.search(LOG, "raider")

	_expect(find.current_number() == 1, "starts on the first")
	find.previous()
	_expect(find.current_number() == 3, "back past the first wraps to the last")


func _overlapping_matches_step_past_themselves() -> void:
	# Searching `aa` in `aaaa` is 0 and 2, not 0, 1, 2: stepping forward should
	# move past what is highlighted, not one character.
	var find := ScrollbackFind.new()

	_expect(find.search("aaaa", "aa") == 2, "overlaps are counted once each")
	_expect(find.current() == 0, "first at 0")
	_expect(find.next() == 2, "second at 2, not 1")


func _an_empty_query_clears_rather_than_matching_everything() -> void:
	var find := ScrollbackFind.new()
	find.search(LOG, "raider")

	_expect(find.search(LOG, "") == 0, "an emptied box finds nothing")
	_expect(find.current() == -1, "and selects nothing")
	_expect(find.next() == -1, "stepping does nothing rather than erroring")


func _no_matches_is_a_state_not_an_error() -> void:
	var find := ScrollbackFind.new()

	_expect(find.search(LOG, "dragon") == 0, "an absent word finds nothing")
	_expect(find.current() == -1, "nothing is selected")
	_expect(find.previous() == -1, "and stepping is safe")
	_expect(find.search("", "raider") == 0, "an empty log finds nothing")


func _status_text_says_what_a_player_needs() -> void:
	# The two states a player actually reads.
	var find := ScrollbackFind.new()

	_expect(find.status_text().is_empty(), "no search shows nothing")

	find.search(LOG, "raider")
	_expect(find.status_text() == "1 / 3", "a live search counts")

	find.next()
	_expect(find.status_text() == "2 / 3", "and follows the selection")

	find.search(LOG, "dragon")
	_expect(find.status_text() == "no matches", "a miss says so")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
