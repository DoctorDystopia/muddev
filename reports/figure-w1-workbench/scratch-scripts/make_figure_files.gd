extends SceneTree
## One-time helper of DESIGN-0014 Phase W1: write the first two rigs and
## their shape list bodies into blackout/assets/figure/, through the rules
## of the workbench. Run with `--headless --path godot -s <this file>`.

## Each body type: its key, its limb scale, and the girth of its body.
const BODY_TYPES := [["body_1", 1.0, 1.0], ["body_2", 0.95, 0.9]]


func _init() -> void:
	var store := FigureStore.new(FigureStore.repo_directory())

	store.load_all()

	for row: Array in BODY_TYPES:
		if store.has(FigureStore.KIND_RIG, row[0]):
			print("kept ", row[0])
			continue

		var rig := FigureEdits.rig_from_profile(row[0], row[1])

		print(store.put(FigureStore.KIND_RIG, row[0], rig.data))
		print(store.put(FigureStore.KIND_LOOK, row[0], FigureEdits.mannequin(rig, row[2]).data))

	print("saved ", store.save(), " errors ", store.errors)
	quit()
