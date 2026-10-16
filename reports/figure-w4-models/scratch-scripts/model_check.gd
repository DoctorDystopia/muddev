@tool
extends EditorPlugin
## Phase W4 check of DESIGN-0014, in a real editor window. It runs only in a
## scratch copy of the project, with a scratch copy of the figure files and
## of the model pipeline beside it. It opens the figure workbench, exports
## a reference body, imports a chainbody model through the import form,
## sets the hide list and the fit, plays a clip, and saves. It writes each
## answer to `res://model_check_result.json`. Then it closes the editor.

const SCENE := "res://addons/blackout_figure/figure_workbench.tscn"
const RESULT := "res://model_check_result.json"
const PICTURES := "res://model_check_%s.png"

## An item of the `body` slot with no worn look and no model at the start.
const CHAIN := "scrap_chainbody"

const AUTHOR := "Editor Check"
const HIDDEN := ["arms", "torso"]
const WALK := "walk"

## The move arrow of the gizmo, in units of the gizmo size. From
## `node_3d_editor_plugin.cpp`: the arrow offset is 1.4, and its size is 0.35.
const ARROW_CENTRE := 1.575
const DRAG_PIXELS := 60.0
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
	bench.set_outfit({})
	dock.select_body("body_1")
	dock.body_changed.emit("body_1")
	await _frames(4)
	_results["store errors"] = Array(bench.store.errors)
	_results["the workbench writes its repository"] = bench.writes_repo()
	_results["the pipeline is there"] = FigurePipeline.is_there()
	_results["python"] = FigurePipeline.python_of(FigurePipeline.game_directory())

	await _the_reference_body(bench, dock)
	dock.show_tab(FigureDock.TAB_GEAR)
	await _frames(4)
	await _the_import(bench, dock, gear)
	await _the_hide_list(bench, dock, gear)
	await _the_fit(bench, dock, gear)
	await _a_clip(bench, dock)
	await _pictures(dock, "rest")
	await _the_new_controls(dock, gear)
	await _a_save(bench, dock)

	var file := FileAccess.open(RESULT, FileAccess.WRITE)

	file.store_string(JSON.stringify(_results, "  "))
	file.close()
	get_tree().quit()


func _the_reference_body(bench: FigureWorkbench, dock: FigureDock) -> void:
	var path := ProjectSettings.globalize_path("res://").path_join("../reference_body_1.glb") \
		.simplify_path()
	var models := FigureModels.new()

	dock.show_tab(FigureDock.TAB_BODY)
	await _frames(4)
	_results["the save box starts with"] = dock.body_panel()._save_dialog.current_file
	dock.body_panel()._save_dialog.file_selected.emit(path)
	await _frames(4)
	_results["status after the reference body"] = dock._status.text
	_results["the reference body is a file"] = FileAccess.file_exists(path)
	_results["the reference body reads as a model"] = models.put_buffer("reference",
		FileAccess.get_file_as_bytes(path))
	_results["nodes of the reference body, parts of the body"] = [
		models.node_names("reference").size(), bench.store.looks["body_1"].parts().size()]


