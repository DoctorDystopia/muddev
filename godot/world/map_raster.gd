class_name MapRaster
extends RefCounted
## The colour rule of both maps, and the images that they draw the ground from.
##
## ## One rule for two maps
##
## The minimap draws the chunks that [WorldState] holds. The world map draws
## the world map summaries of [WorldMapState]. Both must show one colour for
## one tile, so both ask [method tile_colour]:
##
##   - A walkable tile shows the colour of its floor type, from
##     [FloorPalette], the palette of the 3D ground.
##   - A blocked tile or a water tile shows that colour darker.
##   - A void tile has no floor, so it is clear (Phase 7b).
##
## ## One pixel for each tile
##
## A map draws its ground as one [ImageTexture] with the nearest filter, not
## as one rect for each tile. At the widest zoom of the minimap that is 6,561
## rects on each redraw, and the dots redraw on every entity message. An image
## is built again only when the ground changes.
##
## Row 0 of an image is NORTH. Grid Y grows to the north and image Y grows
## down, so each writer here makes that flip one time.

const _Const := preload("res://autoload/blackout_constants.gd")

## How much darker a tile that no one can stand on is drawn, from 0 to 1.
const UNWALKABLE_DARKEN := 0.55

const CLEAR := Color(0, 0, 0, 0)

## WORLD_MAP_ALPHABET character -> its colour. Built on the first use.
static var _class_colours := {}


## The colour of one tile, from its floor type and whether anyone can stand
## on it. Clear for a void tile.
static func tile_colour(floor_name: String, unwalkable: bool) -> Color:
	if floor_name == _Const.TILE_VOID_FLOOR:
		return CLEAR

	var colour := FloorPalette.color_of(floor_name)

	if unwalkable:
		colour = colour.darkened(UNWALKABLE_DARKEN)

	return colour


## The colour of one tile of a [ChunkSet]. Clear when its chunk is not loaded.
static func chunk_set_colour(chunks: ChunkSet, tile: Vector2i) -> Color:
	if not chunks.has_tile(tile):
		return CLEAR

	var unwalkable := (chunks.get_flags(tile) & _Const.TILE_FLAGS_UNWALKABLE) != 0

	return tile_colour(chunks.get_floor(tile), unwalkable)


## The colour of one character of a world map summary. The server owns the
## encoding (`statefeed/worldmap.py`): index = floor_index * 2 + unwalkable.
## A character outside the alphabet is clear.
static func class_colour(character: String) -> Color:
	if _class_colours.is_empty():
		_build_class_colours()

	return _class_colours.get(character, CLEAR)


## An image of one chunk, one pixel for each tile, row 0 north. The minimap
## builds one for each chunk when it arrives, and draws the part of it that
## the window covers.
static func chunk_image(chunk: ChunkFile) -> Image:
	var size: int = _Const.CHUNK_SIZE
	var image := Image.create_empty(size, size, false, Image.FORMAT_RGBA8)
	var seen := {}

	for index: int in mini(chunk.floors.size(), size * size):
		var floor_index := chunk.floors[index]
		var unwalkable := (chunk.flags[index] & _Const.TILE_FLAGS_UNWALKABLE) != 0
		var key := floor_index * 2 + int(unwalkable)

		# A chunk holds a few floor types, so each colour is worked out once.
		if not seen.has(key):
			seen[key] = tile_colour(chunk.floor_names[floor_index], unwalkable)

		@warning_ignore("integer_division")
		image.set_pixel(index % size, size - 1 - index / size, seen[key])

	return image


## An image of a square window of a [ChunkSet], one pixel for each tile.
## `low` is the south-west tile of the window, and `side` is its width.
static func window_image(chunks: ChunkSet, low: Vector2i, side: int) -> Image:
	var image := Image.create_empty(side, side, false, Image.FORMAT_RGBA8)

	for dy: int in side:
		for dx: int in side:
			var colour := chunk_set_colour(chunks, low + Vector2i(dx, dy))

			image.set_pixel(dx, side - 1 - dy, colour)

	return image


## Write one world map summary into an image of a whole plane. `origin` is
## the tile at the south-west corner of the image. The summary covers the
## chunk whose south-west tile is `chunk_low`.
static func paint_summary(image: Image, tiles: String, chunk_low: Vector2i,
		origin: Vector2i) -> void:
	var size: int = _Const.CHUNK_SIZE
	var top := image.get_height() - 1

	for index: int in mini(tiles.length(), size * size):
		@warning_ignore("integer_division")
		var tile := chunk_low + Vector2i(index % size, index / size)
		var at := tile - origin

		image.set_pixel(at.x, top - at.y, class_colour(tiles[index]))


static func _build_class_colours() -> void:
	var alphabet: String = _Const.WORLD_MAP_ALPHABET
	var floors: Array = _Const.TILE_FLOOR_TYPES

	for floor_index: int in floors.size():
		for unwalkable: int in 2:
			var at := floor_index * 2 + unwalkable

			if at >= alphabet.length():
				return

			_class_colours[alphabet[at]] = tile_colour(
				floors[floor_index], unwalkable == 1)
