extends Node
## Unit tests for EntityPool — that what the server says an entity IS becomes
## the right mesh, and that a hit flash reaches all of it.
##
##     godot --headless --path godot res://tests/test_entity_pool.tscn
##
## Needs nothing running. The resolver is built with an EMPTY registry, so every
## resolve falls to tier 2 and no HTTP happens — which is exactly the state the
## real client is in before the manifest lands, and the state every entity
## without art stays in forever.

var _failures := 0
var _pool: EntityPool
var _resolver: MeshResolver

## Payloads in the shape `serialize_entity` produces, floats and all —
## `coords` included, because with STATEFEED_ENTITY_RADIUS at 10 the feed names
## entities across a 441-room neighbourhood and every one carries its own.
const HERE := [7.0, 1.0, "oasis"]
const NEXT_DOOR := [8.0, 1.0, "oasis"]
const FAR_MAP := [3.0, 3.0, "somewhere_unplaced"]

const RAIDER := {"id": 20743.0, "name": "mutant raider", "kind": "npc",
	"asset": "generic", "family": "npc", "interact": "attack mutant raider",
	"coords": HERE}
const SWORD := {"id": 20744.0, "name": "rusty scrap shortsword", "kind": "item",
	"asset": "rusty_scrap_shortsword", "family": "weapon", "interact": "get sword",
	"coords": HERE}
const ODDITY := {"id": 20745.0, "name": "a thing", "kind": "item",
	"asset": "generic", "family": "no_such_family", "interact": "",
	"coords": HERE}

## One room over, and one on a map the client has not drawn yet.
const NEIGHBOUR := {"id": 20746.0, "name": "distant raider", "kind": "npc",
	"asset": "generic", "family": "npc", "interact": "attack distant raider",
	"coords": NEXT_DOOR}
const UNPLACEABLE := {"id": 20747.0, "name": "elsewhere", "kind": "npc",
	"asset": "generic", "family": "npc", "interact": "", "coords": FAR_MAP}

## Stands in for the world pane's placement. Knows two tiles and nothing else,
## which is what makes "not placeable yet" testable.
## A `var` and not a `const`: `str()` is a function call, and a GDScript
## constant must be a constant expression.
var _tile_positions := {
	str(HERE): Vector3(0.0, 0.0, 0.0),
	str(NEXT_DOOR): Vector3(1.18, 0.0, 0.0),
}


func _locate(coords: Array) -> Variant:
	return _tile_positions.get(str(coords))


func _ready() -> void:
	_resolver = MeshResolver.new(ModelRegistry.new(), "")
	add_child(_resolver)

	_pool = EntityPool.new()
	add_child(_pool)
	_pool.bind(_resolver, _locate)

	_the_pool_was_actually_wired()
	_entities_stand_on_their_own_tiles()
	_an_unplaceable_entity_is_drawn_nowhere()
	_every_entity_becomes_a_mesh()
	_the_family_decides_the_shape()
	_an_unknown_family_still_draws()
	_entities_can_be_added_and_removed()
	_a_flash_reaches_every_material()
	_a_flash_on_nothing_is_harmless()
	_hover_lights_one_entity_at_a_time()
	_hover_does_not_survive_a_rebuild()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: entity_pool")
	get_tree().quit(0)


## The vacuity guard. Every check below counts children of the pool; if binding
## or building silently produced nothing, they would all pass over an empty ring.
func _the_pool_was_actually_wired() -> void:
	_pool.replace_all([RAIDER])

	_expect(_pool.get_child_count() == 1,
		"one entity produces one node; if this fails every check below is inert")


