extends RefCounted
## The library of the Phase W0 spike of DESIGN-0014, the figure workbench.
##
## A spike answers questions and ships nothing. Phase W1 replaces this file
## with the real classes in `res://world/figure/`. Until then, the two scenes
## beside it use it: `spike_figure_checks.tscn` (headless) and
## `spike_figure_bench.tscn` (a window, or the web export).
##
## It has no `class_name`, so the project needs no new import. A caller
## preloads it.
##
## ## What it builds
##
## - A rig: a dictionary of bones, as the rig file of DESIGN-0014 section 8.1.
##   [method rig_from_profile] makes one from [SkeletonProfileHumanoid].
## - A part: one rigid mesh on one bone. A part comes from a shape list (the
##   vocabulary of [FamilyShapes]) or from a model.
## - A figure, in two versions. [method build_attached] puts each part below a
##   [BoneAttachment3D]. [method build_merged] makes one mesh for the figure,
##   with each vertex on its one bone and each color in the vertex colors.
## - A walk clip that moves each rig with the same tracks.

const _Const := preload("res://autoload/blackout_constants.gd")

## The profile groups that the rig leaves out: the fingers and the face.
const SKIPPED_GROUPS := ["LeftHand", "RightHand", "Face"]

## The sockets: the bones that carry gear and no body part. Each row is the
## parent bone and the position on that parent.
const SOCKETS := {
	"hand_r": ["RightHand", Vector3(0.0, 0.07, 0.0)],
	"hand_l": ["LeftHand", Vector3(0.0, 0.07, 0.0)],
	"head_top": ["Head", Vector3(0.0, 0.14, 0.0)],
	"back": ["UpperChest", Vector3(0.0, 0.0, -0.12)],
	"neck_front": ["Neck", Vector3(0.0, 0.0, 0.07)],
	"finger_r": ["RightHand", Vector3(0.0, 0.1, 0.02)],
	"finger_l": ["LeftHand", Vector3(0.0, 0.1, 0.02)],
	"hip_r": ["Hips", Vector3(-0.13, 0.0, 0.0)],
}

## The body of the mannequin. Each row is a bone, the bone that ends its
## part, and the radius of the part.
const BODY := [
	["Hips", "", 0.105],
	["Spine", "Chest", 0.1],
	["Chest", "UpperChest", 0.11],
	["UpperChest", "Neck", 0.12],
	["Neck", "Head", 0.04],
	["Head", "", 0.1],
	["LeftUpperArm", "LeftLowerArm", 0.042],
	["LeftLowerArm", "LeftHand", 0.036],
	["LeftHand", "", 0.04],
	["RightUpperArm", "RightLowerArm", 0.042],
	["RightLowerArm", "RightHand", 0.036],
	["RightHand", "", 0.04],
	["LeftUpperLeg", "LeftLowerLeg", 0.062],
	["LeftLowerLeg", "LeftFoot", 0.05],
	["LeftFoot", "LeftToes", 0.04],
	["RightUpperLeg", "RightLowerLeg", 0.062],
	["RightLowerLeg", "RightFoot", 0.05],
	["RightFoot", "RightToes", 0.04],
]

## The bones whose length changes with the limb scale of a rig.
const LIMB_WORDS := ["Arm", "Hand", "Leg", "Foot", "Toes"]

## The swing of the walk clip: a bone, its angle in radians, and its phase.
const WALK_SWINGS := [
	["LeftUpperLeg", 0.55, 0.0],
	["RightUpperLeg", 0.55, PI],
	["LeftLowerLeg", -0.35, 0.0],
	["RightLowerLeg", -0.35, PI],
	["LeftUpperArm", 0.4, PI],
	["RightUpperArm", 0.4, 0.0],
]

## The rest pose is a T-pose. The walk clip turns each upper arm down by this
## angle, about the X axis of the bone.
const ARM_DROPS := {"LeftUpperArm": 1.25, "RightUpperArm": 1.25}

const WALK_CLIP := "walk"
const WALK_SECONDS := 1.0
const WALK_KEYS := 8
const WALK_BOB := 0.02

