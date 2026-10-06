extends Node
## Tests for [HudArranger] -- the one owner of where each HUD element sits.
##
##     godot --headless --path godot res://tests/test_hud_arranger.tscn
##
## Each case builds a pane and a few plain controls in code. The rows here are
## not [HudElements]. Thus a retune of the shipped layout cannot fail a case.
## `smoke_console` checks the shipped layout on the real scene.

const SETTINGS_PATH := "user://test_hud_arranger.cfg"

const PANE := Vector2(1600, 900)
const SMALL_PANE := Vector2(1000, 600)

## A box that hangs from the bottom-right corner, one margin in.
const CORNER_ROW := {
	HudSlot.ROW_TITLE: "Corner",
	HudSlot.ROW_ANCHOR: Vector2(1, 1),
	HudSlot.ROW_OFFSET: Vector2(-8, -8),
	HudSlot.ROW_SIZE: Vector2(400, 500),
	HudSlot.ROW_SHARE: Vector2(0.5, 0.5),
	HudSlot.ROW_CAN_HIDE: false,
	HudSlot.ROW_FADE_BACKGROUND: true,
}

## A box at the top left, which the player can hide, and which fades whole.
const TOP_ROW := {
	HudSlot.ROW_TITLE: "Top",
	HudSlot.ROW_ANCHOR: Vector2(0, 0),
	HudSlot.ROW_OFFSET: Vector2(8, 8),
	HudSlot.ROW_SIZE: Vector2(200, 100),
	HudSlot.ROW_MIN_OPACITY: 0.2,
}

var _failures := 0


func _ready() -> void:
	_a_shipped_element_hangs_from_its_corner()
	_the_shipped_size_takes_its_share_of_a_small_pane()
	_a_moved_element_keeps_its_distance_from_its_new_corner()
	_the_content_minimum_wins_over_a_small_size()
	_a_scale_keeps_the_anchored_corner()
	_a_hidden_or_gated_element_is_not_drawn()
	_an_element_that_must_stay_cannot_be_hidden()
	_opacity_fades_the_background_or_the_whole()
	_a_filled_element_takes_the_room_beside_the_other()
	_a_reset_puts_an_element_back()
	_a_dependent_element_is_placed_after_the_others()
	await _the_layout_survives_the_client()
	_a_preset_moves_every_element()

	DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: hud_arranger")
	get_tree().quit(0)


## A pane, an arranger over it, and one slot for each row. A case that saves
## nothing gives no settings.
func _arranger(rows: Dictionary, settings: ClientSettings = null,
		pane_size: Vector2 = PANE) -> HudArranger:
	var pane := Control.new()
	add_child(pane)
	pane.size = pane_size

	var arranger := HudArranger.new()
	add_child(arranger)
	arranger.bind(pane, settings)

	for key: String in rows:
		var control: Control = PanelContainer.new()
		pane.add_child(control)
		arranger.add_slot(HudSlot.from_row(key, rows[key], control))

	return arranger


func _a_shipped_element_hangs_from_its_corner() -> void:
	var arranger := _arranger({"corner": CORNER_ROW})
	var rect := arranger.footprint("corner")
	var room := PANE - Vector2.ONE * HudLayout.EDGE_MARGIN * 2.0

	_expect(rect.end.is_equal_approx(PANE - Vector2(8, 8)),
		"the shipped box ends one margin from the bottom-right corner")
	_expect(rect.size.is_equal_approx(Vector2(400, room.y * 0.5)),
		"at its shipped size, no more than its share of the room")


func _the_shipped_size_takes_its_share_of_a_small_pane() -> void:
	var arranger := _arranger({"corner": CORNER_ROW}, null, SMALL_PANE)
	var room := SMALL_PANE - Vector2.ONE * HudLayout.EDGE_MARGIN * 2.0

	_expect(arranger.footprint("corner").size.is_equal_approx(
		(room * 0.5).min(Vector2(400, 500))),
		"a small pane gives the box its share of the room")


