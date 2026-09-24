extends Node
## Tests for the pop-up's jobs that can be wrong: it shows only while the server
## holds it open, every command leaving it was named by the server, a left
## click sends the row's FIRST action, and the close button asks rather than
## closes.
##
## The drawing is not tested beyond counts. Slots are cheap to look at and
## expensive to assert.
##
##     godot --headless --path godot res://tests/test_popup_view.tscn

const _Const := preload("res://autoload/blackout_constants.gd")
const _StateTest := preload("res://tests/test_popup_state.gd")

## Disposable, rather than the real profile: one case here writes a rect.
const SETTINGS_PATH := "user://test_popup_view.cfg"

var _failures := 0
var _view: PopupView
var _state: PopupState
var _sent: Array[String] = []


func _ready() -> void:
	_state = PopupState.new()
	_view = PopupView.new()
	add_child(_view)
	_view.command_requested.connect(func(command: String): _sent.append(command))
	_view.bind(_state, null)

	_nothing_shows_before_a_snapshot()

	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.bank_payload())

	_an_open_snapshot_shows_the_box()
	_every_slot_the_server_counted_is_drawn()
	_a_left_click_sends_the_first_action()
	_a_right_click_lists_every_action_in_order()
	_an_empty_slot_sends_nothing()
	_the_active_quantity_button_is_lit()
	_a_quantity_press_sends_and_does_not_relight()
	_hovering_a_slot_names_it_and_its_click()
	_the_bar_follows_a_rebuild_under_the_mouse()
	_leaving_a_slot_clears_the_bar()
	_close_asks_the_server_and_stays_open()
	_a_closed_snapshot_clears_the_bar()
	_a_closed_snapshot_hides_the_box()
	_a_dim_slot_is_dim_and_still_sends()
	_the_detail_line_and_the_footer_are_drawn()
	_a_menu_node_draws_text_options_and_a_box()
	_a_menu_option_sends_its_key()
	_the_box_sends_what_was_typed()
	_a_number_key_picks_the_option()
	_many_choices_share_one_scroll_with_the_text()
	_the_count_sits_in_the_corner_not_the_detail_line()
	_a_timed_station_draws_its_slots()
	_a_grid_pop_up_has_no_side_panel()
	_the_box_stays_inside_the_pane()
	_every_edge_and_corner_has_a_raised_grip()
	_a_drag_on_one_edge_keeps_the_other_edges()
	_the_first_box_opens_between_the_docks()
	await _a_wide_box_can_be_made_narrow_again()
	await _the_players_box_survives_the_client()
	_the_grid_fits_its_columns_to_the_width()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: popup_view")
	get_tree().quit(0)


func _nothing_shows_before_a_snapshot() -> void:
	_expect(not _view.visible, "the box is hidden until the server opens it")


func _an_open_snapshot_shows_the_box() -> void:
	_expect(_view.visible, "an open snapshot shows the box")
	_expect(_view.title_text() == "Bank Vault", "the server's title is drawn")
	_expect(_view.status_text().begins_with("Vault"), "the status line is drawn")


func _every_slot_the_server_counted_is_drawn() -> void:
	_expect(_view.slots_in(0).size() == 1, "the vault draws its one slot")
	_expect(_view.slots_in(1).size() == 32, "the inventory draws all 32 frames")


func _a_left_click_sends_the_first_action() -> void:
	_sent.clear()
	var slot: PopupSlot = _view.slots_in(0)[0]

	slot.activate()

	_expect(_sent_only("withdraw rusty metal dust 5"),
		"a left click sends the first action, byte for byte")


func _a_right_click_lists_every_action_in_order() -> void:
	var slot: PopupSlot = _view.slots_in(0)[0]
	var labels := slot.menu_labels()

	_expect(labels.size() == 4, "every action is offered")
	_expect(labels[0] == "Withdraw 5" and labels[3] == "Withdraw All",
		"in the order the server listed them")


func _an_empty_slot_sends_nothing() -> void:
	_sent.clear()
	var slot: PopupSlot = _view.slots_in(1)[0]

	slot.activate()

	_expect(_sent.is_empty(), "an empty frame affords nothing")


func _the_active_quantity_button_is_lit() -> void:
	var lit: Array = []

	for button: Button in _view.quantity_buttons():
		if button.button_pressed:
			lit.append(button.text)

	_expect(lit == ["5"], "only the mode the server named is lit")


func _a_quantity_press_sends_and_does_not_relight() -> void:
	_sent.clear()
	var first: Button = _view.quantity_buttons()[0]

	first.set_pressed_no_signal(true)
	first.pressed.emit()

	_expect(_sent_only("popup quantity 1"),
		"a press sends the server's command")
	_expect(not first.button_pressed,
		"and the button goes back to what the snapshot said")


