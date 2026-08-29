class_name OptionsView
extends Control
## Font size, interface scale, which panes are drawn, and where a clicked
## skill's detail is shown.
##
## A body in [PanelView], and a Window before 08/28/2026. It is also the reason
## the panel column has no "hide me" setting: a control that can hide the screen
## you change it on is a trap, and this is that screen.
##
## Built in code for the same reason the inventory grid is: the bounds come from
## [ClientSettings], and a scene file would be a second place they live.
##
## It writes through the settings object rather than applying anything itself.
## The console listens for `changed` and is the only thing that touches a font
## or a scale factor, so there is one place that knows how a preference becomes
## a pixel.
##
## ## Two kinds of setting live here, and only one of them is ours
##
## Everything above the Game heading is the PLAYER's and the client's: a font
## size, a scale, which panes are drawn. It is written to [ClientSettings] and
## the server never hears about it.
##
## The Game heading is different. Those settings are the SERVER's, and this
## pane cannot write one -- it emits the same line a telnet player would type
## and the server decides. That is the rule the whole client is built on, and
## it is why they are BUTTONS rather than a checkbox: a checkbox claims to know
## the current state, and the only honest source for that is the server, which
## answers in the log.

## Emitted with a whole command a telnet player could have typed.
signal command_requested(command: String)

## What each skill-detail mode is called on screen.
##
## Keyed by the stored value, so the list the player sees is built by walking
## [constant ClientSettings.SKILL_DETAIL_MODES] rather than by restating the
## order here -- one owner for what the modes ARE, one for what they are
## CALLED, and no third place holding the order.
const SKILL_DETAIL_LABELS := {
	ClientSettings.SKILL_DETAIL_BOTH: "Pane and log",
	ClientSettings.SKILL_DETAIL_PANE: "In the pane",
	ClientSettings.SKILL_DETAIL_LOG: "In the game log",
}

var _settings: ClientSettings
var _font_slider: HSlider
var _font_value: Label
var _scale_slider: HSlider
var _scale_value: Label
var _world_check: CheckBox
var _inventory_check: CheckBox
var _skill_detail: OptionButton

## Set while pushing values INTO the widgets, so their value_changed does not
## write straight back and fight the update that is in progress.
var _syncing := false


func _init() -> void:
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.theme_type_variation = &"PaneMargin"
	add_child(margin)

	var column := VBoxContainer.new()
	column.theme_type_variation = &"FormColumn"
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

	# The two panes toggle separately, because they cost different things: the
	# world pane redraws every tile every frame, the bag redraws when the bag
	# changes. One switch for both meant a player on a slow machine had to give
	# up their inventory to stop the diorama.
	#
	# The HUD's 3D button writes the same setting. Two controls, one owner --
	# both go through ClientSettings and both follow its `changed`, which is
	# what stops them disagreeing.
	column.add_child(_heading("Panes"))
	_world_check = _check("3D world")
	column.add_child(_world_check)
	_inventory_check = _check("Inventory")
	column.add_child(_inventory_check)

	# Where a clicked skill's answer lands. A CHOICE rather than two checkboxes
	# because the three modes are exclusive and "neither" is not one of them --
	# a click that does nothing reads as a broken grid, not as a preference.
	#
	# The labels are written here and the VALUES come from ClientSettings, so
	# what is stored on disk and what is shown to the player have one owner
	# each and neither can drift into the other's job.
	column.add_child(_heading("Skill detail"))
	_skill_detail = OptionButton.new()
	_skill_detail.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN

	for index: int in ClientSettings.SKILL_DETAIL_MODES.size():
		_skill_detail.add_item(
			SKILL_DETAIL_LABELS[ClientSettings.SKILL_DETAIL_MODES[index]], index)

	column.add_child(_skill_detail)

	# Server-owned settings. See the class docstring on why these are buttons.
	#
	# `automap` is the one a player of THIS client would otherwise never
	# discover: the server stops printing the area map into the log because
	# this client draws its own minimap, so there is nothing on screen to
	# suggest the text map ever existed. `?` reports which way it is set.
	column.add_child(_heading("Game"))
	var automap := HBoxContainer.new()
	column.add_child(automap)
	automap.add_child(_label("Text map in log"))
	automap.add_child(_command_button("On", "automap on"))
	automap.add_child(_command_button("Off", "automap off"))
	automap.add_child(_command_button("?", "automap"))

	var reset := Button.new()
	reset.text = "Reset to defaults"
	reset.pressed.connect(func(): _settings.reset())
	column.add_child(reset)

	_font_slider.value_changed.connect(_on_font_changed)
	_scale_slider.value_changed.connect(_on_scale_changed)
	_world_check.toggled.connect(_on_world_toggled)
	_inventory_check.toggled.connect(_on_inventory_toggled)
	_skill_detail.item_selected.connect(_on_skill_detail_selected)


func bind(settings: ClientSettings) -> void:
	_settings = settings
	_settings.changed.connect(_sync)
	_sync()


func _sync() -> void:
	if _settings == null:
		return

	_syncing = true
	_font_slider.value = _settings.font_size
	_font_value.text = "%dpx" % _settings.font_size
	_scale_slider.value = _settings.ui_scale
	_scale_value.text = "%d%%" % roundi(_settings.ui_scale * 100.0)
	_world_check.button_pressed = _settings.show_world
	_inventory_check.button_pressed = _settings.show_inventory
	_skill_detail.selected = ClientSettings.SKILL_DETAIL_MODES.find(
		_settings.skill_detail)
	_syncing = false


func _on_font_changed(value: float) -> void:
	if _syncing:
		return

	_settings.set_font_size(int(value))


func _on_scale_changed(value: float) -> void:
	if _syncing:
		return

	_settings.set_ui_scale(value)


func _on_world_toggled(pressed: bool) -> void:
	if _syncing:
		return

	_settings.set_show_world(pressed)


func _on_inventory_toggled(pressed: bool) -> void:
	if _syncing:
		return

	_settings.set_show_inventory(pressed)


## The chosen index is a position in ClientSettings.SKILL_DETAIL_MODES, because
## that is the list the items were built from. Reading the VALUE back out of
## that array rather than off the label is what keeps the stored setting
## independent of what the option is called.
func _on_skill_detail_selected(index: int) -> void:
	if _syncing:
		return

	if index < 0 or index >= ClientSettings.SKILL_DETAIL_MODES.size():
		return

	_settings.set_skill_detail(ClientSettings.SKILL_DETAIL_MODES[index])


func _check(text: String) -> CheckBox:
	var box := CheckBox.new()
	box.text = text

	return box


## A button that sends one whole line a telnet player could have typed.
##
## Composed nowhere else and substituted into nowhere: the command IS the
## contract, and the server's reply in the log is what tells the player it
## worked. There is no privileged path from this screen to the game.
func _command_button(text: String, command: String) -> Button:
	var button := Button.new()
	button.text = text
	button.pressed.connect(func(): command_requested.emit(command))

	return button


func _label(text: String) -> Label:
	var label := Label.new()
	label.text = text
	label.theme_type_variation = &"RowKey"

	return label


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
