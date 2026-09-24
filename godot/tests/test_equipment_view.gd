extends Node
## Tests for [EquipmentView] -- the paper doll.
##
##     godot --headless --path godot res://tests/test_equipment_view.tscn
##
## Two things here can be wrong, and both are pure functions of the payload and
## of [DollLayout]: which frames get a square, and what a click on one sends.
## The pixels are not tested, for the reason `test_inventory_view.gd` gives.

const _Const := preload("res://autoload/blackout_constants.gd")

## Every wield location the server sends today, in `SLOT_DISPLAY_ORDER`. Typed
## out rather than read from [DollLayout], because a test that took its
## expectations from the table it is checking would pass for any table.
const SERVER_SLOTS: Array = [
	"main_hand", "off_hand", "two_hands", "head", "body", "legs", "feet",
	"back", "neck", "main_hand_finger", "off_hand_finger", "ammo",
]

var _failures := 0
var _view: EquipmentView
var _resolver: MeshResolver
var _state: InventoryState
var _sent: Array = []


func _ready() -> void:
	_state = InventoryState.new()

	# An EMPTY registry, so every item resolves to its family shape and no HTTP
	# happens -- the same state the real client is in before the manifest lands.
	_resolver = MeshResolver.new(ModelRegistry.new(), "")
	add_child(_resolver)

	_view = EquipmentView.new()
	add_child(_view)
	_view.bind(_state, _resolver)
	_view.command_requested.connect(func(command: String): _sent.append(command))

	_state.ingest(_Const.CH_CHAR_ITEMS, _payload())

	_every_frame_the_server_sent_gets_one_square()
	_the_doll_is_laid_out_the_way_the_table_says()
	_a_frame_the_server_did_not_send_is_a_gap()
	_a_slot_the_table_forgets_still_draws()
	_the_two_hand_frame_is_drawn_only_when_it_is_worn()
	_a_click_sends_the_servers_own_command()
	_the_heading_counts_what_is_worn()
	_every_cell_owns_a_different_rectangle()
	_nothing_here_listens_for_a_drop()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: equipment_view")
	get_tree().quit(0)


## One square per frame, and never two. A slot drawn on the doll AND in the
## leftover strip is the bug [method DollLayout.placed_slots] exists to stop.
func _every_frame_the_server_sent_gets_one_square() -> void:
	var seen: Array = []

	for cell: InventorySlotCell in _view.cells():
		_expect(not seen.has(cell.key),
			"%s has exactly one square" % str(cell.key))
		seen.append(cell.key)

	for slot: String in SERVER_SLOTS:
		if slot == DollLayout.WIDE_SLOT:
			continue

		_expect(seen.has(slot), "%s has a square at all" % slot)


## The shape is the reference interface's, and it is the reason this pane
## exists rather than the flat row of squares it replaced.
func _the_doll_is_laid_out_the_way_the_table_says() -> void:
	var rows := _drawn_rows()

	_expect(rows.size() > 3, "the doll has the rows the table declares")
	_expect(_slots_in(rows[0]) == ["head"], "the head is alone on the top row")
	_expect(_slots_in(rows[1]) == ["back", "neck", "ammo"],
		"the cape, the amulet and the ammunition share the second")
	_expect(_slots_in(rows[2]) == ["main_hand", "body", "off_hand"],
		"and the weapon and the shield flank the chest")

	var last := _slots_in(rows[rows.size() - 1])
	_expect(last == ["main_hand_finger", "feet", "off_hand_finger"],
		"the rings flank the boots at the bottom")


## The table is the client's picture of a set the SERVER owns. A square for a
## wield location the server never named would be this pane inventing one.
func _a_frame_the_server_did_not_send_is_a_gap() -> void:
	_state.ingest(_Const.CH_CHAR_ITEMS, _payload(["head", "body"]))

	_expect(_view.cell_for("head") != null, "the frame the server sent is drawn")
	_expect(_view.cell_for("legs") == null,
		"and one it did not send is not")

	_state.ingest(_Const.CH_CHAR_ITEMS, _payload())


