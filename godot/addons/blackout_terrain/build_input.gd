@tool
class_name BuildInput
extends RefCounted
## The mouse and the keys of the Build tools (DESIGN-0013 section 6.7), out
## of `terrain_plugin.gd`. The plugin sends each event here while the Build
## tab shows. [StructureTools] holds the rules. This class only turns a
## gesture into one call and one undo entry.
##
## ## Gestures
##
## | Tool | Gesture | Shift |
## |---|---|---|
## | Wall line | Drag along tile edges, on one axis | Remove the walls under the line |
## | Room | Drag a rectangle | Remove the walls in the rectangle |
## | Doorway | Click a wall edge | Put the wall back |
## | Level above | Click inside a room, or drag a rectangle | Set the tiles back to void |
## | Stairs | Click a tile | Remove the pair |
## | Roof | Click inside a room, or drag a rectangle | Remove the roof |
## | Wall style | Drag the brush ring over walls | Paint the default style |
## | Decor | Click a tile, again and again. R turns the next one | Remove the decor on the tile |
## | Select | Drag a rectangle, or click inside a room | Take tiles out of the selection |
## | Place | Click to place a copy of a template | none |
##
## [TemplateInput] holds the gestures and the keys of Select and Place.
##
## Alt and a click take the floor, the area, and the wall style of a tile
## into the options: the tile of the wall slab under the mouse, else the
## tile of the ground ([method TerrainPicking.wall_hit]). While the Roof tool is on, R and Shift+R turn the ridge,
## and [ and ] step the pitch. While the Wall style tool is on, [ and ] step
## the radius of the brush.
##
## The Wall style brush paints as the mouse moves, as the Paint brushes do.
## The release puts the stroke in the history as one entry. Esc undoes the
## stroke before the release.
## Esc cancels a drag. Page Up and Page Down change the edited plane. V
## toggles "Walls down". A right drag stays the free-look camera of Godot,
## and Ctrl+Z and Ctrl+S stay the keys of the editor.
##
## ## What the author sees
##
## [method hint] gives the hint line: the tool, its gesture, each modifier,
## each toggle, and the last problem or live check. [method readout] gives
## the size of a drag. A tool that refuses names its reason there. Nothing
## is hidden behind a key that the screen does not name.
##
## The Roof tool draws its plan as an outline while the mouse is down: a
## lattice at the roof heights, green when a release builds it, red when
## the tool refuses. The hint line names the reason of a red outline.

const _Const := preload("res://autoload/blackout_constants.gd")

const COLOR_ADD := Color(0.3, 1.0, 0.45, 1.0)
const COLOR_REMOVE := Color(1.0, 0.4, 0.3, 1.0)

## The outline of a plan that a release builds, and of one that it refuses.
const COLOR_OUTLINE := Color(0.3, 1.0, 0.45, 1.0)
const COLOR_OUTLINE_REFUSED := Color(1.0, 0.25, 0.2, 1.0)

## The hint of each tool: the gesture and what Shift does.
const _TOOL_HINTS := {
	BuildPanel.Tool.WALL_LINE: "drag along tile edges. Shift removes walls",
	BuildPanel.Tool.ROOM: "drag a rectangle. Shift removes its walls",
	BuildPanel.Tool.DOORWAY: "click a wall edge. Shift puts the wall back",
	BuildPanel.Tool.LEVEL_ABOVE:
		"click inside a room, or drag a rectangle. Shift sets it back to void",
	BuildPanel.Tool.STAIRS: "click a tile. Shift removes the pair",
	BuildPanel.Tool.ROOF: "click inside a room, or drag a rectangle. "
		+ "Shift removes the roof. R turns. [ and ] step the pitch",
	BuildPanel.Tool.WALL_STYLE: "drag over walls to paint their style. "
		+ "Shift paints the default style. [ and ] step the radius",
	BuildPanel.Tool.DECOR: "click a tile to place, again and again. "
		+ "Shift removes the decor. R turns the next one",
	BuildPanel.Tool.SELECT: "drag a rectangle, or click inside a room. Ctrl adds, "
		+ "Shift takes out. Delete deletes. Ctrl+C copies, Ctrl+V pastes, M moves. "
		+ "Esc drops the selection",
	BuildPanel.Tool.PLACE: "click to place a copy. R turns, F mirrors. "
		+ "Alt and a click replace the objects. Esc ends",
}

