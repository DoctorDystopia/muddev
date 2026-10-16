extends SceneTree
## One-time helper of DESIGN-0014 Phase W2. It gives each rig of
## blackout/assets/figure/ the two changes of the phase:
##
## 1. Each hand socket gets the grip as its rest rotation
##    (`FigureEdits.SOCKETS`).
## 2. The file loses its `motion_scale` key. The reader drops the key, so a
##    save writes the file with no such key.
##
## Run with `--headless --path godot -s <this file>`. A second run changes
## nothing.


func _init() -> void:
	var store := FigureStore.new(FigureStore.repo_directory())

	store.load_all()

	for key: String in store.keys_of(FigureStore.KIND_RIG):
		var data := store.data_of(FigureStore.KIND_RIG, key)

		for row: Dictionary in data["bones"]:
			if FigureEdits.SOCKETS.has(row["name"]):
				row["rotation"] = FigureJson.from_quaternion(FigureEdits.SOCKETS[row["name"]][2])

		print(key, ": ", store.put(FigureStore.KIND_RIG, key, data))

	print("saved ", store.save(), " errors ", store.errors)
	quit()