## The bug this replaced: every entity was ringed around the OBSERVER, so a
## radius-10 feed stacked a 441-room neighbourhood onto one tile.
func _entities_stand_on_their_own_tiles() -> void:
	_pool.replace_all([RAIDER, NEIGHBOUR])

	var here := _node_for(20743)
	var over_there := _node_for(20746)

	_expect(here != null and over_there != null, "both entities are drawn")

	if here == null or over_there == null:
		return

	# Each within its own tile's ring, and the two tiles are 1.18 apart -- so
	# any confusion between them shows up as a distance far under that.
	_expect(here.position.distance_to(_tile_positions[str(HERE)]) < 0.5,
		"the near one stands on its own tile")
	_expect(over_there.position.distance_to(_tile_positions[str(NEXT_DOOR)]) < 0.5,
		"and the far one stands on ITS own tile, not on the observer")
	_expect(here.position.distance_to(over_there.position) > 0.5,
		"so two entities in different rooms are not in the same place")


## Its map has not been drawn, so there is no honest position for it. Drawing it
## anyway is what put the whole neighbourhood on one tile.
func _an_unplaceable_entity_is_drawn_nowhere() -> void:
	_pool.replace_all([RAIDER, UNPLACEABLE])

	_expect(_pool.get_child_count() == 1,
		"an entity whose map has not arrived is not drawn")

	# Still KNOWN, though -- only undrawn. The relayout that places its island
	# calls back and it appears without the feed resending anything.
	_expect(not _pool.entity(20747).is_empty(),
		"but it is still remembered, ready for when the island arrives")

	_pool.replace_all([RAIDER])


func _every_entity_becomes_a_mesh() -> void:
	_pool.replace_all([RAIDER, SWORD, ODDITY])

	_expect(_pool.get_child_count() == 3, "three entities, three nodes")

	for child: Node in _pool.get_children():
		var node := child as Node3D

		_expect(node != null, "every entity is a Node3D")
		_expect(_mesh_count(node) > 0,
			"every entity carries at least one mesh, so it can be seen and hit")


## The server sends `family` precisely so the client does not have to decide
## this. An npc should be the figure, a weapon the blade -- and neither should be
## the sphere they both used to be.
func _the_family_decides_the_shape() -> void:
	_pool.replace_all([RAIDER])
	var npc_node := _pool.get_child(0) as Node3D
	var npc_parts := _mesh_count(npc_node)
	var npc_shapes := _shapes_of(npc_node)

	_pool.replace_all([SWORD])
	var weapon_node := _pool.get_child(0) as Node3D
	var weapon_parts := _mesh_count(weapon_node)
	var weapon_shapes := _shapes_of(weapon_node)

	_expect(npc_parts == FamilyShapes.parts_for("npc").size(),
		"an npc is drawn as the figure (%d parts)" % npc_parts)
	_expect(weapon_parts == FamilyShapes.parts_for("weapon").size(),
		"a weapon is drawn as the blade (%d parts)" % weapon_parts)

	# Compared by PRIMITIVE and not by part count: both families happen to have
	# three parts, so a count proves only that something was built. The figure is
	# a sphere on two cylinders and the blade is two boxes on one, which is the
	# difference a player actually sees -- and the difference that did not exist
	# when both were a coloured sphere.
	_expect(npc_shapes != weapon_shapes,
		"and they are built from different primitives (%s vs %s)"
		% [npc_shapes, weapon_shapes])


func _an_unknown_family_still_draws() -> void:
	_pool.replace_all([ODDITY])

	var node := _pool.get_child(0) as Node3D

	_expect(_mesh_count(node) == FamilyShapes.GENERIC.size(),
		"a family this client has never heard of gets the generic block")


func _entities_can_be_added_and_removed() -> void:
	_pool.replace_all([RAIDER])
	_pool.add(SWORD)

	_expect(_pool.get_child_count() == 2, "add puts a second entity in the ring")
	_expect(not _pool.entity(20744).is_empty(), "and it can be looked up by id")

	_pool.remove(20744)

	_expect(_pool.get_child_count() == 1, "remove takes it away again")
	_expect(_pool.entity(20744).is_empty(), "and it is no longer known")

	# Ids arrive as floats and become dictionary keys; a key of 20743.0 never
	# matches one written as 20743, and nothing raises when it does not.
	_expect(not _pool.entity(20743).is_empty(),
		"an id parsed from a float still looks up as an int")


