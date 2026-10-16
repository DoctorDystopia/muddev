@tool
class_name FigureClipsPanel
extends VBoxContainer
## The Clips tab of the figure workbench (DESIGN-0014 section 8.6, Phase
## W2). It holds the clip library, the clearance of a held item, the
## stances, and the clip lists. The play bar is in the top bar of the dock
## ([FigurePlayBar]). Thus, a clip plays while the author edits on any tab.
##
## This panel changes no file itself. Each control sends a signal, and the
## plugin acts through [FigureWorkbench], [FigureClipEdits], and the undo
## history.
##
## "List source clips" runs the import step only (ENG-0011, item 21). It
## fills the list of the clips of a source, and it writes no clip. "Build
## the clips" asks first. The question names each clip file that the build
## writes over.
##
## ## The stances (Phase W5)
##
## A stance is the clip set that a tool type selects ([FigureStances]). The
## stance list has the default clip set, then each tool type. The table
## below it has one row for each action: the clip of that action, and a
## button that plays it. The author thus sees a greatsword through each clip
## of its stance (use case 14).
##
## A row of a tool type with no clip of its own uses the clip of the default
## clip set. The first choice of its list says which clip that is.

signal clip_chosen(clip_name: String)

## One action of one stance gets its clip. `tool_type` is "" for the
## default clip set. `clip_name` is "" for no clip of its own.
signal stance_clip_set(tool_type: String, action: String, clip_name: String)

## A play button of the stance table: play the clip of that action.
signal play_requested(clip_name: String)
signal probe_toggled(shown: bool)
signal animation_editor_requested
signal clip_set(list_key: String, clip_name: String, from: String, loop: bool)
signal clip_removed(list_key: String, clip_name: String)

## "List source clips": list the clips of the source of one clip list.
signal source_clips_requested(list_key: String)

## "Build the clips": the author asks. The plugin answers with
## [method confirm_build].
signal build_asked
signal build_requested

const CLIP_LIST_HEIGHT := 140.0

const HELP := "Select a clip, then play it with the play bar above the tabs. Each " \
	+ "body type plays the same clip. A clip comes from a clip list: a file that " \
	+ "names the clips of one source."

const EDITOR_HELP := "The Godot animation editor shows the tracks of the selected clip. " \
	+ "Save a changed clip there with Animation > Manage Animations. " \
	+ "A build writes over a clip that a clip list names."

const BUILD_QUESTION := "Build each clip of each clip list again? This writes over " \
	+ "each change that you made to such a clip in the Godot animation editor."

## The second part of the build question: the clip files that the build
## writes over.
const BUILD_OVERWRITES := "\n\nThe build writes over %d clip file(s):\n%s"
const BUILD_NEW := "\n\nNo clip file is there yet. The build writes new files only."

## What the build button says while a build runs.
const BUILD_BUSY := "A build runs now. Wait until it ends."

## The first row of the stance list.
const DEFAULT_STANCE := "(the default clip set)"

## What a row of the stance list says after a tool type that has a stance.
const HAS_STANCE := "  (has a stance)"

## The first choice of a clip list of the default clip set.
const NO_CLIP := "(no clip)"

## The first choice of a clip list of a tool type: the clip of the default
## clip set.
const OF_DEFAULT := "(of the default clip set: %s)"

const STANCE_COLUMNS := 3

var _stance := OptionButton.new()
var _stance_note := Label.new()
var _stance_grid := GridContainer.new()
var _new_action := LineEdit.new()
var _stances := FigureStances.new()

## The tool type whose stance the outfit takes, or "".
var _outfit_stance := ""

## The actions and the clip lists of the stance table, as one text.
var _shown_stance := ""

var _clips := ItemList.new()
var _probe := CheckBox.new()
var _clearance := Label.new()
var _lists := Label.new()
var _list := OptionButton.new()
var _from := OptionButton.new()
var _from_text := LineEdit.new()
var _name := LineEdit.new()
var _loop := CheckBox.new()
var _put: Button
var _take: Button
var _list_source: Button
var _build: Button
var _confirm_build := ConfirmationDialog.new()

