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
## Every part gets its own [StandardMaterial3D] from the palette. That is
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

## A prism needs three sides to hold a volume.
const PRISM_FEWEST_SIDES := 3

## A triangle of a prism with a smaller cross product than this, as a
## square, is a point or a line. Two edges of about 0.1 mm give this value.
const PRISM_NO_AREA := 1e-16


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


## Build one part. With a `material`, the part takes it, and no palette is
## asked. The figure builder gives the material of its own palette
## (DESIGN-0014, Phase W5).
##
## With no material, the part draws with the active palette
## ([method FigurePalette.shared], ENG-0011 step L4): the `color` of the
## part is a color role or a named color of that palette, and a part with
## no `finish` takes the finish of its named color. A name that the palette
## does not have comes from [MeshPalette], as before the palette existed.
static func build_part(part: Dictionary, material: Material = null) -> MeshInstance3D:
	var instance := MeshInstance3D.new()

	instance.mesh = _mesh_for(part)

	if material == null:
		material = FigurePalette.shared().material_for_role(
			str(part.get("color", MeshPalette.GENERIC)), str(part.get("finish", "")))

	instance.material_override = material

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

		FamilyShapes.SHAPE_PRISM:
			return _prism(part)

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
	_set_rings(mesh, "rings", part)

	return mesh


## Give a mesh the `rings` of its part. A part with no `rings` keeps the
## count that Godot gives the primitive. The figure builder names a low
## count, because a crowd pays for each triangle (DESIGN-0014 section 12.4).
static func _set_rings(mesh: PrimitiveMesh, property: String, part: Dictionary) -> void:
	if part.has("rings"):
		mesh.set(property, int(part["rings"]))


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
	_set_rings(mesh, "rings", part)

	return mesh


## A cone is a cylinder whose top has closed to a point.
static func _cone(part: Dictionary) -> CylinderMesh:
	var mesh := CylinderMesh.new()

	mesh.bottom_radius = part.get("radius", DEFAULT_RADIUS)
	mesh.top_radius = 0.0
	mesh.height = part.get("height", DEFAULT_HEIGHT)
	mesh.radial_segments = part.get("segments", DEFAULT_SEGMENTS)
	_set_rings(mesh, "rings", part)

	return mesh


## A torus. `segments` is the count around the hole, and `rings` is the
## count around the tube.
static func _torus(part: Dictionary) -> TorusMesh:
	var mesh := TorusMesh.new()

	mesh.inner_radius = part.get("inner", DEFAULT_TORUS_INNER)
	mesh.outer_radius = part.get("outer", DEFAULT_TORUS_OUTER)
	mesh.rings = part.get("segments", DEFAULT_SEGMENTS)
	_set_rings(mesh, "ring_segments", part)

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


# ─── The prism ───────────────────────────────────────────────────────────────

## A tapered block with flat faces. See [constant FamilyShapes.SHAPE_PRISM].
##
## The bottom face is at half of the height below the origin, and the top
## face is at half of the height above it. `size` gives the width and the
## depth of the bottom face. `top_width` and `top_depth` give the top face,
## and `lean_x` and `lean_z` move it to one side. A face with no width and
## no depth makes a point.
##
## Each triangle has its own three vertices and its own normal. That is the
## flat shade of a low-poly model. A [CylinderMesh] with few sides has
## smooth normals, so it cannot give this look.
static func _prism(part: Dictionary) -> ArrayMesh:
	var size: Vector3 = part.get("size", DEFAULT_BOX_SIZE)
	var top := Vector2(part.get("top_width", size.x), part.get("top_depth", size.z))
	var lean := Vector3(part.get("lean_x", 0.0), 0.0, part.get("lean_z", 0.0))
	var half := Vector3(0.0, size.y * 0.5, 0.0)
	var corners := _prism_corners(maxi(int(part.get("segments", DEFAULT_SEGMENTS)),
		PRISM_FEWEST_SIDES), part.get("diamond", false))
	var low := PackedVector3Array()
	var high := PackedVector3Array()
	var tool := SurfaceTool.new()
	var centre := lean * 0.5

	for corner: Vector2 in corners:
		low.append(Vector3(corner.x * size.x, 0.0, corner.y * size.z) - half)
		high.append(Vector3(corner.x * top.x, 0.0, corner.y * top.y) + half + lean)

	tool.begin(Mesh.PRIMITIVE_TRIANGLES)

	for index in corners.size():
		var next := (index + 1) % corners.size()

		_flat_triangle(tool, low[index], low[next], high[next], centre)
		_flat_triangle(tool, low[index], high[next], high[index], centre)
		_flat_triangle(tool, -half, low[index], low[next], centre)
		_flat_triangle(tool, half + lean, high[index], high[next], centre)

	return tool.commit()


## The corners of a prism face of one unit by one unit, around the origin.
##
## A face of four or eight sides has a side toward +X and toward +Z. With
## `diamond`, it has a corner there. The corners fill the unit box in the
## two cases, so the width of a prism is the width that its part names.
static func _prism_corners(sides: int, diamond: bool) -> PackedVector2Array:
	var corners := PackedVector2Array()
	var first := 0.0 if diamond else 0.5
	var most := Vector2.ZERO

	for index in sides:
		var angle := (index + first) * TAU / sides

		corners.append(Vector2(cos(angle), sin(angle)))
		most = most.max(corners[index].abs())

	for index in sides:
		corners[index] = corners[index] / most * 0.5

	return corners


## Add one triangle with the normal of its own face. The front of a face is
## the side that looks away from `centre`, a point inside the prism. A
## triangle with no area adds nothing: a prism that ends in a point has such
## triangles.
static func _flat_triangle(tool: SurfaceTool, first: Vector3, second: Vector3,
		third: Vector3, centre: Vector3) -> void:
	var normal := (third - first).cross(second - first)

	if normal.length_squared() < PRISM_NO_AREA:
		return

	if normal.dot((first + second + third) / 3.0 - centre) < 0.0:
		var keep := second

		second = third
		third = keep
		normal = -normal

	for point: Vector3 in [first, second, third]:
		tool.set_normal(normal.normalized())
		tool.add_vertex(point)
