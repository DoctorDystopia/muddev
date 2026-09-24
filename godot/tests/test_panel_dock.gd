extends Node
## Tests for [PanelDock] -- the box the control panel hangs in.
##
##     godot --headless --path godot res://tests/test_panel_dock.tscn
##
## The dock has one job that can be wrong: where the box is and how big. Both
## are pure functions of the pane, the player's size and the content's minimum,
## so both are checked here with no window and no mouse.
##
## The BOX is built by hand rather than loaded from `console.tscn`, because the
## dock reads it as `$Box` and nothing else about the real scene matters to it.
## `smoke_console.gd` is what checks that the scene still supplies one.

## Disposable, rather than the real profile: one case here writes a size.
const SETTINGS_PATH := "user://test_panel_dock.cfg"

## The pane the box hangs in, for every case but the clamp ones.
const PANE := Vector2(1200, 900)

## A content minimum small enough that [constant PanelDock.MIN_SIZE] is the
## bound being tested. The real panel's minimum is its widest tab.
const CONTENT_MINIMUM := Vector2(120, 80)

var _failures := 0


func _ready() -> void:
	_the_box_hangs_from_the_bottom_right_corner()
	_a_drag_on_an_edge_grows_the_box_towards_it()
	_a_left_dock_hangs_from_the_bottom_left_corner()
	_a_left_dock_grows_to_the_right()
	_a_filled_dock_takes_the_room_beside_the_other()
	_the_box_stays_inside_the_pane()
	_the_content_minimum_wins_over_the_floor()
	_the_dock_does_not_take_the_mouse()
	_the_shipped_size_follows_the_pane()
	_two_docks_never_overlap()
	await _the_players_size_survives_the_client()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: panel_dock")
	get_tree().quit(0)


## A dock with a box in it, laid out in a pane of `pane` pixels.
func _dock(pane: Vector2 = PANE,
		minimum: Vector2 = CONTENT_MINIMUM,
		corner: String = PanelDock.CORNER_BOTTOM_RIGHT) -> PanelDock:
	var dock := PanelDock.new()
	dock.corner = corner

	var box := PanelContainer.new()
	box.name = "Box"
	box.custom_minimum_size = minimum
	dock.add_child(box)

	# Added BEFORE the size is set, so _ready has built the grips and the timer
	# by the time the first layout pass runs.
	add_child(dock)
	dock.size = pane

	return dock


## The corner is the whole geometry: the player owns the size, the dock owns
## where that size hangs from. See [PanelDock].
func _the_box_hangs_from_the_bottom_right_corner() -> void:
	var dock := _dock()
	dock.resize_box(Vector2(400, 300))

	var rect := dock.box_rect()
	var inset := PanelDock.EDGE_MARGIN

	_expect(is_equal_approx(rect.end.x, PANE.x - inset),
		"the right edge sits one margin off the pane")
	_expect(is_equal_approx(rect.end.y, PANE.y - inset),
		"and so does the bottom edge")
	_expect(rect.size == Vector2(400, 300), "at the size it was given")

	dock.queue_free()


## Growing means moving an edge AWAY from the corner the box hangs from. A
## sign error here makes a drag shrink the box.
func _a_drag_on_an_edge_grows_the_box_towards_it() -> void:
	var dock := _dock()
	dock.resize_box(Vector2(400, 300))

	dock._grips.drag(ResizeGrips.LEFT, Vector2(-60, 0))
	_expect(dock.box_rect().size == Vector2(460, 300),
		"dragging the left edge left widens it")

	dock._grips.drag(ResizeGrips.TOP, Vector2(0, -50))
	_expect(dock.box_rect().size == Vector2(460, 350),
		"dragging the top edge up heightens it")

	dock._grips.drag(ResizeGrips.TOP | ResizeGrips.LEFT, Vector2(60, 50))
	_expect(dock.box_rect().size == Vector2(400, 300),
		"and the corner does both at once")

	_expect(dock._grips.grip(ResizeGrips.RIGHT) == null
		and dock._grips.grip(ResizeGrips.BOTTOM) == null,
		"and the two edges on the corner have no grip")

	dock.queue_free()


