@tool
extends EditorPlugin
## Phase W1 check of DESIGN-0014, in a real editor window. It runs only in a
## scratch copy of the project. It opens the figure workbench, sends mouse
## events to the 3D view, and writes each answer to
## `res://figure_check_result.json`. Then it closes the editor.

const SCENE := "res://addons/blackout_figure/figure_workbench.tscn"
const RESULT := "res://figure_check_result.json"
const VIEW_PICTURE := "res://figure_check_view.png"
const WINDOW_PICTURE := "res://figure_check_window.png"

## The move arrow of the gizmo, in units of the gizmo size. From
## `node_3d_editor_plugin.cpp`: the arrow offset is 1.4, and its size is 0.35.
const ARROW_CENTRE := 1.575
const DRAG_PIXELS := 90.0
const DRAG_STEPS := 6

var _results := {}
var _last := Vector2.ZERO


func _enter_tree() -> void:
	_run.call_deferred()


func _run() -> void:
	await get_tree().create_timer(5.0).timeout
	EditorInterface.open_scene_from_path(SCENE)
	EditorInterface.set_main_screen_editor("3D")
	await get_tree().create_timer(2.0).timeout

	var root := EditorInterface.get_edited_scene_root()
	var bench := root.get_node("FigureWorkbench") as FigureWorkbench
	var selection := EditorInterface.get_selection()
	var dock := _find_dock(EditorInterface.get_base_control())

	_results["the dock is in the editor"] = dock != null
	_results["body types"] = Array(bench.body_keys())
	_results["store errors"] = Array(bench.store.errors)
	selection.clear()
	selection.add_node(bench)
	await _frames(10)
	_results["dock body list"] = dock.active_body()
	_results["dock part rows"] = dock.body_panel()._parts.item_count
	_results["dock cost"] = dock._cost.text

	var head := bench.part_node("body_1", "body_1", "head")
	var chest := bench.part_node("body_2", "body_2", "upper_chest")

	await _click(_screen_point((head.get_child(0) as Node3D).global_position))
	_results["a click selects the head"] = _only(head)
	_results["the dock shows the head"] = dock.body_panel().selected_part()

	await _click(_screen_point(Vector3(0.0, 0.0, 1.0)))
	_results["a click on nothing selects the workbench"] = \
		_only(bench)

	await _click(_screen_point((chest.get_child(0) as Node3D).global_position))
	_results["a click selects the chest of body_2"] = _only(chest)
	_results["the dock follows to body_2"] = dock.active_body()
	_results["the dock shows the chest"] = dock.body_panel().selected_part()

	await _gizmo_and_undo(bench, chest)
	await _dock_edit_and_undo(bench, dock)
	await _bone_change_keeps_selection(bench, dock, selection)
	await _pictures()

	_results["unsaved after each undo"] = bench.has_unsaved_changes()
	(dock.body_panel()._place_position.get_child(1) as SpinBox).value = 0.02
	await _frames(3)
	_results["scene save"] = EditorInterface.save_scene()
	await _frames(5)
	_results["unsaved after save"] = bench.has_unsaved_changes()
	_results["dock status"] = dock._status.text

	var file := FileAccess.open(RESULT, FileAccess.WRITE)

	file.store_string(JSON.stringify(_results, "  "))
	file.close()
	get_tree().quit()


func _gizmo_and_undo(bench: FigureWorkbench, chest: Node3D) -> void:
	var text: String = bench.store.looks["body_2"].to_text()
	var before := chest.position

	await _drag_arrow(chest)
	await _frames(6)
	_results["the gizmo moves the part"] = str(chest.position - before)
	_results["the look follows the gizmo"] = bench.store.looks["body_2"].to_text() != text
	_results["the look has the node place"] = FigureLook.part_transform(
		bench.store.looks["body_2"].part("upper_chest")).origin.distance_to(chest.position) < 0.0001
	_results["unsaved after the gizmo"] = bench.has_unsaved_changes()

	_undo(bench)
	await _frames(6)
	_results["undo moves the node back"] = chest.position.is_equal_approx(before)
	_results["undo brings the look back"] = bench.store.looks["body_2"].to_text() == text