## The reason for anchors: a box moved to the top right stays at the top right
## when the window gets smaller.
func _a_moved_element_keeps_its_distance_from_its_new_corner() -> void:
	var arranger := _arranger({"top": TOP_ROW})
	var target := Rect2(Vector2(PANE.x - 200 - 30, 40), Vector2(200, 100))

	arranger.set_rect("top", target)
	_expect(arranger.footprint("top") == target, "the box goes where it was put")

	arranger.pane().size = SMALL_PANE
	var moved := arranger.footprint("top")

	_expect(is_equal_approx(SMALL_PANE.x - moved.end.x, 30.0),
		"and stays 30 pixels from the right edge of a smaller pane")
	_expect(is_equal_approx(moved.position.y, 40.0), "and 40 pixels from the top")


func _the_content_minimum_wins_over_a_small_size() -> void:
	var arranger := _arranger({"top": TOP_ROW})
	var control := arranger.slot("top").control
	control.custom_minimum_size = Vector2(300, 150)

	arranger.set_rect("top", Rect2(Vector2(8, 8), Vector2(50, 50)))

	_expect(arranger.footprint("top").size == Vector2(300, 150),
		"the box is never smaller than its content")


## The anchored corner stays. A box at the bottom right grows up and to the
## left, and its bottom-right corner does not move.
func _a_scale_keeps_the_anchored_corner() -> void:
	var arranger := _arranger({"corner": CORNER_ROW})
	var before := arranger.footprint("corner")

	arranger.set_element_scale("corner", 1.5)
	var after := arranger.footprint("corner")

	_expect(after.end.is_equal_approx(before.end), "the anchored corner stays")
	_expect(after.size.is_equal_approx(before.size * 1.5), "and the footprint grows by the scale")
	_expect(arranger.slot("corner").control.scale.is_equal_approx(Vector2.ONE * 1.5),
		"and the control draws at that scale")


func _a_hidden_or_gated_element_is_not_drawn() -> void:
	var arranger := _arranger({"top": TOP_ROW})
	var control := arranger.slot("top").control

	arranger.set_shown("top", false)
	_expect(not control.visible and not arranger.is_drawn("top"), "a hidden box is not drawn")

	arranger.set_shown("top", true)
	arranger.set_gate("top", false)
	_expect(not control.visible, "a box that a setting turns off is not drawn")
	_expect(arranger.is_shown("top"), "and it is still shown in the layout")

	arranger.set_gate("top", true)
	_expect(control.visible, "and it comes back with the setting")


func _an_element_that_must_stay_cannot_be_hidden() -> void:
	var arranger := _arranger({"corner": CORNER_ROW})

	arranger.set_shown("corner", false)
	_expect(arranger.is_shown("corner") and arranger.slot("corner").control.visible,
		"the control panel cannot be hidden, because it holds Options")


func _opacity_fades_the_background_or_the_whole() -> void:
	var arranger := _arranger({"corner": CORNER_ROW, "top": TOP_ROW})
	var corner := arranger.slot("corner").control
	var top := arranger.slot("top").control

	arranger.set_opacity("corner", 0.0)
	_expect(is_zero_approx(corner.self_modulate.a) and is_equal_approx(corner.modulate.a, 1.0),
		"a dock fades its background only, so its text stays")

	arranger.set_opacity("top", 0.0)
	_expect(is_equal_approx(top.modulate.a, 0.2),
		"a whole element fades no lower than its floor")


func _a_filled_element_takes_the_room_beside_the_other() -> void:
	var rows := {"corner": CORNER_ROW, "log": TOP_ROW}
	var arranger := _arranger(rows)
	var margin := HudLayout.EDGE_MARGIN

	arranger.fill_beside("log", "corner")
	var filled := arranger.footprint("log")
	var corner := arranger.footprint("corner")

	_expect(is_equal_approx(filled.size.y, PANE.y - margin * 2.0), "the fill takes the full height")
	_expect(is_equal_approx(filled.end.x, corner.position.x - margin),
		"and stops one margin short of the other box")
	_expect(arranger.is_filled("log"), "and the editor knows it has no place to drag")

	arranger.set_rect("log", Rect2(Vector2(500, 500), Vector2(100, 100)))
	_expect(arranger.footprint("log") == filled, "a drag does not move a filled box")

	arranger.fill_beside("log", "")
	_expect(arranger.footprint("log").size == Vector2(200, 100), "the box returns to its own size")