## Clip name -> its length in seconds, for the clips that the list shows.
var _lengths := {}

## Clip list key -> the clip names of its source.
var _source_clips := {}

## Clip name -> the key of the clip list that names it.
var _owners := {}


func _init() -> void:
	add_child(FigureFields.label(HELP))
	_clips.custom_minimum_size.y = CLIP_LIST_HEIGHT
	_clips.item_selected.connect(_on_clip_selected)
	add_child(_clips)
	_probe.text = "Show a held item in each hand"
	_probe.toggled.connect(probe_toggled.emit)
	add_child(_probe)
	_clearance.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_clearance)
	add_child(FigureFields.button("Open animation editor", animation_editor_requested.emit,
		"Show the clip in the Godot animation editor: select the clip player of the " \
		+ "selected body type."))
	add_child(FigureFields.label(EDITOR_HELP))
	_build_stance_rows()
	_build_list_rows()


## Show the clips of a library. The list keeps its choice.
func set_clips(clips: AnimationLibrary) -> void:
	var kept := selected_clip()

	_clips.clear()
	_lengths.clear()

	for clip_name: String in FigureClips.names_of(clips):
		var clip := clips.get_animation(clip_name)
		var loop := ", loop" if clip.loop_mode != Animation.LOOP_NONE else ""

		_lengths[clip_name] = clip.length
		_clips.add_item("%s  (%.2f s%s)" % [clip_name, clip.length, loop])
		_clips.set_item_metadata(_clips.item_count - 1, clip_name)

	select_clip(kept)
	_show_stance()


## Show the stance table. `tool_types` names each tool type of the item
## catalog. `outfit_stance` is the tool type whose stance the outfit takes,
## or "" for the default clip set. The list keeps its choice.
func set_stances(stances: FigureStances, tool_types: PackedStringArray,
		outfit_stance := "") -> void:
	var kept := selected_stance()
	var names := Array(tool_types)

	_stances = stances
	_outfit_stance = outfit_stance

	# A stance of the file stays in the list when no item has its tool type.
	for tool_type: String in stances.tool_types():
		if not tool_type in names:
			names.append(tool_type)

	names.sort()
	_stance.clear()
	_stance.add_item(DEFAULT_STANCE)
	_stance.set_item_metadata(0, "")

	for tool_type: String in names:
		_stance.add_item(tool_type + (HAS_STANCE if stances.has_stance(tool_type) else ""))
		_stance.set_item_metadata(_stance.item_count - 1, tool_type)

	select_stance(kept)


## The tool type of the selected stance, or "" for the default clip set.
func selected_stance() -> String:
	if _stance.selected < 0:
		return ""

	return _stance.get_item_metadata(_stance.selected)


## Select the stance of one tool type. A tool type that the list does not
## have selects the default clip set. The panel sends no signal.
func select_stance(tool_type: String) -> void:
	_stance.select(0)

	for index in _stance.item_count:
		if _stance.get_item_metadata(index) == tool_type:
			_stance.select(index)

	_show_stance()


## Show the clip lists: `key -> FigureClipList`, and the clip names of each
## source, `key -> names`.
func set_clip_lists(lists: Dictionary, source_clips: Dictionary) -> void:
	var lines := PackedStringArray()
	var keys := lists.keys()

	keys.sort()
	_source_clips = source_clips
	_owners.clear()

	for key: String in keys:
		var list: FigureClipList = lists[key]
		var rows := PackedStringArray()

		for clip_name: String in list.clip_names():
			rows.append("%s from %s" % [clip_name, list.source_clip(clip_name)])
			_owners[clip_name] = key

		lines.append("%s (%s): %s" % [key, list.file(), ", ".join(rows)])

	_lists.text = "No clip list." if lines.is_empty() else "\n".join(lines)
	FigureFields.fill(_list, keys)

	if _list.selected < 0 and _list.item_count > 0:
		_list.select(0)

	_fill_source_clips()


