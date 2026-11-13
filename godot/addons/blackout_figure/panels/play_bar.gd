@tool
class_name FigurePlayBar
extends VBoxContainer
## The play bar of the figure workbench: Play, Pause, Rest pose, the time
## slider, and the speed (ENG-0011, item 16). It sits in the top bar of the
## dock, so a clip plays while the author edits on any tab.
##
## The bar knows no clip. The plugin plays the clip that the Clips tab
## selects, and it gives the bar the length of that clip. The bar changes no
## file. Each control sends a signal, and the plugin acts.

## "Play": play the selected clip at `speed`.
signal play_requested(speed: float)
signal pause_requested
signal stop_requested

## The slider moved: hold each stand at `time` of the selected clip.
signal seek_requested(time: float)

const SPEED_LOW := 0.1
const SPEED_HIGH := 3.0
const SPEED_STEP := 0.1

const TIME_STEP := 0.01

var _time := HSlider.new()
var _speed: SpinBox
var _play: Button


func _init() -> void:
	var buttons := HBoxContainer.new()

	_play = FigureFields.button("Play", func() -> void:
		play_requested.emit(speed()), "Play the clip of the Clips tab on each stand.")
	buttons.add_child(_play)
	buttons.add_child(FigureFields.button("Pause", pause_requested.emit,
		"Hold each stand at this moment of the clip."))
	buttons.add_child(FigureFields.button("Rest pose", stop_requested.emit,
		"Put each stand back in its rest pose."))
	_speed = FigureFields.spin(SPEED_LOW, SPEED_HIGH, SPEED_STEP, 1.0)
	_speed.prefix = "speed"
	_speed.tooltip_text = "The speed of the clip. 1 is the speed of the clip file."
	buttons.add_child(_speed)
	add_child(buttons)
	_time.step = TIME_STEP
	_time.max_value = TIME_STEP
	_time.tooltip_text = "The time in the clip, in seconds."
	_time.value_changed.connect(func(value: float) -> void: seek_requested.emit(value))
	add_child(_time)


## Give the slider the length of the selected clip, in seconds. Zero for
## no clip.
func set_clip_length(length: float) -> void:
	# The time goes to zero first. A new maximum below the old time would
	# clamp it, and the slider then sends a seek.
	_time.set_value_no_signal(0.0)
	_time.max_value = maxf(length, TIME_STEP)


## Show the time of the clip. The bar sends no signal.
func set_time(time: float) -> void:
	_time.set_value_no_signal(time)


func speed() -> float:
	return _speed.value
