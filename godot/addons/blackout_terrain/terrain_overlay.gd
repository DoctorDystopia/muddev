class_name TerrainOverlay
extends RefCounted
## The editor-only marks drawn over the terrain: walk flags, walls, areas,
## chunk borders, object markers, links, and the brush ring.
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

## The colour of each mark, by key. The Look tab of the editor can change
## each one for the session ([method set_marks]), and [method mark] gives
## the colour of the moment. These are the defaults.
const MARK_DEFAULTS := {
	"blocked": Color(0.9, 0.2, 0.2, 0.45),
	"water": Color(0.2, 0.45, 0.95, 0.5),
	"wall": Color(1.0, 0.85, 0.2, 0.85),
	"border": Color(1.0, 1.0, 1.0, 0.6),
	"locked": Color(0.9, 0.25, 0.25, 0.9),
	"ring": Color(0.2, 1.0, 0.8, 1.0),
	"add": Color(0.3, 1.0, 0.45, 1.0),
	"remove": Color(1.0, 0.4, 0.3, 1.0),
	"refused": Color(1.0, 0.25, 0.2, 1.0),
	"warning": Color(1.0, 0.75, 0.2, 1.0),
	"selection": Color(0.35, 0.8, 1.0, 1.0),
	"beacon": Color(1.0, 0.3, 1.0),
	"ghost": Color(0.45, 0.45, 0.5),
}

## What each mark key means, for the Look tab and the legend.
const MARK_NAMES := {
	"blocked": "Blocked tile",
	"water": "Water tile",
	"wall": "Wall",
	"border": "Chunk border",
	"locked": "Locked edge",
	"ring": "Brush ring",
	"add": "Build: add",
	"remove": "Build: remove",
	"refused": "Build: refused",
	"warning": "Build: warning",
	"selection": "Tile selection",
	"beacon": "Selection beacon",
	"ghost": "Ghost plane",
}

## The key of the colour of an object category in [method set_marks].
const CATEGORY_KEY := "category:"

const AREA_ALPHA := 0.35

## The colours that the author changed: key to colour.
static var _marks := {}

## The size of an object marker, in tiles.
const MARKER_SIZE := 0.45

## Object category to marker colour: the defaults. [method category_color]
## gives the colour of the moment.
const CATEGORY_COLORS := {
	_Const.OBJECT_CATEGORY_FACILITY: Color("9d7bd8"),
	_Const.OBJECT_CATEGORY_GATHERING: Color("7ac74f"),
	_Const.OBJECT_CATEGORY_LANDMARK: Color("ffffff"),
	_Const.OBJECT_CATEGORY_NPC: Color("ff5f56"),
	_Const.OBJECT_CATEGORY_SIGN: Color("f0c674"),
	_Const.OBJECT_CATEGORY_TRANSITION: Color("4fc1e9"),
	_Const.OBJECT_CATEGORY_CLIMB: Color("e9954f"),
	_Const.OBJECT_CATEGORY_DECOR: Color("b0a48c"),
}

## The height of a link over the ground, and the highest point of an arc.
const LINK_LIFT := 0.6
const LINK_ARC_MAX := 4.0
const LINK_ARC_SEGMENTS := 16

## The length of the stub of a transition whose target is not loaded, in
## tiles.
const LINK_STUB := 2.5

const COLOR_UNKNOWN_KIND := Color(1.0, 0.0, 1.0)


## The colour of the mark `key`: the author's, else the default.
static func mark(key: String) -> Color:
	return _marks.get(key, MARK_DEFAULTS.get(key, COLOR_UNKNOWN_KIND))


## The colour of the marker of an object category: the author's, else the
## default, else magenta for a category that nothing names.
static func category_color(category: String) -> Color:
	return _marks.get(CATEGORY_KEY + category,
		CATEGORY_COLORS.get(category, COLOR_UNKNOWN_KIND))


## Give the marks the colours of `colors`: mark key or category key to
## colour. A key that is not there goes back to its default.
static func set_marks(colors: Dictionary) -> void:
	_marks = colors.duplicate()

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
		_add_tile_quad(tool, chunks, tile, mark("blocked"))
	elif flags & _Const.TILE_FLAG_WATER:
		_add_tile_quad(tool, chunks, tile, mark("water"))

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
		tool.set_color(mark("wall"))
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


## Lines draped on the ground, for the marks of a Build tool. Each item of
## `paths` is an Array of points in tile space, joined in order.
static func path_mesh(chunks: ChunkSet, paths: Array, color: Color) -> ArrayMesh:
	var tool := SurfaceTool.new()

	tool.begin(Mesh.PRIMITIVE_LINES)

	for path: Array in paths:
		for index: int in path.size() - 1:
			_add_draped_line(tool, chunks, path[index], path[index + 1], color)

	return tool.commit()


