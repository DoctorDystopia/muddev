@tool
extends EditorPlugin
## The Blackout picture editor: the Pictures tab of the main screen, beside
## 2D, 3D, and Script (Nick, 11/16/2026).
##
## The tab is one [PictureEditor]. The author picks an item, and sets the
## zoom, the offset, and the turn of its item picture ([PicturePose]). The
## editor draws each picture with [ItemStage], the class that draws the
## cells of the game. Thus, the author sees the picture of the player.
##
## The editor needs no scene. It reads the served model tree and the figure
## set from disk at its first show, so a start of Godot pays nothing for it.
##
## ## The save
##
## Ctrl+S saves the picture poses with each other file, through
## [method _save_external_data]. The Save button of the tab does the same.
## Godot also asks about unsaved poses when it closes.

const TAB_NAME := "Pictures"

## The icon of the tab, by its name in the theme of the editor.
const TAB_ICON := "ImageTexture"
const ICON_THEME_TYPE := "EditorIcons"

const UNSAVED := "The picture editor has unsaved picture poses. Save them?"

var _editor: PictureEditor


func _enter_tree() -> void:
	_editor = PictureEditor.new()
	_editor.size_flags_vertical = Control.SIZE_EXPAND_FILL
	EditorInterface.get_editor_main_screen().add_child(_editor)
	_make_visible(false)


func _exit_tree() -> void:
	if is_instance_valid(_editor):
		_editor.close()
		_editor.queue_free()


func _has_main_screen() -> bool:
	return true


func _get_plugin_name() -> String:
	return TAB_NAME


func _get_plugin_icon() -> Texture2D:
	return EditorInterface.get_editor_theme().get_icon(TAB_ICON, ICON_THEME_TYPE)


## Show or hide the tab. The first show reads the models and the items.
func _make_visible(shown: bool) -> void:
	if not is_instance_valid(_editor):
		return

	_editor.visible = shown

	if shown and not _editor.is_open():
		_editor.open()


func _save_external_data() -> void:
	if is_instance_valid(_editor) and _editor.has_unsaved_changes():
		_editor.save()


func _get_unsaved_status(for_scene: String) -> String:
	# Godot asks one time for each scene and one time for the editor. The
	# poses belong to no scene.
	if not for_scene.is_empty() or not is_instance_valid(_editor):
		return ""

	return UNSAVED if _editor.has_unsaved_changes() else ""
