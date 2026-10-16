extends Node
## Tests for the clips of a figure (DESIGN-0014 Phase W2): [FigureClips],
## [FigureClipList], [FigureClearance], the clips of the workbench, and
## the clip files of the repository.
##
##     godot --headless --path godot res://tests/test_figure_clips.tscn
##
## Needs nothing running and no editor. It writes only into a scratch
## directory under `user://`. It reads the clip files and the figure files
## of the repository, and it never writes one. The cases:
##
## 1. A clip finds the skeleton of a figure by its unique name, and the
##    player moves the bone.
## 2. The pose of one moment is the pose that the player gives.
## 3. One clip moves two body types, and the hips follow the hips height.
## 4. A library has each clip file of its directory, by file name.
## 5. A clip list reads, writes the same bytes, and refuses a bad form.
## 6. A clip list takes a clip, changes it, and loses it.
## 7. The probe of a hand that goes into the other arm is not clear. In
##    the rest pose it is clear.
## 8. The workbench plays one clip on each stand, holds it, and stops.
## 9. The probe shows on each stand, and a ray goes through it.
## 10. Each clip of the repository moves only bones of each rig, keeps one
##     position track, and holds an item clear of the body.

const CLIP := "nod"
const BONE := "RightUpperArm"
const TURN := 1.2
const SECONDS := 1.0
const LIMB_SCALE := 0.9
const HIPS_PART := 0.8
const TOLERANCE := 0.001
const SETTLE_FRAMES := 2

var _failures := 0
var _scratch := ""


func _ready() -> void:
	_scratch = ProjectSettings.globalize_path("user://figure_clips_test_%d"
		% Time.get_ticks_usec())

	await _a_clip_finds_the_skeleton()
	_one_clip_moves_two_body_types()
	_a_library_has_each_clip_file()
	_a_clip_list_reads_and_writes()
	_a_clip_list_takes_and_loses_a_clip()
	_the_probe_finds_a_hand_in_an_arm()
	await _the_workbench_plays_a_clip()
	_the_repository_clips_fit_each_rig()
	_remove_scratch(_scratch)

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_clips")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _frames(count: int) -> void:
	for _frame in count:
		await get_tree().process_frame


## A clip that turns one bone about its X axis from its rest, and that
## holds the hips at a part of the hips height.
func _clip_for(rig: FigureRig, bone: String, turn: float) -> Animation:
	var clip := Animation.new()
	var rest := rig.rest_of(bone).basis.get_rotation_quaternion()
	var track := clip.add_track(Animation.TYPE_ROTATION_3D)
	var hips := clip.add_track(Animation.TYPE_POSITION_3D)

	clip.length = SECONDS
	clip.track_set_path(track, FigureClips.track_path(bone))
	clip.rotation_track_insert_key(track, 0.0, rest)
	clip.rotation_track_insert_key(track, SECONDS, rest * Quaternion(Vector3.RIGHT, turn))
	clip.track_set_path(hips, FigureClips.track_path(FigureRig.SCALE_BONE))
	clip.position_track_insert_key(hips, 0.0, Vector3(0.0, HIPS_PART, 0.0))
	clip.position_track_insert_key(hips, SECONDS, Vector3(0.0, HIPS_PART, 0.0))

	return clip


func _library_for(rig: FigureRig) -> AnimationLibrary:
	var library := AnimationLibrary.new()

	library.add_animation(CLIP, _clip_for(rig, BONE, TURN))

	return library