func selected_clip() -> String:
	var chosen := _clips.get_selected_items()

	if chosen.is_empty():
		return ""

	return _clips.get_item_metadata(chosen[0])


## Select a clip of the list. The panel sends no signal.
func select_clip(clip_name: String) -> void:
	_clips.deselect_all()

	for index in _clips.item_count:
		if _clips.get_item_metadata(index) == clip_name:
			_clips.select(index)


## The length of the selected clip in seconds, or zero for no clip.
func selected_length() -> float:
	return _lengths.get(selected_clip(), 0.0)


## Show the lines of the clearance check for the selected clip.
func set_clearance(lines: PackedStringArray) -> void:
	_clearance.text = "\n".join(lines)


func probe_shown() -> bool:
	return _probe.button_pressed


## The key of the clip list of the clip form, or "".
func selected_list() -> String:
	return FigureFields.text_of(_list)


## Ask the author before a build. `files` names each clip file that the
## build writes over, and the question lists them.
func confirm_build(files: PackedStringArray) -> void:
	_confirm_build.dialog_text = BUILD_QUESTION + _overwrite_text(files)
	_confirm_build.popup_centered()


## The part of the build question that names the files.
static func _overwrite_text(files: PackedStringArray) -> String:
	if files.is_empty():
		return BUILD_NEW

	return BUILD_OVERWRITES % [files.size(), "\n".join(files)]


## A build runs now: the two build buttons are off until it ends.
func set_building(busy: bool) -> void:
	FigureFields.enable(_build, not busy, BUILD_BUSY)
	FigureFields.enable(_list_source, not busy, BUILD_BUSY)


# ─── Building the panel ─────────────────────────────────────────────────────


func _build_stance_rows() -> void:
	_stance.item_selected.connect(func(_index: int) -> void: _show_stance())
	_stance_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_stance_grid.columns = STANCE_COLUMNS
	add_child(FigureFields.label("Stances: the clip of each action, for one tool type"))
	add_child(_stance)
	add_child(_stance_note)
	add_child(_stance_grid)
	_new_action.placeholder_text = "The name of a new action, for example block"
	add_child(_new_action)
	add_child(FigureFields.button("Add action", func() -> void:
		stance_clip_set.emit(selected_stance(), _new_action.text.strip_edges(),
			selected_clip()),
		"Give the action in the field the selected clip, in the selected stance."))
	_stance.add_item(DEFAULT_STANCE)
	_stance.set_item_metadata(0, "")
	_stance.select(0)


## The actions of the stance table. Those of
## [constant FigureStances.ACTIONS] are first. Each other action of the
## selected stance and of the default clip set comes after them.
func _stance_actions() -> Array:
	var actions: Array = FigureStances.ACTIONS.duplicate()
	var more: Array = _stances.default_set().keys()

	more.append_array(_stances.stances().get(selected_stance(), {}).keys())
	more.sort()

	for action: String in more:
		if not action in actions:
			actions.append(action)

	return actions


## Show one row for each action of the selected stance: its clip list, and
## its play button. The rows stay while their content stays, so a list
## keeps the focus through a change.
func _show_stance() -> void:
	var tool_type := selected_stance()
	var actions := _stance_actions()
	var clips := _lengths.keys()
	var firsts := PackedStringArray()

	clips.sort()

	for action: String in actions:
		firsts.append(_first_choice(tool_type, action))

	var wanted := "%s|%s|%s" % [",".join(actions), ",".join(clips), ",".join(firsts)]

	if wanted != _shown_stance:
		_shown_stance = wanted

		for child: Node in _stance_grid.get_children():
			_stance_grid.remove_child(child)
			child.queue_free()

		for index in actions.size():
			_stance_grid.add_child(FigureFields.cell_label(actions[index]))
			_stance_grid.add_child(_new_stance_list(actions[index], firsts[index], clips))
			_stance_grid.add_child(FigureFields.button("Play", _play_action.bind(actions[index])))

	for index in actions.size():
		var list := _stance_grid.get_child(index * STANCE_COLUMNS + 1) as OptionButton
		var play := _stance_grid.get_child(index * STANCE_COLUMNS + 2) as Button
		var own := _stances.own_clip(tool_type, actions[index])

		FigureFields.select_text(list, firsts[index] if own.is_empty() else own)
		play.disabled = _stances.clip_for(tool_type, actions[index]).is_empty()

	_stance_note.text = "The outfit takes %s." % ("the default clip set"
		if _outfit_stance.is_empty() else "the stance of " + _outfit_stance)


