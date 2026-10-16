@tool
class_name FigureRigEdits
extends RefCounted
## The rules of the Rig tab of the figure workbench (DESIGN-0014): a new
## rig, the bones, the sockets, the regions, the slot table, and the name
## of the other side of a bone or a part.
##
## Each routine changes the content of one rig file. The content is the
## dictionary of the `data` member of [FigureRig]. The caller gives a copy,
## and the routine changes the copy. A routine that can refuse returns the
## reason, or "". Nothing here needs the editor.
##
## ## A new rig
##
## [method rig_from_profile] makes a rig from [SkeletonProfileHumanoid]:
## each bone of the profile with no finger and no face, then the sockets.
## The limb scale changes the length of each arm bone and leg bone, and the
## height of the hips. It changes no rest rotation. Thus, each rig shares
## one clip. The motion scale of a rig is its hips height
## ([method FigureRig.motion_scale]), so it follows the limb scale. The arm
## bones do not have the places of the profile: [constant ARM_PLACES] gives
## a figure wide shoulders and short arms (DESIGN-0014 section 16).
##
## ## The sockets and the regions
##
## [method set_bone_rotation] gives a socket its rest rotation: the grip of
## a hand. The routines of a region change the regions table of a rig.
## [method name_problem] is the one name rule of every figure file, and
## each other edit script reads it here.

## The profile groups that a rig leaves out: the fingers and the face.
const SKIPPED_GROUPS := ["LeftHand", "RightHand", "Face"]

const HIPS := "Hips"

## The bones whose length changes with the limb scale of a rig.
const LIMB_WORDS := ["Arm", "Hand", "Leg", "Foot", "Toes"]

## The distance of each arm bone of a new rig from its parent, by the end
## of the bone name. The profile of Godot gives 0.05 for the upper arm and
## 0.25 for each other one. These numbers put the upper arm at the side of
## a wide chest. They also make the arm shorter. An OSRS figure has these
## proportions (Nick, 10/12/2026).
const ARM_PLACES := {"UpperArm": 0.115, "LowerArm": 0.195, "Hand": 0.19}

## The rest rotation of each hand socket on its hand bone: the grip. With
## it, the +Y axis of the socket goes out of the top of the fist, on the
## side of the thumb, and the +Z axis goes out of the back of the hand.
##
## A held item stands on the socket as it stands in the inventory: its
## length along +Y. A blade then points forward when the arm hangs, and not
## down through the leg (Nick, 10/12/2026). The two hand sockets have the
## same axes in the rest pose, as the hand slots of the KayKit rig have.
## The clips of that rig thus hold an item as their author made them.
const GRIP_R := Quaternion(0.70711, 0.70711, 0.0, 0.0)
const GRIP_L := Quaternion(0.70711, -0.70711, 0.0, 0.0)

## The sockets of a new rig: the parent bone, the position on it, and the
## rest rotation on it.
const SOCKETS := {
	"hand_r": ["RightHand", Vector3(0.0, 0.07, 0.0), GRIP_R],
	"hand_l": ["LeftHand", Vector3(0.0, 0.07, 0.0), GRIP_L],
	"head_top": ["Head", Vector3(0.0, 0.14, 0.0), Quaternion.IDENTITY],
	"back": ["UpperChest", Vector3(0.0, 0.0, -0.12), Quaternion.IDENTITY],
	"neck_front": ["Neck", Vector3(0.0, 0.0, 0.07), Quaternion.IDENTITY],
	"finger_r": ["RightHand", Vector3(0.0, 0.1, 0.02), Quaternion.IDENTITY],
	"finger_l": ["LeftHand", Vector3(0.0, 0.1, 0.02), Quaternion.IDENTITY],
	"hip_r": ["Hips", Vector3(-0.13, 0.0, 0.0), Quaternion.IDENTITY],
}

## The regions of a new rig. The hair hangs on the socket of the head top,
## so a new part on the head bone gets the `head` region.
const REGIONS := {
	"head": ["Neck", "Head"],
	"hair": ["head_top"],
	"torso": ["Hips", "Spine", "Chest", "UpperChest"],
	"arms": ["LeftShoulder", "LeftUpperArm", "LeftLowerArm",
		"RightShoulder", "RightUpperArm", "RightLowerArm"],
	"hands": ["LeftHand", "RightHand"],
	"legs": ["LeftUpperLeg", "LeftLowerLeg", "RightUpperLeg", "RightLowerLeg"],
	"feet": ["LeftFoot", "LeftToes", "RightFoot", "RightToes"],
}

