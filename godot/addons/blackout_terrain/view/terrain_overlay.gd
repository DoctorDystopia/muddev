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

## The vertices of the two triangles of one quad.
const TILE_QUAD_VERTICES := 6

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

## The hue of the first area tint, as a part of the colour wheel. At 0.9 the
## first area keeps the pink that the old hash rule gave the Oasis.
const AREA_HUE_START := 0.9

## The number of hues that an area tint can take.
const AREA_HUE_STEPS := 72

## The shades that an area tint can take: saturation, then value. Three
## shades keep two tints apart where two hues come near.
const AREA_SHADES := [Vector2(0.65, 0.95), Vector2(0.9, 0.7), Vector2(0.4, 0.85)]

## The tint of an area that the area table does not name. No shade is grey,
## so this tint is apart from each tint of a row.
const COLOR_UNKNOWN_AREA := Color(0.5, 0.5, 0.5)

## The tint of each row index of the area table, made when a row needs it.
static var _area_tints: Array[Color] = []

## Every colour that an area tint can take, in the order of the hues.
static var _tint_candidates: Array[Color] = []

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
	_Const.OBJECT_CATEGORY_ITEM_SPAWN: Color("e8d44d"),
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


## The shader of a ghost plane: see-through, in the ghost colour. It is for
## the editor alone, so it lives with the plugin and not with
## [TerrainMaterial].
const GHOST_SHADER := preload("res://addons/blackout_terrain/view/ghost.gdshader")

## The name of the opacity uniform of the ghost shader.
const GHOST_OPACITY := "opacity"

## The marks whose alpha the Look tab does not edit. The World tab sets the
## opacity of a ghost plane, so the ghost mark gives its colour only.
const NO_ALPHA_MARKS := ["ghost"]


## A new material of a ghost plane, at `opacity`, in the ghost colour of the
## moment.
static func ghost_material(opacity: float) -> ShaderMaterial:
	var made := ShaderMaterial.new()

	made.shader = GHOST_SHADER
	set_ghost(made, opacity)

	return made


## Give a material of [method ghost_material] the ghost colour of the
## moment, and `opacity`. It builds no mesh again.
static func set_ghost(material: ShaderMaterial, opacity: float) -> void:
	material.set_shader_parameter(TerrainMaterial.TINT, mark("ghost"))
	material.set_shader_parameter(GHOST_OPACITY, opacity)


## True when `material` draws a ghost plane. For a test.
static func is_ghost(material: Material) -> bool:
	var shaded := material as ShaderMaterial

	return shaded != null and shaded.shader == GHOST_SHADER


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


## The triangles of the tile marks of one chunk: two for each quad, in one
## colour. A class, as [ChunkMeshBuilder] has one: a packed array that goes
## through a call can be a copy.
##
## The marks of a chunk were made with a SurfaceTool and four calls of
## [method ground_point] for each tile until 11/11/2026. The area tint of
## one chunk then took 44 ms, and each brush dab paid for it.
class _Quads:
	var vertices := PackedVector3Array()
	var colors := PackedColorArray()

	## Add the quad `sw`, `se`, `ne`, `nw` as two triangles in `color`.
	func add(sw: Vector3, se: Vector3, ne: Vector3, nw: Vector3, color: Color) -> void:
		vertices.append(sw)
		vertices.append(se)
		vertices.append(ne)
		vertices.append(sw)
		vertices.append(ne)
		vertices.append(nw)

		for _corner: int in TILE_QUAD_VERTICES:
			colors.append(color)

	## Add the quad of the tile whose southwest corner is at `south` in
	## `points`, the answer of [method TerrainOverlay.corner_points].
	func add_tile(points: PackedVector3Array, south: int, color: Color) -> void:
		var north: int = south + _Const.CHUNK_CORNERS_PER_SIDE

		add(points[south], points[south + 1], points[north + 1], points[north], color)

	## The mesh of the quads, or null when there is none.
	func mesh() -> ArrayMesh:
		if vertices.is_empty():
			return null

		var made := ArrayMesh.new()
		var arrays := []

		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = vertices
		arrays[Mesh.ARRAY_COLOR] = colors
		made.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)

		return made


## Each corner of `chunk` as a world position, `lift` over the ground, with
## no jitter: row 0 first, as the height grid. The four corners of a tile
## are the ends of its quad. Thus, a tile mark reads four values here, and
## it does not ask [method ground_point] for each one.
static func corner_points(chunk: ChunkFile, lift: float) -> PackedVector3Array:
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE
	var size: int = _Const.CHUNK_SIZE
	var points := PackedVector3Array()

	points.resize(side * side)

	for j: int in side:
		var z := -(chunk.cy * size + j - 0.5) * ChunkMeshBuilder.TILE_SIZE

		for i: int in side:
			var index := j * side + i
			var x := (chunk.cx * size + i - 0.5) * ChunkMeshBuilder.TILE_SIZE
			var y := chunk.heights[index] * ChunkMeshBuilder.HEIGHT_STEP + lift

			points[index] = Vector3(x, y, z)

	return points


