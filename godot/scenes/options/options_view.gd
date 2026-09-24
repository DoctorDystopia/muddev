class_name OptionsView
extends Control
## Font size, interface scale, sound effects volume, which panes are drawn, and
## where a clicked skill's detail is shown.
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

## The player asked to start the XP tracker's session over. Not a setting and
## not a command -- the session is the client's own reading -- so it is a
## signal the console answers by resetting the tracker.
signal xp_session_reset_requested

## The player asked to see the model credits. Not a setting and not a
## command: the credits box is the client's own, so the console opens it.
signal credits_requested

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

## The parts of the room text that `movetext` can turn off, in the order that
## the room prints them. Each key belongs to the SERVER: MOVE_TEXT_PARTS in
## blackout/systems/interface/ui/move_text.py. Each label belongs to the client.
##
## `test_move_text_client.py` reads this table and fails on a key that names
## no part. A part with no row here is fine: the player can still type
## `movetext <part> off`.
const MOVE_TEXT_LABELS := {
	"name": "Room name",
	"desc": "Description",
	"exits": "Exits",
	"characters": "Characters",
	"things": "Things you see",
}

var _settings: ClientSettings
var _font_slider: HSlider
var _font_value: Label
var _scale_slider: HSlider
var _scale_value: Label
var _sfx_slider: HSlider
var _sfx_value: Label
var _world_check: CheckBox
var _inventory_check: CheckBox
var _skill_detail: OptionButton
var _xp_drops_check: CheckBox
var _skill_rates_check: CheckBox
var _smooth_movement_check: CheckBox

## Set while pushing values INTO the widgets, so their value_changed does not
## write straight back and fight the update that is in progress.
var _syncing := false


func _init() -> void:
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.theme_type_variation = &"PaneMargin"
	add_child(margin)

	var scroller := ScrollContainer.new()
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	margin.add_child(scroller)

	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.theme_type_variation = &"FormColumn"
	scroller.add_child(column)

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

	# Linear, shown as a percentage. The console turns it into a bus level
	# through SoundCues, so this pane never learns what a decibel is.
	column.add_child(_heading("Sound effects"))
	var sfx_row := HBoxContainer.new()
	column.add_child(sfx_row)
	_sfx_slider = _slider(ClientSettings.MIN_SFX_VOLUME,
		ClientSettings.MAX_SFX_VOLUME, 0.05)
	sfx_row.add_child(_sfx_slider)
	_sfx_value = Label.new()
	sfx_row.add_child(_sfx_value)

	# The two panes toggle separately, because they cost different things: the
	# world pane redraws every tile every frame, the bag redraws when the bag
	# changes. One switch for both meant a player on a slow machine had to give
	# up their inventory to stop the diorama.
	#
	# The bag box covers BOTH halves of the bag, which are two tabs since
	# 09/21/2026. A switch that hid the carried grid and left the paper doll in
	# the strip would be a switch that half worked.
	#
	# The HUD's 3D button writes the same setting. Two controls, one owner --
	# both go through ClientSettings and both follow its `changed`, which is
	# what stops them disagreeing.
	column.add_child(_heading("Panes"))
	_world_check = _check("3D world")
	column.add_child(_world_check)
	_inventory_check = _check("Inventory and equipment")
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

	# How a step is drawn. One checkbox and not two: the true tile mark is what
	# pays back the information the animation costs, so it is not separately
	# switchable. See ClientSettings.DEFAULT_SMOOTH_MOVEMENT.
	column.add_child(_heading("Movement"))
	_smooth_movement_check = _check("Slide between tiles")
	column.add_child(_smooth_movement_check)

	# The XP drops over the world. Both are the player's; the reset is neither a
	# setting nor a command, which is why it is a signal of its own.
	column.add_child(_heading("XP tracker"))
	_xp_drops_check = _check("XP drops and session tracker")
	column.add_child(_xp_drops_check)
	_skill_rates_check = _check("XP per hour for each skill")
	column.add_child(_skill_rates_check)
	var reset_session := Button.new()
	reset_session.text = "Reset session"
	reset_session.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	reset_session.pressed.connect(func(): xp_session_reset_requested.emit())
	column.add_child(reset_session)

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

	_add_move_text_rows(column)

	# The server only offers a TOGGLE for this one -- no on, no off, no query --
	# so the pane offers exactly that and nothing it would have to fake. The
	# reply in the log names the state it landed on.
	var craft_confirm := HBoxContainer.new()
	column.add_child(craft_confirm)
	craft_confirm.add_child(_label("Confirm before crafting"))
	craft_confirm.add_child(_command_button("Toggle", "toggle craft confirm"))

	var reset := Button.new()
	reset.text = "Reset to defaults"
	reset.pressed.connect(func(): _settings.reset())
	column.add_child(reset)

	# LAST in the pane, below every setting. It is not a setting: it opens the
	# box that credits the art. CC-BY asks for a credit the player can see,
	# and this button is where the player sees it.
	column.add_child(_heading("Credits"))
	var credits := Button.new()
	credits.text = "Model credits"
	credits.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	credits.pressed.connect(func(): credits_requested.emit())
	column.add_child(credits)

	_font_slider.value_changed.connect(_on_font_changed)
	_scale_slider.value_changed.connect(_on_scale_changed)
	_sfx_slider.value_changed.connect(_on_sfx_changed)
	_world_check.toggled.connect(_on_world_toggled)
	_inventory_check.toggled.connect(_on_inventory_toggled)
	_skill_detail.item_selected.connect(_on_skill_detail_selected)
	_xp_drops_check.toggled.connect(_on_xp_drops_toggled)
	_skill_rates_check.toggled.connect(_on_skill_rates_toggled)
	_smooth_movement_check.toggled.connect(_on_smooth_movement_toggled)


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
	_sfx_slider.value = _settings.sfx_volume
	_sfx_value.text = "%d%%" % roundi(_settings.sfx_volume * 100.0)
	_world_check.button_pressed = _settings.show_world
	_inventory_check.button_pressed = _settings.show_inventory
	_skill_detail.selected = ClientSettings.SKILL_DETAIL_MODES.find(
		_settings.skill_detail)
	_xp_drops_check.button_pressed = _settings.show_xp_drops
	_skill_rates_check.button_pressed = _settings.show_skill_rates
	_skill_rates_check.disabled = not _settings.show_xp_drops
	_smooth_movement_check.button_pressed = _settings.smooth_movement
	_syncing = false


