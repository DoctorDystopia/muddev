class_name EntityPool
extends Node3D
## The things standing in the room you are standing in.
##
## Only your own room, ever. STATEFEED_ENTITY_RADIUS is 0 server-side, so the
## feed reports exactly what the text channel reports and a graphical client
## cannot see an NPC through a wall. Raising it is a balance change, not a
## rendering one.
##
## Entities are rebuilt wholesale on every change rather than pooled. There are
## rarely more than a handful in a room, the ring position of each depends on
## how many there are, and the browser pane does the same -- pooling would be
## machinery bought with nothing.

const ENTITY_RADIUS := 0.26     # ring radius within one tile
const ENTITY_SIZE := 0.13
const ENTITY_LIFT := 0.22       # above the tile's top face
const JITTER_SHARE := 0.35      # how far a slot may drift from its even share
const HIT_FLASH_SECONDS := 0.32

const COLOR_NPC := Color("ff5f56")
const COLOR_CHARACTER := Color("7fb3ff")
const COLOR_ITEM := Color("f0c674")
const COLOR_HIT_FLASH := Color.WHITE

const _META_BASE_COLOUR := "base_colour"

var _anchor := Vector3.ZERO
var _entities: Array[Dictionary] = []
var _nodes: Dictionary = {}     # int id -> MeshInstance3D
var _mesh: SphereMesh


func _ready() -> void:
	_mesh = SphereMesh.new()
	_mesh.radius = ENTITY_SIZE
	_mesh.height = ENTITY_SIZE * 2.0


## Move the whole ring to a new tile. Call when the observer's room changes.
func set_anchor(tile_top: Vector3) -> void:
	_anchor = tile_top
	_rebuild()


## Replace everything visible. `room_players` is the full list, sent on arrival
## and on resync; the add/remove channels carry the deltas in between.
func replace_all(entities: Array) -> void:
	_entities.clear()

	for entity: Dictionary in entities:
		_entities.append(entity)

	_rebuild()


func add(entity: Dictionary) -> void:
	if entity.is_empty():
		return

	_entities.append(entity)
	_rebuild()


func remove(entity_id: int) -> void:
	for index: int in _entities.size():
		if _id_of(_entities[index]) == entity_id:
			_entities.remove_at(index)
			_rebuild()
			return


## The entity nearest a point on screen, or 0 for nothing within reach.
##
## Screen-space rather than a physics raycast: there are no collision bodies in
## this scene and adding them would mean a second representation of every
## entity to keep in step. Picking by cursor distance also does the more
## obliging thing when two entities overlap -- it takes whichever LOOKS closest
## to the cursor.
##
## Zero is a safe "nothing" because Evennia object ids start at 1.
func pick(camera: Camera3D, screen_point: Vector2, reach: float) -> int:
	var nearest := reach
	var found := 0

	for entity_id: int in _nodes:
		var node: MeshInstance3D = _nodes[entity_id]

		if camera.is_position_behind(node.global_position):
			continue

		var distance := camera.unproject_position(node.global_position).distance_to(screen_point)

		if distance < nearest:
			nearest = distance
			found = entity_id

	return found


## The payload an id was built from, or an empty dictionary.
func entity(entity_id: int) -> Dictionary:
	for candidate: Dictionary in _entities:
		if _id_of(candidate) == entity_id:
			return candidate

	return {}


## Flash one entity white and fade it back. Called on a landed swing.
func flash(entity_id: int) -> void:
	var node: MeshInstance3D = _nodes.get(entity_id)

	if node == null:
		return

	var material: StandardMaterial3D = node.material_override
	var base: Color = material.get_meta(_META_BASE_COLOUR)

	material.albedo_color = COLOR_HIT_FLASH

	# Must finish inside the 0.6s server tick, so the world is never mid-tween
	# when the next state arrives.
	var tween := create_tween()

	tween.tween_property(material, "albedo_color", base, HIT_FLASH_SECONDS)


# ─── Private helpers ─────────────────────────────────────────────────────────

func _rebuild() -> void:
	for child: Node in get_children():
		remove_child(child)
		child.queue_free()

	_nodes.clear()

	for index: int in _entities.size():
		var entity: Dictionary = _entities[index]
		var node := _build(entity)

		node.position = _slot_position(_id_of(entity), index, _entities.size())
		add_child(node)
		_nodes[_id_of(entity)] = node


func _build(entity: Dictionary) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	var material := StandardMaterial3D.new()
	var colour := _colour_of(entity)

	material.albedo_color = colour
	material.set_meta(_META_BASE_COLOUR, colour)

	node.mesh = _mesh
	node.material_override = material

	return node


## Even slots around the ring, nudged by a hash of the id.
##
## The nudge exists so two rooms holding the same number of things do not
## produce identical rings. It is deliberately smaller than one slot, so the
## slot ORDER -- which is what makes an entity stay put between frames -- still
## comes from the index.
func _slot_position(entity_id: int, index: int, total: int) -> Vector3:
	var spread := maxi(total, 1)
	var jitter := float(WorldView.stable_hash(str(entity_id)) % 100) / 100.0
	var angle := (float(index) + jitter * JITTER_SHARE) / float(spread) * TAU

	return _anchor + Vector3(
		cos(angle) * ENTITY_RADIUS,
		ENTITY_LIFT,
		sin(angle) * ENTITY_RADIUS
	)


func _colour_of(entity: Dictionary) -> Color:
	match str(entity.get("kind", "")):
		"npc":
			return COLOR_NPC
		"character":
			return COLOR_CHARACTER

	return COLOR_ITEM


## Entity ids arrive as floats, like every other number Godot parses out of
## JSON. Converted here, at the point of use, because this is where they become
## dictionary keys -- and a key of 20743.0 never matches one written as 20743.
func _id_of(entity: Dictionary) -> int:
	return int(entity.get("id", 0))