func _a_clip_finds_the_skeleton() -> void:
	var rig := FigureEdits.rig_from_profile("body_1")
	var figure := FigureBuilder.build(rig, [FigureEdits.mannequin(rig)])
	var skeleton := FigureBuilder.skeleton_of(figure)
	var bone := skeleton.find_bone(BONE)
	var library := _library_for(rig)
	var clip := library.get_animation(CLIP)

	add_child(figure)
	_expect(figure.get_node_or_null(FigureClips.TRACK_NODE) == skeleton,
		"the unique name of the skeleton resolves from the figure")

	var player := FigureClips.player_of(figure, library)

	_expect(FigureClips.player_of(figure) == player and player.get_parent() == figure,
		"a figure has one player, on the figure node")
	_expect(not FigureClips.play(figure, "none") and FigureClips.play(figure, CLIP),
		"a figure plays only a clip of its library")
	player.seek(SECONDS * 0.5, true)
	player.pause()
	await _frames(SETTLE_FRAMES)

	var played := skeleton.get_bone_global_pose(bone)
	var hips := skeleton.get_bone_pose_position(skeleton.find_bone(FigureRig.SCALE_BONE))

	_expect(not played.basis.is_equal_approx(skeleton.get_bone_global_rest(bone).basis),
		"the player moves the bone")
	_expect(is_equal_approx(hips.y, HIPS_PART * rig.motion_scale()),
		"the hips are at their part of the hips height")
	FigureClips.pose(skeleton, clip, SECONDS * 0.5)
	_expect(FigureClips.global_pose(skeleton, bone).is_equal_approx(played),
		"the pose of one moment is the pose of the player")
	_expect(FigureClips.bones_of(clip) == PackedStringArray([FigureRig.SCALE_BONE, BONE]),
		"a clip names the bones that it moves: %s" % [FigureClips.bones_of(clip)])

	FigureClips.stop(figure)
	_expect(skeleton.get_bone_pose(bone).is_equal_approx(skeleton.get_bone_rest(bone)),
		"a stop gives the rest pose")
	figure.queue_free()


func _one_clip_moves_two_body_types() -> void:
	var first := FigureEdits.rig_from_profile("body_1")
	var second := FigureEdits.rig_from_profile("body_2", LIMB_SCALE)
	var clip := _clip_for(first, BONE, TURN)
	var heights := []
	var turns := []

	for rig: FigureRig in [first, second]:
		var skeleton := Skeleton3D.new()

		rig.apply_to(skeleton)
		FigureClips.pose(skeleton, clip, SECONDS)
		heights.append(FigureClips.global_pose(skeleton,
			skeleton.find_bone(FigureRig.SCALE_BONE)).origin.y)
		turns.append(FigureClips.global_pose(skeleton, skeleton.find_bone(BONE)).basis)
		skeleton.free()

	_expect(turns[0].is_equal_approx(turns[1]), "one clip turns the bone the same on each rig")
	_expect(is_equal_approx(heights[1], heights[0] * LIMB_SCALE),
		"the hips of the short rig are lower by its limb scale")


func _a_library_has_each_clip_file() -> void:
	var directory := _scratch.path_join("clips")
	var rig := FigureEdits.rig_from_profile("body_1")

	DirAccess.make_dir_recursive_absolute(directory)

	for clip_name: String in ["wave", "bow"]:
		ResourceSaver.save(_clip_for(rig, BONE, TURN),
			directory.path_join(clip_name + FigureClips.CLIP_SUFFIX))

	var library := FigureClips.library_from(directory)

	_expect(FigureClips.names_of(library) == PackedStringArray(["bow", "wave"]),
		"a library has each clip file, by its file name")
	_expect(FigureClips.names_of(FigureClips.library_from(_scratch.path_join("none"))).is_empty(),
		"a directory that is not there gives an empty library")


func _clip_list() -> Dictionary:
	return {"format": 1, "key": "pack", "file": "rig.glb", "skeleton": "Rig/Skeleton3D",
		"bones": {"Hips": "hips"}, "clips": {"walk": {"from": "Walking", "loop": true}}}


func _a_clip_list_reads_and_writes() -> void:
	var list := FigureClipList.from_data(_clip_list())
	var path := _scratch.path_join("lists").path_join("pack.json")

	_expect(list.error.is_empty() and list.key() == "pack", "a clip list reads: " + list.error)
	_expect(list.source_clip("walk") == "Walking" and list.loops("walk")
		and not list.loops("none"), "a clip list gives the row of a clip")
	_expect(FigureClipList.from_text(list.to_text()).to_text() == list.to_text(),
		"a clip list text that is read and written gives the same bytes")
	_expect(list.write_file(path) == OK and FigureClipList.read_file(path).error.is_empty(),
		"a clip list file with its key as its name reads")

	for change: Array in [["format", 99], ["file", ""], ["skeleton", null], ["bones", {}],
			["clips", {"Bad Name": {"from": "x"}}], ["clips", {"walk": {"loop": true}}],
			["clips", {"walk": {"from": "x", "loop": "yes"}}]]:
		var data := _clip_list()

		if change[1] == null:
			data.erase(change[0])
		else:
			data[change[0]] = change[1]

		_expect(not FigureClipList.from_data(data).error.is_empty(),
			"a clip list with a bad %s does not read" % change[0])


