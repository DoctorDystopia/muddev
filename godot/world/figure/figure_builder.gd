class_name FigureBuilder
extends RefCounted
## Builds a figure: one node from a rig and a list of worn looks
## (DESIGN-0014 section 8.2).
##
## The game and the figure workbench build a figure with this class
## (requirement D6). Thus, what the author sees is what the player sees.
##
## ## The node
##
##     Figure (Node3D)
##       ClipPlayer (AnimationPlayer), after the first clip ([FigureClips])
##       GeneralSkeleton (Skeleton3D)
##         <bone> (BoneAttachment3D), one for each bone that carries a part
##           <look>__<part> (Node3D), the part, with its place on the bone
##             MeshInstance3D, one for each shape of the shape list, or
##             one for the node of its model
##
## This is the attached version of Phase W0: one draw for each shape in
## each pass. It serves the workbench, because each part is a node that the
## Godot tools can move. The game draws a crowd with the shared version,
## which a later phase designs. The file formats are the same for the two.
##
## ## A refresh keeps each node
##
## [method refresh] changes a figure in place. A part that stays keeps its
## node. The workbench needs this: the undo history of the editor names the
## node of each part that a gizmo moved, and a selected node that leaves the
## tree is not selected after that.
##
## ## The hide list
##
## A look names the regions that it hides. The builder leaves out each part
## of each other look in such a region. A look does not hide its own parts:
## the parts of a chainbody take the place of the torso that it hides.
##
## ## A part with a model
##
## A part can name one node of one served model (Phase W4). [FigureModels]
## gives the mesh of that node, in the space of the figure. The place of the
## part on its bone puts the node where its file has it. While the model is
## not in hand, the part draws its shape list.
##
## A surface of a model has the name of its material as its color role. A
## role of the color table of the look gets its named color. Each other
## surface keeps the material of the model.
##
## ## The palette, and the colors of the figure (Phase W5)
##
## A shape names a color role, the look gives the role a named color, and
## the palette gives the named color its color and its finish
## ([FigurePalette]). A shape with a `finish` key keeps that finish. With no
## palette, each named color comes from [MeshPalette].
##
## `figure_colors` is the color table of one figure: color role -> named
## color. It wins over the color table of each look. The skin and the hair
## of a character thus take their color from the character, not from the
## look (DESIGN-0014 section 8.5).
##
## ## The fit of a body type
##
## A look can give a part another place on one body type
## ([method FigureLook.place_of]). The key of the rig is the body type.
##
## ## A fault does not stop the figure
##
## A part on a bone that the rig does not have draws nothing, and the other
## parts draw (requirement D7). A part with a model that is not there, or
## with a node that its model does not have, draws its shape list.

const FIGURE_NAME := "Figure"

## The name that a clip of the editor import gives its skeleton
## (DESIGN-0014 section 12.4). Each track of a clip has the path
## `%GeneralSkeleton:<bone>`. Thus, the skeleton has this name as a unique
## name, and the figure is its owner. [FigureClips] plays a clip from the
## figure node, and the path then finds the skeleton.
const SKELETON_NAME := "GeneralSkeleton"

## The meta of a part node: `[look key, part name]`.
const PART_META := "figure_part"

## The meta of a part node: one text for its shape list and its colors.
const CONTENT_META := "figure_content"

## Between the look key and the part name in a node name. A node name
## cannot hold a point or a slash.
const NAME_JOIN := "__"

## The shared materials of the model surfaces, by the text of
## [method FigurePalette.material_key].
static var _role_materials := {}


## A new figure.
##
## - `looks` is an array of [FigureLook]. The body is first.
## - `models` gives the model of each part that names one. With no `models`,
##   such a part draws its shape list.
## - `palette` gives each named color its color.
## - `figure_colors` is the color table of this figure.
static func build(rig: FigureRig, looks: Array, models: FigureModels = null,
		palette: FigurePalette = null, figure_colors := {}) -> Node3D:
	var figure := Node3D.new()
	var skeleton := Skeleton3D.new()

	figure.name = FIGURE_NAME
	skeleton.name = SKELETON_NAME
	figure.add_child(skeleton)
	skeleton.owner = figure
	skeleton.unique_name_in_owner = true
	refresh(figure, rig, looks, models, palette, figure_colors)

	return figure


