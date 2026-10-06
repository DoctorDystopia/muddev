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

## Server-owned names, for the hand-built chat payload.
const Const := preload("res://autoload/blackout_constants.gd")

## A scratch profile. The console never sees the player's `client.cfg`, so a
## dragged dock or `show_world=false` there cannot fail a case (handoff debt
## 9.1.4).
const SETTINGS_PATH := "user://smoke_console.cfg"

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
	"Chat": "Control",
	"ChatBar": "HBoxContainer",
	"ChatMode": "Button",
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

	DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))

	var console: Node = packed.instantiate()
	console.settings_path = SETTINGS_PATH
	add_child(console)

	_every_unique_name_resolves(console)
	_the_theme_reached_the_tree(console)
	_the_veil_is_drawn_over_the_pane_and_not_under_it(console)
	await _the_dock_keeps_clear_of_the_minimap(console)
	_the_two_docks_ship_apart(console)
	await _the_shipped_layout_fits_each_window(console)
	_the_panel_survives_the_world_going_off(console)
	_the_input_hint_follows_login_and_focus(console)
	_the_world_map_sits_over_the_docks_and_under_the_veil(console)
	_the_minimap_strip_stays_inside_the_minimap(console)
	_the_keys_follow_the_camera_only_when_asked(console)
	_the_layout_editor_opens_from_options(console)

	console.queue_free()
	DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))

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

	# A chat mode names itself in both hints, and Command gives them back.
	var modes: ChatModes = console._chat_modes
	modes.ingest(Const.CH_CHAR_CHAT, {"speaker": "Nick", "modes": [
		{"key": "say", "label": "Say", "type": "say", "prefix": "say "}]})
	modes.select("say")

	_expect(input.placeholder_text == console.CHAT_MOVE_HINT % "Say",
		"in a chat mode, the map hint names the mode")

	console._set_typing(true)
	_expect(input.placeholder_text == console.CHAT_TYPE_HINT % "Say",
		"and so does the typing hint")

	modes.select(ChatModes.COMMAND_KEY)
	_expect(input.placeholder_text == console.TYPE_MODE_HINT,
		"Command mode gives the command hint back")

	console._set_typing(false)
	modes.reset()

	state.reset()

	_expect(input.placeholder_text == console.LOGIN_HINT,
		"a logout puts the login line back")


## The world map (09/28/2026) covers the docks, as the OSRS world map covers
## the game. The right-click menu and the veil stay over it. The minimap
## button reaches it, and it opens and closes.
func _the_world_map_sits_over_the_docks_and_under_the_veil(console: Node) -> void:
	var view: WorldMapView = console._world_map_view
	var pane: Control = console.get_node("%WorldPane")
	var at := view.get_index()

	_expect(view.get_parent() == pane, "the world map is a box of the world pane")
	_expect(at > console.get_node("%PanelDock").get_index(),
		"the world map is over the panel dock")
	_expect(at < console.get_node("%ChooseOption").get_index(),
		"and under the right-click menu")
	_expect(at < console.get_node("%LoadingVeil").get_index(),
		"and under the veil")
	_expect(console._minimap.world_map_requested.is_connected(
		console._open_world_map), "the minimap button opens it")

	view.open()
	_expect(view.visible, "it opens")
	view.close()
	_expect(not view.visible, "and it closes")


## The button strip of the minimap is part of the minimap rect, so the dock
## check above covers it. The XP HUD sits to the left of it.
## The real camera gives a heading, and the console turns a key by it only
## with the Options box on.
func _the_keys_follow_the_camera_only_when_asked(console: Node) -> void:
	var forward: Vector2 = console._world.camera_forward()
	var settings: ClientSettings = console._settings
	var was := settings.camera_relative_keys

	_expect(not forward.is_zero_approx(), "the camera gives a heading")

	settings.camera_relative_keys = false
	_expect(console._steer("north") == "north", "with the box off, W is north")

	settings.camera_relative_keys = true
	_expect(console._steer("north") == MovementKeys.nearest(forward),
		"with the box on, W walks where the camera looks")

	settings.camera_relative_keys = was


func _the_minimap_strip_stays_inside_the_minimap(console: Node) -> void:
	var minimap: MinimapView = console.get_node("%Minimap")
	var hud: Control = console.get_node("%XpHud")
	var rect := minimap.get_global_rect()

	_expect(rect.encloses(minimap._world_map_button.get_global_rect()),
		"the world map button is inside the minimap")
	_expect(not rect.intersects(hud.get_global_rect()),
		"the minimap does not cover the XP HUD")


