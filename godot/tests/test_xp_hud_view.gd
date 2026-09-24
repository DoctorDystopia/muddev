extends Node
## Unit tests for XpHudView.
##
##     godot --headless --path godot res://tests/test_xp_hud_view.tscn
##
## Needs nothing running. Asserts what a screenshot would not: that the HUD
## never takes a click, draws nothing before an award, and that every number it
## prints is the model's.

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0
var _now := {"seconds": 50.0}


func _ready() -> void:
	_numbers_are_grouped_in_thousands()
	_nothing_is_drawn_before_an_award()
	_an_award_draws_the_strip_and_the_bar()
	_a_rate_reads_as_dashes_until_it_means_something()
	_an_award_is_one_drop_row_naming_every_skill()
	_drops_on_one_tick_are_queued_rather_than_stacked()
	_the_bar_fills_from_the_level_fraction()
	_the_bar_glides_through_a_level_rise()
	_per_skill_rates_are_a_row_per_skill_when_asked_for()
	_a_level_rise_is_announced_by_name()
	_no_part_of_the_hud_takes_a_click()
	_a_reset_hides_the_column_again()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: xp_hud_view")
	get_tree().quit(0)


func _built() -> Array:
	var tracker := XpTrackerState.new()
	tracker.clock = func() -> float: return _now["seconds"]

	var skills := SkillsState.new()
	var view := XpHudView.new()
	view.size = Vector2(800.0, 240.0)
	add_child(view)
	view.bind(tracker, skills)

	return [view, tracker, skills]


func _payload() -> Dictionary:
	return {"kind": _Const.MSG_GATHERING, "awards": [
		{"skill_key": "butchery", "name": "Butchery", "category": "Gathering",
			"amount": 25.0, "level": 3.0, "current_xp": 60.0, "needed_xp": 120.0},
		{"skill_key": "cutting", "name": "Cutting", "category": "Gathering",
			"amount": 5.0, "level": 11.0, "current_xp": 400.0, "needed_xp": 620.0},
	]}


func _numbers_are_grouped_in_thousands() -> void:
	_expect(XpHudView.thousands(0) == "0", "zero")
	_expect(XpHudView.thousands(999) == "999", "three digits need no separator")
	_expect(XpHudView.thousands(1000) == "1,000", "four do")
	_expect(XpHudView.thousands(1234567) == "1,234,567", "and so does a million")


func _nothing_is_drawn_before_an_award() -> void:
	# An empty "session 0 xp" strip over the world is a readout of nothing.
	var parts := _built()
	var view: XpHudView = parts[0]

	_expect(not view._column.visible, "the column is hidden before any award")

	view.queue_free()


func _an_award_draws_the_strip_and_the_bar() -> void:
	var parts := _built()
	var view: XpHudView = parts[0]
	var tracker: XpTrackerState = parts[1]

	for _index: int in 40:
		tracker.ingest(_Const.CH_XP_DROP, _payload())

	_expect(view._column.visible, "an award shows the column")
	_expect(view._total_label.text == "session 1,200 xp",
		"the strip reads the session total, grouped")
	_expect(not view._total_label.text.contains("uplink"),
		"and carries no label beyond what it counts")
	_expect(view._next_label.text == "butchery 3 → 4 · 60 to go",
		"the bar is labelled for the award's primary skill")

	view.queue_free()


func _a_rate_reads_as_dashes_until_it_means_something() -> void:
	var parts := _built()
	var view: XpHudView = parts[0]
	var tracker: XpTrackerState = parts[1]

	tracker.ingest(_Const.CH_XP_DROP, _payload())
	_expect(view._rate_label.text == "-- xp/hr", "no rate during the warm-up")

	_now["seconds"] += 3600.0
	view._redraw()
	_expect(view._rate_label.text == "30 xp/hr", "and the real one after it")

	view.queue_free()


func _an_award_is_one_drop_row_naming_every_skill() -> void:
	var parts := _built()
	var view: XpHudView = parts[0]
	var tracker: XpTrackerState = parts[1]

	tracker.ingest(_Const.CH_XP_DROP, _payload())

	var rows := view._drops.get_children()
	_expect(rows.size() == 1, "one award is one drop row")

	var texts: Array[String] = []

	if rows.size() == 1:
		for label: Node in rows[0].get_children():
			texts.append((label as Label).text)

	_expect(texts == ["+25 Butchery", "+5 Cutting"],
		"naming every skill it taught, in the order earned")

	var first := rows[0].get_child(0) as Label if rows.size() == 1 else null
	_expect(first != null and first.get_theme_color("font_color")
		== SkillPalette.color_for("Gathering"),
		"coloured by the skill's category, from the palette")

	view.queue_free()


