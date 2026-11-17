class_name ItemStage
extends SubViewport
## The picture of each item that one pane shows, drawn in 3D into ONE texture.
##
## The browser pane gives the inventory a whole second three.js scene, camera and
## renderer, and hit-tests meshes to work out what was clicked. This does the
## drawing half and none of the rest: the cells stay [Control]s, so Godot's own
## drag and drop keeps working — which [InventorySlotCell] calls the single
## largest thing the engine buys on this screen — and this only supplies each
## cell a picture of its item.
##
## ## One viewport, not one per cell
##
## The obvious build is a SubViewport per cell. With 32 carried slots and a
## dozen worn frames that is forty-odd render targets, each with its own camera,
## for forty thumbnails a centimetre across.
##
## Instead every item is laid out on a GRID in one 3D scene under one
## orthographic camera, and each cell displays its own rectangle of the result
## through an [AtlasTexture]. One render target, one camera, one pass.
##
## ## One picture for each item, made one time (11/16/2026)
##
## The stage is a picture cache. [method picture] gives the rectangle of one
## item. The key is the asset key and the family of the item, because those
## two decide what the stage draws. The first request builds the model and
## gives it a cell of the grid. Each later request gives the same rectangle
## and builds nothing. Thus, two stacks of one item show one rectangle.
##
## Before this date the pane cleared the stage on each snapshot and built
## each model again. A full bag cost 52 ms for each snapshot. A snapshot
## arrives on each pickup, each craft, and each shot that uses ammunition.
##
## The stage never drops a picture. The number of pictures is at most the
## number of different items in the game.
##
## ## The picture is static
##
## Each item stands at one fixed turn. The stage renders one time after a
## picture changes, and then it stops. Before this date each item made a slow
## spin, and the stage rendered on each frame: 225 draw calls for a full bag.
##
## ## The picture pose
##
## [PicturePose] gives the zoom, the offset, and the turn of each picture,
## by its asset key. An item with no row in the look file gets the default
## pose. The picture editor writes the look file. It calls
## [method redraw] after each change, so the author sees the change at once.
## The game reads the file at its start.
##
## ## The stage follows its sources
##
## A model that arrives late changes a picture. So does the figure set. The
## stage hears [signal MeshResolver.refreshed] and
## [signal FigureLibrary.changed], and it draws the item again in the same
## cell. The rectangle of the cell does not change. Thus, no pane builds its
## cells again for a picture.
##
## ## The layout is this file's, and only this file's
##
## Where a picture sits in the 3D grid, and therefore which pixels it owns,
## is decided here and nowhere else. A pane never names a cell of the grid.

## Pixels per cell in the render target. Small on purpose: this is drawn at
## thumbnail size, and the target is COLUMNS x rows of these.
const CELL_PIXELS := 96

## Cells per row in the 3D grid. Nothing to do with how many columns the Control
## grid shows -- this is only how the render target is packed.
const COLUMNS := 8

## The rows that the render target gains when the grid is full. A new size
## makes a new render target, so the stage grows by some rows at a time.
const GROW_ROWS := 4

## One world unit per cell, so a cell's world position is its grid position.
const CELL_WORLD := 1.0

## How much of its cell one item fills, on the longer side of its outline,
## at a zoom of 1. Two pixels a side stay empty, so the soft edge of an item
## never draws in the next cell. See [method _seen_outline].
const ITEM_FILL := 0.96

## How far back the camera sits. Any value clear of the items works; it is
## orthographic, so this changes nothing about the framing.
const CAMERA_DISTANCE := 4.0

## Lighting. Bright ambience plus one key light, because these are small
## silhouettes and a moody inventory is an unreadable one.
const AMBIENT_ENERGY := 1.1
const LIGHT_ENERGY := 1.4

## Between the asset key and the family in a picture key. Neither one can
## hold a line break.
const KEY_SEPARATOR := "\n"

var _camera: Camera3D
var _root: Node3D

