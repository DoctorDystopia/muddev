@tool
class_name TemplateInput
extends RefCounted
## The mouse and the keys of the Select and the Place tools of the Build tab
## (DESIGN-0013 sections 6.6 and 6.7). [BuildInput] sends each event here
## while one of the two tools is on. [TileSelection], [StructureTemplate],
## and [StructurePlace] hold the rules.
##
## ## Select
##
## | Gesture | Does |
## |---|---|
## | Drag | Select a rectangle, in place of the selection |
## | Click inside a room | Select the room, and on every plane the floors and the roof over it |
## | Ctrl and a drag or a click | Add to the selection |
## | Shift and a drag or a click | Take out of the selection |
## | Delete | Delete the selection: [method StructurePlace.clear] |
## | Ctrl+C | Copy the selection to the clipboard |
## | Ctrl+V | Place the clipboard: the Place tool |
## | M | Move the selection: the Place tool, and a click clears the old tiles |
## | Esc | Drop the drag, else the selection |
##
## "Select every plane" in the Build tab takes the edited plane and each
## plane above it.
##
## ## Place
##
## The outline follows the mouse, centred on it. It is green, amber, or red,
## and the hint line names the reason of amber or red. A click writes the
## copy. R and Shift+R turn it, F mirrors it, Alt and a click replace the
## objects on its tiles, and Esc ends the tool. A copy of a template
## from the list stays on the tool, so the author places a market row with
## one click for each stall. A move ends on its click, and the tile
## selection then holds the moved tiles.
##
## A move keeps its planes. It writes plane 0 of its template on the plane of
## the capture ([member StructureTemplate.base_plane]). A pick of another
## tool ends the move. Thus a later Place click does not clear the old tiles.

const _Const := preload("res://autoload/blackout_constants.gd")

const COLOR_SELECTION := Color(0.35, 0.8, 1.0, 1.0)
const COLOR_OUTLINE_WARNING := Color(1.0, 0.75, 0.2, 1.0)

## The key of the template that Ctrl+C makes, and of the template of a move.
const CLIPBOARD_KEY := "clipboard"
const MOVE_KEY := "move"

var world: TerrainWorld
var panel: BuildPanel

## Commit one edit, or keep the problem: `(edit, problem, label) -> void`.
## [BuildInput] gives its own, so the live check runs on each edit.
var finish: Callable

## Show one line in the hint line: `(text) -> void`.
var say: Callable

## Where the templates live, as an OS path. Empty is the world template
## directory. A test sets a scratch directory here.
var template_directory := ""

var selection := TileSelection.new()

## The template that Ctrl+C made, or null.
var clipboard: StructureTemplate = null

## The template of the outline, as R and F left it, and the row of the
## template list that it came from. Null when none reads.
var _placing: StructureTemplate = null
var _placing_from := ""
var _load_problem := ""

## The tile selection that a move clears. Empty when no move is on.
var _moving := {}

## The plan under the mouse, from [method StructurePlace.plan], or empty.
var _plan := {}

var _anchor: Variant = null
var _end: Variant = null
var _hover: Variant = null
var _shift := false
var _ctrl := false
var _alt := false


static func handles(tool_index: int) -> bool:
	return tool_index in [BuildPanel.Tool.SELECT, BuildPanel.Tool.PLACE]


func dragging() -> bool:
	return _anchor != null


func cancel() -> void:
	_anchor = null
	_end = null


## True while a move is on: the Place tool holds the tile selection.
func moving() -> bool:
	return not _moving.is_empty()


## A choice of the Build tab changed. A tool other than Place ends a move.
func on_panel_changed() -> void:
	if moving() and panel.current_tool() != BuildPanel.Tool.PLACE:
		_moving = {}
		_placing_from = ""
		_placing = null


func directory() -> String:
	if template_directory.is_empty():
		return StructureTemplate.world_directory()

	return template_directory


# ─── Events ─────────────────────────────────────────────────────────────────

