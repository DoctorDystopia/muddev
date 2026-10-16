extends SceneTree
## Print the clearance of a held item for each clip and each body type of
## the repository (DESIGN-0014 section 16). Run with
## `--headless --path godot -s <this file>`. It writes nothing.


func _init() -> void:
	var store := FigureStore.new(FigureStore.repo_directory())
	var library := FigureClips.library()

	store.load_all()

	for clip_name: String in FigureClips.names_of(library):
		for key: String in store.keys_of(FigureStore.KIND_RIG):
			var result := FigureClearance.check(store.rigs[key], store.looks[key],
				library.get_animation(clip_name))

			print(key, "  ", FigureClearance.line_of(clip_name, result))

	quit()