const SKELETON_NAME := "Skeleton3D"
const PLAYER_NAME := "AnimationPlayer"
const MERGED_NAME := "Merged"

## The digits that a rig file keeps of each number.
const ROUND_STEP := 0.00001

const SEGMENTS := 8
const WEIGHTS_PER_VERTEX := 4

## The rings of a plain shape with [member light_shapes] on.
const LIGHT_SPHERE_RINGS := 4
const LIGHT_CYLINDER_RINGS := 1
const LIGHT_TORUS_SEGMENTS := 6

## With this on, a shape list draws with few triangles. The mannequin then
## has the triangle count of a low-poly figure, not about 12,700.
static var light_shapes := false

## The box that the engine uses to cull a merged figure. A skinned mesh has
## the box of its rest pose, so a moved limb can leave it.
const FIGURE_BOUNDS := AABB(Vector3(-1.2, -0.2, -1.2), Vector3(2.4, 2.4, 2.4))


# ─── The rig ────────────────────────────────────────────────────────────────

## A rig from the humanoid profile of Godot, with the sockets.
##
## `limb_scale` changes the length of each arm and leg bone, and the height
## of the hips. It changes no rest rotation. Thus, two rigs with different
## values share one clip.
static func rig_from_profile(key: String, limb_scale := 1.0) -> Dictionary:
	var profile := SkeletonProfileHumanoid.new()
	var bones := []

	for index in profile.bone_size:
		if String(profile.get_group(index)) in SKIPPED_GROUPS:
			continue

		var bone_name := String(profile.get_bone_name(index))
		var pose := profile.get_reference_pose(index)
		var position := pose.origin

		if _is_limb(bone_name) or bone_name == "Hips":
			position *= limb_scale

		bones.append(_bone_row(bone_name, String(profile.get_bone_parent(index)),
			position, pose.basis.get_rotation_quaternion()))

	for socket: String in SOCKETS:
		var row: Array = SOCKETS[socket]

		bones.append(_bone_row(socket, row[0], row[1], Quaternion.IDENTITY))

	return {
		"format": 1,
		"key": key,
		"bones": bones,
		"sockets": SOCKETS.keys(),
		"motion_scale": limb_scale,
	}


## The text of a rig file: sorted keys, so the same rig gives the same bytes.
static func rig_to_text(rig: Dictionary) -> String:
	return JSON.stringify(rig, "\t", true)


## The rig of a rig file text, or an empty dictionary for a bad text.
static func rig_from_text(text: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(text)

	if typeof(parsed) != TYPE_DICTIONARY:
		return {}

	# Each number of a parsed text is a float. The format number is an
	# integer in the file, so the reader gives it back as one.
	parsed["format"] = int(parsed.get("format", 0))

	return parsed


## A skeleton in the rest pose of a rig.
static func skeleton_from_rig(rig: Dictionary) -> Skeleton3D:
	var skeleton := Skeleton3D.new()

	skeleton.name = SKELETON_NAME

	for bone: Dictionary in rig["bones"]:
		skeleton.add_bone(bone["name"])

	for bone: Dictionary in rig["bones"]:
		var index := skeleton.find_bone(bone["name"])
		var parent := skeleton.find_bone(bone["parent"])

		if parent >= 0:
			skeleton.set_bone_parent(index, parent)

		skeleton.set_bone_rest(index, _rest_of(bone))

	skeleton.reset_bone_poses()
	skeleton.motion_scale = float(rig.get("motion_scale", 1.0))

	return skeleton


static func _rest_of(bone: Dictionary) -> Transform3D:
	var position: Array = bone["position"]
	var rotation: Array = bone["rotation"]
	var turn := Quaternion(rotation[0], rotation[1], rotation[2], rotation[3])

	return Transform3D(Basis(turn.normalized()),
		Vector3(position[0], position[1], position[2]))


static func _bone_row(bone_name: String, parent: String, position: Vector3,
		rotation: Quaternion) -> Dictionary:
	return {
		"name": bone_name,
		"parent": parent,
		"position": [snappedf(position.x, ROUND_STEP),
			snappedf(position.y, ROUND_STEP), snappedf(position.z, ROUND_STEP)],
		"rotation": [snappedf(rotation.x, ROUND_STEP),
			snappedf(rotation.y, ROUND_STEP), snappedf(rotation.z, ROUND_STEP),
			snappedf(rotation.w, ROUND_STEP)],
	}


static func _is_limb(bone_name: String) -> bool:
	for word: String in LIMB_WORDS:
		if bone_name.contains(word):
			return true

	return false


# ─── The parts ──────────────────────────────────────────────────────────────

## The parts of a dressed mannequin: the body, then the gear.
##
## Each part is `{bone, soup, xform}`. `sword` is the node of a model for the
## right hand. With no node, a shape list draws the sword.
static func mannequin_parts(rig: Dictionary, sword: Node3D = null) -> Array:
	var parts := []
	var lengths := _bone_lengths(rig)

	for row: Array in BODY:
		var length: float = lengths.get(row[1], 0.0)

		parts.append(_shape_part(row[0], _body_shapes(row[0], length, row[2])))

	for row: Array in _gear_rows():
		parts.append(_shape_part(row[0], row[1]))

	if sword != null:
		parts.append({"bone": "hand_r", "soup": soup_of_node(sword),
			"xform": _sword_xform(sword)})
	else:
		parts.append(_shape_part("hand_r",
			FamilyShapes.parts_for(_Const.ITEM_FAMILY_WEAPON),
			Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * 0.9),
				Vector3(0.0, 0.0, 0.3))))

	return parts


