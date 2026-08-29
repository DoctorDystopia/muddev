extends Node
## Unit tests for OptionsView.
##
##     godot --headless --path godot res://tests/test_options_view.tscn
##
## Needs nothing running.
##
## Two kinds of control live in this pane and they must not be confused. The
## sliders and checkboxes are the PLAYER's and are written to [ClientSettings];
## the Game buttons are the SERVER's and can only ask. A control that wrote a
## server setting locally would show the player a preference the game does not
## have.

const TEST_PATH := "user://test_options_view.cfg"

var _failures := 0
var _settings: ClientSettings
var _view: OptionsView


func _ready() -> void:
	_clean()

	_a_client_setting_is_written_locally()
	_a_game_setting_is_only_ever_asked_for()
	_every_command_button_sends_a_whole_line()
	_the_skill_detail_choice_offers_every_mode_and_stores_the_value()

	_clean()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: options_view")
	get_tree().quit(0)


func _clean() -> void:
	if FileAccess.file_exists(TEST_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(TEST_PATH))


func _fresh() -> void:
	if _view != null:
		_view.queue_free()

	_clean()
	_settings = ClientSettings.new(TEST_PATH)
	_view = OptionsView.new()
	add_child(_view)
	_view.bind(_settings)


## Every Button under the view, deepest last.
func _buttons(node: Node, into: Array[Button]) -> Array[Button]:
	if node is Button:
		into.append(node as Button)

	for child: Node in node.get_children():
		_buttons(child, into)

	return into


func _a_client_setting_is_written_locally() -> void:
	# Font size is the player's and the server never hears about it.
	_fresh()
	_settings.set_font_size(20)

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()

	_expect(reloaded.font_size == 20, "a client setting is saved to disk")


func _a_game_setting_is_only_ever_asked_for() -> void:
	# The pane cannot write a server setting. It emits the line a telnet player
	# would type, and the server decides -- the same contract a clicked tile
	# and an inventory drag answer.
	_fresh()

	var sent: Array[String] = []
	_view.command_requested.connect(func(line): sent.append(line))

	for button: Button in _buttons(_view, [] as Array[Button]):
		if button.text == "Off":
			button.pressed.emit()

	_expect(sent.size() == 1, "pressing Off sent exactly one line")
	_expect(sent.size() == 1 and sent[0] == "automap off",
		"and it was the whole command, composed nowhere")


func _every_command_button_sends_a_whole_line() -> void:
	# A button that sent a fragment would need the console to finish it, which
	# is the privileged path this client does not have.
	_fresh()

	var sent: Array[String] = []
	_view.command_requested.connect(func(line): sent.append(line))

	for button: Button in _buttons(_view, [] as Array[Button]):
		button.pressed.emit()

	_expect(not sent.is_empty(), "the pane has command buttons at all")

	for line: String in sent:
		if line.strip_edges().is_empty() or line.contains("{"):
			_fail("%s is not a whole command" % line)
			return

	_expect(sent.has("automap"), "including the one that just asks")
	_expect(sent.has("automap on"), "and the one that turns the map back on")


func _the_skill_detail_choice_offers_every_mode_and_stores_the_value() -> void:
	# The items are built by walking ClientSettings.SKILL_DETAIL_MODES, so what
	# is STORED comes back out of that array by index rather than off the
	# label -- which is what keeps the saved setting independent of what the
	# option is called on screen.
	_fresh()

	var picker: OptionButton = _view._skill_detail

	_expect(picker.item_count == ClientSettings.SKILL_DETAIL_MODES.size(),
		"every mode is offered, and only the modes")

	for index: int in picker.item_count:
		var mode: String = ClientSettings.SKILL_DETAIL_MODES[index]

		picker.item_selected.emit(index)

		_expect(_settings.skill_detail == mode,
			"choosing item %d stores %s" % [index, mode])
		_expect(not picker.get_item_text(index).is_empty(),
			"and it has something to read on screen")

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()

	_expect(reloaded.skill_detail == _settings.skill_detail,
		"and the choice survives a reload")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_fail(what)


func _fail(what: String) -> void:
	_failures += 1
	printerr("  FAIL %s" % what)
