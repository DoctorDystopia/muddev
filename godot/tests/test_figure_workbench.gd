extends Node
## Tests for the figure workbench (DESIGN-0014 Phase W1): the file store,
## the workbench node, the pick of a part, and the figure files of the
## repository.
##
##     godot --headless --path godot res://tests/test_figure_workbench.tscn
##
## Needs nothing running and no editor. It writes only into a scratch
## directory under `user://`. It reads the figure files of the repository,
## and it never writes one. The scene of the workbench loads, but it does
## not go into the tree. The cases:
##
## 1. The scene holds a workbench that writes the figure files of the
##    repository.
## 2. A save writes only each changed file. A removed file leaves the disk.
## 3. A file that does not read stays as it is.
## 4. The workbench stands one figure for each rig, side by side.
## 5. New content shows on the stand, and the part keeps its node.
## 6. A part node that a Godot tool moved goes into its worn look. The old
##    place of the node brings the old content back.
## 7. A ray picks the part that it meets first, and the node of one shape
##    of it. A moved shape node goes into its shape.
## 8. The figure files of the repository read, and each one is in its
##    canonical text. A mannequin of each body type stands.
## 9. The outfit dresses each stand: the family shape, then the slot shape,
##    then the worn look of the item (Phase W3). The outfit is no figure
##    file.
## 10. One worn look shows on each stand. A move of its node on one stand
##     goes into the look, and the node on the other stand follows.
## 11. A ray picks a worn part. An item empties each slot that it clears,
##     and the outfit keeps only what the item catalog has.
## 12. The workbench writes a reference body, and it draws a part from a
##     model of its models directory (Phase W4).
## 13. A part with a fit on one body type: a move of its node on that stand
##     goes into the fit row, and the node on the other stand stays.
## 14. Each stand draws in the colors of the palette of the store (Phase
##     W5). A new color of the palette shows on each stand.
## 15. A tier draws the parts of its base. A move of such a part goes into
##     the look that has the parts. The file of the tier stays.
## 16. The colors of the character go over the colors of the body on each
##     stand, and they are no figure file.
## 17. The stance table is a file beside the clip directory. The outfit
##     takes the stance of its first item with one.
## 18. A workbench writes the repository when its figure directory or its
##     clip directory is the repository's (ENG-0011). It names each
##     unsaved file, each clip file that a build writes over, and the
##     rows of a clip build.
## 19. A job runs a routine on a thread, and it gives the result when it
##     ends.
## 20. A served model of an item wins over its worn look on each stand
##     (10/17/2026). A ray picks it. A move of its node goes into the
##     `served` row of the look, and the node on the other stand follows.
##     An item with no look gets a look with the row only.

const WORKBENCH_SCENE := "res://addons/blackout_figure/figure_workbench.tscn"

## The wait of the job of one case, in milliseconds.
const JOB_SLEEP := 50

## The frames that a case waits for a job at most.
const JOB_FRAMES := 600

## A clip list of the test, with no source file.
const CLIP_LIST := {"format": 1, "key": "pack", "file": "rig.glb",
	"skeleton": "Rig/Skeleton3D", "bones": {"Hips": "hips"},
	"clips": {"walk": {"from": "Walking", "loop": true}}}
const RIG := FigureStore.KIND_RIG
const LOOK := FigureStore.KIND_LOOK
const PALETTE := FigureStore.KIND_PALETTE
const STANCES := FigureStore.KIND_STANCES
const LIMB_SCALE := 0.9
const SETTLE_FRAMES := 2
const TOLERANCE := 0.001

## The top width that one case gives the first shape of the head. It is
## small, so the head does not cover the chest for the pick.
const NEW_WIDTH := 0.09

## The items of the test catalog.
const STICK := "wood_sword"
const PIKE := "iron_pike"

var _failures := 0
var _scratch := ""


func _ready() -> void:
	_scratch = ProjectSettings.globalize_path("user://figure_workbench_test_%d"
		% Time.get_ticks_usec())

	_the_scene_writes_the_repository()
	_a_save_writes_each_changed_file()
	_a_file_that_does_not_read_stays()
	await _the_workbench_stands_and_changes()
	await _the_outfit_dresses_each_stand()
	await _the_workbench_has_models_and_a_fit()
	await _a_served_model_moves_on_the_stands()
	await _the_workbench_has_colors_tiers_and_stances()
	await _the_family_stand_shows_an_entity()
	await _a_job_runs_on_a_thread()
	_the_repository_files_read()
	_remove_scratch(_scratch)

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_workbench")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _frames(count: int) -> void:
	for _frame in count:
		await get_tree().process_frame


func _the_scene_writes_the_repository() -> void:
	var scene: PackedScene = load(WORKBENCH_SCENE)
	var root := scene.instantiate()
	var bench := root.get_node("FigureWorkbench") as FigureWorkbench

	_expect(bench != null, "the scene holds a FigureWorkbench")

	if bench != null:
		_expect(bench.writes_repo() and bench.directory() == FigureStore.repo_directory(),
			"the scene uses the figure directory of the repository")
		_expect(FigureWorkbench.of(bench) == bench and FigureWorkbench.of(root) == null,
			"a workbench finds itself, and the scene root is no workbench")

	root.free()


## A store in `directory` with two rigs and the body of each one, not saved.
func _filled_store(directory: String) -> FigureStore:
	var store := FigureStore.new(directory)

	for pair: Array in [["body_1", 1.0], ["body_2", LIMB_SCALE]]:
		var rig := FigureEdits.rig_from_profile(pair[0], pair[1])

		store.put(RIG, pair[0], rig.data)
		store.put(LOOK, pair[0], FigureEdits.mannequin(rig).data)

	return store


