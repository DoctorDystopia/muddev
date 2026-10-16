extends Node
## Tests for the model parts of a figure (DESIGN-0014 Phase W4):
## [FigureModels], [FigureReference], the parts of a model, the fit of a
## body type, and the figure set.
##
##     godot --headless --path godot res://tests/test_figure_models.tscn
##
## Needs nothing running and no editor. It writes only into a scratch
## directory under `user://`. It reads the figure files, the clips, and the
## served `figure.json` of the repository, and it never writes one. The
## cases:
##
## 1. A reference body has one node for each part, at its place in the
##    rest pose, with one material for each color role.
## 2. A reference body that comes back as a model gives each part its
##    place again: the round trip of section 8.3.
## 3. A part with a model draws the node of its model. With no model in
##    hand, it draws its shape list.
## 4. A color role of the color table gives a surface of a model its color.
## 5. A model with new bytes draws again.
## 6. The models of a directory on disk read on the first ask.
## 7. A node gets the bone of its name, or the nearest bone.
## 8. A fit row gives a part another place on one body type only.
## 9. The fit from the bone lengths scales a part along a shorter bone.
## 10. The proof of the phase: a chainbody model hides the torso and the
##     arms on the two body types, through each clip.
## 11. The figure set reads each entry, and a bad entry stays out.
## 12. The served `figure.json` of the repository holds each rig and each
##     worn look of the repository.

const TOLERANCE := 0.001
const SAMPLES := 8
const LIMB_SCALE := 0.9

## The key of the chainbody model of the test, and of its worn look.
const CHAIN := "test_chainbody"

## The hide list of a chainbody, in the sorted order of a look file.
const HIDDEN := ["arms", "torso"]

var _failures := 0
var _scratch := ""


func _ready() -> void:
	_scratch = ProjectSettings.globalize_path("user://figure_models_test_%d"
		% Time.get_ticks_usec())

	_a_reference_body_has_each_part()
	_a_reference_body_comes_back()
	_a_part_draws_its_model()
	_a_color_role_colors_a_surface()
	_new_bytes_draw_again()
	_a_directory_reads_on_the_first_ask()
	_a_node_gets_a_bone()
	_a_fit_row_moves_one_body_type()
	_the_bone_lengths_give_a_fit()
	await _a_chainbody_hides_the_torso_and_the_arms()
	_the_figure_set_reads()
	_the_served_figure_set_is_the_repository()
	_remove_scratch(_scratch)

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_models")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _same(first: Transform3D, second: Transform3D) -> bool:
	if first.origin.distance_to(second.origin) > TOLERANCE:
		return false

	for axis in 3:
		if first.basis[axis].distance_to(second.basis[axis]) > TOLERANCE:
			return false

	return true


func _rig(key := "body_1", limb_scale := 1.0) -> FigureRig:
	return FigureEdits.rig_from_profile(key, limb_scale)


## Write the reference body of `looks` into the scratch directory, and
## return its bytes.
func _reference_bytes(rig: FigureRig, looks: Array, file_name: String) -> PackedByteArray:
	var path := _scratch.path_join(file_name)

	_expect(FigureReference.export(rig, looks, path) == OK, "the reference body writes " + path)

	return FileAccess.get_file_as_bytes(path)


## The models of the test: the slot shape of the `body` slot of a rig, as
## the model `CHAIN`. A node has the name `body__<part>`.
func _chain_models(rig: FigureRig) -> FigureModels:
	var models := FigureModels.new()
	var shell := FigureEdits.slot_shape(rig, "body")

	_expect(models.put_buffer(CHAIN, _reference_bytes(rig, [shell], CHAIN + ".glb")),
		"the chainbody model reads")

	return models


## The worn look of the chainbody: the parts of the model, and the hide
## list of a chainbody.
func _chain_look(rig: FigureRig, models: FigureModels) -> FigureLook:
	var data := {"format": FigureLook.FORMAT, "key": CHAIN}

	_expect(FigureEdits.parts_from_model(data, rig, CHAIN, models).is_empty(),
		"the parts of the chainbody come from its model")

	for region: String in HIDDEN:
		FigureEdits.set_hide(data, region, true)

	return FigureLook.from_data(data)


