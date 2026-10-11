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
## refuses an edit of another block.
##
## A change of the plane keeps the history (DESIGN-0013 Phase S0). The block
## holds every plane, and an edit keys on (plane, tile). Thus an undo writes
## into the plane of its edit.
##
## ## The Build tab
##
## While the Build tab shows, every event of the 3D view goes to
## [BuildInput], and [ToolHint] draws the hint line over the view
## (DESIGN-0013 section 6.7).
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
## One button deletes the scratch files after a confirmation.
##
## ## Saving
##
## Ctrl+S saves the scene, and the editor then calls
## [method _save_external_data], which writes every changed chunk file. The
## editor also asks about unsaved chunks when it closes.

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

var _dock: TerrainDock
var _world: TerrainWorld
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


func _enter_tree() -> void:
	_dock = TerrainDock.new()
	_dock.load_requested.connect(_on_load_requested)
	_dock.save_requested.connect(_on_save_requested)
	_dock.noise_fill_requested.connect(_on_noise_fill_requested)
	_dock.overlays_changed.connect(_on_overlays_changed)
	_dock.selection_action.connect(_on_selection_action)
	_dock.object_chosen.connect(_on_object_chosen)
	_dock.check_requested.connect(_on_check_requested)
	_dock.finding_chosen.connect(_on_finding_chosen)
	_dock.tab_changed.connect(_on_tab_changed)
	_dock.clear_workbench_requested.connect(_on_clear_workbench)
	_dock.switch_scene_requested.connect(_on_switch_scene)
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

	_world.block_loaded.connect(_on_block_loaded)
	_world.plane_changed.connect(_on_plane_changed)
	_build.world = _world
	_dock.set_workbench(not _world.writes_world())
	_on_overlays_changed()
	_refresh_dock()
	_report_block()


# ─── Saving and loading ─────────────────────────────────────────────────────

func _save_external_data() -> void:
	if _world != null and _world.has_unsaved_changes():
		_on_save_requested()


func _get_unsaved_status(_for_scene: String) -> String:
	if _world == null or not _world.has_unsaved_changes():
		return ""

	return "The terrain has unsaved chunk changes. Save them?"


func _on_save_requested() -> void:
	if _world == null:
		return

	var saved := _world.save_block()

	_dock.set_status("Saved %d chunk file(s): %s" % [saved.size(),
		", ".join(saved)])
	_refresh_sync_state()


func _on_load_requested(centre: Vector2i, plane: int) -> void:
	if _world == null:
		return

	_world.move_block(centre, plane)


## Every load of a block: a move, or a jump or a link to another block.
func _on_block_loaded() -> void:
	var history := get_undo_redo()

	history.clear_history(history.get_object_history_id(_world))
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


## "Save the selection as a template" on the Build tab.
func _on_save_template(template_key: String) -> void:
	if _world == null:
		return

	_dock.set_status(_build.save_template(template_key))
	update_overlays()


func _on_reload_templates() -> void:
	_build.reload_templates()
	_dock.set_status("Read the template directory again.")
	update_overlays()


## Leaving the Build tab drops its drag, its marks, and its hint line.
func _on_tab_changed() -> void:
	if _world != null and _build.world != null:
		_build.cancel()
		_world.show_marks([], Color.WHITE)

	update_overlays()


func _report_block() -> void:
	var lines := PackedStringArray(["Block around chunk %s, plane %d."
		% [_world.centre_chunk, _world.plane]])

	if not _world.writes_world():
		lines.insert(0, "The structure workbench: scratch chunk files in %s. "
			% _world.directory() + "Nothing here reaches the world. Save a template "
			+ "from the Build tab.")

	lines.append_array(_world.load_errors)

	for mismatch: String in _world.chunks.seam_mismatches():
		lines.append("Seam: " + mismatch)

	_dock.set_status("\n".join(lines))


## The block, the objects, the selection, and the sync state in the dock.
func _refresh_dock() -> void:
	_dock.set_block(_world.centre_chunk, _world.plane)
	_dock.set_objects(_world.objects_in_block())
	_dock.set_selection(_world.selected, _world.selected_link_end())
	_refresh_sync_state()


