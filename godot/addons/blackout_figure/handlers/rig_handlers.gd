@tool
class_name FigureRigHandlers
extends RefCounted
## The handlers of the Rig tab of the figure dock: a bone, a socket, a
## region, a slot, and a new rig. Each change goes through
## [FigureRigEdits] and the undo seam ([FigureHistory]).

var _context: FigureHandlerContext


func _init(context: FigureHandlerContext) -> void:
	_context = context


func connect_panel(panel: FigureRigPanel) -> void:
	panel.bone_chosen.connect(on_bone_chosen)
	panel.bone_moved.connect(_on_bone_moved)
	panel.bone_turned.connect(_on_bone_turned)
	panel.bone_region_changed.connect(_on_bone_region_changed)
	panel.region_requested.connect(_on_region_requested)
	panel.region_removed.connect(_on_region_removed)
	panel.socket_requested.connect(_on_socket_requested)
	panel.socket_removed.connect(_on_socket_removed)
	panel.slot_changed.connect(_on_slot_changed)
	panel.new_rig_requested.connect(_on_new_rig)


## A selected bone gets its mark on each stand. The plugin then selects the
## mark of the selected body type. The Godot move tool moves that mark.
## [method FigureWorkbench.sync_from_nodes] writes the move into the rig,
## as it writes a part move into a look.
func on_bone_chosen(bone_name: String) -> void:
	var bench := _context.bench()

	if bench == null:
		return

	bench.mark_bone(bone_name)

	var mark := bench.mark_node(_context.dock().active_body())

	if mark != null and mark.visible:
		_context.select_node(mark)


## One drag of a field is one entry. The label names the field: a merged
## entry joins the entries with one name, and a drag of x and then a drag
## of y must stay two.
func _on_bone_moved(bone_name: String, position: Vector3, mirror := false,
		axis := "") -> void:
	var edit := func(rig: Dictionary) -> String:
		return FigureRigEdits.set_bone_position(rig, bone_name, position, mirror)

	_context.history().change(FigureStore.KIND_RIG, _context.dock().active_body(),
		"move the bone %s on %s" % [bone_name, axis], edit, true)


## A socket got a rest rotation. One drag of a field is one entry.
func _on_bone_turned(bone_name: String, rotation: Quaternion, axis := "") -> void:
	var edit := func(rig: Dictionary) -> String:
		return FigureRigEdits.set_bone_rotation(rig, bone_name, rotation)

	_context.history().change(FigureStore.KIND_RIG, _context.dock().active_body(),
		"turn the socket %s on %s" % [bone_name, axis], edit, true)
	# A refused change leaves the fields as the rig has them.
	_context.figure_dock().rig_panel().set_rig(_context.active_rig())
	_context.figure_dock().rig_panel().select_bone(bone_name)


func _on_bone_region_changed(bone_name: String, region: String) -> void:
	_context.history().change(FigureStore.KIND_RIG, _context.dock().active_body(),
		"put the bone %s in %s" % [bone_name, "no region" if region.is_empty() else region],
		func(rig: Dictionary) -> String:
			return FigureRigEdits.set_bone_region(rig, bone_name, region))
	_context.figure_dock().rig_panel().select_bone(bone_name)


func _on_region_requested(region: String) -> void:
	_context.history().change(FigureStore.KIND_RIG, _context.dock().active_body(),
		"add the region " + region, func(rig: Dictionary) -> String:
			return FigureRigEdits.add_region(rig, region))


## "Remove the region of the selected bone". A region that a look names
## stays, and the status box names each such look.
func _on_region_removed(region: String) -> void:
	if region.is_empty():
		_context.status("Select a bone of the region first.")
		return

	_context.history().change(FigureStore.KIND_RIG, _context.dock().active_body(),
		"remove the region " + region, func(rig: Dictionary) -> String:
			return FigureRigEdits.remove_region(rig, region,
				FigureRigEdits.looks_in_region(_context.bench().store.looks, region)))


func _on_socket_requested(socket: String, parent: String) -> void:
	_context.history().change(FigureStore.KIND_RIG, _context.dock().active_body(),
		"add the socket " + socket, func(rig: Dictionary) -> String:
			return FigureRigEdits.add_socket(rig, socket, parent))
	_context.figure_dock().rig_panel().select_bone(socket)
	on_bone_chosen(_context.figure_dock().rig_panel().selected_bone())


## "Remove the selected socket". A socket that carries a part of a look
## stays: the part would draw nothing.
func _on_socket_removed(socket: String) -> void:
	_context.history().change(FigureStore.KIND_RIG, _context.dock().active_body(),
		"remove the socket " + socket, func(rig: Dictionary) -> String:
			var users := FigureRigEdits.looks_on_bone(_context.bench().store.looks, socket)

			if not users.is_empty():
				return "%d look(s) have a part on %s: %s. Put each part on another bone first." \
					% [users.size(), socket, ", ".join(users)]

			return FigureRigEdits.remove_socket(rig, socket))


func _on_slot_changed(slot: String, bone: String) -> void:
	_context.history().change(FigureStore.KIND_RIG, _context.dock().active_body(),
		"set the bone of the slot " + slot, func(rig: Dictionary) -> String:
			return FigureRigEdits.set_slot_bone(rig, slot, bone))


## "New rig from the humanoid profile". An undo removes the rig again.
func _on_new_rig(key: String, limb_scale: float) -> void:
	var bench := _context.bench()

	if bench == null:
		return

	var problem := FigureRigEdits.name_problem(key)

	if problem.is_empty() and bench.store.has(FigureStore.KIND_RIG, key):
		problem = "A rig with the key %s exists." % key

	if not problem.is_empty():
		_context.status(problem)
		return

	_context.history().commit(FigureStore.KIND_RIG, key, {},
		FigureRigEdits.rig_from_profile(key, limb_scale).data, "new rig " + key)
	_context.dock().select_body(key)
	_context.refresh_panels()
