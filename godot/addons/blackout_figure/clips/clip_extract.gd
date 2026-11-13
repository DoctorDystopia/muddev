extends SceneTree
## The second step of a clip import (DESIGN-0014, Phase W2). It runs in the
## temporary project that [FigureClipImport] makes, not in the game project:
##
##     godot --headless --path <temporary project> -s res://clip_extract.gd -- <clip> ...
##
## The editor import of that project already gave the source rig the bone
## names of a figure. This script makes each named clip of the source fit
## the rig of `res://rig.json`, and it saves the result as
## `res://out/<index>.res`, with the index of the name in the arguments. It
## also saves the name of each clip of the source as `res://out/names.json`.
##
## ## Why the script bakes each clip
##
## A track holds the rotation of a bone on its parent. A source rig can
## lack a bone that a figure has. The KayKit rig has no shoulder: its upper
## arm hangs on the chest. The same track on a figure then turns the arm
## from the wrong parent, and the arms cross the chest.
##
## Thus, the script reads each bone of the source in the space of the
## skeleton, at each step of the clip. It takes the turn of the bone from
## its rest pose, gives the same turn to the bone of the figure, and writes
## that as a rotation on the parent that the figure has. A bone of the
## figure that the source lacks stays in its rest pose. A bone of the
## source that the figure lacks still moves the bones below it.
##
## The position of the hips is a copy. The editor import already made it a
## part of the hips height.
##
## It has no class name, and nothing in the game loads it.

const SOURCE_STEM := "res://source."
const RIG_FILE := "res://rig.json"
const OUT_DIRECTORY := "res://out"
const NAMES_FILE := "res://out/names.json"
const TRACK_NODE := "%GeneralSkeleton"

## The bone whose position a clip keeps.
const SCALE_BONE := "Hips"

## The steps of a baked clip in each second: the rate of the editor import.
const STEPS_PER_SECOND := 30.0

const EXIT_NO_SOURCE := 2

## The rig of the figure: bone name -> `{parent, rest}`, with the rest
## rotation of the bone on its parent.
var _rig := {}

## The bone names of the rig, each after its parent.
var _order := PackedStringArray()


func _init() -> void:
	var scene := _source_scene()
	var player := _find(scene, "AnimationPlayer") as AnimationPlayer
	var skeleton := _find(scene, "Skeleton3D") as Skeleton3D

	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT_DIRECTORY))

	if player == null or skeleton == null or not _read_rig():
		printerr("clip_extract: the source needs a skeleton and clips, and the rig must read")
		quit(EXIT_NO_SOURCE)
		return

	var names := Array(player.get_animation_list())
	var wanted := OS.get_cmdline_user_args()
	var file := FileAccess.open(NAMES_FILE, FileAccess.WRITE)

	names.sort()
	file.store_string(JSON.stringify(names))
	file.close()

	for index in wanted.size():
		if not player.has_animation(wanted[index]):
			printerr("clip_extract: the source has no clip ", wanted[index])
			continue

		ResourceSaver.save(_baked(skeleton, player.get_animation(wanted[index])),
			"%s/%d.res" % [OUT_DIRECTORY, index])

	scene.free()
	quit(0)


# ─── The bake ───────────────────────────────────────────────────────────────

## One clip of the source, as a clip for the rig of the figure.
func _baked(source: Skeleton3D, clip: Animation) -> Animation:
	var baked := Animation.new()
	var tracks := {}
	var steps := maxi(int(round(clip.length * STEPS_PER_SECOND)), 1)

	baked.length = clip.length
	baked.step = 1.0 / STEPS_PER_SECOND

	for bone: String in _order:
		if source.find_bone(bone) >= 0:
			tracks[bone] = baked.add_track(Animation.TYPE_ROTATION_3D)
			baked.track_set_path(tracks[bone], "%s:%s" % [TRACK_NODE, bone])

	for step in steps + 1:
		var time := clip.length * step / steps
		var turns := _figure_turns(source, clip, time)

		for bone: String in tracks:
			baked.rotation_track_insert_key(tracks[bone], time, turns[bone])

	_copy_position(clip, baked)

	return baked


