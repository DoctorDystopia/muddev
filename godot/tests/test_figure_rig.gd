extends Node
## Tests for the rig file and its reader (DESIGN-0014 Phase W1):
## [FigureRig] and [FigureJson].
##
##     godot --headless --path godot res://tests/test_figure_rig.tscn
##
## Needs nothing running and no editor. It writes only into a scratch
## directory under `user://`. The cases:
##
## 1. A rig from the humanoid profile has the body bones and the sockets,
##    and each table names only bones of the rig.
## 2. A rig text that is read and written gives the same bytes.
## 3. A rig from its text has the same rest pose.
## 4. The reader refuses a file with a bad form, and a newer format.
## 5. A file whose key is not its name does not read.
## 6. A skeleton takes a changed rig in place.
## 7. Two body types share each bone name and each rest rotation.

const LIMB_SCALE := 0.9
const SOCKET := "hand_r"
const NEW_SOCKET := "knee_r"

var _failures := 0
var _scratch := ""


func _ready() -> void:
	_scratch = ProjectSettings.globalize_path("user://figure_rig_test_%d"
		% Time.get_ticks_usec())

	_the_profile_gives_a_rig()
	_a_rig_text_gives_the_same_bytes()
	_a_rig_from_its_text_has_the_same_rest()
	_the_reader_refuses_a_bad_form()
	_a_key_must_be_the_file_name()
	_a_skeleton_takes_a_changed_rig_in_place()
	_two_body_types_share_one_clip()
	_remove_scratch(_scratch)

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_rig")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _the_profile_gives_a_rig() -> void:
	var rig := FigureEdits.rig_from_profile("body_1")

	_expect(rig.error.is_empty(), "the profile rig reads: " + rig.error)
	_expect(rig.has_bone("Hips") and rig.has_bone("Head"), "the rig has the body bones")
	_expect(not rig.has_bone("LeftIndexProximal"), "the rig has no finger bone")
	_expect(rig.is_socket(SOCKET) and rig.has_bone(SOCKET), "a socket is a bone")
	_expect(not rig.is_socket("Head"), "a body bone is not a socket")
	_expect(rig.bone(SOCKET)["parent"] == FigureEdits.SOCKETS[SOCKET][0],
		"a socket hangs on its parent bone")

	for socket: String in rig.sockets():
		_expect(rig.has_bone(socket), "the socket %s is a bone" % socket)

	for slot: String in rig.slots():
		_expect(rig.has_bone(rig.slots()[slot]), "the slot %s names a bone" % slot)

	for region: String in rig.regions():
		for bone: String in rig.regions()[region]:
			_expect(rig.has_bone(bone), "the region %s names the bone %s" % [region, bone])

	_expect(rig.region_of("Head") == "head", "a new part on the head gets the head region")
	_expect(rig.region_of(SOCKET).is_empty(), "a hand socket is in no region")
	_expect(rig.global_rest_of("Head").origin.y > rig.global_rest_of("Hips").origin.y,
		"the head is above the hips")


func _a_rig_text_gives_the_same_bytes() -> void:
	var rig := FigureEdits.rig_from_profile("body_1", LIMB_SCALE)
	var text := rig.to_text()
	var again := FigureRig.from_text(text)

	_expect(again.error.is_empty(), "the text reads: " + again.error)
	_expect(again.to_text() == text, "a read and a write give the same bytes")
	_expect(text.ends_with("}\n"), "the text ends with one new line")
	_expect(text.contains("\"format\": 1,"), "the format is an integer in the text")
	_expect(not text.contains("-0.0,") and not text.contains("-0.0\n"),
		"the text holds no negative zero")
	_expect(FigureJson.to_text({"a": -0.000001}) == "{\n\t\"a\": 0.0\n}\n",
		"a negative zero becomes zero")
	_expect(FigureJson.to_text({"b": 1.000004, "a": [0.5]})
		== "{\n\t\"a\": [\n\t\t0.5\n\t],\n\t\"b\": 1.0\n}\n",
		"the keys are sorted, and each number has five digits")


func _a_rig_from_its_text_has_the_same_rest() -> void:
	var rig := FigureEdits.rig_from_profile("body_1")
	var again := FigureRig.from_text(rig.to_text())
	var first := Skeleton3D.new()
	var second := Skeleton3D.new()
	var same := true

	rig.apply_to(first)
	again.apply_to(second)
	_expect(first.get_bone_count() == rig.bones().size(),
		"the skeleton has one bone for each bone of the rig")

	for bone in first.get_bone_count():
		same = same and first.get_bone_rest(bone).is_equal_approx(second.get_bone_rest(bone))
		same = same and first.get_bone_parent(bone) == second.get_bone_parent(bone)

	_expect(same, "a rig from its text has the same rest pose")
	_expect(first.get_bone_parent(first.find_bone(SOCKET)) == first.find_bone("RightHand"),
		"a socket has its parent in the skeleton")
	first.free()
	second.free()


