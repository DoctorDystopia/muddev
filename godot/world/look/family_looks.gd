@tool
class_name FamilyLooks
extends RefCounted
## The family shapes as a look file: `families.json` under `res://world/look/`
## (ENG-0011, step L5). It holds the parts of each item family with no art
## of its own, and the model that stands in for a whole family.
##
## [FamilyShapes] asks this file first, and it keeps its old table as the
## fallback. A family with no row draws as before the file existed.
##
## ## The file
##
##     format    1
##     families  family -> {parts}
##     models    family -> asset key
##
## `parts` is the part list of a worn look ([FigureLook]): each part has a
## name, a bone, a place, and a shape list. The bone is [constant ROOT_BONE],
## because a family shape has no rig. The shape list has the part vocabulary
## of [FamilyShapes], with each vector as an `[x, y, z]` array. Thus, the
## part editor of the figure workbench edits a family as it edits a worn
## look, and [method builder_parts] gives [MeshBuilder] the same flat list
## that the table gives.
##
## The Families tab of the figure workbench writes the file. The game reads
## it at start. The Python guard checks that each family names a server
## fact, and that each model names a model that the build can produce.
##
## A file with a fault stays out of the store, and the game draws its table.
## [member error] says why.

const PATH := LookFile.DIRECTORY + "/families.json"

const FORMAT := 1

## The key of the file in the file store of the workbench. It is the name
## of the file also.
const KEY := "families"

const FILE_NAME := KEY + ".json"

const KEY_FAMILIES := "families"
const KEY_MODELS := "models"
const KEY_PARTS := "parts"

## The one bone of a family shape. The part editor needs a bone for each
## part, and the stand of a family has one.
const ROOT_BONE := "root"

## The name of the one part that the generator makes from a table row.
const TABLE_PART := "shape"

## A look key with this prefix names a family on the Families tab, not a
## worn look. A worn look key is an asset key, so it never holds "/".
const LOOK_PREFIX := "family/"

var data := {}

## Why the file does not read, or "" for a file that reads.
var error := ""


# ─── Reading and writing ────────────────────────────────────────────────────

## The families of a parsed file. Check [member error] after.
static func from_data(parsed: Variant) -> FamilyLooks:
	var looks := FamilyLooks.new()

	if typeof(parsed) != TYPE_DICTIONARY or parsed.is_empty():
		looks.error = "a family file must hold one JSON object"
		return looks

	var canonical: Dictionary = FigureJson.canonical(parsed)

	looks.error = _problem(canonical)

	if looks.error.is_empty():
		looks.data = _normal(canonical)

	return looks


static func from_text(text: String) -> FamilyLooks:
	return from_data(FigureJson.parse(text))


## Read one family file. Check [member error] after.
static func read_file(path: String) -> FamilyLooks:
	var text := FileAccess.get_file_as_string(path)

	if text.is_empty():
		var refused := FamilyLooks.new()

		refused.error = "cannot read %s" % path
		return refused

	return from_text(text)


func to_text() -> String:
	return FigureJson.to_text(data)


## Write the canonical text to a path. Makes the directory.
func write_file(path: String) -> Error:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path).get_base_dir())

	return LookFile.write(path, data)


# ─── The facts of the file ──────────────────────────────────────────────────

func key() -> String:
	return KEY


## Family -> `{parts}`.
func families() -> Dictionary:
	return data.get(KEY_FAMILIES, {})


## Family -> asset key.
func models() -> Dictionary:
	return data.get(KEY_MODELS, {})


## Each family with a row, in sorted order.
func family_names() -> PackedStringArray:
	var names := PackedStringArray(families().keys())

	names.sort()

	return names


func has_family(family: String) -> bool:
	return families().has(family)


## The row of one family as a worn look, or null for no row. The key of
## the look is the family.
func look_of(family: String) -> FigureLook:
	if not has_family(family):
		return null

	return FigureLook.from_data(look_data(data, family))


## The asset key that stands in for a family, or "".
func model_of(family: String) -> String:
	return str(models().get(family, ""))


# ─── The row of a family as a worn look ─────────────────────────────────────

## The content of a worn look for the row of one family in `content`: the
## content of a family file. A family with no row gives a look with no
## part. The plugin changes this look and gives it back to [method put_look].
static func look_data(content: Dictionary, family: String) -> Dictionary:
	var row: Variant = content.get(KEY_FAMILIES, {}).get(family, {})
	var look := {"format": FigureLook.FORMAT, "key": family}

	if typeof(row) == TYPE_DICTIONARY and row.has(KEY_PARTS):
		look[KEY_PARTS] = row[KEY_PARTS]

	return look


## Put the parts of a worn look into the row of one family of `content`.
static func put_look(content: Dictionary, family: String, look: Dictionary) -> void:
	if not content.has(KEY_FAMILIES):
		content[KEY_FAMILIES] = {}

	content["format"] = FORMAT
	content[KEY_FAMILIES][family] = {KEY_PARTS: look.get(KEY_PARTS, [])}


