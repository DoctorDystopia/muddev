@tool
class_name FigureClipImport
extends RefCounted
## Builds the clips of one clip list: from a file of a source to the clip
## files of the game (DESIGN-0014, Phase W2).
##
## ## The method
##
## The retarget of the Godot editor import does the first half. It gives
## the bones of the source rig the bone names of a figure, and it turns
## each rest rotation to the rest pose of [SkeletonProfileHumanoid]. A rig
## of a figure has that rest pose.
##
## The editor import reads a file of a project only. Thus, [method build]
## makes a small temporary project, and it starts Godot two times on it:
##
## 1. `--import` imports the source file, with a bone map from the clip
##    list.
## 2. `clip_extract.gd` makes each wanted clip fit the rig of the figure,
##    and it saves each one as a file. That script tells why a clip of the
##    import does not fit as it is.
##
## [method clip_from_import] then makes each clip of the game from such a
## file. The game project never holds the source file.
##
## The temporary project is in the cache directory of the OS. A build
## removes it first, so an old file cannot reach a new clip.
##
## Nothing here needs the editor window. `tests/test_figure_clip_import.tscn`
## runs a whole build with no editor (requirement S3).
##
## Each routine here blocks until Godot ends. The plugin runs a build on a
## thread ([FigureJob]), so the editor does not freeze. A test calls the
## routines as they are.

const ADDON_DIRECTORY := "res://addons/blackout_figure"
const WORK_DIRECTORY := "blackout_figure/clip_import"

const PROJECT_FILE := "project.godot"
const PROJECT_TEXT := "config_version=5\n\n[application]\n\nconfig/name=\"Clip import\"\n"

const BONE_MAP_FILE := "bone_map.tres"
const RIG_FILE := "rig.json"
const SOURCE_STEM := "source."
const EXTRACT_SCRIPT := "clip_extract.gd"
const OUT_DIRECTORY := "out"
const NAMES_FILE := "names.json"

## The import file of the source: the retarget, with the bone map.
const IMPORT_TEXT := "[remap]\n\nimporter=\"scene\"\n\n[params]\n\n" \
	+ "_subresources={\n\"nodes\": {\n\"PATH:%s\": {\n" \
	+ "\"retarget/bone_map\": Resource(\"res://" + BONE_MAP_FILE + "\")\n}\n}\n}\n"


## Build each clip of `list` into `out_directory`, as `<clip name>.res`.
##
## The source directory is an OS path. It holds the file of the clip list.
## The rig is the rig of one body type. Each rig has the same bones and the
## same rest rotations, so a clip for one rig moves each of them.
##
## Returns `{clips, source_clips, error}`:
##
## - `clips`: the name of each clip that the build wrote.
## - `source_clips`: the name of each clip of the source.
## - `error`: "", or the reason for a build that stopped.
static func build(list: FigureClipList, source_directory: String, rig: FigureRig,
		out_directory: String) -> Dictionary:
	var result := import_source(list, source_directory, rig, list.clip_names())
	var work := work_directory(list.key())
	var rig_bones := rig.bone_names()

	if not result["error"].is_empty():
		return result

	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_directory))

	var names := list.clip_names()

	for index in names.size():
		var path := work.path_join(OUT_DIRECTORY).path_join("%d.res" % index)
		var imported := ResourceLoader.load(path, "Animation",
			ResourceLoader.CACHE_MODE_IGNORE) as Animation

		if imported == null:
			result["error"] = "the source %s has no clip %s" % [list.key(),
				list.source_clip(names[index])]
			return result

		var clip := clip_from_import(imported, rig_bones, list.loops(names[index]))

		# With no id, the writer gives the clip a random one, and the same
		# clip then gives other bytes on each build (requirement D2).
		clip.resource_scene_unique_id = names[index]

		if ResourceSaver.save(clip, clip_path(out_directory, names[index])) != OK:
			result["error"] = "cannot write %s" % clip_path(out_directory, names[index])
			return result

		result["clips"].append(names[index])

	return result


## The import step of a build. It makes the temporary project of `list`,
## and it starts Godot on it. `wanted` names each clip that the extract
## script saves. With no name, the step writes no clip. It then gives only
## the names of the clips of the source ("List source clips").
##
## Returns `{clips, source_clips, error}`, as [method build] does. `clips`
## is empty.
static func import_source(list: FigureClipList, source_directory: String, rig: FigureRig,
		wanted: PackedStringArray) -> Dictionary:
	var result := {"clips": PackedStringArray(), "source_clips": PackedStringArray(),
		"error": ""}
	var work := work_directory(list.key())

	result["error"] = _make_project(list, source_directory, rig, work)

	if result["error"].is_empty():
		result["error"] = _run_godot(work, list, wanted)

	if result["error"].is_empty():
		result["source_clips"] = _source_clips(work)

	return result


## The file of one clip in a clip directory.
static func clip_path(directory: String, clip_name: String) -> String:
	return directory.path_join(clip_name + FigureClips.CLIP_SUFFIX)


## The OS path of the temporary project of one clip list.
static func work_directory(key: String) -> String:
	return OS.get_cache_dir().path_join(WORK_DIRECTORY).path_join(key)


