@tool
extends EditorPlugin
## Phase W3 check of DESIGN-0014, in a real editor window. It runs only in a
## scratch copy of the project, with a scratch copy of the figure files
## beside it. It opens the figure workbench, uses the Gear tab and the
## outfit bar, and writes each answer to `res://gear_check_result.json`.
## Then it closes the editor.

const SCENE := "res://addons/blackout_figure/figure_workbench.tscn"
const RESULT := "res://gear_check_result.json"
const VIEW_PICTURE := "res://gear_check_view.png"
const WINDOW_PICTURE := "res://gear_check_window.png"

## Three items of the item catalog with no worn look at the start.
const SWORD := "rusty_scrap_shortsword"
const DAGGER := "rusty_scrap_dagger"
const GREATSWORD := "rusty_scrap_greatsword"
const HELM := "rusty_scrap_great_helm"

const PART := "item"

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
	var gear := dock.gear_panel()

	selection.clear()
	selection.add_node(bench)
	await _frames(10)
	dock.show_tab(FigureDock.TAB_GEAR)
	await _frames(4)
	_results["store errors"] = Array(bench.store.errors)
	_results["gear rows"] = gear._rows.item_count
	_results["catalog slots and items"] = [bench.catalog.slot_keys().size(),
		bench.catalog.items().size()]
	_results["outfit cells"] = dock.outfit_bar()._cells.size()
	_results["cost with no outfit"] = dock._cost.text

	await _a_row_dresses_the_stands(bench, dock, gear)
	await _a_new_look_and_its_undo(bench, dock, gear)
	await _a_click_and_the_gizmo(bench, dock, gear)
	await _the_fields_of_the_gear_tab(bench, dock, gear)
	await _a_copy_into_another_row(bench, dock, gear)
	await _the_outfit_bar(bench, dock)
	await _the_tab_follows_the_part(bench, dock, gear)
	await _pictures()
	await _a_save(bench, dock)

	var file := FileAccess.open(RESULT, FileAccess.WRITE)

	file.store_string(JSON.stringify(_results, "  "))
	file.close()
	get_tree().quit()


func _a_row_dresses_the_stands(bench: FigureWorkbench, dock: FigureDock,
		gear: FigureGearPanel) -> void:
	_pick_row(gear, SWORD)
	await _frames(6)
	_results["a picked row is in the outfit"] = bench.outfit()
	_results["the row draws the slot shape"] = bench.source_of("body_1", "main_hand")
	_results["the slot shape is on each stand"] = \
		bench.part_node("body_1", "main_hand", PART) != null \
		and bench.part_node("body_2", "main_hand", PART) != null
	_results["item line"] = dock._item_line.text
	_results["cost with the sword"] = dock._cost.text
	_results["the outfit bar shows the sword"] = dock.outfit_bar().shown_in("main_hand")
	_results["note of a row with no look"] = gear._note.text
	_results["no unsaved file after a worn item"] = not bench.has_unsaved_changes()


func _a_new_look_and_its_undo(bench: FigureWorkbench, dock: FigureDock,
		gear: FigureGearPanel) -> void:
	gear._new_look.pressed.emit()
	await _frames(6)
	_results["a new look is in the store"] = bench.store.has(FigureStore.KIND_LOOK, SWORD)
	_results["the stand shows the new look"] = bench.source_of("body_1", "main_hand")
	_results["the tab shows the parts of the look"] = gear.parts_panel()._parts.item_count
	_results["unsaved after the new look"] = bench.has_unsaved_changes()

	_undo(bench)
	await _frames(6)
	_results["undo takes the look away"] = not bench.store.has(FigureStore.KIND_LOOK, SWORD) \
		and bench.source_of("body_1", "main_hand") == FigureOutfit.SOURCE_SLOT_SHAPE
	_redo(bench)
	await _frames(6)
	_results["redo brings the look back"] = bench.store.has(FigureStore.KIND_LOOK, SWORD)
	_results["status after the new look"] = dock._status.text


