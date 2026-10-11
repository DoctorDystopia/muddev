@tool
class_name StructurePlace
extends RefCounted
## The Place tool and the Delete key of the Build tab (DESIGN-0013 section
## 6.6). The Place tool writes a template copy into the chunk files. The
## Delete key clears the tiles of a tile selection.
##
## As in [StructureTools], no function calls the editor. `sets` maps a plane
## to its [ChunkSet], so `test_structure_template.tscn` tests each rule with
## no editor. Every write goes through a [TerrainEdit], so one click is one
## undo entry.
##
## ## The plan
##
## [method plan] says what a click writes, and changes nothing. The outline
## draws it, in one of three colours:
##
## | Colour | `problem` | `warning` | A click |
## |---|---|---|---|
## | Green | "" | "" | writes the copy |
## | Amber | "" | the reason | writes the copy |
## | Red | the reason | any | writes nothing |
##
## Four problems refuse a copy:
##
## - A covered tile holds an object. Alt replaces it.
## - A covered tile of a plane above has a floor.
## - A covered corner is on the locked edge of the block.
## - The copy reaches above the top plane.
##
## Two warnings let a copy go:
##
## - The levelling moves a corner more than one plane rise.
## - The blend ring reaches a structure that the copy does not cover.
##
## ## The ground under a copy (decision 10)
##
## The base height is the highest, the lowest, or the average corner of the
## covered tiles of plane 0, as the options say. Each covered corner goes to
## the base plus its relative height. Each corner of the blend ring at a
## distance d (1 to R) from a covered corner then moves toward the base:
##
## ```text
## new = base + round((old - base) * d / (R + 1))
## ```
##
## The distance is the Chebyshev distance of the tile grid.
##
## ## A move
##
## A move clears the tile selection and writes the copy, in one edit.
## `vacated` names the tiles that the move clears, as Vector3i(x, y, plane).
## The plan treats each one as clear: its objects do not refuse, and a tile
## of a plane above counts as void.
##
## ## Delete
##
## [method clear] takes the structure off each tile of a tile selection: its
## walls, its wall style, and its objects. A tile of the ground plane keeps
## its floor, its area, and its other flags, because it is ground. A tile of
## a plane above goes back to void and Blocked.

const _Const := preload("res://autoload/blackout_constants.gd")

## The largest blend ring, in tiles (decision 10).
const BLEND_MAX := 3


## The choices of the Place tool. The Build tab fills one, and a test builds
## one.
class Options:
	var base := StructureTools.Base.HIGHEST

	## The tiles of the blend ring, 0 to [constant BLEND_MAX].
	var blend := 1

	## Write the areas of the template. Off keeps the area of each tile.
	var areas := true

	## Replace the objects on a covered tile: Alt and a click.
	var replace := false


# ─── The plan ───────────────────────────────────────────────────────────────

## What a copy of `template` at `origin` on `plane` writes, with no edit.
## `origin` is the world tile under the south-west tile of the template.
## Returns `{problem, warning, base, heights, ring}`: `heights` maps each
## relative plane to `{world corner: height}`, and `ring` maps each corner of
## the blend ring to its height. See the class comment.
static func plan(sets: Dictionary, template: StructureTemplate, origin: Vector2i,
		plane: int, options: Options, vacated: Dictionary = {}) -> Dictionary:
	var result := {"problem": "", "warning": "", "base": 0, "heights": {}, "ring": {}}
	var ground: ChunkSet = sets.get(plane)

	result["problem"] = _top_problem(sets, template, plane)

	if not result["problem"].is_empty():
		return result

	var footprint := _world_corners(template, template.layers[0], origin)

	result["base"] = StructureTools.base_height(ground, footprint, options.base)
	result["problem"] = _tile_problem(sets, template, origin, plane, options, vacated)

	for layer: StructureTemplate.Layer in template.layers:
		result["heights"][layer.plane] = _layer_heights(template, layer, origin,
			result["base"])

	result["ring"] = blend_ring(ground, footprint, result["base"], options.blend)
	result["warning"] = _warning(sets, plane, result, footprint,
		_world_tiles(template, template.layers[0], origin), vacated)

	return result


## The reason that the planes of the copy do not fit, or "".
static func _top_problem(sets: Dictionary, template: StructureTemplate,
		plane: int) -> String:
	if template.layers.is_empty():
		return "The template covers no tile."

	var top := plane + template.top_plane()

	if sets.get(plane) == null or top > _Const.CHUNK_PLANE_MAX:
		return "The template reaches plane %d. The top plane is %d." % [top,
			_Const.CHUNK_PLANE_MAX]

	return ""