## The slot table of a new rig: the default bone of each slot. The slots are
## the values of `WieldLocation` on the server, and
## `test_figure_files.py` compares the two.
const SLOTS := {
	"main_hand": "hand_r",
	"off_hand": "hand_l",
	"two_hands": "hand_r",
	"body": "UpperChest",
	"legs": "Hips",
	"head": "Head",
	"back": "back",
	"feet": "RightFoot",
	"neck": "neck_front",
	"main_hand_finger": "finger_r",
	"off_hand_finger": "finger_l",
	"ammo": "hip_r",
}

## A name of a socket or of a part: a-z, 0-9, and _, with a letter first.
const NAME_PATTERN := "^[a-z][a-z0-9_]*$"

## The two sides of a figure, at the start and at the end of a name. The
## bones of the humanoid profile start with a side. A socket and a part of
## a new body end with one ([method mirror_name]).
const SIDE_STARTS := [["Left", "Right"], ["left_", "right_"]]
const SIDE_ENDS := [["_l", "_r"], ["_left", "_right"]]


# ─── A new rig ──────────────────────────────────────────────────────────────

## A rig from the humanoid profile of Godot, with the sockets, the regions,
## and the slot table.
static func rig_from_profile(key: String, limb_scale := 1.0) -> FigureRig:
	var profile := SkeletonProfileHumanoid.new()
	var bones := []

	for index in profile.bone_size:
		if String(profile.get_group(index)) in SKIPPED_GROUPS:
			continue

		var bone_name := String(profile.get_bone_name(index))
		var pose := profile.get_reference_pose(index)
		var position := _arm_place(bone_name, pose.origin)

		if _is_limb(bone_name) or bone_name == HIPS:
			position *= limb_scale

		bones.append(_bone_row(bone_name, String(profile.get_bone_parent(index)),
			position, pose.basis.get_rotation_quaternion()))

	for socket: String in SOCKETS:
		bones.append(_bone_row(socket, SOCKETS[socket][0], SOCKETS[socket][1],
			SOCKETS[socket][2]))

	return FigureRig.from_data({
		"format": FigureRig.FORMAT,
		"key": key,
		"bones": bones,
		"sockets": SOCKETS.keys(),
		"regions": REGIONS.duplicate(true),
		"slots": SLOTS.duplicate(),
	})


static func _bone_row(bone_name: String, parent: String, position: Vector3,
		rotation: Quaternion) -> Dictionary:
	return {
		"name": bone_name,
		"parent": parent,
		"position": FigureJson.from_vector3(position),
		"rotation": FigureJson.from_quaternion(rotation),
	}


## The place of a bone of the profile on its parent. An arm bone keeps its
## direction and gets the distance of [constant ARM_PLACES].
static func _arm_place(bone_name: String, position: Vector3) -> Vector3:
	for ending: String in ARM_PLACES:
		if bone_name.ends_with(ending):
			return position.normalized() * ARM_PLACES[ending]

	return position


static func _is_limb(bone_name: String) -> bool:
	for word: String in LIMB_WORDS:
		if bone_name.contains(word):
			return true

	return false


# ─── The Rig tab ────────────────────────────────────────────────────────────

## Why `text` cannot name a socket or a part, or "".
static func name_problem(text: String) -> String:
	var pattern := RegEx.create_from_string(NAME_PATTERN)

	if pattern.search(text) == null:
		return "A name uses only a-z, 0-9, and _, with a letter first. \"%s\" does not." % text

	return ""


## Add a socket to a rig, on `parent`.
static func add_socket(rig: Dictionary, socket: String, parent: String,
		position := Vector3.ZERO) -> String:
	var problem := name_problem(socket)

	if not problem.is_empty():
		return problem

	if bone_index(rig, socket) >= 0:
		return "The rig has a bone with the name %s." % socket

	if bone_index(rig, parent) < 0:
		return "Select the parent bone of the socket first."

	rig["bones"].append(_bone_row(socket, parent, position, Quaternion.IDENTITY))
	rig["sockets"].append(socket)

	return ""


## Remove a socket from a rig. A socket that a slot or a bone uses stays.
static func remove_socket(rig: Dictionary, socket: String) -> String:
	if not socket in rig["sockets"]:
		return "%s is a bone of the body, not a socket." % socket

	for row: Dictionary in rig["bones"]:
		if row["parent"] == socket:
			return "The bone %s hangs on %s." % [row["name"], socket]

	for slot: String in rig["slots"]:
		if rig["slots"][slot] == socket:
			return "The slot %s uses %s. Give the slot another bone first." % [slot, socket]

	rig["bones"].remove_at(bone_index(rig, socket))
	rig["sockets"].erase(socket)

	for region: String in rig["regions"]:
		rig["regions"][region].erase(socket)

	return ""