## A soup of the plain shapes of one shape list: the arrays of one surface,
## with each color in the vertex colors.
static func soup_of_shapes(shapes: Array) -> Dictionary:
	var soup := new_soup()

	for shape: Dictionary in shapes:
		var instance := MeshBuilder.build_part(shape)
		var color := MeshPalette.color_of(str(shape.get("color", MeshPalette.GENERIC)))

		if light_shapes:
			_lighten(instance.mesh)

		append_arrays(soup, instance.mesh.get_mesh_arrays(), instance.transform,
			color, -1)
		instance.free()

	return soup


## A soup of each mesh below the node of a model. A vertex keeps its own
## color. With no vertex color, it takes the albedo of its material.
static func soup_of_node(node: Node3D) -> Dictionary:
	var soup := new_soup()

	for instance: MeshInstance3D in _mesh_instances(node):
		var xform := _xform_below(node, instance)

		for surface in instance.mesh.get_surface_count():
			var material := instance.get_active_material(surface) as BaseMaterial3D
			var color := Color.WHITE if material == null else material.albedo_color

			append_arrays(soup, instance.mesh.surface_get_arrays(surface), xform,
				color, -1)

	return soup


## Give a plain shape the fewest rings that keep its form. A sphere of
## [MeshBuilder] has 32 rings, which is 512 triangles for a joint cap.
static func _lighten(mesh: Mesh) -> void:
	if mesh is SphereMesh:
		(mesh as SphereMesh).rings = LIGHT_SPHERE_RINGS
	elif mesh is CylinderMesh:
		(mesh as CylinderMesh).rings = LIGHT_CYLINDER_RINGS
	elif mesh is TorusMesh:
		(mesh as TorusMesh).ring_segments = LIGHT_TORUS_SEGMENTS


static func new_soup() -> Dictionary:
	return {
		"vertices": PackedVector3Array(),
		"normals": PackedVector3Array(),
		"colors": PackedColorArray(),
		"bones": PackedInt32Array(),
		"indices": PackedInt32Array(),
	}


## Add the arrays of one surface to a soup, moved by `xform`. `bone` is the
## one bone of each vertex, or -1 for a soup that has no bones.
static func append_arrays(soup: Dictionary, arrays: Array, xform: Transform3D,
		color: Color, bone: int) -> void:
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: Variant = arrays[Mesh.ARRAY_NORMAL]
	var colors: Variant = arrays[Mesh.ARRAY_COLOR]
	var indices: Variant = arrays[Mesh.ARRAY_INDEX]
	var base: int = soup["vertices"].size()
	var normal_basis := xform.basis.inverse().transposed()

	for index in vertices.size():
		soup["vertices"].append(xform * vertices[index])
		soup["normals"].append(Vector3.UP if normals == null
			else (normal_basis * normals[index]).normalized())
		soup["colors"].append(color if colors == null else colors[index])

		if bone >= 0:
			soup["bones"].append(bone)

	if indices == null:
		for index in vertices.size():
			soup["indices"].append(base + index)
	else:
		for index: int in indices:
			soup["indices"].append(base + index)


