extends Node
## Unit tests for EntityPicking: the ray against the faces and the box of
## one node.
##
##     godot --headless --path godot res://tests/test_entity_picking.tscn
##
## Needs nothing running. The node is a thin slab in a unit box, so a ray
## can enter the box and miss the slab. The node is moved, scaled and
## turned, because the ray must follow the look of a chunk object.

## The slab fills the unit box in Y and a fifth of it in X and Z.
const SLAB := Vector3(0.2, 1.0, 0.2)
const UNIT_BOX := AABB(Vector3(-0.5, -0.5, -0.5), Vector3.ONE)

## Where the node stands, and how much the look scaled it.
const STAND := Vector3(2.0, 0.0, 0.0)
const SCALE := 2.0

## The ray starts this far up and points down.
const HEIGHT := 5.0
const DOWN := Vector3.DOWN

## A point inside the scaled box and outside the slab, from the node.
const CORNER := Vector3(0.8, 0.0, 0.8)

## How close two distances must be.
const CLOSE := 0.001

var _failures := 0
var _root: Node3D
var _slab: MeshInstance3D


func _ready() -> void:
	_root = Node3D.new()
	_slab = MeshInstance3D.new()

	var mesh := BoxMesh.new()
	mesh.size = SLAB
	_slab.mesh = mesh
	_root.add_child(_slab)
	add_child(_root)
	_root.position = STAND
	_root.scale = Vector3.ONE * SCALE

	_the_faces_of_a_box_are_twelve_triangles()
	_a_ray_through_the_slab_meets_its_top()
	_the_distance_is_a_world_distance()
	_a_ray_in_the_box_beside_the_slab_meets_the_box_alone()
	_a_ray_beside_the_box_meets_nothing()
	_a_hidden_mesh_has_no_surface()
	_a_turned_node_turns_its_faces()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: entity_picking")
	get_tree().quit(0)


func _the_faces_of_a_box_are_twelve_triangles() -> void:
	var faces := EntityPicking.faces_of(_root)

	_expect(faces.size() == 1, "one mesh gives one entry")

	if faces.is_empty():
		return

	var entry: Array = faces[0]

	_expect(entry[0] == _slab, "the entry names the instance that draws it")
	_expect((entry[1] as PackedVector3Array).size() == 36,
		"a box is twelve triangles of three vertices")


## The top of the slab is half its height times the scale above the stand.
func _a_ray_through_the_slab_meets_its_top() -> void:
	var origin := STAND + Vector3.UP * HEIGHT
	var faces := EntityPicking.faces_of(_root)
	var top := SLAB.y * 0.5 * SCALE
	var distance := EntityPicking.surface_distance(faces, origin, DOWN)

	_expect(absf(distance - (HEIGHT - top)) < CLOSE,
		"the ray meets the top of the slab at %.3f, got %.3f" % [HEIGHT - top, distance])

	var boxed := EntityPicking.box_distance(_root, UNIT_BOX, origin, DOWN)

	_expect(absf(boxed - (HEIGHT - 0.5 * SCALE)) < CLOSE,
		"the box begins at its top, got %.3f" % boxed)


## A longer direction vector gives the same distance. The pool gives a unit
## ray, but the move into the space of a scaled node stretches it.
func _the_distance_is_a_world_distance() -> void:
	var origin := STAND + Vector3.UP * HEIGHT
	var faces := EntityPicking.faces_of(_root)
	var unit := EntityPicking.surface_distance(faces, origin, DOWN)
	var long := EntityPicking.surface_distance(faces, origin, DOWN * 3.0)

	_expect(absf(unit - long) < CLOSE, "the length of the direction changes nothing")


## The reason the box is a broad phase and not the answer.
func _a_ray_in_the_box_beside_the_slab_meets_the_box_alone() -> void:
	var origin := STAND + CORNER + Vector3.UP * HEIGHT
	var faces := EntityPicking.faces_of(_root)

	_expect(EntityPicking.surface_distance(faces, origin, DOWN) == EntityPicking.MISS,
		"the ray misses every face of the slab")
	_expect(EntityPicking.box_distance(_root, UNIT_BOX, origin, DOWN) != EntityPicking.MISS,
		"and still enters the box")


func _a_ray_beside_the_box_meets_nothing() -> void:
	var origin := STAND + Vector3(SCALE, HEIGHT, SCALE)
	var faces := EntityPicking.faces_of(_root)

	_expect(EntityPicking.surface_distance(faces, origin, DOWN) == EntityPicking.MISS,
		"no face past the box")
	_expect(EntityPicking.box_distance(_root, UNIT_BOX, origin, DOWN) == EntityPicking.MISS,
		"no box past the box")


## A figure hides the hair under a helmet. A click on the helmet must not
## reach the hair.
func _a_hidden_mesh_has_no_surface() -> void:
	var origin := STAND + Vector3.UP * HEIGHT
	var faces := EntityPicking.faces_of(_root)

	_slab.visible = false

	_expect(EntityPicking.surface_distance(faces, origin, DOWN) == EntityPicking.MISS,
		"a hidden mesh gives no face")
	_expect(EntityPicking.box_distance(_root, UNIT_BOX, origin, DOWN) != EntityPicking.MISS,
		"the box of the node still counts")

	_slab.visible = true


## A tilt of the look turns the node. The slab laid on its side runs along
## Z, and a ray that missed it standing up meets it.
func _a_turned_node_turns_its_faces() -> void:
	var beside := STAND + Vector3(0.0, HEIGHT, CORNER.z)
	var faces := EntityPicking.faces_of(_root)

	_expect(EntityPicking.surface_distance(faces, beside, DOWN) == EntityPicking.MISS,
		"standing up, the slab is not beside itself")

	_root.rotation.x = PI * 0.5

	var distance := EntityPicking.surface_distance(faces, beside, DOWN)
	var top := SLAB.z * 0.5 * SCALE

	_expect(absf(distance - (HEIGHT - top)) < CLOSE,
		"laid down, the slab reaches the point at %.3f, got %.3f" % [HEIGHT - top, distance])

	_root.rotation.x = 0.0


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