## One line, with no tooltip delay: the name, the count, and the click action.
func _hovering_a_slot_names_it_and_its_click() -> void:
	var slot: PopupSlot = _view.slots_in(0)[0]

	slot.hovered.emit()

	var text := _view.hover_bar_text()
	_expect(text.begins_with("rusty metal dust"), "the bar names the item")
	_expect(text.contains("Click: Withdraw 5"), "and what a left click does")
	_expect(not text.contains("\n"), "on one line")


## A withdraw under the mouse rebuilds every slot. The bar must name the new
## slot at the same place, not keep the text from before the click.
func _the_bar_follows_a_rebuild_under_the_mouse() -> void:
	_view.slots_in(0)[0].hovered.emit()

	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.bank_payload())

	_expect(_view.hover_bar_text().begins_with("rusty metal dust"),
		"after a rebuild the bar still names the slot under the mouse")


func _leaving_a_slot_clears_the_bar() -> void:
	var slot: PopupSlot = _view.slots_in(0)[0]
	slot.hovered.emit()
	slot.unhovered.emit()

	_expect(_view.hover_bar_text().is_empty(), "leaving the slot clears the bar")


func _a_closed_snapshot_clears_the_bar() -> void:
	_view.slots_in(0)[0].hovered.emit()
	_expect(not _view.hover_bar_text().is_empty(), "the bar has text before the close")

	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.closed_payload())

	_expect(_view.hover_bar_text().is_empty(), "a closed box leaves no text")


func _close_asks_the_server_and_stays_open() -> void:
	_sent.clear()

	_view.request_close()

	_expect(_sent_only("popup close"),
		"close sends the server's close command")
	_expect(_view.visible, "and the box stays until the server closes it")


func _a_closed_snapshot_hides_the_box() -> void:
	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.closed_payload())

	_expect(not _view.visible, "the closed snapshot hides the box")
	_expect(_view.slots_in(0).is_empty(), "and drops every slot")


func _a_dim_slot_is_dim_and_still_sends() -> void:
	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.crafting_payload())
	_sent.clear()
	var dim: PopupSlot = _view.slots_in(0)[1]

	_expect(dim.modulate == PopupSlot.COLOR_DISABLED, "a disabled slot is dim")

	dim.activate()

	_expect(_sent_only("craft rusty scrap shortsword 1"),
		"and a click still sends, so the server can say what is missing")
	_expect(dim.tooltip_text.contains("Missing"), "the tooltip shows the info")


func _the_detail_line_and_the_footer_are_drawn() -> void:
	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.crafting_payload())
	_sent.clear()
	var buttons := _view.footer_buttons()

	_expect(buttons.size() == 1, "one footer button for one action")
	_expect(buttons[0].text == "Stop crafting", "with the server's label")

	buttons[0].pressed.emit()

	_expect(_sent_only("craft cancel"), "a footer press sends its command")


func _a_menu_node_draws_text_options_and_a_box() -> void:
	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.menu_payload())

	_expect(_view.visible, "a menu node shows the box")
	_expect(_view.menu_text().contains("What do you need?"),
		"the node text is drawn")
	_expect(_view.menu_option_buttons().size() == 2, "one button for each option")
	_expect(_view.menu_input_shown(), "and the text box, for a node that reads text")


func _a_menu_option_sends_its_key() -> void:
	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.menu_payload())
	_sent.clear()
	var second: Button = _view.menu_option_buttons()[1]

	second.pressed.emit()

	_expect(_sent_only("2"), "an option button sends the option key")


func _the_box_sends_what_was_typed() -> void:
	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.menu_payload())
	_sent.clear()

	_view.submit_menu_input("  17 ")
	_view.submit_menu_input("   ")

	_expect(_sent_only("17"), "the box sends the typed text, and blank sends nothing")


func _a_number_key_picks_the_option() -> void:
	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.menu_payload())
	_sent.clear()
	var press := InputEventKey.new()
	press.pressed = true
	press.keycode = KEY_1
	press.unicode = "1".unicode_at(0)

	_view._unhandled_input(press)

	_expect(_sent_only("1"), "pressing 1 sends the option keyed 1")


## The egg's first screen had twelve choices. Before the one scroll, the text
## and the choices split the height, and either one could lose all of it.
func _many_choices_share_one_scroll_with_the_text() -> void:
	var payload := _StateTest.menu_payload()
	var choices: Array = []

	for index: int in range(12):
		var key := str(index + 1)
		choices.append({"key": key, "label": "Choice %s" % key, "command": key})

	payload["choices"] = choices
	_state.ingest(_Const.CH_CHAR_POPUP, payload)

	var buttons := _view.menu_option_buttons()
	var content: Node = buttons[0].get_parent().get_parent()

	_expect(buttons.size() == 12, "every choice is a button")
	_expect(content.get_parent() is ScrollContainer, "the choices are inside the scroll")
	_expect(content.get_child(0) is RichTextLabel,
		"and the node text is above them in the same scroll")


