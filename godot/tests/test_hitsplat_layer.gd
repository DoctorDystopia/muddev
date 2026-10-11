extends Node
## Unit tests for HitsplatLayer and HitsplatStyle. They test the style that a
## swing picks, the text of each line, the place of a hitsplat, and its free.
##
##     godot --headless --path godot res://tests/test_hitsplat_layer.tscn
##
## Needs nothing running. No case reads a colour, a size or a time of a style
## file. Those are look decisions, and they change at any time. Each case
## reads the value from the style that it tests.

var _failures := 0

## Payloads in the shape `emit_swing` sends: JSON numbers arrive as floats.
const DAMAGE := 9.0
const ROLL := 9.0
const CHANGE := 3.0

const HIT := {"hit": true, "damage": DAMAGE, "max_hit": false,
	"max_hit_roll": 0.0, "target_id": 7.0}
const MAX_HIT := {"hit": true, "damage": ROLL, "max_hit": true,
	"max_hit_roll": ROLL, "target_id": 7.0}
const MAX_HIT_BONUS := {"hit": true, "damage": ROLL + CHANGE,
	"max_hit": true, "max_hit_roll": ROLL, "target_id": 7.0}
const MAX_HIT_PENALTY := {"hit": true, "damage": ROLL - CHANGE,
	"max_hit": true, "max_hit_roll": ROLL, "target_id": 7.0}
const MISS := {"hit": false, "damage": 0.0, "max_hit": false,
	"max_hit_roll": 0.0, "target_id": 7.0}

## The edge of the test box figure, in world units.
const BOX_SIZE := 1.0

## Where the test figure stands. Not the origin, so a hitsplat that ignores
## the position of the figure fails.
const FIGURE_AT := Vector3(4.0, 2.0, -3.0)

## Extra frames past the end of the life of a hitsplat before the free check.
const SETTLE_SECONDS := 0.1

## A short life for the free check, so the case takes a fraction of a second.
const SHORT_SECONDS := 0.05

var _layer: HitsplatLayer


func _ready() -> void:
	_layer = HitsplatLayer.new()
	add_child(_layer)

	_every_default_style_loads()
	_a_swing_picks_its_style()
	_the_number_follows_the_format()
	_a_format_with_no_placeholder_shows_as_it_is()
	_only_a_changed_max_hit_has_a_detail_line()
	_the_detail_line_names_the_roll_and_the_change()
	_no_figure_draws_no_hitsplat()
	_a_hitsplat_stands_over_the_figure()
	_a_changed_max_hit_draws_two_lines()
	await _a_hitsplat_frees_itself()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: hitsplat_layer")
	get_tree().quit(0)


func _every_default_style_loads() -> void:
	_expect(_layer.hit_style is HitsplatStyle, "the hit style loads")
	_expect(_layer.max_hit_style is HitsplatStyle, "the max hit style loads")
	_expect(_layer.miss_style is HitsplatStyle, "the miss style loads")
	_expect(_layer.max_hit_style != _layer.hit_style,
		"a max hit has a style of its own")


func _a_swing_picks_its_style() -> void:
	_expect(_layer.style_for(HIT) == _layer.hit_style, "a hit picks hit")
	_expect(_layer.style_for(MAX_HIT) == _layer.max_hit_style,
		"a max hit picks max hit")
	_expect(_layer.style_for(MISS) == _layer.miss_style, "a miss picks miss")

	var odd := MAX_HIT.duplicate()
	odd["hit"] = false
	_expect(_layer.style_for(odd) == _layer.miss_style,
		"a miss is a miss even when it says max_hit")


func _the_number_follows_the_format() -> void:
	var style := HitsplatStyle.new()
	style.text_format = "[{damage}]"

	_expect(HitsplatLayer.number_text(HIT, style) == "[%d]" % int(DAMAGE),
		"the number goes into the format")


func _a_format_with_no_placeholder_shows_as_it_is() -> void:
	var style := HitsplatStyle.new()
	style.text_format = "MISS"

	_expect(HitsplatLayer.number_text(MISS, style) == "MISS",
		"a literal format shows as it is")