## Make a figure of [method build] show `rig` and `looks`. Each part that
## stays keeps its node.
static func refresh(figure: Node3D, rig: FigureRig, looks: Array,
		models: FigureModels = null, palette: FigurePalette = null,
		figure_colors := {}) -> void:
	var skeleton := skeleton_of(figure)
	var old := _parts_by_id(figure)
	var wanted := {}
	# A figure with no palette gets an empty one, and each named color then
	# comes from MeshPalette. The empty one is not a static variable: this
	# script has no `@tool`, so the editor does not run a static initializer
	# of it, and the variable is null there.
	var paint := {"models": models, "figure_colors": figure_colors,
		"palette": FigurePalette.new() if palette == null else palette}

	rig.apply_to(skeleton)

	for look: FigureLook in looks:
		for row: Dictionary in _shown_parts(look, looks):
			if skeleton.find_bone(row["bone"]) < 0:
				continue

			var id := _id_text(look.key(), row["name"])

			wanted[id] = true
			_place(skeleton, old.get(id), look, row, rig.key(), paint)

	for id: String in old:
		if not wanted.has(id):
			_discard(old[id])

	_tidy_attachments(skeleton)


## The skeleton of a figure.
static func skeleton_of(figure: Node3D) -> Skeleton3D:
	return figure.get_node(SKELETON_NAME) as Skeleton3D


## Each part node of a figure.
static func part_nodes(figure: Node3D) -> Array[Node3D]:
	var found: Array[Node3D] = []

	for attachment: Node in skeleton_of(figure).get_children():
		for child: Node in attachment.get_children():
			if child.has_meta(PART_META):
				found.append(child)

	return found


## The node of one part, or null.
static func part_node(figure: Node3D, look_key: String, part_name: String) -> Node3D:
	return _parts_by_id(figure).get(_id_text(look_key, part_name))


## `[look key, part name]` of a part node, or an empty array for a node that
## is not a part.
static func part_id(node: Node) -> Array:
	if node == null or not node.has_meta(PART_META):
		return []

	return node.get_meta(PART_META)


## The cost of a figure: `{parts, draws, triangles}`. One draw is one
## surface of one mesh. The mesh of a shape has one surface. The node of a
## model has one surface for each material.
static func counts(figure: Node3D) -> Dictionary:
	var draws := 0
	var triangles := 0
	var parts := part_nodes(figure)

	for part: Node3D in parts:
		for child: Node in part.get_children():
			var instance := child as MeshInstance3D

			if instance == null or instance.mesh == null:
				continue

			draws += instance.mesh.get_surface_count()
			triangles += instance.mesh.get_faces().size() / 3

	return {"parts": parts.size(), "draws": draws, "triangles": triangles}


# ─── The parts ──────────────────────────────────────────────────────────────

## The parts of `look` that no other look of `looks` hides.
static func _shown_parts(look: FigureLook, looks: Array) -> Array:
	var hidden := {}
	var shown := []

	for other: FigureLook in looks:
		if other != look:
			for region: String in other.hides():
				hidden[region] = true

	for row: Dictionary in look.parts():
		if not hidden.has(row.get("region", "")):
			shown.append(row)

	return shown


## Put one part on its bone.
##
## - `node` is the node that the part has from an earlier build, or null.
## - `body_key` is the body type of the figure.
## - `paint` holds `models`, `palette`, and `figure_colors`.
static func _place(skeleton: Skeleton3D, node: Variant, look: FigureLook,
		row: Dictionary, body_key: String, paint: Dictionary) -> void:
	var part: Node3D = node
	var attachment := _attachment_for(skeleton, row["bone"])
	var xform := look.place_of(row["name"], body_key)

	if part == null:
		part = Node3D.new()
		part.name = look.key() + NAME_JOIN + str(row["name"])
		part.set_meta(PART_META, [look.key(), row["name"]])

	if part.get_parent() != attachment:
		if part.get_parent() != null:
			part.get_parent().remove_child(part)

		attachment.add_child(part)

	_fill(part, row, _colors_of(look, paint["figure_colors"]), paint)

	if not part.transform.is_equal_approx(xform):
		part.transform = xform


## The color table of one look on one figure: the table of the look, with
## each color of the figure over it.
static func _colors_of(look: FigureLook, figure_colors: Dictionary) -> Dictionary:
	if figure_colors.is_empty():
		return look.colors()

	var colors: Dictionary = look.colors().duplicate()

	colors.merge(figure_colors, true)

	return colors