func _a_reference_body_has_each_part() -> void:
	var rig := _rig()
	var body := FigureEdits.mannequin(rig)
	var scene := FigureReference.scene_of(rig, [body])

	_expect(scene.name == FigureReference.ROOT_PREFIX + "body_1",
		"the root of a reference body names its body type")
	_expect(scene.get_child_count() == body.parts().size(),
		"a reference body has one node for each part")

	for row: Dictionary in body.parts():
		var node := scene.get_node_or_null(str(row["name"])) as MeshInstance3D
		var roles := {}

		for shape: Dictionary in row["shapes"]:
			roles[shape["color"]] = true

		_expect(node != null and _same(node.transform,
			rig.global_rest_of(row["bone"]) * FigureLook.part_transform(row)),
			"the node of %s is at its place in the rest pose" % row["name"])

		if node == null:
			continue

		# In the editor, the glTF writer leaves out a node with no owner. No
		# headless test runs as the editor, so this case holds the owner.
		_expect(node.owner == scene, "the node of %s has the root as its owner" % row["name"])
		_expect(node.mesh.get_surface_count() == roles.size(),
			"the node of %s has one surface for each color role" % row["name"])

		for surface in node.mesh.get_surface_count():
			_expect(roles.has(node.mesh.surface_get_material(surface).resource_name),
				"a material of %s has the name of a color role" % row["name"])

	scene.free()


func _a_reference_body_comes_back() -> void:
	var rig := _rig()
	var body := FigureEdits.mannequin(rig)
	var models := FigureModels.new()
	var back := {"format": FigureLook.FORMAT, "key": "copy"}

	_expect(not models.has("ref") and models.stamp_of("ref") == 0,
		"a model with no bytes is not in hand")
	_expect(models.put_buffer("ref", _reference_bytes(rig, [body], "reference.glb")),
		"the reference body reads as a model")
	_expect(models.has("ref") and models.stamp_of("ref") > 0, "the model is in hand")
	_expect(models.node_names("ref").size() == body.parts().size(),
		"the model has one node for each part of the body: %s" % [models.node_names("ref")])
	_expect(FigureEdits.parts_from_model(back, rig, "ref", models).is_empty(),
		"a look takes its parts from the model")

	var copy := FigureLook.from_data(back)

	_expect(copy.error.is_empty() and copy.parts().size() == body.parts().size(),
		"the look reads: " + copy.error)

	for row: Dictionary in copy.parts():
		var source := body.part(row["node"])

		_expect(row["model"] == "ref" and not source.is_empty(),
			"the part %s names its model and its node" % row["name"])

		if source.is_empty():
			continue

		# The bone can differ, so the two places meet in the space of the figure.
		_expect(_same(rig.global_rest_of(row["bone"]) * FigureLook.part_transform(row),
			rig.global_rest_of(source["bone"]) * FigureLook.part_transform(source)),
			"the part %s sits where its author made it" % row["name"])
		_expect(models.node_bounds("ref", row["node"]).size.length() > 0.0,
			"the node %s has a box" % row["node"])

	_expect("skin" in models.material_names("ref", "head"),
		"a material name comes back as a color role: %s" % [models.material_names("ref", "head")])
	_expect(not FigureEdits.parts_from_model(back, rig, "none", models).is_empty(),
		"a model that is not there gives a reason")


