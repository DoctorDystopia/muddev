@tool
extends EditorPlugin
## The Blackout terrain editor: routes the mouse in the 3D viewport to the
## brushes, each stroke to the editor history, and each dock button to the
## [TerrainWorld].
##
## DESIGN-0011 section 6.3. Select a [TerrainWorld] node, for example in
## `res://addons/blackout_terrain/terrain_editor.tscn`, to start. The panel
## is [TerrainDock]. The rules live in [TerrainBrushes], [TerrainEdit],
## [TerrainChecks], and [ChunkSet], and the `tests/test_terrain_*.tscn`
## scenes test them with no editor. This script only decides which rule a
## click calls.
##
## ## One stroke, one undo entry
##
## A press starts a [TerrainEdit]. Each dab adds to it. The release puts it in
## the history as one entry, so Ctrl+Z undoes the whole stroke.
##
## ## A move of the block clears the undo history
##
## A move to another block saves the old block, so an undo there would change
## a file that is no longer loaded. Thus, each load of a block clears the
## history of the edited scene. [method TerrainWorld.replay_edit] also
## refuses an edit of another block. With unsaved chunks, the plugin asks
## before the move, and the status names the files that the move saved.
##
## A change of the plane keeps the history (DESIGN-0013 Phase S0). The block
## holds every plane, and an edit keys on (plane, tile). Thus an undo writes
## into the plane of its edit.
##
## ## The keys of every tab
##
## Page Up and Page Down change the plane. V toggles "Walls down". The
## bracket keys step the radius of the Paint brush, or the pitch and the
## brush of the Build tools. The number keys pick a tool of the tab that
## shows. Esc drops a drag, a half-made ramp, and the selection. The hint
## line at the bottom of the 3D view names the tool and its keys on every
## tab.
##
## ## The Build tab
##
## While the Build tab shows, every event of the 3D view goes to
## [BuildInput] (DESIGN-0013 section 6.7).
##
## ## Protect structures
##
## With "Protect structures" on, a sculpt, a ramp, and a noise fill skip
## each corner of a tile with a wall or with a floor above it
## ([method TerrainBrushes.protect]).
##
## ## The structure workbench
##
## `structure_workbench.tscn` is the terrain editor on a scratch chunk
## directory (DESIGN-0013 Phase S6). The author builds a template there, and
## saves it from the Build tab as in the world. The dock names the scene,
## and "Check world" leaves out the rules of a whole world
## ([constant TerrainChecks.WORLD_RULES]). One button opens the other scene.
## One button deletes the scratch files after a confirmation that counts
## them.
##
## ## Saving
##
## Ctrl+S saves the scene, and the editor then calls
## [method _save_external_data], which writes every changed chunk file. The
## editor also asks about unsaved chunks when it closes. Revert reads the
## chunk files again after a confirmation that counts the unsaved chunks.
##
## ## The Tables tab
##
## [TableEdits] owns the rules of a row change (Nick, 10/14/2026). A rename
## and a removal ask first. A rename saves the unsaved chunks, rewrites the
## files that name the key, and reads the block again. After each change,
## every list reads [TileTables] again, the block draws again, and
## [ClientExport] runs on a thread. The status box gives the result.

## Seconds between two dabs while a sculpt button is held still.
const DAB_INTERVAL := 0.12

## Tiles the mouse must move before a drag makes a new dab.
const DAB_SPACING := 0.35

const _Const := preload("res://autoload/blackout_constants.gd")

## The ring of the Select tool, in tiles.
const SELECT_RING := 0.5

## The two scenes of the terrain editor: the world, and the structure
## workbench.
const EDITOR_SCENE := "res://addons/blackout_terrain/terrain_editor.tscn"
const WORKBENCH_SCENE := "res://addons/blackout_terrain/structure_workbench.tscn"

## The number keys, in the order of the tools of a tab.
const TOOL_KEYS := [KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9, KEY_0]

var _dock: TerrainDock
var _world: TerrainWorld

## The last world that the plugin edited. Godot gives [method _edit] null
## when the author selects another node, for example the sun. Ctrl+S and
## the close prompt must still reach the unsaved chunks of that world.
var _last_world: TerrainWorld
var _stroke: TerrainEdit
var _stroking := false
var _shift := false
var _last_point := Vector2.ZERO
var _since_dab := 0.0
var _flatten_target := 0

## The ramp start in tile space, or null before the first click.
var _ramp_start: Variant = null
var _ramp_start_height := 0

## The Select tool drags the selected object from this tile, or null.
var _drag_from: Variant = null

## The mouse and the keys of the Build tab.
var _build: BuildInput

## The last mouse position in the 3D view, for the size readout.
var _mouse := Vector2.ZERO

## The rules of the Tables tab.
var _edits := TableEdits.new()

## The client export after a change on the Tables tab, on a thread. A
## change while it runs asks for one more run after it.
var _export := FigureJob.new()
var _export_again := false

## The report of the last change of a table, for the status box.
var _table_report := ""


func _enter_tree() -> void:
	_dock = TerrainDock.new()
	_dock.load_requested.connect(_on_load_requested)
	_dock.plane_requested.connect(_on_plane_requested)
	_dock.block_side_requested.connect(_on_block_side_requested)
	_dock.tile_requested.connect(_on_tile_requested)
	_dock.save_requested.connect(_on_save_requested)
	_dock.revert_requested.connect(_on_revert_requested)
	_dock.noise_fill_requested.connect(_on_noise_fill_requested)
	_dock.overlays_changed.connect(_on_overlays_changed)
	_dock.selection_action.connect(_on_selection_action)
	_dock.selection_edited.connect(_on_selection_edited)
	_dock.object_chosen.connect(_on_object_chosen)
	_dock.check_requested.connect(_on_check_requested)
	_dock.finding_chosen.connect(_on_finding_chosen)
	_dock.tab_changed.connect(_on_tab_changed)
	_dock.tool_changed.connect(update_overlays)
	_dock.clear_workbench_asked.connect(_on_clear_workbench_asked)
	_dock.switch_scene_requested.connect(_on_switch_scene)
	_connect_look_panel()
	_connect_tables_panel()
	_build = BuildInput.new()
	_build.panel = _dock.build_panel()
	_build.commit = _commit
	_build.panel.changed.connect(_build.on_panel_changed)
	_build.panel.changed.connect(update_overlays)
	_build.panel.walls_down_toggled.connect(_on_walls_down_toggled)
	_build.panel.save_template_requested.connect(_on_save_template)
	_build.panel.reload_templates_requested.connect(_on_reload_templates)
	add_control_to_dock(DOCK_SLOT_RIGHT_UL, _dock)
	set_process(true)