## Where meshes come from, or null. See [method bind_meshes].
var _meshes: MeshResolver

## The worn looks of the gear editor, or null. See [method bind_figures].
var _figures: FigureLibrary

## picture key -> the index of its cell.
var _cells: Dictionary = {}

## The `[asset, family]` of each cell, by index.
var _sources: Array = []

## The rectangle of each cell, by index. Each cell of a pane that shows one
## item holds the same texture.
var _textures: Array[AtlasTexture] = []

## index -> the Node3D drawn for it. A cell whose item has no source yet has
## no entry.
var _items: Dictionary = {}

## index -> the hull of each mesh of its node: a list of `[points,
## transform]`. The outline of the node at a turn comes from these points,
## so a new picture pose builds no hull again. See [method _hulls_of].
var _hulls: Dictionary = {}

## How many cells the grid is currently sized for.
var _capacity := 0


func _init() -> void:
	# A WORLD OF ITS OWN, and this is not optional.
	#
	# `own_world_3d` defaults to FALSE, which means a SubViewport shares its
	# parent's World3D. Without this the item meshes are added to the same 3D
	# world the game runs in and the world pane's camera sees them: forty
	# swords and rocks in a neat grid, floating in the sky over the map. The
	# WorldEnvironment below leaks the same way and repaints the game's sky
	# black.
	#
	# Both were visible on screen the first time this ran, and neither is
	# anything the render target's size or transparency hints at.
	own_world_3d = true

	# Transparent, so a cell shows the panel behind it rather than a black
	# square wherever an item is not.
	transparent_bg = true

	# The stage renders only on request. See [method _render_soon].
	render_target_update_mode = SubViewport.UPDATE_DISABLED

	_root = Node3D.new()
	add_child(_root)

	_camera = Camera3D.new()
	_camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	_root.add_child(_camera)

	var light := DirectionalLight3D.new()
	light.light_energy = LIGHT_ENERGY
	light.rotation = Vector3(-0.9, -0.6, 0.0)
	_root.add_child(light)

	var environment := WorldEnvironment.new()
	var settings := Environment.new()

	settings.background_mode = Environment.BG_CANVAS
	settings.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	settings.ambient_light_color = Color(0.8, 0.85, 0.95)
	settings.ambient_light_energy = AMBIENT_ENERGY
	environment.environment = settings
	_root.add_child(environment)

	_resize(COLUMNS * GROW_ROWS)


## Take the source of the meshes, and follow it.
##
## A model that arrives later draws again each picture that it changes. Null
## is a normal argument: the stage then draws only a worn look.
func bind_meshes(resolver: MeshResolver) -> void:
	_meshes = resolver

	if _meshes != null:
		_meshes.refreshed.connect(_on_model_arrived)

	_draw_all()


## Take the figure library, and follow it.
##
## An item with no served model then draws its worn look (10/17/2026). The
## arrival of the figure set, or of a model of a part, draws each picture
## again.
func bind_figures(library: FigureLibrary) -> void:
	_figures = library

	if _figures != null:
		_figures.changed.connect(_draw_all)

	_draw_all()


## The picture of one item. `asset` and `family` are the server's, untouched.
##
## Three sources, in this order (10/17/2026):
##
## 1. The served model of the asset key, from the resolver.
## 2. The worn look of the item, from the figure library: the look of the
##    gear editor, which the hand holds also.
## 3. The rest of the mesh ladder: the family model, then the family shape.
##
## A served model that is not in hand yet starts its fetch. The worn look
## stands in until the file arrives.
##
## The first request for an item builds its model. Each later request gives
## the same texture. An item with no source yet gets an empty rectangle,
## which fills when its source arrives.
func picture(asset: String, family: String) -> AtlasTexture:
	var key := asset + KEY_SEPARATOR + family

	if not _cells.has(key):
		_cells[key] = _add_cell(asset, family)

	var index: int = _cells[key]

	return _textures[index]