func _a_save_writes_each_changed_file() -> void:
	var directory := _scratch.path_join("store")
	var store := _filled_store(directory)

	_expect(store.has_unsaved_changes(), "new content is an unsaved change")
	_expect(store.save().size() == 4 and not store.has_unsaved_changes(),
		"a save writes each new file")
	_expect(FileAccess.get_file_as_string(store.path_of(RIG, "body_1"))
		== store.rigs["body_1"].to_text(), "the file holds the canonical text")
	_expect(store.save().is_empty(), "a save with no change writes nothing")

	var saved := store.data_of(RIG, "body_1")
	var moved := saved.duplicate(true)

	FigureEdits.set_bone_position(moved, "hand_l", Vector3(0.0, 0.3, 0.0))
	store.put(RIG, "body_1", moved)
	_expect(store.has_unsaved_changes(), "content that differs from the disk is unsaved")
	store.put(RIG, "body_1", saved)
	_expect(not store.has_unsaved_changes(), "the saved content again leaves nothing to save")

	var data := store.data_of(RIG, "body_2")

	FigureEdits.set_bone_position(data, "hand_r", Vector3(0.0, 0.3, 0.0))
	_expect(store.put(RIG, "body_2", data).is_empty(), "a rig takes new content")
	_expect(store.save() == PackedStringArray(["rigs/body_2.json"]),
		"a save writes only the changed file")

	var again := FigureStore.new(directory)

	again.load_all()
	_expect(again.errors.is_empty() and again.keys_of(RIG) == PackedStringArray(["body_1", "body_2"])
		and again.keys_of(LOOK).size() == 2, "the directory reads back: %s" % again.errors)
	_expect(again.rigs["body_2"].rest_of("hand_r").origin.is_equal_approx(Vector3(0.0, 0.3, 0.0)),
		"the saved change reads back")
	_expect(again.data_of(RIG, "none").is_empty(), "an unknown key gives no content")

	_expect(not store.put(RIG, "body_2", {"format": 1}).is_empty(),
		"content that does not read gives a reason")
	_expect(not store.put(RIG, "body_3", store.data_of(RIG, "body_2")).is_empty(),
		"content under another key gives a reason")
	_expect(not store.has_unsaved_changes(), "a refused content changes nothing")

	_expect(store.put(LOOK, "body_2", {}).is_empty() and not store.has(LOOK, "body_2"),
		"empty content removes a file from the store")
	store.save()
	_expect(not FileAccess.file_exists(store.path_of(LOOK, "body_2"))
		and FileAccess.file_exists(store.path_of(LOOK, "body_1")),
		"the save deletes the removed file, and only that file")


func _a_file_that_does_not_read_stays() -> void:
	var directory := _scratch.path_join("broken")
	var store := _filled_store(directory)
	var broken := "{ this is not a rig"

	store.save()

	var file := FileAccess.open(store.path_of(RIG, "body_2"), FileAccess.WRITE)

	file.store_string(broken)
	file.close()
	store.load_all()
	_expect(store.errors.size() == 1 and not store.has(RIG, "body_2")
		and store.has(RIG, "body_1"), "the bad file stays out, and the store names it")
	_expect(not store.put(RIG, "body_2", FigureEdits.rig_from_profile("body_2").data).is_empty(),
		"the store refuses new content for the bad file")
	store.save()
	_expect(FileAccess.get_file_as_string(store.path_of(RIG, "body_2")) == broken,
		"a save leaves the bad file as it is")


func _the_workbench_stands_and_changes() -> void:
	var directory := _scratch.path_join("bench")
	var bench := FigureWorkbench.new()

	_filled_store(directory).save()
	bench.figure_directory = directory
	bench.clip_directory = directory.path_join("clips")
	add_child(bench)
	await _frames(SETTLE_FRAMES)

	_expect(not bench.writes_repo() and not bench.writes_repo_figures(),
		"a workbench with two scratch directories does not write the repository")
	_a_scratch_figure_directory_alone_still_writes_the_clips()
	_expect(bench.body_keys() == PackedStringArray(["body_1", "body_2"]),
		"the workbench has one body type for each rig")
	_expect(bench.figure_of("body_1") != null and bench.figure_of("body_2") != null
		and bench.figure_of("none") == null, "each body type has a figure")
	_expect(bench.figure_of("body_1").global_position.x
		< bench.figure_of("body_2").global_position.x, "the figures stand side by side")
	_expect(bench.counts_of("body_1")["parts"] == bench.store.looks["body_1"].parts().size(),
		"the figure wears the body of its body type")

	_new_content_shows(bench)
	_a_moved_node_goes_into_the_look(bench)
	_a_moved_shape_goes_into_the_look(bench)
	_a_moved_mark_goes_into_the_rig(bench)
	await _frames(SETTLE_FRAMES)
	_a_ray_picks_the_first_part(bench)
	_a_ray_picks_a_shape(bench)
	_a_new_rig_gets_a_stand(bench)
	bench.queue_free()


## A scratch figure directory with no scratch clip directory writes the
## clips and the stance table of the repository. The node goes into no
## tree, so it reads nothing.
func _a_scratch_figure_directory_alone_still_writes_the_clips() -> void:
	var bench := FigureWorkbench.new()

	bench.figure_directory = _scratch.path_join("alone")
	_expect(bench.writes_repo() and not bench.writes_repo_figures(),
		"a scratch figure directory alone still writes the clips of the repository")
	bench.clip_directory = _scratch.path_join("alone_clips")
	bench.figure_directory = ""
	_expect(bench.writes_repo() and bench.writes_repo_figures(),
		"a scratch clip directory alone still writes the figure files of the repository")
	bench.free()


func _new_content_shows(bench: FigureWorkbench) -> void:
	var head := bench.part_node("body_1", "body_1", "head")
	var data := bench.store.data_of(LOOK, "body_1")
	var seen := []

	bench.changed.connect(func(kind: String, key: String) -> void: seen.append([kind, key]))
	_expect(bench.unsaved_names().is_empty(), "a saved store names no unsaved file")
	FigureEdits.set_shape_value(data, "head", 0, "top_width", NEW_WIDTH)
	_expect(bench.put(LOOK, "body_1", data).is_empty(), "the workbench takes new content")
	_expect(bench.unsaved_names() == PackedStringArray([bench.store.name_of(LOOK, "body_1")]),
		"the workbench names the unsaved file: %s" % [bench.unsaved_names()])
	_expect(bench.part_node("body_1", "body_1", "head") == head
		and is_equal_approx((head.get_child(0) as MeshInstance3D).mesh.get_aabb().size.x,
			NEW_WIDTH),
		"the stand shows the new shape on the same node")
	_expect(seen == [[LOOK, "body_1"]], "the workbench names the changed file: %s" % [seen])
	_expect(bench.has_unsaved_changes(), "the change is not saved yet")
	_expect(bench.body_of(head) == "body_1" and bench.body_of(bench).is_empty(),
		"a part node knows its stand")
	_expect(not bench.put(LOOK, "body_1", {"format": 1}).is_empty(),
		"content that does not read gives a reason")

	bench.mark_bone("hand_r")

	var mark := bench.figure_of("body_1").get_parent().get_node(FigureWorkbench.MARK_NAME) as Node3D

	_expect(mark.visible and mark.position.is_equal_approx(
		bench.store.rigs["body_1"].global_rest_of("hand_r").origin), "a mark shows the bone")
	bench.mark_bone("")
	_expect(not mark.visible, "no bone shows no mark")


