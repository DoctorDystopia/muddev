@tool
class_name FlySpeedBar
extends HBoxContainer
## The fly speed bar in the toolbar of the 3D editor. It sets the speed of
## the free-look camera of Godot. To fly, hold the right mouse button and
## press W, A, S, or D (Nick, 11/10/2026).
##
## The bar keeps no copy of the speed. Godot keeps it in the Editor Setting
## [constant SETTING], and the plugin reads and writes that setting. The bar
## shows a speed and sends the speed that the author types.
##
## While the author holds Shift, Godot multiplies the speed by
## [constant SHIFT_FACTOR]. The code is View3DController::update_freelook
## (scene/debugger/view_3d_controller.cpp, Godot 4.7.2). No setting changes
## that factor. Thus, the bar shows the Shift speed as text only.

## The author typed a new fly speed, in metres per second.
signal speed_chosen(speed: float)

## The Editor Setting of the free-look speed. Godot owns it.
const SETTING := "editors/3d/freelook/freelook_base_speed"

## The factor that Godot applies while the author holds Shift. Godot fixes it.
const SHIFT_FACTOR := 3.0

## The range of the field, in metres per second. A typed value can go above
## the top. The step is the step of the Godot setting.
const SPEED_MIN := 0.1
const SPEED_MAX := 100.0
const SPEED_STEP := 0.01

## One click on an arrow of the field.
const ARROW_STEP := 0.5

## A speed with the most digits below 1000. The field is always wide enough
## for its text. A longer speed makes the field wider.
const WIDE_SPEED := 888.88

const FLY_TEXT := "Fly"
const SPEED_SUFFIX := "m/s"
const SHIFT_TEXT := "Shift %.1f m/s"

const FLY_TIP := "The speed of the free-look camera. Hold the right mouse button, then press W, A, S, or D.\nGodot keeps this value in Editor Settings > Editors > 3D > Freelook > Freelook Base Speed.\nThe mouse wheel in free-look changes the speed until the next change here."
const SHIFT_TIP := "The speed while you hold Shift. Godot multiplies the fly speed by 3, and no setting changes that factor.\nAlt divides the speed by 3."

var _field := SpinBox.new()
var _shift := Label.new()


func _init() -> void:
	var fly := Label.new()
	fly.text = FLY_TEXT
	fly.tooltip_text = FLY_TIP
	fly.mouse_filter = Control.MOUSE_FILTER_PASS
	add_child(fly)

	_field.min_value = SPEED_MIN
	_field.max_value = SPEED_MAX
	_field.step = SPEED_STEP
	_field.custom_arrow_step = ARROW_STEP
	_field.allow_greater = true
	_field.suffix = SPEED_SUFFIX
	_field.tooltip_text = FLY_TIP
	_field.value_changed.connect(_on_value_changed)
	add_child(_field)

	_shift.tooltip_text = SHIFT_TIP
	_shift.mouse_filter = Control.MOUSE_FILTER_PASS
	add_child(_shift)
	_show_shift(_field.value)


func _notification(what: int) -> void:
	if what == NOTIFICATION_THEME_CHANGED:
		_fit_field()


## Show `speed` and send no signal. The plugin calls this for a speed that
## Godot already holds.
func show_speed(speed: float) -> void:
	_field.set_value_no_signal(speed)
	_show_shift(_field.value)
	_fit_field()


## The speed that the field shows, in metres per second.
func speed() -> float:
	return _field.value


## The text that the SpinBox writes for `speed` (SpinBox::_update_text).
static func text_for(speed: float) -> String:
	var number := String.num(speed, step_decimals(SPEED_STEP))
	return "%s %s" % [number, SPEED_SUFFIX]


func _on_value_changed(value: float) -> void:
	_show_shift(value)
	_fit_field()
	speed_chosen.emit(value)


func _show_shift(fly_speed: float) -> void:
	_shift.text = SHIFT_TEXT % (fly_speed * SHIFT_FACTOR)


## Make the field as wide as its text in the font of the editor. A width in
## pixels clips the first digit when the editor draws a larger font. A
## LineEdit scrolls to show the end of a text that does not fit.
func _fit_field() -> void:
	if not is_inside_tree():
		return

	var edit := _field.get_line_edit()
	var widest := maxf(_text_width(edit, text_for(WIDE_SPEED)), _text_width(edit, text_for(_field.value)))
	var margins := edit.get_theme_stylebox("normal").get_minimum_size().x
	var caret := edit.get_theme_constant("caret_width")

	edit.custom_minimum_size.x = ceilf(widest + caret + margins)
	_field.update_minimum_size()


static func _text_width(edit: LineEdit, text: String) -> float:
	var font := edit.get_theme_font("font")
	var font_size := edit.get_theme_font_size("font_size")
	var size := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
	return size.x
