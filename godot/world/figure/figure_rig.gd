class_name FigureRig
extends RefCounted
## One rig: the bones, the sockets, the regions, and the slot table of one
## body type (DESIGN-0014 section 8.1).
##
## The figure workbench writes a rig file to `blackout/assets/figure/rigs/`.
## The game and the workbench read it with this class (requirement D6).
##
## ## The file
##
##     format        1
##     key           the body type, the same as the file name
##     bones         [{name, parent, position, rotation}, ...]
##     sockets       the bones that carry gear and no body part
##     regions       region -> the bones of that region
##     slots         slot -> the default bone of that slot
##
## A `position` is `[x, y, z]` on the parent bone. A `rotation` is the
## `[x, y, z, w]` of the rest rotation. A bone with no parent has `""`.
##
## ## Two body types, one clip
##
## The bone names follow [SkeletonProfileHumanoid]. Each rig has the same
## bone names and the same rest rotations. Only the positions differ. Thus,
## one clip moves each body type.
##
## A clip holds the position of the hips as a part of the hips height, as
## the retarget of the Godot editor import writes it. [method motion_scale]
## is the hips height of this rig, and [member Skeleton3D.motion_scale]
## multiplies the track by it. The file does not hold the number, because
## the hips bone owns it. Until Phase W2 the file had a `motion_scale` key.
## The reader drops it.
##
## ## A file that does not read
##
## [method from_data] refuses a file with a fault in its form, and
## [member error] says why. A bone name that a region or a slot gets wrong
## is not such a fault. The check of the workbench finds it.

## The newest format that this reader knows. It reads each older format.
const FORMAT := 1

const FILE_SUFFIX := ".json"

## The bone whose height scales each position track of a clip. It is the
## scale base bone of [SkeletonProfileHumanoid].
const SCALE_BONE := "Hips"

## The key that a rig file of Phase W1 has, and that this reader drops.
const _OLD_MOTION_KEY := "motion_scale"

var data := {}

## Why the rig does not read, or "" for a rig that reads.
var error := ""

## The index of each bone in [member data], by bone name.
var _index := {}


# ─── Reading and writing ────────────────────────────────────────────────────

## The rig of a parsed rig file. Check [member error] after.
static func from_data(parsed: Variant) -> FigureRig:
	var rig := FigureRig.new()

	if typeof(parsed) != TYPE_DICTIONARY or parsed.is_empty():
		rig.error = "a rig file must hold one JSON object"
		return rig

	var canonical: Dictionary = FigureJson.canonical(parsed)

	rig.error = _problem(canonical)

	if rig.error.is_empty():
		rig.data = _with_defaults(canonical)
		rig._build_index()

	return rig


## The rig of a rig file text. Check [member error] after.
static func from_text(text: String) -> FigureRig:
	return from_data(FigureJson.parse(text))


## Read one rig file. The key must be the file name. Check [member error]
## after.
static func read_file(path: String) -> FigureRig:
	var text := FileAccess.get_file_as_string(path)

	if text.is_empty():
		var refused := FigureRig.new()

		refused.error = "cannot read %s" % path
		return refused

	var rig := from_text(text)
	var stem := path.get_file().trim_suffix(FILE_SUFFIX)

	if rig.error.is_empty() and rig.key() != stem:
		rig.error = "the key %s is not the file name %s" % [rig.key(), stem]

	return rig


## The canonical text. The same rig gives the same bytes.
func to_text() -> String:
	return FigureJson.to_text(data)


## Write the canonical text to an OS path. Makes the directory.
func write_file(path: String) -> Error:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())

	var file := FileAccess.open(path, FileAccess.WRITE)

	if file == null:
		return FileAccess.get_open_error()

	file.store_string(to_text())

	return OK


# ─── The facts of a rig ─────────────────────────────────────────────────────

func key() -> String:
	return data.get("key", "")


## The bone rows, in the order of the file.
func bones() -> Array:
	return data.get("bones", [])


func bone_names() -> PackedStringArray:
	var names := PackedStringArray()

	for row: Dictionary in bones():
		names.append(row["name"])

	return names


func has_bone(bone_name: String) -> bool:
	return _index.has(bone_name)


## The row of one bone, or an empty dictionary.
func bone(bone_name: String) -> Dictionary:
	if not _index.has(bone_name):
		return {}

	return bones()[_index[bone_name]]


func sockets() -> Array:
	return data.get("sockets", [])


func is_socket(bone_name: String) -> bool:
	return bone_name in sockets()


## Region -> the bones of that region.
func regions() -> Dictionary:
	return data.get("regions", {})


## The region that holds a bone, or "" for a bone in no region. The regions
## answer in the order of their names.
func region_of(bone_name: String) -> String:
	var names := regions().keys()

	names.sort()

	for region: String in names:
		if bone_name in regions()[region]:
			return region

	return ""


## Slot -> the default bone of that slot.
func slots() -> Dictionary:
	return data.get("slots", {})


## The scale of each position track of a clip: the height of the hips in
## the rest pose. A rig with no hips, or with its hips at the floor, gives 1.
func motion_scale() -> float:
	if not has_bone(SCALE_BONE):
		return 1.0

	var height := absf(global_rest_of(SCALE_BONE).origin.y)

	return 1.0 if is_zero_approx(height) else height


## The rest of a bone on its parent.
func rest_of(bone_name: String) -> Transform3D:
	var row := bone(bone_name)

	if row.is_empty():
		return Transform3D.IDENTITY

	return Transform3D(Basis(FigureJson.quaternion(row["rotation"])),
		FigureJson.vector3(row["position"]))


