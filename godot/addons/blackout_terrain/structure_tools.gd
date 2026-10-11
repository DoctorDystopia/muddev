@tool
class_name StructureTools
extends RefCounted
## The edits of the Build tools of the terrain editor (DESIGN-0013 section
## 6.7): Wall line, Room, Doorway, Level above, Stairs, Roof, Wall style, and
## Decor.
##
## A structure is tile grid facts, not a scene. A wall is a wall flag. A room
## is floor types inside walls. An upper level is floor tiles on the plane
## above. Stairs are a climb pair. A roof is the ground of the plane above:
## a roof floor type, the Blocked flag, and the corner heights of
## [RoofShapes]. Each function here writes those facts
## through a [TerrainEdit], so one gesture is one undo entry, and the server
## reads nothing new.
##
## No function calls the editor. `sets` maps a plane to its [ChunkSet], as
## [method TerrainWorld.plane_sets] gives it, so `test_structure_tools.tscn`
## tests each rule with no editor.
##
## Each function returns a problem in words, or "" when it did its work. A
## problem changes nothing.
##
## ## Which tile carries a wall
##
## A wall bit sits on one tile, on one edge, and the slab stands inside that
## tile ([WallMeshBuilder]). A wall on either side of an edge stops a step.
## Thus a tool picks one side:
##
## - The Room tool puts each wall on the inner edge of a border tile, so the
##   slab stands inside the room.
## - The Wall line puts each wall on the tile north of a line along x, or
##   east of a line along y. When that tile is void and the other is not,
##   the wall goes on the other tile. A void tile with a wall is the
##   `wall_on_void` finding.
## - A removal clears the bits on both sides of each edge.
##
## ## The wall style (DESIGN-0013 section 6.4)
##
## The Wall line and the Room put their wall style on each tile that gets a
## wall bit. The Wall style brush paints a style on each tile with a wall bit
## under the brush. A removal keeps the style: a style on a tile with no wall
## bit is legal, and nothing draws it.
##
## ## Decor (DESIGN-0013 section 6.5)
##
## A decor kind is an object kind of the category `decor`: scenery that pins
## no room. A tile holds one decor. A place on a tile with decor replaces it,
## so a second click after R turns it. A void tile takes no decor. A Blocked
## tile takes decor, because a Blocked tile under a table stops a walk
## through it.

const _Const := preload("res://autoload/blackout_constants.gd")

## The rule that picks the base height of "Level ground".
enum Base { HIGHEST, LOWEST, AVERAGE }

## The largest room that "click inside a room" accepts. A fill that reaches
## it is not a room.
const FILL_LIMIT := 1024

## The four edges: wall bit, the offset to the tile across the edge, and the
## bit of that tile on the same edge.
const EDGES := [
	[_Const.TILE_FLAG_WALL_NORTH, Vector2i(0, 1), _Const.TILE_FLAG_WALL_SOUTH],
	[_Const.TILE_FLAG_WALL_EAST, Vector2i(1, 0), _Const.TILE_FLAG_WALL_WEST],
	[_Const.TILE_FLAG_WALL_SOUTH, Vector2i(0, -1), _Const.TILE_FLAG_WALL_NORTH],
	[_Const.TILE_FLAG_WALL_WEST, Vector2i(-1, 0), _Const.TILE_FLAG_WALL_EAST],
]


## The choices of the Room tool. The Build tab fills one, and a test builds
## one.
class RoomOptions:
	## The floor inside. Empty keeps each floor.
	var floor_name := ""

	## The area inside. Empty keeps each area.
	var area_name := ""

	## Level the corners of the room to one height.
	var level_ground := true
	var base := Base.HIGHEST

	## Set Blocked on the ring of tiles around the room, for a dungeon. A
	## ring tile with a wall bit is part of another room and stays open.
	var block_outside := false

	## The wall style of each border tile. Empty keeps each style.
	var wall_style := ""


