class_name FigureGlow
extends RefCounted
## The glow of the lit augments on one figure (DESIGN-0015, 10/30/2026).
##
## ## The server names what burns, the client says what it looks like
##
## A row of a character and `char_avatar` carry `augments`, the keys of the
## lit augments. [AugmentLook] says which parts glow for each key, and in
## what colour. This class writes that onto the parts of a built figure: an
## emission on each mesh of a named part, through [MeshGlow], and the rest
## colour on each other part.
##
## ## Emission, as the hover does it
##
## The hover of the pool lights every material of an entity, and puts them
## all to rest when the mouse leaves. A glow that the rest erased would come
## back on the next sync only. Thus, the pool applies the glow again after
## each rest. [method apply] is cheap: a few uniform writes.
##
## ## A node with no skeleton draws no glow
##
## [FigureLibrary.build] gives a holder with the figure inside. The avatar
## is a mesh from the ladder until the figure set arrives. Thus, the glow
## finds the skeleton under the node, wherever it is. A node with no
## skeleton has no part. A served model on a part has meshes under the
## part node, and they glow with it.
##
## Author: Nick Hobar
## Creation date: 10/30/2026

## How bright a glowing part is. The hover of the pool uses its own energy.
const GLOW_ENERGY := 1.6


## Write the glow of `augments` onto `figure`. Each part that a lit augment
## names glows in its colour. Each other part rests.
static func apply(figure: Node3D, augments: Array) -> void:
	if figure == null:
		return

	var colors := AugmentLook.part_colors(augments)

	for part: Node3D in part_nodes_under(figure):
		var part_id := FigureBuilder.part_id(part)
		var part_name := str(part_id[1]) if part_id.size() > 1 else ""
		var materials := _materials_of(part)

		if colors.has(part_name):
			for material: BaseMaterial3D in materials:
				MeshGlow.prepare(material)
				MeshGlow.light(material, colors[part_name], GLOW_ENERGY)
		else:
			for material: BaseMaterial3D in materials:
				MeshGlow.rest(material)


## Each part node under `node`: the figure itself, or a holder with the
## figure inside. An empty array for a node with no skeleton, such as a
## mesh from the ladder.
static func part_nodes_under(node: Node3D) -> Array[Node3D]:
	var found: Array[Node3D] = []

	if node == null:
		return found

	var skeleton := node.find_child(FigureBuilder.SKELETON_NAME, true, false) as Skeleton3D

	if skeleton == null:
		return found

	for attachment: Node in skeleton.get_children():
		for child: Node in attachment.get_children():
			if child.has_meta(FigureBuilder.PART_META):
				found.append(child)

	return found


## The part names that glow for `augments`, for a test and a tip.
static func glowing_parts(augments: Array) -> PackedStringArray:
	var parts := PackedStringArray()

	for part: String in AugmentLook.part_colors(augments):
		parts.append(part)

	return parts


## Every writable material under one node, as [method EntityPool._materials_of]
## finds them: the override of a procedural part, and the surface overrides
## of a fetched model.
static func _materials_of(root: Node3D) -> Array:
	var found: Array = []
	var stack: Array[Node] = [root]

	while not stack.is_empty():
		var node: Node = stack.pop_back()
		var instance := node as MeshInstance3D

		if instance != null:
			var override := instance.material_override as BaseMaterial3D

			if override != null:
				found.append(override)

			for surface: int in instance.get_surface_override_material_count():
				var material := instance.get_surface_override_material(
					surface) as BaseMaterial3D

				if material != null:
					found.append(material)

		for child: Node in node.get_children():
			stack.append(child)

	return found
