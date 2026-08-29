class_name SkillCell
extends PanelContainer
## One square of the skills grid: a category swatch, a name, a level and a bar.
##
## ## It decides nothing about the game
##
## Everything it draws is one row of [SkillsState], and the only thing it emits
## is that row's `command` — a whole line the SERVER named and a telnet player
## could type. There is no verb here and there must never be one; the browser
## pane had a verb table once and it was wrong within a week.
##
## ## Why a bar and not two numbers
##
## The reference interface shows a skill as an icon and its level twice
## (current and base). Blackout has no base/boosted split to show, so the second
## number would be the same number — and the fact a player actually wants at a
## glance is how close the next level is. The server ships `current_xp` and
## `needed_xp` as separate fields precisely so a client can draw that, which
## [method SkillsState.level_fraction] turns into a fraction.
##
## A skill at the cap draws a full bar rather than a special case: `needed_xp`
## is what the fraction reads, and the reading it gives there is "done", which
## is true.

## Emitted with a whole command a telnet player could have typed.
signal chosen(command: String)

const _Palette := preload("res://world/skill_palette.gd")

## The category swatch, in pixels. Square, small, and left of the name — enough
## to band the grid by category without becoming the thing you look at.
const SWATCH_SIZE := 8

const BAR_HEIGHT := 4

## Room reserved for the level, in pixels: three digits, since
## MAX_BASE_SKILL_LEVEL is 127. Reserved rather than measured; see [method
## _init].
const LEVEL_WIDTH := 26

## Floor on a cell, in pixels. Three columns of these fit the panel column at
## its default width; a narrower client scrolls rather than crushing them.
const MIN_WIDTH := 76

var _row: Dictionary = {}
var _name: Label
var _level: Label
var _swatch: ColorRect
var _bar: ProgressBar


## Built in _init, not _ready.
##
## The view makes the whole grid and then swaps it in, and _ready does not run
## until a node ENTERS the tree — so building here is what lets the view
## construct and bind in one pass. Same reason [InventorySlotCell] does it.
func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	custom_minimum_size = Vector2(MIN_WIDTH, 0)

	# The frame, and the padding inside it, are one StyleBox named in the theme.
	# Without it the grid is a wrapped run of labels, which is the shape this
	# whole pane exists to replace.
	theme_type_variation = &"SkillCell"

	# EXPAND_FILL, not just a minimum: a GridContainer sizes its columns to
	# their widest child, so cells that merely have a floor come out ragged and
	# the grid stops reading as columns at all.
	size_flags_horizontal = Control.SIZE_EXPAND_FILL

	var column := VBoxContainer.new()
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_theme_constant_override("separation", 3)
	add_child(column)

	var top := HBoxContainer.new()
	top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(top)

	_swatch = ColorRect.new()
	_swatch.custom_minimum_size = Vector2(SWATCH_SIZE, SWATCH_SIZE)
	_swatch.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_swatch.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top.add_child(_swatch)

	_name = Label.new()
	_name.theme_type_variation = &"CellDetail"
	_name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_name.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_name.mouse_filter = Control.MOUSE_FILTER_IGNORE

	# `clip_text` is what makes the COLUMNS line up, and it is not obvious.
	#
	# A Label reports its whole text as its minimum width, and a GridContainer
	# sizes each column to its widest child's minimum -- so without this the
	# Fortitude column is wider than the Brawn column and the grid stops reading
	# as a grid. Clipping drops the Label's minimum to zero, every cell is left
	# with the same floor (this control's own), and the columns come out equal.
	#
	# It also replaced a hand-rolled substring: the engine ellipsizes on the
	# rendered width, which is right at every font size, where a character count
	# is right at exactly one.
	_name.clip_text = true
	_name.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	top.add_child(_name)

	# The level is the thing the eye is looking for, so it is the one that gets
	# the size -- the reference interface makes the same call, with the name
	# absent entirely and only an icon to say which skill it is.
	_level = Label.new()
	_level.theme_type_variation = &"SkillLevel"
	_level.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_level.mouse_filter = Control.MOUSE_FILTER_IGNORE

	# A fixed width, wide enough for the three digits the cap allows. Without
	# it the number's own width is part of the cell's minimum, so a column of
	# level 9s is narrower than a column of level 127s and the grid comes out
	# ragged again -- the same failure `clip_text` fixes above, arriving from
	# the other end of the row.
	_level.custom_minimum_size = Vector2(LEVEL_WIDTH, 0)
	top.add_child(_level)

	_bar = ProgressBar.new()
	_bar.custom_minimum_size = Vector2(0, BAR_HEIGHT)
	_bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_bar.max_value = 1.0
	_bar.step = 0.001
	_bar.show_percentage = false
	_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(_bar)


## Draw one skill.
func bind(row: Dictionary) -> void:
	_row = row

	_swatch.color = _Palette.color_for(str(row.get("category", "")))
	_name.text = str(row.get("name", ""))
	_level.text = str(int(row.get("level", 0)))
	_bar.value = SkillsState.level_fraction(row)
	tooltip_text = _tooltip()


## The row this cell is drawing. Read by tests, which is worth one accessor
## rather than reaching into a private.
func row() -> Dictionary:
	return _row


func _gui_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return

	var click := event as InputEventMouseButton

	if not click.pressed or click.button_index != MOUSE_BUTTON_LEFT:
		return

	var command := str(_row.get("command", ""))

	if command.is_empty():
		# The server declining to name a command is the server saying this
		# affords nothing. Not an error, and not something to invent a
		# fallback for.
		return

	chosen.emit(command)
	accept_event()


## What the full name and the XP reading are, for a cell too small to show them.
##
## The name is repeated here rather than only the numbers: a cell ellipsizes a
## long name, and this is the only place a player can read the whole one.
func _tooltip() -> String:
	if _row.is_empty():
		return ""

	return "%s  level %d\n%d / %d xp into this level" % [
		str(_row.get("name", "")),
		int(_row.get("level", 0)),
		int(_row.get("current_xp", 0)),
		int(_row.get("needed_xp", 0)),
	]
