extends Node
## Builds the real console scene and checks it came up whole.
##
##     godot --headless --path godot res://tests/smoke_console.tscn
##
## The ONLY test that instantiates `console.tscn`, and it exists for one class
## of failure nothing else can see: a `%UniqueName` that resolves to null, or a
## resource the scene references that no longer loads. Every other test builds
## its subject in code, so a scene edit -- a renamed node, a dropped
## `unique_name_in_owner`, a moved theme -- is invisible to all of them and
## shows up as a client that crashes on the first frame a player sees.
##
## It is a SMOKE test, not a unit test: it asserts the shell exists, not that
## anything in it is right. The socket it opens is expected to fail; there is no
## server in a headless test run, and `_on_closed` schedules a redial that this
## scene is torn down long before.

const CONSOLE := "res://scenes/console.tscn"

## A window to lay the scene out in. Headless boots at 64x64, which is smaller
## than the dock's own minimum and puts every rect on top of every other one.
const WINDOW := Vector2i(1600, 900)

## Common window sizes, from a small laptop to a 1440p screen, at a UI scale of
## 1. A 4K screen at a scale of 2 is the 1920 x 1080 row.
const WINDOWS: Array[Vector2i] = [
	Vector2i(1280, 720),
	Vector2i(1366, 768),
	Vector2i(1600, 900),
	Vector2i(1920, 1080),
	Vector2i(2560, 1440),
]

## Every node the console reaches for by unique name, and what it must be.
##
## A table rather than a run of asserts so a name added to the scene is one row
## here -- and so a failure names the node instead of a line number.
const REQUIRED := {
	"Chat": "TabContainer",
	"Input": "LineEdit",
	"Inventory": "VBoxContainer",
	"Panel": "TabContainer",
	"Login": "Control",
	"ConsoleDock": "Control",
	"PanelDock": "Control",
	"WorldPane": "Control",
	"WorldView": "SubViewportContainer",
	"WorldVitals": "MarginContainer",
	"Minimap": "Control",
	"TextVitals": "MarginContainer",
	"World": "Node3D",
	"LoadingVeil": "PanelContainer",
}

var _failures := 0


func _ready() -> void:
	var packed: PackedScene = load(CONSOLE)

	if packed == null:
		printerr("FAIL: %s did not load" % CONSOLE)
		get_tree().quit(1)
		return

	var console: Node = packed.instantiate()
	add_child(console)

	_every_unique_name_resolves(console)
	_the_theme_reached_the_tree(console)
	_the_veil_is_drawn_over_the_pane_and_not_under_it(console)
	await _the_dock_keeps_clear_of_the_minimap(console)
	_the_two_docks_ship_apart(console)
	await _the_shipped_layout_fits_each_window(console)
	_the_panel_survives_the_world_going_off(console)
	_the_input_hint_follows_login_and_focus(console)

	console.queue_free()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: console")
	get_tree().quit(0)


## The hint in the input names the login line only before login. Until
## 09/22/2026 the hint from the scene stayed after login, until the player
## pressed Enter and then Escape.
##
## On the real scene, because the bug was the scene value that nothing
## replaced. The login is the vitals flag, the same fact the form hides on.
func _the_input_hint_follows_login_and_focus(console: Node) -> void:
	var input: LineEdit = console.get_node("%Input")
	var state: CharState = console._char

	_expect(input.placeholder_text == console.LOGIN_HINT,
		"before login, the input hint is the login line")

	state.has_vitals = true
	state.changed.emit()
	console._set_typing(true)

	_expect(input.placeholder_text == console.TYPE_MODE_HINT,
		"after login, the typing hint replaces the login line")

	console._set_typing(false)

	_expect(input.placeholder_text == console.MOVE_MODE_HINT,
		"with the map on the keyboard, the hint names the movement keys")

	state.reset()

	_expect(input.placeholder_text == console.LOGIN_HINT,
		"a logout puts the login line back")


