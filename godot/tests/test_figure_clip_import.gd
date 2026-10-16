extends Node
## Tests for the clip import of the figure workbench (DESIGN-0014 Phase
## W2): [FigureClipImport] and `clip_extract.gd`.
##
##     godot --headless --path godot res://tests/test_figure_clip_import.tscn
##
## Needs no editor window. It starts Godot again for each build, so it
## takes some seconds. It writes only into a scratch directory under
## `user://` and into the cache directory of the OS. It reads the sources,
## the clip lists, and the clip files of the repository, and it never writes
## one. The cases:
##
## 1. A clip of the editor import keeps the rotation of each bone of the
##    rig and the position of the hips, and nothing more.
## 2. The T-pose clip of a source gives the rest pose of a figure. This
##    proves the retarget on a source rig that has no shoulder bone.
## 3. In the idle clip of that source, each arm hangs: the hand is below
##    the shoulder, and it is not in front of the chest.
## 4. A second build gives the same bytes.
## 5. A build of a source file that is not there gives a reason.
## 6. Each clip file of the repository is what its clip list builds now.
## 7. The import step alone gives the clips of the source, and it writes no
##    clip ("List source clips", ENG-0011).

const SOURCE := "kaykit_adventurers"
const REST_CLIP := "t_pose"
const IDLE_CLIP := "idle"

## The T-pose clip of the source is its rest pose, to this angle in
## radians: about 3 degrees.
const REST_TOLERANCE := 0.05

## A hand of an arm that hangs is this part of the arm length below its
## shoulder, or more. The arm length is a number of the rig.
const HANG_PART := 0.5

var _failures := 0
var _scratch := ""


func _ready() -> void:
	_scratch = ProjectSettings.globalize_path("user://figure_clip_import_test_%d"
		% Time.get_ticks_usec())

	_a_clip_keeps_the_tracks_of_a_figure()
	_a_build_fits_the_rig()
	_a_missing_source_gives_a_reason()
	_the_import_step_lists_the_source_clips()
	_the_repository_clips_are_current()
	_remove_scratch(_scratch)

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_clip_import")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _a_clip_keeps_the_tracks_of_a_figure() -> void:
	var rig := FigureEdits.rig_from_profile("body_1")
	var imported := Animation.new()

	imported.length = 2.0

	for row: Array in [["Hips", Animation.TYPE_POSITION_3D], ["Hips", Animation.TYPE_ROTATION_3D],
			["LeftUpperLeg", Animation.TYPE_POSITION_3D],
			["LeftUpperLeg", Animation.TYPE_ROTATION_3D],
			["LeftUpperLeg", Animation.TYPE_SCALE_3D], ["wrist.l", Animation.TYPE_ROTATION_3D]]:
		var track := imported.add_track(row[1])

		imported.track_set_path(track, "Rig/Skeleton3D:" + row[0])
		imported.track_insert_key(track, 0.0, Quaternion.IDENTITY
			if row[1] == Animation.TYPE_ROTATION_3D else Vector3.ONE)

	var clip := FigureClipImport.clip_from_import(imported, rig.bone_names(), true)
	var kept := []

	for track in clip.get_track_count():
		kept.append([String(clip.track_get_path(track)), clip.track_get_type(track)])

	_expect(kept == [["%GeneralSkeleton:Hips", Animation.TYPE_POSITION_3D],
			["%GeneralSkeleton:Hips", Animation.TYPE_ROTATION_3D],
			["%GeneralSkeleton:LeftUpperLeg", Animation.TYPE_ROTATION_3D]],
		"a clip keeps each rotation of the rig and the position of the hips: %s" % [kept])
	_expect(clip.length == imported.length and clip.loop_mode == Animation.LOOP_LINEAR
		and FigureClipImport.clip_from_import(imported, rig.bone_names(), false).loop_mode
			== Animation.LOOP_NONE, "a clip has the length of its source and its own loop")


## The clip list of the repository for the test source, with the clips of
## this test.
func _test_list() -> FigureClipList:
	var path := FigureStore.repo_directory().path_join(FigureStore.KIND_CLIPS).path_join(
		SOURCE + FigureClipList.FILE_SUFFIX)
	var data: Dictionary = FigureClipList.read_file(path).data.duplicate(true)

	data["clips"] = {REST_CLIP: {"from": "T-Pose", "loop": false},
		IDLE_CLIP: {"from": "Idle", "loop": true}}

	return FigureClipList.from_data(data)


func _a_build_fits_the_rig() -> void:
	var rig := FigureEdits.rig_from_profile("body_1")
	var list := _test_list()
	var first := _scratch.path_join("first")
	var second := _scratch.path_join("second")
	var source := FigureStore.repo_sources_directory().path_join(SOURCE)

	_expect(list.error.is_empty(), "the clip list of the test reads: " + list.error)

	var result := FigureClipImport.build(list, source, rig, first)

	_expect(result["error"].is_empty() and result["clips"].size() == 2,
		"the build writes each clip: %s" % [result])
	_expect("Idle" in result["source_clips"]
		and FigureClipImport.source_clips_of(SOURCE) == result["source_clips"],
		"the build gives the clips of the source")

	var library := FigureClips.library_from(first)

	if not library.has_animation(REST_CLIP) or not library.has_animation(IDLE_CLIP):
		_expect(false, "the library has the clips of the build")
		return

	_the_rest_clip_is_the_rest_pose(rig, library.get_animation(REST_CLIP))
	_the_arms_hang(rig, library.get_animation(IDLE_CLIP))
	_expect(library.get_animation(IDLE_CLIP).loop_mode == Animation.LOOP_LINEAR
		and library.get_animation(REST_CLIP).loop_mode == Animation.LOOP_NONE,
		"each clip has the loop of its row")

	FigureClipImport.build(list, source, rig, second)

	for clip_name: String in [REST_CLIP, IDLE_CLIP]:
		_expect(_bytes(FigureClipImport.clip_path(first, clip_name))
			== _bytes(FigureClipImport.clip_path(second, clip_name)),
			"a second build of %s gives the same bytes" % clip_name)