## How many pictures the stage holds. For tests.
func picture_count() -> int:
	return _sources.size()


## Where cell `index` sits in the 3D grid, in world units.
##
## The first row is at the top and the grid grows down. Thus, a cell keeps
## its place when the grid gains rows, and only the camera moves. Y is
## negated because grid rows run DOWN the texture while world Y runs up.
func cell_centre(index: int) -> Vector3:
	var column := index % COLUMNS
	@warning_ignore("integer_division")
	var row := index / COLUMNS

	return Vector3(
		(float(column) + 0.5 - (float(COLUMNS) * 0.5)) * CELL_WORLD,
		-(float(row) + 0.5) * CELL_WORLD,
		0.0)


## Give each picture of one asset key the picture pose of now. The
## rectangle of each picture stays, and so does its model: only the place of
## the model changes. For the picture editor, after a change of the pose.
func redraw(asset: String) -> void:
	var changed := false

	for index: int in _sources.size():
		if str(_sources[index][0]) == asset:
			_place(index)
			changed = true

	if changed:
		_render_soon()


## Give every picture the picture pose of now. For the picture editor,
## after it reads the look file again.
func redraw_all() -> void:
	for index: int in _sources.size():
		_place(index)

	_render_soon()


# ─── Private ─────────────────────────────────────────────────────────────────

## Give one new item the next cell of the grid, and draw it there.
func _add_cell(asset: String, family: String) -> int:
	var index := _sources.size()

	if index >= _capacity:
		_resize(_capacity + (COLUMNS * GROW_ROWS))

	_sources.append([asset, family])
	_textures.append(_texture_at(index))
	_draw(index)
	_render_soon()

	return index


## The rectangle of one cell: an [AtlasTexture] over the texture of this
## viewport. Every cell shares one render target and none owns a copy.
func _texture_at(index: int) -> AtlasTexture:
	var atlas := AtlasTexture.new()

	atlas.atlas = get_texture()
	@warning_ignore("integer_division")
	atlas.region = Rect2(
		float(index % COLUMNS) * CELL_PIXELS,
		float(index / COLUMNS) * CELL_PIXELS,
		CELL_PIXELS, CELL_PIXELS)

	return atlas


## Build the node of one cell and fit it. A node from an earlier draw goes.
func _draw(index: int) -> void:
	_drop(index)

	var source: Array = _sources[index]
	var node := _item_node(str(source[0]), str(source[1]))

	if node == null:
		return

	_hulls[index] = _hulls_of(node)
	_root.add_child(node)
	_items[index] = node
	_place(index)


## Put the node of one cell in its place. The picture pose of its item
## gives the turn, the zoom of the fit, and the offset. A cell with no node
## stays empty.
func _place(index: int) -> void:
	var node: Node3D = _items.get(index)

	if not is_instance_valid(node):
		return

	var pose := PicturePose.file_row(str(_sources[index][0]))
	var turn := PicturePose.basis_of(pose)

	# The fit reads the outline that the camera sees, at the turn of the
	# pose. Thus, a model that PRESENTATION shrinks still fills its cell.
	# A zoom of 1 fills the cell at each turn.
	var outline := _seen_outline(_hulls[index], turn)
	var longest := maxf(outline.size.x, outline.size.y)
	var side := ITEM_FILL * CELL_WORLD
	var fill := side * PicturePose.zoom_of(pose)

	if longest > ModelLoader.MIN_EXTENT:
		fill /= longest

	# The turn moves the middle of the item off its origin. The shift puts
	# the middle of the outline back on the cell centre. The offset of the
	# pose then moves the picture, and it stops at the edge of the cell.
	var middle := outline.get_center()
	var shift := Vector3(middle.x, middle.y, 0.0) * fill
	var offset := PicturePose.placed_offset(pose, outline.size * fill, side)

	node.transform = Transform3D(turn.scaled(Vector3.ONE * fill),
		cell_centre(index) - shift + Vector3(offset.x, offset.y, 0.0))


