class_name MapIcons
extends RefCounted
## What a chunk object looks like on a map: one symbol for each category.
##
## The categories are server facts (`OBJECT_CATEGORIES`, and `OBJECT_KINDS`
## maps each kind to one). The shapes and the colours are the client's own.
## Both the minimap and the world map draw a map icon through [method draw].
##
## ## No guard test, and why
##
## [constant ICONS] is keyed by the generated constants, not by typed names.
## A category that the server renames or drops breaks the generated file, so
## this table cannot name a category that does not exist. The same argument
## covers the label kinds in `clientexport.py`.
##
## ## The fallback
##
## A category with no row draws nothing. Two categories have no row on
## purpose. An NPC moves, so the minimap draws the live NPC as a map dot, not
## its spawn tile. A sign says nothing at map size.

const _Const := preload("res://autoload/blackout_constants.gd")

const SHAPE_SQUARE := "square"
const SHAPE_DIAMOND := "diamond"
const SHAPE_TRIANGLE := "triangle"
const SHAPE_CIRCLE := "circle"
const SHAPE_RING := "ring"

## Category -> {shape, colour}. A look, for Nick to tune.
const ICONS := {
	_Const.OBJECT_CATEGORY_FACILITY: {
		"shape": SHAPE_SQUARE, "colour": Color("f2c14e")},
	_Const.OBJECT_CATEGORY_GATHERING: {
		"shape": SHAPE_TRIANGLE, "colour": Color("7fd36b")},
	_Const.OBJECT_CATEGORY_LANDMARK: {
		"shape": SHAPE_CIRCLE, "colour": Color("f5f5f5")},
	_Const.OBJECT_CATEGORY_TRANSITION: {
		"shape": SHAPE_RING, "colour": Color("d86bf2")},
	_Const.OBJECT_CATEGORY_CLIMB: {
		"shape": SHAPE_DIAMOND, "colour": Color("6bc6f2")},
}

const OUTLINE := Color(0.02, 0.03, 0.04, 0.9)
const OUTLINE_WIDTH := 1.0


## The category of an object kind, or "" for a kind the server did not name.
static func category_of(kind: String) -> String:
	return str(_Const.OBJECT_KINDS.get(kind, ""))


## True when a category has a map icon.
static func has_icon(category: String) -> bool:
	return ICONS.has(category)


## Draw the map icon of a category, centred on a point, `size` pixels across.
## Returns false, and draws nothing, for a category with no row.
static func draw(canvas: CanvasItem, category: String, centre: Vector2,
		size: float) -> bool:
	if not ICONS.has(category):
		return false

	var look: Dictionary = ICONS[category]
	var colour: Color = look["colour"]
	var half := size * 0.5

	match look["shape"]:
		SHAPE_SQUARE:
			var rect := Rect2(centre - Vector2.ONE * half, Vector2.ONE * size)
			canvas.draw_rect(rect, colour)
			canvas.draw_rect(rect, OUTLINE, false, OUTLINE_WIDTH)

		SHAPE_CIRCLE:
			canvas.draw_circle(centre, half, colour)
			canvas.draw_arc(centre, half, 0.0, TAU, 12, OUTLINE, OUTLINE_WIDTH)

		SHAPE_RING:
			canvas.draw_arc(centre, half * 0.8, 0.0, TAU, 12, colour, half * 0.4)

		SHAPE_TRIANGLE:
			_draw_polygon(canvas, [centre + Vector2(0, -half),
				centre + Vector2(half, half), centre + Vector2(-half, half)],
				colour)

		SHAPE_DIAMOND:
			_draw_polygon(canvas, [centre + Vector2(0, -half),
				centre + Vector2(half, 0), centre + Vector2(0, half),
				centre + Vector2(-half, 0)], colour)

	return true


static func _draw_polygon(canvas: CanvasItem, points: Array,
		colour: Color) -> void:
	var packed := PackedVector2Array(points)

	canvas.draw_colored_polygon(packed, colour)
	packed.append(points[0])
	canvas.draw_polyline(packed, OUTLINE, OUTLINE_WIDTH)