func _the_reader_refuses_a_bad_form() -> void:
	var good := FigureEdits.rig_from_profile("body_1").data

	_expect(not FigureRig.from_text("not json").error.is_empty(), "a bad text does not read")
	_expect(not _changed(good, "format", null).error.is_empty(), "a rig needs a format")
	_expect(not _changed(good, "format", FigureRig.FORMAT + 1).error.is_empty(),
		"a newer format does not read")
	_expect(_changed(good, "format", FigureRig.FORMAT).error.is_empty(),
		"the format of this reader reads")
	_expect(not _changed(good, "key", "").error.is_empty(), "a rig needs a key")
	_expect(not _changed(good, "bones", []).error.is_empty(), "a rig needs bones")
	_expect(not _changed(good, "slots", []).error.is_empty(), "the slots are a table")

	var twice: Dictionary = good.duplicate(true)

	twice["bones"].append(twice["bones"][0].duplicate(true))
	_expect(not FigureRig.from_data(twice).error.is_empty(), "two bones cannot share a name")

	var orphan: Dictionary = good.duplicate(true)

	orphan["bones"][1]["parent"] = "NoSuchBone"
	_expect(not FigureRig.from_data(orphan).error.is_empty(), "a parent must be a bone")

	var short: Dictionary = good.duplicate(true)

	short["bones"][1]["position"] = [0.0, 1.0]
	_expect(not FigureRig.from_data(short).error.is_empty(), "a position is three numbers")

	var bare := FigureRig.from_data({"format": 1, "key": "bare", "bones": [
		{"name": "Root", "parent": "", "position": [0, 0, 0], "rotation": [0, 0, 0, 1]}]})

	_expect(bare.error.is_empty() and bare.slots().is_empty() and bare.motion_scale() == 1.0,
		"a rig with no table reads, with empty tables: " + bare.error)


## The rig of `good` with one key changed. A null value removes the key.
func _changed(good: Dictionary, key: String, value: Variant) -> FigureRig:
	var data: Dictionary = good.duplicate(true)

	if value == null:
		data.erase(key)
	else:
		data[key] = value

	return FigureRig.from_data(data)


func _a_key_must_be_the_file_name() -> void:
	var rig := FigureEdits.rig_from_profile("body_1")
	var right := _scratch.path_join("body_1.json")
	var wrong := _scratch.path_join("other.json")

	_expect(rig.write_file(right) == OK and rig.write_file(wrong) == OK,
		"the rig writes into the scratch directory")
	_expect(FigureRig.read_file(right).error.is_empty(), "a file with its key as its name reads")
	_expect(FileAccess.get_file_as_string(right) == rig.to_text(),
		"the file holds the canonical text")
	_expect(not FigureRig.read_file(wrong).error.is_empty(),
		"a file with another name does not read")
	_expect(not FigureRig.read_file(_scratch.path_join("none.json")).error.is_empty(),
		"a missing file does not read")


func _a_skeleton_takes_a_changed_rig_in_place() -> void:
	var rig := FigureEdits.rig_from_profile("body_1")
	var skeleton := Skeleton3D.new()
	var data: Dictionary = rig.data.duplicate(true)
	var moved := Vector3(0.0, 0.2, 0.1)

	rig.apply_to(skeleton)

	var count := skeleton.get_bone_count()

	_expect(FigureEdits.set_bone_position(data, SOCKET, moved).is_empty(), "a bone moves")
	FigureRig.from_data(data).apply_to(skeleton)
	_expect(skeleton.get_bone_count() == count, "a moved bone adds no bone")
	_expect(skeleton.get_bone_rest(skeleton.find_bone(SOCKET)).origin.is_equal_approx(moved),
		"the skeleton has the new rest")
	_expect(skeleton.get_bone_pose_position(skeleton.find_bone(SOCKET)).is_equal_approx(moved),
		"the pose follows the new rest")

	_expect(FigureEdits.add_socket(data, NEW_SOCKET, "RightLowerLeg").is_empty(),
		"a socket joins the rig")
	FigureRig.from_data(data).apply_to(skeleton)
	_expect(skeleton.get_bone_count() == count + 1, "the skeleton gets the new bone")
	_expect(skeleton.get_bone_parent(skeleton.find_bone(NEW_SOCKET))
		== skeleton.find_bone("RightLowerLeg"), "the new bone has its parent")
	skeleton.free()


func _two_body_types_share_one_clip() -> void:
	var first := FigureEdits.rig_from_profile("body_1")
	var second := FigureEdits.rig_from_profile("body_2", LIMB_SCALE)
	var same := true

	_expect(first.structure() == second.structure(), "the two rigs have the same bones")

	for bone: String in first.bone_names():
		same = same and first.bone(bone)["rotation"] == second.bone(bone)["rotation"]

	_expect(same, "the two rigs have the same rest rotations")
	_expect(is_equal_approx(second.global_rest_of("Hips").origin.y,
		first.global_rest_of("Hips").origin.y * LIMB_SCALE), "the limb scale moves the hips")
	_expect(is_equal_approx(second.motion_scale(), second.global_rest_of("Hips").origin.y),
		"the motion scale of a rig is its hips height")
	_expect(is_equal_approx(second.motion_scale(), first.motion_scale() * LIMB_SCALE),
		"the motion scale follows the limb scale")

	var old: Dictionary = first.data.duplicate(true)

	old["motion_scale"] = 3.0

	var read := FigureRig.from_data(old)

	_expect(read.error.is_empty() and read.to_text() == first.to_text(),
		"the reader drops the motion scale key of a Phase W1 file")
	_expect(first.rest_of(SOCKET).basis.is_equal_approx(Basis(FigureEdits.GRIP_R)),
		"the hand socket has the grip as its rest rotation")
	_expect(first.global_rest_of("hand_r").basis.is_equal_approx(
		first.global_rest_of("hand_l").basis), "the two hand sockets have the same axes")
	_expect(first.global_rest_of(SOCKET).basis.y.is_equal_approx(Vector3.BACK),
		"a held item points forward in the rest pose")


## Delete the scratch tree of this test: files first, then directories.
func _remove_scratch(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return

	for child: String in DirAccess.get_directories_at(path):
		_remove_scratch(path.path_join(child))

	for file_name: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(file_name))

	DirAccess.remove_absolute(path)
