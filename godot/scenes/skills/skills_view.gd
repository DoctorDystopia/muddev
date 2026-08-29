class_name SkillsView
extends Control
## The skills grid, and one skill's sheet, drawn from [SkillsState].
##
## A tab beside Character, and the reason it is not part of it: the dossier's
## contract is that a client iterates panels and never names one, so a client
## that wanted a skills SCREEN had to break that contract to find the band. The
## band left the dossier on 08/28/2026 and became this, with a channel of its
## own.
##
## ## It names no skill, and must not learn one
##
## Every cell, every category heading and every unlock row comes from whatever
## `char_skills` contained, in the order the server sent it. Adding a skill is
## one file under `systems/progression/skills/skill_defs/`, and a table of
## names here would be the third place that fact lives and the first to go
## stale. The colours are the exception, and they are a LOOK rather than a fact
## — see [SkillPalette], which is guarded rather than generated for exactly
## that reason.
##
## The consequence worth stating, because it looks like a bug until you know:
## **a skill this client has never heard of renders correctly**, in the right
## category band, and one that stops being sent simply disappears.
##
## ## Two screens, one control
##
## The grid and the detail sheet are the same pane in two states, switched by
## [member _selected]. Not two tabs: a player clicking a skill is asking about
## that skill, and a second tab would leave them to find it.
##
## The selection SURVIVES a rebuild, which is load-bearing rather than tidy.
## Clicking a skill sends `skills <key>`, which makes the server republish
## `char_skills`, which fires `changed` — so a detail view that rebuilt from
## scratch would throw itself away a tick after opening. Keeping the key means
## the sheet is redrawn with the new numbers instead, which is also what makes
## it update live while the skill levels.

## Emitted with a whole command a telnet player could have typed.
signal command_requested(command: String)

const _Cell := preload("res://scenes/skills/skill_cell.gd")

## Grid width in cells. Presentation: the server says which skills there are and
## what order they come in, never how they are arranged. Three is what the
## reference interface uses and what fits the panel column.
const COLUMNS := 3

## Shown before char_skills has ever arrived. Distinguished from a character
## with every skill at zero, which is a real and different thing.
const NO_DATA_TEXT := "No skills yet."

const TOTAL_LEVEL_TEXT := "Total level: %d"
const TOTAL_XP_TEXT := "Total XP: %s"
const CLOSEST_TEXT := "Closest to levelling: %s, %s XP"
const ALL_CAPPED_TEXT := "Every skill is at the cap."
const BACK_TEXT := "< All skills"
const LEVEL_TEXT := "Level %d / %d"
const PROGRESS_TEXT := "%s / %s XP into this level"
const NEXT_LEVEL_TEXT := "Next level at %s XP  (%s to go)"
const LOCKED_TEXT := "Locked"
const UNLOCK_ROW_TEXT := "%s  (level %d)"

const DETAIL_BAR_HEIGHT := 8

## Dimmed, for an unlock the player has not reached yet. The reached ones use
## the theme's own colour, so "earned" reads as normal text and "not yet" reads
## as quieter — rather than two custom colours that both shout.
const COLOR_UNREACHED := Color(0.55, 0.58, 0.63)

var _state: SkillsState
var _settings: ClientSettings
var _body: VBoxContainer

## The skill whose sheet is open, or "" for the grid. See the class docstring
## on why this outlives a rebuild.
var _selected := ""


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


## Bind to the roster and to the player's preferences, and follow both.
##
## The SETTINGS are here because where a clicked skill's detail goes is a
## presentation choice, and this is the control that acts on it. It is read at
## click time rather than cached, so changing it in Options takes effect on the
## next click with nothing to keep in step.
func bind(state: SkillsState, settings: ClientSettings) -> void:
	_state = state
	_settings = settings
	_state.changed.connect(_rebuild)
	_rebuild()