func _exit_tree() -> void:
	_export.wait()
	remove_control_from_docks(_dock)
	_dock.queue_free()


func _handles(object: Object) -> bool:
	return object is TerrainWorld


func _edit(object: Object) -> void:
	if _world != null and _world.block_loaded.is_connected(_on_block_loaded):
		_world.block_loaded.disconnect(_on_block_loaded)
		_world.plane_changed.disconnect(_on_plane_changed)

	_world = object as TerrainWorld

	if _world == null:
		return

	_last_world = _world
	_world.block_loaded.connect(_on_block_loaded)
	_world.plane_changed.connect(_on_plane_changed)
	_dock.variants_for = _world.variants_for
	_dock.refresh_tables()
	_dock.refresh_items()
	_build.world = _world
	_world.block_side = _dock.block_side()
	_dock.set_workbench(not _world.writes_world())
	_on_overlays_changed()
	_refresh_dock()
	_report_block()


# ─── Saving and loading ─────────────────────────────────────────────────────

func _save_external_data() -> void:
	if is_instance_valid(_last_world) and _last_world.has_unsaved_changes():
		_save(_last_world)


## Godot calls this before each save of a scene, and before a run of the
## game. The preview of an area look writes into the sky and the sun of the
## scene, so it ends here. The save then stores the own sky of the scene.
## The preview starts again on the next frame, after the save (10/14/2026).
func _apply_changes() -> void:
	if not is_instance_valid(_last_world) or not _last_world.previewing():
		return

	var look := _last_world.previewed_look()

	_last_world.preview_look({})
	_resume_preview.call_deferred(_last_world, look)


## Start the preview again after a save, when the box is still on.
func _resume_preview(world: TerrainWorld, look: Dictionary) -> void:
	if is_instance_valid(world) and not world.previewing() \
			and _dock.look_panel().preview_on():
		world.preview_look(look)


func _get_unsaved_status(_for_scene: String) -> String:
	if not is_instance_valid(_last_world) or not _last_world.has_unsaved_changes():
		return ""

	return "The terrain has unsaved chunk changes. Save them?"


func _on_save_requested() -> void:
	if _world != null:
		_dock.set_status(_save(_world))


## Write the changed chunks of `world`. Returns the status line: each file
## that did not write first, then the files that it wrote.
func _save(world: TerrainWorld) -> String:
	var saved := world.save_block()
	var lines := PackedStringArray()

	if not world.save_errors.is_empty():
		lines.append("COULD NOT WRITE %d chunk file(s): %s. They stay unsaved." % [
			world.save_errors.size(), ", ".join(world.save_errors)])

	lines.append("Saved %d chunk file(s): %s" % [saved.size(), ", ".join(saved)])

	if world == _world:
		_refresh_dock()

	return "\n".join(lines)


## "Revert": read the chunk files again. With unsaved chunks, it asks first
## and counts them.
func _on_revert_requested() -> void:
	if _world == null:
		return

	var count := _world.unsaved_count()

	if count == 0:
		_world.load_block()
		return

	_dock.confirm("Read the chunk files again and drop %d unsaved chunk file(s)? " % count
		+ "Undo cannot bring them back.", _world.load_block)


## "Load", and the pan buttons.
func _on_load_requested(centre: Vector2i, plane: int) -> void:
	if _world != null:
		_move_block(centre, plane, "")


## The plane field of the block strip.
func _on_plane_requested(plane: int) -> void:
	if _world != null:
		_world.plane = plane


## The Side field of the block strip. The same rule as [method _move_block]
## for the dialog: a new side loads the block again and drops the undo
## history. A No puts the old side back in the field.
func _on_block_side_requested(side: int) -> void:
	if _world == null:
		return

	if not _world.has_unsaved_changes():
		_world.block_side = side
		return

	var count := _world.unsaved_count()
	var keep := func() -> void:
		_dock.set_block(_world.centre_chunk, _world.plane, _world.block_side)

	_dock.confirm("Save %d changed chunk file(s) and drop the undo history? " % count
		+ "Undo cannot cross a change of the block side.", func() -> void:
			var saved := _save(_world)

			_world.block_side = side
			_dock.set_status(saved), keep)


## "Go to tile".
func _on_tile_requested(tile: Vector2i) -> void:
	if _world != null:
		_jump(tile, _world.plane, "Went to tile %s." % tile)


## Move the block to `centre` and `plane`. A move to another centre saves
## the old block and drops the undo history, so it asks first when a chunk
## is unsaved. `then` is the status line after the move.
func _move_block(centre: Vector2i, plane: int, then: String) -> void:
	if centre == _world.centre_chunk or not _world.has_unsaved_changes():
		_world.move_block(centre, plane)
		_dock.set_status(then)
		return

	var count := _world.unsaved_count()

	_dock.confirm("Save %d changed chunk file(s) and drop the undo history? " % count
		+ "Undo cannot cross a block move.", func() -> void:
			var saved := _save(_world)

			_world.move_block(centre, plane)
			_dock.set_status(then + "\n" + saved))


## Load the block of `tile` on `plane`, and put the beacon on it. The same
## rule as [method _move_block] for the dialog.
func _jump(tile: Vector2i, plane: int, then: String) -> void:
	if _world.block_has_tile(tile) or not _world.has_unsaved_changes():
		_world.jump_to(tile, plane)
		_refresh_dock()
		_dock.set_status(then)
		return

	var count := _world.unsaved_count()

	_dock.confirm("Save %d changed chunk file(s) and drop the undo history? " % count
		+ "The tile is in another block.", func() -> void:
			var saved := _save(_world)

			_world.jump_to(tile, plane)
			_refresh_dock()
			_dock.set_status(then + "\n" + saved))


