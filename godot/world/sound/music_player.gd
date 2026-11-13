class_name MusicPlayer
extends Node
## The music player: which track plays, from the rows of [MusicState], the
## mode in [ClientSettings], and a random source (DESIGN-0016).
##
## ## The server owns the list, this node owns the play
##
## The server sends every track with its state, and the area the character
## stands in. Nothing here sends a command, and no click on the Music tab
## reaches the server. The play is a look, as the fog is.
##
## ## Two players, not one for each play
##
## [SoundCues] makes one player for each clip and frees it on `finished`.
## A track is one long stream, and a change of area blends the old track
## into the new one over [constant FADE_SECONDS]. Thus, two persistent
## players on the Music bus: the front one plays, the back one fades out.
##
## ## The pick
##
## Area mode draws at random from the unlocked rows of the current area,
## and never repeats the track that plays while another exists. Shuffle
## mode draws from every unlocked row. Single mode loops its one track. A
## locked track never plays. An area with no unlocked track is silence. A
## track that ends starts the next pick after [constant GAP_SECONDS].
## Skip ends the track at once, with the fade.
##
## ## The fetch
##
## One request for each track, from the served tree beside the models:
## `<origin>/static/webclient/music/<key>.ogg`. The bytes become a stream
## through `AudioStreamOggVorbis.load_from_buffer`, and a cache keeps each
## stream for the session. The player fetches the tracks of the current
## area first and never the whole list at once. A track that fails to
## fetch is out of the pick for the session, as a model that fails is.
##
## ## The web
##
## A browser refuses sound before the first click. The login gives one, so
## the first track plays, as the first cue does.
##
## Author: Nick Hobar
## Creation date: 11/08/2026

## The track that plays changed. Empty when the player fell silent. The
## Music tab draws its now-playing line and its blue row from it.
signal playing_changed(key: String)

## How long a blend between two tracks takes. The blend of the fog, so a
## border crossing moves the two together.
const FADE_SECONDS := AreaEnvironment.BLEND_SECONDS

## The silence between a track that ends and the next pick. Single mode
## has no gap: a loop is a loop.
const GAP_SECONDS := 3.0

## The served tree of the tracks, on the asset origin, and the suffix of a
## served file. The key names the file. The SERVER never names a file.
const SERVED_DIRECTORY := "/static/webclient/music/"
const SERVED_SUFFIX := ".ogg"

## A track is a few MB, and a slow link gets a long rope before the player
## gives up on it.
const TIMEOUT_SECONDS := 90.0

## The level of a player at the silent end of a fade. Not negative
## infinity, for the reason [method SoundCues.apply_volume] gives.
const SILENT_DB := -80.0

## The model and the settings, bound once.
var _state: MusicState
var _settings: ClientSettings

## Where this build fetches the tracks from. Empty is a failure, as it is
## for the models: nothing is ever fetched, and the game is silent.
var _origin := ""

## The player of the track that plays, and the player of the track that
## fades out. The two swap on each change.
var _front: AudioStreamPlayer
var _back: AudioStreamPlayer

## key -> AudioStream, for each track that arrived.
var _streams: Dictionary = {}

## key -> true while a request is in the air.
var _in_flight: Dictionary = {}

## key -> true for a track that was asked for and did not arrive. A
## permanent answer, so a silent area does not ask forever.
var _failed: Dictionary = {}

## The key of the track that plays, or "" in a gap and in silence.
var _playing_key := ""

## The key of the last track that started, through a gap and into the
## next pick. The pick never repeats it while another exists.
var _last_key := ""

## The key that should play as soon as its stream arrives, or "".
var _wanted_key := ""

## The mode, the chosen track, and the area at the last look, so a change
## of one of them is seen as a change.
var _last_mode := ""
var _last_track := ""
var _last_area := ""

## Where the fade is. A finished fade holds `_fade_elapsed >= FADE_SECONDS`.
var _fade_elapsed := FADE_SECONDS

## The gap that is left before the next pick, in seconds. Zero means no gap
## is running.
var _gap_left := 0.0

## The random source of a pick: a callable that takes a count and gives an
## index under it. A test gives a scripted one through [method set_draw].
var _draw: Callable

var _rng := RandomNumberGenerator.new()


func _init() -> void:
	_rng.randomize()
	_draw = _draw_random

	_front = _new_player()
	_back = _new_player()
	add_child(_front)
	add_child(_back)


## Bind to the model and the settings, and say where the tracks live.
##
## `origin` is [method ServerEndpoint.asset_origin], as for the models.
func bind(state: MusicState, settings: ClientSettings, origin: String) -> void:
	_state = state
	_settings = settings
	_origin = origin
	_last_mode = settings.music_mode
	_last_track = settings.music_track

	_state.changed.connect(_on_state_changed)
	_settings.changed.connect(_on_settings_changed)

	_on_state_changed()