func _a_moved_node_goes_into_the_look(bench: FigureWorkbench) -> void:
	var hand := bench.part_node("body_2", "body_2", "hand_l")
	var before := hand.transform
	var text: String = bench.store.looks["body_2"].to_text()
	var moved := Transform3D(Basis.from_euler(Vector3(0.0, 0.7, 0.0)).scaled_local(
		Vector3(1.0, 1.5, 1.0)), Vector3(0.01, 0.123456789, 0.0))

	_expect(not bench.sync_from_nodes(), "a figure that nobody moved changes no look")

	hand.transform = moved
	_expect(bench.sync_from_nodes(), "a moved node changes its look")

	var row: Dictionary = bench.store.looks["body_2"].part("hand_l")

	_expect(FigureLook.part_transform(row).origin.distance_to(moved.origin) < TOLERANCE
		and FigureLook.part_transform(row).basis.y.distance_to(moved.basis.y) < TOLERANCE,
		"the look has the place of the node")
	_expect(row["position"][1] == snappedf(0.123456789, FigureJson.ROUND_STEP),
		"the look keeps five digits")
	_expect(bench.part_node("body_2", "body_2", "hand_l") == hand, "the part keeps its node")
	_expect(not bench.sync_from_nodes(), "the rounding of the file is not a move")
	_expect(bench.store.looks["body_1"].part("hand_l")["position"][1] == 0.0,
		"the other body type keeps its own body")

	# An undo of the editor gives the node its old place.
	hand.transform = before
	_expect(bench.sync_from_nodes() and bench.store.looks["body_2"].to_text() == text,
		"the old place of the node brings the old content back")


## A shape node that a Godot tool moved goes into its shape: the offset,
## the rotation, and the scale. The node keeps its place, and the old
## place brings the old content back.
func _a_moved_shape_goes_into_the_look(bench: FigureWorkbench) -> void:
	var shape := bench.shape_node("body_1", "body_1", "head", 0)
	var other := bench.shape_node("body_2", "body_2", "head", 0)
	var text: String = bench.store.looks["body_1"].to_text()
	var other_text: String = bench.store.looks["body_2"].to_text()
	var before := shape.transform
	var moved := Transform3D(Basis.from_euler(Vector3(0.3, 0.0, 0.0)).scaled_local(
		Vector3(1.0, 1.2, 1.0)), Vector3(0.0, 0.03, 0.01))

	_expect(shape != null and other != null and not bench.sync_from_nodes(),
		"each stand has the node of the first shape of the head, and nobody moved it")
	shape.transform = moved
	_expect(bench.sync_from_nodes(), "a moved shape node changes its look")

	var row: Dictionary = bench.store.looks["body_1"].part("head")["shapes"][0]

	_expect(FigureLook.shape_transform(row).origin.distance_to(moved.origin) < TOLERANCE
		and FigureLook.shape_transform(row).basis.y.distance_to(moved.basis.y) < TOLERANCE,
		"the shape has the place of the node")
	_expect(is_instance_valid(shape) and bench.shape_node("body_1", "body_1", "head", 0) == shape
		and shape.transform.is_equal_approx(moved), "the moved shape keeps its node")
	_expect(not bench.sync_from_nodes(), "the rounding of the file is not a move")
	_expect(bench.store.looks["body_2"].to_text() == other_text,
		"the other body type keeps its own body")

	shape.transform = before
	_expect(bench.sync_from_nodes() and bench.store.looks["body_1"].to_text() == text,
		"the old place of the shape node brings the old content back")


## A ray picks the node of one shape, and the shape id names the shape.
func _a_ray_picks_a_shape(bench: FigureWorkbench) -> void:
	var head := bench.part_node("body_1", "body_1", "head")
	var head_at: Vector3 = (head.get_child(0) as Node3D).global_position
	var instance := bench.shape_at(head_at + Vector3(0.0, 0.0, 5.0), Vector3.FORWARD)

	_expect(instance != null and instance.get_parent() == head,
		"a ray at the head picks a shape of the head")
	_expect(instance != null and FigureBuilder.shape_id(instance).slice(0, 2)
		== ["body_1", "head"], "the shape id names the look and the part")
	_expect(bench.shape_at(head_at + Vector3(0.0, 5.0, 5.0), Vector3.FORWARD) == null,
		"a ray over the figure picks no shape")


## The bone mark is a node that the Godot move tool moves. Its move goes
## into the rig of its stand, as a part move goes into a look (ENG-0011).
func _a_moved_mark_goes_into_the_rig(bench: FigureWorkbench) -> void:
	var rig_text: String = bench.store.rigs["body_1"].to_text()
	var other_text: String = bench.store.rigs["body_2"].to_text()
	var rest: Vector3 = bench.store.rigs["body_1"].global_rest_of("hand_r").origin
	var lifted := rest + Vector3(0.0, 0.1, 0.0)
	var seen := []

	bench.changed.connect(func(kind: String, key: String) -> void: seen.append([kind, key]))
	bench.mark_bone("hand_r")

	var mark := bench.mark_node("body_1")

	_expect(mark != null and mark.visible and bench.marked_bone() == "hand_r",
		"the stand has a mark on the selected bone")
	_expect(not bench.sync_from_nodes(), "a mark that nobody moved changes no rig")

	mark.position = lifted
	_expect(bench.sync_from_nodes() and seen == [[RIG, "body_1"]],
		"a moved mark changes the rig of its stand: %s" % [seen])
	_expect(bench.store.rigs["body_1"].global_rest_of("hand_r").origin.distance_to(lifted)
		< TOLERANCE, "the bone is where the mark went")
	_expect(mark.position.distance_to(lifted) < TOLERANCE and not bench.sync_from_nodes(),
		"the mark stays on the bone, and the rounding of the file is not a move")
	_expect(bench.store.rigs["body_2"].to_text() == other_text,
		"the other body type keeps its rig")

	mark.position = rest
	_expect(bench.sync_from_nodes() and bench.store.rigs["body_1"].to_text() == rig_text,
		"the old place of the mark brings the old rig back")
	bench.mark_bone("")
	_expect(bench.mark_node("none") == null, "a body type with no stand has no mark")


func _a_ray_picks_the_first_part(bench: FigureWorkbench) -> void:
	var figure := bench.figure_of("body_1")
	var head := bench.part_node("body_1", "body_1", "head")
	var chest := bench.part_node("body_1", "body_1", "upper_chest")
	var front := Vector3(0.0, 0.0, 5.0)
	var head_at: Vector3 = (head.get_child(0) as Node3D).global_position

	_expect(bench.part_at(head_at + front, Vector3.FORWARD) == head,
		"a ray at the head picks the head")
	_expect(bench.part_at(chest.global_position + Vector3(0.0, 0.05, 5.0), Vector3.FORWARD)
		== chest, "a ray at the chest picks the chest")
	_expect(bench.part_at(figure.global_position + Vector3(0.0, 5.0, 5.0), Vector3.FORWARD)
		== null, "a ray over the figure picks nothing")
	_expect(bench.part_at(head_at + Vector3(0.0, 5.0, 0.0), Vector3.DOWN)
		== bench.part_node("body_1", "body_1", "hair"),
		"a ray from above meets the hair first, and not the head below it")
	_expect(bench.body_of(bench.part_at(head_at + front, Vector3.FORWARD)) == "body_1",
		"the pick is on the stand under the ray")


