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
## An edit keys on world tiles, with no plane. A move to another block or
## plane saves the old block, so an undo there would change a file that is no
## longer loaded, or write into the wrong plane. Thus, each load of a block
## clears the history of the edited scene. [method TerrainWorld.replay_edit]
## also refuses an edit of another block.
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

	_world = object as TerrainWorld

	if _world == null:
		return

	_world.block_loaded.connect(_on_block_loaded)
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


## Every load of a block: a move, a plane change, a jump, or a link.
func _on_block_loaded() -> void:
	var history := get_undo_redo()

	history.clear_history(history.get_object_history_id(_world))
	_refresh_dock()
	_report_block()


func _on_overlays_changed() -> void:
	if _world == null:
		return

	_world.show_flags = _dock.show_flags()
	_world.show_areas = _dock.show_areas()
	_world.show_links = _dock.show_links()
	_world.show_lower_planes = _dock.show_lower_planes()


func _report_block() -> void:
	var lines := PackedStringArray(["Block around chunk %s, plane %d."
		% [_world.centre_chunk, _world.plane]])

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
	if not _world.chunk_directory.is_empty():
		_dock.set_sync_state("A scratch directory: no tile sync applies.")
		return

	_dock.set_sync_state(TerrainSyncState.describe(_world.directory(),
		TerrainSyncState.stamp_path()))


# ─── The mouse ──────────────────────────────────────────────────────────────

func _forward_3d_gui_input(camera: Camera3D, event: InputEvent) -> int:
	if _world == null:
		return AFTER_GUI_INPUT_PASS

	if event is InputEventMouseMotion:
		return _on_motion(camera, event)

	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		return _on_left_button(camera, event)

	return AFTER_GUI_INPUT_PASS


## The point in tile space under the mouse, or null.
func _pick(camera: Camera3D, screen: Vector2) -> Variant:
	var origin := camera.project_ray_origin(screen)
	var direction := camera.project_ray_normal(screen)
	var hit: Variant = TerrainPicking.ray_hit(_world.chunks, origin, direction)

	if hit == null:
		return null

	return TerrainPicking.tile_point(hit)


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
		_stroke.apply_heights(chunks, _sculpt(tool_index, point))
	else:
		_paint(tool_index, point)

	_world.queue_rebuild(_stroke.chunk_coords())


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
	var changes := TerrainBrushes.ramp(_world.chunks, _ramp_start, end,
		_dock.radius() * 2.0, _ramp_start_height, _world.chunks.get_corner(corner))

	edit.apply_heights(_world.chunks, changes)
	_world.queue_rebuild(edit.chunk_coords())
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

	_world.queue_rebuild(edit.chunk_coords())
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
	var changes := TerrainBrushes.noise_fill(_world.chunks, _world.centre_chunk,
		_dock.make_noise(), _dock.noise_amplitude())

	edit.apply_heights(_world.chunks, changes)
	_world.queue_rebuild(edit.chunk_coords())
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
	_world.queue_rebuild(edit.chunk_coords())
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
	_world.queue_rebuild(edit.chunk_coords())
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

	_dock.set_findings(found, errors)
	_dock.set_status("Check world: %d chunk file(s), %d finding(s)."
		% [files.size(), found.size() + errors.size()])


func _on_finding_chosen(finding: Dictionary) -> void:
	if _world == null:
		return

	_world.jump_to(Vector2i(finding["x"], finding["y"]), finding["plane"])
	_refresh_dock()
	_dock.set_status(TerrainChecks.describe(finding))
