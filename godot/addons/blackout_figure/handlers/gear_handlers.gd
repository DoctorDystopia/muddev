@tool
class_name FigureGearHandlers
extends RefCounted
## The handlers of the Gear tab and of the outfit bar of the figure dock:
## a row, a worn look, a copy, a tier, the colors and the hide list of a
## look, a model import, and the outfit.
##
## A picked row of the Gear tab dresses each stand in that item. The outfit
## bar does the same for one slot. The outfit is no figure file, so it makes
## no undo entry.
##
## ## Models (Phase W4)
##
## "Import a model file" runs the model pipeline through [FigurePipeline],
## on a thread ([FigureJob]). The status box says "Building ..." until the
## build ends, and the import button is off. The parts of the look then
## become the nodes of the model, as one undo entry. The model files stay
## after an undo, as a built clip stays.
##
## The place of each new part comes from the rig of the selected body type.
## Thus, the author selects the body type whose reference body the model
## was made over. "Fit each part from the bone lengths" then gives the
## selected body type its fit, from the rig of the other body type.
##
## "Make the row a tier of this look" gives the look of a row a base. A
## look that is the base of a tier stays until that tier goes.

const JOB_MODEL := "the model %s"

const SCRATCH_IMPORT := "This workbench is on a scratch directory, and an import " \
	+ "writes the repository. Open the workbench of the repository for an import."

var _context: FigureHandlerContext


func _init(context: FigureHandlerContext) -> void:
	_context = context


func connect_panel(panel: FigureGearPanel) -> void:
	panel.row_chosen.connect(_on_gear_row_chosen)
	panel.look_requested.connect(_on_look_requested)
	panel.look_removed.connect(on_look_removed)
	panel.copy_requested.connect(_on_copy_requested)
	panel.tier_requested.connect(_on_tier_requested)
	panel.color_changed.connect(_on_color_changed)
	panel.color_removed.connect(_on_color_removed)
	panel.hide_changed.connect(on_hide_changed)
	panel.import_requested.connect(_on_import_requested)
	panel.model_parts_requested.connect(_on_model_parts_requested)


func connect_outfit_bar(bar: FigureOutfitBar) -> void:
	bar.slot_set.connect(_on_outfit_slot_set)
	bar.cleared.connect(_on_outfit_cleared)
	bar.npc_chosen.connect(_on_npc_chosen)


## A picked row dresses each stand in that item. A slot shape row puts the
## key of the slot in the slot, and the slot shape then shows with no item.
func _on_gear_row_chosen(key: String, slot: String) -> void:
	var bench := _context.bench()

	if bench == null or key.is_empty():
		return

	bench.wear(slot, key)
	_show_row_on_family_stand(key)
	_context.refresh_cost()


## A row with a served model shows that model on the family stand, as the
## game draws it, with its presentation (ENG-0011, step L6). A row with
## none leaves the stand as it is.
func _show_row_on_family_stand(key: String) -> void:
	var bench := _context.bench()
	var model_key := _context.dock().gear_panel().presented_model(key)

	if model_key.is_empty():
		return

	bench.show_entity(model_key, bench.catalog.families().get(key, ""))


## "New look from the slot shape". A slot shape row gets the slot shape of
## [method FigureLookEdits.slot_shape]. An item row gets a copy of the slot
## shape of its slot (requirement A6). A look that is there goes, and an
## undo brings it back.
func _on_look_requested(key: String, slot: String) -> void:
	var bench := _context.bench()
	var rig := _context.active_rig()

	if bench == null or key.is_empty() or rig == null:
		_context.status("Select a row first. The rig gives the bone of each slot.")
		return

	var data: Dictionary = FigureLookEdits.slot_shape(rig, slot).data

	if key != slot:
		var source: FigureLook = bench.store.looks.get(slot, FigureLookEdits.slot_shape(rig, slot))

		data = FigureLookEdits.look_from(key, source)

	_context.history().commit(FigureStore.KIND_LOOK, key,
		bench.store.data_of(FigureStore.KIND_LOOK, key), data, "new look for " + key)


