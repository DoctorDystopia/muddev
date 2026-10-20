class_name FigureLook
extends RefCounted
## One worn look: the file that says how one asset key dresses a figure
## (DESIGN-0014 section 8.1).
##
## A body is a worn look with a body type as its key. A kit part and a slot
## shape are worn looks also. One format and one reader serve each kind.
##
## ## The file
##
##     format   1
##     key      the asset key, the same as the file name
##     base     optional: the key of another worn look
##     kit      optional: the kit group of a kit part
##     hides    optional: the regions that this look hides
##     colors   optional: color role -> named color
##     parts    optional: [{name, bone, region, position, rotation, scale,
##              shapes, model, node}, ...]
##     fit      optional: body type -> [{part, position, rotation, scale}, ...]
##     served   optional: {bone, position, rotation, scale}
##
## The writer leaves out an optional key that is empty. A tier of an item is
## then a file of a few lines.
##
## ## A part
##
## A part is one rigid mesh on one bone. `name` is its name in this look.
## `position`, `rotation`, and `scale` place it on its bone. `rotation` is
## three angles in radians, in the order of [member Node3D.rotation].
## `region` is the region that a `hides` list of another look can hide, or
## "".
##
## `shapes` is a shape list: the part vocabulary of [FamilyShapes], with
## each vector as an `[x, y, z]` array. It has one more key, `rings`
## ([method MeshBuilder.build_part]).
##
## `model` and `node` name one node of one served model (Phase W4): the
## asset key of the model, and the name of the node. A look holds no path
## (requirement D3). A part with a model draws that node. Its shape list
## draws while the model is not in hand, as a primitive draws until its art
## arrives.
##
## ## The fit of a body type
##
## One look serves each body type (decision 10). A `fit` row gives one part
## another place on one body type. A key that the row does not have keeps
## the value of the part. [method place_of] gives the place that a figure
## uses.
##
## ## A tier (Phase W5)
##
## A look with a `base` is a tier: it takes the parts and the fit of that
## look (requirement D4). It can give a color role another color, and it
## can hide more regions. The copper helm is thus a file of a few lines.
## A tier has no `parts` and no `fit` of its own, and the reader refuses a
## file that has the two.
##
## [method resolved] gives the look that a figure draws for a tier. The
## base can be a tier also. A tier whose base is not there, or whose bases
## name each other, draws no part, and the figure still draws (requirement
## D7). [method base_problem] gives the reason.
##
## ## A kit part
##
## A look with a `kit` is a kit part: one choice of one kit group. One hair
## shape of the `hair` group is an example. A figure wears the kit part that
## its character has for each group ([FigureOutfit]). A kit part can take
## the place of a part of the body. It then hides the region of that part.
## The server names a kit part by its key only.
##
## ## The served place (10/17/2026)
##
## A served model of the asset key wins over the parts of the look
## ([FigureOutfit]). The figure draws it as one part with the name
## [constant SERVED_PART]. `served` holds the bone and the place of that
## part, after the author moved it. With no `served`, the model takes the
## box of the parts. A tier keeps its own `served`, because each asset key
## has its own model. No `fit` row applies to it.

## The newest format that this reader knows. It reads each older format.
const FORMAT := 1

const FILE_SUFFIX := ".json"

## The keys that the writer leaves out when they are empty.
const OPTIONAL_KEYS := ["base", "kit", "hides", "colors", "parts", "fit", "served"]

## The name of the part that draws the served model of the asset key. A
## part of a look file cannot have this name.
const SERVED_PART := "served"

## A name of a kit group: a-z, 0-9, and _, with a letter first.
const NAME_PATTERN := "^[a-z][a-z0-9_]*$"

## The shape keys that hold a vector.
const VECTOR_KEYS := ["size", "offset", "rotation", "scale"]

## The keys that place a part on its bone. A `fit` row can hold each one.
const PLACE_KEYS := ["position", "rotation", "scale"]