## One line from `a` to `b`, in pieces of at most one tile, so it follows the
## ground.
static func _add_draped_line(tool: SurfaceTool, chunks: ChunkSet, a: Vector2,
		b: Vector2, color: Color) -> void:
	var pieces := maxi(1, ceili(a.distance_to(b)))

	for piece: int in pieces:
		var from := a.lerp(b, float(piece) / pieces)
		var to := a.lerp(b, float(piece + 1) / pieces)

		tool.set_color(color)
		tool.add_vertex(ground_point(chunks, from, LIFT * 3.0))
		tool.set_color(color)
		tool.add_vertex(ground_point(chunks, to, LIFT * 3.0))


## The outline of the Build tab (DESIGN-0013 section 6.7): a lattice of
## lines through the corner heights of `heights`, which maps a corner to its
## height in height steps. A line joins each two neighbour corners of the
## map. Corner (x, y) is the south-west
## corner of tile (x, y). The Roof tool draws its plan with it before the
## release.
## One lattice for each map of `layers`, in one mesh. The Place tool draws
## the planes of a template copy with it: one map for each plane.
static func lattice_layers_mesh(layers: Array, color: Color) -> ArrayMesh:
	var tool := SurfaceTool.new()

	tool.begin(Mesh.PRIMITIVE_LINES)

	for heights: Dictionary in layers:
		_add_lattice(tool, heights, color)

	return tool.commit()


static func _add_lattice(tool: SurfaceTool, heights: Dictionary, color: Color) -> void:
	for corner: Vector2i in heights:
		for step: Vector2i in [Vector2i(1, 0), Vector2i(0, 1)]:
			var next := corner + step

			if not heights.has(next):
				continue

			tool.set_color(color)
			tool.add_vertex(_corner_point(corner, heights[corner]))
			tool.set_color(color)
			tool.add_vertex(_corner_point(next, heights[next]))


## The world position of corner `corner` at `height` height steps, lifted a
## little so the line shows over a drawn roof.
static func _corner_point(corner: Vector2i, height: int) -> Vector3:
	return Vector3((corner.x - 0.5) * ChunkMeshBuilder.TILE_SIZE,
		height * ChunkMeshBuilder.HEIGHT_STEP + LIFT * 3.0,
		-(corner.y - 0.5) * ChunkMeshBuilder.TILE_SIZE)


## The outline of a rectangle of tiles, as one path for [method path_mesh].
static func rect_path(rect: Rect2i) -> Array:
	var low := Vector2(rect.position) - Vector2(0.5, 0.5)
	var size := Vector2(rect.size)

	return [low, low + Vector2(size.x, 0.0), low + size, low + Vector2(0.0, size.y), low]


## The edge `bit` of `tile`, as one path for [method path_mesh].
static func edge_path(tile: Vector2i, bit: int) -> Array:
	for wall: Array in _WALLS:
		if wall[0] == bit:
			return [Vector2(tile) + wall[1], Vector2(tile) + wall[2]]

	return []


## The brush ring at `centre`, a point in tile space, as a line loop. A
## square brush gives the outline of its tiles
## ([method TerrainBrushes.square_rect]).
static func ring_mesh(chunks: ChunkSet, centre: Vector2, radius: float,
		shape := TerrainBrushes.Shape.CIRCLE) -> ArrayMesh:
	if shape == TerrainBrushes.Shape.SQUARE:
		var rect := TerrainBrushes.square_rect(centre, radius)

		return path_mesh(chunks, [rect_path(rect)], mark("ring"))

	var tool := SurfaceTool.new()
	var reach := maxf(radius, 0.5)

	tool.begin(Mesh.PRIMITIVE_LINES)

	for segment: int in RING_SEGMENTS:
		var angle_a := TAU * segment / RING_SEGMENTS
		var angle_b := TAU * (segment + 1) / RING_SEGMENTS
		var a := centre + Vector2(cos(angle_a), sin(angle_a)) * reach
		var b := centre + Vector2(cos(angle_b), sin(angle_b)) * reach

		tool.set_color(mark("ring"))
		tool.add_vertex(ground_point(chunks, a, LIFT * 3.0))
		tool.set_color(mark("ring"))
		tool.add_vertex(ground_point(chunks, b, LIFT * 3.0))

	return tool.commit()


# ─── Links ──────────────────────────────────────────────────────────────────

## True when an object of this kind leads somewhere: a transition or a climb.
static func has_link(kind: String) -> bool:
	return _Const.OBJECT_KIND_TARGETS.has(kind) or _Const.OBJECT_KIND_CLIMBS.has(kind)