## Give the player a scripted random source. For a test.
func set_draw(draw: Callable) -> void:
	_draw = draw


## Put one stream into the cache, as the fetch does when a track arrives.
## A test gives its streams here, with no network. The track starts when
## it is the one that should play.
func offer_stream(key: String, stream: AudioStream) -> void:
	_streams[key] = stream
	_in_flight.erase(key)

	if _wanted_key == key:
		_begin(key)


## The key of the track that plays, or "" in a gap and in silence.
func playing_key() -> String:
	return _playing_key


## Whether a blend runs now.
func is_fading() -> bool:
	return _fade_elapsed < FADE_SECONDS


## Whether a track is wanted and not here yet.
func is_waiting() -> bool:
	return not _wanted_key.is_empty()


## End the track that plays at once, with the fade, and pick the next one.
## Single mode starts its track again from the top.
func skip() -> void:
	if _state == null or not _state.has_data:
		return

	_start(_pick(), true)


## What the `finished` signal of the front player calls: the track came to
## its end. Public, so a test can end a track without the clock.
##
## Single mode starts the track again at once. The other modes leave the
## gap, and [method advance] picks the next track when the gap closes.
func end_of_track() -> void:
	var ended := _playing_key

	_playing_key = ""
	playing_changed.emit("")

	if _settings != null and _settings.music_mode == ClientSettings.MUSIC_MODE_SINGLE:
		_start(ended, true)
		return

	_gap_left = GAP_SECONDS


## Move the fade and the gap on by one step. `_process` calls it each
## frame, and a test calls it with the seconds it wants.
func advance(delta: float) -> void:
	_advance_fade(delta)
	_advance_gap(delta)


func _process(delta: float) -> void:
	advance(delta)


func _new_player() -> AudioStreamPlayer:
	var player := AudioStreamPlayer.new()

	player.bus = SoundCues.MUSIC_BUS
	player.finished.connect(_on_player_finished.bind(player))

	return player


func _on_player_finished(player: AudioStreamPlayer) -> void:
	# The back player ends at the tail of a fade, and that is not the end
	# of the track that plays.
	if player != _front or _playing_key.is_empty():
		return

	end_of_track()


## A snapshot landed, or the model was reset.
##
## A reset stops everything: the socket dropped, and the next session
## sends its own snapshot. A new area in Area mode picks a track of that
## area, unless the track that plays is one of them. A new list with the
## same area starts a track when the player is silent, because an unlock
## can turn a silent area into one with music.
func _on_state_changed() -> void:
	if not _state.has_data:
		_stop_all()
		_last_area = ""
		return

	var area_moved := _state.area != _last_area
	_last_area = _state.area

	if area_moved and _settings.music_mode == ClientSettings.MUSIC_MODE_AREA:
		_follow_area()
		return

	if _playing_key.is_empty() and _wanted_key.is_empty() and _gap_left <= 0.0:
		_start(_pick(), false)
		return

	if not _playing_key.is_empty() and not _state.is_unlocked(_playing_key):
		_start(_pick(), false)


## The mode or the chosen track moved. A volume move is the bus's, and it
## passes through here with no pick.
func _on_settings_changed() -> void:
	var same_mode := _settings.music_mode == _last_mode
	var same_track := _settings.music_track == _last_track

	if same_mode and same_track:
		return

	_last_mode = _settings.music_mode
	_last_track = _settings.music_track

	if _state == null or not _state.has_data:
		return

	_start(_pick(), false)


func _follow_area() -> void:
	var row := _state.row_for(_playing_key)
	var still_here := not row.is_empty() and str(row["area"]) == _state.area

	if still_here and _state.is_unlocked(_playing_key):
		_prefetch_area()
		return

	_start(_pick(), false)


## The key to play next by the mode, or "" for silence.
func _pick() -> String:
	var keys := _candidates()

	if keys.is_empty():
		return ""

	if keys.size() > 1 and _settings.music_mode != ClientSettings.MUSIC_MODE_SINGLE:
		keys.erase(_last_key)

	var index: int = clampi(int(_draw.call(keys.size())), 0, keys.size() - 1)

	return keys[index]


## The keys that the mode allows, in table order, less the ones that
## failed to fetch.
func _candidates() -> Array:
	var rows: Array = []

	match _settings.music_mode:
		ClientSettings.MUSIC_MODE_SHUFFLE:
			rows = _state.unlocked_rows()
		ClientSettings.MUSIC_MODE_SINGLE:
			if _state.is_unlocked(_settings.music_track):
				rows = [_state.row_for(_settings.music_track)]
		_:
			rows = _state.unlocked_rows_in(_state.area)

	var keys: Array = []

	for row: Dictionary in rows:
		var key := str(row["key"])

		if not _failed.has(key):
			keys.append(key)

	return keys