func _a_new_rig_gets_a_stand(bench: FigureWorkbench) -> void:
	var rig := FigureEdits.rig_from_profile("body_0")
	var first := bench.figure_of("body_1")

	_expect(bench.put(RIG, "body_0", rig.data).is_empty() and bench.figure_of("body_0") != null,
		"a new rig gets a stand")
	_expect(bench.figure_of("body_1") == first, "the other stands keep their figures")
	_expect(bench.counts_of("body_0")["parts"] == 0, "a rig with no body stands bare")
	_expect(bench.figure_of("body_0").global_position.x < first.global_position.x,
		"the stands are in the order of the keys")
	_expect(bench.put(RIG, "body_0", {}).is_empty() and bench.figure_of("body_0") == null,
		"a removed rig loses its stand")


## Write a small item catalog into the scratch directory, and return its
## path. The stick and the pike have no worn look.
func _write_catalog() -> String:
	var path := _scratch.path_join("item_catalog.json")
	var items := []

	for row: Array in [[STICK, "main_hand", "shortsword"], [PIKE, "two_hands", "spear"]]:
		items.append({"key": row[0], "name": row[0], "slot": row[1], "tool_type": row[2],
			"tier": 0, "family": "weapon"})

	var file := FileAccess.open(path, FileAccess.WRITE)

	file.store_string(JSON.stringify({"format": 1, "items": items, "slots": [
		{"key": "main_hand", "label": "Main Hand", "clears": ["two_hands"]},
		{"key": "two_hands", "label": "Two Hands", "clears": ["main_hand"]},
	]}))
	file.close()

	return path


func _the_outfit_dresses_each_stand() -> void:
	var directory := _scratch.path_join("outfit")
	var bench := FigureWorkbench.new()
	var seen := []

	_filled_store(directory).save()
	bench.figure_directory = directory
	bench.clip_directory = directory.path_join("clips")
	bench.catalog_path = _write_catalog()
	add_child(bench)
	await _frames(SETTLE_FRAMES)
	bench.outfit_changed.connect(func() -> void: seen.append(bench.outfit()))

	var bare: int = bench.counts_of("body_1")["parts"]
	var family_key := FigureOutfit.FAMILY_KEY_PREFIX + "main_hand"

	_expect(bench.catalog.error.is_empty() and bench.outfit().is_empty(),
		"the workbench reads its item catalog, and it starts with no outfit: "
			+ bench.catalog.error)

	bench.wear("main_hand", STICK)
	_expect(seen == [{"main_hand": STICK}], "a worn item changes the outfit one time")
	_expect(bench.source_of("body_1", "main_hand") == FigureOutfit.SOURCE_FAMILY
		and bench.part_node("body_1", family_key, FigureOutfit.FAMILY_PART) != null
		and bench.part_node("body_2", family_key, FigureOutfit.FAMILY_PART) != null,
		"an item with no look and no slot shape shows the family shape on each stand")
	_expect(bench.counts_of("body_1")["parts"] == bare + 1, "the cost counts the worn part")
	_expect(not bench.has_unsaved_changes(), "the outfit is no figure file")
	# The hand socket is inside the hand of the body, so the ray meets the hand.
	_expect(bench.part_at(bench.part_node("body_1", family_key, FigureOutfit.FAMILY_PART)
		.global_position + Vector3(0.0, 0.0, 5.0), Vector3.FORWARD)
		== bench.part_node("body_1", "body_1", "hand_r"),
		"a ray goes through a family shape, because no figure file holds it")

	var slot_shape := FigureEdits.slot_shape(bench.store.rigs["body_1"], "main_hand")

	bench.put(LOOK, "main_hand", slot_shape.data)
	_expect(bench.source_of("body_2", "main_hand") == FigureOutfit.SOURCE_SLOT_SHAPE
		and bench.part_node("body_2", "main_hand", FigureEdits.ITEM_PART) != null
		and bench.part_node("body_2", family_key, FigureOutfit.FAMILY_PART) == null,
		"a new slot shape takes the place of the family shape")

	bench.put(LOOK, STICK, FigureEdits.look_from(STICK, slot_shape))
	_expect(bench.source_of("body_1", "main_hand") == FigureOutfit.SOURCE_LOOK
		and bench.part_node("body_1", STICK, FigureEdits.ITEM_PART) != null
		and bench.part_node("body_1", "main_hand", FigureEdits.ITEM_PART) == null,
		"the worn look of the item takes the place of the slot shape")

	await _frames(SETTLE_FRAMES)
	_a_shared_look_follows_one_moved_node(bench)
	_a_ray_picks_a_worn_part(bench)
	_an_outfit_follows_the_catalog(bench, seen)
	bench.queue_free()


## One worn look shows on each stand. A move of its node on one stand goes
## into the look, and the node on the other stand follows.
func _a_shared_look_follows_one_moved_node(bench: FigureWorkbench) -> void:
	var first := bench.part_node("body_1", STICK, FigureEdits.ITEM_PART)
	var second := bench.part_node("body_2", STICK, FigureEdits.ITEM_PART)
	var before := first.transform
	var text: String = bench.store.looks[STICK].to_text()
	var moved := Transform3D(Basis.from_euler(Vector3(0.3, 0.0, 0.0)), Vector3(0.0, 0.05, 0.02))

	_expect(not bench.sync_from_nodes(), "a worn look that nobody moved does not change")
	first.transform = moved
	_expect(bench.sync_from_nodes(), "a moved node of a worn look changes that look")
	_expect(FigureLook.part_transform(bench.store.looks[STICK].part(FigureEdits.ITEM_PART))
		.origin.distance_to(moved.origin) < TOLERANCE,
		"the look has the place of the moved node, not the place of the other node")
	_expect(second.transform.origin.distance_to(moved.origin) < TOLERANCE
		and bench.part_node("body_2", STICK, FigureEdits.ITEM_PART) == second,
		"the node on the other stand follows, and it keeps its node")
	_expect(not bench.sync_from_nodes(), "the two nodes agree after the move")

	second.transform = before
	_expect(bench.sync_from_nodes() and bench.store.looks[STICK].to_text() == text
		and first.transform.origin.distance_to(before.origin) < TOLERANCE,
		"a move on the other stand goes into the same look")


