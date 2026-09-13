class_name SoundCues
extends Node
## What the game SOUNDS like. The server never names a clip.
##
## ## A cue is a moment, not a file
##
## Callers ask for [constant LEVEL_UP], never for `level_up.wav`, so swapping a
## clip is one line in [constant _STREAMS] and no caller moves. It is the split
## [ModelRegistry] makes for meshes: Python owns what is TRUE about the game,
## this client owns what it looks -- and sounds -- like. A sound named by the
## server would be the client verb table that has been deleted twice, in a new
## medium.
##
## ## Every clip plays on the SFX bus
##
## Declared in `res://default_bus_layout.tres`, so the player's volume is one
## write to one bus -- [method apply_volume] -- rather than a walk over every
## player alive, and it reaches a sound already playing as well as the next.
## A player naming a bus that does not exist falls back to Master without a
## word, which is why the test checks [constant BUS] by name.
##
## ## One player per play
##
## Created, played, and freed on `finished`. Two skills levelling off one kill
## publish two rosters a moment apart, and their cues overlap rather than the
## second cutting the first off, which one shared player would do.
##
## ## The web will not play a sound before the page has been touched
##
## Browsers refuse audio without user activation. Logging in is a click or a
## keypress, so anything cued from a game event is safe; a sound on the login
## screen itself may not be.

## The bus every cue plays on. Must match a name in `default_bus_layout.tres`.
##
## Plain Strings, here and below, and never `&"..."` literals: `test_theme`
## reads every StringName literal under `world/` and `scenes/` as a theme
## variation, and that check is only sound while nothing else spells one.
const BUS := "SFX"

## A skill's level rose. Cued from [signal SkillsState.levelled].
const LEVEL_UP := "level_up"

## Cue to clip. Adding a sound is one constant above and one row here.
const _STREAMS := {
	LEVEL_UP: preload("res://audio/sfx/level_up.wav"),
}


## Play one cue, returning the player so a caller can stop it early.
##
## An unknown cue plays nothing and returns null rather than raising: a missing
## sound is a cosmetic gap, and a client that crashed on one would be trading a
## silent moment for a broken session.
func play(cue: String) -> AudioStreamPlayer:
	var stream: AudioStream = _STREAMS.get(cue)

	if stream == null:
		return null

	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.bus = BUS
	player.finished.connect(player.queue_free)
	add_child(player)
	player.play()

	return player


## Every cue that has a clip.
static func cues() -> Array:
	return _STREAMS.keys()


## Set the SFX bus from a LINEAR volume, 0.0 to 1.0, as the Options slider
## stores it in [member ClientSettings.sfx_volume].
##
## Converted to decibels here because this file owns the bus. Zero MUTES rather
## than writing `linear_to_db(0.0)`, which is negative infinity -- a value that
## leaves "silent" up to how the mixer treats an infinity. Muting keeps the
## last decibel level, so nothing is lost by it.
static func apply_volume(linear: float) -> void:
	var index := AudioServer.get_bus_index(BUS)

	if index == -1:
		return

	var silent := linear <= 0.0
	AudioServer.set_bus_mute(index, silent)

	if silent:
		return

	AudioServer.set_bus_volume_db(index, linear_to_db(linear))
