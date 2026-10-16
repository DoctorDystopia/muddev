@tool
class_name FigurePicking
extends RefCounted
## Finds the part of a figure below the mouse (DESIGN-0014 section 12.4).
##
## A click in the 3D view of the editor does not select a node with no
## owner, and each part of a figure is such a node. Thus, the plugin sends
## the ray of the mouse to [method pick], and it selects the result by code.
## The Godot move, turn, and scale tools then work on the part.
##
## The test is on the triangles of each shape, not on its box. The box of an
## arm in a T-pose covers the chest, so a box test picks the wrong part.


## The part node of `parts` that the ray meets first, or null. Each part
## must be in the tree.
static func pick(parts: Array[Node3D], origin: Vector3, direction: Vector3) -> Node3D:
	var nearest: Node3D = null
	var nearest_distance := INF

	for part: Node3D in parts:
		for child: Node in part.get_children():
			var instance := child as MeshInstance3D

			if instance == null or instance.mesh == null or not instance.visible:
				continue

			var distance := _hit_distance(instance, origin, direction)

			if distance < nearest_distance:
				nearest_distance = distance
				nearest = part

	return nearest


## The distance from `origin` to the first triangle of one mesh on the ray,
## or INF for no hit.
static func _hit_distance(instance: MeshInstance3D, origin: Vector3,
		direction: Vector3) -> float:
	var to_local := instance.global_transform.affine_inverse()
	var local_origin := to_local * origin
	var local_direction := (to_local.basis * direction).normalized()
	var triangles := instance.mesh.generate_triangle_mesh()

	if triangles == null:
		return INF

	var hit := triangles.intersect_ray(local_origin, local_direction)

	if hit.is_empty():
		return INF

	var point: Vector3 = instance.global_transform * hit["position"]

	return origin.distance_to(point)
