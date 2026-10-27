class_name FigureStances
extends RefCounted
## The stance table: the clip set that each tool type selects
## (DESIGN-0014 section 8.1, Phase W5).
##
## A figure with a spear walks with the walk clip of a spear. The tool type
## of the held item is the key. The server owns the tool types
## (`tool_type` of an `ItemDef`), and `test_figure_files.py` compares the
## keys of this file with them.
##
## ## The file
##
##     res://world/figure/stances.json
##
##     format    1
##     default   action -> clip name
##     stances   tool type -> {action -> clip name}
##
## `default` is the clip set of a figure with empty hands, and of an item
## whose tool type has no stance. A stance names only the actions that
## differ from `default`.
##
## The file is in the project, beside the clip files that it names. The
## figure workbench writes it.
##
## ## An action
##
## An action is what a figure does: [constant ACTIONS]. The client asks for
## the clip of one action. [method clip_for] gives the clip name, or "" for
## an action with no clip. A figure with no clip keeps its rest pose.
##
## ## An attack action (10/25/2026)
##
## The server names the action of each swing: the hands of the swing and its
## attack type, for example `attack_one_hand_slash` (`figure_action` of
## `blackout_combat`). The item catalog lists each action that a swing can
## name. The Clips tab shows a row for each. [method attack_clip_for] gives
## its clip. An attack action with no clip of its own plays the clip of
## [constant ACTION_ATTACK]. Thus, a new weapon needs no edit here.

## The newest format that this reader knows. It reads each older format.
const FORMAT := 1

const FILE_NAME := "stances.json"

## The stance table of the game.
const STANCES_PATH := "res://world/figure/stances.json"

## A stance table is one file. This is its key in the file store of the
## workbench.
const KEY := "stances"

## The actions that a clip set can name, in the order of the Clips tab.
const ACTION_IDLE := "idle"
const ACTION_WALK := "walk"
const ACTION_RUN := "run"
const ACTION_ATTACK := "attack"
const ACTIONS := [ACTION_IDLE, ACTION_WALK, ACTION_RUN, ACTION_ATTACK]

## The start of the name of each attack action of the server.
const ATTACK_PREFIX := ACTION_ATTACK + "_"

## A name of a tool type, of an action, or of a clip: a-z, 0-9, and _, with
## a letter first.
const NAME_PATTERN := "^[a-z][a-z0-9_]*$"

var data := {}

## Why the table does not read, or "" for a table that reads.
var error := ""


# ─── Reading and writing ────────────────────────────────────────────────────

## The stance table of a parsed file. Check [member error] after.
static func from_data(parsed: Variant) -> FigureStances:
	var table := FigureStances.new()

	if typeof(parsed) != TYPE_DICTIONARY or parsed.is_empty():
		table.error = "a stance file must hold one JSON object"
		return table

	var canonical: Dictionary = FigureJson.canonical(parsed)

	table.error = _problem(canonical)

	if table.error.is_empty():
		table.data = _normal(canonical)

	return table


## The stance table of a file text. Check [member error] after.
static func from_text(text: String) -> FigureStances:
	return from_data(FigureJson.parse(text))


## Read one stance file. Check [member error] after.
static func read_file(path := STANCES_PATH) -> FigureStances:
	var text := FileAccess.get_file_as_string(path)

	if text.is_empty():
		var refused := FigureStances.new()

		refused.error = "cannot read %s" % path
		return refused

	return from_text(text)


## The canonical text. The same table gives the same bytes.
func to_text() -> String:
	return FigureJson.to_text(data)


## Write the canonical text to an OS path. Makes the directory.
func write_file(path: String) -> Error:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())

	var file := FileAccess.open(path, FileAccess.WRITE)

	if file == null:
		return FileAccess.get_open_error()

	file.store_string(to_text())

	return OK


# ─── The facts of a stance table ────────────────────────────────────────────

func key() -> String:
	return KEY


## Action -> clip name, for a figure with no stance.
func default_set() -> Dictionary:
	return data.get("default", {})


## Tool type -> `{action -> clip name}`.
func stances() -> Dictionary:
	return data.get("stances", {})


## The tool types that have a stance, in sorted order.
func tool_types() -> PackedStringArray:
	var names := PackedStringArray(stances().keys())

	names.sort()

	return names


