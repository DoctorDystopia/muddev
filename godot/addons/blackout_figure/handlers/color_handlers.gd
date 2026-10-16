@tool
class_name FigureColorHandlers
extends RefCounted
## The handlers of the Colors tab of the figure dock: the palette, the
## named colors, the finishes, the color roles, and the colors of the
## character on the stands.
##
## The Colors tab changes the palette, which is one more figure file. Each
## change is an undo entry, and a drag in the color picker is one entry.
## The colors of the character on the stands are no figure file, as the
## outfit is none.
##
## A new name for a named color changes the palette and each look that
## names the color. [method FigureHistory.commit_many] makes one undo entry
## of them.

var _context: FigureHandlerContext


func _init(context: FigureHandlerContext) -> void:
	_context = context


func connect_panel(panel: FigureColorsPanel) -> void:
	panel.palette_requested.connect(_on_palette_requested)
	panel.color_set.connect(_on_named_color_set)
	panel.finish_changed.connect(_on_finish_changed)
	panel.color_removed.connect(_on_named_color_removed)
	panel.color_renamed.connect(_on_named_color_renamed)
	panel.role_changed.connect(_on_role_changed)
	panel.role_removed.connect(_on_role_removed)
	panel.figure_color_changed.connect(_on_figure_color_changed)
	panel.finish_set.connect(_on_finish_set)
	panel.finish_removed.connect(_on_finish_removed)


## "New palette from the start colors". An undo removes the palette again.
func _on_palette_requested() -> void:
	var bench := _context.bench()

	if bench == null:
		return

	if bench.store.has(FigureStore.KIND_PALETTE, FigureStore.KIND_PALETTE):
		_context.status("The workbench has a palette.")
		return

	_context.history().commit(FigureStore.KIND_PALETTE, FigureStore.KIND_PALETTE, {},
		FigurePaletteEdits.new_palette().data, "new palette")


## Change the palette, as one undo entry.
func _change_palette(label: String, edit: Callable, merge := false) -> void:
	_context.history().change(FigureStore.KIND_PALETTE, FigureStore.KIND_PALETTE, label, edit,
		merge)


## A named color got a color. One drag in the color picker is one entry.
func _on_named_color_set(color_name: String, color: Color) -> void:
	var edit := func(palette: Dictionary) -> String:
		return FigurePaletteEdits.set_named_color(palette, color_name, color)

	_change_palette("set the color " + color_name, edit, true)
	_context.dock().colors_panel().select_color(color_name)


func _on_finish_changed(color_name: String, finish: String) -> void:
	_change_palette("set the finish of the color " + color_name,
		func(palette: Dictionary) -> String:
			return FigurePaletteEdits.set_color_finish(palette, color_name, finish))


## A finish got its two numbers, or a new finish joined the palette. One
## drag of a spin box is one entry.
func _on_finish_set(finish: String, metalness: float, roughness: float) -> void:
	_change_palette("set the finish " + finish, func(palette: Dictionary) -> String:
		return FigurePaletteEdits.set_finish(palette, finish, metalness, roughness), true)
	_context.dock().colors_panel().select_finish(finish)


func _on_finish_removed(finish: String) -> void:
	_change_palette("remove the finish " + finish, func(palette: Dictionary) -> String:
		return FigurePaletteEdits.remove_finish(palette, finish))


## The colors of the character on the stands are no figure file, so the
## edit rule cannot see them. The handler refuses for them here.
func _on_named_color_removed(color_name: String) -> void:
	var bench := _context.bench()
	var figure_colors := bench.figure_colors() if bench != null else {}

	for role: String in figure_colors:
		if figure_colors[role] == color_name:
			_context.status("The character on the stands has the color %s for %s. " % [
				color_name, role] + "Pick another color there first.")
			return

	_change_palette("remove the color " + color_name, func(palette: Dictionary) -> String:
		return FigurePaletteEdits.remove_named_color(palette, color_name,
			_context.bench().store.looks))


## "Give the selected color this name": the palette, and each worn look
## that names the color, as one undo entry.
func _on_named_color_renamed(color_name: String, new_name: String) -> void:
	var bench := _context.bench()

	if bench == null \
			or not bench.store.has(FigureStore.KIND_PALETTE, FigureStore.KIND_PALETTE):
		_context.status(FigureHistory.NO_FILE_STATUS[FigureStore.KIND_PALETTE])
		return

	var store := bench.store
	var before := store.data_of(FigureStore.KIND_PALETTE, FigureStore.KIND_PALETTE)
	var after := before.duplicate(true)
	var problem := FigurePaletteEdits.rename_named_color(after, color_name, new_name)
	var changes := [[FigureStore.KIND_PALETTE, FigureStore.KIND_PALETTE, before, after]]

	if not problem.is_empty():
		_context.status(problem)
		return

	for look_key: String in store.keys_of(FigureStore.KIND_LOOK):
		var old_look := store.data_of(FigureStore.KIND_LOOK, look_key)
		var new_look := old_look.duplicate(true)

		if FigurePaletteEdits.rename_color_in_look(new_look, color_name, new_name,
				store.palette().role_names()):
			changes.append([FigureStore.KIND_LOOK, look_key, old_look, new_look])

	_context.history().commit_many(changes, "give the color %s the name %s" % [color_name,
		new_name])
	_rename_figure_color(color_name, new_name)
	_context.dock().colors_panel().select_color(new_name)


## The colors of the character on the stands follow a new name. They are
## no figure file, so they are outside the undo entry: an undo of the name
## leaves them on the new name, and the stands then draw the fallback.
func _rename_figure_color(color_name: String, new_name: String) -> void:
	if not _store_has_color(new_name):
		return

	var bench := _context.bench()
	var colors := bench.figure_colors()
	var renamed := false

	for role: String in colors:
		if colors[role] == color_name:
			colors[role] = new_name
			renamed = true

	if renamed:
		bench.set_figure_colors(colors)
		_context.dock().save_figure_colors(colors)


## True when the palette of the store has the named color.
func _store_has_color(color_name: String) -> bool:
	var bench := _context.bench()

	return bench != null and bench.store.palette().has_color(color_name)


func _on_role_changed(role: String, color_name: String) -> void:
	_change_palette("set the color of the color role " + role,
		func(palette: Dictionary) -> String:
			return FigurePaletteEdits.set_role_color(palette, role, color_name))


func _on_role_removed(role: String) -> void:
	_change_palette("remove the color role " + role, func(palette: Dictionary) -> String:
		return FigurePaletteEdits.remove_role(palette, role, _context.bench().store.looks))
	# A refused change leaves the list on its first choice.
	_context.refresh_colors()


## A color role of the character got a color on the stands. This is no
## figure file, so it makes no undo entry.
func _on_figure_color_changed(role: String, color_name: String) -> void:
	var bench := _context.bench()

	if bench != null:
		bench.set_figure_color(role, color_name)


## The stands have the colors of another character: show them, and keep
## them for the next session. The plugin connects this to
## [signal FigureWorkbench.figure_colors_changed].
func on_figure_colors_changed() -> void:
	_context.dock().save_figure_colors(_context.bench().figure_colors())
	_context.refresh_colors()
