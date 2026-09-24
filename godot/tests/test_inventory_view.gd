extends Node
## Tests for the inventory VIEW's one job that can be wrong: turning a gesture
## into a command.
##
## The drawing is not tested and deliberately so -- a grid of labels is cheap to
## look at and expensive to assert. What matters is that every command leaving
## this pane was named by the server, and that drop legality is the server's
## answer rather than one this client invented. Those are pure functions of the
## model and are checked here.
##
##     godot --headless --path godot res://tests/test_inventory_view.tscn

const _Const := preload("res://autoload/blackout_constants.gd")
const SlotCell := preload("res://scenes/inventory/slot_cell.gd")

## Longer than the 14 characters the bag used to cut a name at.
const LONG_NAME := "rusty scrap metal dust chunk"

var _failures := 0
var _view: InventoryView
var _resolver: MeshResolver
var _state: InventoryState


func _ready() -> void:
	_state = InventoryState.new()
	_state.ingest(_Const.CH_CHAR_ITEMS, _payload())

	# An EMPTY registry, so every item resolves to its family shape and no HTTP
	# happens -- the same state the real client is in before the manifest lands.
	_resolver = MeshResolver.new(ModelRegistry.new(), "")
	add_child(_resolver)

	_view = InventoryView.new()
	add_child(_view)
	_view.bind(_state, _resolver)

	_a_carried_to_carried_drag_swaps()
	_a_gesture_this_pane_cannot_make_sends_nothing()
	_drop_legality_is_the_servers_answer()
	_emitted_commands_reach_the_signal()
	_only_occupied_cells_get_a_picture()
	_every_cell_owns_a_different_rectangle()
	_the_stage_does_not_share_the_game_world()
	_a_name_is_never_cut_by_a_character_count()
	_a_name_reserves_two_lines()
	_hovering_a_cell_names_it_in_the_bar()
	_leaving_a_cell_clears_the_bar()
	_a_stale_exit_does_not_clear_a_newer_hover()
	_the_bar_follows_a_rebuild_under_the_mouse()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: inventory_view")
	get_tree().quit(0)


## An empty square is a square. Giving it a texture would draw whatever the
## stage last left at that index, which is the previous bag's item.
func _only_occupied_cells_get_a_picture() -> void:
	var occupied := 0
	var empty := 0

	for cell: InventorySlotCell in _view._grid.get_children():
		if cell.row().is_empty():
			empty += 1
			_expect(cell.art_texture() == null,
				"empty carried square %s has no picture" % str(cell.key))
		else:
			occupied += 1
			_expect(cell.art_texture() != null,
				"carried item %s has a picture" % str(cell.key))

	# The vacuity guard: a payload with nothing in it, or a grid that failed to
	# build, would pass both branches above without checking anything.
	_expect(occupied > 0, "the bag actually holds something to draw")
	_expect(empty > 0, "and has an empty square to compare against")


## Two cells showing the same rectangle would show the same item.
##
## The stage packs every item into one render target and hands out sub-rects, so
## an index allocated twice is not a crash -- it is two slots quietly drawing one
## object, which is exactly the bug worth a test rather than a comment.
func _every_cell_owns_a_different_rectangle() -> void:
	var seen: Array = []
	var checked := 0

	for cell: InventorySlotCell in _view._grid.get_children():
		var texture := cell.art_texture()

		if texture == null:
			continue

		checked += 1
		_expect(not seen.has(texture.region),
			"cell %s has a rectangle of its own" % str(cell.key))
		seen.append(texture.region)

	_expect(checked > 1, "more than one cell was drawn, so this compares something")