## "Remove look". A look that is the base of a tier stays. The Body tab
## calls this for a kit part also.
func on_look_removed(key: String) -> void:
	var bench := _context.bench()

	if bench == null or not bench.store.has(FigureStore.KIND_LOOK, key):
		_context.status("The row has no worn look.")
		return

	var tiers := FigureLookEdits.tiers_of(bench.store.looks, key)

	if not tiers.is_empty():
		_context.status("%d look(s) take the parts of %s: %s. Remove each one first, or copy a look into it."
			% [tiers.size(), key, ", ".join(tiers)])
		return

	_context.history().commit(FigureStore.KIND_LOOK, key,
		bench.store.data_of(FigureStore.KIND_LOOK, key), {}, "remove the look of " + key)


## "Copy look" (requirement A7). A row with no worn look gets a new one. A
## tier is a legal source. The copy then takes the look that the tier
## draws, with the parts of its base ([method FigureLook.resolved]).
func _on_copy_requested(key: String, from_key: String) -> void:
	var bench := _context.bench()

	if bench == null or key.is_empty() or not bench.store.has(FigureStore.KIND_LOOK, from_key):
		_context.status("Select a row, and the look to copy.")
		return

	var before := bench.store.data_of(FigureStore.KIND_LOOK, key)
	var after: Dictionary = {"format": FigureLook.FORMAT, "key": key} if before.is_empty() \
		else before.duplicate(true)
	var source: FigureLook = bench.store.looks[from_key].resolved(bench.store.looks)
	var problem := FigureLookEdits.copy_look(after, source.data)

	if not problem.is_empty():
		_context.status(problem)
		return

	_context.history().commit(FigureStore.KIND_LOOK, key, before, after,
		"copy the look %s into %s" % [from_key, key])


## "Make the row a tier of this look" (use case 12). The row gets a look
## with a base, and it then has the parts of that base. A look of the row
## that is there keeps only the colors that differ from the base.
func _on_tier_requested(key: String, base_key: String) -> void:
	var bench := _context.bench()

	if bench == null or key.is_empty():
		_context.status("Select a row, and the look that gives its parts.")
		return

	var before := bench.store.data_of(FigureStore.KIND_LOOK, key)
	var after: Dictionary = {"format": FigureLook.FORMAT, "key": key} if before.is_empty() \
		else before.duplicate(true)
	var problem := FigureLookEdits.make_tier(after, base_key, bench.store.looks)

	if not problem.is_empty():
		_context.status(problem)
		return

	_context.history().commit(FigureStore.KIND_LOOK, key, before, after,
		"make %s a tier of %s" % [key, base_key])


func _on_color_changed(key: String, role: String, color: String) -> void:
	_context.history().change_look(key, "set the color of the color role " + role,
		func(look: Dictionary) -> String:
			return FigureLookEdits.set_color(look, role, color, _context.bench().store.palette()))


func _on_color_removed(key: String, role: String) -> void:
	_context.history().change_look(key, "give the color role %s the color of the palette" % role,
		func(look: Dictionary) -> String:
			return FigureLookEdits.remove_color(look, role, _context.bench().store.palette()))
	# A refused change leaves the list on its first choice.
	_context.refresh_panels()


## A region joined the hide list of a look, or left it. The Body tab calls
## this for the body or a kit part also.
func on_hide_changed(key: String, region: String, hidden: bool) -> void:
	var label := ("hide the region %s" if hidden else "show the region %s") % region

	_context.history().change_look(key, label, func(look: Dictionary) -> String:
		return FigureLookEdits.set_hide(look, region, hidden))
	# A refused change leaves the box as the look has it.
	_context.refresh_panels()