## The fallback half of the asymmetry: a wield location added on the server
## reaches the pane with no edit to [DollLayout].
func _a_slot_the_table_forgets_still_draws() -> void:
	var slots := SERVER_SLOTS.duplicate()
	slots.append("tail")
	_state.ingest(_Const.CH_CHAR_ITEMS, _payload(slots))

	var stray := _view.cell_for("tail")

	_expect(stray != null, "a slot the table does not place still gets a square")

	if stray != null:
		_expect(stray.get_parent() == _view._overflow,
			"in the leftover strip, under the doll")

	_expect(_view._overflow_heading.visible, "and the strip names itself")

	_state.ingest(_Const.CH_CHAR_ITEMS, _payload())
	_expect(not _view._overflow_heading.visible,
		"a doll that places everything shows no strip")


## An empty two-hand frame is a square that cannot be filled while a one-hander
## is worn, and a permanent dead square reads as a bug. See [DollLayout].
func _the_two_hand_frame_is_drawn_only_when_it_is_worn() -> void:
	_expect(_view.cell_for(DollLayout.WIDE_SLOT) == null,
		"the wide frame is not drawn while the slot is empty")

	_state.ingest(_Const.CH_CHAR_ITEMS, _payload(SERVER_SLOTS, true))

	_expect(_view.cell_for(DollLayout.WIDE_SLOT) != null,
		"and is drawn as soon as a two-hander is worn")

	_state.ingest(_Const.CH_CHAR_ITEMS, _payload())


## The pane sends what the server named, verbatim. It cannot spell `unequip`.
func _a_click_sends_the_servers_own_command() -> void:
	_sent.clear()
	var cell := _view.cell_for("body")

	if cell == null:
		_fail("the body frame is drawn")
		return

	cell.activate()

	_expect(_sent == ["unequip body"],
		"a click sends the server's own first action")


func _the_heading_counts_what_is_worn() -> void:
	_expect(_view._heading.text == "Worn  1/%d" % SERVER_SLOTS.size(),
		"the heading counts the worn frames against every frame")


## Two cells showing the same rectangle would show the same item. The stage
## hands out sub-rects of one render target; see [ItemStage].
func _every_cell_owns_a_different_rectangle() -> void:
	var seen: Array = []
	var checked := 0

	for cell: InventorySlotCell in _view.cells():
		var texture := cell.art_texture()

		if texture == null:
			continue

		checked += 1
		_expect(not seen.has(texture.region),
			"%s has a rectangle of its own" % str(cell.key))
		seen.append(texture.region)

	_expect(checked > 0, "something was drawn, so this compares something")


## A tab strip draws one tab, so no drag can reach here from the carried grid
## and none can leave. A connection would be a gesture nobody can make.
func _nothing_here_listens_for_a_drop() -> void:
	for cell: InventorySlotCell in _view.cells():
		_expect(cell.dropped.get_connections().is_empty(),
			"%s listens for no drop" % str(cell.key))


## The rows of the doll that actually got a line of pixels.
func _drawn_rows() -> Array:
	return _view._doll.get_children()


## The slots of one row, gaps left out.
func _slots_in(row: Node) -> Array:
	var slots: Array = []

	for cell: Node in row.get_children():
		if cell is InventorySlotCell:
			slots.append(str(cell.key))

	return slots


## A `char_items_list` payload wearing one body plate.
##
## `slots` decides which frames the server sends, so a case can take one away
## or add one the client has never heard of. `two_handed` puts something in the
## wide slot.
func _payload(slots: Array = SERVER_SLOTS,
		two_handed: bool = false) -> Dictionary:
	var frames: Array = []

	for slot: String in slots:
		frames.append({"slot": slot, "label": slot.capitalize()})

	var worn: Array = [
		{"id": 103.0, "slot": "body", "name": "plate", "asset": "",
		 "family": "armor", "quantity": 1.0, "stackable": false,
		 "equip_slot": "body",
		 "actions": [{"label": "Unequip", "command": "unequip body"}]},
	]

	if two_handed:
		worn.append({"id": 104.0, "slot": "two_hands", "name": "greataxe",
			"asset": "", "family": "weapon", "quantity": 1.0,
			"stackable": false, "equip_slot": "two_hands",
			"actions": [{"label": "Unequip", "command": "unequip two_hands"}]})

	return {
		"slots_total": 32.0, "slots_used": 0.0,
		"items": [],
		"equipped": worn,
		"equip_slots": frames,
	}


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_fail(what)


func _fail(what: String) -> void:
	_failures += 1
	printerr("  FAIL %s" % what)