## A three-part figure with one white head would be worse than no flash at all.
func _a_flash_reaches_every_material() -> void:
	_pool.replace_all([RAIDER])

	var node := _pool.get_child(0) as Node3D
	var materials := _materials_of(node)

	_expect(materials.size() > 1,
		"the figure has several materials, so this is worth checking")

	var before: Array = []

	for material: StandardMaterial3D in materials:
		before.append(material.albedo_color)

	_pool.flash(20743)

	var flashed := 0

	for index: int in materials.size():
		if materials[index].albedo_color == Color.WHITE:
			flashed += 1

	_expect(flashed == materials.size(),
		"every material flashes, not just the root's (%d of %d)"
		% [flashed, materials.size()])
	_expect(before.any(func(c: Color): return c != Color.WHITE),
		"and they were not white to begin with")


func _a_flash_on_nothing_is_harmless() -> void:
	_pool.replace_all([RAIDER])
	_pool.flash(999999)

	_expect(true, "flashing an id that is not present does not raise")


## Hover uses emission and the flash uses albedo, so neither can clobber the
## other. Checked on emission specifically for that reason.
func _hover_lights_one_entity_at_a_time() -> void:
	_pool.replace_all([RAIDER, SWORD])
	_pool.hover(20743)

	_expect(_is_lit(_node_for(20743)), "the hovered entity lights up")
	_expect(not _is_lit(_node_for(20744)), "and the other one does not")

	_pool.hover(20744)

	_expect(not _is_lit(_node_for(20743)), "moving the cursor puts the first back")
	_expect(_is_lit(_node_for(20744)), "and lights the second")

	_pool.hover(0)

	_expect(not _is_lit(_node_for(20744)), "leaving everything clears the glow")


## A stale hovered id would make the new node never light up -- and the ring is
## rebuilt on every change to the room, which is most of the time.
func _hover_does_not_survive_a_rebuild() -> void:
	_pool.replace_all([RAIDER])
	_pool.hover(20743)
	_pool.replace_all([RAIDER])

	_expect(not _is_lit(_node_for(20743)), "the rebuilt entity starts unlit")

	_pool.hover(20743)

	_expect(_is_lit(_node_for(20743)), "and can be lit again afterwards")


## The node the pool drew for one entity id.
##
## Straight through the pool's own accessor. This used to infer the node from
## BUILD ORDER, which stopped being meaningful the moment entities were grouped
## by tile -- the ring is per tile now, not one list.
func _node_for(entity_id: int) -> Node3D:
	return _pool.node_for(entity_id)


func _is_lit(node: Node3D) -> bool:
	if node == null:
		return false

	for material: StandardMaterial3D in _materials_of(node):
		if material.emission_enabled:
			return true

	return false


## The primitive class of every mesh under a node, sorted.
##
## Sorted because the ring's build order is not a promise; what is being
## compared is which SHAPES a family is made of, not the order they were added.
func _shapes_of(root: Node3D) -> Array:
	var found: Array = []
	var stack: Array[Node] = [root]

	while not stack.is_empty():
		var node: Node = stack.pop_back()
		var instance := node as MeshInstance3D

		if instance != null and instance.mesh != null:
			found.append(instance.mesh.get_class())

		for child: Node in node.get_children():
			stack.append(child)

	found.sort()

	return found


func _mesh_count(root: Node3D) -> int:
	var found := 0
	var stack: Array[Node] = [root]

	while not stack.is_empty():
		var node: Node = stack.pop_back()

		if node is MeshInstance3D:
			found += 1

		for child: Node in node.get_children():
			stack.append(child)

	return found


func _materials_of(root: Node3D) -> Array:
	var found: Array = []
	var stack: Array[Node] = [root]

	while not stack.is_empty():
		var node: Node = stack.pop_back()
		var instance := node as MeshInstance3D

		if instance != null and instance.material_override != null:
			found.append(instance.material_override)

		for child: Node in node.get_children():
			stack.append(child)

	return found


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