func _refresh_sync_state() -> void:
	if not _world.writes_world():
		_dock.set_sync_state("A scratch directory: no tile sync applies.")
		return

	_dock.set_sync_state(TerrainSyncState.describe(_world.directory(),
		TerrainSyncState.stamp_path()))


# ─── The mouse ──────────────────────────────────────────────────────────────

func _forward_3d_gui_input(camera: Camera3D, event: InputEvent) -> int:
	if _world == null:
		return AFTER_GUI_INPUT_PASS

	if _dock.build_active():
		return _build_event(camera, event)

	if event is InputEventMouseMotion:
		return _on_motion(camera, event)

	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		return _on_left_button(camera, event)

	return AFTER_GUI_INPUT_PASS


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
	elif event is InputEventKey:
		used = _build.on_key(event)

		if used:
			_mark_key_handled(camera)
	else:
		return AFTER_GUI_INPUT_PASS

	update_overlays()

	return AFTER_GUI_INPUT_STOP if used else AFTER_GUI_INPUT_PASS


## Stop a key that a Build tool used. AFTER_GUI_INPUT_STOP stops only the
## 3D view. The editor shortcuts still read the key: Page Down is "Snap
## Object to Floor", and R is the Scale mode. The 3D view sits in a
## SubViewport. Thus, the key belongs to the window around its container.
func _mark_key_handled(camera: Camera3D) -> void:
	var container := camera.get_viewport().get_parent() as Node

	if container == null:
		return

	var window := container.get_viewport()

	if window != null:
		window.set_input_as_handled()


func _forward_3d_draw_over_viewport(overlay: Control) -> void:
	if _world == null or not _dock.build_active():
		return

	ToolHint.draw(overlay, _build.hint(), _build.readout(), _mouse)


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

	if _dock.current_tool() == TerrainDock.Tool.SELECT:
		var ring: Variant = null if point == null else Vector2(ChunkSet.tile_at(point))

		_world.show_ring(ring, SELECT_RING)
		return AFTER_GUI_INPUT_STOP if _drag_from != null else AFTER_GUI_INPUT_PASS

	_world.show_ring(point, _dock.radius())

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
	if not _stroking or not (_dock.current_tool() in TerrainDock.SCULPT_TOOLS):
		return

	_since_dab += delta

	if _since_dab >= DAB_INTERVAL:
		_dab(_last_point)


# ─── Strokes ────────────────────────────────────────────────────────────────

func _start_stroke(point: Vector2) -> void:
	var corner := Vector2i(roundi(point.x + 0.5), roundi(point.y + 0.5))

	_stroke = TerrainEdit.for_world(_world)
	_stroking = true
	_flatten_target = _world.chunks.get_corner(corner)
	_dab(point)


func _end_stroke() -> void:
	_stroking = false
	_commit(_stroke, _dock.tool_name())
	_stroke = null


## Put one finished edit in the editor history. It is already applied, so
## the history must not apply it again.
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
	var strength := _dock.strength()

	match tool_index:
		TerrainDock.Tool.RAISE:
			var direction := -1 if _shift else 1

			return TerrainBrushes.raise(chunks, point, radius, direction * strength)
		TerrainDock.Tool.LOWER:
			return TerrainBrushes.raise(chunks, point, radius, -strength)
		TerrainDock.Tool.FLATTEN:
			return TerrainBrushes.flatten(chunks, point, radius, _flatten_target,
				strength)
		TerrainDock.Tool.SMOOTH:
			return TerrainBrushes.smooth(chunks, point, radius)
		TerrainDock.Tool.NOISE:
			return TerrainBrushes.noise_brush(chunks, point, radius,
				_dock.make_noise(), _dock.noise_amplitude(), strength)

	return {}


## One dab of a paint tool: floors, flags, or areas, on each tile in the
## circle. With Shift, the floor and area tools pick the value under the
## brush, and the flag tool clears the checked flags.
func _paint(tool_index: int, point: Vector2) -> void:
	var chunks := _world.chunks
	var tiles := TerrainBrushes.tiles_in_circle(point, _dock.radius())
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
				_paint_floor(tile, _dock.floor_name())
			TerrainDock.Tool.AREA:
				_stroke.apply_area(chunks, tile, _dock.area_name())
			TerrainDock.Tool.FLAGS:
				_stroke.apply_flags(chunks, tile, _flagged(chunks.get_flags(tile)))


