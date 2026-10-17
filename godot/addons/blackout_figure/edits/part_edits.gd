@tool
class_name FigurePartEdits
extends RefCounted
## The rules of a part of a worn look (DESIGN-0014): add, remove, rename,
## place, fit, bone, region, a copy, the other side, and the parts from a
## served model.
##
## Each routine changes the content of one look file. The content is the
## dictionary of the `data` member of [FigureLook]. The caller gives a
## copy, and the routine changes the copy. A routine that can refuse
## returns the reason, or "". Nothing here needs the editor.
##
## ## A part with a model (Phase W4)
##
## [method parts_from_model] makes one part for each node of a served model
## that holds a mesh. The space of the model file is the space of the
## figure. Thus, the place of a part on its bone is the place of its node
## in the file, seen from the rest pose of that bone. The part then sits
## where its author made it (DESIGN-0014 section 8.3).
##
## A part gets the bone that has the name of its node. If no bone has that
## name, it gets the bone that is nearest to the middle of the node
## ([method nearest_bone]). The author changes the bone in the part editor.
##
## ## The fit
##
## [method set_part_fit] gives one part its own place on one body type, and
## [method set_part_place] then writes that place. [method fit_to_rig]
## makes the fit of each part from the bone lengths of two rigs.
##
## ## The tools of Phase W6
##
## [method mirror_part] makes the part of the other side of a figure, and
## [method duplicate_part] makes a copy. With them, the author shapes one
## arm and gets the other.

## A bone ratio nearer to 1 than this is no change of length. A fit row for
## it only adds lines to the file.
const FIT_TOLERANCE := 0.001

## A bone points along one axis when that axis holds this part of its
## length. The fit from the bone lengths scales a part on that axis
## ([method fit_to_rig]).
const AXIS_ALIGNED := 0.999

const AXES := 3

## The start of a part name for a node whose name starts with no letter.
const NODE_PART_PREFIX := "part_"

## The end of the name of a copy of a part, and of the other side of a part
## with no side in its name.
const COPY_SUFFIX := "_copy"
const MIRROR_SUFFIX := "_mirror"

## The reason of a refusal that needs a selected part. The part editor
## shows it as the tooltip of each button that needs one.
const NO_PART := "Select a part first."

## The reason of a refusal when a model has no node to give.
const NO_MESH_NODE := "The model %s has no node with a mesh, or it is not in the served tree."


# ─── The Body tab: parts ────────────────────────────────────────────────────

## Add a part to a look, on `bone` of `rig`, with one prism as its shape
## list. Returns the name of the new part.
static func add_part(look: Dictionary, rig: FigureRig, bone: String) -> String:
	if not look.has("parts"):
		look["parts"] = []

	var part_name := unique_name(bone.to_snake_case(), _part_names(look))

	look["parts"].append({
		"name": part_name,
		"bone": bone,
		"region": rig.region_of(bone),
		"position": [0.0, 0.0, 0.0],
		"rotation": [0.0, 0.0, 0.0],
		"scale": [1.0, 1.0, 1.0],
		"shapes": [FigureShapeEdits.new_shape(FamilyShapes.SHAPE_PRISM)],
	})

	return part_name


## Remove a part from a look, with each fit row of that part.
static func remove_part(look: Dictionary, part_name: String) -> String:
	var index := part_index(look, part_name)

	if index < 0:
		return "The look has no part %s." % part_name

	look["parts"].remove_at(index)

	for body_key: String in look.get("fit", {}).keys():
		_drop_fit_row(look, body_key, part_name)

	return ""


## Give a part another name. Each fit row of the part follows.
static func rename_part(look: Dictionary, part_name: String, new_name: String) -> String:
	var problem := FigureRigEdits.name_problem(new_name)

	if not problem.is_empty():
		return problem

	if new_name in _part_names(look):
		return "The look has a part with the name %s." % new_name

	var index := part_index(look, part_name)

	if index < 0:
		return "The look has no part %s." % part_name

	look["parts"][index]["name"] = new_name

	for body_key: String in look.get("fit", {}):
		for row: Dictionary in look["fit"][body_key]:
			if row["part"] == part_name:
				row["part"] = new_name

	return ""