## Every load of a block: a move, or a jump or a link to another block. A
## ramp started in the old block ends here: its start corner is not loaded.
func _on_block_loaded() -> void:
	var history := get_undo_redo()

	history.clear_history(history.get_object_history_id(_world))
	_ramp_start = null
	_refresh_dock()
	_report_block()


## A change of the edited plane in the same block. The history stays.
func _on_plane_changed() -> void:
	_refresh_dock()
	_report_block()
	update_overlays()


func _on_overlays_changed() -> void:
	if _world == null:
		return

	_world.show_flags = _dock.show_flags()
	_world.show_areas = _dock.show_areas()
	_world.show_links = _dock.show_links()
	_world.show_lower_planes = _dock.show_lower_planes()
	_world.upper_planes = _dock.upper_planes() as TerrainWorld.UpperPlanes
	_world.walls_down = _dock.build_panel().walls_down()


func _on_walls_down_toggled(down: bool) -> void:
	if _world != null:
		_world.walls_down = down


## "Save as template" on the Build tab. A key that a template has asks
## first: the old file goes, and undo cannot bring it back.
func _on_save_template(template_key: String) -> void:
	if _world == null:
		return

	if not _build.template_exists(template_key):
		_save_template(template_key)
		return

	_dock.confirm("Replace the template %s? The old file goes, and undo cannot bring "
		% template_key + "it back.", _save_template.bind(template_key))


func _save_template(template_key: String) -> void:
	_dock.set_status(_build.save_template(template_key))
	update_overlays()


func _on_reload_templates() -> void:
	_build.reload_templates()
	_dock.set_status("Read the template directory again.")
	update_overlays()


## Leaving the Build tab drops its drag, its marks, its outline, and its
## hint line. The cancel draws the Place lattice again from the last hover,
## so the outline goes after it.
func _on_tab_changed() -> void:
	if _world != null and _build.world != null:
		_build.cancel()
		_world.show_marks([], Color.WHITE)
		_world.show_outline_layers([], Color.WHITE)

	update_overlays()


## The block report of the World tab: the scene, the load errors, and the
## seam faults. The status box gets one line, so the next stroke replaces
## only that line.
func _report_block() -> void:
	var lines := PackedStringArray(["Block of %d x %d chunks around chunk %s, plane %d."
		% [_world.block_side, _world.block_side, _world.centre_chunk, _world.plane]])

	if not _world.writes_world():
		lines.insert(0, "The structure workbench: scratch chunk files in %s. "
			% _world.directory() + "Nothing here reaches the world. Save a template "
			+ "from the Build tab.")

	lines.append_array(_world.load_errors)

	for mismatch: String in _world.chunks.seam_mismatches():
		lines.append("Seam: " + mismatch)

	var faults := _world.load_errors.size() + _world.chunks.seam_mismatches().size()

	_dock.set_block_report(lines, faults > 0)
	_dock.set_status(lines[0] if faults == 0 else "%s %d fault(s): see Block on the World tab."
		% [lines[0], faults])


## The block, the objects, the selection, the unsaved count, and the sync
## state in the dock.
func _refresh_dock() -> void:
	_dock.set_block(_world.centre_chunk, _world.plane, _world.block_side)
	_dock.set_objects(_world.objects_in_block())
	_dock.set_selection(_world.selected, _world.selected_link_end())
	_dock.set_unsaved(_world.unsaved_count())
	_refresh_sync_state()


func _refresh_sync_state() -> void:
	if not _world.writes_world():
		_dock.set_sync_state("A scratch directory: no tile sync applies.")
		return

	_dock.set_sync_state(TerrainSyncState.describe(_world.directory(),
		TerrainSyncState.stamp_path()))


# ─── The mouse and the keys ─────────────────────────────────────────────────

func _forward_3d_gui_input(camera: Camera3D, event: InputEvent) -> int:
	if _world == null:
		return AFTER_GUI_INPUT_PASS

	if event is InputEventKey:
		if _on_key(camera, event):
			return AFTER_GUI_INPUT_STOP

		return AFTER_GUI_INPUT_PASS

	if _dock.build_active():
		return _build_event(camera, event)

	if event is InputEventMouseMotion:
		return _on_motion(camera, event)

	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		return _on_left_button(camera, event)

	return AFTER_GUI_INPUT_PASS


## A key in the 3D view, on every tab. The Build tools read a key first
## while their tab shows. Returns true when a key is used.
func _on_key(camera: Camera3D, event: InputEventKey) -> bool:
	if not event.pressed or event.echo:
		return false

	var used := _dock.build_active() and _build.on_key(event)

	if not used:
		used = _on_global_key(event)

	if used:
		_mark_key_handled(camera)
		update_overlays()

	return used


## The keys of every tab. Returns true when a key is used.
func _on_global_key(event: InputEventKey) -> bool:
	var tool_index := TOOL_KEYS.find(event.keycode)

	if tool_index >= 0:
		_pick_tool(tool_index)
		return true

	match event.keycode:
		KEY_PAGEUP:
			_world.plane = _world.plane + 1
		KEY_PAGEDOWN:
			_world.plane = _world.plane - 1
		KEY_V:
			_build.panel.set_walls_down(not _build.panel.walls_down())
		KEY_BRACKETLEFT:
			_dock.step_radius(-1)
		KEY_BRACKETRIGHT:
			_dock.step_radius(1)
		KEY_ESCAPE:
			_cancel()
		_:
			return false

	return true


## A number key: the tool of the tab that shows.
func _pick_tool(tool_index: int) -> void:
	if _dock.build_active():
		_build.panel.pick_tool(tool_index)
	else:
		_dock.pick_tool(tool_index)


