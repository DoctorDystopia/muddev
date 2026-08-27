class_name ItemStage
extends SubViewport
## Every inventory item, drawn in 3D, into ONE texture.
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
## through an [AtlasTexture]. One render target, one camera, one pass — and the
## slow spin below costs the same whether one item is on screen or forty.
##
## ## The layout is this file's, and only this file's
##
## Cells are addressed by INDEX. [InventoryView] allocates indices — carried
## slots first, then worn frames — and asks for the texture belonging to one.
## Where index 19 sits in the 3D grid, and therefore which pixels it owns, is
## decided here and nowhere else, so the two cannot disagree about which item a
## cell is showing.

## Pixels per cell in the render target. Small on purpose: this is drawn at
## thumbnail size, and the target is COLUMNS x rows of these.
const CELL_PIXELS := 96

## Cells per row in the 3D grid. Nothing to do with how many columns the Control
## grid shows -- this is only how the render target is packed.
const COLUMNS := 8

## One world unit per cell, so a cell's world position is its grid position.
const CELL_WORLD := 1.0

## How much of its cell one item fills. Matches the browser's ITEM_SCALE.
const ITEM_SCALE := 0.84

## A fixed tilt is what makes a flat-on orthographic camera read as 3D. Matches
## the browser, which tilts the ITEM and leaves the frame square because the
## frame is what the player aims at.
const ITEM_TILT_X := -0.34

## Rotations per second. Very slow -- twelve and a half seconds per turn -- so it
## reads as ambience rather than as animation.
const SPIN_HZ := 0.08

## How far back the camera sits. Any value clear of the items works; it is
## orthographic, so this changes nothing about the framing.
const CAMERA_DISTANCE := 4.0

## Lighting. Bright ambience plus one key light, because these are small
## silhouettes and a moody inventory is an unreadable one.
const AMBIENT_ENERGY := 1.1
const LIGHT_ENERGY := 1.4

var _camera: Camera3D
var _root: Node3D

## index -> the Node3D drawn for it, so a spin can turn them all.
var _items: Dictionary = {}

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

	# WHEN_VISIBLE and not ALWAYS: in text-only mode the whole 3D half is
	# hidden, and a spinning inventory nobody can see should not cost a render
	# pass per frame to keep spinning.
	render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE

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

	_resize(1)


## Make room for `count` cells, and forget everything currently drawn.
##
## Called before a rebuild. The render target is resized to fit, so a bag that
## grows costs more pixels rather than needing an edit here.
func reserve(count: int) -> void:
	_clear()
	_resize(count)


## Draw one item at one index. `asset` and `family` are the server's, untouched.
func place(index: int, asset: String, family: String,
		resolver: MeshResolver) -> void:
	if index < 0 or index >= _capacity or resolver == null:
		return

	var node := resolver.resolve_entity(asset, family)

	node.scale = Vector3.ONE * ITEM_SCALE
	node.position = cell_centre(index)
	node.rotation = Vector3(ITEM_TILT_X, 0.0, 0.0)

	_root.add_child(node)
	_items[index] = node


## The picture belonging to one cell.
##
## An [AtlasTexture] over this viewport's own texture, so every cell shares one
## render target and none of them owns a copy of anything.
func texture_for(index: int) -> AtlasTexture:
	var atlas := AtlasTexture.new()

	atlas.atlas = get_texture()
	atlas.region = Rect2(
		float(index % COLUMNS) * CELL_PIXELS,
		float(index / COLUMNS) * CELL_PIXELS,
		CELL_PIXELS, CELL_PIXELS)

	return atlas


## Where cell `index` sits in the 3D grid, in world units.
##
## Y is negated because grid rows run DOWN the texture while world Y runs up,
## and the camera looks along -Z. Getting that backwards draws the last row at
## the top and is invisible until the bag has two rows in it.
func cell_centre(index: int) -> Vector3:
	var column := index % COLUMNS
	var row := index / COLUMNS
	var rows := _row_count()

	return Vector3(
		(float(column) + 0.5 - (float(COLUMNS) * 0.5)) * CELL_WORLD,
		((float(rows) * 0.5) - float(row) - 0.5) * CELL_WORLD,
		0.0)


func _process(delta: float) -> void:
	if _items.is_empty():
		return

	var turn := TAU * SPIN_HZ * delta

	for index: int in _items:
		var node: Node3D = _items[index]

		if is_instance_valid(node):
			node.rotate_y(turn)


# ─── Private ─────────────────────────────────────────────────────────────────

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
	_camera.size = float(rows) * CELL_WORLD
	_camera.position = Vector3(0.0, 0.0, CAMERA_DISTANCE)


func _clear() -> void:
	for index: int in _items:
		var node: Node3D = _items[index]

		if is_instance_valid(node):
			_root.remove_child(node)
			node.free()

	_items.clear()