func on_motion(point: Variant, shift: bool, alt: bool) -> bool:
	_hover = null if point == null else ChunkSet.tile_at(point)
	_shift = shift
	_alt = alt

	if dragging() and _hover != null:
		_end = _hover

	refresh_marks()

	return dragging()


func on_press(point: Variant, shift: bool, ctrl: bool, alt: bool) -> bool:
	if point == null:
		return false

	_hover = ChunkSet.tile_at(point)
	_shift = shift
	_ctrl = ctrl
	_alt = alt

	if panel.current_tool() == BuildPanel.Tool.PLACE:
		_place_click()
	else:
		_anchor = _hover
		_end = _hover

	refresh_marks()

	return true


func on_release() -> bool:
	if not dragging():
		return false

	_select_gesture()
	cancel()
	refresh_marks()

	return true


## Delete, Ctrl+C, Ctrl+V, M, and Esc of the Select tool, and R, F, and Esc
## of the Place tool. Returns true when the key is consumed.
func on_key(event: InputEventKey) -> bool:
	var used := _on_place_key(event) if panel.current_tool() == BuildPanel.Tool.PLACE \
		else _on_select_key(event)

	if used:
		refresh_marks()

	return used


func _on_select_key(event: InputEventKey) -> bool:
	var command := event.is_command_or_control_pressed()

	match event.keycode:
		KEY_DELETE:
			_delete()
		KEY_C when command:
			_copy()
		KEY_V when command:
			_paste()
		KEY_M:
			_start_move()
		KEY_ESCAPE:
			if dragging():
				cancel()
			elif not selection.is_empty():
				selection.clear()
			else:
				return false
		_:
			return false

	return true


func _on_place_key(event: InputEventKey) -> bool:
	match event.keycode:
		KEY_R:
			_transform(func(template: StructureTemplate) -> StructureTemplate:
				var turned := template.turned()

				if event.shift_pressed:
					turned = turned.turned().turned()

				return turned)
		KEY_F:
			_transform(func(template: StructureTemplate) -> StructureTemplate:
				return template.mirrored())
		KEY_ESCAPE:
			_end_place()
		_:
			return false

	return true


# ─── Select ─────────────────────────────────────────────────────────────────

## A release: the rectangle of a drag, or the room of a click.
func _select_gesture() -> void:
	var planes := TileSelection.planes_of(world.plane, panel.every_plane())

	if not (_shift or _ctrl):
		selection.clear()

	if _anchor != _end:
		selection.change_rect(_drag_rect(), planes, _shift)
		return

	var problem := selection.change_room(world.plane_sets(), world.plane, _anchor,
		panel.every_plane(), _shift)

	if not problem.is_empty():
		selection.change_rect(Rect2i(_anchor, Vector2i.ONE), planes, _shift)
		say.call("Not a room: the click took its tile only. Drag a rectangle for more.")


func _drag_rect() -> Rect2i:
	var low: Vector2i = Vector2i(_anchor).min(_end)
	var high: Vector2i = Vector2i(_anchor).max(_end)

	return Rect2i(low, high - low + Vector2i.ONE)


func _delete() -> void:
	if selection.is_empty():
		say.call("Select tiles first, then press Delete.")
		return

	var edit := TerrainEdit.for_world(world)
	var count := StructurePlace.clear(world.plane_sets(), edit, selection.keys)

	finish.call(edit, "", "Delete, %d tiles" % count)


## The template of the selection, or null with a line in the hint.
func _capture(template_key: String) -> StructureTemplate:
	if selection.is_empty():
		say.call("Select the tiles of the structure first.")
		return null

	var template := StructureTemplate.capture(world.plane_sets(), selection.keys,
		world.plane, template_key)

	if not template.error.is_empty():
		say.call(template.error)
		return null

	return template


func _copy() -> void:
	var template := _capture(CLIPBOARD_KEY)

	if template == null:
		return

	clipboard = template
	_placing_from = ""
	say.call("Copied %d x %d tiles on %d plane(s). Ctrl+V places a copy."
		% [template.size.x, template.size.y, template.layers.size()])