## Esc on the Paint tab: the half-made ramp, the drag, and the selection go.
func _cancel() -> void:
	_ramp_start = null
	_drag_from = null

	if _stroking:
		_end_stroke()

	_world.clear_selection()
	_refresh_dock()


## One event of the 3D view while the Build tab shows.
func _build_event(camera: Camera3D, event: InputEvent) -> int:
	var used := false

	if event is InputEventMouseMotion:
		_mouse = event.position
		_world.show_ring(null, 0.0)
		used = _build.on_motion(_pick(camera, event.position), event.shift_pressed,
			event.alt_pressed)
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			var wall: Variant = _pick_wall(camera, event.position) \
				if event.alt_pressed else null

			used = _build.on_press(_pick(camera, event.position), event.shift_pressed,
				event.alt_pressed, wall, event.is_command_or_control_pressed())
		else:
			used = _build.on_release()
	else:
		return AFTER_GUI_INPUT_PASS

	update_overlays()

	return AFTER_GUI_INPUT_STOP if used else AFTER_GUI_INPUT_PASS


## Stop a key that a tool used. AFTER_GUI_INPUT_STOP stops only the 3D
## view. The editor shortcuts still read the key: Page Down is "Snap Object
## to Floor", and R is the Scale mode. The 3D view sits in a SubViewport.
## Thus, the key belongs to the window around its container.
func _mark_key_handled(camera: Camera3D) -> void:
	var container := camera.get_viewport().get_parent() as Node

	if container == null:
		return

	var window := container.get_viewport()

	if window != null:
		window.set_input_as_handled()


## The hint line on every tab: the Build hint with its readout, or the
## Paint hint.
func _forward_3d_draw_over_viewport(overlay: Control) -> void:
	if _world == null:
		return

	if _dock.build_active():
		ToolHint.draw(overlay, _build.hint(), _build.readout(), _mouse)
	else:
		ToolHint.draw(overlay, _dock.paint_hint(_world.plane), _ramp_readout(), _mouse)


## The readout of a half-made ramp, beside the cursor.
func _ramp_readout() -> String:
	if _ramp_start == null:
		return ""

	return "ramp from %s, height %d" % [_ramp_start, _ramp_start_height]


## The point in tile space under the mouse, or null.
func _pick(camera: Camera3D, screen: Vector2) -> Variant:
	var origin := camera.project_ray_origin(screen)
	var direction := camera.project_ray_normal(screen)
	var hit: Variant = TerrainPicking.ray_hit(_world.chunks, origin, direction)

	if hit == null:
		return null

	return TerrainPicking.tile_point(hit)


## The tile of the wall slab under the mouse, or null. Alt and a click
## sample the wall style from it.
func _pick_wall(camera: Camera3D, screen: Vector2) -> Variant:
	var origin := camera.project_ray_origin(screen)
	var direction := camera.project_ray_normal(screen)

	return TerrainPicking.wall_hit(_world.chunks, origin, direction,
		_world.chunks_on(_world.plane + 1), _world.walls_down)


func _on_motion(camera: Camera3D, event: InputEventMouseMotion) -> int:
	var point: Variant = _pick(camera, event.position)

	_mouse = event.position
	update_overlays()

	if _dock.current_tool() == TerrainDock.Tool.SELECT:
		var ring: Variant = null if point == null else Vector2(ChunkSet.tile_at(point))

		_world.show_ring(ring, SELECT_RING)
		return AFTER_GUI_INPUT_STOP if _drag_from != null else AFTER_GUI_INPUT_PASS

	_world.show_ring(point, _dock.radius(), _dock.brush_shape())

	if not _stroking or point == null:
		return AFTER_GUI_INPUT_PASS

	if point.distance_to(_last_point) >= DAB_SPACING:
		_dab(point)

	return AFTER_GUI_INPUT_STOP


func _on_left_button(camera: Camera3D, event: InputEventMouseButton) -> int:
	var point: Variant = _pick(camera, event.position)

	if not event.pressed:
		return _on_release(point)

	if point == null:
		return AFTER_GUI_INPUT_PASS

	_shift = event.shift_pressed

	# A press with another tool ends a half-made ramp. Its start would
	# otherwise wait for a second click, maybe hours later.
	if _dock.current_tool() != TerrainDock.Tool.RAMP:
		_ramp_start = null

	match _dock.current_tool():
		TerrainDock.Tool.RAMP:
			_ramp_click(point)
		TerrainDock.Tool.OBJECT:
			_object_click(point)
		TerrainDock.Tool.SELECT:
			_select_press(ChunkSet.tile_at(point))
		_:
			_start_stroke(point)

	return AFTER_GUI_INPUT_STOP


func _on_release(point: Variant) -> int:
	if _drag_from != null:
		_end_drag(point)
		return AFTER_GUI_INPUT_STOP

	if _stroking:
		_end_stroke()
		return AFTER_GUI_INPUT_STOP

	return AFTER_GUI_INPUT_PASS


func _process(delta: float) -> void:
	if _export.is_done():
		_export.finish()

	if not _stroking or not (_dock.current_tool() in TerrainDock.SCULPT_TOOLS):
		return

	_since_dab += delta

	if _since_dab >= DAB_INTERVAL:
		_dab(_last_point)


# ─── Strokes ────────────────────────────────────────────────────────────────

func _start_stroke(point: Vector2) -> void:
	if not _paint_value_ready():
		return

	_stroke = TerrainEdit.for_world(_world)
	_stroking = true
	_flatten_target = _world.chunks.get_corner(StructureTools.corner_at(point))
	_dab(point)


## True when the Floor brush and the Area brush have a value to paint. With
## "(keep)" chosen, they paint nothing, and the status says so.
func _paint_value_ready() -> bool:
	var tool_index := _dock.current_tool()

	if tool_index == TerrainDock.Tool.FLOOR and _dock.floor_name().is_empty() \
			or tool_index == TerrainDock.Tool.AREA and _dock.area_name().is_empty():
		if _shift:
			return true

		_dock.set_status(TerrainDock.KEEP_HINT % _dock.tool_name())
		return false

	return true


