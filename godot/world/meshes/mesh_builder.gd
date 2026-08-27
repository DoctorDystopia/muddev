class_name MeshBuilder
extends RefCounted
## Turns part data into a [Node3D]. The only file that calls a primitive
## constructor, and the only one that has to know what `radius_top` means.
##
## It knows NO family names. Everything it draws arrives as the dictionaries
## [FamilyShapes] describes, which is what lets the shape table be edited
## without touching mesh construction, and lets this be tested against parts
## that describe nothing in particular.
##
## ## One material per part, never shared
##
## Every part gets its own [StandardMaterial3D] from [MeshPalette]. That is
## deliberate and it is where the browser pane had to add machinery: three.js
## clones share a cached prototype's materials, so tinting one raider for a hit
## flash repainted every raider in the room, and `takeOwnMaterials` exists to
## undo that. Building materials per part means the bug has nowhere to live.
##
## ## Every result fits a unit box
##
## Parts are authored inside one, and this does not rescale them — it trusts the
## table. [ModelLoader] normalises tier 1 into the same box, so all three tiers
## of the ladder hand back something one unit across and each caller applies a
## single scale of its own.

## Fallbacks for the optional keys, so a part may name only what it cares about.
const DEFAULT_SEGMENTS := 12
const DEFAULT_RADIUS := 0.25
const DEFAULT_HEIGHT := 0.5
const DEFAULT_TORUS_INNER := 0.2
const DEFAULT_TORUS_OUTER := 0.3
const DEFAULT_BOX_SIZE := Vector3(0.4, 0.4, 0.4)

## Rings used for a faceted stand-in. Two reads as an octahedron, three or more
## as a lump of rock; the part's `segments` picks the equator either way.
const FACETED_RINGS := 2


## Build one family's parts into a node.
##
## Returns a [Node3D] with one [MeshInstance3D] child per part, centred on the
## origin. Never null and never empty — an unrecognised shape still contributes
## a box rather than a hole, because a missing entity is far worse than an ugly
## one.
static func build(parts: Array) -> Node3D:
	var root := Node3D.new()

	for part: Dictionary in parts:
		root.add_child(build_part(part))

	return root


## Build one part.
static func build_part(part: Dictionary) -> MeshInstance3D:
	var instance := MeshInstance3D.new()

	instance.mesh = _mesh_for(part)
	instance.material_override = MeshPalette.material_for(
		str(part.get("color", MeshPalette.GENERIC)),
		str(part.get("finish", MeshPalette.FINISH_MATTE)))

	instance.position = part.get("offset", Vector3.ZERO)
	instance.scale = part.get("scale", Vector3.ONE)

	var rotation: Vector3 = part.get("rotation", Vector3.ZERO)

	if rotation != Vector3.ZERO:
		instance.rotation = rotation

	return instance


# ─── Primitives ──────────────────────────────────────────────────────────────

## The mesh for one part, by shape.
##
## A `match` rather than a table of builder callables: this is the one place in
## the design that is ALLOWED to enumerate, because the shape vocabulary is
## fixed by what Godot provides rather than by what the game contains. Families
## grow; primitives do not.
static func _mesh_for(part: Dictionary) -> Mesh:
	match str(part.get("shape", "")):
		FamilyShapes.SHAPE_BOX:
			return _box(part)

		FamilyShapes.SHAPE_SPHERE:
			return _sphere(part)

		FamilyShapes.SHAPE_CYLINDER:
			return _cylinder(part)

		FamilyShapes.SHAPE_CONE:
			return _cone(part)

		FamilyShapes.SHAPE_TORUS:
			return _torus(part)

		FamilyShapes.SHAPE_FACETED:
			return _faceted(part)

	push_warning("MeshBuilder: unknown shape '%s'" % part.get("shape", ""))

	return _box(part)


static func _box(part: Dictionary) -> BoxMesh:
	var mesh := BoxMesh.new()
	mesh.size = part.get("size", DEFAULT_BOX_SIZE)

	return mesh


static func _sphere(part: Dictionary) -> SphereMesh:
	var mesh := SphereMesh.new()
	var radius: float = part.get("radius", DEFAULT_RADIUS)

	mesh.radius = radius
	# SphereMesh takes a full height, not a second radius, so a plain sphere is
	# twice its radius. Getting this wrong makes every head an egg.
	mesh.height = radius * 2.0
	mesh.radial_segments = part.get("segments", DEFAULT_SEGMENTS)

	return mesh


## A cylinder, optionally tapered and optionally an open shell.
##
## `radius` is the BOTTOM and `radius_top` the top, defaulting to the bottom so
## an untapered cylinder names one number. That ordering matches the shape
## table, which was transcribed from the browser's `CylinderGeometry(top,
## bottom, ...)` — the arguments are the other way round there, which is exactly
## the kind of silent flip worth naming once here rather than rediscovering.
static func _cylinder(part: Dictionary) -> CylinderMesh:
	var mesh := CylinderMesh.new()
	var radius: float = part.get("radius", DEFAULT_RADIUS)

	mesh.bottom_radius = radius
	mesh.top_radius = part.get("radius_top", radius)
	mesh.height = part.get("height", DEFAULT_HEIGHT)
	mesh.radial_segments = part.get("segments", DEFAULT_SEGMENTS)
	mesh.cap_top = not part.get("open", false)
	mesh.cap_bottom = not part.get("open", false)

	return mesh


## A cone is a cylinder whose top has closed to a point.
static func _cone(part: Dictionary) -> CylinderMesh:
	var mesh := CylinderMesh.new()

	mesh.bottom_radius = part.get("radius", DEFAULT_RADIUS)
	mesh.top_radius = 0.0
	mesh.height = part.get("height", DEFAULT_HEIGHT)
	mesh.radial_segments = part.get("segments", DEFAULT_SEGMENTS)

	return mesh


static func _torus(part: Dictionary) -> TorusMesh:
	var mesh := TorusMesh.new()

	mesh.inner_radius = part.get("inner", DEFAULT_TORUS_INNER)
	mesh.outer_radius = part.get("outer", DEFAULT_TORUS_OUTER)
	mesh.rings = part.get("segments", DEFAULT_SEGMENTS)

	return mesh


## A deliberately low-poly sphere, standing in for a polyhedron.
##
## Godot ships no octahedron or icosahedron primitive. Few enough segments and a
## sphere is faceted in the same way, which is all these need to be: the browser
## states it outright, that silhouette does all the work at the size entities are
## actually drawn. See [constant FamilyShapes.SHAPE_FACETED].
static func _faceted(part: Dictionary) -> SphereMesh:
	var mesh := SphereMesh.new()
	var radius: float = part.get("radius", DEFAULT_RADIUS)

	mesh.radius = radius
	mesh.height = radius * 2.0
	mesh.radial_segments = part.get("segments", 6)
	mesh.rings = FACETED_RINGS

	return mesh