## Take the row of one family out of `content`.
static func remove_row(content: Dictionary, family: String) -> void:
	if content.has(KEY_FAMILIES):
		content[KEY_FAMILIES].erase(family)


## Give one family its model in `content`. An empty key takes the model
## out.
static func put_model(content: Dictionary, family: String, asset_key: String) -> void:
	if not content.has(KEY_MODELS):
		content[KEY_MODELS] = {}

	content["format"] = FORMAT

	if asset_key.is_empty():
		content[KEY_MODELS].erase(family)
	else:
		content[KEY_MODELS][family] = asset_key


## The row of a family for a flat part list of [FamilyShapes]: one part on
## the root bone, with each table row as one shape.
static func row_from_parts(parts: Array) -> Dictionary:
	var shapes := []

	for part: Dictionary in parts:
		shapes.append(file_shape(part))

	return {KEY_PARTS: [{"name": TABLE_PART, "bone": ROOT_BONE, "region": "",
		"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0],
		"shapes": shapes}]}


## One table row as a figure file holds it: each vector is an `[x, y, z]`
## array.
static func file_shape(part: Dictionary) -> Dictionary:
	var out := {}

	for field: String in part:
		if part[field] is Vector3:
			out[field] = FigureJson.from_vector3(part[field])
		else:
			out[field] = part[field]

	return out


## The flat part list of [MeshBuilder] for the row of one family: each
## shape of each part, with the place of the part in its offset, its
## rotation, and its scale.
static func builder_parts(row: Dictionary) -> Array:
	var parts := []

	for part: Variant in row.get(KEY_PARTS, []):
		if typeof(part) != TYPE_DICTIONARY:
			continue

		var place := FigureLook.part_transform(part)

		for shape: Variant in part.get("shapes", []):
			if typeof(shape) == TYPE_DICTIONARY:
				parts.append(builder_shape(shape, place))

	return parts


## One shape of a part as [MeshBuilder] reads it: each vector is a
## [Vector3], and the place of the part goes into the shape.
static func builder_shape(shape: Dictionary, place: Transform3D) -> Dictionary:
	var out := shape.duplicate()

	for vector_key: String in FigureLook.VECTOR_KEYS:
		if out.has(vector_key):
			out[vector_key] = FigureJson.vector3(out[vector_key])

	if place.is_equal_approx(Transform3D.IDENTITY):
		return out

	var own := Basis.from_euler(out.get("rotation", Vector3.ZERO)) \
		.scaled_local(out.get("scale", Vector3.ONE))
	var placed := place * Transform3D(own, out.get("offset", Vector3.ZERO))

	out["offset"] = placed.origin
	out["rotation"] = placed.basis.orthonormalized().get_euler()
	out["scale"] = placed.basis.get_scale()

	return out


## The rig of the stand of a family: one bone at the origin. The part editor
## reads its bones.
static func stand_rig() -> FigureRig:
	return FigureRig.from_data({"format": FigureRig.FORMAT, "key": LOOK_PREFIX.trim_suffix("/"),
		"bones": [{"name": ROOT_BONE, "parent": "", "position": [0.0, 0.0, 0.0],
			"rotation": [0.0, 0.0, 0.0, 1.0]}]})


## The family of a look key of the Families tab, or "" for a worn look key.
static func family_of_key(look_key: String) -> String:
	if not look_key.begins_with(LOOK_PREFIX):
		return ""

	return look_key.trim_prefix(LOOK_PREFIX)


# ─── The form of a family file ──────────────────────────────────────────────

static func _problem(parsed: Dictionary) -> String:
	var format: Variant = parsed.get("format")

	if typeof(format) != TYPE_INT or format < 1:
		return "a family file needs a format number"

	if format > FORMAT:
		return "format %d is newer than this reader (format %d)" % [format, FORMAT]

	if typeof(parsed.get(KEY_FAMILIES, {})) != TYPE_DICTIONARY \
			or typeof(parsed.get(KEY_MODELS, {})) != TYPE_DICTIONARY:
		return "families and models must each be a table"

	for family: String in parsed.get(KEY_FAMILIES, {}):
		var row: Variant = parsed[KEY_FAMILIES][family]

		if typeof(row) != TYPE_DICTIONARY:
			return "the family %s needs a table with its parts" % family

		var look := FigureLook.from_data(look_data(parsed, family))

		if not look.error.is_empty():
			return "the family %s: %s" % [family, look.error]

	for family: String in parsed.get(KEY_MODELS, {}):
		if typeof(parsed[KEY_MODELS][family]) != TYPE_STRING \
				or parsed[KEY_MODELS][family].is_empty():
			return "the model of the family %s must be an asset key" % family

	return ""


## `parsed` as the writer gives it: the two tables, and each part with its
## place and its region.
static func _normal(parsed: Dictionary) -> Dictionary:
	var out := parsed.duplicate(true)

	for table: String in [KEY_FAMILIES, KEY_MODELS]:
		if not out.has(table):
			out[table] = {}

	for family: String in out[KEY_FAMILIES]:
		var look := FigureLook.from_data(look_data(out, family))

		out[KEY_FAMILIES][family] = {KEY_PARTS: look.parts()}

	return out