## Rebuild wholesale, the way the inventory grid and the quest log do.
##
## `char_skills` is a snapshot, so throwing every cell away and making them
## again is the only approach that cannot desync from it. Diffing against a
## payload that is already the whole truth would be inventing a delta protocol
## on the client side, which the server refused to do for good reasons.
##
## ## `queue_free`, where the other panes use `free`
##
## [InventoryView] and [QuestsView] free immediately, and are right to: they
## rebuild from a MODEL's signal, so nothing they are destroying is mid-emit.
##
## This one also rebuilds from a CELL's signal — clicking a skill opens its
## sheet, which destroys the cell that was clicked. Freeing it there tears down
## an object while it is still emitting, which Godot reports as "was freed or
## unreferenced while a signal is being emitted" and which risks a crash rather
## than merely being untidy.
##
## The `remove_child` above is what makes the deferred free safe: the container
## is empty before the replacements arrive, so the two generations never
## coexist in the layout — which is the actual thing `free()` was chosen for
## next door, and it is preserved here.
func _rebuild() -> void:
	if _state == null:
		return

	for child: Node in _body.get_children():
		_body.remove_child(child)
		child.queue_free()

	if not _state.has_data:
		_body.add_child(_label(NO_DATA_TEXT, &"RowKey"))
		return

	# A selection whose skill is no longer sent falls back to the grid rather
	# than drawing an empty sheet. That is not hypothetical: a skill removed
	# from the server disappears from the roster, and the pane must not be
	# left showing a page about it.
	var row := _state.row_for(_selected)

	if _selected.is_empty() or row.is_empty():
		_selected = ""
		_build_grid()
		return

	_build_detail(row)


# ─── The grid ────────────────────────────────────────────────────────────────

## One band per category, in the server's order, then the roster's totals.
##
## Grouped by walking `categories` rather than by grouping the rows here: the
## server already decided both the category order and the order within each,
## and a second opinion would be the place the two screens start disagreeing.
func _build_grid() -> void:
	for category: String in _state.categories:
		_body.add_child(_label(category, &"PanelHeading"))

		var grid := GridContainer.new()
		grid.columns = COLUMNS
		grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		grid.theme_type_variation = &"SkillGrid"
		_body.add_child(grid)

		for row: Dictionary in _state.rows_in(category):
			grid.add_child(_cell(row))

	_body.add_child(HSeparator.new())
	_body.add_child(_label(
		TOTAL_LEVEL_TEXT % _state.total_level, &"PanelHeading"))
	_body.add_child(_label(
		TOTAL_XP_TEXT % _grouped(_state.total_xp), &"RowKey"))
	_body.add_child(_label(_closest_text(), &"RowKey"))


## The one fact no single skill can answer: which is nearest its next level.
##
## Named with the skill's DISPLAY name, looked up in the roster, because the
## server sends `closest` keyed by skill key — the stable identifier — and the
## name it should be shown under is already on that skill's own row.
func _closest_text() -> String:
	if _state.closest.is_empty():
		return ALL_CAPPED_TEXT

	var row := _state.row_for(str(_state.closest.get("skill_key", "")))
	var shown := str(row.get("name", _state.closest.get("skill_key", "")))

	return CLOSEST_TEXT % [
		shown, _grouped(int(_state.closest.get("remaining_xp", 0)))]


func _cell(row: Dictionary) -> SkillCell:
	var cell := _Cell.new()
	cell.bind(row)
	cell.chosen.connect(_on_chosen.bind(str(row.get("key", ""))))

	return cell


## A skill was clicked. Which answer is asked for is the player's choice.
##
## The command is sent ONLY for the modes that show the log's answer, and that
## is not an optimisation. The server cannot be asked for a skill quietly: the
## command that renders the sheet renders it into the log, which is the thing
## `pane` mode exists to avoid — so sending it "to refresh the numbers" would
## put the text on screen anyway and make the setting do nothing.
##
## Which is affordable only because the row this pane already holds is
## COMPLETE. `char_skills` ships each skill's curve and its whole unlock
## ladder, so the sheet needs no round trip; see ClientSettings.skill_detail
## for what that costs in freshness.
##
## A null `_settings` behaves as `both`, which is the shipped default rather
## than a special case — a pane bound without preferences is a programming
## error, and the recovery that shows the player the most is the right one.
func _on_chosen(command: String, skill_key: String) -> void:
	if _settings == null or _settings.skill_detail_in_log():
		command_requested.emit(command)

	if _settings != null and not _settings.skill_detail_in_pane():
		return

	_selected = skill_key
	_rebuild()


