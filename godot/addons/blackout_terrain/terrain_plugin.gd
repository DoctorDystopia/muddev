@tool
extends EditorPlugin
## The Blackout terrain editor: routes the mouse in the 3D viewport to the
## brushes, and each stroke to the editor history.
##
## DESIGN-0011 section 6.3. Select a [TerrainWorld] node, for example in
## `res://addons/blackout_terrain/terrain_editor.tscn`, to start. The panel
## is [TerrainDock]. The rules live in [TerrainBrushes], [TerrainEdit], and
## [ChunkSet], and `tests/test_terrain_editing.tscn` tests them with no
## editor. This script only decides which rule a click calls.
##
## ## One stroke, one undo entry
##
## A press starts a [TerrainEdit]. Each dab adds to it. The release puts it in
## the history as one entry, so Ctrl+Z undoes the whole stroke.
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


func _enter_tree() -> void:
	_dock = TerrainDock.new()
	_dock.load_requested.connect(_on_load_requested)
	_dock.save_requested.connect(_on_save_requested)
	_dock.noise_fill_requested.connect(_on_noise_fill_requested)
	_dock.overlays_changed.connect(_on_overlays_changed)
	add_control_to_dock(DOCK_SLOT_RIGHT_UL, _dock)
	set_process(true)


func _exit_tree() -> void:
	remove_control_from_docks(_dock)
	_dock.queue_free()


func _handles(object: Object) -> bool:
	return object is TerrainWorld


func _edit(object: Object) -> void:
	_world = object as TerrainWorld

	if _world != null:
		_dock.set_centre(_world.centre_chunk)
		_report_block()


# ─── Saving ─────────────────────────────────────────────────────────────────

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


func _on_load_requested(centre: Vector2i) -> void:
	if _world == null:
		return

	_world.centre_chunk = centre
	_report_block()


func _on_overlays_changed(show_flags: bool, show_areas: bool) -> void:
	if _world == null:
		return

	_world.show_flags = show_flags
	_world.show_areas = show_areas


func _report_block() -> void:
	var lines := PackedStringArray(["Block around chunk %s." % _world.centre_chunk])

	lines.append_array(_world.load_errors)

	for mismatch: String in _world.chunks.seam_mismatches():
		lines.append("Seam: " + mismatch)

	_dock.set_status("\n".join(lines))


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

	_world.show_ring(point, _dock.radius())

	if not _stroking or point == null:
		return AFTER_GUI_INPUT_PASS

	if point.distance_to(_last_point) >= DAB_SPACING:
		_dab(point)

	return AFTER_GUI_INPUT_STOP


func _on_left_button(camera: Camera3D, event: InputEventMouseButton) -> int:
	if not event.pressed:
		if _stroking:
			_end_stroke()
			return AFTER_GUI_INPUT_STOP

		return AFTER_GUI_INPUT_PASS

	var point: Variant = _pick(camera, event.position)

	if point == null:
		return AFTER_GUI_INPUT_PASS

	_shift = event.shift_pressed

	match _dock.current_tool():
		TerrainDock.Tool.RAMP:
			_ramp_click(point)
		TerrainDock.Tool.OBJECT:
			_object_click(point)
		_:
			_start_stroke(point)

	return AFTER_GUI_INPUT_STOP


func _process(delta: float) -> void:
	if not _stroking or not (_dock.current_tool() in TerrainDock.SCULPT_TOOLS):
		return

	_since_dab += delta

	if _since_dab >= DAB_INTERVAL:
		_dab(_last_point)


# ─── Strokes ────────────────────────────────────────────────────────────────

func _start_stroke(point: Vector2) -> void:
	var corner := Vector2i(roundi(point.x + 0.5), roundi(point.y + 0.5))

	_stroke = TerrainEdit.new()
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
	history.commit_action(false)
	_dock.set_status("%s: %d change(s)." % [label, edit.size()])


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
				_stroke.apply_floor(chunks, tile, _dock.floor_name())
			TerrainDock.Tool.AREA:
				_stroke.apply_area(chunks, tile, _dock.area_name())
			TerrainDock.Tool.FLAGS:
				_stroke.apply_flags(chunks, tile, _flagged(chunks.get_flags(tile)))


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

	var edit := TerrainEdit.new()
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
	var edit := TerrainEdit.new()

	if not chunks.has_tile(tile):
		return

	if _shift:
		var here := chunks.objects_at(tile)

		if here.is_empty():
			return

		var last: Dictionary = here[here.size() - 1]

		edit.remove_object(chunks, tile, last["kind"], last["rotation"])
	else:
		edit.add_object(chunks, tile, _dock.kind(), _dock.object_rotation())

	_world.queue_rebuild(edit.chunk_coords())
	_commit(edit, "Object")


func _on_noise_fill_requested() -> void:
	if _world == null:
		return

	var edit := TerrainEdit.new()
	var changes := TerrainBrushes.noise_fill(_world.chunks, _world.centre_chunk,
		_dock.make_noise(), _dock.noise_amplitude())

	edit.apply_heights(_world.chunks, changes)
	_world.queue_rebuild(edit.chunk_coords())
	_commit(edit, "Noise fill")
