class_name OptionsView
extends Window
## Font size and interface scale, in a native Window.
##
## Built in code for the same reason the inventory grid is: the bounds come from
## [ClientSettings], and a scene file would be a second place they live.
##
## It writes through the settings object rather than applying anything itself.
## The console listens for `changed` and is the only thing that touches a font
## or a scale factor, so there is one place that knows how a preference becomes
## a pixel.

const TITLE := "Options"

var _settings: ClientSettings
var _font_slider: HSlider
var _font_value: Label
var _scale_slider: HSlider
var _scale_value: Label

## Set while pushing values INTO the widgets, so their value_changed does not
## write straight back and fight the update that is in progress.
var _syncing := false


func _init() -> void:
	title = TITLE
	size = Vector2i(320, 200)
	close_requested.connect(hide)
	hide()

	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side: String in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 12)
	add_child(margin)

	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	margin.add_child(column)

	column.add_child(_heading("Text size"))
	var font_row := HBoxContainer.new()
	column.add_child(font_row)
	_font_slider = _slider(ClientSettings.MIN_FONT_SIZE,
		ClientSettings.MAX_FONT_SIZE, 1.0)
	font_row.add_child(_font_slider)
	_font_value = Label.new()
	font_row.add_child(_font_value)

	column.add_child(_heading("Interface scale"))
	var scale_row := HBoxContainer.new()
	column.add_child(scale_row)
	_scale_slider = _slider(ClientSettings.MIN_UI_SCALE,
		ClientSettings.MAX_UI_SCALE, 0.05)
	scale_row.add_child(_scale_slider)
	_scale_value = Label.new()
	scale_row.add_child(_scale_value)

	var reset := Button.new()
	reset.text = "Reset to defaults"
	reset.pressed.connect(func(): _settings.reset())
	column.add_child(reset)

	_font_slider.value_changed.connect(_on_font_changed)
	_scale_slider.value_changed.connect(_on_scale_changed)


func bind(settings: ClientSettings) -> void:
	_settings = settings
	_settings.changed.connect(_sync)
	_sync()


func toggle() -> void:
	if visible:
		hide()
		return

	popup_centered()


func _sync() -> void:
	if _settings == null:
		return

	_syncing = true
	_font_slider.value = _settings.font_size
	_font_value.text = "%dpx" % _settings.font_size
	_scale_slider.value = _settings.ui_scale
	_scale_value.text = "%d%%" % roundi(_settings.ui_scale * 100.0)
	_syncing = false


func _on_font_changed(value: float) -> void:
	if _syncing:
		return

	_settings.set_font_size(int(value))


func _on_scale_changed(value: float) -> void:
	if _syncing:
		return

	_settings.set_ui_scale(value)


func _heading(text: String) -> Label:
	var label := Label.new()
	label.text = text

	return label


func _slider(minimum: float, maximum: float, step: float) -> HSlider:
	var slider := HSlider.new()
	slider.min_value = minimum
	slider.max_value = maximum
	slider.step = step
	slider.custom_minimum_size = Vector2(200, 0)
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	return slider
