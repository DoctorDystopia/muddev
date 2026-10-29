extends Node
## Tests for the panel of the terrain editor: [TerrainDock], its strips,
## and [BuildPanel] inside it.
##
##     godot --headless --path godot res://tests/test_terrain_dock.tscn
##
## Needs nothing running and no editor. The dock does not persist here, so
## the test writes no file. The cases:
##
## 1. The dock has the seven tabs, and the Paint hint names the tool, its
##    values, and the plane.
## 2. The paint values strip serves the Paint tab and the Build tab: one
##    pick lands in both, and "(keep)" gives the Floor brush its warning.
## 3. A number key picks a tool, and the options of the other tools hide.
##    The Ramp has no brush shape.
## 4. The object list filters by text, and the fields of the selected
##    object send one edit.
## 5. The Save button counts the changed chunks, the findings label says
##    when the rows are old, and the block report keeps its lines.
## 6. The look fields of the selected object send a look with no key at its
##    default (10/16/2026).
## 7. The Side field of the block strip sends the side, within the cap, and
##    [method TerrainDock.set_block] fills it with no send (10/21/2026).
## 8. The spawn fields show for a selected item spawn only (10/21/2026). A
##    fill sends nothing. A changed respawn sends the whole spawn.

const _Const := preload("res://autoload/blackout_constants.gd")
const _Session := preload("res://addons/blackout_terrain/terrain_session.gd")

## The session file of this test. No file is there, so the dock starts on
## its defaults, never on the choices of the author.
const SESSION_PATH := "user://test_terrain_dock_session.cfg"

var _failures := 0
var _sent := []


func _ready() -> void:
	# The dock reads the session file in _init, before `persist = false`.
	_Session.path = SESSION_PATH

	var dock := TerrainDock.new()

	dock.persist = false
	add_child(dock)
	_the_tabs_and_the_paint_hint(dock)
	_one_strip_serves_both_tabs(dock)
	_a_number_key_picks_a_tool(dock)
	_the_ramp_has_no_shape(dock)
	_the_object_list_filters_and_the_fields_send_an_edit(dock)
	_the_frame_counts_and_warns(dock)
	_the_side_field_sends_the_block_side(dock)
	_an_item_spawn_shows_and_sends_its_spawn(dock)
	_expect(not FileAccess.file_exists(SESSION_PATH), "the dock writes no session file")

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: terrain_dock")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("FAIL: " + what)


func _record(sent: Signal, name_of: String) -> void:
	sent.connect(func(a: Variant = null, b: Variant = null, c: Variant = null,
			d: Variant = null, e: Variant = null) -> void:
		_sent.append([name_of, a, b, c, d, e]))


func _the_tabs_and_the_paint_hint(dock: TerrainDock) -> void:
	var tabs: TabContainer = dock.get_node("TabContainer") if dock.has_node("TabContainer") \
		else null

	# The test picks its own tool, so a new default tool breaks no case.
	dock.select_tool(TerrainDock.Tool.RAISE)

	var hint := dock.paint_hint(2)

	if tabs == null:
		for child: Node in dock.get_children():
			if child is TabContainer:
				tabs = child

	_expect(tabs != null and tabs.get_tab_count() == 7, "seven tabs")
	_expect(tabs != null and tabs.get_tab_title(5) == "Tables", "the Tables tab comes sixth")
	_expect(tabs != null and tabs.get_tab_title(6) == "Versions", "the Versions tab comes last")
	_expect(tabs != null and tabs.get_tab_title(0) == "Paint" and tabs.get_tab_title(1) == "Build",
		"Paint and Build come first")
	_expect(hint.begins_with("Raise") and "Plane 2" in hint, "the hint names the tool and the plane: %s" % hint)
	_expect(not dock.build_active(), "the Paint tab shows first")


func _one_strip_serves_both_tabs(dock: TerrainDock) -> void:
	var panel := dock.build_panel()

	dock.pick_floor("sand")
	dock.pick_area("oasis")

	_expect(panel.floor_name() == "sand" and panel.area_name() == "oasis",
		"a pick on the Paint tab reaches the Build tab")

	panel.sample(BuildPanel.KEEP, BuildPanel.KEEP, "brick")

	_expect(dock.floor_name() == "" and panel.wall_style() == "brick",
		"a sample on the Build tab reaches the Paint tab")

	dock.select_tool(TerrainDock.Tool.FLOOR)

	_expect(dock.paint_hint(0).begins_with("Floor: pick a floor"),
		"(keep) gives the Floor brush its warning")

	dock.pick_floor("dirt")

	_expect("paint dirt" in dock.paint_hint(0), "the hint names the floor: %s" % dock.paint_hint(0))


