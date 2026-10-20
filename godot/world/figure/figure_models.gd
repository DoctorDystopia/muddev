class_name FigureModels
extends RefCounted
## The models that the parts of a figure draw (DESIGN-0014 section 8.3).
##
## A part of a worn look names a model by its asset key, and one node of
## that model. This class holds the meshes of each model, and it gives
## [FigureBuilder] the mesh of each node.
##
## ## A model in figure space
##
## The space of a model file is the space of the figure: the feet at the
## origin, +Y up, the face to +Z. Thus, this class does not put a model in
## the unit box, as [ModelLoader] does for the mesh ladder. A node keeps the
## size and the place that its file gives it.
##
## ## One node is one mesh
##
## A node here is a node of the file that holds a mesh. A file with a torso
## node and two arm nodes gives three nodes, and each one is one part on
## its own bone. [method node_place] gives the place of a node in the space
## of the file. The workbench computes the place of the part on its bone
## from it.
##
## This class keeps the mesh and the place of each node, and it frees the
## scene of the file. A mesh is a resource, so nothing here needs a free.
##
## ## Where the bytes come from
##
## [method put_buffer] takes the bytes of one served model. The game gets
## them from its model fetch. [method from_directory] reads the served model
## tree of a directory on disk, for the figure workbench. It reads a file on
## the first ask for its model.
##
## ## The stamp
##
## [method stamp_of] changes when a model gets new bytes. [FigureBuilder]
## keeps the stamp with the content of a part, so a part draws again after
## its model changed.
##
## ## The whole model, in the unit box (10/17/2026)
##
## A served model of an item is not in figure space. Its file has the size
## and the place of its download. The node name [constant WHOLE_MODEL]
## gives each node of such a model as one mesh, in the unit box. The
## longest side is one unit, and the middle of the box is the origin. Each
## surface keeps its material. The served part of a figure draws it
## ([FigureOutfit]), and the place of that part gives its size.

const MANIFEST_NAME := "manifest.json"

## The node name of the whole model in the unit box. No node of a file has
## this name: Godot refuses a slash in the name of a node.
const WHOLE_MODEL := "/"

## The longest side of the whole model, in figure units.
const UNIT := 1.0

## A whole model with a box smaller than this on each side has no unit box.
const MIN_EXTENT := 0.000001

## The directory of the served model tree, under the web directory of the
## game.
const SERVED_DIRECTORY := "static/webclient/models"

## The keys of one node row of [member _nodes].
const _NAME := "name"
const _MESH := "mesh"
const _PLACE := "place"

## The last stamp that a model got, in each set of models.
static var _last_stamp := 0

## Model key -> the node rows of the model: `[{name, mesh, place}, ...]`.
## A row is one node of the file that holds a mesh, with its place in the
## space of the file.
var _nodes := {}

## Model key -> the stamp of its bytes.
var _stamps := {}

## The served model tree on disk, or "" for no directory.
var _directory := ""

## Model key -> the path of its file below [member _directory].
var _manifest := {}

## Model key -> true for a file of the directory that does not read.
var _unreadable := {}

## Model key -> the row of its whole model, made on the first ask.
var _wholes := {}


## The models of one served model tree on disk. `directory` holds
## `manifest.json`. A directory with no manifest gives no model.
static func from_directory(directory: String) -> FigureModels:
	var models := FigureModels.new()

	models._directory = directory
	models.read_manifest()

	return models


## Read the manifest of the directory again, and forget each model. The
## next ask for a model reads its file again, and the model then has a new
## stamp. Returns the count of models that the manifest names.
func read_manifest() -> int:
	var text := FileAccess.get_file_as_string(_directory.path_join(MANIFEST_NAME))
	var parsed: Variant = JSON.parse_string(text) if not text.is_empty() else {}

	_manifest = parsed if typeof(parsed) == TYPE_DICTIONARY else {}
	_nodes.clear()
	_stamps.clear()
	_unreadable.clear()
	_wholes.clear()

	return _manifest.size()