## The covered world tiles of `layer`, as a set.
static func _world_tiles(template: StructureTemplate, layer: StructureTemplate.Layer,
		origin: Vector2i) -> Dictionary:
	var tiles := {}

	for tile: Vector2i in template.covered_tiles(layer):
		tiles[origin + tile] = true

	return tiles


## The world corners of the covered tiles of `layer`.
static func _world_corners(template: StructureTemplate, layer: StructureTemplate.Layer,
		origin: Vector2i) -> Array[Vector2i]:
	var corners: Array[Vector2i] = []

	for corner: Vector2i in template.covered_corners(layer):
		corners.append(origin + corner)

	return corners


static func _layer_heights(template: StructureTemplate, layer: StructureTemplate.Layer,
		origin: Vector2i, base: int) -> Dictionary:
	var heights := {}

	for corner: Vector2i in template.covered_corners(layer):
		heights[origin + corner] = clampi(base + layer.heights[template.corner_index(corner)],
			_Const.CHUNK_HEIGHT_MIN, _Const.CHUNK_HEIGHT_MAX)

	return heights


## The first refusal of a covered tile or corner, or "".
static func _tile_problem(sets: Dictionary, template: StructureTemplate, origin: Vector2i,
		plane: int, options: Options, vacated: Dictionary) -> String:
	for layer: StructureTemplate.Layer in template.layers:
		var chunks: ChunkSet = sets[plane + layer.plane]

		for corner: Vector2i in _world_corners(template, layer, origin):
			if not chunks.corner_is_editable(corner):
				return "The footprint reaches the locked edge of the block at %s. Move the block." \
					% corner

		for tile: Vector2i in template.covered_tiles(layer):
			var problem := _covered_tile_problem(chunks, origin + tile, layer.plane,
				options, vacated)

			if not problem.is_empty():
				return problem

	return ""


static func _covered_tile_problem(chunks: ChunkSet, tile: Vector2i, relative: int,
		options: Options, vacated: Dictionary) -> String:
	if vacated.has(Vector3i(tile.x, tile.y, chunks.plane)):
		return ""

	var here := chunks.objects_at(tile)

	if not here.is_empty() and not options.replace:
		return "%s on plane %d holds a %s. Hold Alt and click to replace it." \
			% [tile, chunks.plane, here[0]["kind"]]

	var floor_here := chunks.get_floor(tile)

	if relative > 0 and floor_here != _Const.TILE_VOID_FLOOR:
		return "Plane %d has a %s floor at %s. Delete it first, or move the footprint." \
			% [chunks.plane, floor_here, tile]

	return ""


## The first warning of the plan, or "".
static func _warning(sets: Dictionary, plane: int, result: Dictionary,
		footprint: Array[Vector2i], covered: Dictionary, vacated: Dictionary) -> String:
	var ground: ChunkSet = sets[plane]
	var heights: Dictionary = result["heights"].get(0, {})

	for corner: Vector2i in footprint:
		var move := absi(heights.get(corner, 0) - ground.get_corner(corner))

		if move > TerrainWorld.NEW_PLANE_RISE:
			return "The levelling moves corner %s by %d height steps, more than one plane rise." \
				% [corner, move]

	for corner: Vector2i in result["ring"]:
		var tile: Variant = _structure_tile_at(sets, plane, corner, covered, vacated)

		if tile != null:
			return "The blend ring reaches the structure at %s." % tile

	return ""


## A tile of a structure that has `corner`, and that the copy does not
## cover, or null. `covered` holds the covered world tiles of plane 0.
static func _structure_tile_at(sets: Dictionary, plane: int, corner: Vector2i,
		covered: Dictionary, vacated: Dictionary) -> Variant:
	var ground: ChunkSet = sets[plane]
	var above: ChunkSet = sets.get(plane + 1)

	for tile: Vector2i in TerrainBrushes.corner_tiles(corner):
		if covered.has(tile) or vacated.has(Vector3i(tile.x, tile.y, plane)):
			continue

		if TerrainBrushes.is_structure_tile(ground, above, tile):
			return tile

	return null


## `{corner: height}` of the blend ring of `footprint`, a set of world
## corners, `rings` tiles wide. Each corner moves toward `base` by the rule
## of the class comment. A corner that is not editable stays out.
static func blend_ring(chunks: ChunkSet, footprint: Array[Vector2i], base: int,
		rings: int) -> Dictionary:
	var changes := {}
	var seen := {}
	var edge := footprint.duplicate()

	for corner: Vector2i in footprint:
		seen[corner] = true

	for distance: int in range(1, rings + 1):
		var next: Array[Vector2i] = []

		for corner: Vector2i in edge:
			for step: Vector2i in _NEIGHBOURS:
				var near: Vector2i = corner + step

				if not seen.has(near):
					seen[near] = true
					next.append(near)

		for corner: Vector2i in next:
			if chunks.corner_is_editable(corner):
				var old := chunks.get_corner(corner)

				changes[corner] = base + roundi(float((old - base) * distance) / (rings + 1))

		edge = next

	return changes


