@tool
class_name FigureBodyHandlers
extends RefCounted
## The handlers of the Body tab of the figure dock: a new body, the
## reference body, and the kit parts.
##
## A kit part is a worn look with a kit group. The Body tab edits the body
## or one kit part, so its part editor asks [method
## FigureBodyPanel.edited_look] for its look. The kit of the stands is no
## figure file, as the outfit is none. An NPC def of the outfit bar gives
## the stands the outfit of that def.
##
## The hide list and the removal of a kit part are rules of a worn look,
## so the two go to [FigureGearHandlers].

var _context: FigureHandlerContext

## The handlers of a worn look: the hide list, and the removal of a look.
var _gear: FigureGearHandlers


func _init(context: FigureHandlerContext, gear: FigureGearHandlers) -> void:
	_context = context
	_gear = gear


func connect_panel(panel: FigureBodyPanel) -> void:
	panel.new_body_requested.connect(_on_new_body)
	panel.reference_requested.connect(_on_reference_requested)
	panel.edited_changed.connect(_on_edited_changed)
	panel.kit_part_chosen.connect(_on_kit_part_chosen)
	panel.kit_requested.connect(_on_kit_requested)
	panel.kit_removed.connect(_on_kit_removed)
	panel.hide_changed.connect(func(region: String, hidden: bool) -> void:
		_gear.on_hide_changed(panel.edited_look(), region, hidden))


## "New body from the rig": the shape list body of the selected body type.
## It takes the place of the body that is there, and an undo brings that
## body back.
func _on_new_body() -> void:
	var bench := _context.bench()
	var body_key := _context.dock().active_body()

	if bench == null or not bench.store.has(FigureStore.KIND_RIG, body_key):
		_context.status("Make a rig first, on the Rig tab.")
		return

	_context.history().commit(FigureStore.KIND_LOOK, body_key,
		bench.store.data_of(FigureStore.KIND_LOOK, body_key),
		FigureLookEdits.mannequin(bench.store.rigs[body_key]).data, "new body for " + body_key)


## "Export the reference body": the figure of the selected body type in its
## rest pose, with its outfit, as a file for a modeler.
func _on_reference_requested(path: String) -> void:
	var bench := _context.bench()

	if bench == null:
		return

	var body_key := _context.dock().active_body()
	var problem := bench.export_reference(body_key, path)

	if problem == OK:
		_context.status("Wrote the reference body of %s to %s." % [body_key, path])
	else:
		_context.status("Cannot write the reference body of %s to %s (error %d)."
			% [body_key, path, problem])


# ─── The kit parts of the Body tab ──────────────────────────────────────────

## The part editor of the Body tab shows another look: the body, or a kit
## part.
func _on_edited_changed() -> void:
	_context.refresh_panels()
	_context.reselect()


## The stands get one kit part of one kit group. The kit is no figure file,
## so it makes no undo entry.
func _on_kit_part_chosen(group: String, look_key: String) -> void:
	var bench := _context.bench()

	if bench != null:
		bench.set_kit_part(group, look_key)


## The stands have the kit of another character: show it, and keep it for
## the next session. The plugin connects this to
## [signal FigureWorkbench.kit_changed].
func on_kit_changed() -> void:
	_context.dock().save_kit(_context.bench().kit())
	_context.refresh_panels()
	_context.reselect()


## "New kit part": a worn look in a kit group, with one prism on the bone of
## the new part list. The stands wear it, and the part editor shows it.
func _on_kit_requested(key: String, group: String, bone: String) -> void:
	var bench := _context.bench()

	if bench == null:
		return

	var taken := PackedStringArray(bench.store.looks.keys())

	taken.append_array(bench.store.keys_of(FigureStore.KIND_RIG))
	taken.append_array(bench.catalog.slot_keys())

	for row: Dictionary in bench.catalog.items():
		taken.append(row["key"])

	var problem := FigureLookEdits.kit_problem(key, group, _context.active_rig(), bone, taken)

	if not problem.is_empty():
		_context.status(problem)
		return

	_context.history().commit(FigureStore.KIND_LOOK, key, {},
		FigureLookEdits.new_kit_part(key, group, _context.active_rig(), bone,
			bench.store.palette()),
		"new kit part %s in the kit group %s" % [key, group])
	_context.dock().body_panel().edit_kit(key)
	bench.set_kit_part(group, key)
	_context.refresh_panels()


## "Remove the kit part that the part editor shows". An undo brings it back.
func _on_kit_removed(key: String) -> void:
	if _context.bench() == null or key.is_empty():
		_context.status("The part editor shows the body. Select a kit part first.")
		return

	_gear.on_look_removed(key)
