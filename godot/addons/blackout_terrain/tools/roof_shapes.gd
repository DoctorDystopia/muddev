@tool
class_name RoofShapes
extends RefCounted
## The corner heights of each roof shape (DESIGN-0013 section 6.2).
##
## A roof is the ground of the plane above a structure. This class gives the
## height of each corner of that ground. [method StructureTools.roof] writes
## the heights, the roof floor type, and the Blocked flag. No function here
## calls the editor, so `test_roof_shapes.tscn` tests each shape with no
## editor.
##
## ## The rise
##
## The roof covers a rectangle of W x H tiles, the overhang included. Corner
## (i, j) is the south-west corner of local tile (i, j), with i in 0..W and j
## in 0..H. The rise of a corner is its height above the outer edge of the
## eave, in height steps. P is the pitch: the rise for each tile of distance.
##
## | Shape | Rise of corner (i, j) |
## |---|---|
## | Flat | 0 |
## | Shed | P x the distance from the low edge. The turn picks that edge |
## | Gable | P x min(d, W - d) across the ridge. The turn picks the ridge axis |
## | Hip | P x min(i, W - i, j, H - j) |
## | Pyramid | One apex at the centre. On a square, it is the hip |
##
## The ridge of a gable or a hip over an odd width is one flat tile wide.
##
## ## The eave
##
## The roof meets each wall at one plane rise above the base of the
## structure: [constant TerrainWorld.NEW_PLANE_RISE] above the highest corner
## of the room. The overhang hangs lower, one pitch for each tile past the
## wall, as a real eave does. A flat roof has no slope, so its overhang
## stays level.
##
## All values are integers. The chunk files store the result, and the server
## reads the stored heights only.

const _Const := preload("res://autoload/blackout_constants.gd")

enum Shape { FLAT, SHED, GABLE, HIP, PYRAMID }

## The names of [enum Shape], in its order, for the Build tab.
const SHAPE_NAMES := ["Flat", "Shed", "Gable", "Hip", "Pyramid"]

## The steepest pitch that the Build tab offers: 16 height steps for each
## tile is 45 degrees (DESIGN-0013 section 8, question 4).
const PITCH_MAX := 16

## The pitch of a new roof: about 27 degrees.
const PITCH_DEFAULT := 8

## The widest overhang that the Build tab offers, in tiles.
const OVERHANG_MAX := 2

## The number of turns of a shape before it repeats.
const TURNS := 4

## The low edge of a shed for each turn, and the ridge axis of a gable for
## each turn, in words, for the hint line.
const SHED_TURN_NAMES := ["low edge south", "low edge west", "low edge north",
	"low edge east"]
const GABLE_TURN_NAMES := ["ridge east-west", "ridge north-south"]


## The rise of every corner of a W x H roof, row 0 first: (W + 1) x (H + 1)
## values. `turn` counts quarter turns clockwise.
static func rises(size: Vector2i, shape: Shape, pitch: int, turn: int) -> PackedInt32Array:
	var result := PackedInt32Array()
	var corners := size + Vector2i.ONE

	result.resize(corners.x * corners.y)

	for j: int in corners.y:
		for i: int in corners.x:
			result[j * corners.x + i] = rise_at(Vector2i(i, j), size, shape, pitch, turn)

	return result


## The rise of corner `at` of a roof of `size` tiles.
static func rise_at(at: Vector2i, size: Vector2i, shape: Shape, pitch: int,
		turn: int) -> int:
	var dx := mini(at.x, size.x - at.x)
	var dy := mini(at.y, size.y - at.y)

	match shape:
		Shape.SHED:
			return pitch * _shed_distance(at, size, turn)
		Shape.GABLE:
			return pitch * (dy if posmod(turn, 2) == 0 else dx)
		Shape.HIP:
			return pitch * mini(dx, dy)
		Shape.PYRAMID:
			return _pyramid_rise(dx, dy, size, pitch)

	return 0


## The distance of corner `at` from the low edge of a shed.
static func _shed_distance(at: Vector2i, size: Vector2i, turn: int) -> int:
	match posmod(turn, TURNS):
		1:
			return at.x
		2:
			return size.y - at.y
		3:
			return size.x - at.x

	return at.y


## One apex at the centre. Each side climbs to the same peak, so a long
## side climbs at less than the pitch. The peak is the rise of a hip on the
## short side.
static func _pyramid_rise(dx: int, dy: int, size: Vector2i, pitch: int) -> int:
	var short := mini(size.x, size.y)
	var share := minf(float(dx) / size.x, float(dy) / size.y)

	return roundi(pitch * short * share)


## The height of the outer edge of the eave: the wall line sits at `eave`,
## and the overhang hangs one pitch lower for each tile. A flat roof stays
## level.
static func outer_eave(eave: int, shape: Shape, pitch: int, overhang: int) -> int:
	if shape == Shape.FLAT:
		return eave

	return eave - pitch * overhang


## The words for the turn of a shape, or "" for a shape that does not turn.
static func turn_name(shape: Shape, turn: int) -> String:
	match shape:
		Shape.SHED:
			return SHED_TURN_NAMES[posmod(turn, TURNS)]
		Shape.GABLE:
			return GABLE_TURN_NAMES[posmod(turn, 2)]

	return ""
