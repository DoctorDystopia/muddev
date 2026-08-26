extends Node
## Unit tests for CommandHistory.
##
##     godot --headless --path godot res://tests/test_command_history.tscn

var _failures := 0


func _ready() -> void:
	_walks_back_through_what_was_typed()
	_a_half_typed_draft_survives_browsing()
	_submitting_returns_to_the_end()
	_consecutive_duplicates_collapse()
	_blank_lines_are_not_commands()
	_it_stops_at_the_oldest_entry()
	_it_is_bounded()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: command_history")
	get_tree().quit(0)


func _filled() -> CommandHistory:
	var h := CommandHistory.new()
	h.push("look")
	h.push("north")
	h.push("attack raider")
	return h


func _walks_back_through_what_was_typed() -> void:
	var h := _filled()

	_expect(h.previous("") == "attack raider", "up gives the most recent first")
	_expect(h.previous("") == "north", "then the one before")
	_expect(h.previous("") == "look", "then the oldest")
	_expect(h.next("") == "north", "down walks back toward the present")
	_expect(h.next("") == "attack raider", "and keeps going")


func _a_half_typed_draft_survives_browsing() -> void:
	# The single most irritating bug this class can have.
	var h := _filled()

	_expect(h.previous("get sw") == "attack raider", "browsing away from a draft")
	_expect(h.next("attack raider") == "get sw",
		"coming back restores what was being typed")

	# And browsing several deep still returns to it.
	h.previous("half typed")
	h.previous("")
	h.previous("")
	h.next("")
	h.next("")
	_expect(h.next("") == "half typed", "even from several entries deep")


func _submitting_returns_to_the_end() -> void:
	# Otherwise the next up-arrow jumps somewhere unrelated to where you are.
	var h := _filled()

	h.previous("")
	h.previous("")
	_expect(h.is_browsing(), "browsing after two ups")

	h.push("south")
	_expect(not h.is_browsing(), "submitting puts you back at the end")
	_expect(h.previous("") == "south", "and up gives the command just sent")


func _consecutive_duplicates_collapse() -> void:
	# A history that makes you press up five times to get past your own
	# repetition is worse than no history.
	var h := CommandHistory.new()
	h.push("look")
	h.push("look")
	h.push("look")

	_expect(h.size() == 1, "three identical commands are one entry")

	h.push("north")
	h.push("look")
	_expect(h.size() == 3, "but a repeat that is not consecutive is kept")


func _blank_lines_are_not_commands() -> void:
	var h := CommandHistory.new()
	h.push("look")
	h.push("")
	h.push("   ")

	_expect(h.size() == 1, "blank and whitespace lines are not stored")
	_expect(h.previous("") == "look", "and do not push the real history down")


func _it_stops_at_the_oldest_entry() -> void:
	var h := _filled()

	for i in range(0, 10):
		h.previous("")

	_expect(h.previous("") == "look", "up past the start stays on the oldest")


func _it_is_bounded() -> void:
	# A client left running for a week must not grow without limit.
	var h := CommandHistory.new()

	for i in range(0, CommandHistory.CAPACITY + 50):
		h.push("command %d" % i)

	_expect(h.size() == CommandHistory.CAPACITY, "the buffer is capped")
	_expect(h.previous("") == "command %d" % (CommandHistory.CAPACITY + 49),
		"and it is the OLD entries that were dropped")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
