extends Node
## Tests for [FigureBuilder] (DESIGN-0014 Phase W1): one figure from a rig
## and a list of worn looks.
##
##     godot --headless --path godot res://tests/test_figure_builder.tscn
##
## Needs nothing running and no editor. It writes no file. The cases:
##
## 1. A figure has one node for each part, on the attachment of its bone.
## 2. Each part follows its bone when the pose changes.
## 3. A refresh keeps the node of each part that stays, and the node of a
##    moved shape takes the new place.
## 4. A part on a bone that the rig does not have draws nothing, and the
##    other parts draw.
## 5. A worn look hides a region of the body, and it keeps its own parts.
## 6. A new bone of the rig leaves each part on its own bone.

const TOLERANCE := 0.001
const SETTLE_FRAMES := 2

var _failures := 0


func _ready() -> void:
	_a_figure_has_one_node_for_each_part()
	await _each_part_follows_its_bone()
	_a_refresh_keeps_each_node()
	_a_missing_bone_does_not_stop_the_figure()
	_a_look_hides_a_region()
	await _a_new_bone_leaves_each_part_on_its_bone()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_builder")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _frames(count: int) -> void:
	for _frame in count:
		await get_tree().process_frame


func _rig() -> FigureRig:
	return FigureEdits.rig_from_profile("body_1")


func _a_figure_has_one_node_for_each_part() -> void:
	var rig := _rig()
	var body := FigureEdits.mannequin(rig)
	var figure := FigureBuilder.build(rig, [body])
	var skeleton := FigureBuilder.skeleton_of(figure)
	var counts := FigureBuilder.counts(figure)
	var shapes := 0

	for row: Dictionary in body.parts():
		var node := FigureBuilder.part_node(figure, body.key(), row["name"])

		shapes += row["shapes"].size()
		_expect(node != null and node.get_parent().name == row["bone"],
			"the part %s is on the attachment of %s" % [row["name"], row["bone"]])
		_expect(node != null and node.get_child_count() == row["shapes"].size(),
			"the part %s has one mesh for each shape" % row["name"])
		_expect(FigureBuilder.part_id(node) == [body.key(), row["name"]],
			"the node of %s knows its part" % row["name"])

	_expect(skeleton.name == FigureBuilder.SKELETON_NAME, "the skeleton has the clip name")
	_expect(FigureBuilder.part_nodes(figure).size() == body.parts().size(),
		"the figure has one node for each part")
	_expect(counts["parts"] == body.parts().size() and counts["draws"] == shapes,
		"the counts give the parts and the draws")
	_expect(counts["triangles"] > 0, "the counts give the triangles")
	_expect(FigureBuilder.part_id(skeleton).is_empty(), "a skeleton is not a part")
	figure.free()


func _each_part_follows_its_bone() -> void:
	var rig := _rig()
	var body := FigureEdits.mannequin(rig)
	var figure := FigureBuilder.build(rig, [body])
	var skeleton := FigureBuilder.skeleton_of(figure)
	var arm := skeleton.find_bone("LeftUpperArm")
	var worst := 0.0

	add_child(figure)
	skeleton.set_bone_pose_rotation(arm, skeleton.get_bone_pose_rotation(arm)
		* Quaternion(Vector3.RIGHT, 0.8))
	await _frames(SETTLE_FRAMES)

	for row: Dictionary in body.parts():
		var node := FigureBuilder.part_node(figure, body.key(), row["name"])
		var bone := skeleton.get_bone_global_pose(skeleton.find_bone(row["bone"]))
		var want: Transform3D = skeleton.global_transform * bone * FigureLook.part_transform(row)

		worst = maxf(worst, node.global_transform.origin.distance_to(want.origin))

	_expect(worst < TOLERANCE, "each part is on its bone in a moved pose: %f" % worst)
	figure.queue_free()