## Give a part its region, or "" for no region.
static func set_part_region(look: Dictionary, part_name: String, region: String) -> String:
	var index := part_index(look, part_name)

	if index < 0:
		return "The look has no part %s." % part_name

	look["parts"][index]["region"] = region

	return ""


## Give a part its place on its bone. With a `body_key` whose fit has a row
## for the part, the place goes into that row, and each other body type
## keeps its place.
static func set_part_place(look: Dictionary, part_name: String,
		xform: Transform3D, body_key := "") -> String:
	var index := part_index(look, part_name)

	if index < 0:
		return "The look has no part %s." % part_name

	var fitted := _fit_row(look, body_key, part_name)

	FigureLook.set_part_transform(look["parts"][index] if fitted.is_empty() else fitted,
		xform)

	return ""


## Give one part its own place on one body type, or take that place away.
## A new fit row starts at the place of the part, so the part does not move.
static func set_part_fit(look: Dictionary, body_key: String, part_name: String,
		fitted: bool) -> String:
	var index := part_index(look, part_name)

	if index < 0:
		return "The look has no part %s." % part_name

	if body_key.is_empty():
		return "Select a body type first."

	if not fitted:
		_drop_fit_row(look, body_key, part_name)
		return ""

	if not _fit_row(look, body_key, part_name).is_empty():
		return ""

	var row := {"part": part_name}

	FigureLook.set_part_transform(row, FigureLook.part_transform(look["parts"][index]))
	_fit_rows(look, body_key).append(row)

	return ""


## Give each part of a look its fit on the body type of `rig`, from the
## bone lengths. `made_on` is the rig that the look has its places for.
##
## A part on a bone that is longer or shorter on `rig` gets a fit row. The
## row scales the part along the bone, from the start of the bone. Returns
## the count of the rows.
##
## The fit has two limits. A bone that points along no axis of its own
## space gets no row. A part with a turn on its bone gets only the nearest
## place that a fit row can hold.
static func fit_to_rig(look: Dictionary, made_on: FigureRig, rig: FigureRig) -> int:
	var count := 0

	for part: Dictionary in look.get("parts", []):
		var stretch := _bone_stretch(made_on, rig, part["bone"])

		_drop_fit_row(look, rig.key(), part["name"])

		if stretch.is_equal_approx(Vector3.ONE):
			continue

		var place := FigureLook.part_transform(part)
		var row := {"part": part["name"]}

		FigureLook.set_part_transform(row, Transform3D(Basis.from_scale(stretch)) * place)
		_fit_rows(look, rig.key()).append(row)
		count += 1

	return count


## How much longer a bone is on `rig` than on `made_on`, as a scale on each
## axis of the bone. The length of a bone is the distance to its first
## child that is no socket.
static func _bone_stretch(made_on: FigureRig, rig: FigureRig, bone: String) -> Vector3:
	var stretch := Vector3.ONE

	for child: String in made_on.children_of(bone):
		if made_on.is_socket(child) or not rig.has_bone(child):
			continue

		var before: Vector3 = FigureJson.vector3(made_on.bone(child)["position"])
		var after: Vector3 = FigureJson.vector3(rig.bone(child)["position"])

		if before.is_zero_approx():
			return stretch

		var ratio := after.length() / before.length()
		var direction := before.normalized().abs()

		if absf(ratio - 1.0) < FIT_TOLERANCE:
			return stretch

		for axis in AXES:
			if direction[axis] >= AXIS_ALIGNED:
				stretch[axis] = ratio

		return stretch

	return stretch