## The flag and wall marks of one chunk, or null when it has none.
static func flag_mesh(chunks: ChunkSet, chunk_coord: Vector2i) -> ArrayMesh:
	var chunk := chunks.get_chunk(chunk_coord)

	if chunk == null:
		return null

	var size: int = _Const.CHUNK_SIZE
	var origin := chunk_coord * size
	var points := corner_points(chunk, LIFT)
	var quads := _Quads.new()

	for ly: int in size:
		for lx: int in size:
			var flags := chunk.flags[ly * size + lx]

			if flags == 0:
				continue

			var south: int = ly * _Const.CHUNK_CORNERS_PER_SIDE + lx

			_add_flag_marks(quads, chunks, points, south, origin + Vector2i(lx, ly), flags)

	return quads.mesh()


## Add the marks of one tile with `flags`. `south` is its southwest corner
## in `points`, and `tile` is its world tile.
static func _add_flag_marks(quads: _Quads, chunks: ChunkSet, points: PackedVector3Array,
		south: int, tile: Vector2i, flags: int) -> void:
	if flags & _Const.TILE_FLAG_BLOCKED:
		quads.add_tile(points, south, mark("blocked"))
	elif flags & _Const.TILE_FLAG_WATER:
		quads.add_tile(points, south, mark("water"))

	for wall: Array in _WALLS:
		if flags & wall[0]:
			_add_wall(quads, chunks, tile, wall[1], wall[2])


## The area tint of one chunk: each tile in the colour of its area. Null
## for a chunk that the set does not hold.
static func area_mesh(chunks: ChunkSet, chunk_coord: Vector2i) -> ArrayMesh:
	var chunk := chunks.get_chunk(chunk_coord)

	if chunk == null:
		return null

	var size: int = _Const.CHUNK_SIZE
	var points := corner_points(chunk, LIFT)
	var tints: Array[Color] = []
	var quads := _Quads.new()

	for area_name: String in chunk.area_names:
		tints.append(area_color(area_name))

	for ly: int in size:
		for lx: int in size:
			var south: int = ly * _Const.CHUNK_CORNERS_PER_SIDE + lx

			quads.add_tile(points, south, tints[chunk.areas[ly * size + lx]])

	return quads.mesh()


## The see-through colour of an area: the tint of its row in the area table
## ([method area_tint]). An area that the table does not name is grey.
##
## Until 11/09/2026 the hue came from a hash of the key, and two keys could
## get one hue: `oasis` and `azm_plains` were 1 degree apart.
static func area_color(area_name: String) -> Color:
	var index := TileTables.keys(TileTables.AREAS).find(area_name)
	var tint := COLOR_UNKNOWN_AREA if index < 0 else area_tint(index)

	tint.a = AREA_ALPHA

	return tint


## The opaque tint of row `index` of the area table. Each row takes the
## candidate that is farthest from the tints of all the rows before it.
## Thus, two rows never share a tint, and a new last row changes no tint of
## an earlier row. The removal of a row moves the tints of the rows after it.
## The candidates run out after AREA_HUE_STEPS x AREA_SHADES rows.
static func area_tint(index: int) -> Color:
	while _area_tints.size() <= index:
		_area_tints.append(_farthest_candidate(_area_tints))

	return _area_tints[index]


## The distance between two colours in RGB space. The alpha is not part of it.
static func color_gap(a: Color, b: Color) -> float:
	return Vector3(a.r - b.r, a.g - b.g, a.b - b.b).length()


## The candidate that is farthest from its nearest colour in `taken`. The
## first candidate when `taken` is empty. A tie goes to the earlier one.
static func _farthest_candidate(taken: Array[Color]) -> Color:
	var candidates := _candidates()
	var best := candidates[0]
	var best_gap := -1.0

	if taken.is_empty():
		return best

	for candidate: Color in candidates:
		var gap := INF

		for other: Color in taken:
			gap = minf(gap, color_gap(candidate, other))

		if gap > best_gap:
			best = candidate
			best_gap = gap

	return best


## Every colour that an area tint can take: each hue step in each shade.
static func _candidates() -> Array[Color]:
	if not _tint_candidates.is_empty():
		return _tint_candidates

	for step: int in AREA_HUE_STEPS:
		var hue := fposmod(AREA_HUE_START + float(step) / AREA_HUE_STEPS, 1.0)

		for shade: Vector2 in AREA_SHADES:
			_tint_candidates.append(Color.from_hsv(hue, shade.x, shade.y))

	return _tint_candidates


## Add the mark of one wall of `tile`: an upright quad a little inside the
## edge from `start` to `end`. The two ends are offsets from the tile centre.
static func _add_wall(quads: _Quads, chunks: ChunkSet, tile: Vector2i,
		start: Vector2, end: Vector2) -> void:
	var centre := Vector2(tile)
	var inset := -(start + end).normalized() * WALL_INSET
	var low_a := ground_point(chunks, centre + start + inset, 0.0)
	var low_b := ground_point(chunks, centre + end + inset, 0.0)
	var high_a := low_a + Vector3.UP * WALL_HEIGHT
	var high_b := low_b + Vector3.UP * WALL_HEIGHT

	quads.add(low_a, low_b, high_b, high_a, mark("wall"))


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