## The item meshes must not end up in the world the game is drawn in.
##
## `SubViewport.own_world_3d` defaults to FALSE, so a stage left at the default
## shares its parent's World3D: every inventory item is added to the same 3D
## world the map lives in, and the world pane's camera draws them as a grid of
## swords floating in the sky. The stage's WorldEnvironment leaks the same way
## and repaints the game's sky.
##
## Both happened. Neither is hinted at by anything else about the viewport,
## which is why this is a test and not a comment.
func _the_stage_does_not_share_the_game_world() -> void:
	_expect(_view._stage.own_world_3d,
		"the stage owns its own 3D world")

	var stage_world := _view._stage.find_world_3d()
	var outer_world := _view.get_viewport().find_world_3d()

	_expect(stage_world != outer_world,
		"so its items are not in the world the map is drawn in")

	# The vacuity guard: two nulls compare equal-ish and would sail through the
	# check above while proving nothing about isolation.
	_expect(stage_world != null and outer_world != null,
		"and both worlds actually exist to be compared")


## The whole name reaches the label. The ENGINE cuts it on the drawn width.
## A character count cut names that had room to fit.
func _a_name_is_never_cut_by_a_character_count() -> void:
	var cell := _carried_cell(3)

	_expect(cell._title.text == LONG_NAME, "the label holds the whole name")
	_expect(cell._title.max_lines_visible == ItemNameLabel.MAX_LINES,
		"and the engine may wrap it to two lines")


## Autowrap plus an overrun reports a one-pixel minimum height. Without the
## floor, the grid gives the name no rows at all.
func _a_name_reserves_two_lines() -> void:
	var title: ItemNameLabel = _carried_cell(3)._title
	var one_line := ItemNameLabel.height_of_lines(title, 1)

	_expect(one_line > 1.0, "a line of the theme font has a height")
	_expect(title.custom_minimum_size.y > one_line,
		"the name reserves more than one line")


func _hovering_a_cell_names_it_in_the_bar() -> void:
	var cell := _carried_cell(3)
	cell.hovered.emit()
	var action_text := "Click: Drop %s" % LONG_NAME

	_expect(_view._bar.text.begins_with("%s x12" % LONG_NAME),
		"the bar shows the full name and the count")
	_expect(_view._bar.text.contains(action_text),
		"the bar names the left-click action")
	_expect(cell.tooltip_text.contains(action_text),
		"the delayed tooltip names the left-click action")


func _leaving_a_cell_clears_the_bar() -> void:
	var cell := _carried_cell(3)
	cell.hovered.emit()
	cell.unhovered.emit()

	_expect(_view._bar.text.is_empty(), "leaving the cell clears the bar")


## Godot sends the exit of the old cell before the entry of the new one. An exit
## from a cell the bar does not name must change nothing.
func _a_stale_exit_does_not_clear_a_newer_hover() -> void:
	_carried_cell(3).hovered.emit()
	_carried_cell(0).unhovered.emit()

	_expect(_view._bar.text.begins_with(LONG_NAME),
		"an exit from another cell leaves the bar alone")


## A rebuild frees the cell under the mouse, and the new cell gets no
## mouse_entered until the mouse moves. The bar must name the NEW row.
func _the_bar_follows_a_rebuild_under_the_mouse() -> void:
	_carried_cell(3).hovered.emit()

	var payload := _payload()
	payload["items"][1]["quantity"] = 5.0
	_state.ingest(_Const.CH_CHAR_ITEMS, payload)

	_expect(_view._bar.text.begins_with("%s x5" % LONG_NAME),
		"after a rebuild the bar shows the new count")

	_carried_cell(3).unhovered.emit()

	_expect(_view._bar.text.is_empty(),
		"and the new cell's exit still clears it")


func _carried_cell(index: int) -> InventorySlotCell:
	return _view._grid.get_child(index)