func _paste() -> void:
	if clipboard == null:
		say.call("The clipboard is empty. Select tiles, then press Ctrl+C.")
		return

	panel.choose_template(BuildPanel.CLIPBOARD)
	panel.select_tool(BuildPanel.Tool.PLACE)
	_placing_from = ""


func _start_move() -> void:
	var template := _capture(MOVE_KEY)

	if template == null:
		return

	_moving = selection.keys.duplicate()
	_placing = template
	panel.select_tool(BuildPanel.Tool.PLACE)
	say.call("Moving the selection. Click to place it. R turns, F mirrors, Esc cancels.")


## Save the tile selection as the template `template_key`. Returns the
## status line.
func save_template(template_key: String) -> String:
	var problem := StructureTemplate.key_problem(template_key)

	if not problem.is_empty():
		return problem

	var template := _capture(template_key)

	if template == null:
		return "No template saved: select the tiles of the structure first."

	var path := StructureTemplate.path_for(directory(), template_key)
	var verb := "Replaced" if FileAccess.file_exists(path) else "Saved"

	if template.write_file(path) != OK:
		return "Cannot write %s." % path

	reload_templates(template_key)

	return "%s the template %s: %d x %d tiles, %d plane(s), %d object(s), in %s." % [verb,
		template_key, template.size.x, template.size.y, template.layers.size(),
		template.objects.size(), path.get_file()]


## Read the template directory again, and pick `chosen` when it is not empty.
func reload_templates(chosen: String = "") -> void:
	panel.set_template_keys(StructureTemplate.list_keys(directory()), chosen)
	_placing_from = ""


# ─── Place ──────────────────────────────────────────────────────────────────

## The template of the outline, or null. A move keeps its own template. A
## new row of the template list reads its file.
func _template_now() -> StructureTemplate:
	if not _moving.is_empty():
		return _placing

	var choice := panel.template_choice()

	if choice == _placing_from:
		return _placing

	_placing_from = choice
	_placing = _load(choice)

	return _placing


func _load(choice: String) -> StructureTemplate:
	_load_problem = ""

	if choice == BuildPanel.CLIPBOARD:
		if clipboard == null:
			_load_problem = "The clipboard is empty. Select tiles, then press Ctrl+C."

		return clipboard

	var template := StructureTemplate.read_file(StructureTemplate.path_for(directory(), choice))

	if not template.error.is_empty():
		_load_problem = "The template %s does not read: %s" % [choice, template.error]
		return null

	return template


func _transform(change: Callable) -> void:
	var template := _template_now()

	if template != null:
		_placing = change.call(template)


## The world tile of the south-west tile of the outline: the outline is
## centred on the mouse.
func _origin(template: StructureTemplate) -> Vector2i:
	@warning_ignore("integer_division")
	return Vector2i(_hover) - Vector2i(template.size.x / 2, template.size.y / 2)


## The plane of plane 0 of the copy: the edited plane, or for a move the
## plane of its capture.
func _place_plane(template: StructureTemplate) -> int:
	return template.base_plane if moving() else world.plane


func _options() -> StructurePlace.Options:
	var options := panel.place_options()

	options.replace = _alt

	return options


func _place_click() -> void:
	var template := _template_now()

	if template == null:
		say.call(_load_problem)
		return

	world.refresh_new_chunks()

	var sets := world.plane_sets()
	var origin := _origin(template)
	var made := StructurePlace.plan(sets, template, origin, _place_plane(template), _options(),
		_moving)

	if not made["problem"].is_empty():
		say.call(made["problem"])
		return

	var edit := TerrainEdit.for_world(world)

	StructurePlace.clear(sets, edit, _moving)

	var result := StructurePlace.place(sets, edit, template, origin, _place_plane(template),
		_options(), _moving)

	_after_place(edit, template, result)


