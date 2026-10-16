class_name FigureClips
extends RefCounted
## The clip library of each figure, and the player that moves one figure
## (DESIGN-0014, Phase W2).
##
## A clip is one animation of the rig. Each clip is one file:
##
##     res://world/figure/clips/<clip name>.res
##
## The file name is the clip name. A new clip is one new file, and no table
## names it. The figure workbench builds each file from a clip list
## (`blackout/assets/figure/clips/`), and the Godot animation editor can
## change it after that.
##
## ## How a clip finds its bones
##
## Each track has the path `%GeneralSkeleton:<bone>`, as the retarget of the
## Godot editor import writes it. [FigureBuilder] gives the skeleton that
## unique name. [method player_of] puts the player on the figure node, so
## the path finds the skeleton of that figure.
##
## A clip holds a rotation for each bone, and one position: the hips. The
## hips position is a part of the hips height
## ([method FigureRig.motion_scale]). Each rig has the same bone names and
## the same rest rotations. Thus, one clip moves each body type.
##
## ## Two ways to move a figure
##
## 1. [method play] uses an [AnimationPlayer]. The game and the workbench
##    play a clip this way.
## 2. [method pose] writes the pose of one moment into a skeleton, with no
##    player and no scene tree. A check and a test read a clip this way.
##
## `tests/test_figure_clips.tscn` makes sure that the two give one pose.

const CLIP_DIRECTORY := "res://world/figure/clips"
const CLIP_SUFFIX := ".res"

## The name of the player node of a figure.
const PLAYER_NAME := "ClipPlayer"

## The library of the player that holds each clip: the library with no name.
const LIBRARY_NAME := &""

## The start of each track path, before the bone name.
const TRACK_NODE := "%" + FigureBuilder.SKELETON_NAME

## The clip library, read one time. [method forget] drops it.
static var _library: AnimationLibrary


# ─── The library ────────────────────────────────────────────────────────────

## The clip library of the game: each clip file of
## [constant CLIP_DIRECTORY].
static func library() -> AnimationLibrary:
	if _library == null:
		_library = library_from(CLIP_DIRECTORY)

	return _library


## Read the clip files again at the next [method library]. The workbench
## calls this after it builds a clip.
static func forget() -> void:
	_library = null


## A library with each clip file of one directory. The directory is a
## `res://` path, or an OS path.
static func library_from(directory: String) -> AnimationLibrary:
	var made := AnimationLibrary.new()

	for file_name: String in _clip_files(directory):
		var clip := ResourceLoader.load(directory.path_join(file_name), "Animation",
			ResourceLoader.CACHE_MODE_REPLACE) as Animation

		if clip != null:
			made.add_animation(file_name.trim_suffix(CLIP_SUFFIX), clip)

	return made


## The clip names of a library, in sorted order.
static func names_of(clips: AnimationLibrary) -> PackedStringArray:
	var names := PackedStringArray()

	for clip_name: StringName in clips.get_animation_list():
		names.append(String(clip_name))

	names.sort()

	return names


## The track path of one bone.
static func track_path(bone: String) -> NodePath:
	return NodePath("%s:%s" % [TRACK_NODE, bone])


## The bone that a track of a clip moves, or "" for a track of no bone.
static func track_bone(clip: Animation, track: int) -> String:
	var path := clip.track_get_path(track)

	if path.get_subname_count() == 0:
		return ""

	return String(path.get_subname(0))


## The bones that a clip moves, in sorted order.
static func bones_of(clip: Animation) -> PackedStringArray:
	var found := {}

	for track in clip.get_track_count():
		found[track_bone(clip, track)] = true

	found.erase("")

	var bones := PackedStringArray(found.keys())

	bones.sort()

	return bones


# ─── The player ─────────────────────────────────────────────────────────────

## The player of a figure. The first call makes it, with `clips` as its
## library. With no `clips`, the player gets the library of the game.
static func player_of(figure: Node3D, clips: AnimationLibrary = null) -> AnimationPlayer:
	var player := figure.get_node_or_null(PLAYER_NAME) as AnimationPlayer

	if player == null:
		player = AnimationPlayer.new()
		player.name = PLAYER_NAME
		figure.add_child(player)
		player.add_animation_library(LIBRARY_NAME, library() if clips == null else clips)
	elif clips != null and player.get_animation_library(LIBRARY_NAME) != clips:
		player.remove_animation_library(LIBRARY_NAME)
		player.add_animation_library(LIBRARY_NAME, clips)

	return player


## Play one clip on a figure, from its start. Returns false for a clip that
## the library of the figure does not have.
static func play(figure: Node3D, clip_name: String, speed := 1.0) -> bool:
	var player := player_of(figure)

	if not player.has_animation(clip_name):
		return false

	player.play(clip_name, -1.0, speed)

	return true


## Stop the clip of a figure, and put each bone back in its rest pose.
static func stop(figure: Node3D) -> void:
	var player := figure.get_node_or_null(PLAYER_NAME) as AnimationPlayer

	if player != null:
		player.stop()

	FigureBuilder.skeleton_of(figure).reset_bone_poses()


# ─── One moment of a clip ───────────────────────────────────────────────────

## Write the pose of a clip at `time` into a skeleton. A bone with no track
## keeps its rest. A track of a bone that the skeleton does not have does
## nothing. This needs no player and no scene tree.
static func pose(skeleton: Skeleton3D, clip: Animation, time: float) -> void:
	skeleton.reset_bone_poses()

	for track in clip.get_track_count():
		var bone := skeleton.find_bone(track_bone(clip, track))

		if bone < 0 or not clip.track_is_enabled(track):
			continue

		match clip.track_get_type(track):
			Animation.TYPE_ROTATION_3D:
				skeleton.set_bone_pose_rotation(bone,
					clip.rotation_track_interpolate(track, time))
			Animation.TYPE_POSITION_3D:
				skeleton.set_bone_pose_position(bone,
					clip.position_track_interpolate(track, time) * skeleton.motion_scale)
			Animation.TYPE_SCALE_3D:
				skeleton.set_bone_pose_scale(bone, clip.scale_track_interpolate(track, time))


## The pose of one bone in the space of its skeleton, from the pose of the
## bone and of each bone above it. A skeleton that is not in the scene tree
## gives an old answer from [method Skeleton3D.get_bone_global_pose], so a
## reader of [method pose] uses this routine.
static func global_pose(skeleton: Skeleton3D, bone: int) -> Transform3D:
	var xform := Transform3D.IDENTITY
	var walk := bone

	while walk >= 0:
		xform = skeleton.get_bone_pose(walk) * xform
		walk = skeleton.get_bone_parent(walk)

	return xform


# ─── Helpers ────────────────────────────────────────────────────────────────

## The clip files of one directory, in sorted order. An export keeps a
## `res://` directory in the pack, and only [ResourceLoader] lists it there.
static func _clip_files(directory: String) -> PackedStringArray:
	var found := PackedStringArray()
	var listed := PackedStringArray()

	if directory.begins_with("res://"):
		listed = ResourceLoader.list_directory(directory)
	elif DirAccess.dir_exists_absolute(directory):
		listed = DirAccess.get_files_at(directory)

	for file_name: String in listed:
		if file_name.ends_with(CLIP_SUFFIX):
			found.append(file_name)

	found.sort()

	return found