func _the_count_sits_in_the_corner_not_the_detail_line() -> void:
	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.bank_payload())
	var slot: PopupSlot = _view.slots_in(0)[0]

	_expect(slot.count_text() == "x40", "a stack shows its count in the corner")
	_expect(not slot.detail_text().contains("x40"),
		"and not on the line under the name")


func _a_timed_station_draws_its_slots() -> void:
	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.curing_payload())
	var panel := _view.timer_panel()
	var texts := panel.row_texts()
	var bars := panel.bars()

	_expect(panel.visible, "a station with timers shows the side panel")
	_expect(texts.size() == 2, "one row for each occupied slot")
	_expect(texts[0].contains("left"), "a running cure counts down")
	_expect(texts[1] == TimerPanel.READY_TEXT, "a finished cure says to collect")
	# Within a hundredth: the bar moves with the clock between two reads.
	_expect(absf((bars[0] as ProgressBar).value - 0.5) < 0.01,
		"half of the cure is done, so half of the bar is full")


func _a_grid_pop_up_has_no_side_panel() -> void:
	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.bank_payload())

	_expect(not _view.timer_panel().visible, "a bank has no side panel")


func _the_box_stays_inside_the_pane() -> void:
	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.bank_payload())
	_view.size = Vector2(1000, 600)
	var pane := Rect2(Vector2.ZERO, _view.size).grow(-PopupView.EDGE_MARGIN)

	_view.resize_box(Vector2(5000, 5000))
	_expect(pane.encloses(_view.box_rect()), "a huge drag stops at the pane")

	_view.resize_box(Vector2(10, 10))
	var small := _view.box_rect().size
	_expect(small.x >= PopupView.MIN_BOX_SIZE.x and small.y >= PopupView.MIN_BOX_SIZE.y,
		"a tiny drag stops at the smallest box")

	_view.move_box(Vector2(-400, 9000))
	_expect(pane.encloses(_view.box_rect()), "a move cannot push it out of the pane")


## The control panel draws over the pop-up. Until 09/22/2026 the pop-up had one
## grip, in the corner that the panel covers. Now each edge and each corner has
## a grip. Each grip is top-level, so no dock draws over it or takes its click.
func _every_edge_and_corner_has_a_raised_grip() -> void:
	var grips := _view.grips()
	var expected := ResizeGrips.EDGES + ResizeGrips.CORNERS

	_expect(grips.offered().size() == expected.size(),
		"the box has a grip on every edge and every corner")

	for edges: int in expected:
		var grip := grips.grip(edges)
		_expect(grip != null and grip.top_level
			and grip.mouse_filter == Control.MOUSE_FILTER_STOP,
			"the grip for edges %d is raised and takes the mouse" % edges)


## A drag moves only the edges of its grip. The old grip sized the box from
## its top-left corner. A left edge that moved thus took the right edge with
## it.
func _a_drag_on_one_edge_keeps_the_other_edges() -> void:
	_state.ingest(_Const.CH_CHAR_POPUP, _StateTest.bank_payload())
	_view.size = Vector2(1000, 600)
	_view.move_box(Vector2(200, 100))
	_view.resize_box(Vector2(500, 400))
	var before := _view.box_rect()

	_view.grips().drag(ResizeGrips.LEFT, Vector2(-50, 0))
	var after := _view.box_rect()
	_expect(is_equal_approx(after.position.x, before.position.x - 50.0)
		and is_equal_approx(after.end.x, before.end.x),
		"a drag on the left edge moves it and keeps the right edge")

	_view.grips().drag(ResizeGrips.TOP | ResizeGrips.LEFT, Vector2(-9000, -9000))
	after = _view.box_rect()
	_expect(is_equal_approx(after.position.x, PopupView.EDGE_MARGIN)
		and is_equal_approx(after.position.y, PopupView.EDGE_MARGIN),
		"a drag past the pane stops the corner at the pane")
	_expect(is_equal_approx(after.end.x, before.end.x)
		and is_equal_approx(after.end.y, before.end.y),
		"and the opposite corner stays where it was")