## The choices of the Roof tool. The Build tab fills one, and a test builds
## one.
class RoofOptions:
	var shape := RoofShapes.Shape.GABLE
	var pitch := RoofShapes.PITCH_DEFAULT

	## Tiles past each wall.
	var overhang := 1

	## Quarter turns clockwise: the ridge of a gable, the low edge of a shed.
	var turn := 0

	## A roof floor type, a row of [code]TILE_ROOF_FLOOR_TYPES[/code].
	var floor_name: String = _Const.TILE_ROOF_FLOOR_TYPES[0]


# ─── Edges ──────────────────────────────────────────────────────────────────

## The edge nearest to `point`, a point in tile space: `[tile, wall bit]`.
static func edge_at(point: Vector2) -> Array:
	var tile := ChunkSet.tile_at(point)
	var offset := point - Vector2(tile)

	if absf(offset.x) > absf(offset.y):
		var bit: int = _Const.TILE_FLAG_WALL_EAST if offset.x > 0.0 \
			else _Const.TILE_FLAG_WALL_WEST

		return [tile, bit]

	var bit: int = _Const.TILE_FLAG_WALL_NORTH if offset.y > 0.0 \
		else _Const.TILE_FLAG_WALL_SOUTH

	return [tile, bit]


## The tile across the edge `bit` of `tile`, and the bit of that tile on the
## same edge: `[tile, bit]`.
static func across(tile: Vector2i, bit: int) -> Array:
	for edge: Array in EDGES:
		if edge[0] == bit:
			return [tile + edge[1], edge[2]]

	return [tile, bit]


## The corner nearest to `point`, a point in tile space. Corner (x, y) is
## the south-west corner of tile (x, y).
static func corner_at(point: Vector2) -> Vector2i:
	return Vector2i(roundi(point.x + 0.5), roundi(point.y + 0.5))


## The end of a wall line from `start`, kept to the axis of the larger move.
static func snap_line(start: Vector2i, end: Vector2i) -> Vector2i:
	var move := end - start

	if absi(move.x) >= absi(move.y):
		return Vector2i(end.x, start.y)

	return Vector2i(start.x, end.y)


## The edges of a line from corner `start` to corner `end`, on one axis, as
## `[tile, bit]` on the default side: north of a line along x, east of a
## line along y.
static func line_edges(start: Vector2i, end: Vector2i) -> Array:
	var stop := snap_line(start, end)
	var edges := []

	if stop.y == start.y:
		for x: int in range(mini(start.x, stop.x), maxi(start.x, stop.x)):
			edges.append([Vector2i(x, start.y), _Const.TILE_FLAG_WALL_SOUTH])
	else:
		for y: int in range(mini(start.y, stop.y), maxi(start.y, stop.y)):
			edges.append([Vector2i(start.x, y), _Const.TILE_FLAG_WALL_WEST])

	return edges


# ─── Wall line and Doorway ──────────────────────────────────────────────────

## Draw walls along a line of corners, or with `remove` clear them on both
## sides. `style` is the wall style of each wall, or "" to keep the style of
## each tile. Returns the problem, or "".
static func wall_line(chunks: ChunkSet, edit: TerrainEdit, start: Vector2i,
		end: Vector2i, remove: bool, style: String = "") -> String:
	var edges := line_edges(start, end)

	if edges.is_empty():
		return "Drag along a tile edge to draw a line."

	for edge: Array in edges:
		if remove:
			_clear_edge(chunks, edit, edge[0], edge[1])
		else:
			_set_edge(chunks, edit, edge[0], edge[1], style)

	return ""


## Put a wall on the edge, on the side that is not void, in `style`. See the
## class comment.
static func _set_edge(chunks: ChunkSet, edit: TerrainEdit, tile: Vector2i,
		bit: int, style: String) -> void:
	var other := across(tile, bit)
	var side := [tile, bit]

	if _is_void(chunks, tile) and not _is_void(chunks, other[0]):
		side = other

	if not chunks.has_tile(side[0]):
		return

	edit.apply_flags(chunks, side[0], chunks.get_flags(side[0]) | side[1])
	_style_tile(chunks, edit, side[0], style)


