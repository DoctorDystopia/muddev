extends Node
## Unit tests for [TileLights], [LightLook], and [FigureLights]: a lamp bakes
## into the ground, the walls, and the props around it, and the nearest
## lamps get a real light for the figures.
##
##     godot --headless --path godot res://tests/test_tile_lights.tscn
##
## Needs nothing running. Headless draws nothing, so each case reads the
## lamp array of a built mesh, which is the whole output of the bake.

const _Const := preload("res://autoload/blackout_constants.gd")

## The tile of the lamp in most cases, in chunk (0, 0).
const _LAMP_TILE := Vector2i(10, 10)

## A tile far from the lamp, out of its reach.
const _FAR_TILE := Vector2i(40, 40)

## A tile with a wall, two tiles north of the lamp.
const _WALL_TILE := Vector2i(10, 12)

## How close two floats must be to count as equal.
const _NEAR := 0.001

var _failures := 0


func _ready() -> void:
	_the_lamp_post_gives_light_and_a_crate_does_not()
	_a_lamp_lights_the_ground_near_it_and_not_far_from_it()
	_a_lamp_in_a_neighbour_chunk_reaches_across_the_edge()
	_the_signature_follows_the_lamps()
	_the_lamp_of_a_lamp_post_glows()
	_a_wall_face_toward_the_lamp_is_brighter_than_the_face_away()
	_a_look_file_row_wins_over_the_fallback()
	_an_energy_of_zero_turns_a_light_off()
	_every_mesh_carries_one_lamp_colour_for_each_vertex()
	_the_figure_lights_stand_on_the_nearest_lamps()
	_a_marked_node_is_on_the_entity_layer()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: tile_lights")
	get_tree().quit(0)


# ─── Cases ───────────────────────────────────────────────────────────────────

func _the_lamp_post_gives_light_and_a_crate_does_not() -> void:
	_expect(LightLook.gives_light(_Const.SCENERY_LAMP_POST), "a lamp post gives light")
	_expect(LightLook.gives_light(_Const.SCENERY_OIL_LAMP), "an oil lamp gives light")
	_expect(LightLook.gives_light(_Const.SCENERY_TORCH), "a torch gives light")
	_expect(not LightLook.gives_light(_Const.SCENERY_CRATE), "a crate gives no light")

	for scenery: String in [_Const.SCENERY_OIL_LAMP, _Const.SCENERY_TORCH]:
		var chunk := _chunk_with(scenery, _LAMP_TILE)
		var lights := TileLights.lights_of(chunk)
		var glow := _brightest(PropMeshBuilder.build(chunk, lights).surface_get_arrays(0))

		_expect(lights.size() == 1, "a %s is one lamp" % scenery)
		_expect(glow.r > 0.0, "the %s glows" % scenery)
		_expect(lights[0].position.y < lights.size() * LightLook.HEIGHT_MAX,
			"the bulb of a %s stands at a height" % scenery)
	_expect(not LightLook.gives_light("no_such_scenery"), "an unknown key gives no light")

	var lit := _chunk_with(_Const.SCENERY_LAMP_POST, _LAMP_TILE)
	var dark := _chunk_with(_Const.SCENERY_CRATE, _LAMP_TILE)

	_expect(TileLights.lights_of(lit).size() == 1, "a lamp post is one lamp")
	_expect(TileLights.lights_of(dark).is_empty(), "a crate is no lamp")


func _a_lamp_lights_the_ground_near_it_and_not_far_from_it() -> void:
	var chunk := _chunk_with(_Const.SCENERY_LAMP_POST, _LAMP_TILE)
	var lights := TileLights.collect(_set_of([chunk]), Vector2i.ZERO)
	var arrays := ChunkMeshBuilder.build_arrays(chunk, lights)
	var near := TerrainMaterial.lamp_at(arrays, _vertex_nearest(arrays, _centre(_LAMP_TILE)))
	var far := TerrainMaterial.lamp_at(arrays, _vertex_nearest(arrays, _centre(_FAR_TILE)))

	_expect(lights.size() == 1, "the chunk collects its own lamp")
	_expect(near.r > 0.0 and near.g > 0.0, "the ground under the lamp is lit")
	_expect(far.r == 0.0 and far.g == 0.0 and far.b == 0.0,
		"the ground out of reach is dark")

	var dark := ChunkMeshBuilder.build_arrays(chunk, [])
	var unlit := TerrainMaterial.lamp_at(dark, _vertex_nearest(dark, _centre(_LAMP_TILE)))

	_expect(unlit.r == 0.0, "a build with no lamp bakes nothing")


