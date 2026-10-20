extends Node
## Tests for the part editor of the gear editor (DESIGN-0014 section 22):
## [PartEditor], the editor that the Gear dock, the Body tab, and the
## Families tab share.
##
##     godot --headless --path godot res://tests/test_part_editor.tscn
##
## Needs nothing running and no editor. It writes no file. The cases:
##
## 1. The tree has one row for each part, and one row below it for each
##    shape. A selected part row sends the part, and a selected shape row
##    sends the part and the shape.
## 2. The toolbar has one button for each kind of shape, and each one
##    sends the kind. The part buttons and the shape buttons send the
##    selection.
## 3. A button that needs a part or a shape is off, with the reason in
##    its tooltip.
## 4. Delete removes the selected row, and Ctrl+D copies it.
## 5. The two grids show the selected part and the selected shape. A new
##    look keeps the selection while the part stays.
## 6. The two folds of the editor have their titles.

var _failures := 0
var _sent := []


func _ready() -> void:
	_the_tree_has_each_part_and_each_shape()
	_the_toolbar_sends_each_kind()
	_a_button_that_needs_a_selection_is_off()
	_the_keys_remove_and_copy()
	_the_grids_follow_the_selection()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: part_editor")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _rig() -> FigureRig:
	return FigureEdits.rig_from_profile("body_1")


## A body with a second shape on the left upper arm, so one part has two
## shapes of two kinds.
func _body(rig: FigureRig) -> FigureLook:
	var data: Dictionary = FigureEdits.mannequin(rig).data.duplicate(true)

	FigureEdits.add_shape(data, "upper_arm_l", FamilyShapes.SHAPE_SPHERE)

	return FigureLook.from_data(data)


## Keep each argument list that a signal of the editor sends.
func _record(sent: Signal, name_of: String) -> void:
	sent.connect(func(a: Variant = null, b: Variant = null, c: Variant = null,
			d: Variant = null) -> void:
		_sent.append([name_of, a, b, c, d]))


## Press the button with one text below `node`. Returns false for no such
## button.
func _press(node: Node, text: String) -> bool:
	for child: Node in node.get_children():
		if child is Button and (child as Button).text == text:
			(child as Button).pressed.emit()
			return true

		if _press(child, text):
			return true

	return false


## The tree item of one part, or null.
func _part_item(editor: PartEditor, part_name: String) -> TreeItem:
	for item: TreeItem in editor._tree.get_root().get_children():
		if item.get_text(PartEditor.COLUMN_NAME) == part_name:
			return item

	return null


func _key(editor: PartEditor, keycode: Key, ctrl := false) -> void:
	var event := InputEventKey.new()

	event.keycode = keycode
	event.pressed = true
	event.ctrl_pressed = ctrl
	editor._tree.gui_input.emit(event)


func _the_tree_has_each_part_and_each_shape() -> void:
	var editor := PartEditor.new()
	var rig := _rig()
	var body := _body(rig)
	var root: TreeItem

	add_child(editor)
	_sent.clear()
	_record(editor.part_chosen, "part")
	_record(editor.shape_chosen, "shape")
	editor.set_content(rig, body)
	root = editor._tree.get_root()
	_expect(root.get_child_count() == body.parts().size() and editor.part_count() == root.get_child_count(),
		"the tree has one row for each part")

	for item: TreeItem in root.get_children():
		var row := body.part(item.get_text(PartEditor.COLUMN_NAME))

		_expect(item.get_child_count() == row.get("shapes", []).size()
			and item.get_text(PartEditor.COLUMN_BONE) == row["bone"],
			"the row of %s has one child for each shape, and its bone" % row["name"])

	var arm := _part_item(editor, "upper_arm_l")

	_expect(arm.get_child(1).get_text(PartEditor.COLUMN_BONE) == FamilyShapes.SHAPE_SPHERE
		and arm.get_child(1).get_text(PartEditor.COLUMN_NAME) == PartEditor.SHAPE_ROW % 1,
		"a shape row names its index and its kind")
	_expect(_sent.is_empty(), "a filled tree sends nothing: %s" % [_sent])

	arm.select(PartEditor.COLUMN_NAME)
	_expect(_sent == [["part", "upper_arm_l", null, null, null]]
		and editor.selected_part() == "upper_arm_l" and not editor.shape_row_selected()
		and editor.selected_shape() == 0, "a part row sends its part, and the grid shows shape 0")

	_sent.clear()
	arm.get_child(1).select(PartEditor.COLUMN_NAME)
	_expect(_sent == [["shape", "upper_arm_l", 1, null, null]]
		and editor.shape_row_selected() and editor.selected_shape() == 1,
		"a shape row sends its part and its index: %s" % [_sent])

	_sent.clear()
	editor.select_part("head")
	editor.select_shape(0)
	_expect(_sent.is_empty() and editor.selected_part() == "head"
		and editor._tree.get_selected() == _part_item(editor, "head").get_child(0),
		"a selection by code sends nothing, and the tree follows it")
	editor.queue_free()


