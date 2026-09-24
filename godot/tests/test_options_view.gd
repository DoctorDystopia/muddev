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
	_the_sfx_slider_writes_the_volume_and_follows_it()
	_the_xp_tracker_checks_write_settings_and_reset_only_asks()
	_the_movement_check_writes_the_setting_and_follows_it()
	_the_credits_button_asks_for_the_box_and_sends_no_command()

	_clean()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: options_view")
	get_tree().quit(0)


func _the_credits_button_asks_for_the_box_and_sends_no_command() -> void:
	# The credits box is the client's own. A button that sent a line would
	# ask the server for a screen it does not have.
	_fresh()

	var asked := [0]
	var sent: Array[String] = []
	_view.credits_requested.connect(func(): asked[0] += 1)
	_view.command_requested.connect(func(line): sent.append(line))

	for button: Button in _buttons(_view, [] as Array[Button]):
		if button.text == "Model credits":
			button.pressed.emit()

	_expect(asked[0] == 1, "the credits button asks for the box once")
	_expect(sent.is_empty(), "and sends the server nothing")


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
	var pressed := [0]
	_view.command_requested.connect(func(line): sent.append(line))

	for button: Button in _buttons(_view, [] as Array[Button]):
		if button.text == "Off":
			pressed[0] += 1
			button.pressed.emit()

	_expect(pressed[0] > 0 and sent.size() == pressed[0],
		"each Off press sent exactly one line")
	_expect(sent.has("automap off"),
		"and the automap one was the whole command, composed nowhere")

	# One Off for each part of the room text, and each names its part.
	for part: String in OptionsView.MOVE_TEXT_LABELS:
		_expect(sent.has("movetext %s off" % part),
			"Off for %s sends the whole movetext line" % part)


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
	_expect(sent.has("toggle craft confirm"),
		"and the crafting confirmation toggle")
	_expect(sent.has("movetext"), "and the room text report")
	_expect(sent.has("movetext reset"), "and the room text reset")


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


func _the_sfx_slider_writes_the_volume_and_follows_it() -> void:
	# The slider writes through ClientSettings like every other client control,
	# and follows `changed` -- so Reset to defaults moves it back as well.
	_fresh()

	var slider: HSlider = _view._sfx_slider
	var readout: Label = _view._sfx_value

	_expect(is_equal_approx(slider.max_value, ClientSettings.MAX_SFX_VOLUME),
		"the slider's bounds come from ClientSettings")

	slider.value = 0.4

	_expect(is_equal_approx(_settings.sfx_volume, 0.4),
		"dragging the slider stores the volume")
	_expect(readout.text == "40%", "and reads it as a percentage")

	_settings.set_sfx_volume(0.0)

	_expect(is_equal_approx(slider.value, 0.0),
		"a volume set elsewhere moves the slider")
	_expect(readout.text == "0%", "and its readout")

	_settings.reset()

	_expect(is_equal_approx(slider.value, ClientSettings.DEFAULT_SFX_VOLUME),
		"and Reset to defaults puts it back")


func _the_xp_tracker_checks_write_settings_and_reset_only_asks() -> void:
	# The two checks are the player's and write ClientSettings. Reset session is
	# neither a setting nor a command: it asks the console, and sends nothing.
	_fresh()

	var resets := {"n": 0}
	var sent: Array[String] = []
	_view.xp_session_reset_requested.connect(func(): resets["n"] += 1)
	_view.command_requested.connect(func(line): sent.append(line))

	_expect(_view._xp_drops_check.button_pressed,
		"the drops check starts on, as the default is")

	_view._xp_drops_check.toggled.emit(false)
	_expect(not _settings.show_xp_drops, "unticking it hides the drops")
	_expect(_view._skill_rates_check.disabled,
		"and per-skill rates cannot be asked for on a hidden tracker")

	_view._skill_rates_check.toggled.emit(true)
	_expect(_settings.show_skill_rates, "ticking per-skill rates stores it")

	for button: Button in _buttons(_view, [] as Array[Button]):
		if button.text == "Reset session":
			button.pressed.emit()

	_expect(resets["n"] == 1, "Reset session asks once")
	_expect(sent.is_empty(), "and sends the server nothing")


## The player's, like every check above the Game heading: it writes
## ClientSettings and the server never hears about it. And it FOLLOWS the
## setting, because Reset to defaults writes the same field from another
## control -- a check that only ever wrote would then show the wrong state.
func _the_movement_check_writes_the_setting_and_follows_it() -> void:
	_fresh()

	var sent: Array[String] = []
	_view.command_requested.connect(func(line): sent.append(line))

	_expect(_view._smooth_movement_check.button_pressed,
		"the movement check starts on, as the default is")

	_view._smooth_movement_check.toggled.emit(false)

	_expect(not _settings.smooth_movement, "unticking it stops the animation")
	_expect(sent.is_empty(), "and asks the server for nothing")

	_settings.reset()

	_expect(_view._smooth_movement_check.button_pressed,
		"and a reset elsewhere ticks it again")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_fail(what)


func _fail(what: String) -> void:
	_failures += 1
	printerr("  FAIL %s" % what)