func _a_ray_picks_a_worn_part(bench: FigureWorkbench) -> void:
	var blade := bench.part_node("body_1", STICK, FigureEdits.ITEM_PART)
	var at: Vector3 = (blade.get_child(0) as Node3D).global_position

	_expect(bench.part_at(at + Vector3(0.0, 0.0, 5.0), Vector3.FORWARD) == blade,
		"a ray at a worn part picks that part")


func _an_outfit_follows_the_catalog(bench: FigureWorkbench, seen: Array) -> void:
	seen.clear()
	bench.wear("two_hands", PIKE)
	_expect(bench.outfit() == {"two_hands": PIKE}
		and bench.part_node("body_1", STICK, FigureEdits.ITEM_PART) == null,
		"a two-handed item empties the hand slot, and its part leaves the stand")
	bench.set_outfit({"two_hands": PIKE})
	_expect(seen.size() == 1, "the same outfit again changes nothing")
	bench.set_outfit({"main_hand": "main_hand", "head": STICK, "two_hands": "gone_item"})
	_expect(bench.outfit() == {"main_hand": "main_hand"}
		and bench.part_node("body_2", "main_hand", FigureEdits.ITEM_PART) != null,
		"the outfit keeps only what the catalog has, and a slot key shows the slot shape")
	bench.wear("main_hand", "")
	_expect(bench.outfit().is_empty(), "an empty key takes the item off")
	bench.wear("main_hand", STICK)
	bench.store.save()
	bench.reload()
	_expect(bench.outfit() == {"main_hand": STICK}
		and bench.part_node("body_1", STICK, FigureEdits.ITEM_PART) != null,
		"a reload keeps the outfit")


## A workbench with a scratch models directory: the reference body, a part
## from a model, and the fit of a body type.
func _the_workbench_has_models_and_a_fit() -> void:
	var directory := _scratch.path_join("models_bench")
	var served := _scratch.path_join("served")
	var relative := "items/%s.glb" % STICK
	var bench := FigureWorkbench.new()

	_filled_store(directory).save()
	bench.figure_directory = directory
	bench.clip_directory = directory.path_join("clips")
	bench.catalog_path = _write_catalog()
	bench.models_directory = served
	add_child(bench)
	await _frames(SETTLE_FRAMES)

	var rig: FigureRig = bench.store.rigs["body_1"]
	var stick := FigureLook.from_data(FigureEdits.look_from(STICK,
		FigureEdits.slot_shape(rig, "main_hand")))
	var reference := _scratch.path_join("reference_body_1.glb")
	var read_back := FigureModels.new()

	bench.put(LOOK, STICK, stick.data)
	bench.wear("main_hand", STICK)
	_expect(bench.served_models_directory() == served and bench.models.node_names(STICK).is_empty(),
		"a workbench with a models directory reads no model of the repository")
	_expect(bench.export_reference("body_1", reference) == OK
		and read_back.put_buffer("reference", FileAccess.get_file_as_bytes(reference))
		and read_back.node_names("reference").size()
			== bench.store.looks["body_1"].parts().size() + stick.parts().size(),
		"the reference body has each part of the body and of the outfit")
	_expect(bench.export_reference("none", reference) == ERR_DOES_NOT_EXIST,
		"a body type with no rig gives no reference body")

	# The model of the stick: the stick alone, as a file of the served tree.
	_expect(FigureReference.export(rig, [stick], served.path_join(relative)) == OK,
		"the model of the stick writes")

	var manifest := FileAccess.open(served.path_join(FigureModels.MANIFEST_NAME), FileAccess.WRITE)

	manifest.store_string(JSON.stringify({STICK: relative}))
	manifest.close()
	bench.reload_models()

	var data := bench.store.data_of(LOOK, STICK)

	_expect(FigureEdits.parts_from_model(data, rig, STICK, bench.models).is_empty()
		and bench.put(LOOK, STICK, data).is_empty(), "the look takes its parts from the model")
	await _frames(SETTLE_FRAMES)

	var part_name: String = data["parts"][0]["name"]
	var first := bench.part_node("body_1", STICK, part_name)
	var second := bench.part_node("body_2", STICK, part_name)

	_expect(first != null and second != null and first.get_child_count() == 1
		and (first.get_child(0) as MeshInstance3D).mesh
			== (second.get_child(0) as MeshInstance3D).mesh,
		"each stand draws the node of the model, and the two share its mesh")
	_expect(bench.part_at((first.get_child(0) as Node3D).global_position
		+ Vector3(0.0, 0.0, 5.0), Vector3.FORWARD) == first, "a ray picks a part with a model")
	_expect(not bench.sync_from_nodes(), "a new part with a model is at its place")

	_a_fit_keeps_the_other_stand(bench, part_name)
	bench.queue_free()


## A workbench whose served tree has a model of the stick: a long box,
## away from the origin, as a download is.
func _served_bench(name: String) -> FigureWorkbench:
	var directory := _scratch.path_join(name)
	var served := directory.path_join("served")
	var relative := "items/%s.glb" % STICK
	var bench := FigureWorkbench.new()

	_filled_store(directory).save()

	var rig := FigureEdits.rig_from_profile("body_1")
	var download := FigureLook.from_data({"format": FigureLook.FORMAT, "key": "download",
		"parts": [{"name": "blade", "bone": rig.slots()["main_hand"], "position": [2.0, 1.0, 0.0],
			"shapes": [{"shape": FamilyShapes.SHAPE_BOX, "size": [0.5, 6.0, 0.2]}]}]})

	_expect(FigureReference.export(rig, [download], served.path_join(relative)) == OK,
		"the served model of the stick writes")

	var manifest := FileAccess.open(served.path_join(FigureModels.MANIFEST_NAME), FileAccess.WRITE)

	manifest.store_string(JSON.stringify({STICK: relative}))
	manifest.close()
	bench.figure_directory = directory
	bench.clip_directory = directory.path_join("clips")
	bench.catalog_path = _write_catalog()
	bench.models_directory = served

	return bench


