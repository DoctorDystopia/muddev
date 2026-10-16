extends SceneTree
## Make the palette and the stance table of the repository, when they are
## not there (DESIGN-0014 Phase W5).
##
##     godot --headless --path godot -s <this file>
##     godot --headless --path godot -s <this file> -- apply
##
## With no `apply`, it prints what it would write, and it writes nothing.
## With `apply`, it writes each missing file. It never writes over a file
## that is there: the palette is the design of the author after the first
## save.
##
## The palette is that of [method FigureEdits.new_palette]. The stance table
## has a default clip set only: each action whose name is the name of a
## clip file gets that clip.


func _init() -> void:
	var apply := "apply" in OS.get_cmdline_user_args()
	var stances_path := ProjectSettings.globalize_path(FigureStances.STANCES_PATH)
	var store := FigureStore.new(FigureStore.repo_directory(), stances_path)
	var palette_kind := FigureStore.KIND_PALETTE
	var stances_kind := FigureStore.KIND_STANCES

	store.load_all()

	if store.has(palette_kind, palette_kind):
		print("the palette is there: no change")
	else:
		var palette := FigureEdits.new_palette()

		print("new palette: %d named color(s), %d color role(s). %s" % [
			palette.colors().size(), palette.roles().size(),
			store.put(palette_kind, palette_kind, palette.data)])

	if store.has(stances_kind, stances_kind):
		print("the stance table is there: no change")
	else:
		var table := FigureEdits.new_stances()
		var clips := FigureClips.names_of(FigureClips.library())

		for action: String in FigureStances.ACTIONS:
			if action in clips:
				FigureEdits.set_stance_clip(table, "", action, action)

		print("new stance table: default clip set %s. %s" % [table["default"],
			store.put(stances_kind, stances_kind, table)])

	for line: String in store.errors:
		print("  error: ", line)

	if apply:
		print("saved: ", store.save())
	else:
		print("no file written. Give `-- apply` to write.")

	quit()
