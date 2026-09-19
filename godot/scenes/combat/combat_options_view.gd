class_name CombatOptionsView
extends Control
## The Combat tab, drawn from [CombatOptionsState]: your weapon, its styles as
## buttons, and what the active one does.
##
## Modelled on OSRS's Combat Options interface — the weapon and combat level at
## the top, one button per style in a two-by-two grid. The auto-retaliate
## toggle and special attack bar are absent because Blackout has neither.
##
## ## It names no style, and sends only what the server named
##
## Every button is one row of `char_combat`, and a click emits that row's
## `command` — `combatoptions guard`, a line a telnet player could type. The
## pane decides nothing about which styles a weapon has or what they are called.
##
## ## A click does not light the button
##
## The button clicked is put straight back to what the snapshot said, and the
## server's republish is what moves the highlight. See [CombatOptionsState] on
## why an optimistic highlight is the wrong answer.

## Emitted with a whole command a telnet player could have typed.
signal command_requested(command: String)

## Buttons per row. The reference interface's two-by-two, and what four styles
## fit in the panel column.
const COLUMNS := 2

## Tall enough for two lines: the style's name and its weapon style.
const STYLE_BUTTON_HEIGHT := 44

const NO_DATA_TEXT := "No combat options yet."
const COMBAT_LEVEL_TEXT := "Combat level: %d"
const SPEED_TEXT := "Attack speed: %d ticks (%.1fs)"
const NO_CHOICE_TEXT := "Wield a weapon to choose a style."
const ACTIVE_HEADING := "Active style"
const ATTACK_TYPE_TEXT := "Attack type: %s"
const BOOSTS_TEXT := "Boosts: %s"
const XP_TEXT := "Trains: %s"
const NONE_TEXT := "(none)"
const BUTTON_TEXT := "%s\n%s"
const PVP_HEADING := "Player versus player"
const PVP_ON_TEXT := "PvP: ON"
const PVP_OFF_TEXT := "PvP: off"
const PVP_TOOLTIP := "With PvP on, you and other players with PvP on can attack each other."
## A plain String, not a StringName literal: `test_theme` reads every `&"..."`
## in this file as a theme variation.
const PVP_BUTTON_NAME := "PvpToggle"

var _state: CombatOptionsState
var _body: VBoxContainer


func _init() -> void:
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.theme_type_variation = &"PaneMargin"
	add_child(margin)

	var scroller := ScrollContainer.new()
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	margin.add_child(scroller)

	_body = VBoxContainer.new()
	_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_body.theme_type_variation = &"FormColumn"
	scroller.add_child(_body)


## Bind to a model and follow it.
func bind(state: CombatOptionsState) -> void:
	_state = state
	_state.changed.connect(_rebuild)
	_rebuild()


## Every style button currently drawn, in the server's order. Read by tests.
func style_buttons() -> Array:
	var found: Array = []

	for child: Node in _body.get_children():
		if child is GridContainer:
			found.append_array(child.get_children())

	return found


## Rebuild wholesale; `char_combat` is a snapshot.
##
## `queue_free` after `remove_child`, as [SkillsView] does: a rebuild can follow
## a button's own signal, and freeing the button there tears down an object
## while it is still emitting.
func _rebuild() -> void:
	if _state == null:
		return

	for child: Node in _body.get_children():
		_body.remove_child(child)
		child.queue_free()

	if not _state.has_data:
		_body.add_child(_label(NO_DATA_TEXT, &"RowKey"))
		return

	_body.add_child(_label(_state.weapon_name, &"PanelHeading"))
	_body.add_child(_label(COMBAT_LEVEL_TEXT % _state.combat_level, &"RowKey"))
	_body.add_child(_label(SPEED_TEXT % [
		_state.attack_speed_ticks, _state.attack_speed_seconds], &"RowKey"))

	var grid := GridContainer.new()
	grid.columns = COLUMNS
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_body.add_child(grid)

	for row: Dictionary in _state.styles:
		grid.add_child(_style_button(row))

	if not _state.has_choice():
		_body.add_child(_wrapped(NO_CHOICE_TEXT))

	_add_pvp_toggle()
	_add_active_detail(_state.active_style())