func _drops_on_one_tick_are_queued_rather_than_stacked() -> void:
	# Two awards on one tick started at the same pixel and printed over each
	# other until the queue existed.
	_expect(is_zero_approx(XpHudView.queued_delay(10.0, 0.0)),
		"a drop with nothing ahead of it rises at once")
	_expect(is_equal_approx(XpHudView.queued_delay(10.0, 10.2), 0.2),
		"one arriving on another's heels waits its turn")
	_expect(is_equal_approx(XpHudView.queued_delay(10.0, 99.0),
		XpHudView.DROP_MAX_DELAY_SECONDS),
		"and a backlog never holds a drop past the cap")


func _the_bar_fills_from_the_level_fraction() -> void:
	var parts := _built()
	var view: XpHudView = parts[0]
	var tracker: XpTrackerState = parts[1]

	_expect(is_zero_approx(view.bar_fraction()), "an empty bar before any award")

	tracker.ingest(_Const.CH_XP_DROP, _payload())
	_expect(is_equal_approx(view.bar_fraction(), 0.5), "60 of 120 fills half the bar")
	_expect(view._bar_shown < view.bar_fraction(),
		"and the bar glides there rather than jumping")

	view.queue_free()


func _the_bar_glides_through_a_level_rise() -> void:
	# The bar is continuous like the HP bar, so a jump would read as a glitch.
	_expect(XpHudView.glide_legs(0.3, 0.6, true, false) == [[0.3, 0.6]],
		"the same level glides once from where the bar stands")
	_expect(XpHudView.glide_legs(0.9, 0.1, true, true) == [[0.9, 1.0], [0.0, 0.1]],
		"a level rise fills to the end, then from empty")
	_expect(XpHudView.glide_legs(0.9, 0.4, false, false) == [[0.0, 0.4]],
		"a new skill fills from empty, never from the old skill's value")


func _per_skill_rates_are_a_row_per_skill_when_asked_for() -> void:
	var parts := _built()
	var view: XpHudView = parts[0]
	var tracker: XpTrackerState = parts[1]

	tracker.ingest(_Const.CH_XP_DROP, _payload())

	_expect(not view._rates.visible, "per-skill rates are off by default")

	view.set_skill_rates_shown(true)
	_expect(view._rates.visible, "and shown when asked for")
	_expect(view._rates.get_child_count() == 2 * view._rates.columns,
		"one row per skill trained this session")
	_expect((view._rates.get_child(0) as Label).text == "Butchery",
		"each named as the award named it")

	view.queue_free()


func _a_level_rise_is_announced_by_name() -> void:
	# From SkillsState.levelled, the one owner of "a level rose".
	var parts := _built()
	var view: XpHudView = parts[0]
	var tracker: XpTrackerState = parts[1]
	var skills: SkillsState = parts[2]

	tracker.ingest(_Const.CH_XP_DROP, _payload())
	skills.levelled.emit("cutting", 12)

	_expect(view._flare_label.text == "level up // cutting 12",
		"the level-up line names the skill and the level reached")

	view.queue_free()


func _no_part_of_the_hud_takes_a_click() -> void:
	# The HUD sits over the 3D world; a control that stopped a click would eat a
	# move meant for the tile under it.
	var parts := _built()
	var view: XpHudView = parts[0]
	var tracker: XpTrackerState = parts[1]

	tracker.ingest(_Const.CH_XP_DROP, _payload())
	view.set_skill_rates_shown(true)

	for control: Control in _controls(view, [] as Array[Control]):
		if control.mouse_filter != Control.MOUSE_FILTER_IGNORE:
			_fail("%s takes the mouse" % control.get_class())
			view.queue_free()
			return

	_expect(true, "every control in the HUD ignores the mouse")

	view.queue_free()


func _a_reset_hides_the_column_again() -> void:
	var parts := _built()
	var view: XpHudView = parts[0]
	var tracker: XpTrackerState = parts[1]

	tracker.ingest(_Const.CH_XP_DROP, _payload())
	tracker.reset()

	_expect(not view._column.visible, "a new session starts hidden")

	view.queue_free()


func _controls(node: Node, into: Array[Control]) -> Array[Control]:
	if node is Control:
		into.append(node as Control)

	for child: Node in node.get_children():
		_controls(child, into)

	return into


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_fail(what)


func _fail(what: String) -> void:
	_failures += 1
	printerr("  FAIL %s" % what)