## A floor paint, and the Blocked flag that a void tile needs (Phase 7c).
func _paint_floor(tile: Vector2i, floor_name: String) -> void:
	var chunks := _world.chunks
	var flags := TerrainBrushes.flags_after_floor(chunks.get_floor(tile),
		floor_name, chunks.get_flags(tile))

	_stroke.apply_floor(chunks, tile, floor_name)

	if flags != chunks.get_flags(tile):
		_stroke.apply_flags(chunks, tile, flags)


func _flagged(flags: int) -> int:
	if _shift:
		return flags & ~_dock.flag_bits()

	return flags | _dock.flag_bits()


func _ramp_click(point: Vector2) -> void:
	var corner := Vector2i(roundi(point.x + 0.5), roundi(point.y + 0.5))

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

		edit.remove_object(chunks, tile, last["kind"], last["rotation"], last["text"])
	else:
		var text: Variant = _text_for(_dock.kind(), "")

		if text == null:
			return

		edit.add_object(chunks, tile, _dock.kind(), _dock.object_rotation(), text)
		_world.select(tile, _dock.kind(), _dock.object_rotation(), text)

	_world.queue_rebuild(edit.chunk_keys())
	_commit(edit, "Object")


## The text that an object of `kind` gets: "" for a kind with no text, else
## `kept`, else the Sign text of the dock. Null, with a status line, when a
## sign would get no legal text. The reader refuses what
## [method ChunkFile.text_problem] refuses, so the editor never writes it.
func _text_for(kind: String, kept: String) -> Variant:
	if not TerrainChecks.takes_text(kind):
		return ""

	var text := kept if not kept.is_empty() else _dock.object_text()

	if text.is_empty():
		_dock.set_status("A %s needs words. Type them in Sign text first." % kind)
		return null

	var problem := ChunkFile.text_problem(text)

	if not problem.is_empty():
		_dock.set_status("Sign text: " + problem)
		return null

	return text


func _on_noise_fill_requested() -> void:
	if _world == null:
		return

	var edit := TerrainEdit.for_world(_world)
	var changes := _protected(TerrainBrushes.noise_fill(_world.chunks, _world.centre_chunk,
		_dock.make_noise(), _dock.noise_amplitude()))

	edit.apply_heights(_world.chunks, changes)
	_world.queue_rebuild(edit.chunk_keys())
	_commit(edit, "Noise fill")


# ─── The Select tool ────────────────────────────────────────────────────────

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

	_world.select(tile, here[index]["kind"], here[index]["rotation"],
		here[index]["text"])
	_drag_from = tile
	_refresh_dock()


func _index_on_tile(here: Array[Dictionary]) -> int:
	for index: int in here.size():
		if here[index]["kind"] == _world.selected["kind"] \
				and here[index]["rotation"] == _world.selected["rotation"] \
				and here[index]["text"] == _world.selected["text"]:
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
		_world.selected["text"], "Move object")


## Replace the selected object with one at `tile` of `kind`, `rotation`, and
## `text`, as one undo entry, and select the new one.
func _replace_selected(tile: Vector2i, kind: String, rotation: int, text: String,
		label: String) -> void:
	var chunks := _world.chunks
	var edit := TerrainEdit.for_world(_world)
	var old: Dictionary = _world.selected

	edit.remove_object(chunks, old["tile"], old["kind"], old["rotation"], old["text"])
	edit.add_object(chunks, tile, kind, rotation, text)
	_world.select(tile, kind, rotation, text)
	_world.queue_rebuild(edit.chunk_keys())
	_commit(edit, label)


