extends Node
## The headless half of the Phase W0 spike of DESIGN-0014.
##
##     godot --headless --path godot res://tests/spike_figure_checks.tscn
##
## Each case answers one claim of DESIGN-0014 section 10 with a yes or a no.
## A `SPIKE_FACT` line gives a number for the record. The scene needs no
## server. Two cases start other programs: Node for one model build into a
## scratch directory, and Python for the check of the model pipeline. Each
## of the two writes nothing into the repository.
##
## `spike_figure_bench.tscn` holds the cases that need a renderer.

const Spike := preload("res://tests/spike_figure.gd")

## A served model for the model part: the one sword with its own model.
const SWORD_MODEL := "web/static/webclient/models/items/rusty_scrap_shortsword.glb"

## The Node half of the model build, and the Python of the repository.
const BUILD_SCRIPT := "assets/pipeline/build_model.mjs"
const PYTHON := "../evenv/Scripts/python.exe"

## The scratch directory of the build case.
const WORK_DIRECTORY := "user://spike_figure"

## The glTF extensions that the runtime loader reads, as
## `assets/pipeline/glb.py` lists them.
const RUNTIME_EXTENSIONS := ["EXT_texture_webp", "GODOT_single_root",
	"KHR_animation_pointer", "KHR_lights_punctual",
	"KHR_materials_emissive_strength", "KHR_materials_pbrSpecularGlossiness",
	"KHR_materials_unlit", "KHR_node_visibility", "KHR_texture_basisu",
	"KHR_texture_transform"]

## The nodes of the model that the build case writes: a name, a position,
## and the name of its material, which is a color role.
const BUILD_NODES := [
	["torso", Vector3(0.0, 1.0, 0.0), "metal"],
	["arm_l", Vector3(0.35, 1.2, 0.0), "cloth"],
	["arm_r", Vector3(-0.35, 1.2, 0.0), "cloth"],
]

const TOLERANCE := 0.001
const LIMB_SCALE := 0.85
const SEEK_SECONDS := 0.125
const SETTLE_FRAMES := 3

var _failures := 0


func _ready() -> void:
	_the_profile_gives_a_rig()
	_a_rig_text_gives_the_same_bytes()
	_a_merged_figure_is_one_surface()
	_a_model_part_joins_both_figures()
	await _an_attachment_follows_its_bone()
	await _one_clip_moves_two_rigs()
	_the_model_build_keeps_each_node()
	_the_editor_can_start_the_pipeline()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: spike_figure_checks")
	get_tree().quit(0)


func _the_profile_gives_a_rig() -> void:
	var rig := Spike.rig_from_profile("body_1")
	var skeleton := Spike.skeleton_from_rig(rig)
	var names := []

	for bone: Dictionary in rig["bones"]:
		names.append(bone["name"])

	_fact("bones of the rig", rig["bones"].size())
	_fact("bone names", ", ".join(names))
	_expect(skeleton.get_bone_count() == rig["bones"].size(),
		"the skeleton has one bone for each bone of the rig")
	_expect(skeleton.find_bone("hand_r") >= 0, "a socket is a bone")
	_expect(skeleton.get_bone_parent(skeleton.find_bone("hand_r"))
		== skeleton.find_bone("RightHand"), "a socket has its parent bone")
	_expect(skeleton.find_bone("LeftIndexProximal") < 0, "the rig has no finger bone")
	_fact("hips height", skeleton.get_bone_global_rest(skeleton.find_bone("Hips")).origin.y)
	_fact("head height", skeleton.get_bone_global_rest(skeleton.find_bone("Head")).origin.y)
	skeleton.free()


func _a_rig_text_gives_the_same_bytes() -> void:
	var rig := Spike.rig_from_profile("body_1")
	var text := Spike.rig_to_text(rig)
	var again := Spike.rig_to_text(Spike.rig_from_text(text))
	var first := Spike.skeleton_from_rig(rig)
	var second := Spike.skeleton_from_rig(Spike.rig_from_text(text))
	var same := true

	_fact("bytes of the rig text", text.to_utf8_buffer().size())
	_expect(text == again, "a rig text that is read and written gives the same bytes")

	for bone in first.get_bone_count():
		same = same and first.get_bone_rest(bone).is_equal_approx(second.get_bone_rest(bone))

	_expect(same, "a rig from its text has the same rest pose")
	first.free()
	second.free()


func _a_merged_figure_is_one_surface() -> void:
	var rig := Spike.rig_from_profile("body_1")
	var parts := Spike.mannequin_parts(rig)
	var material := Spike.figure_material()
	var attached := Spike.build_attached(rig, parts, material)
	var merged := Spike.build_merged(rig, parts, material)
	var instance := merged.get_node("%s/%s" % [Spike.SKELETON_NAME, Spike.MERGED_NAME]) as MeshInstance3D
	var arrays := instance.mesh.surface_get_arrays(0)
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]

	_fact("parts of the dressed mannequin", parts.size())
	_fact("vertices of the merged figure", vertices.size())
	_fact("triangles of the merged figure", indices.size() / 3)
	_expect(instance.mesh.get_surface_count() == 1, "the merged figure has one surface")
	_expect(arrays[Mesh.ARRAY_BONES].size() == vertices.size() * Spike.WEIGHTS_PER_VERTEX,
		"each vertex of the merged figure has its bones")
	_expect(instance.skin.get_bind_count() == rig["bones"].size(),
		"the skin has one bind for each bone")
	_expect(_mesh_count(attached) == parts.size(),
		"the attached figure has one mesh for each part")
	attached.free()
	merged.free()


