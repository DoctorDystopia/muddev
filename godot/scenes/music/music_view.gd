class_name MusicView
extends Control
## The Music tab: the mode, the track that plays, and every track with its
## state, drawn from [MusicState] and [MusicPlayer] (DESIGN-0016).
##
## Presentation only, and it names no track. Every row comes from whatever
## `char_music` contained, so a track that the sound wizard adds on the
## server appears here with no edit. The contract [QuestsView] answers for
## quests.
##
## ## No click here sends a command
##
## The play is a look. A mode button writes [member ClientSettings.music_mode],
## Skip calls [method MusicPlayer.skip], and a click on an unlocked row sets
## Single mode with that track. The server owns the list, and the list
## arrives on its own. Thus, this pane and the telnet `music` listing can
## never disagree on what a player holds.
##
## ## The colours are the OSRS ones
##
## Red is locked, green is unlocked, blue is the track that plays. A locked
## row shows its hint on hover, and a click on it does nothing.
##
## Author: Nick Hobar
## Creation date: 11/08/2026

## Shown before char_music has ever arrived. Distinguished from a world
## with no track, which is a real and different thing.
const NO_DATA_TEXT := "No music list yet."

## Shown when the server has answered and the answer is nothing.
const NO_TRACKS_TEXT := "The world has no music yet."

## The now-playing line, and its text when nothing plays.
const PLAYING_TEXT := "Now playing: %s"
const SILENT_TEXT := "Now playing: nothing"

## The count line.
const COUNT_TEXT := "%d of %d unlocked"

## The labels of the mode buttons, in the order of [constant
## ClientSettings.MUSIC_MODES].
const MODE_LABELS := {
	ClientSettings.MUSIC_MODE_AREA: "Area",
	ClientSettings.MUSIC_MODE_SHUFFLE: "Shuffle",
	ClientSettings.MUSIC_MODE_SINGLE: "Single",
}

const SKIP_LABEL := "Skip"

const COLOR_LOCKED := Color("d04b4b")
const COLOR_UNLOCKED := Color("4caf50")
const COLOR_PLAYING := Color("5aa9ff")

var _state: MusicState
var _settings: ClientSettings
var _player: MusicPlayer

var _mode_buttons: Dictionary = {}
var _skip: Button
var _playing: Label
var _count: Label
var _list: VBoxContainer


func _init() -> void:
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.theme_type_variation = &"PaneMargin"
	add_child(margin)

	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.theme_type_variation = &"FormColumn"
	margin.add_child(column)

	column.add_child(_mode_row())

	_playing = _label(SILENT_TEXT, &"RowKey")
	_playing.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_playing)

	_count = _label("", &"RowKey")
	column.add_child(_count)

	column.add_child(HSeparator.new())

	var scroller := ScrollContainer.new()
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroller.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(scroller)

	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroller.add_child(_list)


## Bind to the model, the settings, and the player, and follow the three.
func bind(state: MusicState, settings: ClientSettings, player: MusicPlayer) -> void:
	_state = state
	_settings = settings
	_player = player

	_state.changed.connect(_rebuild)
	_settings.changed.connect(_sync_modes)
	_player.playing_changed.connect(_on_playing_changed)

	_sync_modes()
	_rebuild()


## The button of each mode, keyed by the mode. For a test.
func mode_buttons() -> Dictionary:
	return _mode_buttons


## The Skip button. For a test.
func skip_button() -> Button:
	return _skip


## One button for each track row, in the order of the list. For a test.
func track_buttons() -> Array:
	return _list.get_children()


## The now-playing line. For a test.
func playing_text() -> String:
	return _playing.text


## The count line. For a test.
func count_text() -> String:
	return _count.text


func _mode_row() -> Control:
	var row := HBoxContainer.new()
	var group := ButtonGroup.new()

	for mode: String in ClientSettings.MUSIC_MODES:
		var button := Button.new()

		button.text = MODE_LABELS[mode]
		button.toggle_mode = true
		button.button_group = group
		# FOCUS_NONE for the rule the tab strip follows: focus is the
		# mode in this client, and a button must not take the keyboard.
		button.focus_mode = Control.FOCUS_NONE
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.pressed.connect(_on_mode_pressed.bind(mode))
		row.add_child(button)
		_mode_buttons[mode] = button

	_skip = Button.new()
	_skip.text = SKIP_LABEL
	_skip.focus_mode = Control.FOCUS_NONE
	_skip.pressed.connect(_on_skip_pressed)
	row.add_child(_skip)

	return row


## Light the button of the mode that the settings hold. The click of a
## button writes the settings, and this follows the write, so a refused
## mode stays dark.
func _sync_modes() -> void:
	if _settings == null:
		return

	for mode: String in _mode_buttons:
		var button: Button = _mode_buttons[mode]

		button.set_pressed_no_signal(mode == _settings.music_mode)


func _on_mode_pressed(mode: String) -> void:
	_settings.set_music_mode(mode)


func _on_skip_pressed() -> void:
	_player.skip()


func _on_playing_changed(_key: String) -> void:
	_rebuild()


## Rebuild wholesale, the way the quest log does. `char_music` is a
## snapshot, so throwing every row away and making them again is the only
## approach that cannot desync from it.
func _rebuild() -> void:
	if _state == null:
		return

	for child: Node in _list.get_children():
		_list.remove_child(child)
		child.free()

	_playing.text = _playing_line()

	if not _state.has_data:
		_count.text = ""
		_list.add_child(_label(NO_DATA_TEXT, &"RowKey"))
		return

	_count.text = COUNT_TEXT % [_state.unlocked_count(), _state.rows.size()]

	if _state.rows.is_empty():
		_list.add_child(_label(NO_TRACKS_TEXT, &"RowKey"))
		return

	for row: Dictionary in _state.rows:
		_list.add_child(_track_button(row))


func _playing_line() -> String:
	if _player == null or _player.playing_key().is_empty():
		return SILENT_TEXT

	var row := _state.row_for(_player.playing_key())

	if row.is_empty():
		return SILENT_TEXT

	return PLAYING_TEXT % str(row["name"])


## One track as a flat button. An unlocked row starts the track in Single
## mode on a click. A locked row is disabled, and its hint is its tooltip.
func _track_button(row: Dictionary) -> Button:
	var button := Button.new()
	var key := str(row["key"])
	var unlocked := _state.is_unlocked(key)

	button.text = str(row["name"])
	button.flat = true
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.focus_mode = Control.FOCUS_NONE
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.add_theme_color_override("font_color", _row_color(key, unlocked))
	button.add_theme_color_override("font_disabled_color", COLOR_LOCKED)
	button.add_theme_color_override("font_hover_color", _row_color(key, unlocked))

	if unlocked:
		button.pressed.connect(_on_track_pressed.bind(key))
	else:
		button.disabled = true
		button.tooltip_text = str(row["hint"])

	return button


func _row_color(key: String, unlocked: bool) -> Color:
	if not unlocked:
		return COLOR_LOCKED

	if _player != null and _player.playing_key() == key:
		return COLOR_PLAYING

	return COLOR_UNLOCKED


func _on_track_pressed(key: String) -> void:
	_settings.set_music_mode(ClientSettings.MUSIC_MODE_SINGLE, key)


func _label(text: String, variation: StringName) -> Label:
	var label := Label.new()
	label.text = text
	label.theme_type_variation = variation

	return label