func _after_place(edit: TerrainEdit, template: StructureTemplate, result: Dictionary) -> void:
	if not result["problem"].is_empty():
		edit.replay_planes(world.plane_sets(), false)
		say.call(result["problem"])
		return

	var label := "Move, %d tiles" % result["keys"].size() if not _moving.is_empty() \
		else "Place %s" % template.key

	finish.call(edit, "", label)

	if not result["warning"].is_empty():
		say.call("Placed with a warning: " + result["warning"])

	if _moving.is_empty():
		return

	selection.clear()

	for at: Vector3i in result["keys"]:
		selection.keys[at] = true

	_end_place()


## End the Place tool: drop a move, and go back to the Select tool.
func _end_place() -> void:
	_moving = {}
	_placing_from = ""
	_placing = null
	panel.select_tool(BuildPanel.Tool.SELECT)


# ─── What the author sees ───────────────────────────────────────────────────

## Draw the selection or the outline.
func refresh_marks() -> void:
	_plan = {}

	if panel.current_tool() == BuildPanel.Tool.PLACE:
		_refresh_outline()
		return

	var paths := TileSelection.outline_paths(selection.footprint())

	if dragging():
		paths.append(TerrainOverlay.rect_path(_drag_rect()))

	var color := BuildInput.COLOR_REMOVE if _shift and dragging() else COLOR_SELECTION

	world.show_outline_layers([], color)
	world.show_marks(paths, color)


func _refresh_outline() -> void:
	var template := _template_now()

	if template == null or _hover == null:
		world.show_outline_layers([], COLOR_SELECTION)
		world.show_marks([], COLOR_SELECTION)
		return

	var origin := _origin(template)

	_plan = StructurePlace.plan(world.plane_sets(), template, origin, _place_plane(template),
		_options(), _moving)

	var color := _plan_color()
	var tiles := {}

	for layer: StructureTemplate.Layer in template.layers:
		for tile: Vector2i in template.covered_tiles(layer):
			tiles[origin + tile] = true

	world.show_outline_layers(_plan["heights"].values(), color)
	world.show_marks(TileSelection.outline_paths(tiles), color)


func _plan_color() -> Color:
	if not _plan["problem"].is_empty():
		return BuildInput.COLOR_OUTLINE_REFUSED

	if not _plan["warning"].is_empty():
		return COLOR_OUTLINE_WARNING

	return BuildInput.COLOR_OUTLINE


## The lines of the hint after the tool line.
func hint_lines() -> String:
	if panel.current_tool() == BuildPanel.Tool.SELECT:
		return "Selection: %s." % _selection_words()

	var template := _template_now()

	if template == null:
		return _load_problem

	var line := "Template: %s, %d x %d tiles, %d plane(s). %s." % [template.key,
		template.size.x, template.size.y, template.layers.size(), panel.place_summary()]

	if not _moving.is_empty():
		line += "\nMoving the selection. Esc cancels."

	return line + _plan_line()


func _plan_line() -> String:
	if _plan.is_empty():
		return ""

	if not _plan["problem"].is_empty():
		return "\nRefused: " + _plan["problem"]

	if not _plan["warning"].is_empty():
		return "\nWarning: " + _plan["warning"]

	return ""


func _selection_words() -> String:
	if selection.is_empty():
		return "none"

	var span := selection.plane_span()
	var planes := "plane %d" % span.x if span.x == span.y \
		else "planes %d to %d" % [span.x, span.y]
	var reach := "every plane" if panel.every_plane() else "this plane only"

	return "%d tiles on %s. A gesture takes %s" % [selection.size(), planes, reach]


## The size of a drag or of the outline, beside the cursor, or "".
func readout() -> String:
	if dragging():
		var rect := _drag_rect()

		return "%d x %d tiles" % [rect.size.x, rect.size.y]

	if _plan.is_empty():
		return ""

	var template := _template_now()
	var line := "%d x %d tiles, planes %d to %d, base %d" % [template.size.x,
		template.size.y, _place_plane(template), _place_plane(template) + template.top_plane(),
		_plan["base"]]

	if not _moving.is_empty():
		var shift: Vector2i = _origin(template) - template.origin

		line += ", moves (%d, %d)" % [shift.x, shift.y]

	return line