func _a_part_draws_its_model() -> void:
	var rig := _rig()
	var models := _chain_models(rig)
	var look := _chain_look(rig, models)
	var first: Dictionary = look.parts()[0]
	var figure := FigureBuilder.build(rig, [look], models)
	var node := FigureBuilder.part_node(figure, CHAIN, first["name"])
	var instance := node.get_child(0) as MeshInstance3D

	_expect(node.get_child_count() == 1 and instance != null
		and instance.mesh.get_surface_count() == models.material_names(CHAIN, first["node"]).size(),
		"a part with a model draws the mesh of its node")
	_expect(FigureBuilder.counts(figure)["draws"] >= look.parts().size(),
		"the cost counts each surface of a model")

	var data := look.data.duplicate(true)

	data["parts"][0]["shapes"] = [FigureEdits.new_shape(FamilyShapes.SHAPE_BOX),
		FigureEdits.new_shape(FamilyShapes.SHAPE_BOX)]

	var with_shapes := FigureLook.from_data(data)

	FigureBuilder.refresh(figure, rig, [with_shapes], models)
	_expect(FigureBuilder.part_node(figure, CHAIN, first["name"]).get_child_count() == 1,
		"a model in hand draws, and not the shape list of its part")
	FigureBuilder.refresh(figure, rig, [with_shapes])
	_expect(FigureBuilder.part_node(figure, CHAIN, first["name"]).get_child_count() == 2,
		"with no model in hand, the part draws its shape list")

	data["parts"][0]["node"] = "no_such_node"
	FigureBuilder.refresh(figure, rig, [FigureLook.from_data(data)], models)
	_expect(FigureBuilder.part_node(figure, CHAIN, first["name"]).get_child_count() == 2
		and FigureBuilder.part_nodes(figure).size() == look.parts().size(),
		"a node that the model does not have draws the shape list, and each other part draws")
	figure.free()


func _a_color_role_colors_a_surface() -> void:
	var rig := _rig()
	var models := _chain_models(rig)
	var data := _chain_look(rig, models).data.duplicate(true)
	var first: Dictionary = data["parts"][0]
	var roles := models.material_names(CHAIN, first["node"])

	data["colors"] = {roles[0]: MeshPalette.GOLD}

	var figure := FigureBuilder.build(rig, [FigureLook.from_data(data)], models)
	var instance := FigureBuilder.part_node(figure, CHAIN, first["name"]).get_child(0) \
		as MeshInstance3D
	var colored := instance.get_surface_override_material(0) as StandardMaterial3D

	_expect(colored != null and colored.albedo_color.is_equal_approx(
		MeshPalette.color_of(MeshPalette.GOLD)), "a role of the color table colors its surface")
	figure.free()

	data.erase("colors")
	figure = FigureBuilder.build(rig, [FigureLook.from_data(data)], models)
	instance = FigureBuilder.part_node(figure, CHAIN, first["name"]).get_child(0) as MeshInstance3D
	_expect(instance.get_surface_override_material(0) == null,
		"a role with no color keeps the material of the model")
	figure.free()


func _new_bytes_draw_again() -> void:
	var rig := _rig()
	var models := _chain_models(rig)
	var look := _chain_look(rig, models)
	var name_of: String = look.parts()[0]["name"]
	var figure := FigureBuilder.build(rig, [look], models)
	var node := FigureBuilder.part_node(figure, CHAIN, name_of)
	var mesh := (node.get_child(0) as MeshInstance3D).mesh
	var stamp := models.stamp_of(CHAIN)

	FigureBuilder.refresh(figure, rig, [look], models)
	_expect((node.get_child(0) as MeshInstance3D).mesh == mesh,
		"a refresh with the same model keeps the mesh")
	models.put_buffer(CHAIN, FileAccess.get_file_as_bytes(_scratch.path_join(CHAIN + ".glb")))
	_expect(models.stamp_of(CHAIN) != stamp, "new bytes give a new stamp")
	FigureBuilder.refresh(figure, rig, [look], models)
	_expect(FigureBuilder.part_node(figure, CHAIN, name_of) == node
		and (node.get_child(0) as MeshInstance3D).mesh != mesh,
		"the part keeps its node, and it draws the new mesh")
	figure.free()