## The fewest sides and rings that keep the form of a plain shape. A shape
## of a figure gets these when it names none (DESIGN-0014 section 12.4): a
## crowd pays for each triangle of each part.
const DEFAULT_SEGMENTS := 8
const DEFAULT_RINGS := {
	FamilyShapes.SHAPE_SPHERE: 4,
	FamilyShapes.SHAPE_CYLINDER: 1,
	FamilyShapes.SHAPE_CONE: 1,
	FamilyShapes.SHAPE_TORUS: 6,
}

var data := {}

## Why the look does not read, or "" for a look that reads.
var error := ""


# ─── Reading and writing ────────────────────────────────────────────────────

## The look of a parsed look file. Check [member error] after.
static func from_data(parsed: Variant) -> FigureLook:
	var look := FigureLook.new()

	if typeof(parsed) != TYPE_DICTIONARY or parsed.is_empty():
		look.error = "a worn look file must hold one JSON object"
		return look

	var canonical: Dictionary = FigureJson.canonical(parsed)

	look.error = _problem(canonical)

	if look.error.is_empty():
		look.data = _normal(canonical)

	return look


## The look of a look file text. Check [member error] after.
static func from_text(text: String) -> FigureLook:
	return from_data(FigureJson.parse(text))


## Read one look file. The key must be the file name. Check [member error]
## after.
static func read_file(path: String) -> FigureLook:
	var text := FileAccess.get_file_as_string(path)

	if text.is_empty():
		var refused := FigureLook.new()

		refused.error = "cannot read %s" % path
		return refused

	var look := from_text(text)
	var stem := path.get_file().trim_suffix(FILE_SUFFIX)

	if look.error.is_empty() and look.key() != stem:
		look.error = "the key %s is not the file name %s" % [look.key(), stem]

	return look


## The canonical text. The same look gives the same bytes.
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


# ─── The facts of a look ────────────────────────────────────────────────────

func key() -> String:
	return data.get("key", "")


func base() -> String:
	return data.get("base", "")


## The kit group of a kit part, or "" for a look that is no kit part.
func kit() -> String:
	return data.get("kit", "")


## The regions that this look hides on each other look of a figure.
func hides() -> Array:
	return data.get("hides", [])


## Color role -> named color.
func colors() -> Dictionary:
	return data.get("colors", {})


func parts() -> Array:
	return data.get("parts", [])


func part_names() -> PackedStringArray:
	var names := PackedStringArray()

	for row: Dictionary in parts():
		names.append(row["name"])

	return names


## The row of one part, or an empty dictionary.
func part(part_name: String) -> Dictionary:
	for row: Dictionary in parts():
		if row["name"] == part_name:
			return row

	return {}


## Body type -> the fit rows of that body type.
func fit() -> Dictionary:
	return data.get("fit", {})


## The bone and the place of the served model: `{bone, position, rotation,
## scale}`. An empty dictionary when the author did not move it.
func served() -> Dictionary:
	return data.get("served", {})


## The fit row of one part on one body type, or an empty dictionary.
func fit_row(body_key: String, part_name: String) -> Dictionary:
	for row: Dictionary in fit().get(body_key, []):
		if row["part"] == part_name:
			return row

	return {}


## The row that places one part on one body type: the part, with each place
## key of its fit row. An empty dictionary for no such part.
func placed_row(part_name: String, body_key: String) -> Dictionary:
	var row := part(part_name)
	var fitted := fit_row(body_key, part_name)

	if row.is_empty() or fitted.is_empty():
		return row

	var placed := row.duplicate()

	for place_key: String in PLACE_KEYS:
		if fitted.has(place_key):
			placed[place_key] = fitted[place_key]

	return placed


## The place of one part on its bone, on the figure of one body type.
func place_of(part_name: String, body_key: String) -> Transform3D:
	return part_transform(placed_row(part_name, body_key))


## The key of each model that a part of this look names, in sorted order.
func model_keys() -> PackedStringArray:
	var keys := PackedStringArray()

	for row: Dictionary in parts():
		var model_key: String = row.get("model", "")

		if not model_key.is_empty() and not model_key in keys:
			keys.append(model_key)

	keys.sort()

	return keys


# ─── A tier ─────────────────────────────────────────────────────────────────