## The clip of the game for one clip of the editor import.
##
## It keeps the rotation track of each bone of `rig_bones`, and the position
## track of the hips. A figure has rigid parts, so no other position and no
## scale can apply. Each track gets the path of [method FigureClips.track_path].
static func clip_from_import(imported: Animation, rig_bones: PackedStringArray,
		loop: bool) -> Animation:
	var clip := Animation.new()

	clip.length = imported.length
	clip.step = imported.step
	clip.loop_mode = Animation.LOOP_LINEAR if loop else Animation.LOOP_NONE

	for track in imported.get_track_count():
		var bone := FigureClips.track_bone(imported, track)
		var type := imported.track_get_type(track)

		if not bone in rig_bones or not _keeps(type, bone):
			continue

		var made := clip.add_track(type)

		clip.track_set_path(made, FigureClips.track_path(bone))
		clip.track_set_interpolation_type(made, imported.track_get_interpolation_type(track))

		for key in imported.track_get_key_count(track):
			clip.track_insert_key(made, imported.track_get_key_time(track, key),
				imported.track_get_key_value(track, key),
				imported.track_get_key_transition(track, key))

	return clip


## True for a track that a clip of a figure keeps.
static func _keeps(type: int, bone: String) -> bool:
	if type == Animation.TYPE_ROTATION_3D:
		return true

	return type == Animation.TYPE_POSITION_3D and bone == FigureRig.SCALE_BONE


# ─── The temporary project ──────────────────────────────────────────────────

## Make the temporary project of one clip list. Returns "" or the reason.
static func _make_project(list: FigureClipList, source_directory: String,
		rig: FigureRig, work: String) -> String:
	var source := source_directory.path_join(list.file())
	var copy := work.path_join(SOURCE_STEM + list.file().get_extension().to_lower())

	if not FileAccess.file_exists(source):
		return "the source file %s is not there" % source

	_remove_tree(work)
	DirAccess.make_dir_recursive_absolute(work)

	if DirAccess.copy_absolute(source, copy) != OK:
		return "cannot copy %s to %s" % [source, copy]

	if ResourceSaver.save(_bone_map(list), work.path_join(BONE_MAP_FILE)) != OK:
		return "cannot write the bone map into %s" % work

	_write(work.path_join(PROJECT_FILE), PROJECT_TEXT)
	_write(work.path_join(RIG_FILE), rig.to_text())
	_write(copy + ".import", IMPORT_TEXT % list.skeleton())
	_write(work.path_join(EXTRACT_SCRIPT),
		FileAccess.get_file_as_string(ADDON_DIRECTORY.path_join(EXTRACT_SCRIPT)))

	return ""


## The bone map of a clip list, for the humanoid profile.
static func _bone_map(list: FigureClipList) -> BoneMap:
	var bone_map := BoneMap.new()

	bone_map.profile = SkeletonProfileHumanoid.new()

	for bone: String in list.bones():
		bone_map.set_skeleton_bone_name(bone, list.bones()[bone])

	return bone_map


## Import the temporary project, then save its wanted clips. `wanted` names
## each clip of the clip list to save. Returns "" or the reason for a run
## that did not end well.
static func _run_godot(work: String, list: FigureClipList, wanted: PackedStringArray) -> String:
	var godot := OS.get_executable_path()
	var output := []
	var extract := PackedStringArray(["--headless", "--path", work, "-s",
		"res://" + EXTRACT_SCRIPT, "--"])

	for clip_name: String in wanted:
		extract.append(list.source_clip(clip_name))

	if OS.execute(godot, ["--headless", "--path", work, "--import"], output, true) != OK:
		return "the import of %s did not end well:\n%s" % [list.file(), "\n".join(output)]

	if OS.execute(godot, extract, output, true) != OK:
		return "the clips of %s did not save:\n%s" % [list.file(), "\n".join(output)]

	return ""


## The name of each clip of one source, from its last build on this
## machine. A source with no build yet gives an empty list.
static func source_clips_of(key: String) -> PackedStringArray:
	return _source_clips(work_directory(key))


## The name of each clip of the source, from the file of `clip_extract.gd`.
static func _source_clips(work: String) -> PackedStringArray:
	var text := FileAccess.get_file_as_string(
		work.path_join(OUT_DIRECTORY).path_join(NAMES_FILE))
	var parsed: Variant = JSON.parse_string(text) if not text.is_empty() else []

	return PackedStringArray(parsed if typeof(parsed) == TYPE_ARRAY else [])


static func _write(path: String, text: String) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)

	if file != null:
		file.store_string(text)


## Delete a directory tree: files first, then directories. The import cache
## of a project is a hidden directory, so this reads the hidden ones also.
static func _remove_tree(path: String) -> void:
	var directory := DirAccess.open(path)

	if directory == null:
		return

	directory.include_hidden = true

	for child: String in directory.get_directories():
		_remove_tree(path.path_join(child))

	for file_name: String in directory.get_files():
		directory.remove(file_name)

	DirAccess.remove_absolute(path)