## The front edge of a tile at each rotation, as a wall bit. The front of an
## object faces this edge, and the mark of the Decor tool shows it.
const _FRONT_EDGES := [_Const.TILE_FLAG_WALL_NORTH, _Const.TILE_FLAG_WALL_EAST,
	_Const.TILE_FLAG_WALL_SOUTH, _Const.TILE_FLAG_WALL_WEST]

## The tools that use the wall style of the options. The hint line names it.
const _STYLE_TOOLS := [BuildPanel.Tool.WALL_LINE, BuildPanel.Tool.ROOM,
	BuildPanel.Tool.WALL_STYLE]

var world: TerrainWorld
var panel: BuildPanel

## Put one finished edit in the editor history: `(edit, label) -> void`.
var commit: Callable

## The anchor of a drag: a corner for the Wall line, else a tile. Null when
## no drag is on.
var _anchor: Variant = null

## The end of the drag, of the same kind as the anchor.
var _end: Variant = null

## The point in tile space under the mouse, or null.
var _hover: Variant = null

var _shift := false

## The last refusal or live check, for the hint line. A new gesture clears it.
var _note := ""

## The roof rectangle of the drag, `{rect, problem}`, and the anchor and end
## it was found for. A click fills the room, so a move of the mouse inside
## one tile must not fill it again.
var _target := {}
var _target_of := []

## The edit of a Wall style stroke. The brush applies each dab at once, so
## the edit grows while the mouse is down. Null when no stroke is on.
var _stroke: TerrainEdit = null

## The Select and the Place tools.
var templates := TemplateInput.new()


func _init() -> void:
	templates.finish = _finish
	templates.say = func(text: String) -> void: _note = text


## [member templates], with the world and the panel of this input.
func _templates() -> TemplateInput:
	templates.world = world
	templates.panel = panel

	return templates


func _template_tool() -> bool:
	return TemplateInput.handles(panel.current_tool())


## "Save the selection as a template". Returns the status line.
func save_template(template_key: String) -> String:
	return _templates().save_template(template_key)


## "Reload the templates": read the template directory again.
func reload_templates() -> void:
	_templates().reload_templates()


func dragging() -> bool:
	return _anchor != null


## A choice of the Build tab changed. The plugin connects this to
## [signal BuildPanel.changed]. A pick of another tool ends a move.
func on_panel_changed() -> void:
	_templates().on_panel_changed()


## Drop the drag and its marks. A Wall style stroke that did not end in a
## release goes back: its dabs are already in the chunks.
func cancel() -> void:
	if _stroke != null:
		_stroke.replay_planes(world.plane_sets(), false)
		world.queue_rebuild(_stroke.chunk_keys())
		_stroke = null

	_anchor = null
	_end = null
	_templates().cancel()
	_refresh_marks()


# ─── Events ─────────────────────────────────────────────────────────────────

## The mouse moved over `point`, a point in tile space, or off the ground.
## Returns true when the event belongs to a drag. `alt` is the Alt key: the
## Place tool replaces objects with it.
func on_motion(point: Variant, shift: bool, alt: bool = false) -> bool:
	_hover = point
	_shift = shift

	if _template_tool():
		world.show_ring(null, 0.0)
		return _templates().on_motion(point, shift, alt)

	if dragging() and point != null:
		_end = _drag_point(point)

		if _stroke != null:
			_dab(point)

	_refresh_marks()
	_refresh_ring()

	return dragging()