## The game log hangs from the other bottom corner. Its side grip sits on the
## RIGHT edge, the one away from that corner.
func _a_left_dock_hangs_from_the_bottom_left_corner() -> void:
	var dock := _dock(PANE, CONTENT_MINIMUM, PanelDock.CORNER_BOTTOM_LEFT)
	dock.resize_box(Vector2(400, 300))

	var rect := dock.box_rect()
	var inset := PanelDock.EDGE_MARGIN

	_expect(is_equal_approx(rect.position.x, inset),
		"a left dock sits one margin off the left edge")
	_expect(is_equal_approx(rect.end.y, PANE.y - inset),
		"and one margin off the bottom")

	var side_grip := dock._grips.grip(ResizeGrips.RIGHT)
	var grip_centre := side_grip.position.x + ResizeGrips.THICKNESS / 2.0
	_expect(is_equal_approx(grip_centre, rect.end.x),
		"and its side grip is on its right edge")

	dock.queue_free()


## The mirror of the case above: for a box on the left, a drag to the RIGHT
## grows it. A sign copied from the right dock makes this drag shrink the box.
func _a_left_dock_grows_to_the_right() -> void:
	var dock := _dock(PANE, CONTENT_MINIMUM, PanelDock.CORNER_BOTTOM_LEFT)
	dock.resize_box(Vector2(400, 300))

	dock._grips.drag(ResizeGrips.RIGHT, Vector2(60, 0))
	_expect(dock.box_rect().size == Vector2(460, 300),
		"dragging the right edge right widens it")

	dock._grips.drag(ResizeGrips.TOP | ResizeGrips.RIGHT, Vector2(60, -50))
	_expect(dock.box_rect().size == Vector2(520, 350),
		"and the corner grows right and up")

	var rect := dock.box_rect()
	_expect(is_equal_approx(rect.position.x, PanelDock.EDGE_MARGIN)
		and is_equal_approx(rect.end.y, PANE.y - PanelDock.EDGE_MARGIN),
		"and the box keeps its corner")

	dock.queue_free()


## With the 3D world off, the log takes the full height and the width that the
## panel leaves. It follows a drag on the panel, and it gives the player's
## size back when the fill stops.
func _a_filled_dock_takes_the_room_beside_the_other() -> void:
	var panel := _dock()
	panel.resize_box(Vector2(400, 300))

	var log_dock := _dock(PANE, CONTENT_MINIMUM, PanelDock.CORNER_BOTTOM_LEFT)
	log_dock.resize_box(Vector2(300, 200))
	log_dock.fill_beside(panel)

	var inset := PanelDock.EDGE_MARGIN
	var rect := log_dock.box_rect()

	_expect(is_equal_approx(rect.size.y, PANE.y - inset * 2.0),
		"a filled dock takes the full height")
	_expect(is_equal_approx(rect.end.x + inset, panel.box_rect().position.x),
		"and stops one margin short of the other dock")
	_expect(not log_dock._grips.grip(ResizeGrips.RIGHT).visible,
		"and shows no grips")

	panel.resize_box(Vector2(500, 300))
	_expect(is_equal_approx(log_dock.box_rect().end.x + inset,
		panel.box_rect().position.x), "and follows a drag on the other dock")

	log_dock.fill_beside(null)
	_expect(log_dock.box_rect().size == Vector2(300, 200),
		"and the player's size comes back when the fill stops")

	panel.queue_free()
	log_dock.queue_free()


func _the_box_stays_inside_the_pane() -> void:
	var dock := _dock()
	var pane := Rect2(Vector2.ZERO, PANE).grow(-PanelDock.EDGE_MARGIN)

	dock.resize_box(Vector2(9000, 9000))
	_expect(pane.encloses(dock.box_rect()), "a huge drag stops at the pane")

	dock.resize_box(Vector2(10, 10))
	var small := dock.box_rect().size
	_expect(small.x >= PanelDock.MIN_SIZE.x and small.y >= PanelDock.MIN_SIZE.y,
		"a tiny drag stops at the smallest box")
	_expect(pane.encloses(dock.box_rect()),
		"and the smallest box is still in the pane")

	dock.queue_free()