## When the gap between the docks is wide enough, the first box opens in it.
## When the gap is too narrow, the box opens centred in the pane.
func _the_first_box_opens_between_the_docks() -> void:
	var pane := Vector2(1920, 1080)
	var wide := PopupView._default_rect(pane, 528.0, 1452.0)
	_expect(is_equal_approx(wide.get_center().x, (528.0 + 1452.0) / 2.0),
		"a wide gap centres the box in the gap")
	_expect(wide.position.x >= 528.0 + PopupView.EDGE_MARGIN - 0.01
		and wide.end.x <= 1452.0 - PopupView.EDGE_MARGIN + 0.01,
		"and the box stays in the gap")

	var gap_right := 528.0 + PopupView.MIN_GAP_WIDTH
	var narrow := PopupView._default_rect(pane, 528.0, gap_right)
	_expect(is_equal_approx(narrow.get_center().x, pane.x / 2.0),
		"a narrow gap centres the box in the pane")

	var large := PopupView._default_rect(Vector2(3840, 2160), 0.0, 0.0)
	_expect(large.size == PopupView.DEFAULT_MAX_SIZE,
		"a large pane gives a box no larger than the largest first box")


## A wider box gives the grid more columns. Until 09/22/2026 those columns
## raised the minimum width of the box. The player could thus make a box wide
## and never make it narrow again.
##
## Every kind of pop-up, because each one fills the box with different
## content. The case waits for layout passes: a container sorts its children
## and reports its new minimum on a later frame.
func _a_wide_box_can_be_made_narrow_again() -> void:
	var payloads := {
		"bank": _StateTest.bank_payload(),
		"crafting": _StateTest.crafting_payload(),
		"menu": _StateTest.menu_payload(),
		"curing": _StateTest.curing_payload(),
	}

	for kind: String in payloads:
		_state.ingest(_Const.CH_CHAR_POPUP, payloads[kind])
		_view.size = Vector2(1600, 900)
		_view.move_box(Vector2(100, 100))
		_view.resize_box(Vector2(400, 500))
		await _layout_passes()
		var narrow := _view.box_rect().size.x

		_view.grips().drag(ResizeGrips.RIGHT, Vector2(1000, 0))
		await _layout_passes()
		_expect(_view.box_rect().size.x > narrow + 500.0,
			"%s: a drag makes the box wide" % kind)

		_view.grips().drag(ResizeGrips.RIGHT, Vector2(-1000, 0))
		await _layout_passes()
		_expect(is_equal_approx(_view.box_rect().size.x, narrow),
			"%s: a drag back makes it narrow again (%s, then %s)"
			% [kind, narrow, _view.box_rect().size.x])

		var short := _view.box_rect().size.y
		_view.grips().drag(ResizeGrips.BOTTOM, Vector2(0, 200))
		await _layout_passes()
		_view.grips().drag(ResizeGrips.BOTTOM, Vector2(0, -200))
		await _layout_passes()
		_expect(is_equal_approx(_view.box_rect().size.y, short),
			"%s: and a tall box can be made short again" % kind)


func _layout_passes() -> void:
	for i: int in 4:
		await get_tree().process_frame


## A rect the player dragged lived in this node and died with the client, so a
## player who moved the bank off their minimap moved it again on every run.
##
## Both halves are checked, because each fails on its own. The rect is read the
## first time the box is PLACED, not at bind time -- the console binds every
## pane before it loads the file. And a drag writes the rect the box ENDED at,
## once, after the gesture.
func _the_players_box_survives_the_client() -> void:
	_clean_settings()
	var settings := ClientSettings.new(SETTINGS_PATH)
	settings.set_popup_rect(Rect2(30, 40, 820, 520))

	var state := PopupState.new()
	var view := PopupView.new()
	add_child(view)
	view.bind(state, null)
	view.bind_settings(settings)
	view.size = Vector2(1000, 600)
	state.ingest(_Const.CH_CHAR_POPUP, _StateTest.bank_payload())

	# The POSITION, because a content minimum can still widen the box. The
	# default rect is centred, so a box at the player's corner cannot be it.
	_expect(view.box_rect().position == Vector2(30, 40),
		"the box opens where the player left it")

	view.resize_box(Vector2(640, 480))
	var ended := view.box_rect()
	await get_tree().create_timer(PopupView.RECT_SAVE_DELAY + 0.2).timeout

	var reloaded := ClientSettings.new(SETTINGS_PATH)
	reloaded.load_from_disk()
	_expect(reloaded.popup_rect == ended,
		"and a drag writes the rect the box ended at")

	view.queue_free()
	_clean_settings()


func _clean_settings() -> void:
	if FileAccess.file_exists(SETTINGS_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SETTINGS_PATH))


func _the_grid_fits_its_columns_to_the_width() -> void:
	var pitch := PopupSlot.SLOT_SIZE.x + PopupView.SLOT_GAP

	_expect(PopupView._columns_for(0.0) == 1, "no width still draws one column")
	_expect(PopupView._columns_for(pitch * 6.0) == 6, "six slots fit six columns")
	_expect(PopupView._columns_for(pitch * 6.0 - 20.0) == 5,
		"and a little less fits five")


## True when exactly one command left the view, and it is `command`.
func _sent_only(command: String) -> bool:
	return _sent.size() == 1 and _sent[0] == command


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  x %s" % what)