func _payload() -> Dictionary:
	return {
		"slots_total": 32.0, "slots_used": 3.0,
		"items": [
			{"id": 101.0, "slot": 0.0, "name": "sword", "asset": "", "family": "weapon",
			 "quantity": 1.0, "stackable": false, "equip_slot": "weapon_hand",
			 "actions": [{"label": "Equip", "command": "equip 1"},
						 {"label": "Drop", "command": "drop 1"}]},
			{"id": 102.0, "slot": 3.0, "name": LONG_NAME, "asset": "", "family": "material",
			 "quantity": 12.0, "stackable": true, "equip_slot": "",
			 "actions": [{"label": "Drop", "command": "drop 4"}]},
			# Equipment the server offered NO equip action for -- a legality
			# edge the client must not paper over by composing one.
			{"id": 106.0, "slot": 6.0, "name": "cursed ring", "asset": "",
			 "family": "jewellery", "quantity": 1.0, "stackable": false,
			 "equip_slot": "ring", "actions": [{"label": "Drop", "command": "drop 7"}]},
		],
		"equipped": [
			{"id": 103.0, "slot": "armor_body", "name": "plate", "asset": "",
			 "family": "armor", "quantity": 1.0, "stackable": false,
			 "equip_slot": "armor_body",
			 "actions": [{"label": "Unequip", "command": "unequip armor_body"}]}],
		"equip_slots": [
			{"slot": "weapon_hand", "label": "Weapon"},
			{"slot": "armor_body", "label": "Body"},
			{"slot": "ring", "label": "Ring"}],
	}


func _a_carried_to_carried_drag_swaps() -> void:
	# The one command this client composes, because a drag knows two endpoints
	# and nothing else does. 1-based, matching serialize_inventory's own +1.
	var command: String = _view._command_for(
		SlotCell.KIND_CARRIED, 0, SlotCell.KIND_CARRIED, 3)

	_expect(command == "swap 1 4", "a carried drag swaps, 1-based")
	_expect(
		_view._command_for(SlotCell.KIND_CARRIED, 2, SlotCell.KIND_CARRIED, 2).is_empty(),
		"a drag onto itself sends nothing")


## A worn frame is not in this pane any more, so a drag cannot reach one.
##
## Asserted rather than left to the layout, because the pane still HOLDS the
## handler: a branch put back here would compose `equip` for a gesture no
## player can make, which is how a verb table gets into a client. The left
## click is the route now; see [EquipmentView].
func _a_gesture_this_pane_cannot_make_sends_nothing() -> void:
	_expect(
		_view._command_for(SlotCell.KIND_CARRIED, 0,
			SlotCell.KIND_EQUIPPED, "weapon_hand").is_empty(),
		"a drag onto a worn frame sends nothing")

	_expect(
		_view._command_for(SlotCell.KIND_EQUIPPED, "armor_body",
			SlotCell.KIND_CARRIED, 8).is_empty(),
		"and so does a drag off one")


func _drop_legality_is_the_servers_answer() -> void:
	# can_equip compares two SERVER-supplied values: the row's equip_slot
	# against the frame's slot.
	var frame := SlotCell.new()
	frame.bind(_state, SlotCell.KIND_EQUIPPED, "weapon_hand", "Weapon")

	var sword := {"kind": SlotCell.KIND_CARRIED, "key": 0,
				  "row": _state.carried_at(0)}
	var chunk := {"kind": SlotCell.KIND_CARRIED, "key": 3,
				  "row": _state.carried_at(3)}

	_expect(frame._can_drop_data(Vector2.ZERO, sword), "the sword may enter the weapon hand")
	_expect(not frame._can_drop_data(Vector2.ZERO, chunk),
		"a material with no equip_slot may not")
	_expect(not frame._can_drop_data(Vector2.ZERO, "junk"),
		"a non-dictionary payload is refused")

	var square := SlotCell.new()
	square.bind(_state, SlotCell.KIND_CARRIED, 8)

	_expect(square._can_drop_data(Vector2.ZERO, sword),
		"anything may be dropped into the bag; the server validates")

	frame.free()
	square.free()


func _emitted_commands_reach_the_signal() -> void:
	var seen: Array = []
	_view.command_requested.connect(func(c: String): seen.append(c))

	_view._on_dropped(SlotCell.KIND_CARRIED, 0, SlotCell.KIND_CARRIED, 3)
	_view._on_dropped(SlotCell.KIND_CARRIED, 6, SlotCell.KIND_EQUIPPED, "ring")

	_expect(seen.size() == 1, "only the gesture with a command emitted")
	_expect(seen[0] == "swap 1 4", "and it emitted the right one")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
