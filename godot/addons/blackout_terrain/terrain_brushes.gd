class_name TerrainBrushes
extends RefCounted
## The height brushes of the terrain editor, as pure functions.
##
## Each brush reads a [ChunkSet] and returns the corners that it changes, as
## `{world corner (Vector2i): new height (int)}`. It writes nothing. The
## plugin applies the result through a [TerrainEdit], so undo holds the same
## change. A test can call a brush with no editor.
##
## Every height is an integer number of height steps (DESIGN-0011 section
## 6.4). A brush never writes a corner that [method ChunkSet.corner_is_editable]
## refuses, so it cannot open a seam with a chunk that is not loaded.
##
## ## Credit
##
## The set of brushes and the stroke model (one stroke is one undo entry, a
## held button keeps sculpting) follow Low Poly Terrain Builder by 78sForge,
## MIT licence, https://github.com/78sForge/LowPolyTerrainBuilder. The code
## here is new: that plugin sculpts float heights on a Delaunay mesh, and this
## editor sculpts integer corners on the tile grid.

const _Const := preload("res://autoload/blackout_constants.gd")

## A radius under this still reaches the corners of the tile under the brush.
const MIN_RADIUS := 0.75


## World corner `corner` as a point in tile space. It is the southwest corner
## of world tile `corner`.
static func corner_point(corner: Vector2i) -> Vector2:
	return Vector2(corner.x - 0.5, corner.y - 0.5)


## Every world corner within `radius` of `centre`, a point in tile space.
static func corners_in_circle(centre: Vector2, radius: float) -> Array[Vector2i]:
	var reach := maxf(radius, MIN_RADIUS)
	var low := Vector2i(floori(centre.x - reach), floori(centre.y - reach))
	var high := Vector2i(ceili(centre.x + reach) + 1, ceili(centre.y + reach) + 1)
	var found: Array[Vector2i] = []

	for y: int in range(low.y, high.y + 1):
		for x: int in range(low.x, high.x + 1):
			var corner := Vector2i(x, y)

			if corner_point(corner).distance_to(centre) <= reach:
				found.append(corner)

	return found


## Every world tile whose centre is within `radius` of `centre`. A radius
## under one tile gives the tile under the brush only.
static func tiles_in_circle(centre: Vector2, radius: float) -> Array[Vector2i]:
	var middle := ChunkSet.tile_at(centre)
	var found: Array[Vector2i] = []

	if radius < 1.0:
		found.append(middle)
		return found

	var reach := ceili(radius)

	for y: int in range(middle.y - reach, middle.y + reach + 1):
		for x: int in range(middle.x - reach, middle.x + reach + 1):
			if Vector2(x, y).distance_to(centre) <= radius:
				found.append(Vector2i(x, y))

	return found


## Raise every corner in the circle by `amount` steps. A negative amount
## lowers it.
static func raise(chunks: ChunkSet, centre: Vector2, radius: float,
		amount: int) -> Dictionary:
	var changes := {}

	for corner: Vector2i in corners_in_circle(centre, radius):
		if chunks.corner_is_editable(corner):
			changes[corner] = chunks.get_corner(corner) + amount

	return changes


## Move every corner in the circle toward `target`, by at most `strength`
## steps.
static func flatten(chunks: ChunkSet, centre: Vector2, radius: float,
		target: int, strength: int) -> Dictionary:
	var changes := {}

	for corner: Vector2i in corners_in_circle(centre, radius):
		if chunks.corner_is_editable(corner):
			var height := chunks.get_corner(corner)
			var moved := _toward(height, target, strength)

			if moved != height:
				changes[corner] = moved

	return changes


## Set every corner in the circle to the rounded mean of the nine corners
## around it. All reads happen before any write, so the order of the corners
## does not change the result.
static func smooth(chunks: ChunkSet, centre: Vector2, radius: float) -> Dictionary:
	var changes := {}

	for corner: Vector2i in corners_in_circle(centre, radius):
		if not chunks.corner_is_editable(corner):
			continue

		var height := chunks.get_corner(corner)
		var mean := roundi(_neighbour_mean(chunks, corner))

		if mean != height:
			changes[corner] = mean

	return changes


static func _neighbour_mean(chunks: ChunkSet, corner: Vector2i) -> float:
	var total := 0
	var count := 0

	for dy: int in range(-1, 2):
		for dx: int in range(-1, 2):
			var near := corner + Vector2i(dx, dy)

			if chunks.corner_is_loaded(near):
				total += chunks.get_corner(near)
				count += 1

	return float(total) / float(maxi(count, 1))


## A straight ramp from `start` to `end`, points in tile space. Each corner
## within `width` / 2 of the segment gets the height on the line from
## `start_height` to `end_height` at its place along the segment.
static func ramp(chunks: ChunkSet, start: Vector2, end: Vector2, width: float,
		start_height: int, end_height: int) -> Dictionary:
	var changes := {}
	var half := maxf(width * 0.5, MIN_RADIUS)
	var span := end - start
	var length_squared := maxf(span.length_squared(), 0.0001)
	var middle := (start + end) * 0.5
	var reach := span.length() * 0.5 + half

	for corner: Vector2i in corners_in_circle(middle, reach):
		var point := corner_point(corner)
		var along := clampf((point - start).dot(span) / length_squared, 0.0, 1.0)
		var nearest := start + span * along

		if point.distance_to(nearest) > half or not chunks.corner_is_editable(corner):
			continue

		var height := roundi(lerpf(start_height, end_height, along))

		if height != chunks.get_corner(corner):
			changes[corner] = height

	return changes


## The noise height of a world corner. It reads world coordinates, so two
## neighbour chunks filled at different times meet with no step.
static func noise_height(noise: Noise, corner: Vector2i, amplitude: int) -> int:
	var value := noise.get_noise_2d(corner.x, corner.y)

	return roundi(value * amplitude)


## Move every corner in the circle toward its noise height, by at most
## `strength` steps.
static func noise_brush(chunks: ChunkSet, centre: Vector2, radius: float,
		noise: Noise, amplitude: int, strength: int) -> Dictionary:
	var changes := {}

	for corner: Vector2i in corners_in_circle(centre, radius):
		if chunks.corner_is_editable(corner):
			var height := chunks.get_corner(corner)
			var target := noise_height(noise, corner, amplitude)
			var moved := _toward(height, target, strength)

			if moved != height:
				changes[corner] = moved

	return changes


## Set every editable corner of one chunk to its noise height.
static func noise_fill(chunks: ChunkSet, chunk_coord: Vector2i, noise: Noise,
		amplitude: int) -> Dictionary:
	var changes := {}
	var side: int = _Const.CHUNK_CORNERS_PER_SIDE
	var origin := chunk_coord * _Const.CHUNK_SIZE

	for j: int in side:
		for i: int in side:
			var corner := origin + Vector2i(i, j)

			if not chunks.corner_is_editable(corner):
				continue

			var target := noise_height(noise, corner, amplitude)

			if target != chunks.get_corner(corner):
				changes[corner] = target

	return changes


static func _toward(height: int, target: int, strength: int) -> int:
	var step := clampi(target - height, -strength, strength)

	return height + step
