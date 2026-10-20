@tool
class_name FigurePartHandlers
extends RefCounted
## The handlers of the part editor ([PartEditor]): a part, its place, its
## fit, and its shapes.
##
## The Body tab, the Families tab, and the Gear dock hold the same part
## editor. Each one edits one worn look: the body of the selected body
## type, the row of the selected family, or the look of the selected row
## of the Gear dock. Thus, [method connect_panel] binds `look_of` to each
## handler, and the handler gets it after the arguments of its signal.
## `look_of` gives the key of the worn look that the editor shows now.

var _context: FigureHandlerContext


func _init(context: FigureHandlerContext) -> void:
	_context = context


## Connect one part editor. `look_of` gives the key of the worn look that
## the editor shows now. Each handler gets it after the arguments of its
## signal.
func connect_panel(panel: PartEditor, look_of: Callable) -> void:
	panel.part_chosen.connect(_on_part_chosen.bind(look_of))
	panel.shape_chosen.connect(_on_shape_chosen.bind(look_of))
	panel.part_requested.connect(_on_part_requested.bind(panel, look_of))
	panel.part_removed.connect(_on_part_removed.bind(look_of))
	panel.part_copied.connect(_on_part_copied.bind(panel, look_of))
	panel.part_mirrored.connect(_on_part_mirrored.bind(panel, look_of))
	panel.shape_copied.connect(_on_shape_copied.bind(panel, look_of))
	panel.part_renamed.connect(_on_part_renamed.bind(panel, look_of))
	panel.part_bone_changed.connect(_on_part_bone_changed.bind(look_of))
	panel.part_region_changed.connect(_on_part_region_changed.bind(look_of))
	panel.part_placed.connect(_on_part_placed.bind(look_of))
	panel.part_fit_changed.connect(_on_part_fit_changed.bind(look_of))
	panel.fit_requested.connect(_on_fit_requested.bind(look_of))
	panel.shape_requested.connect(_on_shape_requested.bind(look_of))
	panel.shape_removed.connect(_on_shape_removed.bind(look_of))
	panel.shape_edited.connect(_on_shape_edited.bind(look_of))
	panel.part_model_import_requested.connect(_on_part_model_import.bind(look_of))
	panel.part_model_requested.connect(_on_part_model_requested.bind(look_of))
	panel.part_model_cleared.connect(_on_part_model_cleared.bind(look_of))


# ─── The model of one part (DESIGN-0014 section 20) ─────────────────────────

## "Import model for part": run the model pipeline on the file, on the job
## of the plugin. When it ends, the selected part takes a node of the built
## model, and each other part stays. The model is in the `figure` family,
## or in `items` when its key is an item.
func _on_part_model_import(part_name: String, model_key: String, path: String,
		look_of: Callable) -> void:
	var bench := _context.bench()
	var problem := FigurePartEdits.NO_PART if part_name.is_empty() \
		else FigureGearHandlers.import_problem(bench, model_key)

	if bench == null or not problem.is_empty():
		_context.status(problem)
		return

	var look_key: String = look_of.call()
	var author := _context.dock().saved_author()

	_context.start_job(FigureGearHandlers.JOB_MODEL % model_key,
		FigurePipeline.import_model.bind(FigureGearHandlers.model_family(bench, model_key),
			model_key, path, author),
		func(result: Dictionary) -> void:
			if not result["ok"]:
				_context.status(FigureGearHandlers.import_failure(path, result))
				return

			_give_part_model(look_key, part_name, model_key))


## "Part from served model": the selected part takes a node of a model that
## the served tree has already.
func _on_part_model_requested(part_name: String, model_key: String,
		look_of: Callable) -> void:
	_give_part_model(look_of.call(), part_name, model_key)


func _on_part_model_cleared(part_name: String, look_of: Callable) -> void:
	_change_look(look_of.call(), "take the model away from the part " + part_name,
		func(look: Dictionary) -> String:
			return FigurePartEdits.clear_part_model(look, part_name))


