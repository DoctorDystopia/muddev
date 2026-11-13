extends Node
## Unit tests for MusicPlayer: the pick rules, the fade, the gap, and the
## silence. No network. Each case gives its streams to offer_stream as a
## long silent WAV, and a test callable stands in for the random source.
##
##     godot --headless --path godot res://tests/world/sound/test_music_player.tscn
##
## Headless runs on the dummy audio driver, so each track plays for real
## with no speaker attached.

const _Const := preload("res://autoload/blackout_constants.gd")
const _StateTest := preload("res://tests/world/state/test_music_state.gd")

const TEST_PATH := "user://test_music_player.cfg"

## A long silent stream, so no track ends on the clock during a case.
const STREAM_SECONDS := 30.0
const SAMPLE_RATE := 8000

var _failures := 0
var _state: MusicState
var _settings: ClientSettings
var _player: MusicPlayer
var _playing: Array[String] = []


func _ready() -> void:
	_clean()

	_nothing_plays_before_a_snapshot()
	_the_first_snapshot_starts_a_track_of_the_area_at_once()
	_a_locked_track_never_plays()
	_an_area_with_no_unlocked_track_is_silence()
	_a_new_area_blends_to_a_track_of_that_area()
	_the_track_of_the_new_area_keeps_playing_across_its_border()
	_area_mode_never_repeats_the_last_pick_while_another_exists()
	_shuffle_draws_from_every_unlocked_track()
	_single_loops_its_track_and_ends_in_no_gap()
	_a_track_that_ends_picks_the_next_after_the_gap()
	_skip_ends_the_track_with_the_fade()
	_a_track_that_is_not_here_yet_starts_when_it_arrives()
	_an_unlock_starts_music_in_a_silent_area()
	_a_reset_stops_everything()
	_the_url_names_the_served_file()

	_clean()

	# The next mix of the AudioServer releases a stopped playback. See
	# test_sound_cues.gd on the wait.
	await get_tree().create_timer(0.25).timeout

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: music_player")
	get_tree().quit(0)


func _clean() -> void:
	if FileAccess.file_exists(TEST_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(TEST_PATH))