## The fit rows of one body type. A look with none gets an empty list.
static func _fit_rows(look: Dictionary, body_key: String) -> Array:
	if not look.has("fit"):
		look["fit"] = {}

	if not look["fit"].has(body_key):
		look["fit"][body_key] = []

	return look["fit"][body_key]


## The fit row of one part on one body type, or an empty dictionary.
static func _fit_row(look: Dictionary, body_key: String, part_name: String) -> Dictionary:
	for row: Dictionary in look.get("fit", {}).get(body_key, []):
		if row["part"] == part_name:
			return row

	return {}


## Take the fit row of one part on one body type out of a look. A body type
## with no row left has no key in the fit.
static func _drop_fit_row(look: Dictionary, body_key: String, part_name: String) -> void:
	var rows: Array = look.get("fit", {}).get(body_key, [])

	for index in range(rows.size() - 1, -1, -1):
		if rows[index]["part"] == part_name:
			rows.remove_at(index)

	if rows.is_empty() and look.has("fit"):
		look["fit"].erase(body_key)

		if look["fit"].is_empty():
			look.erase("fit")


## Move a part to another bone. The part stays where it is on a figure in
## the rest pose, so the author does not place it again.
##
## `rigs` is body type -> [FigureRig]. A fit row of the part stays where it
## is on its own body type also. A fit row of a body type that `rigs` does
## not have leaves the look, because its place is on the old bone.
static func set_part_bone(look: Dictionary, part_name: String, bone: String,
		rig: FigureRig, rigs := {}) -> String:
	var index := part_index(look, part_name)

	if index < 0:
		return "The look has no part %s." % part_name

	if not rig.has_bone(bone):
		return "The rig has no bone %s." % bone

	var row: Dictionary = look["parts"][index]
	var old_bone: String = row["bone"]

	for body_key: String in look.get("fit", {}).keys():
		var fitted := _fit_row(look, body_key, part_name)
		var own: FigureRig = rigs.get(body_key)

		if fitted.is_empty():
			continue

		if own == null or not own.has_bone(bone):
			_drop_fit_row(look, body_key, part_name)
			continue

		var placed := row.duplicate()

		placed.merge(fitted, true)
		FigureLook.set_part_transform(fitted, _on_bone(own, old_bone, bone,
			FigureLook.part_transform(placed)))

	row["bone"] = bone
	FigureLook.set_part_transform(row, _on_bone(rig, old_bone, bone,
		FigureLook.part_transform(row)))

	return ""


## The place on `bone` of a part that has `place` on `old_bone`, so the
## part stays where it is on a figure in the rest pose.
static func _on_bone(rig: FigureRig, old_bone: String, bone: String,
		place: Transform3D) -> Transform3D:
	return rig.global_rest_of(bone).affine_inverse() * rig.global_rest_of(old_bone) * place


## Add a copy of a part to a look, on the same bone and at the same place.
## The author then moves the copy. Returns the name of the copy, or "" for
## no such part.
static func duplicate_part(look: Dictionary, part_name: String) -> String:
	var index := part_index(look, part_name)

	if index < 0:
		return ""

	var copy: Dictionary = look["parts"][index].duplicate(true)

	copy["name"] = unique_name(part_name + COPY_SUFFIX, _part_names(look))
	look["parts"].insert(index + 1, copy)

	return copy["name"]


## Why a part cannot get a part of the other side, or "".
static func mirror_problem(look: Dictionary, part_name: String, rig: FigureRig) -> String:
	var index := part_index(look, part_name)

	if index < 0:
		return "The look has no part %s." % part_name

	if rig == null or not rig.has_bone(look["parts"][index]["bone"]):
		return "The rig has no bone %s." % look["parts"][index]["bone"]

	if look["parts"][index].has("model"):
		return "The part %s draws a model. Make the other side in the modeler." % part_name

	return ""