func _a_directory_reads_on_the_first_ask() -> void:
	var rig := _rig()
	var directory := _scratch.path_join("served")
	var relative := "items/%s.glb" % CHAIN

	_chain_models(rig)
	DirAccess.make_dir_recursive_absolute(directory.path_join("items"))
	DirAccess.copy_absolute(_scratch.path_join(CHAIN + ".glb"), directory.path_join(relative))

	var manifest := FileAccess.open(directory.path_join(FigureModels.MANIFEST_NAME),
		FileAccess.WRITE)

	manifest.store_string(JSON.stringify({CHAIN: relative, "gone": "items/gone.glb"}))
	manifest.close()

	var models := FigureModels.from_directory(directory)

	_expect(models.has(CHAIN) and not models.node_names(CHAIN).is_empty(),
		"a model of the directory reads on the first ask")
	_expect(not models.has("gone") and not models.has("none"),
		"a file that is not there, and a key that the manifest does not have, give no model")

	var stamp := models.stamp_of(CHAIN)

	_expect(models.read_manifest() == 2 and models.stamp_of(CHAIN) != stamp,
		"a new read of the manifest reads each file again")
	_expect(FigureModels.from_directory(_scratch.path_join("no_such")).node_names(CHAIN).is_empty(),
		"a directory with no manifest gives no model")


func _a_node_gets_a_bone() -> void:
	var rig := _rig()
	var head := rig.global_rest_of("Head").origin
	var top := rig.global_rest_of("head_top").origin
	var hand := rig.global_rest_of("RightHand").origin

	_expect(FigureEdits.nearest_bone(rig, head.lerp(top, 0.5)) == "Head",
		"a point over the head is nearest to the head bone")
	_expect(FigureEdits.nearest_bone(rig, hand.lerp(rig.global_rest_of("hand_r").origin, 0.5))
		== "RightHand", "a point in the hand is nearest to the hand bone")
	_expect(FigureEdits.nearest_bone(rig, hand) == "RightLowerArm",
		"a point at a joint is nearest to the first of its two bones")
	_expect(FigureEdits.bone_for_node(rig, "LeftUpperArm", AABB(head, Vector3.ZERO))
		== "LeftUpperArm", "a node with the name of a bone gets that bone")
	_expect(FigureEdits.bone_for_node(rig, "left_upper_arm", AABB(head, Vector3.ZERO))
		== "LeftUpperArm", "the name of a bone can be in snake case")
	_expect(FigureEdits.bone_for_node(rig, "Helm.001", AABB(head.lerp(top, 0.5), Vector3.ZERO))
		== "Head", "each other node gets the nearest bone")


func _a_fit_row_moves_one_body_type() -> void:
	var first := _rig("body_1")
	var second := _rig("body_2", LIMB_SCALE)
	var data := FigureEdits.slot_shape(first, "head").data.duplicate(true)
	var part_name: String = data["parts"][0]["name"]
	var moved := Transform3D(Basis.from_scale(Vector3(1.0, 0.8, 1.0)), Vector3(0.0, 0.02, 0.0))

	_expect(FigureEdits.set_part_fit(data, "body_2", part_name, true).is_empty()
		and data["fit"]["body_2"].size() == 1, "a part gets a fit row")
	_expect(FigureEdits.set_part_fit(data, "body_2", part_name, true).is_empty()
		and data["fit"]["body_2"].size() == 1, "a second ask adds no second row")

	var same := FigureLook.from_data(data)

	_expect(same.error.is_empty()
		and _same(same.place_of(part_name, "body_2"), same.place_of(part_name, "body_1")),
		"a new fit row starts at the place of the part: " + same.error)

	FigureEdits.set_part_place(data, part_name, moved, "body_2")

	var look := FigureLook.from_data(data)

	_expect(_same(look.place_of(part_name, "body_2"), moved)
		and _same(look.place_of(part_name, "body_1"), Transform3D.IDENTITY),
		"a place for a body type with a fit goes into the fit row only")
	_expect(FigureLook.from_text(look.to_text()).to_text() == look.to_text(),
		"a look with a fit gives the same bytes")

	var on_first := FigureBuilder.build(first, [look])
	var on_second := FigureBuilder.build(second, [look])

	_expect(_same(FigureBuilder.part_node(on_first, look.key(), part_name).transform,
		Transform3D.IDENTITY)
		and _same(FigureBuilder.part_node(on_second, look.key(), part_name).transform, moved),
		"the figure of each body type uses its own place")
	on_first.free()
	on_second.free()

	FigureEdits.rename_part(data, part_name, "renamed")
	_expect(data["fit"]["body_2"][0]["part"] == "renamed", "a fit row follows the name of its part")
	FigureEdits.set_part_place(data, "renamed", moved, "body_1")
	_expect(_same(FigureLook.part_transform(data["parts"][0]), moved),
		"a place for a body type with no fit goes into the part")
	FigureEdits.set_part_fit(data, "body_2", "renamed", false)
	_expect(not data.has("fit"), "the last fit row takes the fit table with it")
	FigureEdits.set_part_fit(data, "body_2", "renamed", true)
	FigureEdits.remove_part(data, "renamed")
	_expect(not data.has("fit"), "a removed part takes its fit rows with it")
	_expect(not FigureLook.from_data({"format": 1, "key": "a", "fit": {"body_2": [{}]}})
		.error.is_empty(), "a fit row needs a part")


