class_name SoundCues
extends Node
## What the game SOUNDS like. The server never names a clip.
##
## ## A cue is a moment, not a file
##
## Callers ask for a cue such as [constant LEVEL_UP], never for `level_up.wav`.
## Thus, a clip swap is one line in the cue table, and no caller moves. It is
## the split that [ModelRegistry] makes for meshes: Python owns what is TRUE
## about the game, and this client owns what it looks and sounds like. A sound
## that the server names would be the client verb table again, in a new
## medium. The repo deleted that table two times.
##
## ## The cue table is a file
##
## `res://audio/cues.json` (10/26/2026), because a table that an author grows
## is a table file. The sound wizard, `python -m assets.audio add`, writes it.
## `blackout/assets/audio/cue_table.py` owns its format:
##
## | Key | Holds |
## |---|---|
## | `cues` | Cue to `{kind, clip, note}`. `clip` is relative to `res://audio/` |
## | `moments` | Server moment to cue |
##
## A moment key is a plain string now, not a generated constant. Thus, the
## Python check (`statefeed/tests/test_cue_table.py`) does the work of the
## compiler. It refuses a moment that the server does not name, a missing
## clip, and a clip with no credits row. A moment with no row plays nothing.
##
## ## Every clip plays on the bus of its kind
##
## [constant _KIND_BUSES] maps a sound kind to a bus of
## `res://default_bus_layout.tres`. Thus, the volume of the player is one
## write to one bus, [method apply_volume]. The write reaches a sound that
## plays now, and the next one. A kind with no row plays on [constant BUS].
## An audio player that names a bus that does not exist plays on Master with
## no warning. For that reason, the test checks each bus by name. Music is a
## later kind, with a bus of its own.
##
## ## One player per play
##
## Created, played, and freed on `finished`. Two skills can level up from one
## kill, and their rosters come a moment apart. Their cues then overlap. One
## shared player would cut the first cue off.
##
## ## The web plays no sound before the player touches the page
##
## Browsers refuse audio until the player clicks or types in the page. A login
## does both, so each cue from a game event plays. A sound on the login screen
## itself can fail to play.

## The bus of a sound effect, and of a kind with no row in [constant
## _KIND_BUSES]. Must match a name in `default_bus_layout.tres`.
##
## Plain Strings, here and below, and never `&"..."` literals. `test_theme`
## reads every StringName literal under `world/` and `scenes/` as a theme
## variation. That check is correct only while nothing else spells one.
const BUS := "SFX"

## A level of a skill rose. [signal SkillsState.levelled] cues it, so the
## client names it in code. The cue table must hold it, and the test checks
## that.
const LEVEL_UP := "level_up"

## The cue table, and the folder that each clip of it is relative to.
const TABLE_PATH := "res://audio/cues.json"
const AUDIO_DIR := "res://audio/"

const KEY_CUES := "cues"
const KEY_MOMENTS := "moments"
const FIELD_KIND := "kind"
const FIELD_CLIP := "clip"

## Sound kind to bus. A kind with no row plays on [constant BUS]. Music adds
## a row and a bus.
const _KIND_BUSES := {
	"sfx": BUS,
}

## The cue table after the first read. Empty for a file that is not there or
## does not read.
static var _table := {}
static var _table_read := false

## Cue to its loaded clip, filled on the first play.
static var _streams := {}


## Play one cue, and return the player, so a caller can stop it early.
##
## An unknown cue plays nothing and returns null. It does not raise. A missing
## sound is a cosmetic gap, and a crash would trade a silent moment for a
## broken session.
func play(cue: String) -> AudioStreamPlayer:
	var stream := stream_of(cue)

	if stream == null:
		return null

	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.bus = bus_of(cue)
	player.finished.connect(player.queue_free)
	add_child(player)
	player.play()

	return player


## Play the cue of one server moment, from [signal MomentFeed.happened].
## A moment with no cue plays nothing and returns null, as [method play] does.
func play_moment(moment: String) -> AudioStreamPlayer:
	var cue := cue_for_moment(moment)

	return play(cue)


## Every cue of the cue table.
static func cues() -> Array:
	return _section(KEY_CUES).keys()


## Every server moment that has a cue.
static func moments() -> Array:
	return _section(KEY_MOMENTS).keys()


## The cue of one server moment, or "" for a moment with no row.
static func cue_for_moment(moment: String) -> String:
	var cue: Variant = _section(KEY_MOMENTS).get(moment, "")

	return cue if cue is String else ""


## The clip of one cue, loaded on the first use. Null for a cue with no row,
## or a clip that does not load.
static func stream_of(cue: String) -> AudioStream:
	if _streams.has(cue):
		return _streams[cue]

	var row := _row_of(cue)
	var clip: Variant = row.get(FIELD_CLIP)
	var stream: AudioStream = null

	if clip is String and not clip.is_empty():
		stream = load(AUDIO_DIR + clip) as AudioStream

	_streams[cue] = stream

	return stream


## The bus of one cue: the bus of its kind, or [constant BUS].
static func bus_of(cue: String) -> String:
	var kind: Variant = _row_of(cue).get(FIELD_KIND, "")

	return _KIND_BUSES.get(kind, BUS)


## Every bus that a kind plays on.
static func buses() -> Array:
	var found := [BUS]

	for bus: String in _KIND_BUSES.values():
		if not found.has(bus):
			found.append(bus)

	return found


## Set the SFX bus from a LINEAR volume, 0.0 to 1.0. The Options slider stores
## it in [member ClientSettings.sfx_volume].
##
## This file owns the bus, so it converts to decibels. Zero MUTES the bus. The
## code does not write `linear_to_db(0.0)`, which is negative infinity. Then
## "silent" would depend on how the mixer treats an infinity. A mute keeps the
## last decibel level, so the mute loses nothing.
static func apply_volume(linear: float) -> void:
	var index := AudioServer.get_bus_index(BUS)

	if index == -1:
		return

	var silent := linear <= 0.0
	AudioServer.set_bus_mute(index, silent)

	if silent:
		return

	AudioServer.set_bus_volume_db(index, linear_to_db(linear))


## Drop the cached table and clips, so that the next read sees the file again.
## For a test, and for a reload after an edit outside Godot.
static func forget() -> void:
	_table = {}
	_table_read = false
	_streams = {}


## The row of one cue, or an empty dictionary.
static func _row_of(cue: String) -> Dictionary:
	var row: Variant = _section(KEY_CUES).get(cue, {})

	return row if row is Dictionary else {}


## One section of the cue table, or an empty dictionary.
static func _section(key: String) -> Dictionary:
	var rows: Variant = _data().get(key, {})

	return rows if rows is Dictionary else {}


## The parsed cue table. This routine reads the file one time.
static func _data() -> Dictionary:
	if _table_read:
		return _table

	_table_read = true

	if not FileAccess.file_exists(TABLE_PATH):
		return _table

	var text := FileAccess.get_file_as_string(TABLE_PATH)
	var parsed: Variant = JSON.parse_string(text)

	if parsed is Dictionary:
		_table = parsed

	return _table