## A left press at `point`. `wall` is the tile of the wall slab under the
## mouse, or null: Alt samples that tile first. `ctrl` is the Ctrl key: the
## Select tool adds with it. Returns true when the press belongs to a Build
## tool.
func on_press(point: Variant, shift: bool, alt: bool, wall: Variant = null,
		ctrl: bool = false) -> bool:
	if point == null and wall == null:
		return false

	_shift = shift
	_note = ""

	if _template_tool():
		return _templates().on_press(point, shift, ctrl, alt)

	if alt:
		_sample(wall if wall != null else ChunkSet.tile_at(point))
		return true

	if point == null:
		return false

	match panel.current_tool():
		BuildPanel.Tool.DOORWAY:
			_doorway(point)
		BuildPanel.Tool.STAIRS:
			_stairs(ChunkSet.tile_at(point))
		BuildPanel.Tool.DECOR:
			_decor(ChunkSet.tile_at(point))
		BuildPanel.Tool.WALL_STYLE:
			_anchor = _drag_point(point)
			_end = _anchor
			_stroke = TerrainEdit.for_world(world)
			_dab(point)
		_:
			_anchor = _drag_point(point)
			_end = _anchor

	_refresh_marks()

	return true


## A left release. Returns true when it ended a drag.
func on_release() -> bool:
	if _template_tool():
		return _templates().on_release()

	if not dragging():
		return false

	match panel.current_tool():
		BuildPanel.Tool.WALL_LINE:
			_wall_line()
		BuildPanel.Tool.ROOM:
			_room()
		BuildPanel.Tool.LEVEL_ABOVE:
			_level_above()
		BuildPanel.Tool.ROOF:
			_roof()
		BuildPanel.Tool.WALL_STYLE:
			_end_stroke()

	cancel()

	return true


## A key while the Build tab shows. Returns true when it is consumed.
func on_key(event: InputEventKey) -> bool:
	if not event.pressed or event.echo:
		return false

	if _template_tool() and _templates().on_key(event):
		return true

	match event.keycode:
		KEY_ESCAPE:
			if not dragging():
				return false

			cancel()
		KEY_PAGEUP:
			world.plane = world.plane + 1
		KEY_PAGEDOWN:
			world.plane = world.plane - 1
		KEY_V:
			panel.set_walls_down(not panel.walls_down())
		_:
			return _on_tool_key(event)

	return true


## R, Shift+R, [, and ] while the Roof tool is on, [ and ] while the Wall
## style tool is on, and R and Shift+R while the Decor tool is on. Returns
## true when the tool uses the key. Any other tool leaves them to Godot.
func _on_tool_key(event: InputEventKey) -> bool:
	match panel.current_tool():
		BuildPanel.Tool.ROOF:
			if not _on_roof_key(event):
				return false
		BuildPanel.Tool.WALL_STYLE:
			if not _on_brush_key(event):
				return false
		BuildPanel.Tool.DECOR:
			if event.keycode != KEY_R:
				return false

			panel.turn_decor(-1 if event.shift_pressed else 1)
		_:
			return false

	_refresh_marks()
	_refresh_ring()

	return true


func _on_roof_key(event: InputEventKey) -> bool:
	match event.keycode:
		KEY_R:
			panel.turn_roof(-1 if event.shift_pressed else 1)
		KEY_BRACKETLEFT:
			panel.step_pitch(-1)
		KEY_BRACKETRIGHT:
			panel.step_pitch(1)
		_:
			return false

	return true


func _on_brush_key(event: InputEventKey) -> bool:
	match event.keycode:
		KEY_BRACKETLEFT:
			panel.step_brush(-1)
		KEY_BRACKETRIGHT:
			panel.step_brush(1)
		_:
			return false

	return true


# ─── The hint line ──────────────────────────────────────────────────────────