func _end_stroke() -> void:
	_stroking = false
	_commit(_stroke, _dock.tool_name())
	_stroke = null


## Put one finished edit in the editor history. It is already applied, so
## the history must not apply it again. The findings list of the World tab
## can then be old, and its label says so.
func _commit(edit: TerrainEdit, label: String) -> void:
	if edit == null or edit.is_empty():
		return

	var history := get_undo_redo()

	history.create_action("Terrain: " + label, UndoRedo.MERGE_DISABLE, _world)
	history.add_do_method(_world, "replay_edit", edit, true)
	history.add_undo_method(_world, "replay_edit", edit, false)
	history.add_do_method(self, "_refresh_dock")
	history.add_undo_method(self, "_refresh_dock")
	history.commit_action(false)
	_dock.set_status("%s: %d change(s)." % [label, edit.size()])
	_dock.mark_findings_stale()
	_refresh_dock()


func _dab(point: Vector2) -> void:
	_last_point = point
	_since_dab = 0.0

	var chunks := _world.chunks
	var tool_index := _dock.current_tool()

	if tool_index in TerrainDock.SCULPT_TOOLS:
		_stroke.apply_heights(chunks, _protected(_sculpt(tool_index, point)))
	else:
		_paint(tool_index, point)

	_world.queue_rebuild(_stroke.chunk_keys())


## `changes` without the corners of a structure, when "Protect structures"
## is on.
func _protected(changes: Dictionary) -> Dictionary:
	if not _dock.protect_structures():
		return changes

	return TerrainBrushes.protect(changes, _world.chunks,
		_world.chunks_on(_world.plane + 1))


## The height changes of one dab of a sculpt tool.
func _sculpt(tool_index: int, point: Vector2) -> Dictionary:
	var chunks := _world.chunks
	var radius := _dock.radius()
	var shape := _dock.brush_shape()
	var strength := _dock.strength()

	match tool_index:
		TerrainDock.Tool.RAISE:
			var direction := -1 if _shift else 1

			return TerrainBrushes.raise(chunks, point, radius, direction * strength,
				shape)
		TerrainDock.Tool.LOWER:
			return TerrainBrushes.raise(chunks, point, radius, -strength, shape)
		TerrainDock.Tool.FLATTEN:
			return TerrainBrushes.flatten(chunks, point, radius, _flatten_target,
				strength, shape)
		TerrainDock.Tool.SMOOTH:
			return TerrainBrushes.smooth(chunks, point, radius, shape)
		TerrainDock.Tool.NOISE:
			return TerrainBrushes.noise_brush(chunks, point, radius,
				_dock.make_noise(), _dock.noise_amplitude(), strength, shape)

	return {}


## One dab of a paint tool: floors, flags, or areas, on each tile under the
## brush. With Shift, the floor and area tools pick the value under the
## mouse. The flag tool clears the checked flags.
func _paint(tool_index: int, point: Vector2) -> void:
	var chunks := _world.chunks
	var tiles := TerrainBrushes.tiles_in_brush(point, _dock.radius(),
		_dock.brush_shape())
	var under := ChunkSet.tile_at(point)

	if _shift and tool_index == TerrainDock.Tool.FLOOR:
		_dock.pick_floor(chunks.get_floor(under))
		return

	if _shift and tool_index == TerrainDock.Tool.AREA:
		_dock.pick_area(chunks.get_area(under))
		return

	for tile: Vector2i in tiles:
		if not chunks.has_tile(tile):
			continue

		match tool_index:
			TerrainDock.Tool.FLOOR:
				StructureTools.paint_floor(chunks, _stroke, tile, _dock.floor_name())
			TerrainDock.Tool.AREA:
				_stroke.apply_area(chunks, tile, _dock.area_name())
			TerrainDock.Tool.FLAGS:
				_stroke.apply_flags(chunks, tile, _flagged(chunks.get_flags(tile)))


func _flagged(flags: int) -> int:
	if _shift:
		return flags & ~_dock.flag_bits()

	return flags | _dock.flag_bits()


func _ramp_click(point: Vector2) -> void:
	var corner := StructureTools.corner_at(point)

	if _ramp_start == null:
		_ramp_start = TerrainBrushes.corner_point(corner)
		_ramp_start_height = _world.chunks.get_corner(corner)
		_dock.set_status("Ramp start at corner %s, height %d. Click the end."
			% [corner, _ramp_start_height])
		return

	var edit := TerrainEdit.for_world(_world)
	var end := TerrainBrushes.corner_point(corner)
	var changes := _protected(TerrainBrushes.ramp(_world.chunks, _ramp_start, end,
		_dock.radius() * 2.0, _ramp_start_height, _world.chunks.get_corner(corner)))

	edit.apply_heights(_world.chunks, changes)
	_world.queue_rebuild(edit.chunk_keys())
	_commit(edit, "Ramp")
	_ramp_start = null


## Place the chosen kind on the tile, or with Shift remove the last object
## on it.
func _object_click(point: Vector2) -> void:
	var chunks := _world.chunks
	var tile := ChunkSet.tile_at(point)
	var edit := TerrainEdit.for_world(_world)

	if not chunks.has_tile(tile):
		return

	if _shift:
		var here := chunks.objects_at(tile)

		if here.is_empty():
			return

		var last: Dictionary = here[here.size() - 1]

		edit.remove_object(chunks, tile, last["kind"], last["rotation"], last["text"],
			last["look"], last["spawn"])
	else:
		var text: Variant = _text_for(_dock.kind(), _dock.object_text())
		var spawn: Variant = _spawn_for(_dock.kind(), _dock.object_spawn())

		if text == null or spawn == null:
			return

		var look := _dock.object_look()

		edit.add_object(chunks, tile, _dock.kind(), _dock.object_rotation(), text, look,
			spawn)
		_world.select(tile, _dock.kind(), _dock.object_rotation(), text, look, spawn)

	_world.queue_rebuild(edit.chunk_keys())
	_commit(edit, "Object")


