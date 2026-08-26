extends PanelContainer
## The observer's own status, above the text pane.
##
## Presentation only. Every fact it draws lives on [CharState]; this file
## decides how it LOOKS and nothing else, which is the same line the webclient
## draws between the server naming things and the client drawing them.
##
## It is a strip rather than a floating overlay because the text pane is still
## the authoritative view of the game -- this repeats what `char_vitals` and
## `char_status` say so the player does not have to read for it, and covering
## the log to do that would be a bad trade.

const _Const := preload("res://autoload/blackout_constants.gd")

## Bar colours. Presentation, so they live here and are not generated.
const COLOR_HEALTHY := Color("4caf50")
const COLOR_HURT := Color("d4a017")
const COLOR_CRITICAL := Color("c0392b")
const COLOR_COMBAT := Color("ff6b4a")
const COLOR_IDLE := Color(0.55, 0.55, 0.55)

## Where the bar changes colour. Fractions of max hp.
const HURT_BELOW := 0.6
const CRITICAL_BELOW := 0.3

## Shown before char_vitals has ever arrived, so an empty bar at login does not
## read as being dead. CharState.has_vitals is what distinguishes the two.
const NO_DATA_TEXT := "--/--"

@onready var _bar: ProgressBar = %HealthBar
@onready var _hp_label: Label = %HealthLabel
@onready var _state_label: Label = %StateLabel

var _state: CharState


## Bind to a model. Called by the console, which owns the CharState.
##
## Takes the model rather than reaching for a singleton so this scene can be
## opened on its own with a hand-built state, which is what makes it possible
## to look at without a running server.
func bind(state: CharState) -> void:
	_state = state
	_state.changed.connect(_redraw)
	_redraw()


func _redraw() -> void:
	if _state == null:
		return

	_redraw_health()
	_redraw_state()


func _redraw_health() -> void:
	var fraction := _state.health_fraction()

	_bar.value = fraction * _bar.max_value

	if not _state.has_vitals:
		_hp_label.text = NO_DATA_TEXT
		_bar.modulate = COLOR_IDLE
		return

	_hp_label.text = "%d/%d" % [_state.hp, _state.max_hp]
	_bar.modulate = _health_colour(fraction)


func _redraw_state() -> void:
	if _state.in_combat:
		_state_label.text = "IN COMBAT"
		_state_label.modulate = COLOR_COMBAT
		return

	_state_label.text = _levels_summary()
	_state_label.modulate = COLOR_IDLE


## One line naming the highest few levels.
##
## Iterates the levels dictionary rather than naming skills, because the server
## owns which skills exist -- a skill added under skill_defs/ must appear here
## with no edit, the same way a new room kind already gets a hashed colour
## rather than a missing one.
func _levels_summary() -> String:
	if _state.levels.is_empty():
		return ""

	var names: Array = _state.levels.keys()
	names.sort_custom(func(a, b): return _state.levels[a] > _state.levels[b])

	var parts: PackedStringArray = []

	for skill: String in names.slice(0, 3):
		parts.append("%s %d" % [skill.capitalize(), _state.levels[skill]])

	return "  ".join(parts)


func _health_colour(fraction: float) -> Color:
	if fraction < CRITICAL_BELOW:
		return COLOR_CRITICAL

	if fraction < HURT_BELOW:
		return COLOR_HURT

	return COLOR_HEALTHY