## Play one key: now when its stream is here, or when it arrives. An empty
## key fades to silence. The key that plays stays as it is, unless
## `restart` says to take it from the top.
func _start(key: String, restart: bool) -> void:
	_gap_left = 0.0

	if key.is_empty():
		_wanted_key = ""
		_fade_to_silence()
		return

	if key == _playing_key and not restart:
		_wanted_key = ""
		return

	_wanted_key = key

	if _streams.has(key):
		_begin(key)
	else:
		_fetch(key)

	_prefetch_area()


## Put the stream of a key on the front player, and fade the old front
## out. The first track snaps in, as the first fog does: a login is not a
## border crossing.
func _begin(key: String) -> void:
	_wanted_key = ""

	var was_playing := _front.playing
	var next := _back

	_back = _front
	_front = next

	_front.stream = _streams[key]
	_front.volume_db = SILENT_DB if was_playing else 0.0
	_front.play()

	if was_playing:
		_fade_elapsed = 0.0
	else:
		_fade_elapsed = FADE_SECONDS
		_back.stop()

	_playing_key = key
	_last_key = key
	playing_changed.emit(key)


## Fade the track that plays out, with nothing after it.
func _fade_to_silence() -> void:
	if not _front.playing:
		return

	var next := _back

	_back = _front
	_front = next
	_front.stop()
	_fade_elapsed = 0.0
	_playing_key = ""
	playing_changed.emit("")


func _stop_all() -> void:
	_front.stop()
	_back.stop()
	_wanted_key = ""
	_gap_left = 0.0
	_fade_elapsed = FADE_SECONDS

	if _playing_key.is_empty():
		return

	_playing_key = ""
	playing_changed.emit("")


func _advance_fade(delta: float) -> void:
	if _fade_elapsed >= FADE_SECONDS:
		return

	_fade_elapsed = minf(_fade_elapsed + delta, FADE_SECONDS)

	var weight := _fade_elapsed / FADE_SECONDS

	_front.volume_db = _db(weight)
	_back.volume_db = _db(1.0 - weight)

	if _fade_elapsed >= FADE_SECONDS:
		_back.stop()
		_front.volume_db = 0.0


func _advance_gap(delta: float) -> void:
	if _gap_left <= 0.0:
		return

	_gap_left -= delta

	if _gap_left > 0.0:
		return

	_gap_left = 0.0
	_start(_pick(), true)


## A linear weight as a bus-safe level. See [constant SILENT_DB].
static func _db(linear: float) -> float:
	if linear <= 0.001:
		return SILENT_DB

	return linear_to_db(linear)


func _draw_random(count: int) -> int:
	return _rng.randi_range(0, count - 1)


## Ask for every unlocked track of the current area that is not here, so
## the next pick in the area starts with no wait.
func _prefetch_area() -> void:
	if _state == null:
		return

	for row: Dictionary in _state.unlocked_rows_in(_state.area):
		_fetch(str(row["key"]))


## Fetch one track. A key that is here, in the air, or failed costs
## nothing. An empty origin fetches nothing, as for the models.
func _fetch(key: String) -> void:
	if key.is_empty() or _origin.is_empty():
		return

	if _streams.has(key) or _in_flight.has(key) or _failed.has(key):
		return

	var http := HTTPRequest.new()
	http.timeout = TIMEOUT_SECONDS
	add_child(http)
	_in_flight[key] = true

	http.request_completed.connect(
		func(result: int, code: int, _headers: PackedStringArray,
				body: PackedByteArray):
			http.queue_free()
			_finish_fetch(key, result, code, body))

	var err := http.request(url_for(key))

	if err != OK:
		http.queue_free()
		_finish_fetch(key, HTTPRequest.RESULT_CANT_CONNECT, 0, PackedByteArray())


## The URL of the served file of one key, on this player's origin.
func url_for(key: String) -> String:
	return _origin + SERVED_DIRECTORY + key + SERVED_SUFFIX


func _finish_fetch(key: String, result: int, code: int,
		body: PackedByteArray) -> void:
	_in_flight.erase(key)

	var stream: AudioStream = null

	if result == HTTPRequest.RESULT_SUCCESS and code == 200:
		stream = AudioStreamOggVorbis.load_from_buffer(body)

	if stream == null:
		push_warning("MusicPlayer: %s did not arrive (http %d, result %d)" % [
			key, code, result])
		_failed[key] = true

		if _wanted_key == key:
			_wanted_key = ""
			_start(_pick(), false)

		return

	offer_stream(key, stream)
