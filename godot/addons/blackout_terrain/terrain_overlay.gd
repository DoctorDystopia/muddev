class_name TerrainOverlay
extends RefCounted
## The editor-only marks drawn over the terrain: walk flags, walls, areas,
## chunk borders, object markers, and the brush ring.
##
## None of this is what a player sees. The ground itself comes from
## [ChunkMeshBuilder], the same as in the client. These marks only show the
## author the facts that the ground does not show.

const _Const := preload("res://autoload/blackout_constants.gd")

## How far a mark floats over the ground, so it does not flicker in it.
const LIFT := 0.03

## The height of a wall mark, in world units.
const WALL_HEIGHT := 0.6

## The inset of a wall mark from the tile edge, in tiles.
const WALL_INSET := 0.06

const COLOR_BLOCKED := Color(0.9, 0.2, 0.2, 0.45)
const COLOR_WATER := Color(0.2, 0.45, 0.95, 0.5)
const COLOR_WALL := Color(1.0, 0.85, 0.2, 0.85)
const COLOR_BORDER := Color(1.0, 1.0, 1.0, 0.6)
const COLOR_LOCKED := Color(0.9, 0.25, 0.25, 0.9)
const COLOR_RING := Color(0.2, 1.0, 0.8, 1.0)
const AREA_ALPHA := 0.35

## The size of an object marker, in tiles.
const MARKER_SIZE := 0.45

## Object category to marker colour.
const CATEGORY_COLORS := {
	_Const.OBJECT_CATEGORY_FACILITY: Color("9d7bd8"),
	_Const.OBJECT_CATEGORY_GATHERING: Color("7ac74f"),
	_Const.OBJECT_CATEGORY_LANDMARK: Color("ffffff"),
	_Const.OBJECT_CATEGORY_NPC: Color("ff5f56"),
	_Const.OBJECT_CATEGORY_SIGN: Color("f0c674"),
	_Const.OBJECT_CATEGORY_TRANSITION: Color("4fc1e9"),
}

const COLOR_UNKNOWN_KIND := Color(1.0, 0.0, 1.0)

## The number of segments in the brush ring.
const RING_SEGMENTS := 48

## The four walls: flag bit, then the two ends of the edge as offsets from
## the tile centre, in tile space.
const _WALLS := [
	[_Const.TILE_FLAG_WALL_NORTH, Vector2(-0.5, 0.5), Vector2(0.5, 0.5)],
	[_Const.TILE_FLAG_WALL_EAST, Vector2(0.5, -0.5), Vector2(0.5, 0.5)],
	[_Const.TILE_FLAG_WALL_SOUTH, Vector2(-0.5, -0.5), Vector2(0.5, -0.5)],
	[_Const.TILE_FLAG_WALL_WEST, Vector2(-0.5, -0.5), Vector2(-0.5, 0.5)],
]


## An unshaded, see-through material that shows vertex colours.
static func material() -> StandardMaterial3D:
	var made := StandardMaterial3D.new()

	made.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	made.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	made.vertex_color_use_as_albedo = true
	made.cull_mode = BaseMaterial3D.CULL_DISABLED
	made.no_depth_test = false

	return made


## A world position over the ground at a point in tile space.
static func ground_point(chunks: ChunkSet, point: Vector2, lift: float) -> Vector3:
	var height := chunks.height_at(point)

	if is_nan(height):
		height = 0.0

	return Vector3(point.x * ChunkMeshBuilder.TILE_SIZE,
		height * ChunkMeshBuilder.HEIGHT_STEP + lift,
		-point.y * ChunkMeshBuilder.TILE_SIZE)


## The flag and wall marks of one chunk, or null when it has none.
static func flag_mesh(chunks: ChunkSet, chunk_coord: Vector2i) -> ArrayMesh:
	var tool := SurfaceTool.new()
	var origin := chunk_coord * _Const.CHUNK_SIZE
	var marks := 0

	tool.begin(Mesh.PRIMITIVE_TRIANGLES)

	for ly: int in _Const.CHUNK_SIZE:
		for lx: int in _Const.CHUNK_SIZE:
			var tile := origin + Vector2i(lx, ly)
			var flags := chunks.get_flags(tile)

			if flags == 0:
				continue

			marks += 1
			_add_flag_marks(tool, chunks, tile, flags)

	if marks == 0:
		return null

	return tool.commit()


static func _add_flag_marks(tool: SurfaceTool, chunks: ChunkSet, tile: Vector2i,
		flags: int) -> void:
	if flags & _Const.TILE_FLAG_BLOCKED:
		_add_tile_quad(tool, chunks, tile, COLOR_BLOCKED)
	elif flags & _Const.TILE_FLAG_WATER:
		_add_tile_quad(tool, chunks, tile, COLOR_WATER)

	for wall: Array in _WALLS:
		if flags & wall[0]:
			_add_wall(tool, chunks, tile, wall[1], wall[2])