func _the_toolbar_sends_each_kind() -> void:
	var editor := PartEditor.new()
	var rig := _rig()

	add_child(editor)
	_sent.clear()
	editor.set_content(rig, _body(rig))
	editor.select_part("head")
	_record(editor.shape_requested, "add")
	_record(editor.part_requested, "part")
	_record(editor.part_copied, "copy_part")
	_record(editor.part_mirrored, "mirror")
	_record(editor.part_removed, "remove_part")
	_record(editor.shape_copied, "copy_shape")
	_record(editor.shape_removed, "remove_shape")

	for kind: String in FigureShapeEdits.SHAPE_FIELDS:
		_expect(_press(editor, PartEditor.ADD_SHAPE_TEXT % kind),
			"the toolbar has a button for the kind %s" % kind)
		_expect(_sent.back() == ["add", "head", kind, null, null],
			"the button of %s sends the part and the kind" % kind)

	_sent.clear()
	_press(editor, "Add part")
	_press(editor, "Copy part")
	_press(editor, "Mirror part")
	_press(editor, "Remove part")
	editor.select_shape(0)
	_press(editor, "Copy shape")
	_press(editor, "Remove shape")
	_expect(_sent == [["part", editor.new_part_bone(), null, null, null],
			["copy_part", "head", null, null, null], ["mirror", "head", null, null, null],
			["remove_part", "head", null, null, null], ["copy_shape", "head", 0, null, null],
			["remove_shape", "head", 0, null, null]],
		"the part buttons and the shape buttons send the selection: %s" % [_sent])
	editor.queue_free()


func _a_button_that_needs_a_selection_is_off() -> void:
	var editor := PartEditor.new()
	var rig := _rig()
	var prism: Button = editor._shape_buttons[FamilyShapes.SHAPE_PRISM]

	add_child(editor)
	editor.set_content(rig, _body(rig))
	_expect(editor._remove_part.disabled and prism.disabled and editor._copy_shape.disabled
		and editor._remove_part.tooltip_text == PartEditor.NEEDS_PART
		and editor._copy_shape.tooltip_text == PartEditor.NEEDS_PART,
		"with no part, each button is off, with the reason")
	editor.select_part("head")
	_expect(not editor._remove_part.disabled and not prism.disabled
		and not editor._copy_shape.disabled and editor._copy_shape.tooltip_text != PartEditor.NEEDS_PART,
		"with a part, each button is on, with its own tooltip")

	var data: Dictionary = _body(rig).data.duplicate(true)

	while not FigureLook.from_data(data).part("head").get("shapes", []).is_empty():
		FigureEdits.remove_shape(data, "head", 0)

	editor.set_content(rig, FigureLook.from_data(data))
	editor.select_part("head")
	_expect(editor.selected_shape() == -1 and editor._copy_shape.disabled
		and editor._copy_shape.tooltip_text == PartEditor.NEEDS_SHAPE and not prism.disabled,
		"a part with no shape turns the two shape buttons off, and the add buttons stay on")
	editor.queue_free()


func _the_keys_remove_and_copy() -> void:
	var editor := PartEditor.new()
	var rig := _rig()

	add_child(editor)
	editor.set_content(rig, _body(rig))
	_sent.clear()
	_record(editor.part_removed, "remove_part")
	_record(editor.part_copied, "copy_part")
	_record(editor.shape_removed, "remove_shape")
	_record(editor.shape_copied, "copy_shape")
	_key(editor, KEY_DELETE)
	_expect(_sent.is_empty(), "a key with no selection sends nothing")
	editor.select_part("upper_arm_l")
	_key(editor, KEY_DELETE)
	_key(editor, KEY_D, true)
	editor.select_shape(1)
	_key(editor, KEY_DELETE)
	_key(editor, KEY_D, true)
	_key(editor, KEY_D)
	_expect(_sent == [["remove_part", "upper_arm_l", null, null, null],
			["copy_part", "upper_arm_l", null, null, null],
			["remove_shape", "upper_arm_l", 1, null, null],
			["copy_shape", "upper_arm_l", 1, null, null]],
		"Delete removes the row, Ctrl+D copies it, and D alone does nothing: %s" % [_sent])
	editor.queue_free()


func _the_grids_follow_the_selection() -> void:
	var editor := PartEditor.new()
	var rig := _rig()
	var body := _body(rig)

	add_child(editor)
	editor.set_content(rig, body)
	editor.select_part("upper_arm_l")
	_expect(editor._name.text == "upper_arm_l"
		and FigureFields.text_of(editor._bone) == body.part("upper_arm_l")["bone"]
		and editor._shape_heading.text.begins_with("Shape 0 (%s)" % FamilyShapes.SHAPE_PRISM),
		"the part grid shows the part, and the shape heading names shape 0")
	editor.select_shape(1)
	_expect(editor._shape_heading.text.begins_with("Shape 1 (%s)" % FamilyShapes.SHAPE_SPHERE)
		and editor._field_controls.has("radius") and editor._name.text == "upper_arm_l",
		"a shape row changes the shape grid, and the part grid stays")

	var data: Dictionary = body.data.duplicate(true)

	FigureEdits.set_shape_value(data, "upper_arm_l", 1, "radius", 0.09)
	editor.set_content(rig, FigureLook.from_data(data))
	_expect(editor.selected_part() == "upper_arm_l" and editor.selected_shape() == 1
		and is_equal_approx((editor._field_controls["radius"] as SpinBox).value, 0.09),
		"new content keeps the selection, and the grid shows the new value")

	FigureEdits.remove_shape(data, "upper_arm_l", 1)
	editor.set_content(rig, FigureLook.from_data(data))
	_expect(editor.selected_part() == "upper_arm_l" and not editor.shape_row_selected()
		and editor.selected_shape() == 0,
		"a shape row that left goes back to the part row")
	_expect(editor.folds().has(PartEditor.FOLD_PARTS) and editor.folds().has(PartEditor.FOLD_MODEL)
		and not (editor.folds()[PartEditor.FOLD_PARTS] as FoldableContainer).folded
		and (editor.folds()[PartEditor.FOLD_MODEL] as FoldableContainer).folded,
		"the Parts fold starts open, and the Part model fold starts closed")
	editor.fit_controls = false
	_expect(not editor._fit.visible and not editor._fit_all.visible and not editor._fit_label.visible,
		"the fit controls hide with their labels")
	editor.queue_free()