## The rotation of each bone of the figure on its parent, for one moment
## of a clip of the source.
func _figure_turns(source: Skeleton3D, clip: Animation, time: float) -> Dictionary:
	var turns := {}
	var in_figure := {}

	_pose(source, clip, time)

	for bone: String in _order:
		var row: Dictionary = _rig[bone]
		var above: Quaternion = in_figure.get(row["parent"], Quaternion.IDENTITY)
		var index := source.find_bone(bone)

		if index < 0:
			in_figure[bone] = above * row["rest"]
			continue

		# The turn of the source bone from its rest, in the skeleton space.
		var turn := _global(source, index, false) * _global(source, index, true).inverse()

		in_figure[bone] = (turn * row["global_rest"]).normalized()
		turns[bone] = (above.inverse() * in_figure[bone]).normalized()

	return turns


## Write the pose of a clip at `time` into the source skeleton.
func _pose(source: Skeleton3D, clip: Animation, time: float) -> void:
	source.reset_bone_poses()

	for track in clip.get_track_count():
		var path := clip.track_get_path(track)

		if path.get_subname_count() == 0:
			continue

		var bone := source.find_bone(path.get_subname(0))

		if bone < 0:
			continue

		match clip.track_get_type(track):
			Animation.TYPE_ROTATION_3D:
				source.set_bone_pose_rotation(bone, clip.rotation_track_interpolate(track, time))
			Animation.TYPE_POSITION_3D:
				source.set_bone_pose_position(bone,
					clip.position_track_interpolate(track, time) * source.motion_scale)


## The rotation of a source bone in the skeleton space, in its pose or in
## its rest. The skeleton is not in the tree, so this multiplies each bone
## above it.
func _global(source: Skeleton3D, bone: int, at_rest: bool) -> Quaternion:
	var turn := Quaternion.IDENTITY
	var walk := bone

	while walk >= 0:
		var local := source.get_bone_rest(walk).basis.get_rotation_quaternion() if at_rest \
			else source.get_bone_pose_rotation(walk)

		turn = local * turn
		walk = source.get_bone_parent(walk)

	return turn.normalized()


## Copy the position track of the hips.
func _copy_position(clip: Animation, baked: Animation) -> void:
	for track in clip.get_track_count():
		var path := clip.track_get_path(track)

		if clip.track_get_type(track) != Animation.TYPE_POSITION_3D \
				or path.get_subname_count() == 0 or path.get_subname(0) != SCALE_BONE:
			continue

		var made := baked.add_track(Animation.TYPE_POSITION_3D)

		baked.track_set_path(made, "%s:%s" % [TRACK_NODE, SCALE_BONE])

		for key in clip.track_get_key_count(track):
			baked.position_track_insert_key(made, clip.track_get_key_time(track, key),
				clip.track_get_key_value(track, key))


# ─── The rig and the source ─────────────────────────────────────────────────

## Read the rig file of the figure. Returns false for a file with no bones.
func _read_rig() -> bool:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(RIG_FILE))

	if typeof(parsed) != TYPE_DICTIONARY or typeof(parsed.get("bones")) != TYPE_ARRAY:
		return false

	for row: Dictionary in parsed["bones"]:
		var turn: Array = row["rotation"]

		_rig[row["name"]] = {"parent": row["parent"],
			"rest": Quaternion(turn[0], turn[1], turn[2], turn[3]).normalized()}

	for bone: String in _rig:
		_add_in_order(bone, 0)

	return not _order.is_empty()


## Put a bone in the order, after each bone above it. The bone also gets
## its rest rotation in the space of the figure. The count in `depth`
## stops a parent loop of a bad file.
func _add_in_order(bone: String, depth: int) -> void:
	if bone in _order or not _rig.has(bone) or depth > _rig.size():
		return

	var row: Dictionary = _rig[bone]
	var above := Quaternion.IDENTITY

	if _rig.has(row["parent"]):
		_add_in_order(row["parent"], depth + 1)
		above = _rig[row["parent"]].get("global_rest", Quaternion.IDENTITY)

	row["global_rest"] = (above * row["rest"]).normalized()
	_order.append(bone)


## The scene of the one source file of the project, or null.
func _source_scene() -> Node:
	for file_name: String in DirAccess.get_files_at("res://"):
		var path := "res://" + file_name

		if path.begins_with(SOURCE_STEM) and not path.ends_with(".import"):
			var scene := load(path) as PackedScene

			if scene != null:
				return scene.instantiate()

	return null


## The first node of one class below `node`, or null.
func _find(node: Node, type: String) -> Node:
	if node == null or node.is_class(type):
		return node

	for child: Node in node.get_children():
		var found := _find(child, type)

		if found != null:
			return found

	return null