## The rest of a bone in the space of the figure.
func global_rest_of(bone_name: String) -> Transform3D:
	var rest := Transform3D.IDENTITY
	var walk := bone_name

	# A parent loop in a bad file must not hang the editor.
	for _step in bones().size():
		if not has_bone(walk):
			break

		rest = rest_of(walk) * rest
		walk = bone(walk)["parent"]

	return rest


## The bones that have `bone_name` as their parent.
func children_of(bone_name: String) -> PackedStringArray:
	var found := PackedStringArray()

	for row: Dictionary in bones():
		if row["parent"] == bone_name:
			found.append(row["name"])

	return found


## One text for the names and the parents of the bones. Two rigs with the
## same text have the same skeleton, apart from the rest of each bone.
func structure() -> String:
	var parts := PackedStringArray()

	for row: Dictionary in bones():
		parts.append("%s<%s" % [row["name"], row["parent"]])

	return ",".join(parts)


# ─── The skeleton ───────────────────────────────────────────────────────────

## Give `skeleton` the bones and the rest pose of this rig. A skeleton with
## the same bones keeps them, and its bone attachments stay in place.
func apply_to(skeleton: Skeleton3D) -> void:
	if _structure_of(skeleton) != structure():
		_rebuild_bones(skeleton)

	for row: Dictionary in bones():
		var index := skeleton.find_bone(row["name"])
		var rest := rest_of(row["name"])

		if not skeleton.get_bone_rest(index).is_equal_approx(rest):
			skeleton.set_bone_rest(index, rest)
			skeleton.reset_bone_pose(index)

	skeleton.motion_scale = motion_scale()


func _rebuild_bones(skeleton: Skeleton3D) -> void:
	skeleton.clear_bones()

	for row: Dictionary in bones():
		skeleton.add_bone(row["name"])

	for row: Dictionary in bones():
		var parent := skeleton.find_bone(row["parent"])

		if parent >= 0:
			skeleton.set_bone_parent(skeleton.find_bone(row["name"]), parent)

	for index in skeleton.get_bone_count():
		skeleton.set_bone_rest(index, rest_of(skeleton.get_bone_name(index)))

	skeleton.reset_bone_poses()


static func _structure_of(skeleton: Skeleton3D) -> String:
	var parts := PackedStringArray()

	for index in skeleton.get_bone_count():
		var parent := skeleton.get_bone_parent(index)
		var parent_name := "" if parent < 0 else skeleton.get_bone_name(parent)

		parts.append("%s<%s" % [skeleton.get_bone_name(index), parent_name])

	return ",".join(parts)


# ─── The form of a rig file ─────────────────────────────────────────────────

## Why a parsed rig file has a bad form, or "".
static func _problem(parsed: Dictionary) -> String:
	var format: Variant = parsed.get("format")

	if typeof(format) != TYPE_INT or format < 1:
		return "a rig file needs a format number"

	if format > FORMAT:
		return "format %d is newer than this reader (format %d)" % [format, FORMAT]

	if typeof(parsed.get("key")) != TYPE_STRING or parsed["key"].is_empty():
		return "a rig file needs a key"

	if typeof(parsed.get("bones")) != TYPE_ARRAY or parsed["bones"].is_empty():
		return "a rig file needs bones"

	var problem := _bones_problem(parsed["bones"])

	if problem.is_empty():
		problem = _tables_problem(parsed)

	return problem


static func _bones_problem(rows: Array) -> String:
	var names := {}

	for row: Variant in rows:
		if typeof(row) != TYPE_DICTIONARY or typeof(row.get("name")) != TYPE_STRING \
				or row["name"].is_empty():
			return "each bone needs a name"

		if names.has(row["name"]):
			return "two bones have the name %s" % row["name"]

		names[row["name"]] = true

		if typeof(row.get("parent")) != TYPE_STRING:
			return "the bone %s needs a parent, or \"\"" % row["name"]

		if not FigureJson.is_numbers(row.get("position"), FigureJson.VECTOR_SIZE) \
				or not FigureJson.is_numbers(row.get("rotation"),
					FigureJson.QUATERNION_SIZE):
			return "the bone %s needs a position and a rotation" % row["name"]

	for row: Dictionary in rows:
		if not row["parent"].is_empty() and not names.has(row["parent"]):
			return "the bone %s has the unknown parent %s" % [row["name"], row["parent"]]

	return ""


## The form of the sockets, the regions, and the slots.
static func _tables_problem(parsed: Dictionary) -> String:
	if not FigureJson.is_strings(parsed.get("sockets", [])):
		return "sockets must be a list of bone names"

	var regions: Variant = parsed.get("regions", {})

	if typeof(regions) != TYPE_DICTIONARY:
		return "regions must map a region to its bones"

	for region: String in regions:
		if not FigureJson.is_strings(regions[region]):
			return "the region %s must be a list of bone names" % region

	var slots: Variant = parsed.get("slots", {})

	if typeof(slots) != TYPE_DICTIONARY:
		return "slots must map a slot to its bone"

	for slot: String in slots:
		if typeof(slots[slot]) != TYPE_STRING:
			return "the slot %s must name one bone" % slot

	return ""


## `parsed` with each key of a rig file. A file with no table gets an empty
## one, so the writer always gives the same set of keys.
static func _with_defaults(parsed: Dictionary) -> Dictionary:
	var full := parsed.duplicate(true)

	for pair: Array in [["sockets", []], ["regions", {}], ["slots", {}]]:
		if not full.has(pair[0]):
			full[pair[0]] = pair[1]

	full.erase(_OLD_MOTION_KEY)

	return full


func _build_index() -> void:
	_index.clear()

	for index in bones().size():
		_index[bones()[index]["name"]] = index
