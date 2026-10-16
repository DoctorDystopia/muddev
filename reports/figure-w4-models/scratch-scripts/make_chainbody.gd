extends SceneTree
## Scratch: write a chainbody model for the import. The model is the slot
## shape of the `body` slot on body_1, as a reference body file.
##     godot --headless --path <project> -s make_chainbody.gd -- <out.glb>

func _init() -> void:
	var out := OS.get_cmdline_user_args()[0]
	var store := FigureStore.new(FigureStore.repo_directory())

	store.load_all()

	var rig: FigureRig = store.rigs["body_1"]
	var problem := FigureReference.export(rig, [store.looks["body"]], out)

	print("export: ", problem, " -> ", out)
	quit(0 if problem == OK else 1)