## The text that an object of `kind` gets: "" for a kind with no text, else
## `words`. Null, with a status line, when a sign would get no legal text.
## The reader refuses what [method ChunkFile.text_problem] refuses, so the
## editor never writes it.
func _text_for(kind: String, words: String) -> Variant:
	if not TerrainChecks.takes_text(kind):
		return ""

	if words.is_empty():
		_dock.set_status("A %s needs words. Type them in Sign text first." % kind)
		return null

	var problem := ChunkFile.text_problem(words)

	if not problem.is_empty():
		_dock.set_status("Sign text: " + problem)
		return null

	return words


## The spawn that an object of `kind` gets: `{}` for a kind with no spawn,
## else `spawn` (10/21/2026). Null, with a status line, when an item spawn
## would get no legal spawn. The reader refuses what
## [method ChunkFile.spawn_problem] refuses, and "Check world" refuses what
## [method _item_problem] refuses. Thus, the editor writes neither.
func _spawn_for(kind: String, spawn: Dictionary) -> Variant:
	if not TerrainChecks.takes_spawn(kind):
		return {}

	var problem := ChunkFile.spawn_problem(spawn)

	if problem.is_empty():
		problem = _item_problem(spawn)

	if not problem.is_empty():
		_dock.set_status("Item spawn: " + problem)
		return null

	return ChunkFile.normal_spawn(spawn)


## Why the item list refuses the item of `spawn`, or "". The rules of
## `spawn_item` in [TerrainChecks], with the item list of the game.
func _item_problem(spawn: Dictionary) -> String:
	var items := SpawnItems.game()
	var item: String = spawn[_Const.SPAWN_ITEM_KEY]

	if not items.error.is_empty():
		return items.error

	if not items.has(item):
		return "no item %s may spawn. Pick one in the Item list." % item

	if ChunkFile.spawn_quantity(spawn)[1] > _Const.SPAWN_QUANTITY_UNIT \
			and not items.stacks(item):
		return "%s does not stack, so its quantity must be one." % item

	return ""


func _on_noise_fill_requested() -> void:
	if _world == null:
		return

	var edit := TerrainEdit.for_world(_world)
	var changes := _protected(TerrainBrushes.noise_fill(_world.chunks, _world.centre_chunk,
		_dock.make_noise(), _dock.noise_amplitude()))

	edit.apply_heights(_world.chunks, changes)
	_world.queue_rebuild(edit.chunk_keys())
	_commit(edit, "Noise fill")


# ─── The Pick object tool ───────────────────────────────────────────────────

## Select an object on `tile`. A press on the tile of the selection picks
## the next object there, so a stack of objects can each be reached. The
## press also starts a drag of the selection.
func _select_press(tile: Vector2i) -> void:
	var here := _world.chunks.objects_at(tile)

	if here.is_empty():
		_world.clear_selection()
		_refresh_dock()
		return

	var index := 0

	if not _world.selected.is_empty() and _world.selected["tile"] == tile:
		index = (_index_on_tile(here) + 1) % here.size()

	_world.select_thing(tile, here[index])
	_drag_from = tile
	_refresh_dock()


func _index_on_tile(here: Array[Dictionary]) -> int:
	for index: int in here.size():
		if ChunkSet.same_object(here[index], _world.selected):
			return index

	return -1


## Drop the dragged object on the tile under the mouse.
func _end_drag(point: Variant) -> void:
	var from: Vector2i = _drag_from

	_drag_from = null

	if point == null or _world.selected.is_empty():
		return

	var to := ChunkSet.tile_at(point)

	if to == from or not _world.chunks.has_tile(to):
		return

	_replace_selected(to, _world.selected["kind"], _world.selected["rotation"],
		_world.selected["text"], _world.selected["look"], _world.selected["spawn"],
		"Move object")


## Replace the selected object with one at `tile` of `kind`, `rotation`,
## `text`, `look`, and `spawn`, as one undo entry, and select the new one.
func _replace_selected(tile: Vector2i, kind: String, rotation: int, text: String,
		look: Dictionary, spawn: Dictionary, label: String) -> void:
	var chunks := _world.chunks
	var edit := TerrainEdit.for_world(_world)
	var old: Dictionary = _world.selected

	edit.remove_object(chunks, old["tile"], old["kind"], old["rotation"], old["text"],
		old["look"], old["spawn"])
	edit.add_object(chunks, tile, kind, rotation, text, look, spawn)
	_world.select(tile, kind, rotation, text, look, spawn)
	_world.queue_rebuild(edit.chunk_keys())
	_commit(edit, label)


func _on_selection_action(action: String) -> void:
	if _world == null or _world.selected.is_empty():
		return

	var chosen: Dictionary = _world.selected
	var count: int = _Const.CHUNK_ROTATION_COUNT

	match action:
		TerrainDock.ACTION_TURN:
			_replace_selected(chosen["tile"], chosen["kind"], (chosen["rotation"] + 1) % count,
				chosen["text"], chosen["look"], chosen["spawn"], "Turn object")
		TerrainDock.ACTION_TURN_BACK:
			_replace_selected(chosen["tile"], chosen["kind"],
				posmod(chosen["rotation"] - 1, count), chosen["text"], chosen["look"],
				chosen["spawn"], "Turn object back")
		TerrainDock.ACTION_DELETE:
			_delete_selected()
		TerrainDock.ACTION_FOLLOW:
			_follow_link()


## The fields of the Objects tab changed: the kind, the rotation, the text,
## the look, or the spawn of the selected object. A sign keeps its words
## through a change of the kind to another sign kind. A kind with no text
## drops them. A kind with no spawn drops its spawn in the same way. The
## reader refuses what [method ChunkFile.look_problem] refuses, so a bad
## look stops here with a status line.
func _on_selection_edited(kind: String, rotation: int, text: String,
		look: Dictionary, spawn: Dictionary) -> void:
	if _world == null or _world.selected.is_empty():
		return

	var chosen: Dictionary = _world.selected
	var words: Variant = _text_for(kind, text if not text.is_empty() else chosen["text"])
	var spawned: Variant = _spawn_for(kind, spawn)

	if words == null or spawned == null:
		return

	if not look.is_empty():
		var problem := ChunkFile.look_problem(look)

		if not problem.is_empty():
			_dock.set_status("Look: " + problem)
			return

	var edited := {"kind": kind, "rotation": rotation, "text": words, "look": look,
		"spawn": spawned}

	if ChunkSet.same_object(edited, chosen):
		return

	_replace_selected(chosen["tile"], kind, rotation, words, look, spawned, "Edit object")