## Give one part of one look a node of a served model, as one undo entry.
## The place comes from the rig of the look: the selected body type.
func _give_part_model(look_key: String, part_name: String, model_key: String) -> void:
	var bench := _context.bench()

	if bench == null:
		return

	bench.reload_models()

	var rig := _rig_of_look(look_key)

	_change_look(look_key, "give the part %s the model %s" % [part_name, model_key],
		func(look: Dictionary) -> String:
			return FigurePartEdits.part_from_model(look, rig, part_name, model_key,
				bench.models))


func _on_part_chosen(part_name: String, look_of: Callable) -> void:
	_context.select_part(look_of.call(), part_name)


## A shape row of the tree: the Godot tools then move that shape.
func _on_shape_chosen(part_name: String, shape_index: int, look_of: Callable) -> void:
	_context.select_shape(look_of.call(), part_name, shape_index)


func _on_part_requested(bone: String, panel: PartEditor, look_of: Callable) -> void:
	var made := PackedStringArray()
	var rig := _rig_of_look(look_of.call())

	_change_look(look_of.call(), "add a part on " + bone, func(look: Dictionary) -> String:
		if rig == null or not rig.has_bone(bone):
			return "Select the bone of the new part first."

		made.append(FigurePartEdits.add_part(look, rig, bone))
		return "")

	if not made.is_empty():
		panel.select_part(made[0])
		_context.select_part(look_of.call(), made[0])


func _on_part_removed(part_name: String, look_of: Callable) -> void:
	_change_look(look_of.call(), "remove the part " + part_name,
		func(look: Dictionary) -> String:
			return FigurePartEdits.remove_part(look, part_name))


## "Copy the selected part": a second part at the same place, selected.
func _on_part_copied(part_name: String, panel: PartEditor, look_of: Callable) -> void:
	var made := PackedStringArray()

	_change_look(look_of.call(), "copy the part " + part_name, func(look: Dictionary) -> String:
		made.append(FigurePartEdits.duplicate_part(look, part_name))
		return "" if not made[0].is_empty() else FigurePartEdits.NO_PART)

	if not made.is_empty() and not made[0].is_empty():
		panel.select_part(made[0])
		_context.select_part(look_of.call(), made[0])


## "Make the part of the other side": the mirror picture of a part, on the
## bone of the other side.
func _on_part_mirrored(part_name: String, panel: PartEditor,
		look_of: Callable) -> void:
	var made := PackedStringArray()

	var rig := _rig_of_look(look_of.call())

	_change_look(look_of.call(), "make the other side of the part " + part_name,
		func(look: Dictionary) -> String:
			var problem := FigurePartEdits.mirror_problem(look, part_name, rig)

			if problem.is_empty():
				made.append(FigurePartEdits.mirror_part(look, part_name, rig))

			return problem)

	if not made.is_empty():
		panel.select_part(made[0])
		_context.select_part(look_of.call(), made[0])


func _on_shape_copied(part_name: String, shape_index: int, panel: PartEditor,
		look_of: Callable) -> void:
	var made := PackedInt32Array()

	_change_look(look_of.call(), "copy a shape of the part " + part_name,
		func(look: Dictionary) -> String:
			made.append(FigureShapeEdits.duplicate_shape(look, part_name, shape_index))
			return "" if made[0] >= 0 else "Select a shape first.")

	if not made.is_empty():
		panel.select_shape(made[0])


func _on_part_renamed(part_name: String, new_name: String, panel: PartEditor,
		look_of: Callable) -> void:
	if part_name == new_name:
		return

	_change_look(look_of.call(), "rename the part " + part_name,
		func(look: Dictionary) -> String:
			return FigurePartEdits.rename_part(look, part_name, new_name))
	panel.select_part(new_name)
	_context.select_part(look_of.call(), panel.selected_part())


func _on_part_bone_changed(part_name: String, bone: String, look_of: Callable) -> void:
	var rig := _rig_of_look(look_of.call())

	_change_look(look_of.call(), "put the part %s on %s" % [part_name, bone],
		func(look: Dictionary) -> String:
			return FigurePartEdits.set_part_bone(look, part_name, bone, rig,
				_context.bench().store.rigs))