## Add one soup to another, moved by `xform`, with each vertex on `bone`.
static func append_soup(soup: Dictionary, other: Dictionary, xform: Transform3D,
		bone: int) -> void:
	var arrays := []

	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = other["vertices"]
	arrays[Mesh.ARRAY_NORMAL] = other["normals"]
	arrays[Mesh.ARRAY_COLOR] = other["colors"]
	arrays[Mesh.ARRAY_INDEX] = other["indices"]
	append_arrays(soup, arrays, xform, Color.WHITE, bone)


## The mesh of a soup: one surface. A soup with bones gives a skinned mesh
## with full weight on the one bone of each vertex.
static func mesh_of_soup(soup: Dictionary) -> ArrayMesh:
	var arrays := []
	var mesh := ArrayMesh.new()

	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = soup["vertices"]
	arrays[Mesh.ARRAY_NORMAL] = soup["normals"]
	arrays[Mesh.ARRAY_COLOR] = soup["colors"]
	arrays[Mesh.ARRAY_INDEX] = soup["indices"]

	if not soup["bones"].is_empty():
		arrays[Mesh.ARRAY_BONES] = _bone_array(soup["bones"])
		arrays[Mesh.ARRAY_WEIGHTS] = _weight_array(soup["bones"].size())

	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)

	return mesh


## The one material of a figure: the vertex color is the albedo.
static func figure_material() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()

	material.vertex_color_use_as_albedo = true
	material.roughness = 0.85

	return material


static func _bone_array(bones: PackedInt32Array) -> PackedInt32Array:
	var out := PackedInt32Array()

	out.resize(bones.size() * WEIGHTS_PER_VERTEX)

	for index in bones.size():
		out[index * WEIGHTS_PER_VERTEX] = bones[index]

	return out


static func _weight_array(count: int) -> PackedFloat32Array:
	var out := PackedFloat32Array()

	out.resize(count * WEIGHTS_PER_VERTEX)

	for index in count:
		out[index * WEIGHTS_PER_VERTEX] = 1.0

	return out


static func _shape_part(bone: String, shapes: Array,
		xform := Transform3D.IDENTITY) -> Dictionary:
	return {"bone": bone, "soup": soup_of_shapes(shapes), "xform": xform}


## The shapes of one body part. A limb is a cylinder along the bone, with a
## round cap on its joint. The cap reaches into the part before it, so a bent
## joint shows no gap.
static func _body_shapes(bone: String, length: float, radius: float) -> Array:
	var role := MeshPalette.CHARACTER

	if bone == "Head":
		return [{"shape": FamilyShapes.SHAPE_SPHERE, "radius": radius,
			"segments": SEGMENTS, "offset": Vector3(0.0, 0.09, 0.0), "color": role}]

	if length <= 0.0:
		return [{"shape": FamilyShapes.SHAPE_SPHERE, "radius": radius,
			"segments": SEGMENTS, "color": role}]

	return [
		{"shape": FamilyShapes.SHAPE_CYLINDER, "radius": radius, "height": length,
			"segments": SEGMENTS, "offset": Vector3(0.0, length * 0.5, 0.0),
			"color": role},
		{"shape": FamilyShapes.SHAPE_SPHERE, "radius": radius * 1.05,
			"segments": SEGMENTS, "color": role},
	]