func _a_number_key_picks_a_tool(dock: TerrainDock) -> void:
	_sent.clear()
	_record(dock.tool_changed, "tool_changed")
	dock.pick_tool(TerrainDock.Tool.OBJECT)

	_expect(dock.current_tool() == TerrainDock.Tool.OBJECT and _sent.size() == 1,
		"pick_tool picks the tool and sends one signal")

	dock.pick_tool(TerrainDock.Tool.OBJECT)

	_expect(_sent.size() == 1, "the same tool again sends nothing")

	var panel := dock.build_panel()

	panel.select_tool(BuildPanel.Tool.ROOF)

	var roof_rows := _visible_labels(panel)

	panel.select_tool(BuildPanel.Tool.DOORWAY)

	_expect("Roof shape" in roof_rows and not "Roof shape" in _visible_labels(panel),
		"the Build tab shows the options of the current tool only: %s" % [roof_rows])
	_expect(_visible_labels(panel).is_empty(), "the Doorway tool has no option")


## A square brush stays a square on each tool with a shape. The Ramp reads
## the radius as a width, so it gives a circle, and its options hide the
## Shape row.
func _the_ramp_has_no_shape(dock: TerrainDock) -> void:
	var shape := _shape_list(dock)

	_expect(shape != null, "the Paint tab has the Shape list")

	if shape == null:
		return

	shape.select(TerrainBrushes.Shape.SQUARE)
	dock.select_tool(TerrainDock.Tool.FLOOR)

	_expect(dock.brush_shape() == TerrainBrushes.Shape.SQUARE and shape.visible,
		"the Floor brush takes the square")

	dock.select_tool(TerrainDock.Tool.RAMP)

	_expect(dock.brush_shape() == TerrainBrushes.Shape.CIRCLE and not shape.visible,
		"the Ramp has no shape")


## The Shape list of the Paint tab: the list with the names of the shapes.
func _shape_list(root: Node) -> OptionButton:
	for child: Node in root.get_children():
		if child is OptionButton and child.item_count == TerrainBrushes.SHAPE_NAMES.size() \
				and child.get_item_text(0) == TerrainBrushes.SHAPE_NAMES[0]:
			return child

		var found := _shape_list(child)

		if found != null:
			return found

	return null


## The text of each visible Label of `panel`.
func _visible_labels(panel: Control) -> Array:
	var texts := []

	for child: Node in panel.get_children():
		if child is Label and child.visible:
			texts.append(child.text)

	return texts


func _the_object_list_filters_and_the_fields_send_an_edit(dock: TerrainDock) -> void:
	var rows: Array[Dictionary] = [
		{"tile": Vector2i(1, 1), "kind": "signpost", "rotation": 0, "text": "Welcome"},
		{"tile": Vector2i(2, 2), "kind": "ladder_up", "rotation": 1, "text": ""},
	]

	_expect(TerrainDock.listed_objects(rows, true, "welc").size() == 1,
		"the filter keeps the rows with its text")
	_expect(TerrainDock.listed_objects(rows, true, "").size() == 2, "no filter keeps every row")
	_sent.clear()
	_record(dock.selection_edited, "selection_edited")
	dock.set_selection(rows[1], {"tile": Vector2i(2, 2), "plane": 1})

	_expect(_sent.is_empty(), "a shown selection sends nothing")

	var rotation: SpinBox = _find(dock, SpinBox, 1)

	_expect(rotation != null, "the Objects tab has the rotation field")

	if rotation != null:
		rotation.value = 2

	_expect(_sent.size() == 1 and _sent[0][1] == "ladder_up" and _sent[0][2] == 2,
		"a changed rotation sends the kind and the rotation: %s" % [_sent])
	_expect(_sent.size() == 1 and _sent[0][4] == {},
		"a selection with no look sends an empty look: %s" % [_sent])

	# The look fields (10/16/2026). A scale off the unit joins the look. A
	# scale back at the unit leaves it out again.
	_sent.clear()

	var scale: SpinBox = _find_suffixed(dock, "%")

	_expect(scale != null, "the Objects tab has the scale field")

	if scale != null:
		scale.value = 150
		_expect(_sent.size() == 1 and _sent[0][4] == {_Const.LOOK_SCALE_KEY: 150},
			"a scale of 150 sends a look with the scale: %s" % [_sent])
		_sent.clear()
		scale.value = _Const.LOOK_SCALE_UNIT
		_expect(_sent.size() == 1 and _sent[0][4] == {},
			"a scale at the unit sends a look with no scale: %s" % [_sent])


## The number field of `root` whose suffix is `suffix`, or null.
func _find_suffixed(root: Node, suffix: String) -> SpinBox:
	for child: Node in root.get_children():
		if child is SpinBox and child.suffix == suffix:
			return child

		var found := _find_suffixed(child, suffix)

		if found != null:
			return found

	return null