func _the_import(bench: FigureWorkbench, dock: FigureDock, gear: FigureGearPanel) -> void:
	var art := ProjectSettings.globalize_path("res://").path_join("../chainbody_art.glb") \
		.simplify_path()
	var before: int = bench.counts_of("body_1")["parts"]

	_pick_row(gear, CHAIN)
	await _frames(6)
	_results["the row draws"] = bench.source_of("body_1", "body")
	_results["a row with no look has no hide list to change"] = \
		(gear._hides.get_child(0) as CheckBox).disabled
	_results["hide boxes"] = gear._hides.get_child_count()
	_results["the art file is there"] = FileAccess.file_exists(art)

	var started := Time.get_ticks_msec()

	gear._author.text = AUTHOR
	gear._open_dialog.file_selected.emit(art)
	_results["seconds for the import"] = (Time.get_ticks_msec() - started) / 1000.0
	await _frames(8)
	_results["status after the import"] = dock._status.text
	_results["the look is in the store"] = bench.store.has(FigureStore.KIND_LOOK, CHAIN)

	if not bench.store.has(FigureStore.KIND_LOOK, CHAIN):
		return

	var look: FigureLook = bench.store.looks[CHAIN]
	var bones := {}
	var drawn := 0

	for row: Dictionary in look.parts():
		bones[row["name"]] = row["bone"]

		for body_key: String in bench.body_keys():
			var node := bench.part_node(body_key, CHAIN, row["name"])

			if node != null and node.get_child_count() == 1 \
					and (node.get_child(0) as MeshInstance3D).mesh != null \
					and node.get_child(0).name == row["node"]:
				drawn += 1

	_results["the bone of each part"] = bones
	_results["the models of the look"] = Array(look.model_keys())
	_results["nodes that draw their model, on the two stands"] = drawn
	_results["the stand shows the look of the item"] = bench.source_of("body_1", "body")
	_results["parts before and after the import"] = [before, bench.counts_of("body_1")["parts"]]
	_results["cost with the chainbody"] = dock._cost.text
	_results["the options file keeps the author"] = dock.saved_author()
	_results["the model line"] = _model_line(gear, look.parts()[0]["name"])
	_results["the served model is a file"] = FileAccess.file_exists(
		bench.served_models_directory().path_join("items/%s.glb" % CHAIN))

	_undo(bench)
	await _frames(6)
	_results["undo takes the look away"] = not bench.store.has(FigureStore.KIND_LOOK, CHAIN)
	_redo(bench)
	await _frames(6)
	_results["redo brings the look back"] = bench.store.has(FigureStore.KIND_LOOK, CHAIN)


func _model_line(gear: FigureGearPanel, part_name: String) -> String:
	gear.parts_panel().select_part(part_name)

	return gear.parts_panel()._model_line.text


func _the_hide_list(bench: FigureWorkbench, dock: FigureDock, gear: FigureGearPanel) -> void:
	var bare: int = bench.counts_of("body_1")["parts"]

	for index in gear._hides.get_child_count():
		var box := gear._hides.get_child(index) as CheckBox

		if box.text in HIDDEN:
			box.button_pressed = true
			await _frames(4)

	_results["the hide list of the look"] = bench.store.looks[CHAIN].hides()
	_results["status after the hide list"] = dock._status.text
	_results["parts before and after the hide list"] = [bare, bench.counts_of("body_1")["parts"]]

	for body_key: String in bench.body_keys():
		var shown := PackedStringArray()

		for row: Dictionary in bench.store.looks[body_key].parts():
			if row["region"] in HIDDEN and bench.part_node(body_key, body_key, row["name"]) != null:
				shown.append(row["name"])

		_results["body parts of %s that still show in a hidden region" % body_key] = Array(shown)

	_undo(bench)
	await _frames(6)
	_results["undo shows one region again"] = bench.store.looks[CHAIN].hides()
	_redo(bench)
	await _frames(6)
	_results["the boxes after the redo"] = _ticked(gear)


func _ticked(gear: FigureGearPanel) -> Array:
	var ticked := []

	for index in gear._hides.get_child_count():
		var box := gear._hides.get_child(index) as CheckBox

		if box.button_pressed:
			ticked.append(box.text)

	return ticked


func _the_fit(bench: FigureWorkbench, dock: FigureDock, gear: FigureGearPanel) -> void:
	var parts := gear.parts_panel()

	dock.select_body("body_2")
	dock.body_changed.emit("body_2")
	await _frames(6)
	parts._fit_all.pressed.emit()
	await _frames(6)
	_results["status after the fit from the bone lengths"] = dock._status.text

	var look: FigureLook = bench.store.looks[CHAIN]
	var fitted := {}

	for row: Dictionary in look.fit().get("body_2", []):
		fitted[row["part"]] = row["scale"]

	_results["the fit rows of body_2"] = fitted

	if fitted.is_empty():
		return

	var part_name: String = fitted.keys()[0]
	var first := bench.part_node("body_1", CHAIN, part_name)
	var second := bench.part_node("body_2", CHAIN, part_name)

	_results["the two stands place the fitted part differently"] = \
		not first.transform.is_equal_approx(second.transform)
	parts.select_part(part_name)
	await _frames(4)
	_results["the fit box is ticked for the fitted part"] = parts._fit.button_pressed

	# A move with the gizmo on the stand of body_2 goes into the fit row.
	await _click(_screen_point((second.get_child(0) as Node3D).global_position))
	_results["a click selects the part on body_2"] = _only(second)

	var base := FigureLook.part_transform(look.part(part_name))
	var before := second.position

	await _drag_arrow(second)
	await _frames(6)
	look = bench.store.looks[CHAIN]
	_results["the gizmo moves the part on body_2"] = str(second.position - before)
	_results["the move is in the fit row"] = \
		look.place_of(part_name, "body_2").origin.distance_to(second.position) < 0.0001
	_results["the part keeps its place on body_1"] = \
		FigureLook.part_transform(look.part(part_name)).is_equal_approx(base) \
		and first.transform.is_equal_approx(base)

	# The fit box takes the row away, and the part goes back to its place.
	parts.select_part(part_name)
	await _frames(3)
	parts._fit.button_pressed = false
	await _frames(6)
	_results["an empty fit box takes the row away"] = \
		bench.store.looks[CHAIN].fit_row("body_2", part_name).is_empty()
	_undo(bench)
	await _frames(6)
	_results["undo brings the row back"] = \
		not bench.store.looks[CHAIN].fit_row("body_2", part_name).is_empty()
	await _click(_screen_point(Vector3(0.0, 0.0, 1.5)))


