extends Node
## Tests for [LayoutEditor] -- the mode in which the player edits the HUD.
##
##     godot --headless --path godot res://tests/test_layout_editor.tscn
##
## The drags go through [method LayoutEditor.drag_element] and
## [method LayoutEditor.size_element]. The mouse takes the same path, so a
## case here needs no mouse.

const SETTINGS_PATH := "user://test_layout_editor.cfg"
const PANE := Vector2(1600, 900)

const DOCK_ROW := {
	HudSlot.ROW_TITLE: "Dock",
	HudSlot.ROW_ANCHOR: Vector2(1, 1),
	HudSlot.ROW_OFFSET: Vector2(-8, -8),
	HudSlot.ROW_SIZE: Vector2(400, 400),
	HudSlot.ROW_CAN_HIDE: false,
}

const MAP_ROW := {
	HudSlot.ROW_TITLE: "Map",
	HudSlot.ROW_ANCHOR: Vector2(0, 0),
	HudSlot.ROW_OFFSET: Vector2(8, 8),
	HudSlot.ROW_SIZE: Vector2(200, 200),
}

## A bar that moves but only grows sideways, like the hover bar.
const BAR_ROW := {
	HudSlot.ROW_TITLE: "Bar",
	HudSlot.ROW_ANCHOR: Vector2(0, 1),
	HudSlot.ROW_OFFSET: Vector2(8, -8),
	HudSlot.ROW_SIZE: Vector2(300, 20),
	HudSlot.ROW_EDGES: ResizeGrips.LEFT | ResizeGrips.RIGHT,
}


## Counts the keys that reach it. The editor is its child, so the editor gets
## each key first, as it does under the console.
class KeyCounter extends Control:
	var count := 0

	func _unhandled_key_input(_event: InputEvent) -> void:
		count += 1


var _failures := 0
var _settings: ClientSettings
var _arranger: HudArranger
var _editor: LayoutEditor
var _host: KeyCounter


func _ready() -> void:
	DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))
	_build()

	_it_opens_with_a_frame_for_each_element()
	_a_drag_on_a_frame_moves_the_element()
	_a_drag_near_another_element_snaps_beside_it()
	_a_grip_sizes_the_element()
	_a_resize_does_not_snap_to_an_element_that_follows_it()
	_an_element_offers_only_its_own_edges()
	_a_click_selects_and_the_bar_shows_its_settings()
	_a_hidden_element_keeps_a_frame()
	_the_sliders_write_the_element()
	_a_filled_element_does_not_move()
	_a_preset_saves_loads_and_deletes()
	await _no_key_walks_the_player_while_it_is_open()
	_escape_closes_it_and_writes_the_layout()

	DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: layout_editor")
	get_tree().quit(0)


func _build() -> void:
	_settings = ClientSettings.new(SETTINGS_PATH)
	_host = KeyCounter.new()
	add_child(_host)
	_host.size = PANE

	var pane := Control.new()
	_host.add_child(pane)
	pane.size = PANE

	_arranger = HudArranger.new()
	add_child(_arranger)
	_arranger.bind(pane, _settings)

	var rows := {"dock": DOCK_ROW, "map": MAP_ROW, "bar": BAR_ROW}

	for key: String in rows:
		var control := PanelContainer.new()
		pane.add_child(control)
		_arranger.add_slot(HudSlot.from_row(key, rows[key], control))

	# A box that ships 6 pixels right of the map, as the hover bar ships
	# beside the log. Its place follows the map.
	var tail := Control.new()
	pane.add_child(tail)
	var tail_slot := HudSlot.new("tail", "Tail", tail)
	tail_slot.default_rect = func(_pane_size: Vector2) -> Rect2:
		var map := _arranger.footprint("map")
		return Rect2(Vector2(map.end.x + 6.0, map.position.y), Vector2(50, 20))
	_arranger.add_slot(tail_slot)

	_editor = LayoutEditor.new()
	_host.add_child(_editor)
	_editor.bind(_arranger, _settings)