## The gear of the mannequin: a bone and a shape list for each worn item.
static func _gear_rows() -> Array:
	var steel := MeshPalette.STEEL
	var rust := MeshPalette.RUST
	var gold := MeshPalette.GOLD
	var boot := [{"shape": FamilyShapes.SHAPE_BOX, "size": Vector3(0.1, 0.16, 0.1),
		"offset": Vector3(0.0, 0.06, 0.0), "color": rust}]
	var ring := [{"shape": FamilyShapes.SHAPE_TORUS, "inner": 0.012,
		"outer": 0.022, "segments": SEGMENTS, "color": gold}]

	return [
		["Head", [{"shape": FamilyShapes.SHAPE_CYLINDER, "radius": 0.115,
			"radius_top": 0.09, "height": 0.13, "segments": SEGMENTS,
			"offset": Vector3(0.0, 0.14, 0.0), "color": steel}]],
		["UpperChest", [{"shape": FamilyShapes.SHAPE_CYLINDER, "radius": 0.135,
			"radius_top": 0.15, "height": 0.2, "segments": SEGMENTS,
			"offset": Vector3(0.0, 0.06, 0.0), "color": steel}]],
		["hand_l", [{"shape": FamilyShapes.SHAPE_BOX,
			"size": Vector3(0.26, 0.32, 0.03), "color": MeshPalette.WOOD}]],
		["LeftFoot", boot],
		["RightFoot", boot],
		["neck_front", [{"shape": FamilyShapes.SHAPE_TORUS, "inner": 0.02,
			"outer": 0.035, "segments": SEGMENTS, "color": gold}]],
		["finger_r", ring],
		["finger_l", ring],
		["back", [{"shape": FamilyShapes.SHAPE_BOX,
			"size": Vector3(0.3, 0.5, 0.02), "offset": Vector3(0.0, -0.2, 0.0),
			"color": MeshPalette.GENERIC}]],
	]


## The length of each bone: the distance from its parent, by bone name.
static func _bone_lengths(rig: Dictionary) -> Dictionary:
	var lengths := {}

	for bone: Dictionary in rig["bones"]:
		var position: Array = bone["position"]

		lengths[bone["name"]] = Vector3(position[0], position[1], position[2]).length()

	return lengths


## The place of a sword model in the hand: 0.7 units long, with the blade
## along the hand.
static func _sword_xform(sword: Node3D) -> Transform3D:
	var soup := soup_of_node(sword)
	var bounds := AABB()

	for index in soup["vertices"].size():
		var vertex: Vector3 = soup["vertices"][index]

		bounds = AABB(vertex, Vector3.ZERO) if index == 0 else bounds.expand(vertex)

	var longest := maxf(bounds.size.x, maxf(bounds.size.y, bounds.size.z))
	var size := 0.7 / maxf(longest, 0.0001)
	var basis := Basis.IDENTITY.scaled(Vector3.ONE * size)

	return Transform3D(basis, -(basis * bounds.get_center()) + Vector3(0.0, 0.0, 0.3))


static func _mesh_instances(node: Node) -> Array:
	var found := []

	if node is MeshInstance3D and (node as MeshInstance3D).mesh != null:
		found.append(node)

	for child: Node in node.get_children():
		found.append_array(_mesh_instances(child))

	return found


## The transform of `node` in the space of `root`, with no scene tree.
static func _xform_below(root: Node3D, node: Node3D) -> Transform3D:
	var xform := Transform3D.IDENTITY
	var walk: Node = node

	while walk != null and walk != root:
		if walk is Node3D:
			xform = (walk as Node3D).transform * xform

		walk = walk.get_parent()

	return xform


# ─── The two figures ────────────────────────────────────────────────────────

## A figure with each part below a bone attachment. One draw for each part.
static func build_attached(rig: Dictionary, parts: Array,
		material: Material) -> Node3D:
	var figure := Node3D.new()
	var skeleton := skeleton_from_rig(rig)

	figure.add_child(skeleton)

	for part: Dictionary in parts:
		if skeleton.find_bone(part["bone"]) < 0:
			continue

		var attachment := BoneAttachment3D.new()
		var instance := MeshInstance3D.new()

		# Each figure of one look shares the mesh of a part.
		if not part.has("mesh"):
			part["mesh"] = mesh_of_soup(part["soup"])

		attachment.bone_name = part["bone"]
		instance.mesh = part["mesh"]
		instance.material_override = material
		instance.transform = part["xform"]
		attachment.add_child(instance)
		skeleton.add_child(attachment)

	return figure