## Give a part node its meshes: the node of its model, or the meshes of its
## shape list. A part with the same content as before keeps its meshes. The
## content is the shapes, the colors, the model, the node, the stamp of the
## model, and the stamp of the palette.
static func _fill(part: Node3D, row: Dictionary, colors: Dictionary,
		paint: Dictionary) -> void:
	var models: FigureModels = paint["models"]
	var palette: FigurePalette = paint["palette"]
	var model_key: String = row.get("model", "")
	var node_name: String = row.get("node", "")
	var stamp := 0 if models == null else models.stamp_of(model_key)
	var content := JSON.stringify([row.get("shapes", []), colors, model_key, node_name,
		stamp, palette.stamp()], "", true)

	if part.get_meta(CONTENT_META, "") == content:
		return

	for child: Node in part.get_children():
		part.remove_child(child)
		child.free()

	var instance := _model_instance(models, model_key, node_name, colors, palette)

	if instance != null:
		part.add_child(instance)
	else:
		for shape: Dictionary in row.get("shapes", []):
			part.add_child(_shape_instance(shape, colors, palette))

	part.set_meta(CONTENT_META, content)


## The mesh of one shape of a shape list, with the color of its color role.
## A shape with a `finish` key keeps that finish. Each other shape gets the
## finish of its named color.
static func _shape_instance(shape: Dictionary, colors: Dictionary,
		palette: FigurePalette) -> MeshInstance3D:
	var role: String = shape.get("color", MeshPalette.GENERIC)
	var named := palette.named_for(role, colors)
	var material := palette.material_for(named, shape.get("finish", ""))

	return MeshBuilder.build_part(FigureLook.builder_shape(shape, colors), material)


## The mesh of one node of one model, with a palette color on each surface
## whose color role the color table has. Null when the model or the node is
## not in hand.
static func _model_instance(models: FigureModels, model_key: String, node_name: String,
		colors: Dictionary, palette: FigurePalette) -> MeshInstance3D:
	if models == null or model_key.is_empty():
		return null

	var instance := models.instance_of(model_key, node_name)

	if instance == null:
		return null

	var roles := models.material_names(model_key, node_name)

	for surface in roles.size():
		if colors.has(roles[surface]):
			instance.set_surface_override_material(surface,
				_role_material(palette, colors[roles[surface]]))

	return instance


## The material of one named color on a surface of a model. Each surface
## of one color and one finish shares one material from a small cache. The
## builder uses no instance uniform (DESIGN-0014 section 8.5).
static func _role_material(palette: FigurePalette, color: String) -> StandardMaterial3D:
	var cache_key := palette.material_key(color)

	if not _role_materials.has(cache_key):
		_role_materials[cache_key] = palette.material_for(color)

	return _role_materials[cache_key]


## The attachment of one bone. The skeleton has one for each bone that
## carries a part.
static func _attachment_for(skeleton: Skeleton3D, bone: String) -> BoneAttachment3D:
	var attachment := skeleton.get_node_or_null(bone) as BoneAttachment3D

	if attachment == null:
		attachment = BoneAttachment3D.new()
		attachment.name = bone
		skeleton.add_child(attachment)

	# The index of a bone changes when the rig gets a bone, so set the two.
	attachment.bone_name = bone
	attachment.bone_idx = skeleton.find_bone(bone)

	return attachment


## Free each attachment that carries no part.
static func _tidy_attachments(skeleton: Skeleton3D) -> void:
	for child: Node in skeleton.get_children():
		if child is BoneAttachment3D and child.get_child_count() == 0:
			_discard(child)


## Each part node of a figure, by the text of its id.
static func _parts_by_id(figure: Node3D) -> Dictionary:
	var found := {}

	for part: Node3D in part_nodes(figure):
		var id: Array = part.get_meta(PART_META)

		found[_id_text(id[0], id[1])] = part

	return found


static func _id_text(look_key: String, part_name: String) -> String:
	return look_key + NAME_JOIN + part_name


## Take a node out of the figure and free it. A node in the tree goes at
## the end of the frame. The editor can hold it until then.
static func _discard(node: Node) -> void:
	var in_tree := node.is_inside_tree()

	if node.get_parent() != null:
		node.get_parent().remove_child(node)

	if in_tree:
		node.queue_free()
	else:
		node.free()