func _on_font_changed(value: float) -> void:
	if _syncing:
		return

	_settings.set_font_size(int(value))


func _on_scale_changed(value: float) -> void:
	if _syncing:
		return

	_settings.set_ui_scale(value)


func _on_sfx_changed(value: float) -> void:
	if _syncing:
		return

	_settings.set_sfx_volume(value)


func _on_world_toggled(pressed: bool) -> void:
	if _syncing:
		return

	_settings.set_show_world(pressed)


func _on_inventory_toggled(pressed: bool) -> void:
	if _syncing:
		return

	_settings.set_show_inventory(pressed)


func _on_xp_drops_toggled(pressed: bool) -> void:
	if _syncing:
		return

	_settings.set_show_xp_drops(pressed)


func _on_skill_rates_toggled(pressed: bool) -> void:
	if _syncing:
		return

	_settings.set_show_skill_rates(pressed)


func _on_smooth_movement_toggled(pressed: bool) -> void:
	if _syncing:
		return

	_settings.set_smooth_movement(pressed)


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


## One On / Off row for each part of the room text that a step prints.
##
## Buttons, like `automap`, and for the same reason: the server holds the
## choice, and its reply in the log tells the player the state. `?` lists
## every part. `All on` puts the default back.
func _add_move_text_rows(column: VBoxContainer) -> void:
	var header := HBoxContainer.new()
	column.add_child(header)
	header.add_child(_label("Room text when you move"))
	header.add_child(_command_button("?", "movetext"))
	header.add_child(_command_button("All on", "movetext reset"))

	for part: String in MOVE_TEXT_LABELS:
		var row := HBoxContainer.new()
		column.add_child(row)
		row.add_child(_label(str(MOVE_TEXT_LABELS[part])))
		row.add_child(_command_button("On", "movetext %s on" % part))
		row.add_child(_command_button("Off", "movetext %s off" % part))


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