func _a_served_model_moves_on_the_stands() -> void:
	var bench := _served_bench("served_bench")

	add_child(bench)
	await _frames(SETTLE_FRAMES)

	var rig: FigureRig = bench.store.rigs["body_1"]
	var stick := FigureLook.from_data(FigureEdits.look_from(STICK,
		FigureEdits.slot_shape(rig, "main_hand")))

	bench.put(LOOK, STICK, stick.data)
	bench.wear("main_hand", STICK)
	await _frames(SETTLE_FRAMES)

	var first := bench.part_node("body_1", STICK, FigureLook.SERVED_PART)
	var second := bench.part_node("body_2", STICK, FigureLook.SERVED_PART)
	var fitted := FigureOutfit.fit_place(rig, rig.slots()["main_hand"], stick, bench.models)

	_expect(bench.source_of("body_1", "main_hand") == FigureOutfit.SOURCE_MODEL
		and first != null and second != null
		and bench.part_node("body_1", STICK, stick.parts()[0]["name"]) == null,
		"each stand draws the served model, and no part of the worn look")

	if first == null or second == null:
		bench.queue_free()
		return

	_expect(_near(first.transform, fitted) and not bench.sync_from_nodes(),
		"the served model takes the box of the worn look, and nothing moved")
	_expect(bench.part_at((first.get_child(0) as Node3D).global_position
		+ Vector3(0.0, 0.0, 5.0), Vector3.FORWARD) == first, "a ray picks the served model")

	var moved := Transform3D(Basis.from_scale(Vector3.ONE * 0.4), Vector3(0.0, 0.1, 0.02))

	first.transform = moved
	_expect(bench.sync_from_nodes()
		and bench.store.looks[STICK].served().get("bone") == rig.slots()["main_hand"]
		and _near(FigureLook.part_transform(bench.store.looks[STICK].served()), moved),
		"a moved served model goes into the served row of the look")
	await _frames(SETTLE_FRAMES)
	_expect(_near(bench.part_node("body_2", STICK, FigureLook.SERVED_PART).transform, moved),
		"the served model on the other stand follows")

	bench.put(LOOK, STICK, {})
	await _frames(SETTLE_FRAMES)
	first = bench.part_node("body_1", STICK, FigureLook.SERVED_PART)
	first.transform = moved
	_expect(bench.sync_from_nodes() and bench.store.has(LOOK, STICK)
		and bench.store.looks[STICK].parts().is_empty()
		and not bench.store.looks[STICK].served().is_empty(),
		"an item with no look gets a look with the served row only")
	_expect(bench.source_of("body_1", "main_hand") == FigureOutfit.SOURCE_MODEL,
		"the served model still draws")
	bench.queue_free()


## A part with a fit on `body_2`: a move of its node there goes into the
## fit row. A move on `body_1` goes into the part, and the fit stays.
func _a_fit_keeps_the_other_stand(bench: FigureWorkbench, part_name: String) -> void:
	var data := bench.store.data_of(LOOK, STICK)
	var first := bench.part_node("body_1", STICK, part_name)
	var second := bench.part_node("body_2", STICK, part_name)
	var before := first.transform
	var fitted := Transform3D(Basis.from_scale(Vector3(1.0, 0.8, 1.0)), Vector3(0.0, 0.03, 0.01))
	var moved := Transform3D(Basis.IDENTITY, Vector3(0.02, 0.0, 0.0))

	FigureEdits.set_part_fit(data, "body_2", part_name, true)
	bench.put(LOOK, STICK, data)
	_expect(not bench.sync_from_nodes() and second.transform.is_equal_approx(before),
		"a new fit row moves no node")

	second.transform = fitted
	_expect(bench.sync_from_nodes(), "a moved node on the stand with a fit changes the look")

	var look: FigureLook = bench.store.looks[STICK]

	_expect(_near(look.place_of(part_name, "body_2"), fitted)
		and _near(look.place_of(part_name, "body_1"), before) and _near(first.transform, before),
		"the move goes into the fit row, and the other stand stays")

	first.transform = moved
	_expect(bench.sync_from_nodes(), "a moved node on the stand with no fit changes the look")
	look = bench.store.looks[STICK]
	_expect(_near(look.place_of(part_name, "body_1"), moved)
		and _near(look.place_of(part_name, "body_2"), fitted) and _near(second.transform, fitted),
		"the move goes into the part, and the fit stays")
	_expect(not bench.sync_from_nodes(), "the two nodes agree with the look after the moves")


func _near(first: Transform3D, second: Transform3D) -> bool:
	if first.origin.distance_to(second.origin) > TOLERANCE:
		return false

	for axis in 3:
		if first.basis[axis].distance_to(second.basis[axis]) > TOLERANCE:
			return false

	return true


## The color of one shape of one part on one stand.
func _shape_color(bench: FigureWorkbench, body_key: String, look_key: String,
		part_name: String, shape := 0) -> Color:
	var part := bench.part_node(body_key, look_key, part_name)
	var instance := part.get_child(shape) as MeshInstance3D

	return (instance.material_override as StandardMaterial3D).albedo_color


## The index of the first shape of one part that names one color role.
func _shape_with_role(look: FigureLook, part_name: String, role: String) -> int:
	var shapes: Array = look.part(part_name)["shapes"]

	for index in shapes.size():
		if shapes[index].get("color", "") == role:
			return index

	return -1


## A workbench with a palette, a tier, the colors of a character, and a
## stance table (Phase W5). Each file is in a scratch directory.
func _the_workbench_has_colors_tiers_and_stances() -> void:
	var directory := _scratch.path_join("colors")
	var clips := _scratch.path_join("colors_clips")
	var bench := FigureWorkbench.new()
	var store := _filled_store(directory)
	var slot_shape := FigureEdits.slot_shape(store.rigs["body_1"], "main_hand")

	store.put(PALETTE, PALETTE, FigureEdits.new_palette().data)
	store.put(LOOK, "main_hand", slot_shape.data)
	store.put(LOOK, STICK, {"format": 1, "key": STICK, "base": "main_hand",
		"colors": {FigureEdits.ROLE_METAL: MeshPalette.COPPER}})
	_expect(store.save().has(FigurePalette.FILE_NAME) and store.errors.is_empty(),
		"a save names the palette by its file name: %s" % [store.errors])
	_expect(FigureStore.kind_of_name(FigurePalette.FILE_NAME) == PALETTE
		and FigureStore.kind_of_name(store.name_of(LOOK, STICK)) == LOOK,
		"the name of a saved file gives its kind")
	_expect(not store.put(STANCES, STANCES, FigureEdits.new_stances()).is_empty(),
		"a store with no stance file takes no stance table")

	bench.figure_directory = directory
	bench.clip_directory = clips
	bench.catalog_path = _write_catalog()
	add_child(bench)
	await _frames(SETTLE_FRAMES)
	bench.wear("main_hand", STICK)
	_expect(bench.store.has(PALETTE, PALETTE) and bench.store.errors.is_empty(),
		"the workbench reads the palette of its directory: %s" % [bench.store.errors])

	_a_stand_draws_in_the_palette(bench)
	_a_moved_tier_part_goes_into_its_base(bench)
	_the_character_colors_go_over_the_body(bench)
	_the_outfit_takes_a_stance(bench, clips)
	bench.queue_free()