## Give `tile` the wall style `style`. An empty style, or the style that the
## tile has, records no change.
static func _style_tile(chunks: ChunkSet, edit: TerrainEdit, tile: Vector2i,
		style: String) -> void:
	if not style.is_empty() and chunks.get_wall_style(tile) != style:
		edit.apply_wall_style(chunks, tile, style)


## Clear the wall on both sides of the edge.
static func _clear_edge(chunks: ChunkSet, edit: TerrainEdit, tile: Vector2i,
		bit: int) -> void:
	for side: Array in [[tile, bit], across(tile, bit)]:
		var flags := chunks.get_flags(side[0])

		if chunks.has_tile(side[0]) and flags & side[1]:
			edit.apply_flags(chunks, side[0], flags & ~side[1])


static func _is_void(chunks: ChunkSet, tile: Vector2i) -> bool:
	return chunks.get_floor(tile) == _Const.TILE_VOID_FLOOR


## Open a doorway: clear the wall on both sides of the edge. With
## `add_back`, put the wall back on the side of `tile`.
static func doorway(chunks: ChunkSet, edit: TerrainEdit, tile: Vector2i,
		bit: int, add_back: bool) -> String:
	if add_back:
		edit.apply_flags(chunks, tile, chunks.get_flags(tile) | bit)
		return ""

	var other: Array = across(tile, bit)

	if not (chunks.get_flags(tile) & bit or chunks.get_flags(other[0]) & other[1]):
		return "No wall on that edge. Click nearer to a wall."

	_clear_edge(chunks, edit, tile, bit)

	return ""


# ─── Room ───────────────────────────────────────────────────────────────────

## Build a room on `rect` of tiles: the levelled ground, the floor, the area,
## walls on the inner edges of the border, and the Blocked ring, as
## `options` say. With `remove`, clear every wall in the rectangle instead.
static func room(chunks: ChunkSet, edit: TerrainEdit, rect: Rect2i,
		options: RoomOptions, remove: bool) -> String:
	if rect.size.x < 1 or rect.size.y < 1:
		return "Drag a rectangle of one tile or more."

	if remove:
		for tile: Vector2i in rect_tiles(rect):
			edit.apply_flags(chunks, tile, chunks.get_flags(tile) & ~_Const.TILE_FLAGS_WALLS)

		return ""

	if options.level_ground:
		edit.apply_heights(chunks, level_changes(chunks, rect, options.base))

	for tile: Vector2i in rect_tiles(rect):
		_room_tile(chunks, edit, tile, rect, options)

	if options.block_outside:
		_block_ring(chunks, edit, rect)

	return ""


## The floor, the area, and the border walls of one tile of a room.
static func _room_tile(chunks: ChunkSet, edit: TerrainEdit, tile: Vector2i,
		rect: Rect2i, options: RoomOptions) -> void:
	if not options.floor_name.is_empty():
		paint_floor(chunks, edit, tile, options.floor_name)

	if not options.area_name.is_empty():
		edit.apply_area(chunks, tile, options.area_name)

	var walls := border_bits(tile, rect)

	if walls == 0:
		return

	edit.apply_flags(chunks, tile, chunks.get_flags(tile) | walls)
	_style_tile(chunks, edit, tile, options.wall_style)


## Paint `style` on each tile of `tiles` that has a wall bit. A tile with no
## wall keeps its style. Returns the number of tiles that changed.
static func paint_wall_style(chunks: ChunkSet, edit: TerrainEdit,
		tiles: Array[Vector2i], style: String) -> int:
	var changed := 0

	for tile: Vector2i in tiles:
		if chunks.get_flags(tile) & _Const.TILE_FLAGS_WALLS == 0:
			continue

		if chunks.get_wall_style(tile) != style:
			_style_tile(chunks, edit, tile, style)
			changed += 1

	return changed