## A box smaller than what is in it would draw its content over the world.
## The floor is the larger of the two, which is the rule [PopupView] follows.
func _the_content_minimum_wins_over_the_floor() -> void:
	var wide := PanelDock.MIN_SIZE + Vector2(200, 200)
	var dock := _dock(PANE, wide)
	dock.resize_box(Vector2(10, 10))

	_expect(dock.box_rect().size == wide,
		"the content's own minimum is the floor when it is the larger")

	dock.queue_free()


## The dock covers the whole window, so a dock that took the mouse would make
## every tile under it unclickable. Only the box and the grips may.
func _the_dock_does_not_take_the_mouse() -> void:
	var dock := _dock()

	_expect(dock.mouse_filter == Control.MOUSE_FILTER_IGNORE,
		"the dock itself passes the mouse through")
	_expect(dock._grips.grip(ResizeGrips.TOP | ResizeGrips.LEFT).mouse_filter
		== Control.MOUSE_FILTER_STOP,
		"and the grips take it")

	dock.queue_free()


## Before the first drag, the box takes its shipped size or its share of the
## room, whichever is smaller. A fixed size covered the minimap in a small
## window.
func _the_shipped_size_follows_the_pane() -> void:
	for pane: Vector2 in [Vector2(1280, 720), Vector2(2560, 1440)]:
		var dock := _dock(pane)
		var room := pane - Vector2.ONE * PanelDock.EDGE_MARGIN * 2.0
		var shipped := dock.default_size.min(room * dock.default_share)

		_expect(dock.box_rect().size.is_equal_approx(shipped),
			"in %s, the box takes the smaller of its size and its share" % pane)

		dock.queue_free()


## The log dock draws over the panel dock, so an overlap hides the panel's side
## grip under the log. Each box stops one margin short of the other, and a
## drag on either one stops there too.
func _two_docks_never_overlap() -> void:
	var panel := _dock()
	var log_dock := _dock(PANE, CONTENT_MINIMUM, PanelDock.CORNER_BOTTOM_LEFT)
	panel.keep_clear_of(log_dock)
	log_dock.keep_clear_of(panel)
	panel.resize_box(Vector2(400, 300))

	log_dock.resize_box(Vector2(9000, 300))
	var gap := panel.box_rect().position.x - log_dock.box_rect().end.x
	_expect(gap >= PanelDock.EDGE_MARGIN - 0.01,
		"a log sized over the panel stops one margin short of it")

	log_dock.resize_box(Vector2(300, 300))
	panel._grips.drag(ResizeGrips.LEFT, Vector2(-9000, 0))
	gap = panel.box_rect().position.x - log_dock.box_rect().end.x
	_expect(gap >= PanelDock.EDGE_MARGIN - 0.01,
		"and a drag on the panel stops at the log")

	panel.queue_free()
	log_dock.queue_free()


## A size the player dragged died with the client until 09/21/2026, because the
## panel was a divider offset and the divider went.
##
## Both halves are checked, because each fails on its own. The size is read the
## first time the box is PLACED, not at bind time -- the console binds every
## pane before it loads the file. And a drag writes the size the box ENDED at,
## once, after the gesture.
func _the_players_size_survives_the_client() -> void:
	_clean_settings()
	var settings := ClientSettings.new(SETTINGS_PATH)
	settings.set_dock_size(ClientSettings.KEY_PANEL_SIZE, Vector2i(640, 480))

	var dock := _dock()
	dock.bind_settings(settings)

	_expect(dock.box_rect().size == Vector2(640, 480),
		"the box opens at the size the player left")

	dock.resize_box(Vector2(500, 400))
	var ended := dock.box_rect().size
	await get_tree().create_timer(PanelDock.SIZE_SAVE_DELAY + 0.2).timeout

	var reloaded := ClientSettings.new(SETTINGS_PATH)
	reloaded.load_from_disk()
	_expect(reloaded.panel_size == Vector2i(ended),
		"and a drag writes the size the box ended at")

	dock.queue_free()
	_clean_settings()


func _clean_settings() -> void:
	if FileAccess.file_exists(SETTINGS_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
