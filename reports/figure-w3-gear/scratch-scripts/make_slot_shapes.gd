extends SceneTree
## One-time helper of DESIGN-0014 Phase W3: write the slot shape of each
## slot of the item catalog into blackout/assets/figure/looks/, through the
## rules of the workbench. Run with `--headless --path godot -s <this file>`.
##
## A slot shape that is there stays, so a run after Nick changed one keeps
## his work. Pass `-- again` to write each one again from the rules.


func _init() -> void:
	var store := FigureStore.new(FigureStore.repo_directory())
	var catalog := FigureCatalog.read_file()
	var again := "again" in OS.get_cmdline_user_args()

	store.load_all()

	var rig: FigureRig = store.rigs[store.keys_of(FigureStore.KIND_RIG)[0]]

	for slot: String in catalog.slot_keys():
		if store.has(FigureStore.KIND_LOOK, slot) and not again:
			print("kept ", slot)
			continue

		print(slot, " ", store.put(FigureStore.KIND_LOOK, slot,
			FigureEdits.slot_shape(rig, slot).data))

	print("saved ", store.save(), " errors ", store.errors)
	quit()