## The wall bits of `tile` on the inner edges of the border of `rect`.
static func border_bits(tile: Vector2i, rect: Rect2i) -> int:
	var bits := 0
	var high := rect.end - Vector2i.ONE

	if tile.x == rect.position.x:
		bits |= _Const.TILE_FLAG_WALL_WEST

	if tile.x == high.x:
		bits |= _Const.TILE_FLAG_WALL_EAST

	if tile.y == rect.position.y:
		bits |= _Const.TILE_FLAG_WALL_SOUTH

	if tile.y == high.y:
		bits |= _Const.TILE_FLAG_WALL_NORTH

	return bits


## Set Blocked on each tile of the ring around `rect` that is open and has
## no wall bit.
static func _block_ring(chunks: ChunkSet, edit: TerrainEdit, rect: Rect2i) -> void:
	var outer := rect.grow(1)

	for tile: Vector2i in rect_tiles(outer):
		if rect.has_point(tile) or not chunks.has_tile(tile):
			continue

		var flags := chunks.get_flags(tile)

		if flags & (_Const.TILE_FLAGS_WALLS | _Const.TILE_FLAG_BLOCKED) == 0:
			edit.apply_flags(chunks, tile, flags | _Const.TILE_FLAG_BLOCKED)


## A floor paint, and the Blocked flag that a void tile needs (Phase 7c).
static func paint_floor(chunks: ChunkSet, edit: TerrainEdit, tile: Vector2i,
		floor_name: String) -> void:
	var flags := TerrainBrushes.flags_after_floor(chunks.get_floor(tile),
		floor_name, chunks.get_flags(tile))

	edit.apply_floor(chunks, tile, floor_name)

	if flags != chunks.get_flags(tile):
		edit.apply_flags(chunks, tile, flags)


## Every tile of `rect`, south row first.
static func rect_tiles(rect: Rect2i) -> Array[Vector2i]:
	var tiles: Array[Vector2i] = []

	for y: int in range(rect.position.y, rect.end.y):
		for x: int in range(rect.position.x, rect.end.x):
			tiles.append(Vector2i(x, y))

	return tiles


## Every corner of the tiles of `rect`.
static func rect_corners(rect: Rect2i) -> Array[Vector2i]:
	var corners: Array[Vector2i] = []

	for y: int in range(rect.position.y, rect.end.y + 1):
		for x: int in range(rect.position.x, rect.end.x + 1):
			corners.append(Vector2i(x, y))

	return corners


## `{corner: height}` that sets each editable corner of `rect` to the base.
static func level_changes(chunks: ChunkSet, rect: Rect2i, base: Base) -> Dictionary:
	var corners := rect_corners(rect)
	var target := base_height(chunks, corners, base)
	var changes := {}

	for corner: Vector2i in corners:
		if chunks.corner_is_editable(corner):
			changes[corner] = target

	return changes


## The base height of `corners` by the `base` rule. The average rounds.
static func base_height(chunks: ChunkSet, corners: Array[Vector2i], base: Base) -> int:
	var heights: Array[int] = []

	for corner: Vector2i in corners:
		heights.append(chunks.get_corner(corner))

	match base:
		Base.LOWEST:
			return heights.min()
		Base.AVERAGE:
			var total := 0

			for height: int in heights:
				total += height

			return roundi(float(total) / heights.size())

	return heights.max()


# ─── Level above and Stairs ─────────────────────────────────────────────────