## The first choice of the clip list of one action. The default clip set
## has "no clip" there. A tool type has the clip of the default clip set.
func _first_choice(tool_type: String, action: String) -> String:
	if tool_type.is_empty():
		return NO_CLIP

	var clip := _stances.own_clip("", action)

	return OF_DEFAULT % ("no clip" if clip.is_empty() else clip)


func _new_stance_list(action: String, first: String, clips: Array) -> OptionButton:
	var list := OptionButton.new()

	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_item(first)

	for clip_name: String in clips:
		list.add_item(clip_name)

	list.item_selected.connect(func(index: int) -> void:
		stance_clip_set.emit(selected_stance(), action,
			"" if index == 0 else list.get_item_text(index)))

	return list


## Play the clip that the selected stance has for one action.
func _play_action(action: String) -> void:
	var clip := _stances.clip_for(selected_stance(), action)

	select_clip(clip)
	clip_chosen.emit(clip)
	play_requested.emit(clip)


func _build_list_rows() -> void:
	_lists.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_list.item_selected.connect(func(_index: int) -> void: _fill_source_clips())
	_from.item_selected.connect(func(_index: int) -> void:
		_from_text.text = FigureFields.text_of(_from))
	_from_text.placeholder_text = "The name of the clip in the source, for example Running_A"
	_name.placeholder_text = "The name of the clip in the game, for example run"
	_loop.text = "The clip plays again from its start (a loop)"
	_confirm_build.dialog_text = BUILD_QUESTION
	_confirm_build.confirmed.connect(build_requested.emit)
	add_child(FigureFields.label("Clip lists"))
	add_child(_lists)
	add_child(FigureFields.label("Take a clip from the source of this clip list"))
	add_child(_list)
	_list_source = FigureFields.button("List source clips", func() -> void:
		source_clips_requested.emit(selected_list()),
		"Run the import step of the source of this clip list, and fill the list of " \
		+ "its clips. This writes no clip file.")
	add_child(_list_source)
	add_child(_from)
	add_child(_from_text)
	add_child(_name)
	add_child(_loop)
	_put = FigureFields.button("Put clip in list", func() -> void:
		clip_set.emit(selected_list(), _name.text.strip_edges(),
			_from_text.text.strip_edges(), _loop.button_pressed),
		"Put the clip of the fields in the clip list.")
	_take = FigureFields.button("Take clip out", func() -> void:
		clip_removed.emit(_owners.get(selected_clip(), ""), selected_clip()),
		"Take the selected clip out of its clip list.")
	_build = FigureFields.button("Build the clips", build_asked.emit,
		"Make each clip file of each clip list again. This starts Godot two times for " \
		+ "each clip list.")
	add_child(_put)
	add_child(_take)
	add_child(_build)
	add_child(_confirm_build)


## Fill the list of the clips that the source of the selected clip list
## has. It is empty until the first build of that list on this machine, or
## until "List source clips".
func _fill_source_clips() -> void:
	var names: PackedStringArray = _source_clips.get(FigureFields.text_of(_list),
		PackedStringArray())

	FigureFields.fill(_from, Array(names))
	_from.visible = not names.is_empty()
	_from.select(-1)


func _on_clip_selected(_index: int) -> void:
	clip_chosen.emit(selected_clip())