func _a_clip(bench: FigureWorkbench, dock: FigureDock) -> void:
	_results["the clip plays"] = bench.play_clip(WALK)

	for index in 3:
		await get_tree().create_timer(0.3).timeout
		await _pictures(dock, "walk_%d" % index)

	bench.stop_clip()
	await _frames(4)


## Two window pictures with the Gear tab at its new controls: the hide list
## with the model form, and the fit controls of the part editor.
func _the_new_controls(dock: FigureDock, gear: FigureGearPanel) -> void:
	var scroll := gear.get_parent() as ScrollContainer
	var parts := gear.parts_panel()

	_pick_row(gear, CHAIN)
	await _frames(6)
	parts.select_part(parts._parts.get_item_metadata(0))
	await _frames(4)
	await _pictures(dock, "rest")
	scroll.scroll_vertical = int(gear._hides.position.y) - 60
	await _frames(4)
	get_tree().root.get_texture().get_image().save_png(PICTURES % "window_hide_list")
	scroll.scroll_vertical = int(parts.position.y + parts._name.position.y) - 120
	await _frames(4)
	get_tree().root.get_texture().get_image().save_png(PICTURES % "window_fit")
	scroll.scroll_vertical = 0


func _a_save(bench: FigureWorkbench, dock: FigureDock) -> void:
	_results["scene save"] = EditorInterface.save_scene()
	await _frames(5)
	_results["unsaved after the save"] = bench.has_unsaved_changes()
	_results["dock status after the save"] = dock._status.text

	var figure_set := FigureSet.read_file(
		bench.served_models_directory().path_join(FigureSet.FILE_NAME))

	_results["the served figure set has the look"] = figure_set.looks.has(CHAIN) \
		and figure_set.looks[CHAIN].to_text() == bench.store.looks[CHAIN].to_text()
	_results["the saved look file"] = FileAccess.get_file_as_string(
		bench.store.path_of(FigureStore.KIND_LOOK, CHAIN)).length()
	_results["the saved scene holds no skeleton"] = \
		not FileAccess.get_file_as_string(SCENE).contains(FigureBuilder.SKELETON_NAME)


func _pick_row(gear: FigureGearPanel, key: String) -> void:
	for index in gear._rows.item_count:
		if gear._rows.get_item_metadata(index) == key:
			gear._rows.select(index)
			gear._rows.item_selected.emit(index)


## Save the 3D view and the whole window. The Figure dock is in front, on
## its Gear tab, so the window picture shows the new controls.
func _pictures(dock: FigureDock, name_of: String) -> void:
	var view := EditorInterface.get_editor_viewport_3d(0)
	var page: Node = dock

	while page != null and not page.get_parent() is TabContainer:
		page = page.get_parent()

	if page != null:
		(page.get_parent() as TabContainer).current_tab = page.get_index()

	dock.show_tab(FigureDock.TAB_GEAR)
	await _frames(4)
	view.get_texture().get_image().save_png(PICTURES % ("view_" + name_of))
	get_tree().root.get_texture().get_image().save_png(PICTURES % ("window_" + name_of))


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