func _it_opens_with_a_frame_for_each_element() -> void:
	var opened := {"n": 0}
	_editor.opened.connect(func() -> void: opened["n"] += 1)

	_expect(not _editor.is_open(), "the editor starts closed")

	_editor.open()
	_expect(_editor.is_open() and opened["n"] == 1, "and opens")
	_expect(_editor._frames.size() == _arranger.slots().size(), "with a frame for each element")

	var frame: Control = _editor._frames["map"]
	_expect(frame.get_rect() == _arranger.footprint("map"), "each frame sits on its element")


func _a_drag_on_a_frame_moves_the_element() -> void:
	var before := _arranger.footprint("map")

	_editor.drag_element("map", Vector2(333, 211))
	var after := _arranger.footprint("map")

	_expect(after.position.is_equal_approx(before.position + Vector2(333, 211)),
		"the element moves by the drag")
	_expect((_editor._frames["map"] as Control).get_rect() == after, "and its frame follows")
	_expect(_editor.selected() == "map", "and the drag selects it")


## The dock sits at the bottom right. A map dragged to four pixels over one gap
## to the left of it snaps to one gap to the left of it.
func _a_drag_near_another_element_snaps_beside_it() -> void:
	var dock := _arranger.footprint("dock")
	var map := _arranger.footprint("map")
	var target_x := dock.position.x - HudLayout.GAP - map.size.x + 4.0
	var target := Vector2(target_x, dock.position.y + 57.0)

	_editor.drag_element("map", target - map.position)

	_expect(is_equal_approx(_arranger.footprint("map").end.x, dock.position.x - HudLayout.GAP),
		"the right edge snaps one gap beside the dock")


func _a_grip_sizes_the_element() -> void:
	_arranger.reset_element("map")
	var before := _arranger.footprint("map")

	_editor.size_element("map", ResizeGrips.BOTTOM | ResizeGrips.RIGHT, Vector2(123, 77))
	var after := _arranger.footprint("map")

	_expect(after.size.is_equal_approx(before.size + Vector2(123, 77)), "the corner grip sizes it")
	_expect(after.position == before.position, "and the top-left corner stays")


## The jitter of 09/29/2026. The hover bar ships one margin right of the log.
## A drag on the right grip of the log snapped the edge to one gap left of the
## hover bar: 2 pixels behind the edge. Each mouse step pulled the edge back,
## and the hover bar followed it.
##
## One whole drag, in small steps, as the mouse gives it. The edge must follow
## the mouse on each step.
func _a_resize_does_not_snap_to_an_element_that_follows_it() -> void:
	_arranger.reset_element("map")
	var grips: ResizeGrips = _editor._grips["map"]
	var start := _arranger.footprint("map").end.x
	var step := 3.0
	var steps := 8
	var followed := true

	grips._start(ResizeGrips.RIGHT)

	for index: int in range(1, steps + 1):
		grips._move(Vector2(step * index, 0))

		if not is_equal_approx(_arranger.footprint("map").end.x, start + step * index):
			followed = false

	grips._drag_edges = 0

	_expect(followed, "the right edge follows each step of the mouse")
	_expect(is_equal_approx(_arranger.footprint("tail").position.x,
		_arranger.footprint("map").end.x + 6.0), "and the box that follows it moves with it")

	_arranger.reset_element("map")


func _an_element_offers_only_its_own_edges() -> void:
	var grips: ResizeGrips = _editor._grips["bar"]

	_expect(grips.grip(ResizeGrips.LEFT) != null and grips.grip(ResizeGrips.RIGHT) != null,
		"the bar has side grips")
	_expect(grips.grip(ResizeGrips.TOP) == null, "and no top grip, because it does not grow up")