## The area tint of one chunk: each tile in a stable colour for its area.
static func area_mesh(chunks: ChunkSet, chunk_coord: Vector2i) -> ArrayMesh:
	var tool := SurfaceTool.new()
	var origin := chunk_coord * _Const.CHUNK_SIZE

	tool.begin(Mesh.PRIMITIVE_TRIANGLES)

	for ly: int in _Const.CHUNK_SIZE:
		for lx: int in _Const.CHUNK_SIZE:
			var tile := origin + Vector2i(lx, ly)

			_add_tile_quad(tool, chunks, tile, area_color(chunks.get_area(tile)))

	return tool.commit()


## A stable see-through colour for an area name.
static func area_color(area_name: String) -> Color:
	var hue := float(absi(area_name.hash()) % 360) / 360.0
	var tint := Color.from_hsv(hue, 0.7, 0.9)

	tint.a = AREA_ALPHA

	return tint


static func _add_tile_quad(tool: SurfaceTool, chunks: ChunkSet, tile: Vector2i,
		color: Color) -> void:
	var centre := Vector2(tile)
	var sw := ground_point(chunks, centre + Vector2(-0.5, -0.5), LIFT)
	var se := ground_point(chunks, centre + Vector2(0.5, -0.5), LIFT)
	var nw := ground_point(chunks, centre + Vector2(-0.5, 0.5), LIFT)
	var ne := ground_point(chunks, centre + Vector2(0.5, 0.5), LIFT)

	for corner: Vector3 in [sw, se, ne, sw, ne, nw]:
		tool.set_color(color)
		tool.add_vertex(corner)


static func _add_wall(tool: SurfaceTool, chunks: ChunkSet, tile: Vector2i,
		start: Vector2, end: Vector2) -> void:
	var centre := Vector2(tile)
	var inset := -(start + end).normalized() * WALL_INSET
	var low_a := ground_point(chunks, centre + start + inset, 0.0)
	var low_b := ground_point(chunks, centre + end + inset, 0.0)
	var high_a := low_a + Vector3.UP * WALL_HEIGHT
	var high_b := low_b + Vector3.UP * WALL_HEIGHT

	for corner: Vector3 in [low_a, low_b, high_b, low_a, high_b, high_a]:
		tool.set_color(COLOR_WALL)
		tool.add_vertex(corner)


## The outline of a square of tiles as lines, draped on the ground.
## `low_tile` is the southwest tile, and `tiles` is the side in tiles.
static func outline_mesh(chunks: ChunkSet, low_tile: Vector2i, tiles: int,
		color: Color) -> ArrayMesh:
	var tool := SurfaceTool.new()
	var origin := Vector2(low_tile) - Vector2(0.5, 0.5)
	var corners := [origin, origin + Vector2(tiles, 0),
		origin + Vector2(tiles, tiles), origin + Vector2(0, tiles), origin]

	tool.begin(Mesh.PRIMITIVE_LINES)

	for side: int in 4:
		for step: int in tiles:
			var a: Vector2 = corners[side].lerp(corners[side + 1],
				float(step) / float(tiles))
			var b: Vector2 = corners[side].lerp(corners[side + 1],
				float(step + 1) / float(tiles))

			tool.set_color(color)
			tool.add_vertex(ground_point(chunks, a, LIFT * 2.0))
			tool.set_color(color)
			tool.add_vertex(ground_point(chunks, b, LIFT * 2.0))

	return tool.commit()


## The brush ring at `centre`, a point in tile space, as a line loop.
static func ring_mesh(chunks: ChunkSet, centre: Vector2, radius: float) -> ArrayMesh:
	var tool := SurfaceTool.new()
	var reach := maxf(radius, 0.5)

	tool.begin(Mesh.PRIMITIVE_LINES)

	for segment: int in RING_SEGMENTS:
		var angle_a := TAU * segment / RING_SEGMENTS
		var angle_b := TAU * (segment + 1) / RING_SEGMENTS
		var a := centre + Vector2(cos(angle_a), sin(angle_a)) * reach
		var b := centre + Vector2(cos(angle_b), sin(angle_b)) * reach

		tool.set_color(COLOR_RING)
		tool.add_vertex(ground_point(chunks, a, LIFT * 3.0))
		tool.set_color(COLOR_RING)
		tool.add_vertex(ground_point(chunks, b, LIFT * 3.0))

	return tool.commit()


## The colour of the marker of an object kind.
static func kind_color(kind: String) -> Color:
	var category: String = _Const.OBJECT_KINDS.get(kind, "")

	return CATEGORY_COLORS.get(category, COLOR_UNKNOWN_KIND)