func _delete_selected() -> void:
	var chosen: Dictionary = _world.selected
	var edit := TerrainEdit.for_world(_world)

	edit.remove_object(_world.chunks, chosen["tile"], chosen["kind"], chosen["rotation"],
		chosen["text"], chosen["look"], chosen["spawn"])
	_world.clear_selection()
	_world.queue_rebuild(edit.chunk_keys())
	_commit(edit, "Delete object")


func _follow_link() -> void:
	var end := _world.selected_link_end()

	if not end.is_empty():
		_jump(end["tile"], end["plane"], "Followed the link to %s, plane %d."
			% [end["tile"], end["plane"]])


## A row of the object list. The Paint tool stays as it is: the Objects
## tab owns its selection.
func _on_object_chosen(thing: Dictionary) -> void:
	if _world == null:
		return

	_world.select_thing(thing["tile"], thing)
	_dock.set_selection(_world.selected, _world.selected_link_end())


# ─── Check world ────────────────────────────────────────────────────────────

func _on_check_requested() -> void:
	if _world == null:
		return

	var errors := PackedStringArray()
	var files := _world.world_chunk_files(errors)

	# The item list may be new since the last check: the export writes it.
	SpawnItems.forget()

	var items := SpawnItems.game()

	if not items.error.is_empty():
		errors.append(items.error)

	var found := TerrainChecks.check_world(files, items.stacking())

	if not _world.writes_world():
		found = TerrainChecks.for_workbench(found)

	_dock.set_findings(found, errors)
	_dock.set_status("Check world: %d chunk file(s), %d finding(s)."
		% [files.size(), found.size() + errors.size()])


# ─── The structure workbench ────────────────────────────────────────────────

## "Clear workbench": ask with the count of the files, then delete them.
func _on_clear_workbench_asked() -> void:
	if _world == null:
		return

	_dock.confirm("Delete %d scratch chunk file(s) of the structure workbench? "
		% _world.chunk_file_count() + "The templates stay. Undo cannot bring the chunks "
		+ "back.", _clear_workbench)


## The load of the blank block clears the undo history.
func _clear_workbench() -> void:
	var deleted := _world.clear_workbench()

	if deleted < 0:
		_dock.set_status("This scene edits the world chunk files. Nothing deleted.")
		return

	_dock.set_status("Cleared the structure workbench: %d scratch chunk file(s) deleted."
		% deleted)


## Open the structure workbench from the world, or the world from the
## workbench. With unsaved chunks, it asks to save them first. The plugin
## saves the chunks of the node that it edits only, so edits left in the
## other scene could go unsaved.
func _on_switch_scene() -> void:
	if _world == null or not _world.has_unsaved_changes():
		_open_other_scene()
		return

	_dock.confirm("Save %d changed chunk file(s) and open the other scene?"
		% _world.unsaved_count(), func() -> void:
			_save(_world)
			_open_other_scene())


func _open_other_scene() -> void:
	var leaving_world := _world == null or _world.writes_world()

	EditorInterface.open_scene_from_path(WORKBENCH_SCENE if leaving_world else EDITOR_SCENE)


func _on_finding_chosen(finding: Dictionary) -> void:
	if _world != null:
		_jump(Vector2i(finding["x"], finding["y"]), finding["plane"],
			TerrainChecks.describe(finding))


# ─── The Look tab ───────────────────────────────────────────────────────────

func _connect_look_panel() -> void:
	var look := _dock.look_panel()

	look.palette_changed.connect(_on_palette_changed)
	look.light_changed.connect(_on_light_changed)
	look.area_look_changed.connect(_on_area_look_changed)
	look.shadow_minimum_changed.connect(_on_shadow_minimum_changed)
	look.preview_changed.connect(_on_preview_changed)
	look.reset_requested.connect(_on_reset_palette_asked)
	look.area_reset_requested.connect(_on_reset_area_asked)
	look.marks_changed.connect(_on_marks_changed)
	look.load_marks()


## The colours of the editor marks changed: the overlay, the legend, and
## the ghost planes take them.
func _on_marks_changed() -> void:
	_dock.refresh_legend()

	if _world != null:
		_world.refresh_mark_colors()
		update_overlays()


## The terrain palette file changed. The block draws again with it.
func _on_palette_changed() -> void:
	if _world == null:
		return

	_world.rebuild_all()
	_dock.set_status("The terrain palette changed: %s." % TerrainPalette.PATH)


## The light of a scenery key changed in the file. The block draws again
## with it, because each mesh carries the light.
func _on_light_changed(scenery: String) -> void:
	if _world == null:
		return

	_world.rebuild_all()
	_dock.set_status("The light of %s changed: %s." % [scenery, LightLook.PATH])


## The look of `area` changed in the file. A preview of that area follows.
func _on_area_look_changed(area: String) -> void:
	var look := _dock.look_panel()

	if _world != null and look.preview_on() and look.area() == area:
		_world.preview_look(AreaLook.look_for(area))

	_dock.set_status("The look of the area %s changed: %s." % [area, AreaLook.PATH])


## The shadow minimum of every area changed in the file. A preview follows,
## because the sun of the preview carries it.
func _on_shadow_minimum_changed() -> void:
	var look := _dock.look_panel()

	if _world != null and look.preview_on():
		_world.preview_look(AreaLook.look_for(look.area()))

	_dock.set_status("The shadow minimum of every area changed: %s." % AreaLook.PATH)