func _a_stand_draws_in_the_palette(bench: FigureWorkbench) -> void:
	var blade := bench.part_node("body_1", STICK, FigureEdits.ITEM_PART)
	var metal := _shape_with_role(bench.store.looks["main_hand"], FigureEdits.ITEM_PART,
		FigureEdits.ROLE_METAL)
	var palette := bench.store.data_of(PALETTE, PALETTE)
	var dark := Color("102030")

	_expect(blade != null and metal >= 0, "a tier draws the parts of its base on a stand")
	_expect(_shape_color(bench, "body_1", STICK, FigureEdits.ITEM_PART, metal).is_equal_approx(
		bench.store.palette().color_of(MeshPalette.COPPER)),
		"the metal of a tier has the color of the tier, from the palette")

	FigureEdits.set_named_color(palette, MeshPalette.COPPER, dark)
	_expect(bench.put(PALETTE, PALETTE, palette).is_empty() and bench.has_unsaved_changes(),
		"the workbench takes a new palette")

	for body_key: String in bench.body_keys():
		_expect(_shape_color(bench, body_key, STICK, FigureEdits.ITEM_PART, metal)
			.is_equal_approx(dark), "the new color shows on the stand of %s" % body_key)

	_expect(bench.part_node("body_1", STICK, FigureEdits.ITEM_PART) == blade,
		"a part keeps its node through a change of the palette")


func _a_moved_tier_part_goes_into_its_base(bench: FigureWorkbench) -> void:
	var first := bench.part_node("body_1", STICK, FigureEdits.ITEM_PART)
	var second := bench.part_node("body_2", STICK, FigureEdits.ITEM_PART)
	var tier_text: String = bench.store.looks[STICK].to_text()
	var moved := Transform3D(Basis.IDENTITY, Vector3(0.0, 0.04, 0.01))

	_expect(bench.parts_owner(STICK) == "main_hand" and bench.parts_owner("main_hand") == "main_hand"
		and bench.parts_owner("no_such_look") == "no_such_look",
		"the parts of a tier are the parts of its last base")
	_expect(not bench.sync_from_nodes(), "a tier that nobody moved changes no look")

	first.transform = moved
	_expect(bench.sync_from_nodes(), "a moved part of a tier changes a look")
	_expect(FigureLook.part_transform(bench.store.looks["main_hand"].part(FigureEdits.ITEM_PART))
		.origin.distance_to(moved.origin) < TOLERANCE,
		"the place goes into the look that has the parts")
	_expect(bench.store.looks[STICK].to_text() == tier_text, "the file of the tier stays")
	_expect(second.transform.origin.distance_to(moved.origin) < TOLERANCE,
		"the part of the tier follows on the other stand")
	_expect(not bench.sync_from_nodes(), "the two nodes agree with the base after the move")


func _the_character_colors_go_over_the_body(bench: FigureWorkbench) -> void:
	var body: FigureLook = bench.store.looks["body_1"]
	var skin := _shape_with_role(body, "head", FigureEdits.SKIN_ROLE)
	var own := _shape_color(bench, "body_1", "body_1", "head", skin)
	var gold := bench.store.palette().color_of(MeshPalette.GOLD)
	var seen := []

	bench.figure_colors_changed.connect(func() -> void: seen.append(bench.figure_colors()))
	bench.set_figure_color(FigureEdits.SKIN_ROLE, MeshPalette.GOLD)
	_expect(seen == [{FigureEdits.SKIN_ROLE: MeshPalette.GOLD}],
		"a color of the character changes the colors one time: %s" % [seen])
	_expect(_shape_color(bench, "body_1", "body_1", "head", skin).is_equal_approx(gold)
		and _shape_color(bench, "body_2", "body_2", "head", skin).is_equal_approx(gold),
		"the skin of each stand has the color of the character")
	_expect(bench.store.looks["body_1"].to_text() == body.to_text(),
		"the colors of the character change no figure file")

	bench.set_figure_colors({FigureEdits.SKIN_ROLE: MeshPalette.GOLD})
	_expect(seen.size() == 1, "the same colors again change nothing")
	bench.set_figure_color(FigureEdits.SKIN_ROLE, "")
	_expect(bench.figure_colors().is_empty()
		and _shape_color(bench, "body_1", "body_1", "head", skin).is_equal_approx(own),
		"with no color of the character, the body has its own color again")
	bench.set_figure_colors({"skin": 3, "": MeshPalette.GOLD, "hair": ""})
	_expect(bench.figure_colors().is_empty() and seen.size() == 2,
		"an entry with no role or no color does not go in")


func _the_outfit_takes_a_stance(bench: FigureWorkbench, clips: String) -> void:
	var table := FigureEdits.new_stances()
	var path := clips.get_base_dir().path_join(FigureStances.FILE_NAME)

	_expect(bench.stances_path() == path, "the stance table is beside the clip directory")
	_expect(bench.stance_of_outfit().is_empty(), "with no stance table, the outfit has no stance")

	FigureEdits.set_stance_clip(table, "spear", "walk", "spear_walk")
	_expect(bench.put(STANCES, STANCES, table).is_empty() and bench.stance_of_outfit().is_empty(),
		"an outfit with no item that has a stance takes the default clip set")
	bench.wear("two_hands", PIKE)
	_expect(bench.stance_of_outfit() == "spear", "the outfit takes the stance of its spear")
	_expect(bench.save().has(FigureStances.FILE_NAME)
		and FigureStances.read_file(path).has_stance("spear"),
		"a save writes the stance table to its file")
	bench.reload()
	_expect(bench.store.stances().has_stance("spear") and bench.stance_of_outfit() == "spear",
		"a reload reads the stance table again")
	_a_clip_build_has_a_plan(bench, clips)


## The plan of a clip build, the clip files that it writes over, and the
## arguments of the import step. No build runs here.
func _a_clip_build_has_a_plan(bench: FigureWorkbench, clips: String) -> void:
	var walk := FigureClipImport.clip_path(clips, "walk")

	_expect(bench.put(FigureStore.KIND_CLIPS, "pack", CLIP_LIST.duplicate(true)).is_empty(),
		"the workbench takes a clip list")
	_expect(bench.overwritten_clip_files().is_empty(),
		"with no clip file on the disk, a build writes over nothing")
	DirAccess.make_dir_recursive_absolute(clips)

	var file := FileAccess.open(walk, FileAccess.WRITE)

	file.store_string("not a clip")
	file.close()
	_expect(bench.overwritten_clip_files() == PackedStringArray([walk]),
		"a build writes over the clip file that is there: %s" % [bench.overwritten_clip_files()])

	var plan := bench.clip_build_plan()

	_expect(plan["rows"].size() == 1 and plan["lines"].is_empty()
		and plan["rows"][0][0] == bench.store.clip_lists["pack"] and plan["rows"][0][3] == clips,
		"the plan has one row for the clip list, with the clip directory")
	_expect(bench.source_clips_arguments("pack").size() == 3
		and bench.source_clips_arguments("none").is_empty(),
		"the import step gets the clip list, its source directory, and a rig")
	_expect(not FigureWorkbench.run_clip_build(plan["rows"])[0].contains("built 1"),
		"a build with no source file builds no clip, and it says so")