func _dock_edit_and_undo(bench: FigureWorkbench, dock: FigureDock) -> void:
	var text: String = bench.store.looks["body_2"].to_text()
	var field := dock.body_panel()._place_position.get_child(0) as SpinBox

	field.value = 0.05
	await _frames(3)
	field.value = 0.08
	await _frames(3)
	_results["a dock field changes the look"] = \
		bench.store.looks["body_2"].part("upper_chest")["position"][0]
	_results["the node follows the field"] = bench.part_node("body_2", "body_2",
		"upper_chest").position.x

	_undo(bench)
	await _frames(3)
	_results["one undo takes back the two field steps"] = \
		bench.store.looks["body_2"].to_text() == text


func _bone_change_keeps_selection(bench: FigureWorkbench, dock: FigureDock,
		selection: EditorSelection) -> void:
	var chest := bench.part_node("body_2", "body_2", "upper_chest")
	var list: OptionButton = dock.body_panel()._bone
	var world_before := chest.global_position

	FigureFields.select_text(list, "Chest")
	list.item_selected.emit(list.selected)
	await _frames(6)
	_results["the part is on the new bone"] = str(chest.get_parent().name)
	_results["the part keeps its place in the world"] = \
		chest.global_position.distance_to(world_before) < 0.001
	_results["the part stays selected"] = _only(chest)
	_undo(bench)
	await _frames(6)
	_results["undo puts the part back on its bone"] = str(chest.get_parent().name)


func _pictures() -> void:
	var view := EditorInterface.get_editor_viewport_3d(0)

	await _frames(4)
	view.get_texture().get_image().save_png(VIEW_PICTURE)
	get_tree().root.get_texture().get_image().save_png(WINDOW_PICTURE)


func _undo(bench: FigureWorkbench) -> void:
	var manager := EditorInterface.get_editor_undo_redo()
	var history := manager.get_history_undo_redo(manager.get_object_history_id(bench))

	_results["undo of: " + history.get_current_action_name()] = history.undo()


func _find_dock(node: Node) -> FigureDock:
	if node is FigureDock:
		return node

	for child: Node in node.get_children():
		var found := _find_dock(child)

		if found != null:
			return found

	return null


## The point of the editor window that shows a world point of the 3D view.
func _screen_point(world: Vector3) -> Vector2:
	var view := EditorInterface.get_editor_viewport_3d(0)
	var container := view.get_parent() as Control
	var camera := view.get_camera_3d()
	var scale := container.size / Vector2(view.size)

	return container.global_position + camera.unproject_position(world) * scale


func _click(at: Vector2) -> void:
	await _move(at)
	await _button(at, true)
	await _button(at, false)
	await _frames(6)


## Drag the X arrow of the move gizmo of a selected node.
func _drag_arrow(node: Node3D) -> void:
	var settings := EditorInterface.get_editor_settings()
	var size := float(settings.get_setting("editors/3d/manipulator_gizmo_size")) \
		* EditorInterface.get_editor_scale()
	var origin := _screen_point(node.global_position)
	var along := (_screen_point(node.global_position + Vector3.RIGHT * 0.2) - origin).normalized()
	var start := origin + along * size * ARROW_CENTRE

	await _move(start)
	await _button(start, true)

	for step in DRAG_STEPS:
		await _move(start + along * DRAG_PIXELS * (step + 1) / DRAG_STEPS, true)

	await _button(start + along * DRAG_PIXELS, false)
	await _frames(4)


func _move(at: Vector2, held := false) -> void:
	var event := InputEventMouseMotion.new()

	event.position = at
	event.global_position = at
	event.relative = at - _last
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if held else 0
	_last = at
	Input.parse_input_event(event)
	await _frames(2)


func _button(at: Vector2, pressed: bool) -> void:
	var event := InputEventMouseButton.new()

	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = pressed
	event.position = at
	event.global_position = at
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
	Input.parse_input_event(event)
	await _frames(2)


func _frames(count: int) -> void:
	for _frame in count:
		await get_tree().process_frame


func _only(node: Node) -> bool:
	var nodes := EditorInterface.get_selection().get_selected_nodes()

	return nodes.size() == 1 and nodes[0] == node