## Make the part of the other side of a figure: a copy of one part, as a
## mirror shows it. The copy is on the bone of the other side
## ([method FigureRigEdits.mirror_name]). A bone with no other side keeps
## the copy.
##
## The copy has the name of the other side, and it takes the place of a
## part with that name. A part with no side in its name gets a new name.
## Each fit row of the part gets a row for the copy. Returns the name of
## the copy, or "" when [method mirror_problem] gives a reason.
##
## The fit of a copy is correct for a rig whose two sides are the same.
static func mirror_part(look: Dictionary, part_name: String, rig: FigureRig) -> String:
	if not mirror_problem(look, part_name, rig).is_empty():
		return ""

	var row: Dictionary = look["parts"][part_index(look, part_name)]
	var bone := FigureRigEdits.mirror_name(row["bone"])
	var copy: Dictionary = row.duplicate(true)

	if not rig.has_bone(bone):
		bone = row["bone"]

	copy["name"] = FigureRigEdits.mirror_name(part_name)

	if copy["name"] == part_name:
		copy["name"] = unique_name(part_name + MIRROR_SUFFIX, _part_names(look))

	copy["bone"] = bone
	FigureLook.set_part_transform(copy, _mirrored(rig, row["bone"], bone,
		FigureLook.part_transform(row)))
	copy["shapes"] = _mirrored_shapes(row.get("shapes", []))
	_mirror_fit(look, part_name, copy, rig)

	var old := part_index(look, copy["name"])

	if old >= 0:
		look["parts"][old] = copy
	else:
		look["parts"].append(copy)

	return copy["name"]


## The place on `bone` of the mirror picture of a part that has `place` on
## `old_bone`. The mirror is the plane through the middle of the figure.
## Two turns of the X axis make no turn of a face, so the answer is a place
## that a part can have.
static func _mirrored(rig: FigureRig, old_bone: String, bone: String,
		place: Transform3D) -> Transform3D:
	var flip := Transform3D(Basis.FLIP_X, Vector3.ZERO)
	var in_figure := flip * rig.global_rest_of(old_bone) * place * flip

	return rig.global_rest_of(bone).affine_inverse() * in_figure


## A shape list as a mirror shows it. Each shape of the vocabulary has two
## equal sides, apart from a prism with a lean.
static func _mirrored_shapes(shapes: Array) -> Array:
	var made := []

	for shape: Dictionary in shapes:
		var copy := shape.duplicate(true)
		var turn := Basis.from_euler(FigureJson.vector3(shape.get("rotation")))

		if shape.has("offset"):
			copy["offset"] = FigureJson.from_vector3(
				FigureJson.vector3(shape["offset"]) * Vector3(-1.0, 1.0, 1.0))

		if shape.has("rotation"):
			copy["rotation"] = FigureJson.from_vector3(
				(Basis.FLIP_X * turn * Basis.FLIP_X).get_euler())

		if shape.has("lean_x"):
			copy["lean_x"] = -float(shape["lean_x"])

		made.append(copy)

	return made


## Give the copy of [method mirror_part] one fit row for each fit row of
## its part. An old fit row of the copy goes.
static func _mirror_fit(look: Dictionary, part_name: String, copy: Dictionary,
		rig: FigureRig) -> void:
	var source_bone: String = look["parts"][part_index(look, part_name)]["bone"]

	for body_key: String in look.get("fit", {}).keys():
		var fitted := _fit_row(look, body_key, part_name).duplicate(true)

		_drop_fit_row(look, body_key, copy["name"])

		if fitted.is_empty():
			continue

		var placed: Dictionary = look["parts"][part_index(look, part_name)].duplicate()
		var row := {"part": copy["name"]}

		placed.merge(fitted, true)
		FigureLook.set_part_transform(row, _mirrored(rig, source_bone, copy["bone"],
			FigureLook.part_transform(placed)))
		_fit_rows(look, body_key).append(row)