## The control panel hangs from the bottom-right corner of the world pane, and
## the minimap owns the top-right of it. That is the whole reason the dock
## picked that corner, and a default size that covered the map would undo it.
##
## Checked on the REAL scene, because the two rects come from two files: the
## minimap's offsets are authored in `console.tscn` and the box's size is
## [constant PanelDock.DEFAULT_SIZE]. Neither file can see the other.
func _the_dock_keeps_clear_of_the_minimap(console: Node) -> void:
	var dock: PanelDock = console.get_node_or_null("%PanelDock")
	var minimap: Control = console.get_node_or_null("%Minimap")

	if dock == null or minimap == null:
		_fail("the dock and the minimap both exist")
		return

	# A real window, because headless boots at 64x64 and every rect below would
	# be meaningless. Two passes after it: the first sizes the console to the
	# window, the second places the box in the pane that resize gave it.
	get_window().size = WINDOW
	_forget_saved_dock_sizes(console)
	await get_tree().process_frame
	await get_tree().process_frame

	var box := dock.box_rect()

	_expect(box.size.x > 0.0 and box.size.y > 0.0, "the box was laid out")
	_expect(not box.intersects(minimap.get_global_rect()),
		"and the shipped box does not cover the minimap")


## Put both docks back at their shipped sizes, in memory only.
##
## The console loads the REAL player profile, and a player who dragged a dock
## has a saved size in it. These cases check the SHIPPED sizes, so a saved size
## must not reach them. The setting is written on the object, not through its
## setter, so the profile on disk does not change.
func _forget_saved_dock_sizes(console: Node) -> void:
	for key: String in ClientSettings.DOCK_SIZE_KEYS:
		console._settings.set(key, Vector2i.ZERO)

	for dock_name: String in ["%ConsoleDock", "%PanelDock"]:
		var dock: PanelDock = console.get_node(dock_name)
		dock._size = Vector2.ZERO
		dock._place_box()


## The two docks hang from the two bottom corners at their shipped sizes. At
## the test window, the shipped sizes must leave a gap between them, or the
## log covers part of the bag on a first run.
##
## Runs after [method _the_dock_keeps_clear_of_the_minimap], which lays the
## scene out in the test window.
func _the_two_docks_ship_apart(console: Node) -> void:
	var log_dock: PanelDock = console.get_node_or_null("%ConsoleDock")
	var panel_dock: PanelDock = console.get_node_or_null("%PanelDock")

	if log_dock == null or panel_dock == null:
		_fail("both docks exist")
		return

	var log_box := log_dock.box_rect()

	_expect(is_equal_approx(log_box.position.x, PanelDock.EDGE_MARGIN),
		"the log dock hangs from the left edge")
	_expect(log_box.end.x < panel_dock.box_rect().position.x,
		"and the shipped docks do not overlap")


## The shipped layout at each size in [constant WINDOWS]. The panel leaves the
## minimap clear, and the docks leave a gap. A first pop-up opens in that gap
## and covers neither dock.
##
## The pop-up rect comes from [method PopupView._default_rect] with the gap
## that the console gave the view. The real view reads the player's saved rect
## first, and this case checks the shipped one.
func _the_shipped_layout_fits_each_window(console: Node) -> void:
	var log_dock: PanelDock = console.get_node("%ConsoleDock")
	var panel_dock: PanelDock = console.get_node("%PanelDock")
	var minimap: Control = console.get_node("%Minimap")
	var popup: PopupView = console._popup_view

	# The console applies the player's saved scale. Each row is at a scale of 1.
	get_window().content_scale_factor = 1.0

	for window: Vector2i in WINDOWS:
		get_window().size = window
		_forget_saved_dock_sizes(console)
		await get_tree().process_frame
		await get_tree().process_frame

		var log_box := log_dock.box_rect()
		var panel_box := panel_dock.box_rect()
		var pane := popup.size

		_expect(not panel_box.intersects(minimap.get_global_rect()),
			"%s: the panel leaves the minimap clear" % window)
		_expect(is_equal_approx(popup._gap_left, log_box.end.x)
			and is_equal_approx(popup._gap_right, panel_box.position.x),
			"%s: the pop-up has the gap between the docks" % window)

		var first := PopupView._default_rect(pane, popup._gap_left, popup._gap_right)

		_expect(not first.intersects(log_box) and not first.intersects(panel_box),
			"%s: a first pop-up covers neither dock" % window)

	get_window().size = WINDOW
	await get_tree().process_frame
	await get_tree().process_frame