## The control panel hangs from the bottom-right corner of the world pane, and
## the minimap owns the top-right of it. A shipped size that covered the map
## would undo that.
##
## Checked on the REAL scene, because the rects come from the arranger, the
## rows of [HudElements], and the minimums of the real content. No other test
## has all three.
func _the_dock_keeps_clear_of_the_minimap(console: Node) -> void:
	var arranger: HudArranger = console._arranger

	# A real window, because headless boots at 64x64 and every rect below would
	# be meaningless. Two passes after it: the first sizes the console to the
	# window, the second places the elements in the pane that resize gave it.
	get_window().size = WINDOW
	arranger.reset_all()
	await get_tree().process_frame
	await get_tree().process_frame

	var box := arranger.footprint(HudElements.PANEL)

	_expect(box.size.x > 0.0 and box.size.y > 0.0, "the box was laid out")
	_expect(not box.intersects(arranger.footprint(HudElements.MINIMAP)),
		"and the shipped box does not cover the minimap")


## The two docks hang from the two bottom corners at their shipped sizes. At
## the test window, the shipped sizes must leave a gap between them, or the
## log covers part of the bag on a first run.
##
## Runs after [method _the_dock_keeps_clear_of_the_minimap], which lays the
## scene out in the test window.
func _the_two_docks_ship_apart(console: Node) -> void:
	var arranger: HudArranger = console._arranger
	var log_box := arranger.footprint(HudElements.LOG)

	_expect(is_equal_approx(log_box.position.x, HudLayout.EDGE_MARGIN),
		"the log dock hangs from the left edge")
	_expect(log_box.end.x < arranger.footprint(HudElements.PANEL).position.x,
		"and the shipped docks do not overlap")


## The shipped layout at each size in [constant WINDOWS]. No two elements
## overlap, and the docks leave a gap. A first pop-up opens in that gap and
## covers neither dock.
##
## The pop-up rect comes from [method PopupView._default_rect] with the gap
## that the console gave the view. The real view reads the player's saved rect
## first, and this case checks the shipped one.
func _the_shipped_layout_fits_each_window(console: Node) -> void:
	var arranger: HudArranger = console._arranger
	var popup: PopupView = console._popup_view

	# The console applies the player's saved scale. Each row is at a scale of 1.
	get_window().content_scale_factor = 1.0

	for window: Vector2i in WINDOWS:
		get_window().size = window
		arranger.reset_all()
		await get_tree().process_frame
		await get_tree().process_frame

		var log_box := arranger.footprint(HudElements.LOG)
		var panel_box := arranger.footprint(HudElements.PANEL)
		var pane := popup.size

		_expect(_nothing_overlaps(arranger),
			"%s: no two shipped elements overlap" % window)
		_expect(is_equal_approx(popup._gap_left, log_box.end.x)
			and is_equal_approx(popup._gap_right, panel_box.position.x),
			"%s: the pop-up has the gap between the docks" % window)

		var first := PopupView._default_rect(pane, popup._gap_left, popup._gap_right)

		_expect(not first.intersects(log_box) and not first.intersects(panel_box),
			"%s: a first pop-up covers neither dock" % window)

	get_window().size = WINDOW
	await get_tree().process_frame
	await get_tree().process_frame


## True when no two drawn elements of the arranger overlap.
func _nothing_overlaps(arranger: HudArranger) -> bool:
	var keys: Array[String] = []

	for slot: HudSlot in arranger.slots():
		if arranger.is_drawn(slot.key):
			keys.append(slot.key)

	for first: int in keys.size():
		for second: int in range(first + 1, keys.size()):
			var one := arranger.footprint(keys[first])
			var other := arranger.footprint(keys[second])

			if one.intersects(other):
				printerr("    %s %s overlaps %s %s" % [keys[first], one,
					keys[second], other])
				return false

	return true


## The layout editor is the last child of the console, so it draws over the
## docks, the veil and the right-click menu. The Options button opens it, it
## has a frame for each element, and Escape closes it.
func _the_layout_editor_opens_from_options(console: Node) -> void:
	var editor: LayoutEditor = console._layout_editor
	var options: OptionsView = console._options

	_expect(editor.get_index() == console.get_child_count() - 1,
		"the layout editor is the last child of the console")
	_expect(not editor.is_open(), "and it starts closed")

	options.layout_edit_requested.emit()
	_expect(editor.is_open(), "the Options button opens it")
	_expect(editor._frames.size() == HudElements.ROWS.size(),
		"with a frame for each HUD element")

	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	editor._input(escape)
	_expect(not editor.is_open(), "and Escape closes it")


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
	# panel leaves. The editor shows no grips on it, because the player did
	# not choose that size.
	var arranger: HudArranger = console._arranger
	var pane := (console as Control).size

	_expect(is_equal_approx(arranger.footprint(HudElements.LOG).size.y,
		pane.y - HudLayout.EDGE_MARGIN * 2.0),
		"and the log fills the height with the world off")
	_expect(not arranger.is_drawn(HudElements.MINIMAP),
		"and the minimap goes with the world")

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