func _a_reset_puts_an_element_back() -> void:
	var arranger := _arranger({"top": TOP_ROW})
	var shipped := arranger.footprint("top")

	arranger.set_rect("top", Rect2(Vector2(700, 400), Vector2(250, 120)))
	arranger.set_opacity("top", 0.5)
	arranger.reset_element("top")

	_expect(arranger.footprint("top") == shipped, "reset puts the box back where it ships")
	_expect(is_equal_approx(arranger.opacity("top"), 1.0), "and makes it opaque")


## The hover bar ships in the gap between the docks, so its rect function reads
## the rects of the docks. It is placed after them, even when it was added
## first.
func _a_dependent_element_is_placed_after_the_others() -> void:
	var arranger := _arranger({})
	var pane := arranger.pane()
	var gap := Control.new()
	pane.add_child(gap)

	var slot := HudSlot.new("gap", "Gap", gap)
	slot.default_rect = func(_pane_size: Vector2) -> Rect2:
		var corner := arranger.footprint("corner")
		return Rect2(Vector2(0, corner.position.y), Vector2(corner.position.x, 20))
	arranger.add_slot(slot)

	var corner_control := PanelContainer.new()
	pane.add_child(corner_control)
	arranger.add_slot(HudSlot.from_row("corner", CORNER_ROW, corner_control))

	_expect(is_equal_approx(arranger.footprint("gap").size.x,
		arranger.footprint("corner").position.x),
		"the dependent box reads the rect of the box it depends on")
	_expect(arranger.others("corner").is_empty(),
		"a drag does not snap to a box that follows the dragged box")

	arranger.set_rect("gap", Rect2(Vector2(100, 100), Vector2(200, 20)))
	_expect(arranger.others("corner").size() == 1,
		"but it snaps to that box after the player places it")


## A drag writes the layout after [constant HudArranger.SAVE_DELAY], and a new
## client reads it back.
func _the_layout_survives_the_client() -> void:
	DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))
	var settings := ClientSettings.new(SETTINGS_PATH)
	var arranger := _arranger({"top": TOP_ROW}, settings)
	var target := Rect2(Vector2(600, 300), Vector2(260, 140))

	arranger.set_rect("top", target)
	arranger.set_element_scale("top", 1.25)
	_expect(settings.layout.is_empty(), "a drag does not write the file at once")

	await get_tree().create_timer(HudArranger.SAVE_DELAY * 2.0).timeout
	_expect(not settings.layout.is_empty(), "the layout is written after the delay")

	var reloaded := ClientSettings.new(SETTINGS_PATH)
	reloaded.load_from_disk()
	var second := _arranger({"top": TOP_ROW}, reloaded)

	_expect(second.footprint("top").is_equal_approx(arranger.footprint("top")),
		"a new client puts the box in the same place")
	_expect(is_equal_approx(second.element_scale("top"), 1.25), "at the same scale")


func _a_preset_moves_every_element() -> void:
	DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))
	var settings := ClientSettings.new(SETTINGS_PATH)
	var arranger := _arranger({"top": TOP_ROW}, settings)
	var shipped := arranger.footprint("top")

	arranger.set_rect("top", Rect2(Vector2(900, 600), Vector2(200, 100)))
	settings.save_layout_preset("Moved", arranger.layout())
	arranger.reset_all()
	_expect(arranger.footprint("top") == shipped, "Reset all puts the box back")

	settings.apply_layout_preset("Moved")
	_expect(arranger.footprint("top").position == Vector2(900, 600),
		"and loading the preset moves it again")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