func _a_click_and_the_gizmo(bench: FigureWorkbench, dock: FigureDock,
		gear: FigureGearPanel) -> void:
	var blade := bench.part_node("body_1", SWORD, PART)
	var other := bench.part_node("body_2", SWORD, PART)

	if blade == null or other == null:
		_results["the look has a node on each stand"] = false
		return

	await _click(_screen_point((blade.get_child(0) as Node3D).global_position))
	_results["a click selects the blade"] = _only(blade)
	_results["the gear tab shows the clicked part"] = [gear.selected_key(),
		gear.parts_panel().selected_part()]

	var text: String = bench.store.looks[SWORD].to_text()
	var before := blade.position

	await _drag_arrow(blade)
	await _frames(6)
	_results["the gizmo moves the blade"] = str(blade.position - before)
	_results["the look follows the gizmo"] = bench.store.looks[SWORD].to_text() != text
	_results["the node of the other stand follows"] = \
		other.position.distance_to(blade.position) < 0.0001
	_results["the blade stays selected"] = _only(blade)

	_undo(bench)
	await _frames(6)
	_results["undo moves the two nodes back"] = blade.position.is_equal_approx(before) \
		and other.position.is_equal_approx(before)
	_results["undo brings the look back"] = bench.store.looks[SWORD].to_text() == text


func _the_fields_of_the_gear_tab(bench: FigureWorkbench, dock: FigureDock,
		gear: FigureGearPanel) -> void:
	var parts := gear.parts_panel()
	var text: String = bench.store.looks[SWORD].to_text()

	parts.select_part(PART)
	await _frames(3)

	var field := parts._place_position.get_child(1) as SpinBox

	field.value = 0.03
	await _frames(3)
	field.value = 0.06
	await _frames(3)
	_results["a place field changes the look"] = \
		bench.store.looks[SWORD].part(PART)["position"][1]
	_undo(bench)
	await _frames(3)
	_results["one undo takes back the two field steps"] = \
		bench.store.looks[SWORD].to_text() == text

	parts._new_kind.select(0)
	parts.shape_requested.emit(PART, FigureFields.text_of(parts._new_kind))
	await _frames(3)
	_results["a new shape joins the part"] = \
		bench.store.looks[SWORD].part(PART)["shapes"].size()
	_results["cost with one more shape"] = dock._cost.text

	var list := gear._colors.get_child(1) as OptionButton
	var role := (gear._colors.get_child(0) as Label).text

	FigureFields.select_text(list, MeshPalette.GOLD)
	list.item_selected.emit(list.selected)
	await _frames(3)
	_results["the color role %s takes gold" % role] = bench.store.looks[SWORD].colors()[role]
	list.item_selected.emit(0)
	await _frames(3)
	_results["a color role in use stays"] = bench.store.looks[SWORD].colors().has(role)
	_results["status of the refused change"] = dock._status.text


func _a_copy_into_another_row(bench: FigureWorkbench, dock: FigureDock,
		gear: FigureGearPanel) -> void:
	_pick_row(gear, DAGGER)
	await _frames(4)
	_results["the dagger takes the place of the sword"] = bench.outfit()
	FigureFields.select_text(gear._copy_from, SWORD)
	gear._copy.pressed.emit()
	await _frames(4)
	_results["the dagger has the parts of the sword"] = \
		bench.store.has(FigureStore.KIND_LOOK, DAGGER) \
		and bench.store.looks[DAGGER].parts() == bench.store.looks[SWORD].parts()

	gear._missing_only.button_pressed = true
	await _frames(3)
	_results["rows with no worn look"] = gear._rows.item_count
	gear._missing_only.button_pressed = false
	await _frames(3)