func _the_bone_lengths_give_a_fit() -> void:
	var first := _rig("body_1")
	var second := _rig("body_2", LIMB_SCALE)
	var data := FigureEdits.slot_shape(first, "legs").data.duplicate(true)
	var count := FigureEdits.fit_to_rig(data, first, second)
	var look := FigureLook.from_data(data)
	var fitted := 0

	_expect(count > 0 and look.error.is_empty(),
		"a leg shell gets a fit on a body type with shorter legs: " + look.error)

	for row: Dictionary in look.parts():
		var fit_row := look.fit_row("body_2", row["name"])

		if fit_row.is_empty():
			continue

		fitted += 1

		var scale := FigureJson.vector3(fit_row["scale"])
		var changed := 0

		for axis in 3:
			if not is_equal_approx(scale[axis], 1.0):
				changed += 1
				_expect(absf(scale[axis] - LIMB_SCALE) < TOLERANCE,
					"the part %s is as long as the bone: %s" % [row["name"], scale])

		_expect(changed == 1, "the fit of %s scales one axis: the axis of the bone" % row["name"])

	_expect(fitted == count, "the count is the count of the fit rows")
	_expect(FigureEdits.fit_to_rig(data, first, second) == count
		and data["fit"]["body_2"].size() == count, "a second fit makes no second row")
	_expect(FigureEdits.fit_to_rig(data, first, _rig("body_2")) == 0 and not data.has("fit"),
		"two rigs with the same bones need no fit, and the old rows go")


## The proof of Phase W4: a chainbody model hides the torso and the arms
## on the two body types, through each clip of the repository.
func _a_chainbody_hides_the_torso_and_the_arms() -> void:
	var first := _rig("body_1")
	var models := _chain_models(first)
	var look := _chain_look(first, models)
	var clips := FigureClips.library()

	_expect(not look.parts().is_empty() and look.hides() == HIDDEN,
		"the chainbody has its parts and its hide list")
	_expect(not FigureClips.names_of(clips).is_empty(), "the repository has a clip")

	for rig: FigureRig in [first, _rig("body_2", LIMB_SCALE)]:
		var body := FigureEdits.mannequin(rig)
		var figure := FigureBuilder.build(rig, [body, look], models)

		add_child(figure)

		for row: Dictionary in body.parts():
			var shown := FigureBuilder.part_node(figure, body.key(), row["name"]) != null

			_expect(shown != (row["region"] in HIDDEN),
				"%s: the body part %s shows only out of the hidden regions" % [rig.key(),
					row["name"]])

		for row: Dictionary in look.parts():
			var node := FigureBuilder.part_node(figure, CHAIN, row["name"])

			_expect(node != null and (node.get_child(0) as MeshInstance3D).mesh != null,
				"%s: the chainbody part %s draws its model" % [rig.key(), row["name"]])

		for clip_name: String in FigureClips.names_of(clips):
			await _the_chainbody_follows(figure, rig, look, clips, clip_name)

		figure.queue_free()