## Floor `tiles` on the plane above `plane`, flat at the highest corner of
## the tiles plus one plane rise. An empty `floor_name` takes the floor of
## each tile below. With `remove`, set the tiles above back to void and
## Blocked.
static func level_above(sets: Dictionary, edit: TerrainEdit, plane: int,
		tiles: Array[Vector2i], floor_name: String, remove: bool) -> String:
	var below: ChunkSet = sets.get(plane)
	var above: ChunkSet = sets.get(plane + 1)

	if above == null:
		return "Plane %d is the top plane. No level goes above it." % plane

	if tiles.is_empty():
		return "No tile to build a level on."

	if remove:
		for tile: Vector2i in tiles:
			edit.apply_floor(above, tile, _Const.TILE_VOID_FLOOR)
			edit.apply_flags(above, tile, _Const.TILE_FLAG_BLOCKED)

		return ""

	var target := base_height(below, tile_corners(tiles), Base.HIGHEST) \
		+ TerrainWorld.NEW_PLANE_RISE

	edit.apply_heights(above, _flat_changes(above, tile_corners(tiles), target))

	for tile: Vector2i in tiles:
		var floor_here := floor_name

		if floor_here.is_empty():
			floor_here = below.get_floor(tile)

		if floor_here == _Const.TILE_VOID_FLOOR:
			floor_here = _Const.TILE_DEFAULT_FLOOR

		paint_floor(above, edit, tile, floor_here)

	return ""


## Every corner of every tile of `tiles`, once each.
static func tile_corners(tiles: Array[Vector2i]) -> Array[Vector2i]:
	var found := {}

	for tile: Vector2i in tiles:
		for offset: Vector2i in [Vector2i(0, 0), Vector2i(1, 0), Vector2i(0, 1),
				Vector2i(1, 1)]:
			found[tile + offset] = true

	var corners: Array[Vector2i] = []

	corners.assign(found.keys())

	return corners


static func _flat_changes(chunks: ChunkSet, corners: Array[Vector2i],
		target: int) -> Dictionary:
	var changes := {}

	for corner: Vector2i in corners:
		if chunks.corner_is_editable(corner):
			changes[corner] = target

	return changes


## Up kind to down kind: each climb kind that leads only up, and the kind
## that leads only down from the plane above. The pair shares a name: the
## up kind ends in "_up", and its twin ends in "_down".
static func climb_pairs() -> Dictionary:
	var pairs := {}
	var up_suffix := "_" + _Const.CLIMB_UP

	for kind: String in _Const.OBJECT_KIND_CLIMBS:
		if _Const.OBJECT_KIND_CLIMBS[kind] != [_Const.CLIMB_UP] \
				or not kind.ends_with(up_suffix):
			continue

		var twin := kind.trim_suffix(up_suffix) + "_" + _Const.CLIMB_DOWN

		if _Const.OBJECT_KIND_CLIMBS.get(twin, []) == [_Const.CLIMB_DOWN]:
			pairs[kind] = twin

	return pairs


## Place the climb pair on `tile`: `up_kind` on `plane` and its twin on the
## plane above. A void landing gets a floor first, flat at one plane rise.
## A tile that holds the pair refuses. With `remove`, take the pair away.
static func stairs(sets: Dictionary, edit: TerrainEdit, plane: int, tile: Vector2i,
		up_kind: String, floor_name: String, remove: bool) -> String:
	var below: ChunkSet = sets.get(plane)
	var above: ChunkSet = sets.get(plane + 1)
	var down_kind: String = climb_pairs().get(up_kind, "")

	if above == null:
		return "Plane %d is the top plane. No stairs lead above it." % plane

	if down_kind.is_empty():
		return "%s has no twin that leads down." % up_kind

	if remove:
		_remove_kind(below, edit, tile, up_kind)
		_remove_kind(above, edit, tile, down_kind)
		return ""

	var has_up := _has_kind(below, tile, up_kind)
	var has_down := _has_kind(above, tile, down_kind)

	if has_up and has_down:
		return "A %s already stands on %s. Shift removes it." % [up_kind, tile]

	if _is_void(above, tile):
		var tiles: Array[Vector2i] = [tile]

		level_above(sets, edit, plane, tiles, floor_name, false)

	# A second click must not stack a second pair. A half pair gets its twin.
	if not has_up:
		edit.add_object(below, tile, up_kind, 0)

	if not has_down:
		edit.add_object(above, tile, down_kind, 0)

	return ""


static func _has_kind(chunks: ChunkSet, tile: Vector2i, kind: String) -> bool:
	for thing: Dictionary in chunks.objects_at(tile):
		if thing["kind"] == kind:
			return true

	return false