func _a_clip_list_takes_and_loses_a_clip() -> void:
	var data := _clip_list()

	_expect(FigureEdits.set_clip(data, "run", "Running_A", true).is_empty()
		and data["clips"]["run"] == {"from": "Running_A", "loop": true},
		"a clip list takes a clip")
	_expect(FigureEdits.set_clip(data, "run", "Running_B", false).is_empty()
		and data["clips"]["run"]["from"] == "Running_B", "a clip of the list takes a new row")
	_expect(not FigureEdits.set_clip(data, "Run Fast", "x", true).is_empty()
		and not FigureEdits.set_clip(data, "sprint", "", true).is_empty(),
		"a clip needs a good name and a source clip")
	_expect(FigureClipList.from_data(data).error.is_empty(), "the changed clip list reads")
	_expect(FigureEdits.remove_clip(data, "run").is_empty() and not data["clips"].has("run")
		and not FigureEdits.remove_clip(data, "run").is_empty(), "a clip list loses a clip")


func _the_probe_finds_a_hand_in_an_arm() -> void:
	var rig := FigureEdits.rig_from_profile("body_1")
	var body := FigureEdits.mannequin(rig)
	var rest := Animation.new()
	var hand := FigureClearance.hand_bones(rig)

	rest.length = SECONDS
	_expect(hand == PackedStringArray([rig.slots()["main_hand"], rig.slots()["off_hand"]]),
		"the probe is on the bone of each hand slot")

	var clear := FigureClearance.check(rig, body, rest)

	_expect(FigureClearance.is_clear(clear) and clear["gap"] > 0.0,
		"the probe is clear of the body in the rest pose: %s" % [clear])

	# The right arm turns half a circle about the up axis of the figure. Its
	# hand is then inside the left arm, and the grip of the probe with it.
	var bad := _clip_for(rig, BONE, 0.0)
	var arm := bad.find_track(FigureClips.track_path(BONE), Animation.TYPE_ROTATION_3D)
	var in_figure := rig.global_rest_of(BONE).basis.get_rotation_quaternion()
	var across := in_figure.inverse() * Quaternion(Vector3.UP, PI) * in_figure

	bad.track_set_key_value(arm, 1,
		rig.rest_of(BONE).basis.get_rotation_quaternion() * across)

	var hit := FigureClearance.check(rig, body, bad)

	_expect(not FigureClearance.is_clear(hit) and hit["hand"] == "hand_r"
		and hit["time"] > SECONDS * 0.5,
		"a probe inside the other arm is not clear: %s" % [hit])
	_expect(FigureClearance.line_of("bad", hit).contains(hit["part"])
		and FigureClearance.line_of("rest", clear).contains("clear"),
		"the line of a result names the part, or says clear")
	_expect(FigureClearance.probe_look(rig).error.is_empty()
		and FigureClearance.probe_look(rig).parts().size() == hand.size(),
		"the probe is a worn look with one part for each hand")


func _the_workbench_plays_a_clip() -> void:
	var directory := _scratch.path_join("bench")
	var clip_directory := _scratch.path_join("bench_clips")
	var bench := FigureWorkbench.new()
	var store := FigureStore.new(directory)

	for pair: Array in [["body_1", 1.0], ["body_2", LIMB_SCALE]]:
		var rig := FigureEdits.rig_from_profile(pair[0], pair[1])

		store.put(FigureStore.KIND_RIG, pair[0], rig.data)
		store.put(FigureStore.KIND_LOOK, pair[0], FigureEdits.mannequin(rig).data)

	store.save()
	DirAccess.make_dir_recursive_absolute(clip_directory)
	ResourceSaver.save(_clip_for(store.rigs["body_1"], BONE, TURN),
		clip_directory.path_join(CLIP + FigureClips.CLIP_SUFFIX))
	bench.figure_directory = directory
	bench.clip_directory = clip_directory
	add_child(bench)
	await _frames(SETTLE_FRAMES)

	_expect(bench.clip_names() == PackedStringArray([CLIP]), "the workbench has the clips")
	_expect(is_equal_approx(bench.clip_length(CLIP), SECONDS) and bench.clip_length("none") == 0.0,
		"the workbench gives the length of a clip")
	_expect(not bench.play_clip("none") and bench.show_clip(CLIP, SECONDS)
		and not bench.is_playing() and bench.shown_clip() == CLIP,
		"the workbench holds each stand at one moment of a clip")
	await _frames(SETTLE_FRAMES)

	var turns := []

	for body_key: String in bench.body_keys():
		var skeleton := FigureBuilder.skeleton_of(bench.figure_of(body_key))

		turns.append(skeleton.get_bone_pose_rotation(skeleton.find_bone(BONE)))

	_expect(turns[0].is_equal_approx(turns[1]) and not turns[0].is_equal_approx(
		bench.store.rigs["body_1"].rest_of(BONE).basis.get_rotation_quaternion()),
		"each stand shows the same moment of the clip")
	_expect(is_equal_approx(bench.clip_time(), SECONDS), "the workbench gives the time of the clip")
	_expect(bench.play_clip(CLIP) and bench.is_playing(), "the workbench plays a clip")
	_expect(not bench.sync_from_nodes(), "a clip moves no part on its bone")
	_expect(bench.clearance_lines(CLIP).size() == 2 and bench.clearance_lines("none").is_empty(),
		"the workbench gives one clearance line for each body type")
	_the_probe_shows(bench)
	bench.stop_clip()
	_expect(bench.shown_clip().is_empty() and not bench.is_playing(),
		"a stop puts each stand in its rest pose")
	bench.queue_free()