## Free the node of one cell, if the cell has one.
func _drop(index: int) -> void:
	var node: Node3D = _items.get(index)

	_items.erase(index)
	_hulls.erase(index)

	if is_instance_valid(node):
		_root.remove_child(node)
		node.free()


## Draw every picture again, each in its own cell.
func _draw_all() -> void:
	if _sources.is_empty():
		return

	for index: int in _sources.size():
		_draw(index)

	_render_soon()


## Draw again each picture that the arrival of one model changes. The
## resolver owns the mesh ladder, so it says which pictures those are.
func _on_model_arrived(arrived_key: String) -> void:
	var changed := false

	for index: int in _sources.size():
		var source: Array = _sources[index]
		var redraws := _meshes.redraws_for(str(source[0]), str(source[1]), arrived_key)

		if redraws:
			_draw(index)
			changed = true

	if changed:
		_render_soon()


## Render the grid one time, at the next frame. The viewport then keeps its
## texture and renders no more, until the next call.
func _render_soon() -> void:
	render_target_update_mode = SubViewport.UPDATE_ONCE


## The served model, else the worn look, else the rest of the mesh ladder.
## Null when the stage has no source.
func _item_node(asset: String, family: String) -> Node3D:
	var node: Node3D = null

	if _meshes != null:
		node = _meshes.resolve_own_art(asset)

	if node == null and _figures != null:
		node = _figures.build_item(asset)

	if node == null and _meshes != null:
		node = _meshes.resolve_entity(asset, family)

	return node


## The hull of each mesh of a node: a list of `[points, transform]`. The
## transform takes a point of the hull into the units of the node.
##
## The hull of each mesh gives the same outline as all of its vertices,
## because the outline is largest at a corner of the hull. A served model
## has thousands of vertices and a hull of some hundreds.
func _hulls_of(node: Node3D) -> Array:
	var hulls := []

	for part: Array in ModelLoader.mesh_parts(node):
		var mesh: Mesh = part[0]
		var hull := mesh.create_convex_shape(true, false)

		# Null when a surface gives no arrays. The mesh then adds nothing.
		if hull != null:
			hulls.append([hull.points, part[1]])

	return hulls


## The outline of a node as the camera sees it at the turn `turn`, in the
## units of the node. X is the horizontal and Y is the vertical. `hulls`
## is the list of [method _hulls_of] for the node.
##
## An empty rectangle for a node with no mesh.
func _seen_outline(hulls: Array, turn: Basis) -> Rect2:
	var view := Transform3D(turn)
	var low := Vector2(INF, INF)
	var high := Vector2(-INF, -INF)

	for hull: Array in hulls:
		var to_camera: Transform3D = view * (hull[1] as Transform3D)

		for point: Vector3 in (hull[0] as PackedVector3Array):
			var seen := to_camera * point
			var flat := Vector2(seen.x, seen.y)

			low = low.min(flat)
			high = high.max(flat)

	if high.x < low.x:
		return Rect2()

	return Rect2(low, high - low)


func _row_count() -> int:
	return maxi(1, ceili(float(_capacity) / float(COLUMNS)))


## Size the render target and frame the camera on the whole grid.
func _resize(count: int) -> void:
	_capacity = maxi(count, 1)

	var rows := _row_count()

	size = Vector2i(COLUMNS * CELL_PIXELS, rows * CELL_PIXELS)

	# An orthographic camera's `size` is its VERTICAL extent; the horizontal
	# follows from the aspect ratio. Since the target is COLUMNS wide and `rows`
	# tall in cells, framing `rows` vertically frames COLUMNS horizontally --
	# which is what makes one world unit exactly one cell in both directions.
	# The grid grows down from zero, so the camera stands at its middle row.
	_camera.size = float(rows) * CELL_WORLD
	_camera.position = Vector3(0.0, -float(rows) * CELL_WORLD * 0.5, CAMERA_DISTANCE)