## "Import model": run the model pipeline on the file, on a thread. When
## it ends, the parts of the look of the row come from the nodes of the
## built model.
func _on_import_requested(key: String, model_key: String, path: String,
		author: String) -> void:
	var bench := _context.bench()
	var problem := "Select a row first." if key.is_empty() \
		else FigureRigEdits.name_problem(model_key)

	if bench == null or not problem.is_empty():
		_context.status(problem)
		return

	if not bench.writes_repo_figures() or not bench.models_directory.is_empty():
		_context.status(SCRATCH_IMPORT)
		return

	var family := FigurePipeline.FAMILY_FIGURE

	if bench.catalog.has_item(model_key):
		family = FigurePipeline.FAMILY_ITEMS

	_context.dock().save_author(author)
	_context.start_job(JOB_MODEL % model_key,
		FigurePipeline.import_model.bind(family, model_key, path, author),
		_on_import_done.bind(key, model_key, path))


## The model pipeline ended. A built model gives the look its parts.
func _on_import_done(result: Dictionary, key: String, model_key: String, path: String) -> void:
	if not result["ok"]:
		_context.status("The import of %s did not end well:\n%s" % [path.get_file(),
			result["output"]])
		return

	var bench := _context.bench()

	if bench == null:
		return

	bench.reload_models()
	_make_model_parts(key, model_key)


## "Make the parts from the served model".
func _on_model_parts_requested(key: String, model_key: String) -> void:
	var bench := _context.bench()

	if bench == null or key.is_empty():
		_context.status("Select a row first.")
		return

	bench.reload_models()
	_make_model_parts(key, model_key)


## Make the parts of one worn look from the nodes of one served model, as
## one undo entry. A row with no worn look gets a new one. The places come
## from the rig of the selected body type.
func _make_model_parts(key: String, model_key: String) -> void:
	var bench := _context.bench()
	var rig := _context.active_rig()
	var before := bench.store.data_of(FigureStore.KIND_LOOK, key)
	var after: Dictionary = {"format": FigureLook.FORMAT, "key": key} if before.is_empty() \
		else before.duplicate(true)

	if rig == null:
		_context.status("Make a rig first, on the Rig tab.")
		return

	var problem := FigurePartEdits.parts_from_model(after, rig, model_key, bench.models)

	if not problem.is_empty():
		_context.status(problem)
		return

	_context.history().commit(FigureStore.KIND_LOOK, key, before, after,
		"make the parts of %s from the model %s" % [key, model_key])

	var names := PackedStringArray()

	for row: Dictionary in after["parts"]:
		names.append("%s on %s" % [row["name"], row["bone"]])

	_context.status("%d part(s) of %s come from the model %s, on the rig %s: %s."
		% [names.size(), key, model_key, rig.key(), ", ".join(names)])


# ─── The outfit bar ─────────────────────────────────────────────────────────

## The stands wear another outfit: show it, and keep it for the next
## session. The Clips tab goes to the stance of the first item with a tool
## type, so the author sees the clips of the item that the figure holds.
## The plugin connects this to [signal FigureWorkbench.outfit_changed].
func on_outfit_changed() -> void:
	var bench := _context.bench()
	var dock := _context.dock()
	var tool_types := bench.catalog.outfit_tool_types(bench.outfit())

	dock.outfit_bar().set_outfit(bench.outfit())
	dock.save_outfit(bench.outfit())
	_context.refresh_cost()
	_context.refresh_clips()

	if not tool_types.is_empty():
		dock.clips_panel().select_stance(tool_types[0])

	_context.reselect()


func _on_outfit_slot_set(slot: String, asset_key: String) -> void:
	var bench := _context.bench()

	if bench != null:
		bench.wear(slot, asset_key)


func _on_outfit_cleared() -> void:
	var bench := _context.bench()

	if bench != null:
		bench.set_outfit({})


## The author picked an NPC def on the outfit bar. Each stand then wears
## the outfit of that def (use case 15). The server owns the outfit, so
## this changes no file.
func _on_npc_chosen(key: String) -> void:
	var bench := _context.bench()

	if bench == null:
		return

	var outfit := bench.catalog.npc_outfit(key)
	var worn := bench.catalog.valid_outfit(outfit)

	bench.set_outfit(outfit)
	_context.status("The figure wears the outfit of %s: %d item(s)." % [key, worn.size()])

	if worn.size() < outfit.size():
		_context.status("The outfit of %s names %d item(s) that the item catalog does not have. " \
			% [key, outfit.size() - worn.size()] + "Run export_client_constants.py.")
