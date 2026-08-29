extends Node
## Unit tests for QuestState and the quest log it feeds.
##
##     godot --headless --path godot res://tests/test_quest_state.tscn
##
## Needs nothing running. Payloads are hand-built in the shape Godot's JSON
## parser actually produces -- every number a float -- because that boundary is
## where this model earns its keep.

const Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_it_only_wants_its_own_channel()
	_no_data_is_not_the_same_as_no_quests()
	_the_float_boundary_is_crossed_once()
	_a_one_shot_objective_is_told_apart_from_a_counted_one()
	_a_malformed_payload_does_not_take_the_client_with_it()
	_step_fraction_counts_what_is_done()
	_a_dropped_socket_clears_the_log()
	_the_view_draws_whatever_it_was_sent()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: quest_state")
	get_tree().quit(0)


## One quest, one step, both kinds of objective -- as floats.
func _payload() -> Dictionary:
	return {
		"active": [{
			"key": "testquest",
			"title": "Test Quest",
			"step": "intro",
			"step_description": "Speak to the tester and cull three rats.",
			"objectives": [
				{
					"key": "talk:tester",
					"description": "Speak to the tester",
					"current": 1.0,
					"required": 1.0,
					"counted": false,
					"done": true,
				},
				{
					"key": "kill:rat",
					"description": "Rats culled",
					"current": 2.0,
					"required": 3.0,
					"counted": true,
					"done": false,
				},
			],
		}],
		"completed": [{"key": "prologue", "title": "Prologue"}],
	}


func _it_only_wants_its_own_channel() -> void:
	# The console offers every payload to every model in turn, so a model that
	# claimed one that was not its own would swallow it.
	var log := QuestState.new()

	_expect(log.ingest(Const.CH_CHAR_QUESTS, _payload()), "it takes char_quests")
	_expect(not log.ingest(Const.CH_CHAR_VITALS, {"hp": 1.0}),
		"and declines a channel that is not its own")


func _no_data_is_not_the_same_as_no_quests() -> void:
	# A player who has just logged in has been told nothing; one who has taken
	# nothing has been told that. The pane says different things for each.
	var log := QuestState.new()

	_expect(not log.has_data, "a fresh log has heard nothing")

	log.ingest(Const.CH_CHAR_QUESTS, {"active": [], "completed": []})

	_expect(log.has_data, "an empty answer is still an answer")
	_expect(log.active.is_empty(), "and it holds no quests")


func _the_float_boundary_is_crossed_once() -> void:
	# JSON.parse_string returns 3.0, always. "%d/%d" on a float is not what it
	# looks like, and a dictionary keyed on one silently misses.
	var log := QuestState.new()
	log.ingest(Const.CH_CHAR_QUESTS, _payload())

	var objective: Dictionary = log.active[0]["objectives"][1]

	_expect(typeof(objective["current"]) == TYPE_INT, "current is an int")
	_expect(typeof(objective["required"]) == TYPE_INT, "required is an int")
	_expect(objective["current"] == 2 and objective["required"] == 3,
		"and both carry the server's numbers")


func _a_one_shot_objective_is_told_apart_from_a_counted_one() -> void:
	var log := QuestState.new()
	log.ingest(Const.CH_CHAR_QUESTS, _payload())

	var objectives: Array = log.active[0]["objectives"]

	_expect(not objectives[0]["counted"], "a one-shot objective is not counted")
	_expect(objectives[0]["required"] == 1,
		"but still reports a requirement of one, so a bar needs no branch")
	_expect(objectives[1]["counted"], "and a counted one says so")


func _a_malformed_payload_does_not_take_the_client_with_it() -> void:
	# Nothing on the wire is guaranteed. A quest log that crashed the client
	# would be worse than one that drew nothing.
	var log := QuestState.new()

	log.ingest(Const.CH_CHAR_QUESTS, {"active": "not a list"})
	_expect(log.active.is_empty(), "a non-list of quests is read as none")

	log.ingest(Const.CH_CHAR_QUESTS, {
		"active": [{"key": "q", "objectives": [7, "nonsense"]}],
	})
	_expect(log.active.size() == 1, "the quest survives")
	_expect(log.active[0]["objectives"].is_empty(),
		"and its unreadable objectives are dropped rather than drawn")

	log.ingest(Const.CH_CHAR_QUESTS, {
		"active": [{"key": "q", "objectives": [{"required": 0.0}]}],
	})
	_expect(log.active[0]["objectives"][0]["required"] == 1,
		"a requirement of zero is floored, so nothing divides by it")


func _step_fraction_counts_what_is_done() -> void:
	var log := QuestState.new()
	log.ingest(Const.CH_CHAR_QUESTS, _payload())

	_expect(is_equal_approx(QuestState.step_fraction(log.active[0]), 0.5),
		"one of two objectives done is half a step")
	_expect(is_equal_approx(QuestState.step_fraction({}), 1.0),
		"a step that asks for nothing reads as complete")


func _a_dropped_socket_clears_the_log() -> void:
	# A websocket close ends the Evennia Session, so what this held describes a
	# character nobody is puppeting any more.
	var log := QuestState.new()
	log.ingest(Const.CH_CHAR_QUESTS, _payload())
	log.reset()

	_expect(not log.has_data and log.active.is_empty(),
		"reset forgets everything")


func _the_view_draws_whatever_it_was_sent() -> void:
	# It names no quest and must not learn any: adding a quest is one file under
	# systems/quests/content/, and a table here would be what goes stale.
	var log := QuestState.new()
	var view := QuestsView.new()
	add_child(view)
	view.bind(log)

	var before := _text_of(view)
	_expect(before.contains(QuestsView.NO_DATA_TEXT),
		"before the server answers it says so")

	log.ingest(Const.CH_CHAR_QUESTS, _payload())

	var after := _text_of(view)
	_expect(after.contains("Test Quest"), "the quest's title is drawn")
	_expect(after.contains("Rats culled"), "and each objective's description")
	_expect(after.contains("2/3"), "a counted objective reads as a fraction")
	_expect(after.contains("[x]"), "and a finished one-shot one as a tick")
	_expect(after.contains("Prologue"), "completed quests are listed too")

	view.queue_free()


## Every Label in a view, joined. Enough to assert what a player would read.
func _text_of(node: Node) -> String:
	var found := ""

	if node is Label:
		found += (node as Label).text + "\n"

	for child: Node in node.get_children():
		found += _text_of(child)

	return found


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