func _the_probe_shows(bench: FigureWorkbench) -> void:
	var before: int = bench.counts_of("body_1")["parts"]
	var rig: FigureRig = bench.store.rigs["body_1"]

	bench.show_probe = true

	var probe := bench.part_node("body_1", FigureClearance.PROBE_LOOK, "probe_hand_r")

	_expect(bench.counts_of("body_1")["parts"] == before + FigureClearance.hand_bones(rig).size()
		and probe != null, "the probe shows in each hand")
	_expect(bench.is_playing(), "the clip plays on while the probe joins")
	bench.stop_clip()

	if probe != null:
		var grip := bench.figure_of("body_1").global_transform * rig.global_rest_of("hand_r")
		var on_probe := grip * Vector3(0.0, FigureClearance.PROBE_LENGTH * 0.8, 0.0)

		_expect(bench.part_at(on_probe + Vector3(0.0, 5.0, 0.0), Vector3.DOWN) == null,
			"a ray goes through the probe")

	bench.show_probe = false
	_expect(bench.counts_of("body_1")["parts"] == before and not bench.has_unsaved_changes(),
		"the probe leaves, and it changes no file")


## The clip files and the figure files of the repository. This case writes
## nothing.
func _the_repository_clips_fit_each_rig() -> void:
	var store := FigureStore.new(FigureStore.repo_directory())
	var library := FigureClips.library()

	store.load_all()
	_expect(not FigureClips.names_of(library).is_empty(), "the game has a clip")

	for key: String in store.keys_of(FigureStore.KIND_CLIPS):
		for clip_name: String in store.clip_lists[key].clip_names():
			_expect(library.has_animation(clip_name),
				"the clip %s of the clip list %s has a clip file. Build the clips." % [clip_name, key])

	for clip_name: String in FigureClips.names_of(library):
		var clip := library.get_animation(clip_name)
		var positions := 0

		for track in clip.get_track_count():
			_expect(String(clip.track_get_path(track)).begins_with(FigureClips.TRACK_NODE + ":"),
				"each track of %s names the skeleton by its unique name" % clip_name)

			if clip.track_get_type(track) == Animation.TYPE_POSITION_3D:
				positions += 1
				_expect(FigureClips.track_bone(clip, track) == FigureRig.SCALE_BONE,
					"the one position track of %s moves the hips" % clip_name)

		_expect(positions <= 1, "%s has one position track at most" % clip_name)

		for key: String in store.keys_of(FigureStore.KIND_RIG):
			var rig: FigureRig = store.rigs[key]

			for bone: String in FigureClips.bones_of(clip):
				_expect(rig.has_bone(bone), "%s moves the bone %s, which %s has"
					% [clip_name, bone, key])

			var result := FigureClearance.check(rig, store.looks[key], clip)

			_expect(FigureClearance.is_clear(result), "%s on %s: %s"
				% [clip_name, key, FigureClearance.line_of(clip_name, result)])


## Delete the scratch tree of this test: files first, then directories.
func _remove_scratch(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return

	for child: String in DirAccess.get_directories_at(path):
		_remove_scratch(path.path_join(child))

	for file_name: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(file_name))

	DirAccess.remove_absolute(path)