func _expect(condition: bool, message: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("FAIL: %s" % message)


## A fresh player, settings, and model. Every track of the payload is in
## the cache. The draw gives the first candidate.
func _setup(mode: String = ClientSettings.MUSIC_MODE_AREA, track: String = "") -> void:
	if _player != null:
		_player.free()

	_clean()
	_state = MusicState.new()
	_settings = ClientSettings.new(TEST_PATH)
	_settings.set_music_mode(mode, track)
	_player = MusicPlayer.new()
	add_child(_player)
	_player.set_draw(func(_count: int) -> int: return 0)
	_playing = []
	_player.playing_changed.connect(func(key: String): _playing.append(key))

	for row: Dictionary in _StateTest.payload()[_Const.MUSIC_ROWS_KEY]:
		_player.offer_stream(str(row["key"]), _silent_stream())

	_player.bind(_state, _settings, "http://unit.test")


static func _silent_stream() -> AudioStream:
	var stream := AudioStreamWAV.new()

	stream.format = AudioStreamWAV.FORMAT_8_BITS
	stream.mix_rate = SAMPLE_RATE
	stream.stereo = false

	var data := PackedByteArray()
	data.resize(int(STREAM_SECONDS * SAMPLE_RATE))
	stream.data = data

	return stream


func _send(payload: Dictionary) -> void:
	_state.ingest(_Const.CH_CHAR_MUSIC, payload)


## The payload with every row unlocked, so a pick has a choice.
static func _all_unlocked() -> Dictionary:
	var snapshot := _StateTest.payload()

	for row: Dictionary in snapshot[_Const.MUSIC_ROWS_KEY]:
		row["state"] = "unlocked"

	return snapshot


func _nothing_plays_before_a_snapshot() -> void:
	_setup()
	_expect(_player.playing_key() == "", "silence before char_music")
	_expect(_playing.is_empty(), "and nothing was announced")


func _the_first_snapshot_starts_a_track_of_the_area_at_once() -> void:
	_setup()
	_send(_StateTest.payload())
	_expect(_player.playing_key() == "frigid_memory", "the one unlocked track of the area plays")
	_expect(not _player.is_fading(), "the first track snaps in, with no fade")
	_expect(_playing == ["frigid_memory"], "and it was announced one time")


func _a_locked_track_never_plays() -> void:
	_setup(ClientSettings.MUSIC_MODE_SINGLE, "dune_song")
	_send(_StateTest.payload())
	_expect(_player.playing_key() == "", "a locked single track is silence")

	_setup(ClientSettings.MUSIC_MODE_SHUFFLE)
	_player.set_draw(func(count: int) -> int: return count - 1)
	_send(_StateTest.payload())
	_expect(_player.playing_key() != "dune_song", "shuffle never draws the locked one")


func _an_area_with_no_unlocked_track_is_silence() -> void:
	_setup()
	var snapshot := _StateTest.payload()
	snapshot[_Const.MUSIC_AREA_KEY] = "al_wasta"
	_send(snapshot)
	_expect(_player.playing_key() == "", "an area with no unlocked track is silence")
	_expect(not _player.is_waiting(), "and nothing is waited for")


func _a_new_area_blends_to_a_track_of_that_area() -> void:
	_setup()
	_send(_StateTest.payload())

	var moved := _StateTest.payload()
	moved[_Const.MUSIC_AREA_KEY] = "oasis"
	_send(moved)

	_expect(_player.playing_key() == "oasis_calm", "the track of the new area plays")
	_expect(_player.is_fading(), "and the change is a blend")

	_player.advance(MusicPlayer.FADE_SECONDS)
	_expect(not _player.is_fading(), "the blend ends after FADE_SECONDS")


func _the_track_of_the_new_area_keeps_playing_across_its_border() -> void:
	_setup(ClientSettings.MUSIC_MODE_SINGLE, "oasis_calm")
	_send(_StateTest.payload())
	_expect(_player.playing_key() == "oasis_calm", "single plays its track in any area")

	_settings.set_music_mode(ClientSettings.MUSIC_MODE_AREA)
	_expect(_player.playing_key() == "frigid_memory", "area mode picks the area")

	var moved := _StateTest.payload()
	moved[_Const.MUSIC_AREA_KEY] = "oasis"
	_send(moved)
	_send(moved)
	_expect(_playing.count("oasis_calm") == 2,
		"a second snapshot of the same area does not restart the track")


func _area_mode_never_repeats_the_last_pick_while_another_exists() -> void:
	_setup()
	_send(_all_unlocked())
	_expect(_player.playing_key() == "frigid_memory", "the first candidate plays")

	_player.end_of_track()
	_player.advance(MusicPlayer.GAP_SECONDS)
	_expect(_player.playing_key() == "dune_song",
		"the next pick is the other track of the area, with the draw at 0")

	_player.end_of_track()
	_player.advance(MusicPlayer.GAP_SECONDS)
	_expect(_player.playing_key() == "frigid_memory", "and then the first again")


func _shuffle_draws_from_every_unlocked_track() -> void:
	_setup(ClientSettings.MUSIC_MODE_SHUFFLE)
	_player.set_draw(func(count: int) -> int: return count - 1)
	_send(_all_unlocked())
	_expect(_player.playing_key() == "oasis_calm",
		"shuffle draws past the area, with the draw at the last candidate")


func _single_loops_its_track_and_ends_in_no_gap() -> void:
	_setup(ClientSettings.MUSIC_MODE_SINGLE, "frigid_memory")
	_send(_StateTest.payload())
	_player.end_of_track()
	_expect(_player.playing_key() == "frigid_memory", "single starts again at once")
	_expect(_playing == ["frigid_memory", "", "frigid_memory"],
		"the end and the restart are both announced")


func _a_track_that_ends_picks_the_next_after_the_gap() -> void:
	_setup()
	_send(_StateTest.payload())
	_player.end_of_track()
	_expect(_player.playing_key() == "", "silence in the gap")

	_player.advance(MusicPlayer.GAP_SECONDS * 0.5)
	_expect(_player.playing_key() == "", "still silence half way through the gap")

	_player.advance(MusicPlayer.GAP_SECONDS * 0.5)
	_expect(_player.playing_key() == "frigid_memory", "the next pick after the gap")


func _skip_ends_the_track_with_the_fade() -> void:
	_setup()
	_send(_all_unlocked())
	_player.skip()
	_expect(_player.playing_key() == "dune_song", "skip moves to the other track of the area")
	_expect(_player.is_fading(), "with the fade")


func _a_track_that_is_not_here_yet_starts_when_it_arrives() -> void:
	_setup(ClientSettings.MUSIC_MODE_SINGLE, "late_track")
	var snapshot := _StateTest.payload()
	snapshot[_Const.MUSIC_ROWS_KEY].append(
		{"key": "late_track", "name": "Late", "area": "oasis", "state": "unlocked", "hint": ""})
	_send(snapshot)
	_expect(_player.playing_key() == "", "nothing plays before the stream arrives")
	_expect(_player.is_waiting(), "and the track is waited for")

	_player.offer_stream("late_track", _silent_stream())
	_expect(_player.playing_key() == "late_track", "the track starts when it arrives")
	_expect(not _player.is_waiting(), "and the wait is over")


func _an_unlock_starts_music_in_a_silent_area() -> void:
	_setup()
	var snapshot := _StateTest.payload()
	snapshot[_Const.MUSIC_ROWS_KEY][0]["state"] = "locked"
	_send(snapshot)
	_expect(_player.playing_key() == "", "a locked area is silent")

	_send(_StateTest.payload())
	_expect(_player.playing_key() == "frigid_memory", "the unlock starts the track")


func _a_reset_stops_everything() -> void:
	_setup()
	_send(_StateTest.payload())
	_state.reset()
	_expect(_player.playing_key() == "", "silence after a reset")
	_expect(_playing[-1] == "", "and the silence was announced")


func _the_url_names_the_served_file() -> void:
	_setup()
	_expect(_player.url_for("frigid_memory")
		== "http://unit.test/static/webclient/music/frigid_memory.ogg",
		"the key names the file on the asset origin")
