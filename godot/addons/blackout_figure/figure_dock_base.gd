@tool
class_name FigureDockBase
extends VBoxContainer
## What the Figure dock and the Gear dock share (DESIGN-0014 section 22):
## the top strip, the bar of the body type, the play bar, the budget
## line, the line of the selected item, the outfit bar, the status box,
## the folds, and the two option files.
##
## [FigureDock] puts its tabs between the outfit bar and the status box.
## [GearDock] puts its three zones there. A subclass builds the frame in
## its own order: [method _build_strip], [method _build_bar], then its own
## rows, then [method _build_status_box], and [method _connect_folds]
## last.
##
## ## The top strip
##
## The top strip is the first row of the dock (ENG-0011, item 10): Save,
## Revert, the scene of this dock, and the scene of the other dock. Save
## says how many files are unsaved. Revert asks first, and the question
## names each unsaved file. The terrain editor has the same strip.
##
## ## The bar
##
## The bar picks the body type that the dock shows. The 3D view shows each
## body type at all times (requirement A2). The bar also holds the play
## bar ([FigurePlayBar]), the budget line, and the line of the selected
## item. The outfit bar ([FigureOutfitBar]) is below it.
##
## This panel changes no figure file itself. Each control sends a signal,
## and the plugin acts.
##
## ## The options and the session
##
## Two files keep the options (requirement A11, ENG-0011 item 22):
##
## - [member config_path], the repository file, holds the budgets. Git
##   tracks it, because a budget is a rule that the team shares. The two
##   docks read one file.
## - [member session_path], under `user://`, holds the session of one dock:
##   the selected body type, the outfit, the colors and the kit of the
##   character, the row of the gear editor, the author of the last model
##   import, and the fold state of each section. Nothing tracks it.
##
## A test sets [member persist] to false, so it reads and writes no file.
## A test that checks the two files points the two paths at a scratch
## directory.

signal body_changed(body_key: String)
signal save_requested
signal reload_requested

## "Open workbench", or "Open gear editor": the scene of this dock.
signal open_requested

## The scene of the other dock.
signal other_requested

const CONFIG_PATH := "res://addons/blackout_figure/figure_editor.cfg"
const _CONFIG_SECTION := "workbench"

## The options of the repository file. Each other option is of the session.
const _SHARED_OPTIONS := ["budgets"]

## What the cost line says after a count that is over its budget.
const OVER_BUDGET := "  OVER THE BUDGET: %s."

## The height of the status box under the tabs, in pixels: about five lines.
const STATUS_HEIGHT := 100.0

## The text of the Save button with no unsaved file, and with some.
const SAVE_TEXT := "Save"
const SAVE_CHANGED_TEXT := "Save (%d changed)"

## The question before a revert. The dock builds it when the author asks,
## with the count and the names of the unsaved files.
const REVERT_QUESTION := "Read each figure file again? This drops %d unsaved file(s). " \
	+ "Undo cannot bring them back.\n\n%s"

## The first choice of the clip list of the bar: no clip plays.
const NO_CLIP := "(rest pose)"

## False in a test: the dock then reads and writes no option.
var persist := true

## The file of the shared options, and the file of the session. A subclass
## sets the session file.
var config_path := CONFIG_PATH
var session_path := ""

var _save: Button
var _revert: Button
var _body := OptionButton.new()
var _clip_list := OptionButton.new()
var _play_bar := FigurePlayBar.new()
var _cost := Label.new()
var _item_line := Label.new()
var _outfit_bar := FigureOutfitBar.new()
var _confirm_reload := ConfirmationDialog.new()
var _confirm := ConfirmationDialog.new()
var _status := Label.new()

## The names of the unsaved files, as the Save button shows them.
var _unsaved := PackedStringArray()

## What the confirmation runs on a yes.
var _confirmed := Callable()


func outfit_bar() -> FigureOutfitBar:
	return _outfit_bar


func play_bar() -> FigurePlayBar:
	return _play_bar


## The title of the tab that the dock shows, or "" for a dock with no tab.
func shown_tab() -> String:
	return ""


## Show one tab by its title. A dock with no tab does nothing.
func show_tab(_title: String) -> void:
	pass


## The body type that the dock shows, or "" for no rig.
func active_body() -> String:
	return FigureFields.text_of(_body)


## Fill the body type list. The list keeps its choice when the choice is
## in `keys`. If not, it takes the saved choice, then the first key.
func set_bodies(keys: PackedStringArray) -> void:
	var kept := active_body()

	if not kept in keys:
		kept = _saved_text("body")

	FigureFields.fill(_body, Array(keys))
	FigureFields.select_text(_body, kept)

	if _body.selected < 0 and _body.item_count > 0:
		_body.select(0)