## Turning the 3D world off must not take the control panel with it.
##
## The panel holds Options, and Options is where `show_world` is turned back
## on. It also holds the bag. The pane the dock hangs in used to be the node
## that `show_world` hid, so this case is the guard on the rule that replaced
## that -- see [member Console._world_pane].
##
## The setting is written on the object rather than through its setter, so this
## case never touches the player's real profile.
func _the_panel_survives_the_world_going_off(console: Node) -> void:
	var dock: Node = console.get_node_or_null("%PanelDock")
	var world_view: Node = console.get_node_or_null("%WorldView")

	if dock == null or world_view == null:
		_fail("the dock and the world view both exist")
		return

	console._settings.show_world = false
	console._apply_settings()

	_expect(not (world_view as Control).is_visible_in_tree(),
		"the 3D view goes when the world is turned off")
	_expect((dock as Control).is_visible_in_tree(),
		"and the control panel stays")

	# With no world to show, the log takes the height and the width that the
	# panel leaves. It shows no grips, because the size is not the player's.
	var log_dock: PanelDock = console.get_node_or_null("%ConsoleDock")
	var pane := (console as Control).size

	_expect(is_equal_approx(log_dock.box_rect().size.y,
		pane.y - PanelDock.EDGE_MARGIN * 2.0),
		"and the log fills the height with the world off")

	console._settings.show_world = true
	console._apply_settings()

	_expect((world_view as Control).is_visible_in_tree(),
		"and the view comes back with the setting")


func _every_unique_name_resolves(console: Node) -> void:
	for unique_name: String in REQUIRED:
		var node: Node = console.get_node_or_null("%" + unique_name)

		if node == null:
			_fail("%%%s resolves" % unique_name)
			continue

		_expect(node.is_class(REQUIRED[unique_name]),
			"%%%s is a %s" % [unique_name, REQUIRED[unique_name]])


## The theme has two homes, and each one reaches a part that the other misses.
##
## The ROOT carries it to every pane built in code, and to the 2D view of the
## editor. The PROJECT setting carries it to each Window: a PopupMenu, an
## AcceptDialog, a drag preview. Godot stops the tree lookup at a Window, so
## before 09/22/2026 the right-click menus of the slots used the default theme.
func _the_theme_reached_the_tree(console: Node) -> void:
	var control := console as Control

	if control == null:
		_fail("the console root is a Control")
		return

	_expect(control.theme != null, "the console root carries the theme")

	var project := ThemeDB.get_project_theme()
	_expect(project != null and project.resource_path == control.theme.resource_path,
		"gui/theme/custom names the same theme as the console root")

	# A Window under the root, asked for a variation that only this theme
	# declares. A zero means that the lookup stopped at the Window.
	var menu := PopupMenu.new()
	console.add_child(menu)
	_expect(menu.get_theme_constant("margin_left", &"PaneMargin") > 0,
		"a Window under the console resolves a variation from the theme")
	menu.free()


## The veil has to be the LAST child of the world pane.
##
## Sibling order IS draw order for Controls, and the veil's whole job is to
## stand in front of the 3D viewport, the minimap and the vitals. Authored
## anywhere earlier it still exists, still resolves by unique name and still
## reports the right phase -- and is drawn underneath an opaque
## SubViewportContainer, so the screen it is meant to put up is simply never
## seen. No other test can see that, and neither can a reader of `console.gd`.
func _the_veil_is_drawn_over_the_pane_and_not_under_it(console: Node) -> void:
	var pane: Node = console.get_node_or_null("%WorldPane")
	var veil: Node = console.get_node_or_null("%LoadingVeil")

	if pane == null or veil == null:
		_fail("the pane and the veil are both in the scene")
		return

	var last: Node = pane.get_child(pane.get_child_count() - 1)

	_expect(last == veil, "the veil is the last child of the world pane")

	# And the right-click menu is directly under it, for the same reason
	# stated the other way round: it has to be drawn over the viewport, the
	# minimap and the vitals, and under the veil. Over the veil it would show
	# through the loading screen; under the viewport it would be invisible,
	# which is a menu with no options at all.
	var menu: Node = console.get_node_or_null("%ChooseOption")

	if menu == null:
		_fail("the choose-option menu is in the scene")
		return

	var beneath_veil: Node = pane.get_child(pane.get_child_count() - 2)

	_expect(beneath_veil == menu,
			"the choose-option menu sits directly under the veil")
	_expect(not (menu as Control).visible,
			"and starts hidden, so it never opens itself on login")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_fail(what)


func _fail(what: String) -> void:
	_failures += 1
	printerr("  FAIL %s" % what)
