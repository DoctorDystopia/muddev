extends SceneTree
## Give each slot shape its fit on each body type but the first one, from
## the bone lengths (DESIGN-0014 Phase W4). The first body type is the one
## that each slot shape has its places for.
##
##     godot --headless --path godot -s <this file>
##     godot --headless --path godot -s <this file> -- apply
##
## With no `apply`, it prints each fit row and writes nothing. With `apply`,
## it writes each changed look file of the repository. It writes over the
## fit rows that a slot shape has for those body types, and it changes no
## other key of a look.


func _init() -> void:
	var apply := "apply" in OS.get_cmdline_user_args()
	var store := FigureStore.new(FigureStore.repo_directory())

	store.load_all()

	var bodies := store.keys_of(FigureStore.KIND_RIG)
	var made_on: FigureRig = store.rigs[bodies[0]]

	for slot: String in made_on.slots():
		if not store.has(FigureStore.KIND_LOOK, slot):
			continue

		var data := store.data_of(FigureStore.KIND_LOOK, slot)

		for index in range(1, bodies.size()):
			var count := FigureEdits.fit_to_rig(data, made_on, store.rigs[bodies[index]])

			print("%s on %s: %d fit row(s)" % [slot, bodies[index], count])

			for row: Dictionary in data.get("fit", {}).get(bodies[index], []):
				print("    %s scale %s position %s" % [row["part"], row["scale"], row["position"]])

		var problem := store.put(FigureStore.KIND_LOOK, slot, data)

		if not problem.is_empty():
			print("  refused: ", problem)

	if apply:
		print("saved: ", store.save())
	else:
		print("no file written. Give `-- apply` to write.")

	quit()
