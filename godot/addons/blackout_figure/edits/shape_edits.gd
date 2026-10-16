@tool
class_name FigureShapeEdits
extends RefCounted
## The rules of a shape of a part (DESIGN-0014): the fields of each shape
## kind, a new shape, add, remove, a copy, and the value of one field.
##
## Each routine changes the shape list of one part of one look file. The
## caller gives a copy of the look content, and the routine changes the
## copy. A routine that can refuse returns the reason, or "". Nothing here
## needs the editor.
##
## [constant SHAPE_FIELDS] names the fields of each shape kind, and
## [constant FIELD_KINDS] names the kind of control for each field. The
## Body tab builds its field grid from the two tables.

## The kinds of a shape field, for the fields of the Body tab.
const FIELD_FLOAT := "float"
const FIELD_SIGNED := "signed"
const FIELD_VECTOR := "vector"
const FIELD_ANGLES := "angles"
const FIELD_COUNT := "count"
const FIELD_FLAG := "flag"
const FIELD_COLOR := "color"
const FIELD_FINISH := "finish"

## The fields of each shape, in the order of the Body tab. The prism is
## first, so the list of a new shape starts with the shape of the low-poly
## look.
const SHAPE_FIELDS := {
	FamilyShapes.SHAPE_PRISM: ["size", "top_width", "top_depth", "lean_x", "lean_z",
		"diamond"],
	FamilyShapes.SHAPE_BOX: ["size"],
	FamilyShapes.SHAPE_SPHERE: ["radius"],
	FamilyShapes.SHAPE_CYLINDER: ["radius", "radius_top", "height", "open"],
	FamilyShapes.SHAPE_CONE: ["radius", "height"],
	FamilyShapes.SHAPE_TORUS: ["inner", "outer"],
	FamilyShapes.SHAPE_FACETED: ["radius"],
}

## The fields that each shape has.
const COMMON_FIELDS := ["offset", "rotation", "scale", "segments", "rings",
	"color", "finish"]

const FIELD_KINDS := {
	"size": FIELD_VECTOR,
	"radius": FIELD_FLOAT,
	"radius_top": FIELD_FLOAT,
	"height": FIELD_FLOAT,
	"inner": FIELD_FLOAT,
	"outer": FIELD_FLOAT,
	"open": FIELD_FLAG,
	"top_width": FIELD_FLOAT,
	"top_depth": FIELD_FLOAT,
	"lean_x": FIELD_SIGNED,
	"lean_z": FIELD_SIGNED,
	"diamond": FIELD_FLAG,
	"offset": FIELD_VECTOR,
	"rotation": FIELD_ANGLES,
	"scale": FIELD_VECTOR,
	"segments": FIELD_COUNT,
	"rings": FIELD_COUNT,
	"color": FIELD_COLOR,
	"finish": FIELD_FINISH,
}

## A new shape of each kind, at a size that shows on a figure.
const NEW_SHAPES := {
	FamilyShapes.SHAPE_BOX: {"size": [0.1, 0.1, 0.1]},
	FamilyShapes.SHAPE_SPHERE: {"radius": 0.05},
	FamilyShapes.SHAPE_CYLINDER: {"radius": 0.05, "height": 0.1},
	FamilyShapes.SHAPE_CONE: {"radius": 0.05, "height": 0.1},
	FamilyShapes.SHAPE_TORUS: {"inner": 0.03, "outer": 0.05},
	FamilyShapes.SHAPE_FACETED: {"radius": 0.05},
	FamilyShapes.SHAPE_PRISM: {"size": [0.1, 0.1, 0.1], "segments": 4},
}

## The rings of a shape that has no default in [FigureLook].
const FALLBACK_RINGS := 2

## The choice of the finish field for a shape with no `finish` key. Such a
## shape has the finish of its named color ([FigurePalette]).
const FINISH_OF_COLOR := "(of the color)"


# ─── The Body tab: shapes ───────────────────────────────────────────────────

## A new shape of one kind, with the generic color.
static func new_shape(kind: String) -> Dictionary:
	var shape: Dictionary = NEW_SHAPES.get(kind, {}).duplicate(true)

	shape["shape"] = kind
	shape["color"] = MeshPalette.GENERIC

	return shape


