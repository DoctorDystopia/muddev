extends Node
## Unit tests for FlySpeedBar, the fly speed bar of the camera plugin.
##
##     godot --headless --path godot res://tests/addons/blackout_camera/test_fly_speed_bar.tscn

## A speed that the Godot setting holds, between two arrow steps.
const GODOT_SPEED := 0.37

## A speed that the author types.
const TYPED_SPEED := 4.0

## The speed that showed as "6.0 m/s" in the editor of Nick (11/10/2026).
const TWO_DIGIT_SPEED := 16.0

## A speed above the wide sample of the bar, so the field must grow.
const LONG_SPEED := 12345.67

## The font sizes to try. The large one stands for an editor with a large
## display scale.
const FONT_SIZES: Array[int] = [16, 40]

var _failures := 0

## Each speed that the bar sent, in order.
var _sent: Array[float] = []


func _ready() -> void:
	_a_speed_from_godot_sends_nothing()
	_a_typed_speed_goes_to_the_plugin()
	_the_shift_text_follows_the_fly_speed()
	_a_speed_from_godot_shows_as_it_is()
	_a_speed_above_the_top_stays()
	_the_bar_never_sends_a_speed_of_zero()
	_the_field_holds_its_whole_text()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: fly_speed_bar")
	get_tree().quit(0)


## The plugin shows the speed that Godot holds. A signal would write the same
## value back to the setting.
func _a_speed_from_godot_sends_nothing() -> void:
	var bar := _bar()
	bar.show_speed(TYPED_SPEED)

	_expect(_sent.is_empty(), "show_speed sends no speed")
	_expect(is_equal_approx(bar.speed(), TYPED_SPEED), "the field shows the speed")

	bar.free()


func _a_typed_speed_goes_to_the_plugin() -> void:
	var bar := _bar()
	bar._field.value = TYPED_SPEED

	_expect(_sent.size() == 1, "one change sends one speed")
	_expect(not _sent.is_empty() and is_equal_approx(_sent[0], TYPED_SPEED),
		"the bar sends the typed speed")

	bar.free()


func _the_shift_text_follows_the_fly_speed() -> void:
	var bar := _bar()
	var shift_speed := "%.1f" % (TYPED_SPEED * FlySpeedBar.SHIFT_FACTOR)

	bar.show_speed(TYPED_SPEED)
	_expect(bar._shift.text.contains(shift_speed), "a shown speed updates the Shift text")

	bar.show_speed(GODOT_SPEED)
	bar._field.value = TYPED_SPEED
	_expect(bar._shift.text.contains(shift_speed), "a typed speed updates the Shift text")

	bar.free()


## The step of the field is the step of the Godot setting. Thus, the field
## does not round a value that the author set in Editor Settings.
func _a_speed_from_godot_shows_as_it_is() -> void:
	var bar := _bar()
	bar.show_speed(GODOT_SPEED)

	_expect(is_equal_approx(bar.speed(), GODOT_SPEED), "the field keeps a speed between arrow steps")

	bar.free()


func _a_speed_above_the_top_stays() -> void:
	var bar := _bar()
	var fast := FlySpeedBar.SPEED_MAX * 2.0

	bar._field.value = fast

	_expect(is_equal_approx(bar.speed(), fast), "a typed speed can go above the top of the field")

	bar.free()


## A fly speed of zero holds the camera in place, and nothing on screen
## tells the author why.
func _the_bar_never_sends_a_speed_of_zero() -> void:
	var bar := _bar()
	bar.show_speed(TYPED_SPEED)
	bar._field.value = 0.0

	_expect(not _sent.is_empty() and _sent[-1] > 0.0, "a typed zero sends the bottom of the field")

	bar.free()


## A field of a fixed width clipped the first digit of 16 in an editor with a
## large font. The LineEdit scrolls to the end of a text that does not fit.
## Thus, the room for text must hold the whole text at each font size.
func _the_field_holds_its_whole_text() -> void:
	for font_size: int in FONT_SIZES:
		for speed: float in [TWO_DIGIT_SPEED, LONG_SPEED]:
			var bar := _bar()
			var theme := Theme.new()
			theme.default_font_size = font_size
			bar.theme = theme
			bar.show_speed(speed)

			var edit: LineEdit = bar._field.get_line_edit()
			var margins := edit.get_theme_stylebox("normal").get_minimum_size().x
			var room := edit.get_combined_minimum_size().x - margins
			var text := FlySpeedBar.text_for(speed)

			_expect(room >= FlySpeedBar._text_width(edit, text),
				"the field holds all of \"%s\" at font size %d" % [text, font_size])

			bar.free()


## A bar in the tree that records each speed it sends. A Range sends
## value_changed only inside the tree. Each case starts with no record.
func _bar() -> FlySpeedBar:
	_sent.clear()

	var bar := FlySpeedBar.new()
	bar.speed_chosen.connect(func(speed: float) -> void: _sent.append(speed))
	add_child(bar)
	return bar


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