# ─── The parts from a model ─────────────────────────────────────────────────

## Make the parts of a look from the nodes of one served model: one part
## for each node that holds a mesh. Each other part of the look goes.
##
## A part has the name of its node, as a part name. A part that the look
## has for a node keeps its bone, its region, and its shape list. The shape
## list draws while the model is not in hand. Each new part gets its bone
## from [method bone_for_node], and the region of that bone.
##
## The place of each part comes from the file again, so a new export moves
## the part. A fit row of a part that goes leaves the look.
static func parts_from_model(look: Dictionary, rig: FigureRig, model_key: String,
		models: FigureModels) -> String:
	var nodes := models.node_names(model_key)
	var parts := []
	var taken := PackedStringArray()

	if nodes.is_empty():
		return NO_MESH_NODE % model_key

	for node_name: String in nodes:
		var part_name := unique_name(_part_name_of(node_name), taken)
		var old := _part_for_node(look, model_key, node_name, part_name)
		var bone: String = old.get("bone", "")

		if not rig.has_bone(bone):
			bone = bone_for_node(rig, node_name, models.node_bounds(model_key, node_name))

		var row := {"name": part_name, "bone": bone,
			"region": old.get("region", rig.region_of(bone)),
			"model": model_key, "node": node_name}

		if old.has("shapes"):
			row["shapes"] = old["shapes"]

		FigureLook.set_part_transform(row, rig.global_rest_of(bone).affine_inverse()
			* models.node_place(model_key, node_name))
		taken.append(part_name)
		parts.append(row)

	look["parts"] = parts
	# A tier gets parts of its own, so it is no tier after this.
	look.erase("base")

	for body_key: String in look.get("fit", {}).keys():
		for fitted: Dictionary in look["fit"][body_key].duplicate():
			if not fitted["part"] in taken:
				_drop_fit_row(look, body_key, fitted["part"])

	return ""


## Give ONE part of a look the node of a served model (DESIGN-0014 section
## 20). Each other part of the look stays as it is. This is how a part of a
## body takes a model from a modeler: the head from Blender, and each other
## body part from its shape list.
##
## The part keeps its name, its bone, its region, and its shape list. The
## shape list draws again when the model is not in hand. Its place comes
## from the place of the node in the file, seen from the rest of its bone
## on `rig`, so the part sits where the author made it. The place goes
## where a gizmo move goes ([method set_part_place]): into the fit row of
## the part on that body type when it has one, else into the part. Returns
## "" or the reason for a refusal.
static func part_from_model(look: Dictionary, rig: FigureRig, part_name: String,
		model_key: String, models: FigureModels) -> String:
	var index := part_index(look, part_name)

	if index < 0:
		return NO_PART

	var row: Dictionary = look["parts"][index]
	var node_name := node_for_part(models, model_key, row)

	if node_name.is_empty():
		return _no_node_reason(models, model_key, row)

	row["model"] = model_key
	row["node"] = node_name

	return set_part_place(look, part_name, rig.global_rest_of(row["bone"]).affine_inverse()
		* models.node_place(model_key, node_name), rig.key())


## Take the model away from one part. The part draws its shape list again,
## at the place that it has.
static func clear_part_model(look: Dictionary, part_name: String) -> String:
	var index := part_index(look, part_name)

	if index < 0:
		return NO_PART

	var row: Dictionary = look["parts"][index]

	if not row.has("model"):
		return "The part %s has no model." % part_name

	row.erase("model")
	row.erase("node")

	return ""