## The one mesh of a figure: each part in the rest pose of the rig, with each
## vertex on the one bone of its part. A cache by the look can keep it.
static func merged_mesh(rig: Dictionary, parts: Array) -> ArrayMesh:
	var skeleton := skeleton_from_rig(rig)
	var soup := new_soup()

	for part: Dictionary in parts:
		var bone := skeleton.find_bone(part["bone"])

		if bone < 0:
			continue

		append_soup(soup, part["soup"],
			skeleton.get_bone_global_rest(bone) * part["xform"], bone)

	skeleton.free()

	return mesh_of_soup(soup)


## A figure as one mesh with one surface. Each vertex has full weight on the
## one bone of its part. `mesh` is the result of [method merged_mesh]. With
## no mesh, this routine makes it.
static func build_merged(rig: Dictionary, parts: Array, material: Material,
		mesh: ArrayMesh = null) -> Node3D:
	var figure := Node3D.new()
	var skeleton := skeleton_from_rig(rig)
	var instance := MeshInstance3D.new()

	figure.add_child(skeleton)
	instance.name = MERGED_NAME
	instance.mesh = merged_mesh(rig, parts) if mesh == null else mesh
	instance.material_override = material
	instance.skin = skeleton.create_skin_from_rest_transforms()
	instance.custom_aabb = FIGURE_BOUNDS
	skeleton.add_child(instance)
	# Since Godot 4.6 the default path is empty, and an empty path detaches
	# the mesh with no error.
	instance.skeleton = NodePath("..")

	return figure


# ─── The clip ───────────────────────────────────────────────────────────────

## A library with one walk clip. Each track holds the rest rotation of its
## bone times a swing. The two rigs share each rest rotation, so one library
## moves the two.
static func walk_library(rig: Dictionary) -> AnimationLibrary:
	var clip := Animation.new()
	var library := AnimationLibrary.new()
	var rests := {}

	for bone: Dictionary in rig["bones"]:
		rests[bone["name"]] = _rest_of(bone)

	clip.length = WALK_SECONDS
	clip.loop_mode = Animation.LOOP_LINEAR

	for swing: Array in WALK_SWINGS:
		_add_swing(clip, swing[0], rests[swing[0]].basis.get_rotation_quaternion(),
			swing[1], swing[2])

	_add_bob(clip, rests["Hips"].origin)
	library.add_animation(WALK_CLIP, clip)

	return library


## Give a figure a player that plays the walk clip of `library`.
static func add_player(figure: Node3D, library: AnimationLibrary) -> AnimationPlayer:
	var player := AnimationPlayer.new()

	player.name = PLAYER_NAME
	figure.add_child(player)
	player.add_animation_library("", library)

	return player


static func _add_swing(clip: Animation, bone: String, rest: Quaternion,
		angle: float, phase: float) -> void:
	var track := clip.add_track(Animation.TYPE_ROTATION_3D)

	clip.track_set_path(track, "%s:%s" % [SKELETON_NAME, bone])

	for key in WALK_KEYS + 1:
		var time := WALK_SECONDS * key / WALK_KEYS
		var turn := angle * sin(TAU * key / WALK_KEYS + phase)

		# An arm bone of the profile drops about its X axis, so its swing is
		# about its Z axis.
		var swing_axis := Vector3.BACK if ARM_DROPS.has(bone) else Vector3.RIGHT

		clip.rotation_track_insert_key(track, time, rest
			* Quaternion(Vector3.RIGHT, ARM_DROPS.get(bone, 0.0))
			* Quaternion(swing_axis, turn))


static func _add_bob(clip: Animation, rest: Vector3) -> void:
	var track := clip.add_track(Animation.TYPE_POSITION_3D)

	clip.track_set_path(track, "%s:Hips" % SKELETON_NAME)

	for key in WALK_KEYS + 1:
		var time := WALK_SECONDS * key / WALK_KEYS
		var lift := WALK_BOB * absf(sin(TAU * key / WALK_KEYS))

		clip.position_track_insert_key(track, time, rest + Vector3.UP * lift)