func has_stance(tool_type: String) -> bool:
	return stances().has(tool_type)


## The clip that one stance names for one action itself, or "". An empty
## `tool_type` is the default clip set.
func own_clip(tool_type: String, action: String) -> String:
	if tool_type.is_empty():
		return default_set().get(action, "")

	return stances().get(tool_type, {}).get(action, "")


## The clip of one action for one tool type: the clip of its stance, then
## the clip of the default clip set, then "".
func clip_for(tool_type: String, action: String) -> String:
	var clip: String = stances().get(tool_type, {}).get(action, "")

	return default_set().get(action, "") if clip.is_empty() else clip


## The clip of one attack action for one tool type: the clip of the action
## ([method clip_for]), then the clip of [constant ACTION_ATTACK], then "".
func attack_clip_for(tool_type: String, action: String) -> String:
	var clip := clip_for(tool_type, action)

	return clip_for(tool_type, ACTION_ATTACK) if clip.is_empty() else clip


## True for the name of an attack action of the server: it starts with
## [constant ATTACK_PREFIX]. The stance check compares each such action of
## the table with the item catalog.
static func is_attack_action(action: String) -> bool:
	return action.begins_with(ATTACK_PREFIX)


## The clip set of one tool type: action -> clip name, for each action that
## has a clip.
func clip_set_of(tool_type: String) -> Dictionary:
	var clips: Dictionary = default_set().duplicate()

	clips.merge(stances().get(tool_type, {}), true)

	return clips


## The tool type whose stance a figure takes. The list `worn_types` holds
## the tool type of each worn item, in the order of the slots. The first one
## with a stance decides. "" for the default clip set.
func stance_of(worn_types: Array) -> String:
	for tool_type: String in worn_types:
		if has_stance(tool_type):
			return tool_type

	return ""


## Each clip name that the table names, in sorted order.
func clip_names() -> PackedStringArray:
	var found := {}

	for clip: String in default_set().values():
		found[clip] = true

	for tool_type: String in stances():
		for clip: String in stances()[tool_type].values():
			found[clip] = true

	var names := PackedStringArray(found.keys())

	names.sort()

	return names


# ─── The form of a stance file ──────────────────────────────────────────────

## Why a parsed stance file has a bad form, or "".
static func _problem(parsed: Dictionary) -> String:
	var format: Variant = parsed.get("format")

	if typeof(format) != TYPE_INT or format < 1:
		return "a stance file needs a format number"

	if format > FORMAT:
		return "format %d is newer than this reader (format %d)" % [format, FORMAT]

	if typeof(parsed.get("stances", {})) != TYPE_DICTIONARY:
		return "stances must be a table"

	var problem := _set_problem(parsed.get("default", {}), "the default clip set")
	var plain := RegEx.create_from_string(NAME_PATTERN)

	for tool_type: String in parsed.get("stances", {}):
		if not problem.is_empty():
			break

		if plain.search(tool_type) == null:
			return "the tool type %s must use only a-z, 0-9, and _" % tool_type

		problem = _set_problem(parsed["stances"][tool_type], "the stance of " + tool_type)

	return problem


## Why one clip set has a bad form, or "". `what` names it for the message.
static func _set_problem(clips: Variant, what: String) -> String:
	var plain := RegEx.create_from_string(NAME_PATTERN)

	if typeof(clips) != TYPE_DICTIONARY:
		return "%s must be a table" % what

	for action: String in clips:
		if plain.search(action) == null:
			return "the action %s of %s must use only a-z, 0-9, and _" % [action, what]

		if typeof(clips[action]) != TYPE_STRING:
			return "the action %s of %s needs a clip name" % [action, what]

	return ""


## `parsed` as the writer gives it: the two tables, no action with an empty
## clip name, and no stance with no action.
static func _normal(parsed: Dictionary) -> Dictionary:
	var out := parsed.duplicate(true)

	if not out.has("default"):
		out["default"] = {}

	if not out.has("stances"):
		out["stances"] = {}

	_drop_empty(out["default"])

	for tool_type: String in out["stances"].keys():
		_drop_empty(out["stances"][tool_type])

		if out["stances"][tool_type].is_empty():
			out["stances"].erase(tool_type)

	return out


static func _drop_empty(clips: Dictionary) -> void:
	for action: String in clips.keys():
		if clips[action].is_empty():
			clips.erase(action)