## The node of a model that one part takes, or "". The node with the name
## of the part comes first, then the node with the name of its bone. A
## model with one node gives that node to any part.
##
## A node of a reference body has the name `<look>__<part>`
## ([FigureReference]). Only the text after the last `__` counts, so an
## author can change one node of the reference body and keep its name.
static func node_for_part(models: FigureModels, model_key: String, row: Dictionary) -> String:
	var nodes := models.node_names(model_key)

	for wanted: String in [str(row.get("name", "")), str(row.get("bone", ""))]:
		for node_name: String in nodes:
			var own := node_name.get_slice(FigureBuilder.NAME_JOIN,
				node_name.get_slice_count(FigureBuilder.NAME_JOIN) - 1)

			if own.to_snake_case() == wanted.to_snake_case():
				return node_name

	return nodes[0] if nodes.size() == 1 else ""


static func _no_node_reason(models: FigureModels, model_key: String, row: Dictionary) -> String:
	var nodes := models.node_names(model_key)

	if nodes.is_empty():
		return NO_MESH_NODE % model_key

	return "The model %s has %d nodes (%s). Name one node %s or %s." % [model_key,
		nodes.size(), ", ".join(nodes), row.get("name", ""), row.get("bone", "")]


## The bone of a new part for one node of a model. A node with the name of
## a bone gets that bone: `LeftUpperArm` or `left_upper_arm`. Each other
## node gets the bone that is nearest to the middle of its box.
static func bone_for_node(rig: FigureRig, node_name: String, bounds: AABB) -> String:
	for bone: String in rig.bone_names():
		if bone == node_name or bone.to_snake_case() == node_name.to_snake_case():
			return bone

	return nearest_bone(rig, bounds.get_center())


## The bone of a rig that is nearest to a point of the figure, in the rest
## pose. A bone is the line from its start to each child bone. A bone with
## no child is the point of its start. Two bones at one distance give the
## first one of the rig.
static func nearest_bone(rig: FigureRig, point: Vector3) -> String:
	var nearest := ""
	var nearest_distance := INF

	for bone: String in rig.bone_names():
		var start := rig.global_rest_of(bone).origin
		var distance := point.distance_to(start)

		for child: String in rig.children_of(bone):
			var end := rig.global_rest_of(child).origin
			var on_line := Geometry3D.get_closest_point_to_segment(point, start, end)

			distance = minf(distance, point.distance_to(on_line))

		if distance < nearest_distance:
			nearest_distance = distance
			nearest = bone

	return nearest


## The part that a look has for one node of a model, or an empty
## dictionary. It is the part with that model and that node. With none, it
## is the part with the name `part_name`.
static func _part_for_node(look: Dictionary, model_key: String, node_name: String,
		part_name: String) -> Dictionary:
	for row: Dictionary in look.get("parts", []):
		if row.get("model", "") == model_key and row.get("node", "") == node_name:
			return row

	for row: Dictionary in look.get("parts", []):
		if row["name"] == part_name:
			return row

	return {}


## A part name for the name of a node: a-z, 0-9, and _, with a letter
## first.
static func _part_name_of(node_name: String) -> String:
	var not_plain := RegEx.create_from_string("[^a-z0-9]+")
	var plain := not_plain.sub(node_name.to_snake_case(), "_", true)

	plain = plain.lstrip("_").rstrip("_")

	if plain.is_empty() or plain[0].is_valid_int():
		plain = (NODE_PART_PREFIX + plain).rstrip("_")

	return plain


# ─── Helpers ────────────────────────────────────────────────────────────────

## `base`, or `base` with the first number that makes a name not in `taken`.
static func unique_name(base: String, taken: PackedStringArray) -> String:
	if not base in taken:
		return base

	var number := 2

	while "%s_%d" % [base, number] in taken:
		number += 1

	return "%s_%d" % [base, number]


static func _part_names(look: Dictionary) -> PackedStringArray:
	var names := PackedStringArray()

	for row: Dictionary in look.get("parts", []):
		names.append(row["name"])

	return names


## The index of one part in the part list of a look, or -1.
static func part_index(look: Dictionary, part_name: String) -> int:
	var rows: Array = look.get("parts", [])

	for index in rows.size():
		if rows[index]["name"] == part_name:
			return index

	return -1
