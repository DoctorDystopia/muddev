class_name HitsplatLayer
extends Node3D
## Draws a hitsplat over each figure that a swing reaches: the damage number,
## the max hit mark, and a miss.
##
## **The server names. The layer draws.** One `blackout_combat` payload is one
## hitsplat. The server decides if the swing is a max hit (`max_hit`, and the
## roll in `max_hit_roll`). The layer only picks the [HitsplatStyle] for that
## kind. Every payload reaches each person in the fight: the attacker, the
## target and the room. Thus, everyone in the fight sees the same hitsplat.
##
## **Edit the look in the style files**, not here. See [HitsplatStyle]. To try
## a different file without an edit of the default, set [member hit_style],
## [member max_hit_style] or [member miss_style] on this node.
##
## **A hitsplat stands in the world, not on the figure.** It is a child of
## this layer. The layer puts it at the top of the figure one time. A killed NPC
## deletes its figure in the same tick, and a hitsplat on that figure would
## vanish with it. The killing blow is the hitsplat a player most wants to see.

const _HIT_STYLE := preload("res://world/hitsplats/styles/hit.tres")
const _MAX_HIT_STYLE := preload("res://world/hitsplats/styles/max_hit.tres")
const _MISS_STYLE := preload("res://world/hitsplats/styles/miss.tres")

## The draw order of the text, over other see-through surfaces. The outline
## draws one step below its text, or the outline covers the glyphs.
const RENDER_PRIORITY := 10

## The look of a swing that connected, 0 included.
@export var hit_style: HitsplatStyle = _HIT_STYLE

## The look of a swing that rolled the top face of its damage die.
@export var max_hit_style: HitsplatStyle = _MAX_HIT_STYLE

## The look of a swing that missed.
@export var miss_style: HitsplatStyle = _MISS_STYLE

## The source of the sideways step ([member HitsplatStyle.jitter]). A test
## seeds it.
var rng := RandomNumberGenerator.new()


## The style for one payload. A miss is a miss even when a payload says
## `max_hit`, because a swing that missed rolled no damage.
func style_for(payload: Dictionary) -> HitsplatStyle:
	if not payload.get("hit", false):
		return miss_style

	if payload.get("max_hit", false):
		return max_hit_style

	return hit_style


## The big number of one hitsplat.
static func number_text(payload: Dictionary, style: HitsplatStyle) -> String:
	var damage := int(payload.get("damage", 0))

	return style.text_format.format({"damage": damage})


## The small line under the number, or "" for none.
##
## Only a max hit that the damage channel changed has one. The roll was the
## max hit, but a bonus or a penalty after the roll changed the damage. The
## line names the two numbers, so the player sees why the big number is not
## the max hit (Nick, 10/08/2026). The hit line in the log says the same.
static func detail_text(payload: Dictionary, style: HitsplatStyle) -> String:
	if not payload.get("max_hit", false):
		return ""

	var roll := int(payload.get("max_hit_roll", 0))
	var change := int(payload.get("damage", 0)) - roll

	if change > 0:
		return style.detail_bonus_format.format(
			{"max_hit": roll, "change": change})

	if change < 0:
		return style.detail_penalty_format.format(
			{"max_hit": roll, "change": -change})

	return ""


## Draw one hitsplat over [param anchor]. Returns the hitsplat, or null when
## there is no figure to draw it over.
##
## The hitsplat frees itself at the end of its life. Nothing else holds it.
func show_hit(payload: Dictionary, anchor: Node3D) -> Node3D:
	if anchor == null or not anchor.is_inside_tree():
		return null

	var style := style_for(payload)

	if style == null:
		return null

	var splat := Node3D.new()
	add_child(splat)
	splat.global_position = _top_of(anchor) + _offset(style)

	var number := _label(number_text(payload, style), style.font_size,
		style.color, style)
	splat.add_child(number)

	var detail := detail_text(payload, style)

	# The detail line stands on the point, and the number stands on the
	# detail line. The offset is in font pixels, so it scales with the text.
	# A gap in world units closes up under [member HitsplatStyle.fixed_size]
	# when the camera moves away.
	if not detail.is_empty():
		var line := _label(detail, style.detail_font_size, style.detail_color,
			style)
		number.offset.y = style.detail_gap
		splat.add_child(line)

	_animate(splat, style)

	return splat


## The top centre of a figure, in world space.
##
## [method ModelLoader.bounds_of] measures in the space of the figure. The
## transform of the figure (with its scale) turns the point into world space.
## A figure with no mesh measures as one point at its origin.
static func _top_of(anchor: Node3D) -> Vector3:
	var bounds := ModelLoader.bounds_of(anchor)
	var centre := bounds.get_center()
	var top := Vector3(centre.x, bounds.end.y, centre.z)

	return anchor.global_transform * top


## The height of the style, and a random step sideways on the ground plane.
func _offset(style: HitsplatStyle) -> Vector3:
	var x := rng.randf_range(-style.jitter, style.jitter)
	var z := rng.randf_range(-style.jitter, style.jitter)

	return Vector3(x, style.height, z)


## One line of hitsplat text.
##
## A full billboard, unlike the Y-only labels of [EntityPool]. A hitsplat
## lives for under a second, so it never lies flat under a high camera.
## Blended and not alpha cut, because the fade needs the alpha.
##
## The text stands ON its point (bottom alignment) and grows up. Far from the
## camera, [member HitsplatStyle.fixed_size] keeps the text large and the
## figure gets small. Centred text then covers the figure.
func _label(text: String, size: int, color: Color,
		style: HitsplatStyle) -> Label3D:
	var label := Label3D.new()
	label.text = text
	label.font_size = size
	label.pixel_size = style.pixel_size
	label.fixed_size = style.fixed_size
	label.modulate = color
	label.outline_size = style.outline_size
	label.outline_modulate = style.outline_color
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = style.draw_on_top
	label.render_priority = RENDER_PRIORITY
	label.outline_render_priority = RENDER_PRIORITY - 1

	if style.font != null:
		label.font = style.font

	return label


## Pop, rise, hold, fade, free.
##
## Two tweens. The motion runs the whole life. The fade waits for the pop and
## the hold. One tween cannot do both: a step of a tween ends when its LONGEST
## part ends, so the rise would hold the fade back to the end of the life.
func _animate(splat: Node3D, style: HitsplatStyle) -> void:
	splat.scale = Vector3.ONE * style.pop_scale

	var motion := splat.create_tween().set_parallel(true)
	motion.tween_property(splat, "scale", Vector3.ONE, style.pop_seconds) \
		.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	motion.tween_property(splat, "position:y", splat.position.y + style.rise,
		style.lifetime())

	var fade := splat.create_tween()
	fade.tween_interval(style.pop_seconds + style.hold_seconds)

	# The outline has its own colour, and modulate does not reach it. Each
	# label fades both, all at one time.
	var first := true

	for child: Node in splat.get_children():
		var label := child as Label3D

		if not first:
			fade.parallel()

		fade.tween_property(label, "modulate:a", 0.0, style.fade_seconds)
		fade.parallel().tween_property(label, "outline_modulate:a", 0.0,
			style.fade_seconds)
		first = false

	fade.tween_callback(splat.queue_free)