## A job runs a routine on a thread. The result comes back through the
## callable of the start, when the owner takes it.
## The family stand (ENG-0011, steps L5 and L6): a scratch workbench keeps
## its look files below its figure directory. A shown family draws its
## shape on the stand. A new family row writes the file at once, it goes
## into the cache of the look file, and the stand draws it. A presentation
## row writes its file at once also. The two files are never unsaved.
func _the_family_stand_shows_an_entity() -> void:
	var Const := preload("res://autoload/blackout_constants.gd")
	var directory := _scratch.path_join("family_bench")
	var bench := FigureWorkbench.new()
	var weapon: String = Const.ITEM_FAMILY_WEAPON

	_filled_store(directory).save()
	bench.figure_directory = directory
	bench.clip_directory = directory.path_join("clips")
	bench.models_directory = _scratch.path_join("no_models")
	add_child(bench)
	await _frames(SETTLE_FRAMES)

	var look_path := bench.store.path_of(FigureStore.KIND_FAMILY, FigureStore.KIND_FAMILY)

	_expect(look_path.begins_with(directory) and not FileAccess.file_exists(look_path),
		"a scratch workbench keeps its look files below its figure directory: " + look_path)
	_expect(bench.entity_node() == null and bench.shown_family().is_empty(),
		"the family stand shows nothing at first")

	bench.show_entity("", weapon)
	_expect(bench.entity_node() != null
		and bench.entity_node().get_child_count() == FamilyShapes.SHAPES[weapon].size()
		and bench.entity_node().get_parent().position.x > bench.figure_of("body_2").position.x,
		"a shown family draws its table shape on the stand at the right")

	var content := {"format": 1, "families": {}, "models": {}}
	var seen := []

	FamilyLooks.put_look(content, weapon, FamilyLooks.row_from_parts(FamilyShapes.GENERIC))
	bench.changed.connect(func(kind: String, key: String) -> void: seen.append([kind, key]))
	_expect(bench.put(FigureStore.KIND_FAMILY, FigureStore.KIND_FAMILY, content).is_empty(),
		"the workbench takes a family file")
	_expect(FileAccess.file_exists(look_path) and bench.unsaved_names().is_empty()
		and seen == [[FigureStore.KIND_FAMILY, FigureStore.KIND_FAMILY]],
		"a family file writes at once, and it is never unsaved: %s" % [bench.unsaved_names()])
	_expect(FamilyShapes.parts_for(weapon).size() == FamilyShapes.GENERIC.size()
		and bench.entity_node().get_child_count() == FamilyShapes.GENERIC.size(),
		"the new row reaches the look file cache, and the stand draws it")

	var presentation := {"format": 1, "models": {}}

	ModelPresentation.set_model(presentation, "a_model", Vector3.ZERO, Vector3.ZERO, 2.0)
	_expect(bench.put(FigureStore.KIND_PRESENTATION, FigureStore.KIND_PRESENTATION,
		presentation).is_empty() and FileAccess.file_exists(bench.store.path_of(
			FigureStore.KIND_PRESENTATION, FigureStore.KIND_PRESENTATION))
		and bench.unsaved_names().is_empty()
		and is_equal_approx(ModelRegistry.new().scale_for("a_model"), 2.0),
		"a presentation file writes at once, and the registry reads it")

	bench.reload()
	await _frames(SETTLE_FRAMES)
	_expect(bench.store.families().has_family(weapon) and bench.store.presentation().has_model("a_model"),
		"a reload reads the two look files again")
	LookFile.forget(FamilyLooks.PATH)
	LookFile.forget(ModelPresentation.PATH)
	bench.queue_free()


func _a_job_runs_on_a_thread() -> void:
	var job := FigureJob.new()
	var seen := []
	var work := func() -> int:
		OS.delay_msec(JOB_SLEEP)
		return 42

	_expect(not job.is_running() and not job.is_done() and not job.finish(),
		"a new job runs nothing")
	_expect(job.start("a wait", work, func(result: int) -> void: seen.append(result)),
		"a job starts")
	_expect(not job.start("a second wait", work, func(_result: int) -> void: pass),
		"one job runs at a time")
	_expect(job.busy_text().contains("a wait"), "the busy text names the work")

	for _frame in JOB_FRAMES:
		if job.is_done():
			break

		await get_tree().process_frame

	_expect(job.is_done() and seen.is_empty(), "the job ended, and nothing took its result yet")
	_expect(job.finish() and seen == [42] and not job.is_done(),
		"the owner takes the result one time: %s" % [seen])
	job.wait()


## The figure files of the repository. This case writes nothing.
func _the_repository_files_read() -> void:
	var store := FigureStore.new(FigureStore.repo_directory())
	var first: FigureRig = null

	store.load_all()
	_expect(store.errors.is_empty(), "each figure file of the repository reads: %s" % store.errors)
	_expect(store.keys_of(RIG).size() >= 2, "the repository has two body types or more")

	for kind: String in FigureStore.KINDS:
		for key: String in store.keys_of(kind):
			var item := store.item_of(kind, key)

			_expect(FileAccess.get_file_as_string(store.path_of(kind, key)) == item.to_text(),
				"%s/%s is in its canonical text" % [kind, key])

	for key: String in store.keys_of(RIG):
		var rig: FigureRig = store.rigs[key]

		_a_repository_body_stands(store, rig)

		if first == null:
			first = rig

		_expect(rig.structure() == first.structure(), "%s has the bones of %s" % [key, first.key()])

		for bone: String in rig.bone_names():
			_expect(rig.bone(bone)["rotation"] == first.bone(bone).get("rotation"),
				"%s of %s has the rest rotation of %s" % [bone, key, first.key()])


## One body type of the repository: its body reads, and its mannequin
## stands with each part on a bone of the rig.
func _a_repository_body_stands(store: FigureStore, rig: FigureRig) -> void:
	var key := rig.key()

	_expect(store.has(LOOK, key), "the body type %s has a body" % key)

	if not store.has(LOOK, key):
		return

	var body: FigureLook = store.looks[key]
	var figure := FigureBuilder.build(rig, [body])

	_expect(body.parts().size() > 0
		and FigureBuilder.part_nodes(figure).size() == body.parts().size(),
		"a mannequin of %s stands, with each part on a bone of the rig" % key)

	for row: Dictionary in body.parts():
		_expect(rig.regions().has(row["region"]),
			"the part %s of %s is in a region of the rig" % [row["name"], key])

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
