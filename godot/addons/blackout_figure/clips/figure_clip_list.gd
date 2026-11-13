@tool
class_name FigureClipList
extends RefCounted
## One clip list: the file that names the clips that the figure workbench
## takes from one source (DESIGN-0014, Phase W2).
##
## A source is one download in `blackout/assets/sources/`, with its license
## in its source record. A clip list is the recipe: which file of the source
## holds the rig, how its bones map to the bones of a figure, and which of
## its clips go into the clip library. [FigureClipImport] builds the clips.
##
## ## The file
##
##     blackout/assets/figure/clips/<source id>.json
##
##     format    1
##     key       the source id, the same as the file name
##     file      the file of the source that holds the rig and its clips
##     skeleton  the path of the skeleton node in that file, after an import
##     bones     bone of a figure -> bone of the source rig
##     clips     clip name -> {from, loop, held_in}
##
## `from` is the name of the clip in the source. `loop` is true for a clip
## that plays again from its start, such as a walk.
##
## `held_in` is optional (10/25/2026). It names each slot that holds an item
## through the clip, for the clearance check ([FigureClearance]). A clip
## with no `held_in` holds an item in each hand slot. A two-handed swing
## holds one item in `two_hands`: the off hand grips that item and holds no
## item of its own.
##
## A bone of a figure with no row in `bones` keeps its rest pose in each
## clip of this list.

## The newest format that this reader knows. It reads each older format.
const FORMAT := 1

const FILE_SUFFIX := ".json"

## A clip name: a-z, 0-9, and _, with a letter first. It is a file name.
const NAME_PATTERN := "^[a-z][a-z0-9_]*$"

var data := {}

## Why the clip list does not read, or "" for one that reads.
var error := ""


# ─── Reading and writing ────────────────────────────────────────────────────

## The clip list of a parsed file. Check [member error] after.
static func from_data(parsed: Variant) -> FigureClipList:
	var list := FigureClipList.new()

	if typeof(parsed) != TYPE_DICTIONARY or parsed.is_empty():
		list.error = "a clip list file must hold one JSON object"
		return list

	var canonical: Dictionary = FigureJson.canonical(parsed)

	list.error = _problem(canonical)

	if list.error.is_empty():
		list.data = canonical

	return list


## The clip list of a file text. Check [member error] after.
static func from_text(text: String) -> FigureClipList:
	return from_data(FigureJson.parse(text))


## Read one clip list file. The key must be the file name. Check
## [member error] after.
static func read_file(path: String) -> FigureClipList:
	var text := FileAccess.get_file_as_string(path)

	if text.is_empty():
		var refused := FigureClipList.new()

		refused.error = "cannot read %s" % path
		return refused

	var list := from_text(text)
	var stem := path.get_file().trim_suffix(FILE_SUFFIX)

	if list.error.is_empty() and list.key() != stem:
		list.error = "the key %s is not the file name %s" % [list.key(), stem]

	return list


## The canonical text. The same clip list gives the same bytes.
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


# ─── The facts of a clip list ───────────────────────────────────────────────

## The source id.
func key() -> String:
	return data.get("key", "")


func file() -> String:
	return data.get("file", "")


func skeleton() -> String:
	return data.get("skeleton", "")


## Bone of a figure -> bone of the source rig.
func bones() -> Dictionary:
	return data.get("bones", {})


## Clip name -> `{from, loop}`.
func clips() -> Dictionary:
	return data.get("clips", {})


## The clip names, in sorted order.
func clip_names() -> PackedStringArray:
	var names := PackedStringArray(clips().keys())

	names.sort()

	return names


## The name that one clip has in the source.
func source_clip(clip_name: String) -> String:
	return clips().get(clip_name, {}).get("from", "")


func loops(clip_name: String) -> bool:
	return clips().get(clip_name, {}).get("loop", false)


## The slots that hold an item through one clip. A clip with no `held_in`
## gives [constant FigureClearance.HAND_SLOTS].
func held_in(clip_name: String) -> PackedStringArray:
	return PackedStringArray(clips().get(clip_name, {}).get("held_in",
		FigureClearance.HAND_SLOTS))


# ─── The form of a clip list file ───────────────────────────────────────────

## Why a parsed clip list file has a bad form, or "".
static func _problem(parsed: Dictionary) -> String:
	var format: Variant = parsed.get("format")

	if typeof(format) != TYPE_INT or format < 1:
		return "a clip list file needs a format number"

	if format > FORMAT:
		return "format %d is newer than this reader (format %d)" % [format, FORMAT]

	for key: String in ["key", "file", "skeleton"]:
		if typeof(parsed.get(key)) != TYPE_STRING or parsed[key].is_empty():
			return "a clip list file needs a %s" % key

	var bones: Variant = parsed.get("bones")

	if typeof(bones) != TYPE_DICTIONARY or bones.is_empty():
		return "bones must map a bone of a figure to a bone of the source"

	for bone: String in bones:
		if typeof(bones[bone]) != TYPE_STRING or bones[bone].is_empty():
			return "the bone %s must name one bone of the source" % bone

	return _clips_problem(parsed.get("clips", {}))


static func _clips_problem(clips: Variant) -> String:
	var pattern := RegEx.create_from_string(NAME_PATTERN)

	if typeof(clips) != TYPE_DICTIONARY:
		return "clips must map a clip name to its row"

	for clip_name: String in clips:
		var row: Variant = clips[clip_name]

		if pattern.search(clip_name) == null:
			return "the clip name %s must use only a-z, 0-9, and _, with a letter first" \
				% clip_name

		if typeof(row) != TYPE_DICTIONARY or typeof(row.get("from")) != TYPE_STRING \
				or row["from"].is_empty():
			return "the clip %s needs a from: the name of the clip in the source" % clip_name

		if typeof(row.get("loop", false)) != TYPE_BOOL:
			return "the loop of the clip %s must be true or false" % clip_name

		if not FigureJson.is_strings(row.get("held_in", [])):
			return "the held_in of the clip %s must be a list of slots" % clip_name

	return ""