func _a_model_part_joins_both_figures() -> void:
	var sword := _load_model(_game_path(SWORD_MODEL))

	_expect(sword != null, "the served sword model loads from disk")

	if sword == null:
		return

	var rig := Spike.rig_from_profile("body_1")
	var plain := Spike.mannequin_parts(rig)
	var parts := Spike.mannequin_parts(rig, sword)
	var model_part: Dictionary = parts[parts.size() - 1]
	var merged := Spike.build_merged(rig, parts, Spike.figure_material())
	var instance := merged.get_node("%s/%s" % [Spike.SKELETON_NAME, Spike.MERGED_NAME]) as MeshInstance3D

	_fact("vertices of the sword model", model_part["soup"]["vertices"].size())
	_expect(model_part["soup"]["vertices"].size() > 0, "the model part has vertices")
	_expect(parts.size() == plain.size(), "a model part replaces the shape list part")
	_expect(instance.mesh.get_surface_count() == 1,
		"the merged figure with a model part has one surface")
	sword.free()
	merged.free()


func _an_attachment_follows_its_bone() -> void:
	var rig := Spike.rig_from_profile("body_1")
	var figure := Spike.build_attached(rig, Spike.mannequin_parts(rig), Spike.figure_material())
	var player := Spike.add_player(figure, Spike.walk_library(rig))
	var skeleton := figure.get_node(Spike.SKELETON_NAME) as Skeleton3D
	var thigh := skeleton.find_bone("LeftUpperLeg")
	var worst := 0.0

	add_child(figure)
	player.play(Spike.WALK_CLIP)
	player.seek(SEEK_SECONDS, true)
	player.pause()
	await _frames(SETTLE_FRAMES)

	_expect(not skeleton.get_bone_pose_rotation(thigh).is_equal_approx(
		skeleton.get_bone_rest(thigh).basis.get_rotation_quaternion()),
		"the clip moves a bone of a skeleton that code made from a rig")

	for child: Node in skeleton.get_children():
		var attachment := child as BoneAttachment3D
		var pose := skeleton.global_transform * skeleton.get_bone_global_pose(
			skeleton.find_bone(attachment.bone_name))

		worst = maxf(worst, attachment.global_transform.origin.distance_to(pose.origin))

	_fact("worst distance of a part from its bone", worst)
	_expect(worst < TOLERANCE, "each part follows its bone through the clip")
	figure.queue_free()


func _one_clip_moves_two_rigs() -> void:
	var first_rig := Spike.rig_from_profile("body_1")
	var second_rig := Spike.rig_from_profile("body_2", LIMB_SCALE)
	var library := Spike.walk_library(first_rig)
	var first := _walker(first_rig, library)
	var second := _walker(second_rig, library)

	await _frames(SETTLE_FRAMES)

	var same := true
	var hips := first.find_bone("Hips")
	var foot := first.find_bone("LeftFoot")

	for bone in first.get_bone_count():
		same = same and first.get_bone_pose_rotation(bone).is_equal_approx(
			second.get_bone_pose_rotation(second.find_bone(first.get_bone_name(bone))))

	var first_hips := first.get_bone_pose_position(hips).y
	var second_hips := second.get_bone_pose_position(second.find_bone("Hips")).y

	_fact("hips of body_1 in the clip", first_hips)
	_fact("hips of body_2 in the clip", second_hips)
	_fact("left foot height of body_1", first.get_bone_global_pose(foot).origin.y)
	_fact("left foot height of body_2",
		second.get_bone_global_pose(second.find_bone("LeftFoot")).origin.y)
	_expect(same, "one clip gives each bone of the two rigs the same rotation")
	_expect(absf(second_hips - first_hips * LIMB_SCALE) < TOLERANCE,
		"the motion scale of a rig scales the hips track of the clip")
	first.get_parent().queue_free()
	second.get_parent().queue_free()


## One merged figure in the tree, in the walk clip at a fixed time.
func _walker(rig: Dictionary, library: AnimationLibrary) -> Skeleton3D:
	var figure := Spike.build_merged(rig, Spike.mannequin_parts(rig), Spike.figure_material())
	var player := Spike.add_player(figure, library)

	add_child(figure)
	player.play(Spike.WALK_CLIP)
	player.seek(SEEK_SECONDS, true)
	player.pause()

	return figure.get_node(Spike.SKELETON_NAME) as Skeleton3D


