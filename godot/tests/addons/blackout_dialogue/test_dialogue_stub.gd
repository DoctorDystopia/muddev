extends Node
## Unit tests for the editor side of a dialogue script (DESIGN-0017): the
## generated stub ([DialogueStub]), the list of yes or no queries
## ([DialogueStubCalls]), the runtime of Dialogue Manager on a real script of
## the game, and the test scene of the Dialogue tab.
##
##     godot --headless --path godot res://tests/addons/blackout_dialogue/test_dialogue_stub.tscn
##
## The real script is the Clinic recruiter. The cases read its queries from
## the script, so a new line there breaks no case.

const SCRIPT_PATH := "res://dialogue/aug_clinic_1.dialogue"
const TEST_SCENE := "res://addons/blackout_dialogue/dialogue_test_scene.tscn"
const ANSWERS_PATH := "user://test_blackout_dialogue_test.json"

## The keys of the user config of the addon that the Run button writes.
const RUN_PATH_KEY := "run_resource_path"
const RUN_CUE_KEY := "run_key"

var _failures := 0


func _ready() -> void:
	_clean()

	_a_flag_is_false_until_the_author_sets_it()
	_a_text_gives_its_call_in_angle_brackets()
	_a_value_reads_with_no_brackets()
	_an_action_only_records_its_call()
	_each_name_of_the_table_is_a_member()
	_the_script_lists_each_flag_call_one_time()
	_the_switches_of_a_script_survive_a_new_run()
	await _the_runtime_of_the_addon_runs_the_script()
	await _a_switch_changes_the_path_of_the_script()
	await _the_test_scene_shows_one_switch_for_each_query()

	_clean()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: dialogue_stub")
	get_tree().quit(0)


func _a_flag_is_false_until_the_author_sets_it() -> void:
	var stub := DialogueStub.new()
	var asked := DialogueStub.call_text("quest.is_active", ["some_quest"])

	_expect(asked == "quest.is_active(\"some_quest\")", "the call text: %s" % asked)
	_expect(stub.quest.is_active("some_quest") == false, "a flag starts false")

	stub.answers[asked] = true

	_expect(stub.quest.is_active("some_quest") == true, "a set flag is true")
	_expect(stub.quest.is_active("other_quest") == false,
		"a flag of different arguments stays false")


func _a_text_gives_its_call_in_angle_brackets() -> void:
	var stub := DialogueStub.new()

	_expect(stub.quest.title("some_quest") == "<quest.title(\"some_quest\")>",
		"a text shows its call")


func _a_value_reads_with_no_brackets() -> void:
	var stub := DialogueStub.new()

	_expect(stub.npc.name == "<npc.name>", "a value shows its name")

	stub.answers["npc.name"] = "Guard"

	_expect(stub.npc.name == "Guard", "a value takes the answer of the author")


func _an_action_only_records_its_call() -> void:
	var stub := DialogueStub.new()

	stub.quest.accept("some_quest")

	_expect(stub.actions.size() == 1
		and stub.actions[0] == "quest.accept(\"some_quest\")",
		"the action is in the list: %s" % [stub.actions])
	_expect(stub.quest.is_active("some_quest") == false,
		"an action changes no answer")


## The table of the stub and its members come from one render. This case
## finds a member that the render lost.
func _each_name_of_the_table_is_a_member() -> void:
	var stub := DialogueStub.new()

	for name: String in DialogueStub.KINDS:
		var bits := name.split(".")
		var namespace_object: Object = stub.get(bits[0])
		var is_member: bool = namespace_object != null \
			and (namespace_object.has_method(bits[1]) or bits[1] in namespace_object)

		_expect(is_member, "the stub has the member %s" % name)


func _the_script_lists_each_flag_call_one_time() -> void:
	var calls := DialogueStubCalls.flag_calls(_script().lines)
	var unique := {}

	for asked: String in calls:
		unique[asked] = true

		var name := asked.get_slice("(", 0)

		_expect(DialogueStub.KINDS.get(name) == DialogueStub.KIND_FLAG,
			"%s is a flag of the stub" % asked)

	_expect(not calls.is_empty(), "the script asks some query")
	_expect(unique.size() == calls.size(), "no call is in the list two times")


func _the_switches_of_a_script_survive_a_new_run() -> void:
	var scene_script: Script = load(TEST_SCENE.get_basename() + ".gd")

	scene_script.save_answers("res://a.dialogue", {"x": true}, ANSWERS_PATH)
	scene_script.save_answers("res://b.dialogue", {"y": true}, ANSWERS_PATH)

	_expect(scene_script.saved_answers("res://a.dialogue", ANSWERS_PATH) == {"x": true},
		"the switches of one script come back")
	_expect(scene_script.saved_answers("res://c.dialogue", ANSWERS_PATH).is_empty(),
		"a script with no saved switch gets none")


func _the_runtime_of_the_addon_runs_the_script() -> void:
	var stub := DialogueStub.new()
	var line: DialogueLine = await _manager().get_next_dialogue_line(
		_script(), "start", [stub])

	_expect(line != null, "the runtime gives a first line")

	if line == null:
		return

	_expect(line.text.contains("<npc.header>"),
		"the first line holds the header of the stub: %s" % line.text)


## With each flag false, the script greets. With each flag true, its first
## branch runs, so the first line is a different line.
func _a_switch_changes_the_path_of_the_script() -> void:
	var plain := DialogueStub.new()
	var switched := DialogueStub.new()

	for asked: String in DialogueStubCalls.flag_calls(_script().lines):
		switched.answers[asked] = true

	var first: DialogueLine = await _manager().get_next_dialogue_line(
		_script(), "start", [plain])
	var other: DialogueLine = await _manager().get_next_dialogue_line(
		_script(), "start", [switched])

	_expect(first != null and other != null, "both runs give a line")

	if first == null or other == null:
		return

	_expect(first.text != other.text,
		"the switches change the first line: %s" % other.text)


func _the_test_scene_shows_one_switch_for_each_query() -> void:
	var old_path: Variant = DMSettings.get_user_value(RUN_PATH_KEY, "")
	var old_cue: Variant = DMSettings.get_user_value(RUN_CUE_KEY, "")

	DMSettings.set_user_value(RUN_PATH_KEY, SCRIPT_PATH)
	DMSettings.set_user_value(RUN_CUE_KEY, "start")

	var scene: Node = load(TEST_SCENE).instantiate()

	scene.answers_path = ANSWERS_PATH
	add_child(scene)

	await get_tree().process_frame
	await get_tree().process_frame

	var switches := scene.find_children("*", "CheckBox", true, false)
	var calls := DialogueStubCalls.flag_calls(_script().lines)

	_expect(switches.size() == calls.size(),
		"one switch for each query: %d of %d" % [switches.size(), calls.size()])

	if not switches.is_empty():
		var first: CheckBox = switches[0]

		first.button_pressed = true

		var saved: Dictionary = scene.saved_answers(SCRIPT_PATH, ANSWERS_PATH)

		_expect(saved.get(first.text) == true, "a switch goes into the file")

	scene.queue_free()

	await get_tree().process_frame

	DMSettings.set_user_value(RUN_PATH_KEY, old_path)
	DMSettings.set_user_value(RUN_CUE_KEY, old_cue)
	DMSettings.set_user_value("is_running_test_scene", false)


func _script() -> DialogueResource:
	return load(SCRIPT_PATH)


func _manager() -> Node:
	return Engine.get_singleton("DialogueManager")


func _clean() -> void:
	if FileAccess.file_exists(ANSWERS_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(ANSWERS_PATH))


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  FAIL: %s" % what)
