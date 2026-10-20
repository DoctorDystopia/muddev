class_name TileLights
extends RefCounted
## The lamp light of the tile world, baked into the meshes of a chunk.
##
## A chunk object whose scenery gives light ([LightLook]) is a lamp. This
## class finds the lamps that reach a chunk, and gives each vertex of its
## ground, its walls, and its props the colour that those lamps add. The
## mesh builders write that colour into the CUSTOM0 array of the mesh, and
## `terrain.gdshader` sends it out as emission ([TerrainMaterial]).
##
## The client ([TerrainView]) and the terrain editor ([TerrainWorld]) both
## bake through this class. Thus, what an author sees is what a player sees.
##
## ## The reach
##
## A lamp reaches the chunks around its own. [method collect] reads the
## chunk and its eight neighbours of the same chunk set, and keeps each lamp
## whose range touches the chunk. A lamp lights its own plane only: a lamp
## on an upper floor does not light the ground through the floor.
##
## ## The falloff
##
## The light at a point is the glow of the lamp (its colour times its
## energy) times a falloff of the distance, squared, times how much the
## surface faces the lamp. A surface that faces away gets nothing, so the
## side of a wall toward a lamp lights up and the side away stays dark.
##
## ## The cost
##
## A chunk has about 25,000 ground vertices. A test of each one against each
## lamp would cost a build its frame. Thus [method bucket] sorts the lamps
## of a chunk by the tiles that they reach, one time for each build, and a
## tile with no lamp pays nothing.

const _Const := preload("res://autoload/blackout_constants.gd")

## The chunks that a lamp of one chunk may reach, as chunk offsets: the
## chunk itself and its eight neighbours.
const AROUND := [Vector2i(-1, -1), Vector2i(0, -1), Vector2i(1, -1),
	Vector2i(-1, 0), Vector2i(0, 0), Vector2i(1, 0),
	Vector2i(-1, 1), Vector2i(0, 1), Vector2i(1, 1)]


## One lamp in the world.
class Light:
	## The bulb, in world units.
	var position: Vector3
	## The colour of the light.
	var color: Color
	## How bright it is.
	var energy: float
	## How far it reaches, in world units.
	var reach: float

	## The colour times the energy: what the bake adds right under the bulb.
	func glow() -> Color:
		return Color(color.r * energy, color.g * energy, color.b * energy, 1.0)

	## True when the light reaches a box from `low` to `high` on the ground
	## plane.
	func touches(low: Vector2, high: Vector2) -> bool:
		return position.x + reach >= low.x and position.x - reach <= high.x \
			and position.z + reach >= low.y and position.z - reach <= high.y

	## A text that names the light: its place, its colour, and its reach.
	func key() -> String:
		return "%.2f,%.2f,%.2f %s %.2f %.2f" % [position.x, position.y, position.z,
			color.to_html(false), energy, reach]


# ─── Finding the lamps ──────────────────────────────────────────────────────

## The lamps of one chunk.
static func lights_of(chunk: ChunkFile) -> Array[Light]:
	var found: Array[Light] = []

	for thing: Dictionary in chunk.objects:
		var light := _light_of(chunk, thing)

		if light != null:
			found.append(light)

	return found


## The lamps that reach the chunk at `coord`: those of the chunk and of its
## neighbours in `chunks`, with a range that touches it. The chunk itself
## need not be in the set yet.
static func collect(chunks: ChunkSet, coord: Vector2i) -> Array[Light]:
	var found: Array[Light] = []

	if chunks == null:
		return found

	var size: int = _Const.CHUNK_SIZE
	var low := Vector2(coord.x * size - 0.5, -(coord.y * size + size - 0.5))
	var high := Vector2(coord.x * size + size - 0.5, -(coord.y * size - 0.5))

	for offset: Vector2i in AROUND:
		var chunk := chunks.get_chunk(coord + offset)

		if chunk == null:
			continue

		for light: Light in lights_of(chunk):
			if light.touches(low, high):
				found.append(light)

	return found