func _a_lamp_in_a_neighbour_chunk_reaches_across_the_edge() -> void:
	var edge := Vector2i(_Const.CHUNK_SIZE - 1, 10)
	var west := _chunk_with(_Const.SCENERY_LAMP_POST, edge)
	var east := ChunkFile.blank(1, 0)
	var chunks := _set_of([west, east])
	var lights := TileLights.collect(chunks, Vector2i(1, 0))

	_expect(lights.size() == 1, "the east chunk collects the lamp of the west chunk")

	var arrays := ChunkMeshBuilder.build_arrays(east, lights)
	var first := _vertex_nearest(arrays, Vector3(_Const.CHUNK_SIZE, 0.0, -10.0))

	_expect(TerrainMaterial.lamp_at(arrays, first).r > 0.0,
		"the ground past the chunk edge is lit")

	var far_chunk := ChunkFile.blank(3, 0)

	chunks.add(far_chunk)
	_expect(TileLights.collect(chunks, Vector2i(3, 0)).is_empty(),
		"a chunk out of reach collects nothing")


func _the_signature_follows_the_lamps() -> void:
	var chunk := _chunk_with(_Const.SCENERY_LAMP_POST, _LAMP_TILE)
	var one := TileLights.lights_of(chunk)

	chunk.objects.append(_thing(_Const.SCENERY_LAMP_POST, _FAR_TILE))

	var two := TileLights.lights_of(chunk)
	var swapped := [two[1], two[0]]

	_expect(TileLights.signature([]).is_empty(), "no lamp is an empty signature")
	_expect(TileLights.signature(one) != TileLights.signature(two),
		"a new lamp changes the signature")
	_expect(TileLights.signature(two) == TileLights.signature(swapped),
		"the order of the lamps does not change the signature")


func _the_lamp_of_a_lamp_post_glows() -> void:
	var chunk := _chunk_with(_Const.SCENERY_LAMP_POST, _LAMP_TILE)
	var lights := TileLights.lights_of(chunk)
	var arrays := PropMeshBuilder.build(chunk, lights).surface_get_arrays(0)
	var glow := _brightest(arrays)
	var expected := LightLook.glow_of(LightLook.light_of(_Const.SCENERY_LAMP_POST))
	var base := _brightest(PropMeshBuilder.build(chunk, []).surface_get_arrays(0))

	_expect(glow.r >= expected.r - _NEAR and glow.g >= expected.g - _NEAR,
		"the lamp glows with at least the light of its row")
	_expect(base.r >= expected.r - _NEAR, "the lamp glows with no lamp in reach too")

	var crate := _chunk_with(_Const.SCENERY_CRATE, _LAMP_TILE)
	var dark := PropMeshBuilder.build(crate, []).surface_get_arrays(0)

	_expect(_all_dark(dark), "a crate with no lamp near it glows nowhere")


func _a_wall_face_toward_the_lamp_is_brighter_than_the_face_away() -> void:
	var chunk := _chunk_with(_Const.SCENERY_LAMP_POST, _LAMP_TILE)
	var index := _WALL_TILE.y * _Const.CHUNK_SIZE + _WALL_TILE.x

	chunk.flags[index] = chunk.flags[index] | _Const.TILE_FLAG_WALL_NORTH

	var lights := TileLights.lights_of(chunk)
	var arrays := WallMeshBuilder.build(chunk, null, false, lights).surface_get_arrays(0)
	var toward := _mean_lamp(arrays, Vector3.BACK)
	var away := _mean_lamp(arrays, Vector3.FORWARD)

	_expect(toward > 0.0, "the face toward the lamp is lit")
	_expect(away < _NEAR, "the face away from the lamp is dark")