## The eight corners around a corner: the Chebyshev step.
const _NEIGHBOURS := [Vector2i(-1, -1), Vector2i(0, -1), Vector2i(1, -1), Vector2i(-1, 0),
	Vector2i(1, 0), Vector2i(-1, 1), Vector2i(0, 1), Vector2i(1, 1)]


# ─── The copy ───────────────────────────────────────────────────────────────

## Write a copy of `template` at `origin` on `plane`, through `edit`. Returns
## `{problem, warning, keys}`: `keys` is each covered tile that the copy
## wrote, as Vector3i(x, y, plane). A problem writes nothing.
static func place(sets: Dictionary, edit: TerrainEdit, template: StructureTemplate,
		origin: Vector2i, plane: int, options: Options,
		vacated: Dictionary = {}) -> Dictionary:
	var made := plan(sets, template, origin, plane, options, vacated)
	var result := {"problem": made["problem"], "warning": made["warning"], "keys": []}

	if not made["problem"].is_empty():
		return result

	edit.apply_heights(sets[plane], made["ring"])

	for layer: StructureTemplate.Layer in template.layers:
		var chunks: ChunkSet = sets[plane + layer.plane]

		edit.apply_heights(chunks, made["heights"][layer.plane])

		for tile: Vector2i in template.covered_tiles(layer):
			_write_tile(chunks, edit, template, layer, tile, origin, options)
			result["keys"].append(Vector3i(origin.x + tile.x, origin.y + tile.y, chunks.plane))

	return result


## The facts and the objects of one covered tile.
static func _write_tile(chunks: ChunkSet, edit: TerrainEdit, template: StructureTemplate,
		layer: StructureTemplate.Layer, tile: Vector2i, origin: Vector2i,
		options: Options) -> void:
	var at := origin + tile
	var index := template.tile_index(tile)

	edit.apply_floor(chunks, at, template.floor_names[layer.floors[index]])
	edit.apply_flags(chunks, at, layer.flags[index])
	edit.apply_wall_style(chunks, at, template.wall_names[layer.walls[index]])

	if options.areas:
		edit.apply_area(chunks, at, template.area_names[layer.areas[index]])

	for thing: Dictionary in chunks.objects_at(at):
		edit.remove_object(chunks, at, thing["kind"], thing["rotation"], thing["text"])

	for thing: Dictionary in template.objects_at(tile, layer.plane):
		edit.add_object(chunks, at, thing["kind"], thing["rotation"], thing["text"])


# ─── Delete ─────────────────────────────────────────────────────────────────

## Take the structure off each tile of `keys`, a set of Vector3i(x, y,
## plane). See "Delete" in the class comment. Returns the number of tiles
## that changed.
static func clear(sets: Dictionary, edit: TerrainEdit, keys: Dictionary) -> int:
	var changed := 0

	for at: Vector3i in keys:
		var chunks: ChunkSet = sets.get(at.z)
		var tile := Vector2i(at.x, at.y)

		if chunks == null or not chunks.has_tile(tile):
			continue

		var size_before := edit.size()

		_clear_tile(chunks, edit, tile)

		if edit.size() != size_before:
			changed += 1

	return changed


static func _clear_tile(chunks: ChunkSet, edit: TerrainEdit, tile: Vector2i) -> void:
	for thing: Dictionary in chunks.objects_at(tile):
		edit.remove_object(chunks, tile, thing["kind"], thing["rotation"], thing["text"])

	if chunks.get_wall_style(tile) != _Const.TILE_DEFAULT_WALL_STYLE:
		edit.apply_wall_style(chunks, tile, _Const.TILE_DEFAULT_WALL_STYLE)

	if chunks.plane == _Const.TILE_GROUND_PLANE:
		var flags := chunks.get_flags(tile)

		if flags & _Const.TILE_FLAGS_WALLS:
			edit.apply_flags(chunks, tile, flags & ~_Const.TILE_FLAGS_WALLS)

		return

	if chunks.get_floor(tile) != _Const.TILE_VOID_FLOOR:
		edit.apply_floor(chunks, tile, _Const.TILE_VOID_FLOOR)

	if chunks.get_flags(tile) != _Const.TILE_FLAG_BLOCKED:
		edit.apply_flags(chunks, tile, _Const.TILE_FLAG_BLOCKED)