## Each part of the chainbody stays on its bone through one clip, and no
## hidden body part comes back.
func _the_chainbody_follows(figure: Node3D, rig: FigureRig, look: FigureLook,
		clips: AnimationLibrary, clip_name: String) -> void:
	var skeleton := FigureBuilder.skeleton_of(figure)
	var player := FigureClips.player_of(figure, clips)
	var length := clips.get_animation(clip_name).length
	var moved := false

	for sample in SAMPLES:
		player.play(clip_name)
		player.seek(length * sample / SAMPLES, true)
		player.pause()
		await get_tree().process_frame

		for row: Dictionary in look.parts():
			var node := FigureBuilder.part_node(figure, CHAIN, row["name"])
			var bone := skeleton.find_bone(row["bone"])
			var wanted := figure.global_transform * skeleton.get_bone_global_pose(bone) \
				* look.place_of(row["name"], rig.key())

			moved = moved or not skeleton.get_bone_global_pose(bone).is_equal_approx(
				skeleton.get_bone_global_rest(bone))
			_expect(_same(node.global_transform, wanted),
				"%s, %s: the part %s is on its bone at sample %d" % [rig.key(), clip_name,
					row["name"], sample])

	_expect(moved, "%s, %s: the clip moves a bone of the chainbody" % [rig.key(), clip_name])
	FigureClips.stop(figure)


func _the_figure_set_reads() -> void:
	var rig := _rig()
	var body := FigureEdits.mannequin(rig)
	var text := JSON.stringify({"format": 1, "rigs": {"body_1": rig.data, "bad": {"format": 1}},
		"looks": {"body_1": body.data, "wrong_name": body.data}})
	var figure_set := FigureSet.from_text(text)

	_expect(figure_set.error.is_empty(), "a figure set reads: " + figure_set.error)
	_expect(figure_set.rigs.keys() == ["body_1"] and figure_set.looks.keys() == ["body_1"],
		"each entry that reads is in the set, and each other entry stays out")
	_expect(figure_set.errors.size() == 2, "the set names each entry that does not read: %s"
		% [figure_set.errors])
	_expect(figure_set.rigs["body_1"].to_text() == rig.to_text()
		and figure_set.looks["body_1"].to_text() == body.to_text(),
		"an entry is the content of its figure file")
	_expect(not FigureSet.from_text("[]").error.is_empty(), "a list is no figure set")
	_expect(not FigureSet.from_data({"rigs": {}}).error.is_empty(), "a figure set needs a format")
	_expect(not FigureSet.from_data({"format": FigureSet.FORMAT + 1}).error.is_empty(),
		"a newer format does not read")
	_expect(not FigureSet.read_file(_scratch.path_join("none.json")).error.is_empty(),
		"a file that is not there gives a reason")


## The served `figure.json` of the repository. This case writes nothing.
func _the_served_figure_set_is_the_repository() -> void:
	var store := FigureStore.new(FigureStore.repo_directory())
	var figure_set := FigureSet.read_file(
		FigureStore.repo_models_directory().path_join(FigureSet.FILE_NAME))

	store.load_all()
	_expect(figure_set.error.is_empty() and figure_set.errors.is_empty(),
		"the served figure set reads: %s %s" % [figure_set.error, figure_set.errors])
	_expect(not figure_set.rigs.is_empty(), "the served figure set has a rig")

	for pair: Array in [[FigureStore.KIND_RIG, figure_set.rigs],
			[FigureStore.KIND_LOOK, figure_set.looks]]:
		var served: Dictionary = pair[1]

		_expect(served.size() == store.keys_of(pair[0]).size(),
			"the served figure set has each file of %s" % pair[0])

		for key: String in store.keys_of(pair[0]):
			_expect(served.has(key) and served[key].to_text() == store.item_of(pair[0], key).to_text(),
				"%s/%s is the same in the served figure set" % [pair[0], key])

	for rig_key: String in figure_set.rigs:
		var figure := FigureBuilder.build(figure_set.rigs[rig_key],
			FigureOutfit.looks_for(figure_set.rigs[rig_key], {}, figure_set.looks))

		_expect(FigureBuilder.part_nodes(figure).size() > 0,
			"a figure of %s stands from the served figure set" % rig_key)
		figure.free()


## Delete the scratch tree of this test: files first, then directories.
func _remove_scratch(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return

	for child: String in DirAccess.get_directories_at(path):
		_remove_scratch(path.path_join(child))

	for file_name: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(file_name))

	DirAccess.remove_absolute(path)
