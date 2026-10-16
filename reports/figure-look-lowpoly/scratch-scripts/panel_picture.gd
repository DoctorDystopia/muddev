extends SceneTree
## One picture of the part editor of the Body tab with a prism selected,
## for DESIGN-0014 section 16.
##
##     godot --path godot -s <this file> -- <output png>
##
## It needs a window, because it draws. It reads the figure files of the
## repository, and it writes only the picture. The panel stands in a plain
## window, not in the editor.

const PIXELS := Vector2i(460, 1500)
const SETTLE_FRAMES := 6


func _init() -> void:
	_run.call_deferred()


func _run() -> void:
	var store := FigureStore.new(FigureStore.repo_directory())
	var panel := FigureBodyPanel.new()
	var back := ColorRect.new()

	store.load_all()
	root.size = PIXELS
	back.color = Color(0.17, 0.18, 0.21)
	back.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(back)
	panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(panel)
	panel.set_content(store.rigs["body_1"], store.looks["body_1"])
	panel.select_part("head")

	for _frame in SETTLE_FRAMES:
		await process_frame

	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(OS.get_cmdline_user_args()[0])
	quit()