## The preview went on for `area`, or off.
func _on_preview_changed(area: String) -> void:
	if _world == null:
		return

	if area.is_empty():
		_world.preview_look({})
		_dock.set_status("The preview is off. The scene has its own sky and sun again.")
		return

	_world.preview_look(AreaLook.look_for(area))
	_dock.set_status("The preview shows the fog and the light of %s. A save of the "
		% area + "scene keeps the own sky and sun of the scene.")


func _on_reset_palette_asked() -> void:
	_dock.confirm("Take every colour and height out of %s? Each one then shows the "
		% TerrainPalette.PATH.get_file() + "fallback of the client table. Undo cannot "
		+ "bring the file back.", _dock.look_panel().reset_palette)


func _on_reset_area_asked(area: String) -> void:
	_dock.confirm("Take the area %s out of %s? It then shows its fallback look. Undo "
		% [area, AreaLook.PATH.get_file()] + "cannot bring the row back.",
		_dock.look_panel().reset_area.bind(area))


# ─── The Tables tab ─────────────────────────────────────────────────────────

func _connect_tables_panel() -> void:
	var tables := _dock.tables_panel()

	tables.add_requested.connect(_on_table_add)
	tables.save_requested.connect(_on_table_save)
	tables.rename_requested.connect(_on_table_rename)
	tables.remove_requested.connect(_on_table_remove)
	tables.reload_requested.connect(func() -> void:
		_after_table_change("Read the table files again.", {}, ""))


## "New row". A row needs no confirmation: nothing names it yet.
func _on_table_add(table: String, row: Dictionary) -> void:
	var problem := _edits.add(table, row)

	if not problem.is_empty():
		_table_problem(problem)
		return

	_after_table_change("Added %s to %s." % [row["key"], TileTables.file_path(table)],
		{}, row["key"])


## "Save row". The key stays, so no other file changes.
func _on_table_save(table: String, key: String, row: Dictionary) -> void:
	if key.is_empty():
		_table_problem("Select a row first.")
		return

	var problem := _edits.save(table, key, row)

	if not problem.is_empty():
		_table_problem(problem)
		return

	_after_table_change("Saved the row %s of %s." % [key, TileTables.file_path(table)],
		{}, key)


## "Rename row". It rewrites files that undo cannot reach, so it asks first,
## and it counts them. Unsaved chunks save first, and the block reads again.
func _on_table_rename(table: String, old: String, new: String) -> void:
	var problem := "Select a row first." if old.is_empty() \
		else TableEdits.rename_problem(table, old, new)

	if not problem.is_empty():
		_table_problem(problem)
		return

	var found := _edits.uses(table, old)
	var unsaved := _last_world.unsaved_count() if is_instance_valid(_last_world) else 0
	var text := "Rename %s to %s? It rewrites %d chunk file(s), %d template(s), and the " \
		% [old, new, found["chunks"].size(), found["templates"].size()] \
		+ "look rows of the key. Undo cannot reverse it."

	if unsaved > 0:
		text += " First it saves %d changed chunk file(s)." % unsaved

	_dock.confirm(text, _rename_row.bind(table, old, new))


func _rename_row(table: String, old: String, new: String) -> void:
	var lines := PackedStringArray()

	if is_instance_valid(_last_world) and _last_world.has_unsaved_changes():
		lines.append(_save(_last_world))

	var result := _edits.rename(table, old, new)

	if not result["problem"].is_empty():
		_table_problem(result["problem"])
		return

	lines.append("Renamed %s to %s." % [old, new])
	lines.append_array(result["lines"])

	if is_instance_valid(_last_world):
		_last_world.load_block()

	_after_table_change("\n".join(lines), {"table": table, "old": old, "new": new}, new)


## "Remove row". A key in use stays, and the status names the files.
func _on_table_remove(table: String, key: String) -> void:
	if key.is_empty():
		_table_problem("Select a row first.")
		return

	var problem := _edits.remove_problem(table, key, _open_chunks())

	if not problem.is_empty():
		_table_problem(problem)
		return

	_dock.confirm("Remove %s from %s? Its look rows go too. Undo cannot bring them back."
		% [key, TileTables.file_path(table).get_file()], _remove_row.bind(table, key))


func _remove_row(table: String, key: String) -> void:
	var result := _edits.remove(table, key, _open_chunks())

	if not result["problem"].is_empty():
		_table_problem(result["problem"])
		return

	var lines := PackedStringArray(["Removed %s." % key])

	lines.append_array(result["lines"])
	_after_table_change("\n".join(lines), {}, "")


## The chunks of the open block, unsaved edits included, for the use check
## of a removal.
func _open_chunks() -> Array[ChunkFile]:
	if not is_instance_valid(_last_world):
		return []

	return _last_world.world_chunk_files(PackedStringArray())


func _table_problem(problem: String) -> void:
	_dock.tables_panel().set_hint(problem)
	_dock.set_status(problem)


## After each change of a table file: every list reads again, the block
## draws again, and the client export runs. The Tables tab selects
## `select`.
func _after_table_change(text: String, rename: Dictionary, select: String) -> void:
	TileTables.forget()
	_dock.refresh_tables(rename, select)
	_dock.tables_panel().set_hint(text.get_slice("\n", 0))

	if _world != null:
		_world.rebuild_all()
		_refresh_dock()

	_table_report = text
	_start_export()
	update_overlays()


func _start_export() -> void:
	if _export.is_running():
		_export_again = true
		return

	_export.start(ClientExport.LABEL, func() -> Dictionary: return ClientExport.run(),
		_on_export_done)
	_dock.set_status(_table_report + "\n" + _export.busy_text())


## The export ended. The status keeps the report of the change above the
## result.
func _on_export_done(result: Dictionary) -> void:
	if _export_again:
		_export_again = false
		_start_export()
		return

	if result.get("ok", false):
		_dock.set_status(_table_report + "\nThe client constants follow the table "
			+ "files. Restart the server to give it the change.")
		return

	_dock.set_status(_table_report + "\nTHE CLIENT EXPORT FAILED. In blackout/, run "
		+ "python scripts/export_client_constants.py to see why.\n"
		+ str(result.get("output", "")))