## The looks from this look to the last base that `looks` has: this look
## first. `looks` is key -> [FigureLook]. The walk stops before a base that
## is not there, and before a look that the list has already.
func base_chain(looks: Dictionary) -> Array:
	var chain := [self]
	var seen := {key(): true}
	var walk := self

	while not walk.base().is_empty():
		var next: FigureLook = looks.get(walk.base())

		if next == null or seen.has(next.key()):
			break

		seen[next.key()] = true
		chain.append(next)
		walk = next

	return chain


## Why this look cannot take the parts of its base, or "". A look with no
## base has no problem.
func base_problem(looks: Dictionary) -> String:
	var last: FigureLook = base_chain(looks)[-1]

	if last.base().is_empty():
		return ""

	if not looks.has(last.base()):
		return "the base %s of %s is not there" % [last.base(), last.key()]

	return "the bases of %s name each other" % key()


## The look that a figure draws for this look. A look with no base is that
## look itself. A tier gets the parts and the fit of its last base, each
## color of each base with its own colors over them, and each hidden region
## of each base with its own. `looks` is key -> [FigureLook].
##
## The answer shares its parts with the base, so a caller must not change
## it.
func resolved(looks: Dictionary) -> FigureLook:
	if base().is_empty():
		return self

	var chain := base_chain(looks)
	var root: FigureLook = chain[-1]
	var out := {"format": FORMAT, "key": key()}
	var colors := {}
	var hidden := {}

	if root.base().is_empty():
		for kept: String in ["parts", "fit"]:
			if root.data.has(kept):
				out[kept] = root.data[kept]

	for index in range(chain.size() - 1, -1, -1):
		colors.merge(chain[index].colors(), true)

		for region: String in chain[index].hides():
			hidden[region] = true

	if not colors.is_empty():
		out["colors"] = colors

	if not hidden.is_empty():
		out["hides"] = hidden.keys()
		out["hides"].sort()

	if data.has("served"):
		out["served"] = data["served"]

	var look := FigureLook.new()

	look.data = out

	return look


# ─── A part and its shapes ──────────────────────────────────────────────────

## The place of a part on its bone.
static func part_transform(row: Dictionary) -> Transform3D:
	var turn := FigureJson.vector3(row.get("rotation"))
	var size := FigureJson.vector3(row.get("scale"), Vector3.ONE)
	var basis := Basis.from_euler(turn).scaled_local(size)

	return Transform3D(basis, FigureJson.vector3(row.get("position")))


## Write the place of a part on its bone into its row.
static func set_part_transform(row: Dictionary, xform: Transform3D) -> void:
	row["position"] = FigureJson.from_vector3(xform.origin)
	# The angles come from the basis with no scale in it.
	row["rotation"] = FigureJson.from_vector3(xform.basis.orthonormalized().get_euler())
	row["scale"] = FigureJson.from_vector3(xform.basis.get_scale())


## The place of one shape of a shape list in the space of its part: its
## offset, its rotation, and its scale. [MeshBuilder] puts the three on the
## node of the shape, so the node of a shape has this transform.
static func shape_transform(shape: Dictionary) -> Transform3D:
	var turn := FigureJson.vector3(shape.get("rotation"))
	var size := FigureJson.vector3(shape.get("scale"), Vector3.ONE)
	var basis := Basis.from_euler(turn).scaled_local(size)

	return Transform3D(basis, FigureJson.vector3(shape.get("offset")))


## Write the place of one shape into its row. A place that is the default
## of its key leaves the row with no key, as a new shape has none. Thus, a
## shape that goes back to its place leaves the file as it was.
static func set_shape_transform(shape: Dictionary, xform: Transform3D) -> void:
	var places := {
		"offset": [FigureJson.from_vector3(xform.origin), FigureJson.from_vector3(Vector3.ZERO)],
		"rotation": [FigureJson.from_vector3(xform.basis.orthonormalized().get_euler()),
			FigureJson.from_vector3(Vector3.ZERO)],
		"scale": [FigureJson.from_vector3(xform.basis.get_scale()),
			FigureJson.from_vector3(Vector3.ONE)],
	}

	for place_key: String in places:
		if places[place_key][0] == places[place_key][1]:
			shape.erase(place_key)
		else:
			shape[place_key] = places[place_key][0]


