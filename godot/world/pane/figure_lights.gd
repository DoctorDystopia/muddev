class_name FigureLights
extends Node3D
## The real lights of the tile world: one [OmniLight3D] on each of the
## nearest few lamps, and they light the figures alone.
##
## The ground, the walls, and the props get their lamp light baked in
## ([TileLights]). A figure moves, so a bake cannot light it. This node
## stands a real light on the [constant MAX_LIGHTS] lamps nearest the
## player, on the plane of the player. Each light casts no shadow, fades
## with the distance, and has a cull mask of the entity layer only. Thus
## the ground never counts them. The Compatibility renderer lights one mesh
## with at most 8 omni lights, and [constant MAX_LIGHTS] stays under that.
##
## [method mark_entity] puts a node on the entity layer. [EntityPool] calls
## it for each figure and each item, and [WorldView] calls it for the
## avatar. A node that nobody marks gets no real light, and that is the
## ground.
##
## The lights follow the chunks ([signal WorldState.chunks_changed]) and the
## room ([signal WorldState.room_changed]), so a walk toward a lamp picks
## it up.

## How many real lights stand at one time.
const MAX_LIGHTS := 4

## The render layer of a figure, as a bit. Layer 1 is the first bit, and
## every node draws on it. The entity layer is the second.
const ENTITY_LAYER_BIT := 2

## The layers of a marked node: the first layer, so the camera and the sun
## see it as before, and the entity layer, so the lamps light it.
const ENTITY_LAYERS := 1 | ENTITY_LAYER_BIT

## Where a light starts to fade, and over how far, in world units. The fog
## of an area ends at about 30 tiles.
const FADE_BEGIN := 16.0
const FADE_LENGTH := 8.0

var _state: WorldState
var _lights: Array[OmniLight3D] = []


func _init() -> void:
	name = "FigureLights"

	for _index: int in MAX_LIGHTS:
		var light := OmniLight3D.new()

		light.shadow_enabled = false
		light.light_cull_mask = ENTITY_LAYER_BIT
		light.distance_fade_enabled = true
		light.distance_fade_begin = FADE_BEGIN
		light.distance_fade_length = FADE_LENGTH
		light.visible = false
		add_child(light)
		_lights.append(light)


## Follow the lamps of this model, now and each time they change.
func bind(state: WorldState) -> void:
	_state = state
	_state.chunks_changed.connect(refresh)
	_state.room_changed.connect(refresh)
	refresh()


## Stand the lights on the lamps nearest the player again.
func refresh() -> void:
	if _state == null or not _state.on_tile_world():
		show_lights([], Vector3.ZERO)
		return

	var cell := _state.current_cell
	var ground: Variant = _state.ground_y(cell)
	var origin := Vector3(cell.x * ChunkMeshBuilder.TILE_SIZE,
		float(ground) if ground != null else 0.0,
		-cell.y * ChunkMeshBuilder.TILE_SIZE)

	show_lights(TileLights.all_of(_state.plane_chunks(_state.current_plane)), origin)


## Stand a light on each of the [constant MAX_LIGHTS] `lamps` nearest
## `origin`, and hide the rest.
func show_lights(lamps: Array, origin: Vector3) -> void:
	var chosen := nearest(lamps, origin, MAX_LIGHTS)

	for index: int in MAX_LIGHTS:
		var light := _lights[index]

		if index >= chosen.size():
			light.visible = false
			continue

		var lamp: TileLights.Light = chosen[index]

		light.position = lamp.position
		light.light_color = lamp.color
		light.light_energy = lamp.energy
		light.omni_range = lamp.reach
		light.visible = true


## How many lights stand now. For a test.
func lit_count() -> int:
	var count := 0

	for light: OmniLight3D in _lights:
		if light.visible:
			count += 1

	return count


## The light nodes, in order. For a test.
func lights() -> Array[OmniLight3D]:
	return _lights


## The `count` entries of `lamps` nearest `origin`, nearest first.
static func nearest(lamps: Array, origin: Vector3, count: int) -> Array:
	var sorted := lamps.duplicate()

	sorted.sort_custom(func(a: TileLights.Light, b: TileLights.Light) -> bool:
		return a.position.distance_squared_to(origin) < b.position.distance_squared_to(origin))

	return sorted.slice(0, count)


## Put `node` and every visual instance under it on the entity layer, so
## the lamps light it.
static func mark_entity(node: Node) -> void:
	if node is VisualInstance3D:
		(node as VisualInstance3D).layers = ENTITY_LAYERS

	for child: Node in node.get_children():
		mark_entity(child)