## Give one model its bytes: a served `.glb`. Returns false for bytes that
## are no glTF. The model then stays as it was.
func put_buffer(model_key: String, body: PackedByteArray) -> bool:
	var scene := ModelLoader.raw_scene(body, true)

	if scene == null:
		return false

	var rows := []

	_collect(scene, Transform3D.IDENTITY, rows)
	scene.free()
	_nodes[model_key] = rows
	_unreadable.erase(model_key)
	_wholes.erase(model_key)
	_last_stamp += 1
	_stamps[model_key] = _last_stamp

	return true


## True when the model is in hand, or when the directory has its file.
func has(model_key: String) -> bool:
	return _load(model_key)


## A number that changes when the model gets new bytes. Zero for a model
## that is not in hand. One count serves each set of models of a run. Thus,
## a second set never gives a stamp of the first set again.
func stamp_of(model_key: String) -> int:
	# The first ask of a model of the directory reads its file.
	_load(model_key)

	return _stamps.get(model_key, 0)


## The name of each node of a model that holds a mesh, in the order of the
## file. Two nodes with one name give the name one time.
func node_names(model_key: String) -> PackedStringArray:
	var names := PackedStringArray()

	for row: Dictionary in _rows_of(model_key):
		if not row[_NAME] in names:
			names.append(row[_NAME])

	return names


func has_node(model_key: String, node_name: String) -> bool:
	return not _row_of(model_key, node_name).is_empty()


## The place of one node in the space of its file.
func node_place(model_key: String, node_name: String) -> Transform3D:
	return _row_of(model_key, node_name).get(_PLACE, Transform3D.IDENTITY)


## The box of one node in the space of its file. An empty box for no such
## node.
func node_bounds(model_key: String, node_name: String) -> AABB:
	var row := _row_of(model_key, node_name)

	if row.is_empty():
		return AABB()

	return row[_PLACE] * (row[_MESH] as Mesh).get_aabb()


## The name of the material of each surface of one node. In a figure model,
## the name of a material is a color role (DESIGN-0014 section 8.5).
func material_names(model_key: String, node_name: String) -> PackedStringArray:
	var names := PackedStringArray()
	var row := _row_of(model_key, node_name)

	if row.is_empty():
		return names

	var mesh: Mesh = row[_MESH]

	for surface in mesh.get_surface_count():
		var material := mesh.surface_get_material(surface)

		names.append("" if material == null else material.resource_name)

	return names


## A new mesh instance for one node of a model, with no place of its own.
## The mesh is the mesh of the model, and each instance shares it. Null for
## no such node. [constant WHOLE_MODEL] gives the whole model in the unit
## box.
func instance_of(model_key: String, node_name: String) -> MeshInstance3D:
	var row := _row_of(model_key, node_name)

	if row.is_empty():
		return null

	var instance := MeshInstance3D.new()

	instance.name = node_name.validate_node_name()
	instance.mesh = row[_MESH]

	return instance


# ─── Private ────────────────────────────────────────────────────────────────

## Make sure that one model is in hand. A model of the directory reads its
## file on the first ask. A file that does not read fails one time. Returns
## false for a model that is not there.
func _load(model_key: String) -> bool:
	if _nodes.has(model_key):
		return true

	if model_key.is_empty() or _unreadable.has(model_key) \
			or not _manifest.has(model_key):
		return false

	var body := FileAccess.get_file_as_bytes(
		_directory.path_join(str(_manifest[model_key])))

	if body.is_empty() or not put_buffer(model_key, body):
		_unreadable[model_key] = true
		return false

	return true


## The node rows of one model, or an empty list.
func _rows_of(model_key: String) -> Array:
	return _nodes[model_key] if _load(model_key) else []


## The row of one node of a model, or an empty dictionary. The name
## [constant WHOLE_MODEL] gives the row of the whole model.
func _row_of(model_key: String, node_name: String) -> Dictionary:
	if node_name == WHOLE_MODEL:
		return _whole_row(model_key)

	for row: Dictionary in _rows_of(model_key):
		if row[_NAME] == node_name:
			return row

	return {}