## One shape of a shape list as [MeshBuilder] reads it: each vector is a
## [Vector3], the color role is the named color of the look, and a shape
## with no count of sides or rings gets a low one. `colors` is the color
## table of the look. [FigurePalette] gives the named color its color.
static func builder_shape(shape: Dictionary, colors: Dictionary) -> Dictionary:
	var out := shape.duplicate()
	var role: String = shape.get("color", MeshPalette.GENERIC)

	for vector_key: String in VECTOR_KEYS:
		if out.has(vector_key):
			out[vector_key] = FigureJson.vector3(out[vector_key])

	out["color"] = colors.get(role, role)

	if not out.has("segments"):
		out["segments"] = DEFAULT_SEGMENTS

	if not out.has("rings") and DEFAULT_RINGS.has(shape.get("shape")):
		out["rings"] = DEFAULT_RINGS[shape["shape"]]

	return out


# ─── The form of a look file ────────────────────────────────────────────────

## Why a parsed look file has a bad form, or "".
static func _problem(parsed: Dictionary) -> String:
	var format: Variant = parsed.get("format")

	if typeof(format) != TYPE_INT or format < 1:
		return "a worn look file needs a format number"

	if format > FORMAT:
		return "format %d is newer than this reader (format %d)" % [format, FORMAT]

	if typeof(parsed.get("key")) != TYPE_STRING or parsed["key"].is_empty():
		return "a worn look file needs a key"

	if typeof(parsed.get("base", "")) != TYPE_STRING:
		return "base must be the key of a worn look"

	if parsed.get("base", "") == parsed["key"]:
		return "a worn look cannot be its own base"

	if not FigureJson.is_strings(parsed.get("hides", [])):
		return "hides must be a list of regions"

	if typeof(parsed.get("colors", {})) != TYPE_DICTIONARY \
			or typeof(parsed.get("fit", {})) != TYPE_DICTIONARY:
		return "colors and fit must each be a table"

	var named := _names_problem(parsed)

	if not named.is_empty():
		return named

	if typeof(parsed.get("parts", [])) != TYPE_ARRAY:
		return "parts must be a list"

	var bare: bool = parsed.get("parts", []).is_empty() and parsed.get("fit", {}).is_empty()

	if not parsed.get("base", "").is_empty() and not bare:
		return "the look %s has a base, so it has no part and no fit of its own" % parsed["key"]

	var problem := _parts_problem(parsed.get("parts", []))

	if problem.is_empty():
		problem = _fit_problem(parsed.get("fit", {}))

	if problem.is_empty():
		problem = _served_problem(parsed.get("served", {}))

	return problem


## Why the `served` row of a parsed look file has a bad form, or "".
static func _served_problem(row: Variant) -> String:
	if typeof(row) != TYPE_DICTIONARY:
		return "served must be a table"

	if row.is_empty():
		return ""

	if typeof(row.get("bone")) != TYPE_STRING or row["bone"].is_empty():
		return "the served model needs a bone"

	return _place_problem(row, "the served model")


## Why the kit group or the color table of a parsed look file has a bad
## form, or "". A color that is no text would stop the builder, and a fault
## of a file must not stop a figure (requirement D7).
static func _names_problem(parsed: Dictionary) -> String:
	var plain := RegEx.create_from_string(NAME_PATTERN)
	var group: Variant = parsed.get("kit", "")

	if typeof(group) != TYPE_STRING \
			or (not group.is_empty() and plain.search(group) == null):
		return "kit must be the name of a kit group: a-z, 0-9, and _"

	var colors: Dictionary = parsed.get("colors", {})

	for role: Variant in colors:
		if typeof(colors[role]) != TYPE_STRING or colors[role].is_empty():
			return "the color role %s needs a named color" % role

	return ""


## Why the `fit` table of a parsed look file has a bad form, or "".
static func _fit_problem(fit_table: Dictionary) -> String:
	for body_key: String in fit_table:
		if typeof(fit_table[body_key]) != TYPE_ARRAY:
			return "the fit of %s must be a list" % body_key

		for row: Variant in fit_table[body_key]:
			if typeof(row) != TYPE_DICTIONARY or typeof(row.get("part")) != TYPE_STRING \
					or row["part"].is_empty():
				return "each fit row of %s needs a part" % body_key

			var problem := _place_problem(row, "the fit of the part %s" % row["part"])

			if not problem.is_empty():
				return problem

	return ""