## Write a model of three named nodes, run the Node half of the model build
## on it, and read the result.
func _the_model_build_keeps_each_node() -> void:
	var work := ProjectSettings.globalize_path(WORK_DIRECTORY)
	var input := work.path_join("three_nodes.glb")
	var output := work.path_join("three_nodes_built.glb")
	var job := work.path_join("job.json")
	var log := []

	DirAccess.make_dir_recursive_absolute(work)
	_write_build_model(input)
	_write_job(job, input, output)

	var code := OS.execute("node", [_game_path(BUILD_SCRIPT), "build", job], log, true)

	_expect(code == 0, "OS.execute runs the Node half of the model build")

	if code != 0:
		print("    ", "\n".join(log))
		return

	var built := _load_model(output)

	_expect(built != null, "the built model loads")

	if built == null:
		return

	for row: Array in BUILD_NODES:
		var node := built.find_child(row[0], true, false) as MeshInstance3D

		_expect(node != null, "the build keeps the node name '%s'" % row[0])

		if node == null:
			continue

		var position := Spike._xform_below(built, node).origin
		var material := node.get_active_material(0)

		_expect(position.is_equal_approx(row[1]),
			"the build keeps the position of '%s' (%s)" % [row[0], position])
		_answer(material != null and material.resource_name == row[2],
			"the build keeps the material name '%s' of '%s'" % [row[2], row[0]])

	built.free()


## Start the two programs that the import button of the workbench needs.
func _the_editor_can_start_the_pipeline() -> void:
	var game := _game_path("")
	var log := []
	var run := ("import os, runpy, sys; os.chdir(sys.argv[1]); "
		+ "sys.path.insert(0, sys.argv[1]); sys.argv = ['assets.pipeline', 'check']; "
		+ "runpy.run_module('assets.pipeline', run_name='__main__')")
	var code := OS.execute(_game_path(PYTHON), ["-c", run, game], log, true)

	_fact("exit code of the model pipeline check", code)
	_expect(code == 0, "OS.execute runs the check of the model pipeline")

	if code != 0:
		print("    ", "\n".join(log).right(600))

	log.clear()
	code = OS.execute("node", [_game_path(BUILD_SCRIPT), "validate",
		_game_path(SWORD_MODEL)], log, true)
	_expect(code == 0, "OS.execute runs the glTF validator through Node")


func _write_build_model(path: String) -> void:
	var root := Node3D.new()
	var document := GLTFDocument.new()
	var state := GLTFState.new()

	var materials := {}

	root.name = "worn"

	for row: Array in BUILD_NODES:
		var instance := MeshInstance3D.new()
		var mesh := BoxMesh.new()

		# One material for each color role, as a modeler exports it. The
		# materials differ in the name only.
		if not materials.has(row[2]):
			materials[row[2]] = StandardMaterial3D.new()
			materials[row[2]].resource_name = row[2]

		mesh.size = Vector3(0.2, 0.3, 0.2)
		mesh.material = materials[row[2]]
		instance.name = row[0]
		instance.mesh = mesh
		instance.position = row[1]
		root.add_child(instance)
		instance.owner = root

	document.append_from_scene(root, state)
	document.write_to_filesystem(state, path)
	root.free()


func _write_job(path: String, input: String, output: String) -> void:
	var job := {
		"input": input,
		"output": output,
		"node": "",
		"texture": null,
		"fix": {"rotate": null, "opaque": false, "filter": "linear"},
		"max_texture_edge": 512,
		"texture_format": "png",
		"animations": true,
		"allowed_extensions": RUNTIME_EXTENSIONS,
	}
	var file := FileAccess.open(path, FileAccess.WRITE)

	file.store_string(JSON.stringify(job, "  "))
	file.close()


## A model from a file, as the runtime loader of the game reads it. Null
## when the file does not load.
func _load_model(path: String) -> Node3D:
	var document := GLTFDocument.new()
	var state := GLTFState.new()

	if document.append_from_file(path, state) != OK:
		return null

	return document.generate_scene(state) as Node3D


## A path in the game directory, as an OS path.
func _game_path(relative: String) -> String:
	var project := ProjectSettings.globalize_path("res://")
	var game := project.path_join(ChunkFile.GAME_DIRECTORY_FROM_PROJECT)

	return game.path_join(relative).simplify_path()


func _mesh_count(node: Node) -> int:
	var count := 1 if node is MeshInstance3D else 0

	for child: Node in node.get_children():
		count += _mesh_count(child)

	return count


func _frames(count: int) -> void:
	for _frame in count:
		await get_tree().process_frame


func _fact(label: String, value: Variant) -> void:
	print("SPIKE_FACT %s: %s" % [label, value])


## An answer that is a finding of the spike. A "no" does not fail the run.
func _answer(condition: bool, label: String) -> void:
	print("  %s  %s" % ["yes" if condition else "NO ", label])


func _expect(condition: bool, label: String) -> void:
	if condition:
		print("  yes  ", label)
		return

	_failures += 1
	printerr("  NO   ", label)