## The hint line: the tool, its gesture, the modifiers, the toggles, and the
## last problem.
func hint() -> String:
	var walls := "down" if panel.walls_down() else "up"
	var sample := "" if _template_tool() else " Alt+click samples. Esc cancels."
	var line := "%s: %s.%s PgUp/PgDn: plane %d. V: walls %s." \
		% [panel.tool_name(), _TOOL_HINTS[panel.current_tool()], sample, world.plane, walls]

	if _template_tool():
		var more := _templates().hint_lines()

		if not more.is_empty():
			line += "\n" + more

	if panel.current_tool() == BuildPanel.Tool.ROOF:
		line += "\nRoof: %s." % panel.roof_summary()

	if panel.current_tool() in _STYLE_TOOLS:
		line += "\nWall style: %s." % _stroke_style()

	if panel.current_tool() == BuildPanel.Tool.DECOR:
		line += "\nDecor: %s." % panel.decor_summary()

	var problem := _outline_problem()

	if not problem.is_empty():
		return line + "\n" + problem

	if _note.is_empty():
		return line

	return line + "\n" + _note


## The size of the drag, beside the cursor, or "".
func readout() -> String:
	if _template_tool():
		return _templates().readout()

	if not dragging():
		return ""

	if panel.current_tool() == BuildPanel.Tool.WALL_LINE:
		return "%d edges, plane %d" % [StructureTools.line_edges(_anchor, _end).size(),
			world.plane]

	if panel.current_tool() == BuildPanel.Tool.ROOF:
		return _roof_readout()

	if panel.current_tool() == BuildPanel.Tool.WALL_STYLE:
		return "%d wall tiles, radius %.1f, plane %d" % [_stroke_tiles(),
			panel.brush_radius(), world.plane]

	var rect := drag_rect()
	var base := StructureTools.base_height(world.chunks,
		StructureTools.rect_corners(rect), panel.room_options().base)

	return "%d x %d tiles, plane %d, base %d" % [rect.size.x, rect.size.y, world.plane,
		base]


## The size of the room under the roof, and the plane of the roof.
func _roof_readout() -> String:
	var target := _roof_target()

	if not target["problem"].is_empty():
		return "no room"

	var rect: Rect2i = target["rect"]

	return "%d x %d tiles, roof on plane %d" % [rect.size.x, rect.size.y,
		world.plane + 1]


## The rectangle of tiles between the anchor and the end of a drag.
func drag_rect() -> Rect2i:
	var low: Vector2i = Vector2i(_anchor).min(_end)
	var high: Vector2i = Vector2i(_anchor).max(_end)

	return Rect2i(low, high - low + Vector2i.ONE)


# ─── The tools ──────────────────────────────────────────────────────────────

func _drag_point(point: Vector2) -> Vector2i:
	if panel.current_tool() == BuildPanel.Tool.WALL_LINE:
		return StructureTools.corner_at(point)

	return ChunkSet.tile_at(point)


func _wall_line() -> void:
	var edit := TerrainEdit.for_world(world)
	var count := StructureTools.line_edges(_anchor, _end).size()

	_finish(edit, StructureTools.wall_line(world.chunks, edit, _anchor, _end, _shift,
		panel.wall_style()), "Wall line, %d edges" % count)


func _room() -> void:
	var edit := TerrainEdit.for_world(world)
	var rect := drag_rect()
	var problem := StructureTools.room(world.chunks, edit, rect, panel.room_options(),
		_shift)

	_finish(edit, problem, "Room %d x %d" % [rect.size.x, rect.size.y])


## A click finds the room around the tile. A drag takes the rectangle.
func _level_above() -> void:
	var tiles: Array[Vector2i] = []

	if _anchor == _end:
		var found := RoomFill.fill(world.chunks, _anchor)

		if not found["closed"]:
			_note = "Not a room: the fill found no closed walls. Drag a rectangle."
			return

		tiles = found["tiles"]
	else:
		tiles = StructureTools.rect_tiles(drag_rect())

	world.refresh_new_chunks()

	var edit := TerrainEdit.for_world(world)
	var problem := StructureTools.level_above(world.plane_sets(), edit, world.plane,
		tiles, panel.floor_name(), _shift)

	_finish(edit, problem, "Level above, %d tiles" % tiles.size())