func _only_a_changed_max_hit_has_a_detail_line() -> void:
	var style := _layer.max_hit_style

	_expect(HitsplatLayer.detail_text(HIT, style).is_empty(),
		"a usual hit has no detail line")
	_expect(HitsplatLayer.detail_text(MAX_HIT, style).is_empty(),
		"an unchanged max hit has no detail line")
	_expect(HitsplatLayer.detail_text(MISS, style).is_empty(),
		"a miss has no detail line")
	_expect(not HitsplatLayer.detail_text(MAX_HIT_BONUS, style).is_empty(),
		"a max hit with a bonus has a detail line")
	_expect(not HitsplatLayer.detail_text(MAX_HIT_PENALTY, style).is_empty(),
		"a max hit with a penalty has a detail line")


func _the_detail_line_names_the_roll_and_the_change() -> void:
	var style := HitsplatStyle.new()
	style.detail_bonus_format = "{max_hit}|+{change}"
	style.detail_penalty_format = "{max_hit}|-{change}"

	_expect(HitsplatLayer.detail_text(MAX_HIT_BONUS, style)
			== "%d|+%d" % [int(ROLL), int(CHANGE)],
		"the bonus line names the roll and the bonus")
	_expect(HitsplatLayer.detail_text(MAX_HIT_PENALTY, style)
			== "%d|-%d" % [int(ROLL), int(CHANGE)],
		"the penalty line names the roll and the penalty")


func _no_figure_draws_no_hitsplat() -> void:
	_expect(_layer.show_hit(HIT, null) == null, "no figure, no hitsplat")


func _a_hitsplat_stands_over_the_figure() -> void:
	var figure := _box_figure()
	var splat := _layer.show_hit(HIT, figure)
	var style := _layer.hit_style
	var top := FIGURE_AT.y + BOX_SIZE / 2.0

	_expect(splat != null, "a figure gets a hitsplat")
	_expect(splat.get_child_count() == 1, "a usual hit draws one line")
	_expect(absf(splat.global_position.y - (top + style.height)) < 0.001,
		"the hitsplat starts at the style height over the top")
	_expect(absf(splat.global_position.x - FIGURE_AT.x) <= style.jitter,
		"the sideways step stays inside the jitter")

	var label := splat.get_child(0) as Label3D
	_expect(label.text == HitsplatLayer.number_text(HIT, style),
		"the label shows the number")

	figure.queue_free()


func _a_changed_max_hit_draws_two_lines() -> void:
	var figure := _box_figure()
	var splat := _layer.show_hit(MAX_HIT_BONUS, figure)
	var style := _layer.max_hit_style

	_expect(splat.get_child_count() == 2, "a changed max hit draws two lines")

	var number := splat.get_child(0) as Label3D
	var line := splat.get_child(1) as Label3D
	_expect(line.text == HitsplatLayer.detail_text(MAX_HIT_BONUS, style),
		"the second line is the detail line")
	_expect(number.offset.y > line.offset.y,
		"the number stands above the detail line")

	figure.queue_free()


func _a_hitsplat_frees_itself() -> void:
	var quick := _layer.hit_style.duplicate() as HitsplatStyle
	quick.pop_seconds = SHORT_SECONDS
	quick.hold_seconds = SHORT_SECONDS
	quick.fade_seconds = SHORT_SECONDS
	_layer.hit_style = quick

	var figure := _box_figure()
	var splat := _layer.show_hit(HIT, figure)

	await get_tree().create_timer(quick.lifetime() + SETTLE_SECONDS).timeout

	_expect(not is_instance_valid(splat), "the hitsplat frees itself")

	figure.queue_free()


## A figure the way the pool builds one: a root node with a mesh under it.
func _box_figure() -> Node3D:
	var root := Node3D.new()
	var box := BoxMesh.new()
	var mesh := MeshInstance3D.new()

	box.size = Vector3.ONE * BOX_SIZE
	mesh.mesh = box
	root.add_child(mesh)
	add_child(root)
	root.global_position = FIGURE_AT

	return root


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