func _on_part_region_changed(part_name: String, region: String, look_of: Callable) -> void:
	_change_look(look_of.call(), "set the region of the part " + part_name,
		func(look: Dictionary) -> String:
			return FigurePartEdits.set_part_region(look, part_name, region))


## The place fields of a part changed. The place goes into the fit row of
## the selected body type when the part has one.
func _on_part_placed(part_name: String, xform: Transform3D, field: String,
		look_of: Callable) -> void:
	var body_key := _context.dock().active_body()
	var edit := func(look: Dictionary) -> String:
		return FigurePartEdits.set_part_place(look, part_name, xform, body_key)

	_change_look(look_of.call(), "set the %s of the part %s" % [field, part_name], edit, true)


## "Own place on this body type": give the part a fit row for the selected
## body type, or take the row away.
func _on_part_fit_changed(part_name: String, fitted: bool, look_of: Callable) -> void:
	var body_key := _context.dock().active_body()
	var label := "give the part %s its own place on %s" % [part_name, body_key]

	if not fitted:
		label = "take the place on %s from the part %s" % [body_key, part_name]

	_change_look(look_of.call(), label, func(look: Dictionary) -> String:
		return FigurePartEdits.set_part_fit(look, body_key, part_name, fitted))
	# A refused change leaves the box as the look has it.
	_context.refresh_panels()


## "Fit each part from the bone lengths": the fit of the selected body
## type, from the rig of the other body type. The look has its places for
## that other rig.
func _on_fit_requested(look_of: Callable) -> void:
	var rig: FigureRig = _context.active_rig()
	var made_on := _other_rig(rig)
	var count := [0]

	if rig == null or made_on == null:
		_context.status("A fit needs two body types. Make a second rig on the Rig tab.")
		return

	_change_look(look_of.call(), "fit the look to " + rig.key(), func(look: Dictionary) -> String:
		count[0] = FigurePartEdits.fit_to_rig(look, made_on, rig)
		return "")

	if count[0] == 0:
		_context.status("No part needs a fit: each bone of a part has the same length on %s and on %s."
			% [made_on.key(), rig.key()])
	else:
		_context.status("%d part(s) have a fit on %s, from the bone lengths of %s."
			% [count[0], rig.key(), made_on.key()])


## The rig of the first body type that is not the body type of `rig`, or
## null.
func _other_rig(rig: FigureRig) -> FigureRig:
	if rig == null:
		return null

	var bench := _context.bench()

	for body_key: String in bench.body_keys():
		if body_key != rig.key():
			return bench.store.rigs[body_key]

	return null


func _on_shape_requested(part_name: String, kind: String, look_of: Callable) -> void:
	_change_look(look_of.call(), "add a %s to the part %s" % [kind, part_name],
		func(look: Dictionary) -> String:
			if FigureShapeEdits.add_shape(look, part_name, kind) < 0:
				return FigurePartEdits.NO_PART

			return "")


func _on_shape_removed(part_name: String, shape_index: int, look_of: Callable) -> void:
	_change_look(look_of.call(), "remove a shape of the part " + part_name,
		func(look: Dictionary) -> String:
			return FigureShapeEdits.remove_shape(look, part_name, shape_index))


func _on_shape_edited(part_name: String, shape_index: int, field: String,
		value: Variant, look_of: Callable) -> void:
	var edit := func(look: Dictionary) -> String:
		return FigureShapeEdits.set_shape_value(look, part_name, shape_index, field, value)

	_change_look(look_of.call(), "set the %s of shape %d of the part %s" % [field,
		shape_index, part_name], edit, true)


## Change one worn look, as one undo entry ([method FigureHistory.change_look]).
func _change_look(look_key: String, label: String, edit: Callable, merge := false) -> void:
	_context.history().change_look(look_key, label, edit, merge)


## The rig that one look key draws on: the one-bone rig of the family
## stand for a family key, else the rig of the selected body type.
func _rig_of_look(look_key: String) -> FigureRig:
	if FamilyLooks.family_of_key(look_key).is_empty():
		return _context.active_rig()

	return FamilyLooks.stand_rig()
