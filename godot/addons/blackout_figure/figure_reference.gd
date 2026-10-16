@tool
class_name FigureReference
extends RefCounted
## The reference body of the figure workbench: one figure in its rest pose,
## as a `.glb` file for a modeler (DESIGN-0014 section 8.3).
##
## The author opens the file in a modeler, and models a part over the body:
## a helm over the head, a chainbody over the torso and the arms. The space
## of the file is the space of the figure. Thus, the new part comes back
## through the import with its place, and it sits where its author made it.
##
## ## The file
##
## The file has one node for each part of the figure, with the name of the
## part. A part of a worn look of the outfit has the key of its look before
## its name. Each node has its place in the rest pose. The file has no
## skeleton, because a part of a figure needs no armature (decision 2).
##
## A node holds one mesh, with one surface for each color role of its part.
## The material of a surface has the name of its color role. A modeler then
## shows which role each surface of the body has, and a model that comes
## back keeps the names (DESIGN-0014 section 8.5).
##
## The file has one material for each color role. The glTF writer of Godot
## gives a second material with one name a number: `skin2`. Thus, each
## surface of one role shares the material of the first one, with its color.
##
## Nothing here needs the editor. `tests/test_figure_models.tscn` writes a
## reference body with no editor (requirement S3).

const FILE_SUFFIX := ".glb"

## The name of the root node of the file, before the body type.
const ROOT_PREFIX := "reference_"

## Between the key of a look and the name of a part, in a node name.
const NAME_JOIN := "__"

## The name of a material of a model that has no name, before its number.
const NO_ROLE := "material_"


## Write the reference body of one rig to an OS path. Returns OK, or the
## error of the writer.
##
## The list `looks` is the list that the figure builder takes. The body is
## first. Each worn look that the author wants in the file comes after it.
static func export(rig: FigureRig, looks: Array, path: String,
		models: FigureModels = null, palette: FigurePalette = null) -> Error:
	var scene := scene_of(rig, looks, models, palette)
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	var problem := document.append_from_scene(scene, state)

	if problem == OK:
		DirAccess.make_dir_recursive_absolute(path.get_base_dir())
		problem = document.write_to_filesystem(state, path)

	scene.free()

	return problem


## The bytes of the reference body of one rig, as a `.glb`. A scene that
## the glTF writer refuses gives no bytes. A test gives the bytes to a set
## of models, so it needs no file ([method FigureModels.put_buffer]).
static func buffer_of(rig: FigureRig, looks: Array,
		models: FigureModels = null, palette: FigurePalette = null) -> PackedByteArray:
	var scene := scene_of(rig, looks, models, palette)
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	var body := PackedByteArray()

	if document.append_from_scene(scene, state) == OK:
		body = document.generate_buffer(state)

	scene.free()

	return body


## The scene of a reference body: one mesh node for each part that the
## figure shows, at its place in the rest pose. The caller frees it.
static func scene_of(rig: FigureRig, looks: Array, models: FigureModels = null,
		palette: FigurePalette = null) -> Node3D:
	var figure := FigureBuilder.build(rig, looks, models, palette)
	var by_key := {}
	var materials := {}
	var root := Node3D.new()

	root.name = ROOT_PREFIX + rig.key()

	for look: FigureLook in looks:
		by_key[look.key()] = look

	for part: Node3D in FigureBuilder.part_nodes(figure):
		var id := FigureBuilder.part_id(part)
		var look: FigureLook = by_key[id[0]]
		var row := look.part(id[1])
		var node := MeshInstance3D.new()

		node.name = id[1] if id[0] == rig.key() else id[0] + NAME_JOIN + id[1]
		node.transform = rig.global_rest_of(row["bone"]) * look.place_of(id[1], rig.key())
		node.mesh = _part_mesh(part, row, materials)
		root.add_child(node)
		# In the editor, the glTF writer leaves out a node with no owner. The
		# file then has no mesh, and the writer gives no error.
		node.owner = root

	figure.free()

	return root


## One mesh for the meshes of one part node: one surface for each color
## role, in the order of the first use of each role. `materials` is color
## role -> the one material of that role in the file.
static func _part_mesh(part: Node3D, row: Dictionary, materials: Dictionary) -> ArrayMesh:
	var tools := {}
	var mesh := ArrayMesh.new()

	for index in part.get_child_count():
		var source := part.get_child(index) as MeshInstance3D

		if source == null or source.mesh == null:
			continue

		for surface in source.mesh.get_surface_count():
			var material := source.get_active_material(surface)
			var role := _role_of(row, index, source, material, materials.size())

			if not materials.has(role):
				materials[role] = _named(role, material)

			if not tools.has(role):
				tools[role] = SurfaceTool.new()
				tools[role].begin(Mesh.PRIMITIVE_TRIANGLES)
				tools[role].set_material(materials[role])

			(tools[role] as SurfaceTool).append_from(source.mesh, surface, source.transform)

	for role: String in tools:
		(tools[role] as SurfaceTool).commit(mesh)

	return mesh


## A copy of a material with the name of its color role. A surface with no
## material gets a plain one.
static func _named(role: String, material: Material) -> Material:
	var named: Material = StandardMaterial3D.new() if material == null \
		else material.duplicate()

	named.resource_name = role

	return named


## The color role of one surface of one mesh of a part. The mesh of a shape
## has the role of its shape: only such a mesh has one material for the
## whole mesh. The node of a model has the name of its material.
static func _role_of(row: Dictionary, index: int, source: MeshInstance3D,
		material: Material, count: int) -> String:
	var shapes: Array = row.get("shapes", [])

	if source.material_override != null and index < shapes.size():
		return shapes[index].get("color", MeshPalette.GENERIC)

	if material == null or material.resource_name.is_empty():
		return NO_ROLE + str(count)

	return material.resource_name