# ─── Decor ──────────────────────────────────────────────────────────────────

## Every decor kind, in the order of the server table.
static func decor_kinds() -> Array[String]:
	var kinds: Array[String] = []

	for kind: String in _Const.OBJECT_KINDS:
		if _Const.OBJECT_KINDS[kind] == _Const.OBJECT_CATEGORY_DECOR:
			kinds.append(kind)

	return kinds


## The decor on `tile` as `{kind, rotation, text}`, or an empty Dictionary.
static func decor_at(chunks: ChunkSet, tile: Vector2i) -> Dictionary:
	for thing: Dictionary in chunks.objects_at(tile):
		if _Const.OBJECT_KINDS.get(thing["kind"], "") == _Const.OBJECT_CATEGORY_DECOR:
			return thing

	return {}


## Place `kind` on `tile` at `rotation`. A tile holds one decor, so a place on
## a tile with decor replaces it. With `remove`, take the decor off the tile.
## Returns the problem, or "".
static func decor(chunks: ChunkSet, edit: TerrainEdit, tile: Vector2i, kind: String,
		rotation: int, remove: bool) -> String:
	if not chunks.has_tile(tile):
		return "No loaded chunk holds %s." % tile

	var standing := decor_at(chunks, tile)

	if remove:
		if standing.is_empty():
			return "No decor on %s." % tile

		_remove_thing(chunks, edit, tile, standing)
		return ""

	if kind.is_empty():
		return "The server names no decor kind."

	if _is_void(chunks, tile):
		return "%s is void. Decor stands on a floor." % tile

	if standing.get("kind", "") == kind and standing.get("rotation", -1) == rotation:
		return ""

	if not standing.is_empty():
		_remove_thing(chunks, edit, tile, standing)

	edit.add_object(chunks, tile, kind, rotation)

	return ""


static func _remove_thing(chunks: ChunkSet, edit: TerrainEdit, tile: Vector2i,
		thing: Dictionary) -> void:
	edit.remove_object(chunks, tile, thing["kind"], thing["rotation"], thing["text"])


## Remove the first object of `kind` on `tile`, at any rotation.
static func _remove_kind(chunks: ChunkSet, edit: TerrainEdit, tile: Vector2i,
		kind: String) -> void:
	for thing: Dictionary in chunks.objects_at(tile):
		if thing["kind"] == kind:
			edit.remove_object(chunks, tile, kind, thing["rotation"], thing["text"])
			return


# ─── Roof ───────────────────────────────────────────────────────────────────

## The rectangle of a room that a fill found: `{rect, problem}`. A roof
## covers a rectangle, so a fill that is not one is a problem.
static func fill_rect(found: Dictionary) -> Dictionary:
	var tiles: Array[Vector2i] = found["tiles"]

	if not found["closed"] or tiles.is_empty():
		return {"rect": Rect2i(), "problem":
			"Not a room: the fill found no closed walls. Drag a rectangle."}

	var low := tiles[0]
	var high := tiles[0]

	for tile: Vector2i in tiles:
		low = low.min(tile)
		high = high.max(tile)

	var rect := Rect2i(low, high - low + Vector2i.ONE)

	if rect.get_area() != tiles.size():
		return {"rect": rect, "problem":
			"The room is not a rectangle. Drag a rectangle for each part of its roof."}

	return {"rect": rect, "problem": ""}


## The plan of a roof over `rect` of `plane`: `{problem, rect, heights}`. It
## changes nothing. `rect` grows by the overhang. `heights` maps each corner
## of it to its height, also with a problem. The outline of the Build tab
## draws the plan. A problem makes the outline red. [method roof] writes a
## plan with no problem only.
static func roof_plan(sets: Dictionary, plane: int, rect: Rect2i,
		options: RoofOptions) -> Dictionary:
	var roof_rect := rect.grow(options.overhang)
	var plan := {"problem": "", "rect": roof_rect, "heights": {}}
	var below: ChunkSet = sets.get(plane)
	var above: ChunkSet = sets.get(plane + 1)

	if above == null:
		plan["problem"] = "Plane %d is the top plane. No roof goes above it." % plane
		return plan

	if rect.size.x < 1 or rect.size.y < 1:
		plan["problem"] = "Drag a rectangle of one tile or more."
		return plan

	# A refused plan keeps its heights, so the outline draws it in red.
	plan["problem"] = _roof_refusal(above, roof_rect)
	plan["heights"] = _roof_heights(below, rect, roof_rect, options)

	return plan


