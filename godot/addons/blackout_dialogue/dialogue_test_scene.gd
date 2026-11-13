extends Node2D
## The test scene of the Dialogue tab (DESIGN-0017). The Run button of
## Dialogue Manager opens it, through the project setting
## `dialogue_manager/editor/advanced/custom_test_scene_path`.
##
## The server runs each dialogue script of the game. This scene runs one in
## the editor with no server, so an author can read the flow before a save
## reaches the game:
##
## - [DialogueStub] stands for the dialogue vocabulary. It reads no game.
## - The panel shows one switch for each yes or no query that the script
##   asks ([DialogueStubCalls]). The author sets the state of the player
##   with them: "the quest is active", "the player is on the report step".
## - The panel lists each action that the script ran.
## - "Restart" starts the script again at the cue of the Run button, with
##   the switches as they are.
##
## The scene keeps the switches of each script in a file outside the repo,
## so the author sets them one time.
##
## The runtime of the addon decides the order of `and` and `or`, and the
## server copies that order. Each other rule of the server is in the server
## check, which runs at each save. This scene does not run that check.

## The switches of each script: `{resource path: {call text: bool}}`.
const ANSWERS_PATH := "user://blackout_dialogue_test.json"

## The layer of the panel. The example balloon of the addon uses 100.
const PANEL_LAYER := 101

const PANEL_MARGIN := 12
const PANEL_WIDTH := 420

const TITLE_TEXT := "Dialogue test: %s"
const NO_QUERY_TEXT := "This script asks no yes or no query."
const ACTIONS_TITLE := "Actions that the script ran:"
const NO_ACTION_TEXT := "(none yet)"
const ENDED_TEXT := "The conversation ended. Press Restart."
const RESTART_TEXT := "Restart"

## The file of the switches. A test gives a disposable path.
var answers_path := ANSWERS_PATH

var _stub := DialogueStub.new()
var _resource: DialogueResource
var _cue := ""
var _balloon: Node
var _actions_label: Label
var _status_label: Label

## The count of actions that the label shows. The label follows the stub.
var _shown_actions := -1


func _enter_tree() -> void:
	DMSettings.set_user_value("is_running_test_scene", false)


func _ready() -> void:
	_resource = load(DMSettings.get_user_value("run_resource_path"))
	_cue = DMSettings.get_user_value("run_key", "")

	if _cue.is_empty():
		_cue = _resource.first_cue

	_stub.answers.merge(saved_answers(_resource.resource_path, answers_path), true)
	_build_panel(DialogueStubCalls.flag_calls(_resource.lines))
	_manager().dialogue_ended.connect(_on_dialogue_ended)
	_start()


func _process(_delta: float) -> void:
	if _shown_actions == _stub.actions.size():
		return

	_shown_actions = _stub.actions.size()
	_actions_label.text = NO_ACTION_TEXT if _stub.actions.is_empty() \
		else "\n".join(_stub.actions)


## The switches that the file keeps for one script.
static func saved_answers(resource_path: String, path := ANSWERS_PATH) -> Dictionary:
	var all := _all_answers(path)

	if not all.get(resource_path) is Dictionary:
		return {}

	return all[resource_path]


## The whole file of the switches: `{resource path: {call text: bool}}`.
## Empty when no file exists yet, or when the file is not that shape.
static func _all_answers(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}

	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))

	if not parsed is Dictionary:
		return {}

	return parsed


## Keep the switches of one script in the file. The switches of each other
## script stay.
static func save_answers(resource_path: String, answers: Dictionary,
		path := ANSWERS_PATH) -> void:
	var all := _all_answers(path)

	all[resource_path] = answers

	var file := FileAccess.open(path, FileAccess.WRITE)

	file.store_string(JSON.stringify(all, "\t"))
	file.close()


## The addon registers its autoload under this name. `get_singleton` works
## also before the plugin is on, as the test scene of the addon says.
func _manager() -> Node:
	return Engine.get_singleton("DialogueManager")


func _start() -> void:
	if is_instance_valid(_balloon):
		_balloon.queue_free()

	_stub.actions.clear()
	_status_label.text = ""
	_balloon = _manager().show_dialogue_balloon(_resource, _cue, [_stub])


func _build_panel(calls: Array[String]) -> void:
	var layer := CanvasLayer.new()
	var panel := PanelContainer.new()
	var margin := MarginContainer.new()
	var box := VBoxContainer.new()

	layer.layer = PANEL_LAYER
	panel.position = Vector2(PANEL_MARGIN, PANEL_MARGIN)
	panel.custom_minimum_size.x = PANEL_WIDTH

	for side: String in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, PANEL_MARGIN)

	add_child(layer)
	layer.add_child(panel)
	panel.add_child(margin)
	margin.add_child(box)

	box.add_child(_label(TITLE_TEXT % _resource.resource_path.get_file()))

	if calls.is_empty():
		box.add_child(_label(NO_QUERY_TEXT))

	for query: String in calls:
		box.add_child(_switch(query))

	var restart := Button.new()

	restart.text = RESTART_TEXT
	restart.pressed.connect(_start)
	box.add_child(restart)
	box.add_child(_label(ACTIONS_TITLE))

	_actions_label = _label(NO_ACTION_TEXT)
	_status_label = _label("")
	box.add_child(_actions_label)
	box.add_child(_status_label)


func _label(text: String) -> Label:
	var label := Label.new()

	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART

	return label


## One switch for one yes or no query. Its text is the call, as the author
## wrote it in the script.
func _switch(query: String) -> CheckBox:
	var box := CheckBox.new()

	box.text = query
	box.button_pressed = bool(_stub.answers.get(query, false))
	box.toggled.connect(_on_switch_toggled.bind(query))

	return box


func _on_switch_toggled(pressed: bool, query: String) -> void:
	_stub.answers[query] = pressed
	save_answers(_resource.resource_path, _stub.answers, answers_path)


func _on_dialogue_ended(_ended: DialogueResource) -> void:
	_status_label.text = ENDED_TEXT