func _a_look_file_row_wins_over_the_fallback() -> void:
	var red := "ff0000"

	LookFile.put(LightLook.PATH, {"format": LookFile.FORMAT, LightLook.KEY_LIGHTS: {
		_Const.SCENERY_LAMP_POST: {LightLook.FIELD_COLOR: red, LightLook.FIELD_ENERGY: 2.0,
			LightLook.FIELD_RANGE: 3.0, LightLook.FIELD_HEIGHT: 1.0}}})

	var light := LightLook.light_of(_Const.SCENERY_LAMP_POST)

	_expect(light[LightLook.FIELD_COLOR] == Color.html(red), "the file gives the colour")
	_expect(is_equal_approx(light[LightLook.FIELD_ENERGY], 2.0), "the file gives the energy")
	_expect(LightLook.has_file_row(_Const.SCENERY_LAMP_POST), "the key has a file row")

	LookFile.put(LightLook.PATH, {"format": LookFile.FORMAT, LightLook.KEY_LIGHTS: {
		_Const.SCENERY_LAMP_POST: {LightLook.FIELD_COLOR: "not a colour"}}})

	var patched := LightLook.light_of(_Const.SCENERY_LAMP_POST)
	var fallback: Dictionary = LightLook.LIGHTS[_Const.SCENERY_LAMP_POST]

	_expect(patched[LightLook.FIELD_COLOR] == fallback[LightLook.FIELD_COLOR],
		"a bad colour takes the fallback colour")
	_expect(is_equal_approx(patched[LightLook.FIELD_RANGE], fallback[LightLook.FIELD_RANGE]),
		"a missing field takes the fallback field")

	LookFile.forget(LightLook.PATH)


func _an_energy_of_zero_turns_a_light_off() -> void:
	LookFile.put(LightLook.PATH, {"format": LookFile.FORMAT, LightLook.KEY_LIGHTS: {
		_Const.SCENERY_LAMP_POST: {LightLook.FIELD_ENERGY: 0.0}}})

	var chunk := _chunk_with(_Const.SCENERY_LAMP_POST, _LAMP_TILE)

	_expect(not LightLook.gives_light(_Const.SCENERY_LAMP_POST),
		"an energy of zero gives no light")
	_expect(TileLights.lights_of(chunk).is_empty(), "a lamp post with no energy is no lamp")

	LookFile.put(LightLook.PATH, {"format": LookFile.FORMAT, LightLook.KEY_LIGHTS: {
		_Const.SCENERY_CRATE: {LightLook.FIELD_ENERGY: 1.0, LightLook.FIELD_RANGE: 2.0}}})

	_expect(LightLook.gives_light(_Const.SCENERY_CRATE), "a file row gives a crate a light")
	_expect(LightLook.keys().has(_Const.SCENERY_CRATE)
		and LightLook.keys().has(_Const.SCENERY_LAMP_POST),
		"the keys list the file rows and the fallback rows")

	LookFile.forget(LightLook.PATH)


func _every_mesh_carries_one_lamp_colour_for_each_vertex() -> void:
	var chunk := _chunk_with(_Const.SCENERY_LAMP_POST, _LAMP_TILE)
	var index := _WALL_TILE.y * _Const.CHUNK_SIZE + _WALL_TILE.x

	chunk.flags[index] = chunk.flags[index] | _Const.TILE_FLAG_WALL_EAST

	var lights := TileLights.lights_of(chunk)
	var meshes := {
		"ground": ChunkMeshBuilder.build(chunk, lights),
		"walls": WallMeshBuilder.build(chunk, null, false, lights),
		"props": PropMeshBuilder.build(chunk, lights),
	}

	for layer_name: String in meshes:
		var mesh: ArrayMesh = meshes[layer_name]
		var arrays := mesh.surface_get_arrays(0)
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var lamp: PackedFloat32Array = arrays[Mesh.ARRAY_CUSTOM0]

		_expect(mesh.surface_get_format(0) & TerrainMaterial.LAMP_FORMAT == TerrainMaterial.LAMP_FORMAT,
			"the %s mesh names the lamp format" % layer_name)
		_expect(lamp.size() == vertices.size() * 3,
			"the %s mesh has three lamp channels for each vertex" % layer_name)