## The reason that no roof goes on `roof_rect` of the plane above, or "".
static func _roof_refusal(above: ChunkSet, roof_rect: Rect2i) -> String:
	for corner: Vector2i in rect_corners(roof_rect):
		if not above.corner_is_editable(corner):
			return "The roof reaches the locked edge of the block at %s. Move the block." \
				% corner

	for tile: Vector2i in rect_tiles(roof_rect):
		var floor_here := above.get_floor(tile)

		if floor_here != _Const.TILE_VOID_FLOOR \
				and not _Const.TILE_ROOF_FLOOR_TYPES.has(floor_here):
			return "Plane %d has a %s floor at %s. Edit plane %d to roof that level." \
				% [above.plane, floor_here, tile, above.plane]

	return ""


## `{corner: height}` of each corner of `roof_rect`. The roof meets the
## walls of `rect` at one plane rise above the highest corner of the room.
static func _roof_heights(below: ChunkSet, rect: Rect2i, roof_rect: Rect2i,
		options: RoofOptions) -> Dictionary:
	var eave := base_height(below, rect_corners(rect), Base.HIGHEST) \
		+ TerrainWorld.NEW_PLANE_RISE
	var outer := RoofShapes.outer_eave(eave, options.shape, options.pitch,
		options.overhang)
	var rises := RoofShapes.rises(roof_rect.size, options.shape, options.pitch,
		options.turn)
	var side := roof_rect.size.x + 1
	var heights := {}

	for corner: Vector2i in rect_corners(roof_rect):
		var local := corner - roof_rect.position
		var height := outer + rises[local.y * side + local.x]

		heights[corner] = clampi(height, _Const.CHUNK_HEIGHT_MIN, _Const.CHUNK_HEIGHT_MAX)

	return heights


## Put a roof over `rect` of `plane`, on the plane above: the corner heights
## of the shape, the roof floor type, and the Blocked flag on each tile of
## the rectangle and its overhang. With `remove`, set each roof tile over the
## rectangle and its overhang back to void and Blocked.
static func roof(sets: Dictionary, edit: TerrainEdit, plane: int, rect: Rect2i,
		options: RoofOptions, remove: bool) -> String:
	if remove:
		return _remove_roof(sets.get(plane + 1), edit, rect.grow(options.overhang))

	var plan := roof_plan(sets, plane, rect, options)

	if not plan["problem"].is_empty():
		return plan["problem"]

	var above: ChunkSet = sets[plane + 1]

	edit.apply_heights(above, plan["heights"])

	for tile: Vector2i in rect_tiles(plan["rect"]):
		paint_floor(above, edit, tile, options.floor_name)

		var flags := above.get_flags(tile)

		if not flags & _Const.TILE_FLAG_BLOCKED:
			edit.apply_flags(above, tile, flags | _Const.TILE_FLAG_BLOCKED)

	return ""


static func _remove_roof(above: ChunkSet, edit: TerrainEdit, roof_rect: Rect2i) -> String:
	if above == null:
		return "No plane above this one holds a roof."

	var removed := 0

	for tile: Vector2i in rect_tiles(roof_rect):
		if above.has_tile(tile) \
				and _Const.TILE_ROOF_FLOOR_TYPES.has(above.get_floor(tile)):
			paint_floor(above, edit, tile, _Const.TILE_VOID_FLOOR)
			removed += 1

	if removed == 0:
		return "No roof on plane %d over that rectangle." % above.plane

	return ""