func _doorway(point: Vector2) -> void:
	var edge := StructureTools.edge_at(point)
	var edit := TerrainEdit.for_world(world)

	_finish(edit, StructureTools.doorway(world.chunks, edit, edge[0], edge[1], _shift),
		"Doorway")


func _stairs(tile: Vector2i) -> void:
	world.refresh_new_chunks()

	var edit := TerrainEdit.for_world(world)
	var problem := StructureTools.stairs(world.plane_sets(), edit, world.plane, tile,
		panel.climb_kind(), panel.floor_name(), _shift)

	_finish(edit, problem, "Stairs")


## A click places the decor of the options on `tile`, or with Shift removes
## the decor there.
func _decor(tile: Vector2i) -> void:
	var edit := TerrainEdit.for_world(world)
	var kind := panel.decor_kind()
	var problem := StructureTools.decor(world.chunks, edit, tile, kind,
		panel.decor_turn(), _shift)
	var label := "Remove decor" if _shift else "Decor %s" % kind

	_finish(edit, problem, label)


## A click finds the room around the tile. A drag takes the rectangle.
func _roof() -> void:
	var target := _roof_target()

	if not target["problem"].is_empty():
		_note = target["problem"]
		return

	var rect: Rect2i = target["rect"]
	var options := panel.roof_options()

	world.refresh_new_chunks()

	var edit := TerrainEdit.for_world(world)
	var problem := StructureTools.roof(world.plane_sets(), edit, world.plane, rect,
		options, _shift)
	var label := "%s roof %d x %d" % [RoofShapes.SHAPE_NAMES[options.shape],
		rect.size.x, rect.size.y]

	_finish(edit, problem, label)

	if problem.is_empty() and _note.is_empty() and not _shift \
			and world.upper_planes == TerrainWorld.UpperPlanes.HIDDEN:
		_note = "The roof is on plane %d. The World tab shows the planes above." \
			% (world.plane + 1)


## The roof rectangle of the drag: the room around a click, or the dragged
## rectangle. `{rect, problem}`. Found once for each anchor and end.
func _roof_target() -> Dictionary:
	if _target_of == [_anchor, _end]:
		return _target

	if _anchor == _end:
		_target = StructureTools.fill_rect(RoomFill.fill(world.chunks, _anchor))
	else:
		_target = {"rect": drag_rect(), "problem": ""}

	_target_of = [_anchor, _end]

	return _target


## The reason that the outline of the drag is red, or "".
func _outline_problem() -> String:
	if not _shows_outline():
		return ""

	var target := _roof_target()

	if not target["problem"].is_empty():
		return target["problem"]

	return StructureTools.roof_plan(world.plane_sets(), world.plane, target["rect"],
		panel.roof_options())["problem"]


## True while a drag of the Roof tool builds a roof.
func _shows_outline() -> bool:
	return dragging() and panel.current_tool() == BuildPanel.Tool.ROOF and not _shift


## Draw the plan of the Roof tool, or hide the outline.
func _refresh_outline() -> void:
	var heights := {}
	var color := COLOR_OUTLINE

	if _shows_outline() and _roof_target()["problem"].is_empty():
		var plan := StructureTools.roof_plan(world.plane_sets(), world.plane,
			_roof_target()["rect"], panel.roof_options())

		heights = plan["heights"]

		if not plan["problem"].is_empty():
			color = COLOR_OUTLINE_REFUSED

	world.show_outline(heights, color)


func _sample(tile: Vector2i) -> void:
	var chunks := world.chunks
	var decor := StructureTools.decor_at(chunks, tile)

	panel.sample(chunks.get_floor(tile), chunks.get_area(tile),
		chunks.get_wall_style(tile), decor)
	_note = "Sampled %s, %s, and the %s wall style from %s." % [chunks.get_floor(tile),
		chunks.get_area(tile), chunks.get_wall_style(tile), tile]

	if not decor.is_empty():
		_note += " Decor: %s." % panel.decor_summary()


# ─── The Wall style brush ───────────────────────────────────────────────────