func _the_figure_lights_stand_on_the_nearest_lamps() -> void:
	var node := FigureLights.new()
	var lights: Array = []

	add_child(node)

	for index: int in FigureLights.MAX_LIGHTS + 2:
		lights.append(_light_at(Vector3(index * 3.0, 1.0, 0.0)))

	node.show_lights(lights, Vector3(20.0, 0.0, 0.0))

	var first: OmniLight3D = node.lights()[0]

	_expect(node.lit_count() == FigureLights.MAX_LIGHTS, "at most MAX_LIGHTS lights stand")
	_expect(first.position == lights[-1].position, "the nearest lamp gets the first light")
	_expect(first.light_cull_mask == FigureLights.ENTITY_LAYER_BIT,
		"a light lights the entity layer only")
	_expect(not first.shadow_enabled, "a light casts no shadow")
	_expect(is_equal_approx(first.omni_range, lights[-1].reach), "a light has the reach of its lamp")

	node.show_lights([lights[0]], Vector3.ZERO)
	_expect(node.lit_count() == 1, "one lamp stands one light")

	node.show_lights([], Vector3.ZERO)
	_expect(node.lit_count() == 0, "no lamp stands no light")

	remove_child(node)
	node.queue_free()


func _a_marked_node_is_on_the_entity_layer() -> void:
	var root := Node3D.new()
	var mesh := MeshInstance3D.new()
	var deep := MeshInstance3D.new()

	root.add_child(mesh)
	mesh.add_child(deep)
	FigureLights.mark_entity(root)

	_expect(mesh.layers == FigureLights.ENTITY_LAYERS, "a mesh under the node joins the layer")
	_expect(deep.layers == FigureLights.ENTITY_LAYERS, "a mesh deeper down joins it too")
	_expect(FigureLights.ENTITY_LAYERS & 1 == 1, "a marked node stays on the first layer")

	root.free()


# ─── Helpers ─────────────────────────────────────────────────────────────────

func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


## A flat chunk (0, 0) with one object of `kind` on `tile`.
func _chunk_with(kind: String, tile: Vector2i) -> ChunkFile:
	var chunk := ChunkFile.blank(0, 0)

	chunk.objects.append(_thing(kind, tile))

	return chunk


func _thing(kind: String, tile: Vector2i) -> Dictionary:
	return {"kind": kind, "x": tile.x, "y": tile.y, "rotation": 0, "text": ""}


func _set_of(chunks: Array) -> ChunkSet:
	var chunk_set := ChunkSet.new()

	for chunk: ChunkFile in chunks:
		chunk_set.add(chunk)

	return chunk_set


## The world point of the centre of a tile of chunk (0, 0), on flat ground.
func _centre(tile: Vector2i) -> Vector3:
	return Vector3(tile.x * ChunkMeshBuilder.TILE_SIZE, 0.0, -tile.y * ChunkMeshBuilder.TILE_SIZE)


## The index of the vertex of `arrays` nearest `point`.
func _vertex_nearest(arrays: Array, point: Vector3) -> int:
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var best := 0
	var best_distance := INF

	for index: int in vertices.size():
		var distance := vertices[index].distance_squared_to(point)

		if distance < best_distance:
			best_distance = distance
			best = index

	return best


## The mean red lamp channel of the vertices whose normal points along
## `direction`.
func _mean_lamp(arrays: Array, direction: Vector3) -> float:
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var total := 0.0
	var count := 0

	for index: int in normals.size():
		if normals[index].dot(direction) > 0.9:
			total += TerrainMaterial.lamp_at(arrays, index).r
			count += 1

	return total / count if count > 0 else 0.0


## The lamp colour of the brightest vertex of `arrays`, by its red channel.
func _brightest(arrays: Array) -> Color:
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var best := Color.BLACK

	for index: int in vertices.size():
		var lamp := TerrainMaterial.lamp_at(arrays, index)

		if lamp.r > best.r:
			best = lamp

	return best


func _all_dark(arrays: Array) -> bool:
	var lamp: PackedFloat32Array = arrays[Mesh.ARRAY_CUSTOM0]

	for value: float in lamp:
		if value != 0.0:
			return false

	return true


func _light_at(position: Vector3) -> TileLights.Light:
	var light := TileLights.Light.new()

	light.position = position
	light.color = Color.WHITE
	light.energy = 1.0
	light.reach = 5.0

	return light
