@tool
extends EditorPlugin
## The Blackout camera plugin: the fly speed bar ([FlySpeedBar]) in the
## toolbar of the 3D editor (Nick, 11/10/2026). The bar works in every 3D
## scene: the terrain editor, the workbenches, and any other scene.
##
## A script that writes an Editor Setting does not move the 3D views at once.
## The Editor Settings dialog sends the change to the editor 1.5 s later, when
## it saves. Thus, the plugin also sends the change notification to each 3D
## view itself. A new speed then applies at the next frame. The save of the
## dialog still writes the setting to disk.

## Godot always makes four 3D views (Node3DEditor::VIEWPORTS_COUNT).
const VIEW_COUNT := 4

## The class of the control that owns the camera of one 3D view. It is an
## ancestor of the SubViewport that EditorInterface gives.
const VIEW_CLASS := "Node3DEditorViewport"

var _bar: FlySpeedBar


func _enter_tree() -> void:
	var settings := EditorInterface.get_editor_settings()

	_bar = FlySpeedBar.new()
	_bar.show_speed(settings.get_setting(FlySpeedBar.SETTING))
	_bar.speed_chosen.connect(_on_speed_chosen)
	settings.settings_changed.connect(_on_settings_changed)
	add_control_to_container(CONTAINER_SPATIAL_EDITOR_MENU, _bar)


func _exit_tree() -> void:
	EditorInterface.get_editor_settings().settings_changed.disconnect(_on_settings_changed)
	remove_control_from_container(CONTAINER_SPATIAL_EDITOR_MENU, _bar)
	_bar.queue_free()


func _on_speed_chosen(speed: float) -> void:
	EditorInterface.get_editor_settings().set_setting(FlySpeedBar.SETTING, speed)
	_tell_views()


## Follow a change from the Editor Settings dialog. A write of the bar comes
## back here too, with the value that the bar already shows.
func _on_settings_changed() -> void:
	_bar.show_speed(EditorInterface.get_editor_settings().get_setting(FlySpeedBar.SETTING))


## Each 3D view reads the "editors/3d" settings again when it gets this
## notification. Then its camera uses the new speed.
func _tell_views() -> void:
	for index in VIEW_COUNT:
		var view := _view_of(EditorInterface.get_editor_viewport_3d(index))

		if view != null:
			view.notification(EditorSettings.NOTIFICATION_EDITOR_SETTINGS_CHANGED)


## The 3D view that holds `node`, or null if no ancestor is one.
static func _view_of(node: Node) -> Node:
	var at := node

	while at != null and at.get_class() != VIEW_CLASS:
		at = at.get_parent()

	return at