# ─── One skill's sheet ───────────────────────────────────────────────────────

## Everything the server said about one skill, in the order it said it.
func _build_detail(row: Dictionary) -> void:
	var back := Button.new()
	back.text = BACK_TEXT
	back.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	back.pressed.connect(_close_detail)
	_body.add_child(back)

	_body.add_child(_label(str(row.get("name", "")), &"PanelHeading"))
	_body.add_child(_label(LEVEL_TEXT % [
		int(row.get("level", 0)), int(row.get("max_level", 0))], &"RowValue"))

	var bar := ProgressBar.new()
	bar.custom_minimum_size = Vector2(0, DETAIL_BAR_HEIGHT)
	bar.max_value = 1.0
	bar.step = 0.001
	bar.show_percentage = false
	bar.value = SkillsState.level_fraction(row)
	_body.add_child(bar)

	_body.add_child(_label(PROGRESS_TEXT % [
		_grouped(int(row.get("current_xp", 0))),
		_grouped(int(row.get("needed_xp", 0)))], &"RowKey"))
	_body.add_child(_label(NEXT_LEVEL_TEXT % [
		_grouped(int(row.get("next_level_at", 0))),
		_grouped(int(row.get("remaining_xp", 0)))], &"RowKey"))

	if not bool(row.get("unlocked", true)):
		_body.add_child(_label(LOCKED_TEXT, &"RowValue"))

	_body.add_child(HSeparator.new())
	_body.add_child(_wrapped(str(row.get("description", ""))))

	for section: Dictionary in row.get("unlocks", []):
		_add_unlock_section(section, int(row.get("level", 0)))


## One "<Title>:" block of the unlock ladder.
##
## The server drops a section with nothing in it, so this needs no guard — a
## heading with no rows under it is a state the payload cannot express. Rows
## the player has already reached draw normally and the rest are dimmed, which
## is what makes the list a ladder rather than a catalogue.
func _add_unlock_section(section: Dictionary, level: int) -> void:
	_body.add_child(HSeparator.new())
	_body.add_child(_label(str(section.get("title", "")), &"SectionHeading"))

	for entry: Dictionary in section.get("rows", []):
		var required := int(entry.get("level", 0))
		var text := UNLOCK_ROW_TEXT % [str(entry.get("name", "")), required]
		var note := str(entry.get("note", ""))

		if not note.is_empty():
			text += " - " + note

		var label := _wrapped(text)

		if level < required:
			label.add_theme_color_override("font_color", COLOR_UNREACHED)

		_body.add_child(label)


func _close_detail() -> void:
	_selected = ""
	_rebuild()


# ─── Shared ──────────────────────────────────────────────────────────────────

## One label, styled by NAMING a variation rather than by carrying a size and a
## colour of its own.
##
## Every name passed here is declared in `ui/blackout_theme.tres` and asserted
## to exist by `test_theme.gd`, which reads this file as text.
func _label(text: String, variation: StringName) -> Label:
	var label := Label.new()
	label.text = text
	label.theme_type_variation = variation

	return label


## A label that wraps. Separate from [method _label] because wrapping needs the
## control to fill its width, and a one-line row must not.
func _wrapped(text: String) -> Label:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.theme_type_variation = &"RowKey"

	return label


## Thousands separators, because these numbers get large.
##
## Written out rather than reached for in a formatter: GDScript's `%d` has no
## grouping flag, and the alternative is the raw figure — "1204882" is a number
## a player has to count digits on.
static func _grouped(value: int) -> String:
	var digits := str(absi(value))
	var out := ""

	while digits.length() > 3:
		out = "," + digits.substr(digits.length() - 3) + out
		digits = digits.substr(0, digits.length() - 3)

	out = digits + out

	if value < 0:
		return "-" + out

	return out
