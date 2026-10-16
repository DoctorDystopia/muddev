extends SceneTree
## Phase W0 spike of DESIGN-0014, step 1 of the retarget case. Print the
## tree of the plain import, and save the bone map that the second import
## uses.
##
##     godot --headless --path . --script res://spike_retarget_setup.gd

## Profile bone -> the bone of the Quaternius rig.
const MAP := {
	"Root": "root", "Hips": "pelvis", "Spine": "spine_01", "Chest": "spine_02",
	"UpperChest": "spine_03", "Neck": "neck_01", "Head": "Head",
	"LeftShoulder": "clavicle_l", "LeftUpperArm": "upperarm_l",
	"LeftLowerArm": "lowerarm_l", "LeftHand": "hand_l",
	"RightShoulder": "clavicle_r", "RightUpperArm": "upperarm_r",
	"RightLowerArm": "lowerarm_r", "RightHand": "hand_r",
	"LeftUpperLeg": "thigh_l", "LeftLowerLeg": "calf_l", "LeftFoot": "foot_l",
	"LeftToes": "ball_l", "RightUpperLeg": "thigh_r", "RightLowerLeg": "calf_r",
	"RightFoot": "foot_r", "RightToes": "ball_r",
}


func _init() -> void:
	var scene := load("res://spike_retarget/plain.gltf") as PackedScene
	var root := scene.instantiate()
	var bone_map := BoneMap.new()

	_print_tree(root, "")
	bone_map.profile = SkeletonProfileHumanoid.new()

	for bone: String in MAP:
		bone_map.set_skeleton_bone_name(bone, MAP[bone])

	print("save: ", ResourceSaver.save(bone_map, "res://spike_retarget/bone_map.tres"))
	root.free()
	quit()


func _print_tree(node: Node, indent: String) -> void:
	print(indent, node.name, " (", node.get_class(), ")")

	for child: Node in node.get_children():
		_print_tree(child, indent + "  ")
