extends Node
## Tests for the Music tab: the colours, the count, the now-playing line,
## and that no click sends a command. A click writes the settings or asks
## the player, and the list redraws from the model alone.
##
##     godot --headless --path godot res://tests/scenes/test_music_tab.tscn

const _Const := preload("res://autoload/blackout_constants.gd")
const _StateTest := preload("res://tests/world/state/test_music_state.gd")

const TEST_PATH := "user://test_music_tab.cfg"

var _failures := 0
var _state: MusicState
var _settings: ClientSettings
var _player: MusicPlayer
var _view: MusicView


func _ready() -> void:
	_clean()
	_state = MusicState.new()
	_settings = ClientSettings.new(TEST_PATH)
	_player = MusicPlayer.new()
	add_child(_player)
	_player.set_draw(func(_count: int) -> int: return 0)
	_player.bind(_state, _settings, "")
	_view = MusicView.new()
	add_child(_view)
	_view.bind(_state, _settings, _player)

	_nothing_is_drawn_before_a_snapshot()

	_state.ingest(_Const.CH_CHAR_MUSIC, _StateTest.payload())

	_a_button_is_drawn_for_every_row()
	_the_count_reads_the_rows()
	_a_locked_row_is_red_disabled_and_carries_its_hint()
	_an_unlocked_row_is_green()
	_the_playing_row_is_blue_and_named()
	_a_click_on_an_unlocked_row_sets_single_mode_with_that_track()
	_the_mode_buttons_follow_the_settings()
	_a_mode_button_writes_the_settings()
	_the_buttons_never_take_the_keyboard()
	_an_empty_list_says_so()

	_clean()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: music_tab")
	get_tree().quit(0)


func _clean() -> void:
	if FileAccess.file_exists(TEST_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(TEST_PATH))


func _expect(condition: bool, message: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("FAIL: %s" % message)


func _button(key_name: String) -> Button:
	for child: Node in _view.track_buttons():
		if child is Button and (child as Button).text == key_name:
			return child

	return null


func _color_of(button: Button) -> Color:
	return button.get_theme_color("font_color")


func _nothing_is_drawn_before_a_snapshot() -> void:
	_expect(_view.track_buttons().size() == 1, "one line before char_music")
	_expect(_view.track_buttons()[0] is Label, "and it is a label, not a row")
	_expect(_view.count_text() == "", "and no count")
	_expect(_view.playing_text() == MusicView.SILENT_TEXT, "and nothing plays")


func _a_button_is_drawn_for_every_row() -> void:
	# Iterate, never enumerate: the rows are built from what arrived.
	var rows: Array = _StateTest.payload()[_Const.MUSIC_ROWS_KEY]

	_expect(_view.track_buttons().size() == rows.size(), "one button for each row")

	for row: Dictionary in rows:
		_expect(_button(str(row["name"])) != null, "a button named %s" % row["name"])


func _the_count_reads_the_rows() -> void:
	_expect(_view.count_text() == MusicView.COUNT_TEXT % [2, 3], "two of three unlocked")


func _a_locked_row_is_red_disabled_and_carries_its_hint() -> void:
	var button := _button("Dune Song")

	_expect(button.disabled, "a locked row cannot be clicked")
	_expect(_color_of(button) == MusicView.COLOR_LOCKED, "and it is red")
	_expect(button.tooltip_text == "Walk the dunes.", "and its hint is its tooltip")


func _an_unlocked_row_is_green() -> void:
	var button := _button("Oasis Calm")

	_expect(not button.disabled, "an unlocked row can be clicked")
	_expect(_color_of(button) == MusicView.COLOR_UNLOCKED, "and it is green")
	_expect(button.tooltip_text == "", "and it shows no hint")


func _the_playing_row_is_blue_and_named() -> void:
	# The player bound with no origin and no stream, so nothing plays yet.
	_expect(_view.playing_text() == MusicView.SILENT_TEXT, "silence before a stream")

	_player.offer_stream("frigid_memory", _silent_stream())
	_expect(_player.playing_key() == "frigid_memory", "the track of the area plays")
	_expect(_view.playing_text() == MusicView.PLAYING_TEXT % "Frigid Memory",
		"the now-playing line names it")
	_expect(_color_of(_button("Frigid Memory")) == MusicView.COLOR_PLAYING,
		"and its row is blue")
	_expect(_color_of(_button("Oasis Calm")) == MusicView.COLOR_UNLOCKED,
		"while the other unlocked row stays green")


func _a_click_on_an_unlocked_row_sets_single_mode_with_that_track() -> void:
	_button("Oasis Calm").pressed.emit()

	_expect(_settings.music_mode == ClientSettings.MUSIC_MODE_SINGLE, "single mode")
	_expect(_settings.music_track == "oasis_calm", "with the clicked track")
	_expect(_view.mode_buttons()[ClientSettings.MUSIC_MODE_SINGLE].button_pressed,
		"and the Single button is lit")


func _the_mode_buttons_follow_the_settings() -> void:
	_settings.set_music_mode(ClientSettings.MUSIC_MODE_SHUFFLE)

	_expect(_view.mode_buttons()[ClientSettings.MUSIC_MODE_SHUFFLE].button_pressed,
		"the Shuffle button lights on the setting")
	_expect(not _view.mode_buttons()[ClientSettings.MUSIC_MODE_SINGLE].button_pressed,
		"and the Single button goes dark")


func _a_mode_button_writes_the_settings() -> void:
	var button: Button = _view.mode_buttons()[ClientSettings.MUSIC_MODE_AREA]

	button.set_pressed_no_signal(true)
	button.pressed.emit()

	_expect(_settings.music_mode == ClientSettings.MUSIC_MODE_AREA,
		"the Area button writes the setting")


func _the_buttons_never_take_the_keyboard() -> void:
	for mode: String in _view.mode_buttons():
		_expect(_view.mode_buttons()[mode].focus_mode == Control.FOCUS_NONE,
			"the %s button takes no focus" % mode)

	_expect(_view.skip_button().focus_mode == Control.FOCUS_NONE, "Skip takes no focus")

	for child: Node in _view.track_buttons():
		_expect((child as Control).focus_mode == Control.FOCUS_NONE,
			"a track row takes no focus")


func _an_empty_list_says_so() -> void:
	_state.ingest(_Const.CH_CHAR_MUSIC, {_Const.MUSIC_ROWS_KEY: []})

	_expect(_view.track_buttons().size() == 1, "one line for an empty list")
	_expect((_view.track_buttons()[0] as Label).text == MusicView.NO_TRACKS_TEXT,
		"and it says the world has no music")
	_expect(_view.count_text() == MusicView.COUNT_TEXT % [0, 0], "and the count is 0 of 0")


static func _silent_stream() -> AudioStream:
	var stream := AudioStreamWAV.new()

	stream.format = AudioStreamWAV.FORMAT_8_BITS
	stream.mix_rate = 8000
	stream.stereo = false

	var data := PackedByteArray()
	data.resize(8000 * 30)
	stream.data = data

	return stream