## One dab of the Wall style brush at `point`, a point in tile space.
func _dab(point: Vector2) -> void:
	var tiles := TerrainBrushes.tiles_in_circle(point, panel.brush_radius())

	StructureTools.paint_wall_style(world.chunks, _stroke, tiles, _stroke_style())
	world.queue_rebuild(_stroke.chunk_keys())


## The style that the brush paints: the default style with Shift.
func _stroke_style() -> String:
	if _shift and panel.current_tool() == BuildPanel.Tool.WALL_STYLE:
		return _Const.TILE_DEFAULT_WALL_STYLE

	return panel.wall_style()


## The tiles that the stroke changed so far.
func _stroke_tiles() -> int:
	return 0 if _stroke == null else _stroke.size()


## Put the stroke in the history, and keep it out of [method cancel].
func _end_stroke() -> void:
	var edit := _stroke

	_stroke = null
	_finish(edit, "", "Wall style, %d wall tiles" % edit.size())

	if edit.is_empty():
		_note = "No wall under the brush. The brush paints only the tiles with a wall."


## The brush ring of the Wall style tool, or none for another tool.
func _refresh_ring() -> void:
	if panel.current_tool() == BuildPanel.Tool.WALL_STYLE and _hover != null:
		world.show_ring(_hover, panel.brush_radius())
	else:
		world.show_ring(null, 0.0)


## Commit the edit, or keep the problem for the hint line. Then run the live
## check on the tiles of the edit.
func _finish(edit: TerrainEdit, problem: String, label: String) -> void:
	if not problem.is_empty():
		_note = problem
		return

	if edit.is_empty():
		_note = "%s changed nothing." % label
		return

	world.queue_rebuild(edit.chunk_keys())
	commit.call(edit, label)
	_note = _live_check(edit)


## The live check of the tiles of one edit, as one line, or "".
func _live_check(edit: TerrainEdit) -> String:
	var found := TerrainChecks.check_tiles(world.plane_sets(), edit.tiles())

	if found.is_empty():
		return ""

	var line := "Live check: " + TerrainChecks.describe(found[0])

	if found.size() > 1:
		line += " (and %d more)" % (found.size() - 1)

	return line


# ─── The marks ──────────────────────────────────────────────────────────────

func _refresh_marks() -> void:
	if _template_tool():
		_templates().refresh_marks()
		return

	var color := COLOR_REMOVE if _shift else COLOR_ADD

	# A refused roof marks its rectangle in the colour of its red outline.
	if not _outline_problem().is_empty():
		color = COLOR_OUTLINE_REFUSED

	world.show_marks(_mark_paths(), color)
	_refresh_outline()


## The paths of the marks: the drag, or what a click would change.
func _mark_paths() -> Array:
	if panel.current_tool() == BuildPanel.Tool.WALL_STYLE:
		return []

	if dragging():
		if panel.current_tool() == BuildPanel.Tool.WALL_LINE:
			var stop := StructureTools.snap_line(_anchor, _end)

			return [[TerrainBrushes.corner_point(_anchor), TerrainBrushes.corner_point(stop)]]

		if panel.current_tool() == BuildPanel.Tool.ROOF \
				and _roof_target()["problem"].is_empty():
			return [TerrainOverlay.rect_path(_roof_target()["rect"])]

		return [TerrainOverlay.rect_path(drag_rect())]

	if _hover == null:
		return []

	if panel.current_tool() == BuildPanel.Tool.DOORWAY:
		var edge := StructureTools.edge_at(_hover)

		return [TerrainOverlay.edge_path(edge[0], edge[1])]

	var tile := ChunkSet.tile_at(_hover)
	var paths := [TerrainOverlay.rect_path(Rect2i(tile, Vector2i.ONE))]

	# The Decor tool marks the edge that the front of the next decor faces.
	if panel.current_tool() == BuildPanel.Tool.DECOR and not _shift:
		paths.append(TerrainOverlay.edge_path(tile, _FRONT_EDGES[panel.decor_turn()]))

	return paths