## Move a bone on its parent. With `mirror`, the bone of the other side
## moves to the same place on the other side of the figure
## ([method mirror_name]).
static func set_bone_position(rig: Dictionary, bone: String, position: Vector3,
		mirror := false) -> String:
	var index := bone_index(rig, bone)

	if index < 0:
		return "The rig has no bone %s." % bone

	rig["bones"][index]["position"] = FigureJson.from_vector3(position)

	var other := bone_index(rig, mirror_name(bone))

	if mirror and other >= 0 and other != index:
		var read := FigureRig.from_data(rig)
		var place := read.global_rest_of(bone).origin * Vector3(-1.0, 1.0, 1.0)
		var parent: String = rig["bones"][other]["parent"]

		rig["bones"][other]["position"] = FigureJson.from_vector3(
			read.global_rest_of(parent).affine_inverse() * place)

	return ""


## Give a socket its rest rotation on its parent bone. The rest rotation of
## a hand socket is the grip: a held item has its length along +Y of the
## socket.
##
## A bone of the body keeps its rest rotation. Each body type has the same
## one, and one clip then moves each of them.
static func set_bone_rotation(rig: Dictionary, bone: String, rotation: Quaternion) -> String:
	var index := bone_index(rig, bone)

	if index < 0:
		return "The rig has no bone %s." % bone

	if not bone in rig["sockets"]:
		return "%s is a bone of the body. Only a socket takes a rotation, " % bone \
			+ "because each body type shares the rest rotation of each body bone."

	rig["bones"][index]["rotation"] = FigureJson.from_quaternion(rotation.normalized())

	return ""


## The name of the other side of a bone or of a part: `Left` and `Right`
## change at the start of a name, and `_l` and `_r` change at its end. A
## name with no side comes back as it is.
static func mirror_name(text: String) -> String:
	for pair: Array in SIDE_STARTS:
		for side in pair.size():
			if text.begins_with(pair[side]):
				return pair[1 - side] + text.substr(pair[side].length())

	for pair: Array in SIDE_ENDS:
		for side in pair.size():
			if text.ends_with(pair[side]):
				return text.left(text.length() - pair[side].length()) + pair[1 - side]

	return text


# ─── The Rig tab: regions ───────────────────────────────────────────────────

## Add a region to a rig, with no bone.
static func add_region(rig: Dictionary, region: String) -> String:
	var problem := name_problem(region)

	if not problem.is_empty():
		return problem

	if rig["regions"].has(region):
		return "The rig has a region with the name %s." % region

	rig["regions"][region] = []

	return ""


## Remove a region from a rig. A region that a worn look names stays:
## `users` names each such look ([method looks_in_region]).
static func remove_region(rig: Dictionary, region: String,
		users := PackedStringArray()) -> String:
	if not rig["regions"].has(region):
		return "The rig has no region %s." % region

	if not users.is_empty():
		return "%d look(s) name the region %s: %s. Give each part another region first." \
			% [users.size(), region, ", ".join(users)]

	rig["regions"].erase(region)

	return ""


## Put a bone in one region, or in no region for "". A new part on the bone
## then starts in that region.
static func set_bone_region(rig: Dictionary, bone: String, region: String) -> String:
	if bone_index(rig, bone) < 0:
		return "The rig has no bone %s." % bone

	if not region.is_empty() and not rig["regions"].has(region):
		return "The rig has no region %s." % region

	for other: String in rig["regions"]:
		rig["regions"][other].erase(bone)

	if not region.is_empty():
		rig["regions"][region].append(bone)

	return ""


## The key of each look that names one region, in sorted order: a part is
## in the region, or the look hides it. `looks` is key -> [FigureLook].
static func looks_in_region(looks: Dictionary, region: String) -> PackedStringArray:
	var found := PackedStringArray()

	for look_key: String in looks:
		var look: FigureLook = looks[look_key]
		var named: bool = region in look.hides()

		for row: Dictionary in look.parts():
			named = named or row.get("region", "") == region

		if named:
			found.append(look_key)

	found.sort()

	return found


## The key of each look that has a part on one bone, in sorted order.
## `looks` is key -> [FigureLook].
static func looks_on_bone(looks: Dictionary, bone: String) -> PackedStringArray:
	var found := PackedStringArray()

	for look_key: String in looks:
		for row: Dictionary in looks[look_key].parts():
			if row["bone"] == bone and not look_key in found:
				found.append(look_key)

	found.sort()

	return found


## Give a slot its default bone.
static func set_slot_bone(rig: Dictionary, slot: String, bone: String) -> String:
	if bone_index(rig, bone) < 0:
		return "The rig has no bone %s." % bone

	rig["slots"][slot] = bone

	return ""


## The index of one bone in the bone list of a rig, or -1.
static func bone_index(rig: Dictionary, bone: String) -> int:
	for index in rig["bones"].size():
		if rig["bones"][index]["name"] == bone:
			return index

	return -1
