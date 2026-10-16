extends SceneTree
## Phase W0 spike of DESIGN-0014, step 2 of the retarget case.
##
##     godot --headless --path . --script res://spike_retarget_check.gd
##
## `plain.gltf` and `mapped.gltf` hold the same rig and the same clip. The
## editor imported the second with a bone map to the humanoid profile. This
## script plays the clip of the second on a rig that code made from the
## profile, and compares each limb direction with the first.

const Spike := preload("res://tests/spike_figure.gd")

const CLIP := "Swing"
const SECONDS := 0.5

## A limb of the source rig, and the same limb of the profile.
const LIMBS := [
	[["upperarm_l", "lowerarm_l"], ["LeftUpperArm", "LeftLowerArm"]],
	[["lowerarm_l", "hand_l"], ["LeftLowerArm", "LeftHand"]],
	[["thigh_l", "calf_l"], ["LeftUpperLeg", "LeftLowerLeg"]],
	[["calf_l", "foot_l"], ["LeftLowerLeg", "LeftFoot"]],
	[["upperarm_r", "lowerarm_r"], ["RightUpperArm", "RightLowerArm"]],
	[["thigh_r", "calf_r"], ["RightUpperLeg", "RightLowerLeg"]],
]


func _init() -> void:
	_run.call_deferred()


func _run() -> void:
	var plain := (load("res://spike_retarget/plain.gltf") as PackedScene).instantiate()
	var mapped := (load("res://spike_retarget/mapped.gltf") as PackedScene).instantiate()

	root.add_child(plain)
	root.add_child(mapped)

	var source := _find(plain, "Skeleton3D") as Skeleton3D
	var renamed := _find(mapped, "Skeleton3D") as Skeleton3D
	var player := _find(mapped, "AnimationPlayer") as AnimationPlayer
	var clip := player.get_animation(CLIP)

	print("SPIKE_FACT mapped skeleton: ", renamed.name, ", bones ", renamed.get_bone_count())
	print("SPIKE_FACT the import renamed the bones: ", renamed.find_bone("LeftUpperArm") >= 0)
	print("SPIKE_FACT tracks of the mapped clip: ", clip.get_track_count())

	for track in clip.get_track_count():
		print("SPIKE_FACT track ", track, ": ", clip.track_get_path(track),
			" type ", clip.track_get_type(track))

	# The rig that code makes, with the clip of the mapped import.
	var rig := Spike.rig_from_profile("body_1")
	var figure := Spike.build_merged(rig, Spike.mannequin_parts(rig), Spike.figure_material())
	var library := AnimationLibrary.new()
	var copy := clip.duplicate() as Animation

	for track in copy.get_track_count():
		var bone := String(copy.track_get_path(track)).get_slice(":", 1)

		copy.track_set_path(track, "%s:%s" % [Spike.SKELETON_NAME, bone])

	library.add_animation(CLIP, copy)
	root.add_child(figure)

	var target := figure.get_node(Spike.SKELETON_NAME) as Skeleton3D
	var target_player := Spike.add_player(figure, library)
	var source_player := _find(plain, "AnimationPlayer") as AnimationPlayer

	for each: AnimationPlayer in [source_player, target_player]:
		each.play(CLIP)
		each.seek(SECONDS, true)
		each.pause()

	await process_frame
	await process_frame

	var worst := 0.0

	for limb: Array in LIMBS:
		var from := _direction(source, limb[0][0], limb[0][1])
		var to := _direction(target, limb[1][0], limb[1][1])
		var angle := rad_to_deg(from.angle_to(to))

		worst = maxf(worst, angle)
		print("SPIKE_FACT %s: source %s, rig %s, apart %.2f degrees"
			% [limb[1][0], _short(from), _short(to), angle])

	print("SPIKE_FACT worst angle between a source limb and a rig limb: %.2f degrees" % worst)
	print("  %s  the clip of the import retarget moves the rig as the source clip moves its rig"
		% ("yes" if worst < 5.0 else "NO "))
	quit()


## The direction from one bone to the next, in the space of the skeleton.
func _direction(skeleton: Skeleton3D, from: String, to: String) -> Vector3:
	var start := skeleton.get_bone_global_pose(skeleton.find_bone(from)).origin
	var end := skeleton.get_bone_global_pose(skeleton.find_bone(to)).origin

	return (end - start).normalized()


func _short(vector: Vector3) -> String:
	return "(%.2f, %.2f, %.2f)" % [vector.x, vector.y, vector.z]


func _find(node: Node, type: String) -> Node:
	if node.is_class(type):
		return node

	for child: Node in node.get_children():
		var found := _find(child, type)

		if found != null:
			return found

	return null