func _on_selection_action(action: String) -> void:
	if _world == null or _world.selected.is_empty():
		return

	var chosen: Dictionary = _world.selected
	var turned: int = (chosen["rotation"] + 1) % _Const.CHUNK_ROTATION_COUNT

	match action:
		TerrainDock.ACTION_TURN:
			_replace_selected(chosen["tile"], chosen["kind"], turned, chosen["text"],
				"Turn object")
		TerrainDock.ACTION_SET_KIND:
			_set_selected_kind(chosen)
		TerrainDock.ACTION_SET_TEXT:
			_set_selected_text(chosen)
		TerrainDock.ACTION_DELETE:
			_delete_selected()
		TerrainDock.ACTION_FOLLOW:
			_follow_link()


## Give the selected object the kind of the Object choice. A sign keeps its
## words. A kind with no text drops them.
func _set_selected_kind(chosen: Dictionary) -> void:
	var text: Variant = _text_for(_dock.kind(), chosen["text"])

	if text == null:
		return

	_replace_selected(chosen["tile"], _dock.kind(), chosen["rotation"], text,
		"Set object kind")


## Give the selected sign the words of the Sign text.
func _set_selected_text(chosen: Dictionary) -> void:
	if not TerrainChecks.takes_text(chosen["kind"]):
		_dock.set_status("A %s has no text. Only a sign kind has text." % chosen["kind"])
		return

	var text: Variant = _text_for(chosen["kind"], "")

	if text == null:
		return

	_replace_selected(chosen["tile"], chosen["kind"], chosen["rotation"], text,
		"Set sign text")


func _delete_selected() -> void:
	var chosen: Dictionary = _world.selected
	var edit := TerrainEdit.for_world(_world)

	edit.remove_object(_world.chunks, chosen["tile"], chosen["kind"], chosen["rotation"],
		chosen["text"])
	_world.clear_selection()
	_world.queue_rebuild(edit.chunk_keys())
	_commit(edit, "Delete object")


func _follow_link() -> void:
	var end := _world.selected_link_end()

	if end.is_empty():
		return

	_world.jump_to(end["tile"], end["plane"])
	_refresh_dock()
	_dock.set_status("Followed the link to %s, plane %d." % [end["tile"], end["plane"]])


func _on_object_chosen(thing: Dictionary) -> void:
	if _world == null:
		return

	_world.select(thing["tile"], thing["kind"], thing["rotation"], thing["text"])
	_dock.select_tool(TerrainDock.Tool.SELECT)
	_dock.set_selection(_world.selected, _world.selected_link_end())


# ─── Check world ────────────────────────────────────────────────────────────

func _on_check_requested() -> void:
	if _world == null:
		return

	var errors := PackedStringArray()
	var files := _world.world_chunk_files(errors)
	var found := TerrainChecks.check_world(files)

	if not _world.writes_world():
		found = TerrainChecks.for_workbench(found)

	_dock.set_findings(found, errors)
	_dock.set_status("Check world: %d chunk file(s), %d finding(s)."
		% [files.size(), found.size() + errors.size()])


# ─── The structure workbench ────────────────────────────────────────────────

## "Clear the structure workbench", after the confirmation of the dock. The
## load of the blank block clears the undo history.
func _on_clear_workbench() -> void:
	if _world == null:
		return

	var deleted := _world.clear_workbench()

	if deleted < 0:
		_dock.set_status("This scene edits the world chunk files. Nothing deleted.")
		return

	_dock.set_status("Cleared the structure workbench: %d scratch chunk file(s) deleted."
		% deleted)


## Open the structure workbench from the world, or the world from the
## workbench. Unsaved chunks refuse the switch. The plugin saves the chunks
## of the node that it edits only, so edits left in the other scene could
## go unsaved.
func _on_switch_scene() -> void:
	if _world != null and _world.has_unsaved_changes():
		_dock.set_status("Save the chunk files first (Ctrl+S), then open the other scene.")
		return

	var leaving_world := _world == null or _world.writes_world()

	EditorInterface.open_scene_from_path(WORKBENCH_SCENE if leaving_world else EDITOR_SCENE)


func _on_finding_chosen(finding: Dictionary) -> void:
	if _world == null:
		return

	_world.jump_to(Vector2i(finding["x"], finding["y"]), finding["plane"])
	_refresh_dock()
	_dock.set_status(TerrainChecks.describe(finding))
