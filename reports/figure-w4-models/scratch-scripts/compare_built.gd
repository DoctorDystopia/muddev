extends SceneTree
## Scratch: compare the art file of the chainbody with the served model
## that the pipeline built from it: node names, places, material names.

func _init() -> void:
	var art := FigureModels.new()
	var served := FigureModels.from_directory(FigureStore.repo_models_directory())
	var key := "rusty_scrap_chainbody"
	var worst := 0.0

	art.put_buffer(key, FileAccess.get_file_as_bytes(OS.get_cmdline_user_args()[0]))
	print("art nodes:    ", art.node_names(key))
	print("served nodes: ", served.node_names(key))

	for node: String in art.node_names(key):
		var a := art.node_place(key, node)
		var b := served.node_place(key, node)

		worst = maxf(worst, a.origin.distance_to(b.origin))

		for axis in 3:
			worst = maxf(worst, a.basis[axis].distance_to(b.basis[axis]))

		print("  ", node, ": art roles ", art.material_names(key, node), ", served roles ",
			served.material_names(key, node), ", box ", served.node_bounds(key, node).size)

	print("worst place difference: ", worst)
	quit()