## The row of the whole model in the unit box. A model that is not there,
## or that has no box, gives an empty dictionary. The first ask makes it.
func _whole_row(model_key: String) -> Dictionary:
	if _wholes.has(model_key):
		return _wholes[model_key]

	var rows := _rows_of(model_key)

	if rows.is_empty():
		return {}

	var mesh := _unit_mesh(rows)
	var row := {} if mesh == null \
		else {_NAME: WHOLE_MODEL, _MESH: mesh, _PLACE: Transform3D.IDENTITY}

	_wholes[model_key] = row

	return row


## The mesh of each node row as one mesh, in the unit box. The longest side
## is [constant UNIT], and the middle of the box is the origin. Rows with
## no box give null.
static func _unit_mesh(rows: Array) -> ArrayMesh:
	var bounds: AABB = rows[0][_PLACE] * (rows[0][_MESH] as Mesh).get_aabb()

	for row: Dictionary in rows:
		bounds = bounds.merge(row[_PLACE] * (row[_MESH] as Mesh).get_aabb())

	var longest := maxf(bounds.size.x, maxf(bounds.size.y, bounds.size.z))

	if longest < MIN_EXTENT:
		return null

	var factor := UNIT / longest
	var unit := Transform3D(Basis.from_scale(Vector3.ONE * factor), -bounds.get_center() * factor)
	var merged := ArrayMesh.new()

	for row: Dictionary in rows:
		_append_surfaces(merged, row[_MESH], unit * row[_PLACE])

	return merged


## Add each surface of `mesh` to `target`, moved by `place`. Each surface
## keeps its material. A normal and a tangent turn with the basis, and each
## keeps the length one.
static func _append_surfaces(target: ArrayMesh, mesh: Mesh, place: Transform3D) -> void:
	var normal_basis := place.basis.inverse().transposed()

	for surface in mesh.get_surface_count():
		var arrays := mesh.surface_get_arrays(surface)
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var primitive := Mesh.PRIMITIVE_TRIANGLES

		for index in vertices.size():
			vertices[index] = place * vertices[index]

		arrays[Mesh.ARRAY_VERTEX] = vertices

		if arrays[Mesh.ARRAY_NORMAL] != null:
			arrays[Mesh.ARRAY_NORMAL] = _turned(arrays[Mesh.ARRAY_NORMAL], normal_basis)

		if arrays[Mesh.ARRAY_TANGENT] != null:
			arrays[Mesh.ARRAY_TANGENT] = _turned_tangents(arrays[Mesh.ARRAY_TANGENT], place.basis)

		if mesh is ArrayMesh:
			primitive = (mesh as ArrayMesh).surface_get_primitive_type(surface)

		target.add_surface_from_arrays(primitive, arrays)
		target.surface_set_material(target.get_surface_count() - 1,
			mesh.surface_get_material(surface))


## Turn each vector of `directions` by `basis`, and give it the length one.
static func _turned(directions: PackedVector3Array, basis: Basis) -> PackedVector3Array:
	for index in directions.size():
		directions[index] = (basis * directions[index]).normalized()

	return directions


## Each tangent of a tangent array, turned by `basis`. A tangent is four
## numbers: the direction, then the sign of the bitangent, which stays.
static func _turned_tangents(tangents: PackedFloat32Array, basis: Basis) -> PackedFloat32Array:
	for index in range(0, tangents.size(), 4):
		var turned := (basis * Vector3(tangents[index], tangents[index + 1],
			tangents[index + 2])).normalized()

		tangents[index] = turned.x
		tangents[index + 1] = turned.y
		tangents[index + 2] = turned.z

	return tangents


## Add one row for each node below `node` that holds a mesh. `place` is the
## place of `node` in the file. The root of the scene is no node of the
## file, so its own place stays out.
static func _collect(node: Node, place: Transform3D, rows: Array) -> void:
	for child: Node in node.get_children():
		var spatial := child as Node3D
		var child_place := place if spatial == null else place * spatial.transform
		var instance := child as MeshInstance3D

		if instance != null and instance.mesh != null:
			rows.append({_NAME: String(instance.name), _MESH: instance.mesh,
				_PLACE: child_place})

		_collect(child, child_place, rows)