func _a_click_selects_and_the_bar_shows_its_settings() -> void:
	_editor.select("")
	_expect(_editor._hint.visible and not _editor._element_row.visible,
		"with nothing selected, the bar shows the hint")

	_editor.select("dock")
	_expect(_editor._element_row.visible, "a selected element shows its settings")
	_expect(_editor._shown_check.disabled, "and the dock cannot be hidden")

	_editor.select("map")
	_expect(not _editor._shown_check.disabled, "but the map can")


func _a_hidden_element_keeps_a_frame() -> void:
	_editor.select("map")
	_editor._shown_check.button_pressed = false

	_expect(not _arranger.is_shown("map"), "the Shown box hides the element")
	_expect((_editor._frames["map"] as Control).visible,
		"and its frame stays, so the player can show it again")
	_expect((_editor._titles["map"] as Label).text.contains(LayoutEditor.NOTE_HIDDEN),
		"and the frame says that it is hidden")

	_editor._shown_check.button_pressed = true
	_expect(_arranger.is_shown("map"), "and the box shows it again")


func _the_sliders_write_the_element() -> void:
	_editor.select("map")
	_editor._opacity_slider.value = 0.5
	_editor._scale_slider.value = 1.5

	_expect(is_equal_approx(_arranger.opacity("map"), 0.5), "the opacity slider fades it")
	_expect(is_equal_approx(_arranger.element_scale("map"), 1.5), "the scale slider scales it")
	_expect(_editor._scale_value.text == "150%", "and the bar shows the scale")

	_arranger.reset_element("map")


func _a_filled_element_does_not_move() -> void:
	_arranger.fill_beside("bar", "dock")
	var filled := _arranger.footprint("bar")

	_editor.drag_element("bar", Vector2(50, -50))
	_expect(_arranger.footprint("bar") == filled, "a drag does not move a filled element")
	_expect(not (_editor._grips["bar"] as ResizeGrips).grip(ResizeGrips.LEFT).visible,
		"and its grips are hidden")
	_expect((_editor._titles["bar"] as Label).text.contains(LayoutEditor.NOTE_FILLED),
		"and the frame says why")

	_arranger.fill_beside("bar", "")


func _a_preset_saves_loads_and_deletes() -> void:
	_arranger.reset_all()
	_editor.drag_element("map", Vector2(400, 300))
	var moved := _arranger.footprint("map")

	_expect(not _editor.save_preset("   "), "a preset with no name is refused")
	_expect(_editor._status.text == LayoutEditor.STATUS_NO_NAME, "and the bar says why")
	_expect(_editor.save_preset("Mine"), "a named preset saves")
	_expect(_editor._chosen_preset() == "Mine", "and the list selects it")

	_arranger.reset_all()
	_editor.load_preset("Mine")
	_expect(_arranger.footprint("map") == moved, "loading the preset moves the map back")

	_editor.delete_preset("Mine")
	_expect(_settings.layout_preset_names().is_empty(), "and delete forgets it")
	_expect(_editor._load_button.disabled, "and Load has nothing to load")


## A movement key must not walk the player behind the editor. Godot gives an
## unhandled key to a child before its parent, as under the console.
func _no_key_walks_the_player_while_it_is_open() -> void:
	var key := InputEventKey.new()
	key.keycode = KEY_W
	key.pressed = true

	_host.count = 0
	get_viewport().push_input(key)
	await get_tree().process_frame
	_expect(_host.count == 0, "a key does not reach the console while the editor is open")

	_editor.close()
	get_viewport().push_input(key)
	await get_tree().process_frame
	_expect(_host.count == 1, "and reaches it again after the editor closes")

	_editor.open()


func _escape_closes_it_and_writes_the_layout() -> void:
	var closed := {"n": 0}
	_editor.closed.connect(func() -> void: closed["n"] += 1)
	_editor.drag_element("map", Vector2(10, 10))

	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	_editor._input(escape)

	_expect(not _editor.is_open() and closed["n"] == 1, "Escape closes the editor")
	_expect(_settings.layout.has("map"), "and the layout is written at once")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