## Every lamp of a chunk set.
static func all_of(chunks: ChunkSet) -> Array[Light]:
	var found: Array[Light] = []

	if chunks == null:
		return found

	for coord: Vector2i in chunks.chunk_coords():
		found.append_array(lights_of(chunks.get_chunk(coord)))

	return found


## A text that changes when the lamps change: a new lamp, a moved lamp, or
## a new look. A reader keeps it beside a built mesh, and builds again when
## it differs.
static func signature(lights: Array) -> String:
	var keys := PackedStringArray()

	for light: Light in lights:
		keys.append(light.key())

	keys.sort()

	return "\n".join(keys)


## The lamp of one chunk object, or null for an object whose scenery gives
## no light. The bulb stands over the ground of the tile centre, at the
## height of the row, scaled and nudged by the look of the object.
static func _light_of(chunk: ChunkFile, thing: Dictionary) -> Light:
	var row := LightLook.light_of(TileTables.scenery_of(thing["kind"]))

	if not LightLook.is_lit(row):
		return null

	var lx: int = thing["x"]
	var ly: int = thing["y"]
	var look: Dictionary = thing.get("look", {})
	var world_x := chunk.cx * _Const.CHUNK_SIZE + lx
	var world_y := chunk.cy * _Const.CHUNK_SIZE + ly
	var ground := ChunkMeshBuilder.surface_height(chunk, lx + 0.5, ly + 0.5) \
		* ChunkMeshBuilder.HEIGHT_STEP
	var height: float = row[LightLook.FIELD_HEIGHT] * ObjectLook.scale_of(look)
	var light := Light.new()

	light.position = Vector3(world_x * ChunkMeshBuilder.TILE_SIZE, ground + height,
		-world_y * ChunkMeshBuilder.TILE_SIZE) + ObjectLook.offset_of(look)
	light.color = row[LightLook.FIELD_COLOR]
	light.energy = row[LightLook.FIELD_ENERGY]
	light.reach = row[LightLook.FIELD_RANGE] * ChunkMeshBuilder.TILE_SIZE

	return light


# ─── The bake ───────────────────────────────────────────────────────────────

## The lamps of `lights` that reach each local tile of `chunk`: local tile
## index to an Array of [Light]. A tile that no lamp reaches has no entry.
static func bucket(chunk: ChunkFile, lights: Array) -> Dictionary:
	var buckets := {}
	var size: int = _Const.CHUNK_SIZE
	var origin_x := chunk.cx * size
	var origin_y := chunk.cy * size

	for light: Light in lights:
		var tile_x := light.position.x / ChunkMeshBuilder.TILE_SIZE - origin_x
		var tile_y := -light.position.z / ChunkMeshBuilder.TILE_SIZE - origin_y
		var reach := light.reach / ChunkMeshBuilder.TILE_SIZE
		var first_x := maxi(int(floorf(tile_x - reach)), 0)
		var last_x := mini(int(ceilf(tile_x + reach)), size - 1)
		var first_y := maxi(int(floorf(tile_y - reach)), 0)
		var last_y := mini(int(ceilf(tile_y + reach)), size - 1)

		for ly: int in range(first_y, last_y + 1):
			for lx: int in range(first_x, last_x + 1):
				var index := ly * size + lx

				if not buckets.has(index):
					buckets[index] = []

				buckets[index].append(light)

	return buckets


## The colour that `lights` add at `point`, on a surface with `normal`.
## Black with no lamp in reach.
static func lit(point: Vector3, normal: Vector3, lights: Array) -> Color:
	var total := Color.BLACK

	for light: Light in lights:
		var to_light := light.position - point
		var distance := to_light.length()

		if distance >= light.reach or distance == 0.0:
			continue

		var falloff := 1.0 - distance / light.reach
		var facing := maxf(normal.dot(to_light / distance), 0.0)
		var amount := falloff * falloff * facing

		if amount > 0.0:
			total += light.glow() * amount

	total.a = 1.0

	return total


## Append the three channels of `color` to a lamp array.
static func append(lamp: PackedFloat32Array, color: Color) -> void:
	lamp.append(color.r)
	lamp.append(color.g)
	lamp.append(color.b)