## Case 8. The item comes from the item list of the game, so no item key is
## typed here.
func _an_item_spawn_shows_and_sends_its_spawn(dock: TerrainDock) -> void:
	var items := SpawnItems.game().keys()

	_expect(not items.is_empty(), "the item list of the game names an item")

	if items.is_empty():
		return

	var spawn := {_Const.SPAWN_ITEM_KEY: items[0], _Const.SPAWN_RESPAWN_KEY: 40}
	var row := {"tile": Vector2i(3, 3), "kind": _Const.OBJECT_ITEM_SPAWN_KIND,
		"rotation": 0, "text": "", "look": {}, "spawn": spawn}
	var fields: Array[SpawnFields] = []

	_collect(dock, SpawnFields, fields)
	_expect(fields.size() == 2, "the Paint tab and the Objects tab each have spawn fields")

	if fields.size() != 2:
		return

	var selected := fields[1]

	dock.set_selection({"tile": Vector2i(2, 2), "kind": "ladder_up", "rotation": 0,
		"text": "", "look": {}, "spawn": {}}, {})
	_expect(not selected.visible, "a ladder shows no spawn fields")
	_sent.clear()
	dock.set_selection(row, {})
	_expect(selected.visible, "an item spawn shows its spawn fields")
	_expect(_sent.is_empty(), "a filled spawn sends nothing")
	_expect(selected.spawn() == spawn, "the fields show the spawn: %s" % [selected.spawn()])
	_expect(TerrainDock.describe_object(row).contains(items[0]),
		"the object list names the item of a spawn")

	var respawn := _find_suffixed(selected, "ticks")

	if respawn != null:
		respawn.value = 60

	_expect(_sent.size() == 1 and _sent[0][5].get(_Const.SPAWN_RESPAWN_KEY) == 60,
		"a changed respawn sends the spawn: %s" % [_sent])


## Each node of `type` under `root`, depth first, into `found`.
func _collect(root: Node, type: Variant, found: Array) -> void:
	for child: Node in root.get_children():
		if is_instance_of(child, type):
			found.append(child)

		_collect(child, type, found)


## The rotation field of `type` with `value`. The Paint tab has a rotation
## field too, with the same tooltip, so the search goes by the value.
func _find(root: Node, type: Variant, value: int) -> Control:
	for child: Node in root.get_children():
		if is_instance_of(child, type) and child.value == value \
				and child.tooltip_text.begins_with("Quarter turns"):
			return child

		var found := _find(child, type, value)

		if found != null:
			return found

	return null


func _the_frame_counts_and_warns(dock: TerrainDock) -> void:
	dock.set_unsaved(3)

	var save := _button(dock, "Save (3 changed)")

	_expect(save != null, "the Save button counts the changed chunks")

	dock.set_unsaved(0)

	_expect(_button(dock, "Save") != null, "no change gives a plain Save")

	var findings: Array[Dictionary] = [{"rule": "respawn_count", "x": 0, "y": 0, "plane": 0,
		"message": "one respawn point"}]

	dock.set_findings(findings, PackedStringArray())
	dock.mark_findings_stale()

	_expect(_label(dock, "Findings (changed since the last check)") != null,
		"an edit after a check marks the list as old")

	dock.set_block_report(PackedStringArray(["Block around chunk (0, 0), plane 0.",
		"Seam: east"]), true)

	_expect(_label(dock, "Block around chunk (0, 0), plane 0.\nSeam: east") != null,
		"the block report keeps its lines")


func _the_side_field_sends_the_block_side(dock: TerrainDock) -> void:
	var field := _spin_with_cap(dock, TerrainWorld.BLOCK_SIDE_MAX)

	_sent.clear()
	_record(dock.block_side_requested, "side")

	_expect(dock.block_side() == TerrainWorld.BLOCK_SIDE_DEFAULT,
		"the field starts at the default side of the world")
	_expect(field != null, "the block strip has the Side field")

	dock.set_block(Vector2i(2, 3), 1, 6)

	_expect(dock.block_side() == 6 and _sent.is_empty(),
		"set_block fills the field and sends nothing")

	if field == null:
		return

	field.value = 7

	_expect(_sent.size() == 1 and _sent[0].slice(0, 3) == ["side", 7, null],
		"a change sends the side")

	field.value = TerrainWorld.BLOCK_SIDE_MAX + 10

	_expect(dock.block_side() == TerrainWorld.BLOCK_SIDE_MAX, "the field holds the cap")

	dock.set_block(Vector2i.ZERO, 0, TerrainWorld.BLOCK_SIDE_DEFAULT)


## The one SpinBox under `root` whose largest value is `cap`.
func _spin_with_cap(root: Node, cap: int) -> SpinBox:
	for child: Node in root.get_children():
		if child is SpinBox and int(child.max_value) == cap:
			return child

		var found := _spin_with_cap(child, cap)

		if found != null:
			return found

	return null


func _button(root: Node, text: String) -> Button:
	for child: Node in root.get_children():
		if child is Button and child.text == text:
			return child

		var found := _button(child, text)

		if found != null:
			return found

	return null


func _label(root: Node, text: String) -> Label:
	for child: Node in root.get_children():
		if child is Label and child.text == text:
			return child

		var found := _label(child, text)

		if found != null:
			return found

	return null