## The lines of every link of `linked` (`{tile, kind, rotation}` each). A
## transition draws an arc to its target when the target is loaded, and a
## stub toward it when not. A climb draws a line up or down to its landing,
## as far as the next plane starts ([constant TerrainWorld.NEW_PLANE_RISE]).
## A ladder draws a post. A flight draws a slope over its steps.
static func link_mesh(chunks: ChunkSet, linked: Array[Dictionary],
		_plane: int) -> ArrayMesh:
	var tool := SurfaceTool.new()

	tool.begin(Mesh.PRIMITIVE_LINES)

	for thing: Dictionary in linked:
		var color := kind_color(thing["kind"])

		for segment: Array in _link_segments(chunks, thing):
			tool.set_color(color)
			tool.add_vertex(segment[0])
			tool.set_color(color)
			tool.add_vertex(segment[1])

	return tool.commit()


## The labels of one link: where it leads, in words.
static func link_labels(chunks: ChunkSet, thing: Dictionary,
		plane: int) -> Array[Label3D]:
	var labels: Array[Label3D] = []
	var kind: String = thing["kind"]
	var start := _link_start(chunks, thing["tile"])
	var target: Array = _Const.OBJECT_KIND_TARGETS.get(kind, [])

	if not target.is_empty():
		labels.append(_label("-> (%d, %d)" % [target[0], target[1]],
			start + Vector3.UP * 0.4, kind_color(kind)))

	for way: String in _Const.OBJECT_KIND_CLIMBS.get(kind, []):
		var step: int = _Const.CLIMB_PLANE_STEPS[way]

		labels.append(_label("%s -> plane %d" % [way, plane + step],
			_climb_end(chunks, thing, way), kind_color(kind)))

	return labels


static func _link_segments(chunks: ChunkSet, thing: Dictionary) -> Array:
	var kind: String = thing["kind"]
	var tile: Vector2i = thing["tile"]
	var start := _link_start(chunks, tile)
	var segments := []
	var target: Array = _Const.OBJECT_KIND_TARGETS.get(kind, [])

	if not target.is_empty():
		segments.append_array(_transition_segments(chunks, tile,
			Vector2i(target[0], target[1])))

	for way: String in _Const.OBJECT_KIND_CLIMBS.get(kind, []):
		segments.append([start, _climb_end(chunks, thing, way)])

	return segments


## The end of the link of one climb way: over its landing, one plane rise
## from the start. A ladder ends over its own tile. A flight ends over the
## tile past its top step.
static func _climb_end(chunks: ChunkSet, thing: Dictionary, way: String) -> Vector3:
	var start := _link_start(chunks, thing["tile"])
	var landing := ClimbRule.landing(thing["tile"], thing["kind"],
		thing["rotation"], way)
	var over := Vector3(landing.x * ChunkMeshBuilder.TILE_SIZE, start.y,
		-landing.y * ChunkMeshBuilder.TILE_SIZE)
	var step: int = _Const.CLIMB_PLANE_STEPS[way]

	return over + Vector3.UP * _climb_height() * step


static func _transition_segments(chunks: ChunkSet, tile: Vector2i,
		target: Vector2i) -> Array:
	var start := _link_start(chunks, tile)

	if not chunks.has_tile(target):
		var toward := Vector2(target - tile).normalized() * LINK_STUB
		var stub := ground_point(chunks, Vector2(tile) + toward, LINK_LIFT)

		return [[start, stub]]

	var end := _link_start(chunks, target)
	var rise := minf(LINK_ARC_MAX, start.distance_to(end) * 0.25)
	var segments := []

	for index: int in LINK_ARC_SEGMENTS:
		var a := _arc_point(start, end, rise, float(index) / LINK_ARC_SEGMENTS)
		var b := _arc_point(start, end, rise, float(index + 1) / LINK_ARC_SEGMENTS)

		segments.append([a, b])

	return segments


static func _arc_point(start: Vector3, end: Vector3, rise: float,
		along: float) -> Vector3:
	return start.lerp(end, along) + Vector3.UP * rise * 4.0 * along * (1.0 - along)


static func _link_start(chunks: ChunkSet, tile: Vector2i) -> Vector3:
	return ground_point(chunks, Vector2(tile), LINK_LIFT)


static func _climb_height() -> float:
	return TerrainWorld.NEW_PLANE_RISE * ChunkMeshBuilder.HEIGHT_STEP


static func _label(text: String, at: Vector3, color: Color) -> Label3D:
	var label := Label3D.new()

	label.text = text
	label.position = at
	label.modulate = color
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.pixel_size = 0.004

	return label


## The colour of the marker of an object kind.
static func kind_color(kind: String) -> Color:
	var category: String = TileTables.object_category(kind)

	return category_color(category)