## The PvP flag, drawn as one toggle. Lit when the server says the flag is on.
##
## The click sends the server's `command` verbatim — `pvp on` or `pvp off` —
## and puts the button straight back, for the rule the style buttons follow.
## The server refuses `pvp off` during a fight and says why in the log, so the
## pane carries no lock of its own.
##
## Absent when the server named no command: a server that predates the flag.
func _add_pvp_toggle() -> void:
	if _state.pvp_command.is_empty():
		return

	_body.add_child(HSeparator.new())
	_body.add_child(_label(PVP_HEADING, &"SectionHeading"))

	var button := Button.new()
	button.name = PVP_BUTTON_NAME
	button.toggle_mode = true
	button.button_pressed = _state.pvp_enabled
	button.text = PVP_ON_TEXT if _state.pvp_enabled else PVP_OFF_TEXT
	button.focus_mode = Control.FOCUS_NONE
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.tooltip_text = PVP_TOOLTIP
	button.pressed.connect(_on_pvp_pressed.bind(button))
	_body.add_child(button)


func _on_pvp_pressed(button: Button) -> void:
	button.set_pressed_no_signal(_state.pvp_enabled)
	command_requested.emit(_state.pvp_command)


## The PvP toggle, or null when none is drawn. Read by tests.
func pvp_button() -> Button:
	return _body.get_node_or_null(NodePath(PVP_BUTTON_NAME)) as Button


## One style. Lit when the server says it is active; disabled when the server
## named no command for it.
##
## `FOCUS_NONE` for the rule the tab strip follows: focus IS the mode in this
## client, and a button that took the keyboard would turn the player's next
## letter into a movement command.
func _style_button(row: Dictionary) -> Button:
	var button := Button.new()
	button.text = BUTTON_TEXT % [
		str(row["name"]), str(row["weapon_style"]).capitalize()]
	button.toggle_mode = true
	button.button_pressed = bool(row["active"])
	button.disabled = str(row["command"]).is_empty()
	button.focus_mode = Control.FOCUS_NONE
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.custom_minimum_size = Vector2(0, STYLE_BUTTON_HEIGHT)
	button.tooltip_text = _tooltip(row)
	button.pressed.connect(_on_pressed.bind(button, row))

	return button


## A style was clicked. Put the button back, then ask.
##
## The active style sends nothing: the server would only answer "already using
## it", which is a line in the log for a click that meant nothing.
func _on_pressed(button: Button, row: Dictionary) -> void:
	button.set_pressed_no_signal(bool(row["active"]))

	if bool(row["active"]):
		return

	var command := str(row["command"])

	if command.is_empty():
		return

	command_requested.emit(command)


func _add_active_detail(row: Dictionary) -> void:
	if row.is_empty():
		return

	_body.add_child(HSeparator.new())
	_body.add_child(_label(ACTIVE_HEADING, &"SectionHeading"))
	_body.add_child(_label(str(row["name"]), &"RowValue"))
	_body.add_child(_label(
		ATTACK_TYPE_TEXT % str(row["attack_type"]).capitalize(), &"RowKey"))
	_body.add_child(_wrapped(BOOSTS_TEXT % _boost_text(row["boosts"])))
	_body.add_child(_wrapped(XP_TEXT % _names(row["xp_skills"])))


func _tooltip(row: Dictionary) -> String:
	return "%s, %s\n%s\n%s" % [
		str(row["attack_type"]).capitalize(),
		str(row["weapon_style"]).capitalize(),
		BOOSTS_TEXT % _boost_text(row["boosts"]),
		XP_TEXT % _names(row["xp_skills"]),
	]


## "Strike +3, Brawn +1".
static func _boost_text(boosts: Array) -> String:
	var parts := PackedStringArray()

	for boost: Dictionary in boosts:
		parts.append("%s +%d" % [str(boost["name"]), int(boost["amount"])])

	if parts.is_empty():
		return NONE_TEXT

	return ", ".join(parts)


static func _names(entries: Array) -> String:
	var parts := PackedStringArray()

	for entry: Dictionary in entries:
		parts.append(str(entry["name"]))

	if parts.is_empty():
		return NONE_TEXT

	return ", ".join(parts)


## One label, styled by NAMING a variation declared in `ui/blackout_theme.tres`
## -- which `test_theme.gd` checks by reading this file as text.
func _label(text: String, variation: StringName) -> Label:
	var label := Label.new()
	label.text = text
	label.theme_type_variation = variation

	return label


func _wrapped(text: String) -> Label:
	var label := _label(text, &"RowKey")
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	return label