## Select a body type. The dock sends no signal.
func select_body(body_key: String) -> void:
	FigureFields.select_text(_body, body_key)
	_save_body()


## Fill the clip list of the bar: the rest pose, then each clip. The list
## keeps its choice.
func set_clip_names(names: PackedStringArray) -> void:
	var keys: Array = [NO_CLIP]

	keys.append_array(Array(names))
	FigureFields.fill(_clip_list, keys)

	if _clip_list.selected < 0:
		_clip_list.select(0)


## The clip of the bar, or "" for the rest pose.
func chosen_clip() -> String:
	return "" if _clip_list.selected <= 0 else FigureFields.text_of(_clip_list)


## Show the cost of the selected figure against its budget: the budget line
## (use case 17). `counts` is `{parts, draws, triangles}`. `budgets` is the
## budget table of the Check tab ([FigureChecks]).
func set_cost(counts: Dictionary, budgets := {}) -> void:
	var full := FigureChecks.with_defaults(budgets)
	var over := FigureChecks.over_budget(counts, budgets)

	_cost.text = "%d part(s), %d of %d draw(s), %d of %d triangle(s)." % [counts["parts"],
		counts["draws"], full[FigureChecks.BUDGET_DRAWS], counts["triangles"],
		full[FigureChecks.BUDGET_TRIANGLES]]

	if not over.is_empty():
		_cost.text += OVER_BUDGET % ", ".join(over)


## Show the line of the selected item: the item, its slot, and what the
## figure shows for it (requirement A8).
func set_item_line(text: String) -> void:
	_item_line.text = text
	_item_line.visible = not text.is_empty()


func set_status(text: String) -> void:
	_status.text = text


## The text of the status box.
func status() -> String:
	return _status.text


## Show how many files are unsaved on the Save button. `names` holds each
## one, for the revert question.
func set_unsaved(names: PackedStringArray) -> void:
	_unsaved = names
	_save.text = SAVE_TEXT if names.is_empty() else SAVE_CHANGED_TEXT % names.size()


## Ask before a revert. The question names each unsaved file. With none,
## the dock asks nothing, and the reload runs.
func ask_reload() -> void:
	if _unsaved.is_empty():
		reload_requested.emit()
		return

	_confirm_reload.dialog_text = revert_question(_unsaved)
	_confirm_reload.popup_centered()


## Ask `question`, and run `on_yes` on a yes.
func confirm(question: String, on_yes: Callable) -> void:
	_confirmed = on_yes
	_confirm.dialog_text = question
	_confirm.popup_centered()


## The question before a revert that drops `names`.
static func revert_question(names: PackedStringArray) -> String:
	return REVERT_QUESTION % [names.size(), "\n".join(names)]


# ─── Building the frame ─────────────────────────────────────────────────────

## The top strip: Save, Revert, and the two scene buttons. `open_text`
## names the scene of this dock, and `other_text` the scene of the other
## dock.
func _build_strip(open_text: String, other_text: String) -> void:
	var strip := HFlowContainer.new()

	_save = FigureFields.button(SAVE_TEXT, save_requested.emit,
		"Write each changed figure file to the disk. Ctrl+S does the same.")
	_revert = FigureFields.button("Revert", ask_reload,
		"Read each figure file from the disk again. This drops each unsaved change.")
	strip.add_child(_save)
	strip.add_child(_revert)
	strip.add_child(FigureFields.button(open_text, open_requested.emit,
		"Open the scene of this dock, and select its node."))
	strip.add_child(FigureFields.button(other_text, other_requested.emit,
		"Open the scene of the other dock. With unsaved files, it asks to save them first."))
	add_child(strip)
	_confirm_reload.confirmed.connect(reload_requested.emit)
	add_child(_confirm_reload)
	_confirm.confirmed.connect(func() -> void:
		if _confirmed.is_valid():
			_confirmed.call())
	add_child(_confirm)


## The bar: the body type, the clip list when asked, the play bar, the
## budget line, and the item line.
func _build_bar(with_clips: bool) -> void:
	_body.item_selected.connect(func(_index: int) -> void:
		_save_body()
		body_changed.emit(active_body()))
	add_child(FigureFields.label("Body type that the dock shows"))
	add_child(_body)

	if with_clips:
		_clip_list.tooltip_text = "The clip that Play plays on each stand."
		add_child(_clip_list)

	add_child(_play_bar)
	_cost.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_cost)
	_item_line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_item_line.visible = false
	add_child(_item_line)
	add_child(_outfit_bar)