func _the_rest_clip_is_the_rest_pose(rig: FigureRig, clip: Animation) -> void:
	var skeleton := Skeleton3D.new()
	var worst := 0.0
	var worst_bone := ""

	rig.apply_to(skeleton)
	FigureClips.pose(skeleton, clip, 0.0)

	for index in skeleton.get_bone_count():
		var posed := FigureClips.global_pose(skeleton, index).basis.get_rotation_quaternion()
		var rest := skeleton.get_bone_global_rest(index).basis.get_rotation_quaternion()

		if posed.angle_to(rest) > worst:
			worst = posed.angle_to(rest)
			worst_bone = skeleton.get_bone_name(index)

	_expect(worst < REST_TOLERANCE, "the T-pose clip gives the rest pose. Worst: %s, %.3f radians"
		% [worst_bone, worst])
	_expect(FigureClips.bones_of(clip).has("LeftUpperArm")
		and not FigureClips.bones_of(clip).has("LeftShoulder"),
		"the clip moves the bones that the source has, and no other")
	skeleton.free()


func _the_arms_hang(rig: FigureRig, clip: Animation) -> void:
	var skeleton := Skeleton3D.new()

	rig.apply_to(skeleton)
	FigureClips.pose(skeleton, clip, 0.0)

	for side: String in ["Left", "Right"]:
		var hand := FigureClips.global_pose(skeleton, skeleton.find_bone(side + "Hand")).origin
		var shoulder := FigureClips.global_pose(skeleton,
			skeleton.find_bone(side + "UpperArm")).origin

		var arm := rig.global_rest_of(side + "Hand").origin.distance_to(
			rig.global_rest_of(side + "UpperArm").origin)

		_expect(hand.y < shoulder.y - arm * HANG_PART,
			"the %s hand is below its shoulder" % side)
		_expect(absf(hand.x) > absf(shoulder.x), "the %s hand is not in front of the chest" % side)

	skeleton.free()


func _a_missing_source_gives_a_reason() -> void:
	var result := FigureClipImport.build(_test_list(), _scratch.path_join("no_source"),
		FigureEdits.rig_from_profile("body_1"), _scratch.path_join("never"))

	_expect(not result["error"].is_empty() and result["clips"].is_empty(),
		"a build with no source file gives a reason")
	_expect(not DirAccess.dir_exists_absolute(_scratch.path_join("never")),
		"a build that stops writes no clip")


func _the_import_step_lists_the_source_clips() -> void:
	var list := _test_list()
	var source := FigureStore.repo_sources_directory().path_join(SOURCE)
	var result := FigureClipImport.import_source(list, source,
		FigureEdits.rig_from_profile("body_1"), PackedStringArray())
	var out := FigureClipImport.work_directory(list.key()).path_join(
		FigureClipImport.OUT_DIRECTORY)

	_expect(result["error"].is_empty() and "Idle" in result["source_clips"]
		and result["clips"].is_empty(), "the import step gives the clips of the source: %s"
			% [result])
	_expect(DirAccess.get_files_at(out) == PackedStringArray([FigureClipImport.NAMES_FILE]),
		"the import step with no clip writes only the names: %s" % [DirAccess.get_files_at(out)])


## Each clip list of the repository, built again into the scratch
## directory. This case writes nothing into the repository.
func _the_repository_clips_are_current() -> void:
	var store := FigureStore.new(FigureStore.repo_directory())
	var out := _scratch.path_join("current")

	store.load_all()
	_expect(not store.keys_of(FigureStore.KIND_RIG).is_empty(), "the repository has a rig")

	for key: String in store.keys_of(FigureStore.KIND_CLIPS):
		var list: FigureClipList = store.clip_lists[key]
		var result := FigureClipImport.build(list,
			FigureStore.repo_sources_directory().path_join(key),
			store.rigs[store.keys_of(FigureStore.KIND_RIG)[0]], out)

		_expect(result["error"].is_empty(), "the clip list %s builds: %s" % [key, result["error"]])

		for clip_name: String in list.clip_names():
			_expect(_bytes(FigureClipImport.clip_path(out, clip_name))
				== _bytes(FigureClipImport.clip_path(FigureClips.CLIP_DIRECTORY, clip_name)),
				"the clip file %s is current. If not, build the clips in the workbench." % clip_name)


func _bytes(path: String) -> PackedByteArray:
	return FileAccess.get_file_as_bytes(path)


## Delete the scratch tree of this test: files first, then directories.
func _remove_scratch(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return

	for child: String in DirAccess.get_directories_at(path):
		_remove_scratch(path.path_join(child))

	for file_name: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(file_name))

	DirAccess.remove_absolute(path)