func _a_refresh_keeps_each_node() -> void:
	var rig := _rig()
	var body := FigureEdits.mannequin(rig)
	var figure := FigureBuilder.build(rig, [body])
	var head := FigureBuilder.part_node(figure, body.key(), "head")
	var mesh := head.get_child(0)
	var data: Dictionary = body.data.duplicate(true)
	var place := Transform3D(Basis.IDENTITY, Vector3(0.0, 0.05, 0.0))

	FigureBuilder.refresh(figure, rig, [body])
	_expect(FigureBuilder.part_node(figure, body.key(), "head") == head
		and head.get_child(0) == mesh, "a refresh with no change keeps the node and its mesh")

	FigureEdits.set_part_place(data, "head", place)
	FigureBuilder.refresh(figure, rig, [FigureLook.from_data(data)])
	_expect(FigureBuilder.part_node(figure, body.key(), "head") == head
		and head.transform.is_equal_approx(place) and head.get_child(0) == mesh,
		"a moved part keeps its node and its mesh")

	var shape_place := Transform3D(Basis.from_euler(Vector3(0.0, 0.5, 0.0)),
		Vector3(0.0, 0.04, 0.0))

	FigureEdits.set_shape_place(data, "head", 0, shape_place)
	FigureBuilder.refresh(figure, rig, [FigureLook.from_data(data)])
	_expect(head.get_child(0) == mesh and (mesh as Node3D).transform.is_equal_approx(shape_place)
		and FigureBuilder.shape_id(mesh) == [body.key(), "head", 0]
		and FigureBuilder.shape_node(figure, body.key(), "head", 0) == mesh,
		"a moved shape keeps its node, and the node takes the place")
	_expect(FigureBuilder.shape_id(head).is_empty()
		and FigureBuilder.shape_node(figure, body.key(), "head", 9) == null,
		"a part is no shape, and a shape index past the list gives no node")

	FigureEdits.set_shape_value(data, "head", 0, "size", Vector3(0.2, 0.3, 0.2))
	FigureEdits.set_shape_value(data, "head", 0, "top_width", 0.2)
	FigureEdits.set_shape_value(data, "head", 0, "top_depth", 0.2)
	FigureEdits.set_shape_value(data, "head", 0, "lean_z", 0.0)
	FigureBuilder.refresh(figure, rig, [FigureLook.from_data(data)])
	_expect(FigureBuilder.part_node(figure, body.key(), "head") == head
		and (head.get_child(0) as MeshInstance3D).mesh.get_aabb().size.is_equal_approx(
			Vector3(0.2, 0.3, 0.2)), "a changed shape keeps the node and gets a new mesh")

	FigureEdits.set_part_bone(data, "head", "Neck", rig)
	FigureBuilder.refresh(figure, rig, [FigureLook.from_data(data)])
	_expect(FigureBuilder.part_node(figure, body.key(), "head") == head
		and head.get_parent().name == "Neck", "a part on another bone keeps its node")
	_expect(FigureBuilder.skeleton_of(figure).get_node_or_null("Head") == null,
		"an attachment with no part goes")

	FigureEdits.remove_part(data, "head")
	FigureBuilder.refresh(figure, rig, [FigureLook.from_data(data)])
	_expect(FigureBuilder.part_node(figure, body.key(), "head") == null
		and not is_instance_valid(head), "a removed part loses its node")
	figure.free()


func _a_missing_bone_does_not_stop_the_figure() -> void:
	var rig := _rig()
	var data: Dictionary = FigureEdits.mannequin(rig).data.duplicate(true)

	data["parts"][0]["bone"] = "NoSuchBone"

	var look := FigureLook.from_data(data)
	var figure := FigureBuilder.build(rig, [look])

	_expect(look.error.is_empty(), "a look with an unknown bone reads")
	_expect(FigureBuilder.part_nodes(figure).size() == look.parts().size() - 1,
		"the figure draws each part but the one on the unknown bone")
	figure.free()


func _a_look_hides_a_region() -> void:
	var rig := _rig()
	var body := FigureEdits.mannequin(rig)
	var sleeve := {"name": "sleeve_l", "bone": "LeftUpperArm", "region": "arms",
		"shapes": [FigureEdits.new_shape(FamilyShapes.SHAPE_CYLINDER)]}
	var shirt := FigureLook.from_data({"format": 1, "key": "shirt", "hides": ["arms"],
		"parts": [sleeve]})
	var figure := FigureBuilder.build(rig, [body, shirt])
	var arms := 0

	for row: Dictionary in body.parts():
		var node := FigureBuilder.part_node(figure, body.key(), row["name"])

		if row["region"] == "arms":
			arms += 1

		_expect((node == null) == (row["region"] == "arms"),
			"the body part %s shows only outside the hidden region" % row["name"])

	_expect(arms > 0, "the body has arm parts to hide")
	_expect(FigureBuilder.part_node(figure, "shirt", "sleeve_l") != null,
		"the look keeps its own part in the region that it hides")

	FigureBuilder.refresh(figure, rig, [body])
	_expect(FigureBuilder.part_nodes(figure).size() == body.parts().size(),
		"the arms come back when the look goes")
	figure.free()


func _a_new_bone_leaves_each_part_on_its_bone() -> void:
	var rig := _rig()
	var body := FigureEdits.mannequin(rig)
	var figure := FigureBuilder.build(rig, [body])
	var skeleton := FigureBuilder.skeleton_of(figure)
	var hand := FigureBuilder.part_node(figure, body.key(), "hand_r")
	var data: Dictionary = rig.data.duplicate(true)

	add_child(figure)
	await _frames(SETTLE_FRAMES)

	# A new bone before the others changes the index of each bone after it.
	data["bones"].insert(1, {"name": "extra", "parent": "Root",
		"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0, 1.0]})

	var wider := FigureRig.from_data(data)

	FigureBuilder.refresh(figure, wider, [body])
	await _frames(SETTLE_FRAMES)
	_expect(FigureBuilder.skeleton_of(figure) == skeleton, "the figure keeps its skeleton")
	_expect(FigureBuilder.part_node(figure, body.key(), "hand_r") == hand,
		"the figure keeps each part node")

	var bone := skeleton.get_bone_global_pose(skeleton.find_bone("RightHand"))

	_expect(hand.global_transform.origin.distance_to(
		(skeleton.global_transform * bone).origin) < TOLERANCE,
		"the hand part is on the hand bone after the rig got a bone")
	figure.queue_free()