## The status sits under the tabs in a box of a fixed height, with its own
## scroll bar. A long report then cannot push the tabs off the dock.
func _build_status_box() -> void:
	var box := ScrollContainer.new()

	box.custom_minimum_size.y = STATUS_HEIGHT
	box.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_child(_status)
	add_child(box)


## A page that scrolls, with `panel` inside.
static func _scroll_page(title: String, panel: Control) -> ScrollContainer:
	var scroll := ScrollContainer.new()

	scroll.name = title
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(panel)

	return scroll


# ─── The folds ──────────────────────────────────────────────────────────────

## Each fold of the dock: key -> the fold. A subclass gives its own.
func folds() -> Dictionary:
	return {}


## Each fold keeps its state in the session file.
func _connect_folds() -> void:
	var all := folds()

	for key: String in all:
		(all[key] as FoldableContainer).folding_changed.connect(func(_folded: bool) -> void:
			save_folds(fold_states()))


## The state of each fold: key -> true for open.
func fold_states() -> Dictionary:
	var states := {}
	var all := folds()

	for key: String in all:
		states[key] = not (all[key] as FoldableContainer).folded

	return states


## Open or close each fold as `states` says. A fold that `states` does not
## name stays.
func apply_folds(states: Dictionary) -> void:
	var all := folds()

	for key: String in all:
		if states.has(key) and typeof(states[key]) == TYPE_BOOL:
			(all[key] as FoldableContainer).folded = not states[key]


## Open or close each fold as the last session left it.
func restore_folds() -> void:
	apply_folds(saved_folds())


# ─── The options file and the session file ──────────────────────────────────

## The file that holds one option: the repository file for a shared
## option, and the session file for each other one.
func _path_of(option: String) -> String:
	return config_path if option in _SHARED_OPTIONS else session_path


## One text of the options, or "".
func _saved_text(option: String) -> String:
	var config := ConfigFile.new()

	if not persist or config.load(_path_of(option)) != OK:
		return ""

	return str(config.get_value(_CONFIG_SECTION, option, ""))


## Write one text into its file, when it differs from the file.
func _save_text(option: String, text: String) -> void:
	if not persist or text == _saved_text(option):
		return

	_write(option, text)


## One table of the options, or an empty one.
func _saved_table(option: String) -> Dictionary:
	var config := ConfigFile.new()

	if not persist or config.load(_path_of(option)) != OK:
		return {}

	var table: Variant = config.get_value(_CONFIG_SECTION, option, {})

	return table if typeof(table) == TYPE_DICTIONARY else {}


## Write one table into its file, when it differs from the file.
func _save_table(option: String, table: Dictionary) -> void:
	if not persist or table == _saved_table(option):
		return

	_write(option, table)


## Write one option into its file. The file keeps each other option.
func _write(option: String, value: Variant) -> void:
	var config := ConfigFile.new()
	var path := _path_of(option)

	config.load(path)
	config.set_value(_CONFIG_SECTION, option, value)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path).get_base_dir())
	config.save(path)


func _save_body() -> void:
	_save_text("body", active_body())


## The outfit of the last session: slot -> asset key. The workbench drops
## each entry that the item catalog does not have.
func saved_outfit() -> Dictionary:
	return _saved_table("outfit")


func save_outfit(outfit: Dictionary) -> void:
	_save_table("outfit", outfit)


## The colors of the character of the last session: color role -> named
## color.
func saved_figure_colors() -> Dictionary:
	return _saved_table("figure_colors")


func save_figure_colors(colors: Dictionary) -> void:
	_save_table("figure_colors", colors)


## The kit of the character of the last session: kit group -> the key of a
## kit part.
func saved_kit() -> Dictionary:
	return _saved_table("kit")


func save_kit(kit: Dictionary) -> void:
	_save_table("kit", kit)


## The budget table of the repository file, for the Check tab. An empty
## table for no saved budget: each budget then has its start number.
func saved_budgets() -> Dictionary:
	return _saved_table("budgets")


func save_budgets(budgets: Dictionary) -> void:
	_save_table("budgets", budgets)


## The fold state of each section of the last session: fold key -> true
## for open.
func saved_folds() -> Dictionary:
	return _saved_table("folds")


func save_folds(states: Dictionary) -> void:
	_save_table("folds", states)


## The author of the last model import, or "". The import form starts
## with it.
func saved_author() -> String:
	return _saved_text("author")


func save_author(author: String) -> void:
	_save_text("author", author)


## The row of the gear editor of the last session, or "".
func saved_row() -> String:
	return _saved_text("row")


func save_row(key: String) -> void:
	_save_text("row", key)
