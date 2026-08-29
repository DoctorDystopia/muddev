extends Node
## Unit tests for VitalsBars.
##
##     godot --headless --path godot res://tests/test_vitals_bars.tscn
##
## Needs nothing running. Feeds a real [CharState] the payloads the server
## sends and reads the bars back.

const Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_every_row_names_a_property_char_state_has()
	_no_data_is_not_the_same_as_dead()
	_a_reading_arrives_and_the_bar_follows_it()
	_the_colour_grades_with_the_fraction()
	_the_bars_never_swallow_a_click()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: vitals_bars")
	get_tree().quit(0)


func _built() -> Array:
	var state := CharState.new()
	var bars := VitalsBars.new()
	add_child(bars)
	bars.bind(state)

	return [state, bars]


## The reading beside one bar, as the player sees it.
func _reading(bars: VitalsBars, index: int) -> String:
	var row := bars.get_child(index) as HBoxContainer

	return (row.get_child(2) as Label).text


func _fill(bars: VitalsBars, index: int) -> ProgressBar:
	return (bars.get_child(index) as HBoxContainer).get_child(1) as ProgressBar


## The guard that pays for the table being data.
##
## BARS names CharState PROPERTIES as strings so this view has no branch per
## resource. Strings are not checked by the compiler, so a renamed field would
## draw an empty bar for ever and look like a server that had gone quiet.
func _every_row_names_a_property_char_state_has() -> void:
	var state := CharState.new()
	var known: Dictionary = {}

	for entry: Dictionary in state.get_property_list():
		known[str(entry.get("name", ""))] = true

	for row: Dictionary in VitalsBars.BARS:
		for field: String in ["current", "maximum"]:
			var property := str(row.get(field, ""))

			if not known.has(property):
				_fail('bar "%s" reads CharState.%s, which does not exist'
					% [row.get("label", "?"), property])
				return

	_pass("every bar reads a property CharState actually has")


func _no_data_is_not_the_same_as_dead() -> void:
	# An empty bar at login reads as being dead, which is why the maximum and
	# not the current value decides this.
	var built := _built()
	var bars: VitalsBars = built[1]

	_expect(_reading(bars, 0) == VitalsBars.NO_DATA_TEXT,
		"before any vitals arrive the bar says so")
	_expect(_fill(bars, 0).modulate == VitalsBars.COLOR_IDLE,
		"and is drawn as idle rather than critical")


func _a_reading_arrives_and_the_bar_follows_it() -> void:
	var built := _built()
	var state: CharState = built[0]
	var bars: VitalsBars = built[1]

	# The float shape JSON.parse_string actually produces.
	state.ingest(Const.CH_CHAR_VITALS, {"hp": 30.0, "max_hp": 60.0})

	_expect(_reading(bars, 0) == "30/60", "the reading is the server's numbers")
	_expect(is_equal_approx(_fill(bars, 0).value, 0.5),
		"and the bar is half full")

	# Dead is a real state and must not read as "no data".
	state.ingest(Const.CH_CHAR_VITALS, {"hp": 0.0, "max_hp": 60.0})
	_expect(_reading(bars, 0) == "0/60", "zero hit points reads as zero")


func _the_colour_grades_with_the_fraction() -> void:
	var built := _built()
	var state: CharState = built[0]
	var bars: VitalsBars = built[1]
	var fill := _fill(bars, 0)

	state.ingest(Const.CH_CHAR_VITALS, {"hp": 100.0, "max_hp": 100.0})
	_expect(fill.modulate == VitalsBars.COLOR_HEALTHY, "full is healthy")

	state.ingest(Const.CH_CHAR_VITALS, {"hp": 50.0, "max_hp": 100.0})
	_expect(fill.modulate == VitalsBars.COLOR_HURT, "half is hurt")

	state.ingest(Const.CH_CHAR_VITALS, {"hp": 10.0, "max_hp": 100.0})
	_expect(fill.modulate == VitalsBars.COLOR_CRITICAL, "a tenth is critical")


func _the_bars_never_swallow_a_click() -> void:
	# They are drawn OVER the world pane, where a click means walk. A bar that
	# ate one would make the top-left corner of the map dead.
	var built := _built()
	var bars: VitalsBars = built[1]

	_expect(bars.mouse_filter == Control.MOUSE_FILTER_IGNORE,
		"the strip ignores the mouse")

	var row := bars.get_child(0) as Control
	_expect(row.mouse_filter == Control.MOUSE_FILTER_IGNORE,
		"and so does each row")

	for index: int in row.get_child_count():
		var child := row.get_child(index) as Control
		_expect(child.mouse_filter == Control.MOUSE_FILTER_IGNORE,
			"and so does %s" % child.get_class())


func _expect(passed: bool, what: String) -> void:
	if passed:
		_pass(what)
		return

	_fail(what)


func _pass(what: String) -> void:
	print("  ok   %s" % what)


func _fail(what: String) -> void:
	_failures += 1
	printerr("  FAIL %s" % what)
