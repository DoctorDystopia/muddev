class_name EntityPicking
## The ray test of one drawn entity: its surface, then its box.
##
## Purpose: give [method EntityPool.pick] the two ray tiers. The box of a
## node is the broad phase. A ray that misses the box of a node cannot meet
## its surface, so the pool tests the faces of a node only when the ray
## enters its box. The faces decide between two models that overlap: the
## one whose face the ray meets first is the one that the player sees
## under the cursor. A box alone cannot decide that. The box of a figure
## in front covers a visible part of the figure behind it.
##
## No collision body. A body for each entity is a second copy of each
## model, and the copy goes stale on each redraw. The faces come from the
## meshes that the pool draws, so the clickable area is the drawn area.
##
## A ray is an origin and a direction. Each test moves the ray into the
## space of the node, because a look scales and tilts a node
## (10/16/2026). The direction is not a unit vector after that move. Both
## Godot tests accept that. The distance is the parameter of the hit along
## the ray, and the move keeps that parameter. Each test makes the world
## direction a unit vector first, so the parameter is the world distance,
## and a scale cannot stretch it. See [method _along].
##
## Author: Nick Hobar. Date: 10/20/2026.

## The answer for a ray that meets nothing. A distance is never negative.
const MISS := -1.0

## The vertices of one triangle in the face list of a mesh.
const TRIANGLE := 3


## The faces of every mesh under a node, each with the instance that draws
## it, as `[[MeshInstance3D, PackedVector3Array], ...]`.
##
## Built one time for each node. `Mesh.get_faces` copies every vertex, and
## a served model carries thousands. A mesh with no faces is left out.
static func faces_of(root: Node3D) -> Array:
	var found: Array = []
	var stack: Array[Node] = [root]

	while not stack.is_empty():
		var node: Node = stack.pop_back()
		var instance := node as MeshInstance3D

		if instance != null and instance.mesh != null:
			var faces := instance.mesh.get_faces()

			if not faces.is_empty():
				found.append([instance, faces])

		for child: Node in node.get_children():
			stack.append(child)

	return found


## How far along the ray the box of `node` begins, or [constant MISS].
##
## `box` is in the space of the node, as [method ModelLoader.bounds_of]
## gives it. A ray that starts inside the box begins at distance zero.
static func box_distance(node: Node3D, box: AABB, origin: Vector3,
		direction: Vector3) -> float:
	var to_node := node.global_transform.affine_inverse()
	var from := to_node * origin
	var heading := to_node.basis * direction.normalized()
	var hit: Variant = box.intersects_ray(from, heading)

	if hit == null:
		return MISS

	return _along(hit, from, heading)


## How far along the ray the nearest face of a node is, or [constant MISS].
##
## `faces` comes from [method faces_of]. A hidden instance does not count.
## A figure hides the hair under a helmet, and a click on the helmet must
## not reach the hair. The nearest face of every mesh counts, so a ray
## that enters at the back of a model still gives its front.
static func surface_distance(faces: Array, origin: Vector3,
		direction: Vector3) -> float:
	var nearest := MISS

	for entry: Array in faces:
		var instance: MeshInstance3D = entry[0]

		if not instance.is_visible_in_tree():
			continue

		var found := _mesh_distance(instance, entry[1], origin, direction)

		if found != MISS and (nearest == MISS or found < nearest):
			nearest = found

	return nearest


## The nearest face of one mesh along the ray, or [constant MISS].
##
## Both sides of a face count. A model that shows its back faces is rare,
## and a one-sided test lets a click fall through a face that the player
## sees.
static func _mesh_distance(instance: MeshInstance3D, faces: PackedVector3Array,
		origin: Vector3, direction: Vector3) -> float:
	var to_mesh := instance.global_transform.affine_inverse()
	var from := to_mesh * origin
	var heading := to_mesh.basis * direction.normalized()
	var nearest := MISS
	var last := faces.size() - TRIANGLE
	var index := 0

	while index <= last:
		var hit: Variant = Geometry3D.ray_intersects_triangle(from, heading,
			faces[index], faces[index + 1], faces[index + 2])

		index += TRIANGLE

		if hit == null:
			continue

		var distance := _along(hit, from, heading)

		if nearest == MISS or distance < nearest:
			nearest = distance

	return nearest


## How far along the ray a hit point is, as the parameter of the ray.
##
## In the space of the node, not the world. A read of `global_transform`
## for each hit costs about 1.6 ms (measured 10/20/2026, Godot 4.7.2). A
## ray through the pole of a sphere meets 256 triangles there, and that
## read made the test 400 ms. The parameter needs no read, and it is the
## same in both spaces.
static func _along(hit: Vector3, from: Vector3, heading: Vector3) -> float:
	return (hit - from).dot(heading) / heading.length_squared()