## Add a shape to the shape list of a part. Returns its index, or -1.
static func add_shape(look: Dictionary, part_name: String, kind: String) -> int:
	var index := FigurePartEdits.part_index(look, part_name)

	if index < 0 or not SHAPE_FIELDS.has(kind):
		return -1

	var row: Dictionary = look["parts"][index]

	if not row.has("shapes"):
		row["shapes"] = []

	row["shapes"].append(new_shape(kind))

	return row["shapes"].size() - 1


static func remove_shape(look: Dictionary, part_name: String, shape_index: int) -> String:
	var shapes := _shapes(look, part_name)

	if shape_index < 0 or shape_index >= shapes.size():
		return "The part %s has no shape %d." % [part_name, shape_index]

	shapes.remove_at(shape_index)

	return ""


## Add a copy of one shape to the shape list of its part, after that shape.
## Returns the index of the copy, or -1.
static func duplicate_shape(look: Dictionary, part_name: String, shape_index: int) -> int:
	var shapes := _shapes(look, part_name)

	if shape_index < 0 or shape_index >= shapes.size():
		return -1

	shapes.insert(shape_index + 1, shapes[shape_index].duplicate(true))

	return shape_index + 1


## The fields of a shape: those of its kind, then those of each shape.
static func fields_of(shape: Dictionary) -> Array:
	var fields: Array = SHAPE_FIELDS.get(shape.get("shape", ""), []).duplicate()

	fields.append_array(COMMON_FIELDS)

	return fields


## The value that a field of a shape has. A shape with no such key gives
## the value that the builder uses for it. A vector is a [Vector3].
static func shape_value(shape: Dictionary, field: String) -> Variant:
	var kind: String = FIELD_KINDS.get(field, FIELD_FLOAT)

	if kind == FIELD_VECTOR or kind == FIELD_ANGLES:
		return FigureJson.vector3(shape.get(field), _default_vector(field))

	if shape.has(field):
		return shape[field]

	return _default_value(shape, field)


## Write one field of one shape. A vector is a [Vector3].
static func set_shape_value(look: Dictionary, part_name: String, shape_index: int,
		field: String, value: Variant) -> String:
	var shapes := _shapes(look, part_name)

	if shape_index < 0 or shape_index >= shapes.size():
		return "The part %s has no shape %d." % [part_name, shape_index]

	if not FIELD_KINDS.has(field):
		return "A shape has no field %s." % field

	if FIELD_KINDS[field] == FIELD_FINISH and str(value) == FINISH_OF_COLOR:
		shapes[shape_index].erase(field)
	elif value is Vector3:
		shapes[shape_index][field] = FigureJson.from_vector3(value)
	else:
		shapes[shape_index][field] = value

	return ""


static func _default_vector(field: String) -> Vector3:
	if field == "scale":
		return Vector3.ONE

	if field == "size":
		return MeshBuilder.DEFAULT_BOX_SIZE

	return Vector3.ZERO


static func _default_value(shape: Dictionary, field: String) -> Variant:
	match field:
		"radius":
			return MeshBuilder.DEFAULT_RADIUS
		"radius_top":
			return shape.get("radius", MeshBuilder.DEFAULT_RADIUS)
		"height":
			return MeshBuilder.DEFAULT_HEIGHT
		"inner":
			return MeshBuilder.DEFAULT_TORUS_INNER
		"outer":
			return MeshBuilder.DEFAULT_TORUS_OUTER
		"open", "diamond":
			return false
		"top_width":
			return FigureJson.vector3(shape.get("size"), MeshBuilder.DEFAULT_BOX_SIZE).x
		"top_depth":
			return FigureJson.vector3(shape.get("size"), MeshBuilder.DEFAULT_BOX_SIZE).z
		"segments":
			return FigureLook.DEFAULT_SEGMENTS
		"rings":
			return FigureLook.DEFAULT_RINGS.get(shape.get("shape", ""), FALLBACK_RINGS)
		"color":
			return MeshPalette.GENERIC
		"finish":
			return FINISH_OF_COLOR

	return 0.0


## The shape list of a part, or an empty list for a part that the look does
## not have.
static func _shapes(look: Dictionary, part_name: String) -> Array:
	var index := FigurePartEdits.part_index(look, part_name)

	if index < 0:
		return []

	return look["parts"][index].get("shapes", [])
