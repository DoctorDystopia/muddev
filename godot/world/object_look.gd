@tool
class_name ObjectLook
extends RefCounted
## The look of one chunk object, applied to the node that draws it: its
## scale, its tilt, and its nudge (10/16/2026). The variant is the fourth
## fact of a look, and [method ModelRegistry.variant_for] picks it.
##
## The chunk file holds a look as ints: a scale in percent, a tilt in
## degrees on three axes, and a nudge in hundredths of a tile. The server
## sends the same table on the row of an entity ([code]ENTITY_LOOK_KEY[/code]).
## This class turns each one into the units of a [Node3D], one time, for
## the three places that draw a chunk object: [EntityPool] for an entity,
## [TerrainView] for scenery, and [TerrainModels] in the editor.
## [PropMeshBuilder] reads the same three facts for a primitive.
##
## The tilt rides on the quarter turn of the rotation. [member Node3D.rotation]
## is YXZ, so the yaw comes first, and the tilt then turns the object in its
## own frame. The nudge is in the frame of the tile: x east, y up, z north.
## It does not turn with the object, so an author can push a thing off the
## centre of its tile and know which way it went.
##
## A bad value reads as its default, so a row that a client did not expect
## never hides the thing. The server already refused what the chunk file
## refuses.

const _Const := preload("res://autoload/blackout_constants.gd")

## A look that draws the base model as it comes.
const NONE := {}


## The variant of a look: a model key, [code]LOOK_VARIANT_ANY[/code], or
## "" for the base model.
static func variant_of(look: Dictionary) -> String:
	var choice: Variant = look.get(_Const.LOOK_VARIANT_KEY, "")

	return choice if choice is String else ""


## The scale of a look as a multiplier: 1.0 for no scale.
static func scale_of(look: Dictionary) -> float:
	var percent: Variant = look.get(_Const.LOOK_SCALE_KEY, _Const.LOOK_SCALE_UNIT)

	if not (percent is int or percent is float) or percent <= 0:
		return 1.0

	return float(percent) / float(_Const.LOOK_SCALE_UNIT)


## The tilt of a look in radians, in the order of [member Node3D.rotation].
static func turn_of(look: Dictionary) -> Vector3:
	var degrees := _axes_of(look, _Const.LOOK_TURN_KEY)

	return Vector3(deg_to_rad(degrees.x), deg_to_rad(degrees.y), deg_to_rad(degrees.z))


## The nudge of a look in world units: x east, y up, and north along -z,
## as [ChunkMeshBuilder] lays the tiles.
static func offset_of(look: Dictionary) -> Vector3:
	var hundredths := _axes_of(look, _Const.LOOK_OFFSET_KEY)
	var step := ChunkMeshBuilder.TILE_SIZE / float(_Const.LOOK_OFFSET_UNIT)

	return Vector3(hundredths.x, hundredths.y, -hundredths.z) * step


## The seed of the auto variant of a chunk object: its world tile and its
## plane. The same tile picks the same variant in every session.
static func seed_of(tile: Vector2i, plane: int) -> String:
	return "%d,%d,%d" % [tile.x, tile.y, plane]


## One text for a look, so a pool can tell two rows apart. The order of
## the keys is that of the server, which never changes for one row.
static func key_of(look: Dictionary) -> String:
	if look.is_empty():
		return ""

	return JSON.stringify(look)


## Size and turn `node` by a look: `base_scale` times the scale of the
## look, and `yaw` plus its tilt. The caller places the node after, with
## [method rest_lift] and [method offset_of].
static func apply(node: Node3D, look: Dictionary, base_scale: float, yaw: float) -> void:
	node.scale = Vector3.ONE * base_scale * scale_of(look)
	node.rotation = turn_of(look) + Vector3(0.0, yaw, 0.0)


## How far to lift `node` so its bottom rests on the ground, after
## [method apply]. [method ModelLoader.bounds_of] leaves out the transform
## of the root, so the unscaled bottom times the scale is the lift. The
## rule of [code]EntityPool._rest_offset[/code], with the scale of the look
## in it.
static func rest_lift(node: Node3D) -> float:
	var bounds := ModelLoader.bounds_of(node)

	return -bounds.position.y * node.scale.y


static func _axes_of(look: Dictionary, key: String) -> Vector3:
	var values: Variant = look.get(key, [])

	if not (values is Array) or values.size() != _Const.LOOK_AXES:
		return Vector3.ZERO

	var found := Vector3.ZERO

	for axis: int in _Const.LOOK_AXES:
		var number: Variant = values[axis]

		if number is int or number is float:
			found[axis] = float(number)

	return found
