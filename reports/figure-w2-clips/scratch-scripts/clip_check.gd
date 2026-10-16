@tool
extends EditorPlugin
## Phase W2 check of DESIGN-0014, in a real editor window. It runs only in a
## scratch copy of the project, with a scratch copy of the figure files and
## of the source beside it. It opens the figure workbench, uses the Clips
## tab, and writes each answer to `res://clip_check_result.json`. Then it
## closes the editor.

const SCENE := "res://addons/blackout_figure/figure_workbench.tscn"
const RESULT := "res://clip_check_result.json"
const VIEW_PICTURE := "res://clip_check_view.png"
const WINDOW_PICTURE := "res://clip_check_window.png"
const CLIPS_TAB := 2
const WALK := "walk"
const PLAY_FRAMES := 40

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
	var dock := _find(EditorInterface.get_base_control(), "FigureDock") as FigureDock
	var panel := dock.clips_panel()

	selection.clear()
	selection.add_node(bench)
	await _frames(10)
	dock._tabs.current_tab = CLIPS_TAB
	_results["store errors"] = Array(bench.store.errors)
	_results["clips in the tab"] = panel._clips.item_count
	_results["clip lists in the tab"] = panel._lists.text

	await _play(bench, panel)
	await _probe(bench, dock, panel)
	await _clip_list(bench, panel)
	await _animation_editor(bench, panel, selection)

	_results["scene save"] = EditorInterface.save_scene()
	await _frames(5)

	var scene_text := FileAccess.get_file_as_string(SCENE)

	_results["the saved scene holds no player and no skeleton"] = \
		not scene_text.contains(FigureClips.PLAYER_NAME) \
		and not scene_text.contains(FigureBuilder.SKELETON_NAME)
	_results["dock status"] = dock._status.text

	var file := FileAccess.open(RESULT, FileAccess.WRITE)

	file.store_string(JSON.stringify(_results, "  "))
	file.close()
	get_tree().quit()


func _play(bench: FigureWorkbench, panel: FigureClipsPanel) -> void:
	_choose(panel, WALK)
	await _frames(4)
	_results["a chosen clip shows its first moment"] = bench.shown_clip() == WALK \
		and not bench.is_playing()
	_results["clearance lines"] = panel._clearance.text

	panel.play_requested.emit(panel.selected_clip(), panel.speed())
	await _frames(PLAY_FRAMES)
	_results["the clip plays in the editor"] = bench.is_playing()
	_results["time after %d frames" % PLAY_FRAMES] = bench.clip_time()
	_results["the slider follows the clip"] = absf(panel._time.value - bench.clip_time()) < 0.1

	var skeleton := FigureBuilder.skeleton_of(bench.figure_of("body_2"))
	var leg := skeleton.find_bone("LeftUpperLeg")

	_results["a bone of body_2 is off its rest"] = not skeleton.get_bone_pose(leg).is_equal_approx(
		skeleton.get_bone_rest(leg))

	panel.pause_requested.emit()
	await _frames(4)

	var held := bench.clip_time()

	await _frames(10)
	_results["a pause holds the time"] = is_equal_approx(bench.clip_time(), held) \
		and not bench.is_playing()

	panel._time.value = 0.4
	await _frames(4)
	_results["the slider moves the figures"] = is_equal_approx(bench.clip_time(), 0.4)


func _probe(bench: FigureWorkbench, dock: FigureDock, panel: FigureClipsPanel) -> void:
	var before := dock._cost.text

	panel._probe.button_pressed = true
	await _frames(6)
	_results["cost with no probe"] = before
	_results["cost with the probe"] = dock._cost.text

	var probe := bench.part_node("body_1", FigureClearance.PROBE_LOOK, "probe_hand_r")

	_results["the probe is on the stand"] = probe != null
	await _pictures()

	if probe != null:
		var tip := probe.global_transform * Vector3(0.0, FigureClearance.PROBE_LENGTH * 0.9, 0.0)

		await _click(_screen_point(tip))
		_results["a click on the probe does not select it"] = \
			not EditorInterface.get_selection().get_selected_nodes().has(probe)

	_results["no unsaved file after the probe"] = not bench.has_unsaved_changes()


func _clip_list(bench: FigureWorkbench, panel: FigureClipsPanel) -> void:
	var key: String = bench.store.keys_of(FigureStore.KIND_CLIPS)[0]

	panel._from_text.text = "Running_A"
	panel._name.text = "run"
	panel._loop.button_pressed = true
	panel._put.pressed.emit()
	await _frames(4)
	_results["the clip list takes the clip"] = bench.store.clip_lists[key].source_clip("run")
	_results["unsaved after the new clip"] = bench.has_unsaved_changes()

	var manager := EditorInterface.get_editor_undo_redo()
	var history := manager.get_history_undo_redo(manager.get_object_history_id(bench))

	_results["undo of: " + history.get_current_action_name()] = history.undo()
	await _frames(4)
	_results["undo takes the clip out"] = not bench.store.clip_lists[key].clips().has("run")
	history.redo()
	await _frames(4)

	var start := Time.get_ticks_msec()

	panel.build_requested.emit()
	await _frames(10)
	_results["build milliseconds"] = Time.get_ticks_msec() - start
	_results["clips after the build"] = Array(bench.clip_names())
	_results["the tab lists the clips of the source"] = panel._from.item_count
	_results["the shown clip stays after the build"] = bench.shown_clip()


func _animation_editor(bench: FigureWorkbench, panel: FigureClipsPanel,
		selection: EditorSelection) -> void:
	_choose(panel, "run")
	panel.animation_editor_requested.emit()
	await _frames(10)

	var player := bench.player_of("body_1") if bench.body_keys()[0] == "body_1" else null
	var nodes := selection.get_selected_nodes()
	var editor := _find(EditorInterface.get_base_control(), "AnimationPlayerEditor") as Control

	_results["the button selects a clip player"] = nodes.size() == 1 \
		and nodes[0] is AnimationPlayer
	_results["the selected player is of the active body type"] = player != null \
		and nodes.size() == 1 and nodes[0] == player
	_results["the animation editor is on the screen"] = editor != null \
		and editor.is_visible_in_tree()

	if nodes.size() == 1 and nodes[0] is AnimationPlayer:
		_results["the animation editor has the clip"] = (nodes[0] as AnimationPlayer).assigned_animation

	await _frames(4)
	get_tree().root.get_texture().get_image().save_png("res://clip_check_animation_editor.png")
	selection.clear()
	selection.add_node(bench)
	await _frames(6)


func _choose(panel: FigureClipsPanel, clip_name: String) -> void:
	for index in panel._clips.item_count:
		if panel._clips.get_item_metadata(index) == clip_name:
			panel._clips.select(index)
			panel._clips.item_selected.emit(index)


func _pictures() -> void:
	var view := EditorInterface.get_editor_viewport_3d(0)

	await _frames(4)
	view.get_texture().get_image().save_png(VIEW_PICTURE)
	get_tree().root.get_texture().get_image().save_png(WINDOW_PICTURE)


func _find(node: Node, type: String) -> Node:
	if node.is_class(type) or (node.get_script() != null
			and node.get_script().get_global_name() == type):
		return node

	for child: Node in node.get_children():
		var found := _find(child, type)

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


func _move(at: Vector2) -> void:
	var event := InputEventMouseMotion.new()

	event.position = at
	event.global_position = at
	event.relative = at - _last
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