## Why a place key of a row has a bad form, or "". The row is a part row or
## a fit row, and `what` names it for the message.
static func _place_problem(row: Dictionary, what: String) -> String:
	for place_key: String in PLACE_KEYS:
		if row.has(place_key) \
				and not FigureJson.is_numbers(row[place_key], FigureJson.VECTOR_SIZE):
			return "the %s of %s must be [x, y, z]" % [place_key, what]

	return ""


static func _parts_problem(rows: Array) -> String:
	var names := {}

	for row: Variant in rows:
		if typeof(row) != TYPE_DICTIONARY or typeof(row.get("name")) != TYPE_STRING \
				or row["name"].is_empty():
			return "each part needs a name"

		if names.has(row["name"]):
			return "two parts have the name %s" % row["name"]

		if row["name"] == SERVED_PART:
			return "the part name %s belongs to the served model" % SERVED_PART

		names[row["name"]] = true

		if typeof(row.get("bone")) != TYPE_STRING \
				or typeof(row.get("region", "")) != TYPE_STRING:
			return "the part %s needs a bone" % row["name"]

		var problem := _place_problem(row, "the part %s" % row["name"])

		if problem.is_empty():
			problem = _shapes_problem(row)

		if not problem.is_empty():
			return problem

	return ""


static func _shapes_problem(row: Dictionary) -> String:
	if typeof(row.get("model", "")) != TYPE_STRING \
			or typeof(row.get("node", "")) != TYPE_STRING:
		return "the model and the node of the part %s must each be a name" % row["name"]

	if typeof(row.get("shapes", [])) != TYPE_ARRAY:
		return "the shapes of the part %s must be a list" % row["name"]

	for shape: Variant in row.get("shapes", []):
		if typeof(shape) != TYPE_DICTIONARY or typeof(shape.get("shape")) != TYPE_STRING:
			return "each shape of the part %s needs a shape name" % row["name"]

		for vector_key: String in VECTOR_KEYS:
			if shape.has(vector_key) \
					and not FigureJson.is_numbers(shape[vector_key], FigureJson.VECTOR_SIZE):
				return "the %s of a shape of the part %s must be [x, y, z]" \
					% [vector_key, row["name"]]

		for name_key: String in ["color", "finish"]:
			if typeof(shape.get(name_key, "")) != TYPE_STRING:
				return "the %s of a shape of the part %s must be a name" \
					% [name_key, row["name"]]

	return ""


## `parsed` as the writer gives it: no empty optional key, and each part
## with its place and its region. A look with a `base` then has no `parts`
## key. A body type with no fit row has no key in `fit`.
static func _normal(parsed: Dictionary) -> Dictionary:
	var out := parsed.duplicate(true)

	for body_key: String in out.get("fit", {}).keys():
		if out["fit"][body_key].is_empty():
			out["fit"].erase(body_key)

	for optional_key: String in OPTIONAL_KEYS:
		if out.has(optional_key) and out[optional_key].is_empty():
			out.erase(optional_key)

	for row: Dictionary in out.get("parts", []):
		for pair: Array in [["region", ""], ["position", [0.0, 0.0, 0.0]],
				["rotation", [0.0, 0.0, 0.0]], ["scale", [1.0, 1.0, 1.0]]]:
			if not row.has(pair[0]):
				row[pair[0]] = pair[1].duplicate() if pair[1] is Array else pair[1]

		for name_key: String in ["model", "node"]:
			if row.get(name_key, "x").is_empty():
				row.erase(name_key)

	if out.has("served"):
		var served: Dictionary = out["served"]

		for pair: Array in [["position", [0.0, 0.0, 0.0]], ["rotation", [0.0, 0.0, 0.0]],
				["scale", [1.0, 1.0, 1.0]]]:
			if not served.has(pair[0]):
				served[pair[0]] = pair[1].duplicate()

	return out