func _the_outfit_bar(bench: FigureWorkbench, dock: FigureDock) -> void:
	var bar := dock.outfit_bar()

	_set_cell(bar, "head", HELM)
	await _frames(4)
	_results["a cell puts the helm on"] = bench.outfit()
	_results["the helm draws"] = bench.source_of("body_2", "head")
	_set_cell(bar, "two_hands", GREATSWORD)
	await _frames(4)
	_results["a two-handed item empties the hand"] = bench.outfit()
	_results["the bar shows the empty hand"] = bar.shown_in("main_hand")
	_results["cost of the outfit"] = dock._cost.text

	var config := ConfigFile.new()

	config.load(FigureDock.CONFIG_PATH)
	_results["the options file keeps the outfit"] = config.get_value("workbench", "outfit", {})
	_set_cell(bar, "main_hand", SWORD)
	await _frames(4)


func _the_tab_follows_the_part(bench: FigureWorkbench, dock: FigureDock,
		gear: FigureGearPanel) -> void:
	var head := bench.part_node("body_1", "body_1", "upper_leg_l")
	var blade := bench.part_node("body_1", SWORD, PART)

	await _click(_screen_point((head.get_child(0) as Node3D).global_position))
	_results["a click on a body part shows the Body tab"] = [dock.shown_tab(),
		dock.body_panel().selected_part()]
	await _click(_screen_point((blade.get_child(0) as Node3D).global_position))
	_results["a click on a worn part shows the Gear tab"] = [dock.shown_tab(),
		gear.selected_key(), gear.parts_panel().selected_part()]
	await _click(_screen_point(Vector3(0.0, 0.0, 1.5)))
	_results["a click on nothing selects the workbench"] = _only(bench)


func _a_save(bench: FigureWorkbench, dock: FigureDock) -> void:
	_results["scene save"] = EditorInterface.save_scene()
	await _frames(5)
	_results["unsaved after the save"] = bench.has_unsaved_changes()
	_results["dock status"] = dock._status.text
	_results["the look files are on the disk"] = \
		FileAccess.file_exists(bench.store.path_of(FigureStore.KIND_LOOK, SWORD)) \
		and FileAccess.file_exists(bench.store.path_of(FigureStore.KIND_LOOK, DAGGER))
	_results["the saved scene holds no skeleton"] = \
		not FileAccess.get_file_as_string(SCENE).contains(FigureBuilder.SKELETON_NAME)


func _pick_row(gear: FigureGearPanel, key: String) -> void:
	for index in gear._rows.item_count:
		if gear._rows.get_item_metadata(index) == key:
			gear._rows.select(index)
			gear._rows.item_selected.emit(index)


func _set_cell(bar: FigureOutfitBar, slot: String, key: String) -> void:
	var cell: OptionButton = bar._cells[slot]

	for index in cell.item_count:
		if cell.get_item_metadata(index) == key:
			cell.select(index)
			cell.item_selected.emit(index)


func _pictures() -> void:
	var view := EditorInterface.get_editor_viewport_3d(0)
	var dock := _find_dock(EditorInterface.get_base_control())
	var page: Node = dock

	# The Terrain dock shares the tab bar. Put the Figure dock in front, on
	# its Gear tab, so the window picture shows it. The editor can wrap a
	# dock, so the page is the first node above it in a tab container.
	while page != null and not page.get_parent() is TabContainer:
		page = page.get_parent()

	if page != null:
		(page.get_parent() as TabContainer).current_tab = page.get_index()

	dock.show_tab(FigureDock.TAB_GEAR)
	await _frames(4)
	view.get_texture().get_image().save_png(VIEW_PICTURE)
	get_tree().root.get_texture().get_image().save_png(WINDOW_PICTURE)


func _history(bench: FigureWorkbench) -> UndoRedo:
	var manager := EditorInterface.get_editor_undo_redo()

	return manager.get_history_undo_redo(manager.get_object_history_id(bench))


func _undo(bench: FigureWorkbench) -> void:
	var history := _history(bench)

	_results["undo of: " + history.get_current_action_name()] = history.undo()


func _redo(bench: FigureWorkbench) -> void:
	_history(bench).redo()


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
