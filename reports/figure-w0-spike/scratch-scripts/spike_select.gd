@tool
extends EditorPlugin
## Phase W0 spike of DESIGN-0014. It answers one question in a real editor
## window: can the Godot tools select and move a Node3D that a tool script
## made? It makes two nodes, one with no owner and one that the scene root
## owns. It sends mouse events to the 3D view, writes the answers to
## `res://spike_select_result.json`, and closes the editor.

const SCENE := "res://spike_select_scene.tscn"
const RESULT := "res://spike_select_result.json"

## The move arrow of the gizmo, in units of the gizmo size. From
## `node_3d_editor_plugin.cpp`: the arrow offset is 1.4, and its size is 0.35.
const ARROW_CENTRE := 1.575
const DRAG_PIXELS := 90.0
const DRAG_STEPS := 6

var _results := {}


func _enter_tree() -> void:
	_run.call_deferred()


func _run() -> void:
	await get_tree().create_timer(5.0).timeout
	EditorInterface.open_scene_from_path(SCENE)
	EditorInterface.set_main_screen_editor("3D")
	await get_tree().create_timer(2.0).timeout

	var root := EditorInterface.get_edited_scene_root() as Node3D
	var unowned := _box(root, "unowned", Vector3(-1.0, 0.5, 0.0), false)
	var owned := _box(root, "owned", Vector3(1.0, 0.5, 0.0), true)
	var selection := EditorInterface.get_selection()

	await _frames(10)

	for node: Node3D in [unowned, owned]:
		selection.clear()
		await _frames(3)
		await _click(_screen_point(node.global_position))
		_results["click selects %s" % node.name] = selection.get_selected_nodes().has(node)

	for node: Node3D in [unowned, owned]:
		selection.clear()
		selection.add_node(node)
		await _frames(10)
		_results["code selects %s" % node.name] = selection.get_selected_nodes().has(node)

		var before := node.position

		await _drag_arrow(node)
		_results["gizmo moves %s" % node.name] = not node.position.is_equal_approx(before)
		_results["%s moved by" % node.name] = str(node.position - before)

	_results["editor scale"] = EditorInterface.get_editor_scale()
	_results["version"] = Engine.get_version_info()["string"]

	var file := FileAccess.open(RESULT, FileAccess.WRITE)

	file.store_string(JSON.stringify(_results, "  "))
	file.close()
	get_tree().quit()


func _box(root: Node3D, node_name: String, at: Vector3, with_owner: bool) -> Node3D:
	var instance := MeshInstance3D.new()
	var mesh := BoxMesh.new()

	mesh.size = Vector3.ONE * 0.5
	instance.name = node_name
	instance.mesh = mesh
	instance.position = at
	root.add_child(instance)

	if with_owner:
		instance.owner = root

	return instance


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
	await _frames(4)


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


var _last := Vector2.ZERO


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
