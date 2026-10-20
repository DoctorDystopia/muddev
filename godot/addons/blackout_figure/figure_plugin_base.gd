@tool
class_name FigureEditorBase
extends EditorPlugin
## What the figure workbench and the gear editor share of the editor
## contract (DESIGN-0014 section 22): the dock, the workbench that the
## editor edits, the undo seam, the jobs, the save, the click in the 3D
## view, the hint, and the selection.
##
## A subclass gives its dock, its scene, its handlers, the refresh of its
## panels, and what to show for a selected part. The hooks are the
## routines with a `_` and a comment that names the subclass.
##
## ## A click selects a part or a shape
##
## The editor does not select a node with no owner on a click, and each
## part is such a node. Thus, this plugin finds the mesh below the mouse,
## and it selects the node by code. The Godot move, turn, and scale tools
## then work on the node. This plugin needs no gizmo of its own.
##
## A click on a shape of a shape list selects the node of that shape, and
## the tools move the shape in the space of its part. A second click on
## the same shape selects the whole part. A click on the node of a model
## selects the part at once: the place of a model node is in the model
## file. A click on no part selects the workbench node again. The editor
## clears the selection on such a click, and the dock would then stop. An
## empty selection of any other kind selects the workbench again too.
## When the author selects another node, the status box says so.
##
## ## Two kinds of undo entry
##
## A change from the dock is one entry of [FigureHistory]: it gives the old
## or the new content of one figure file to [method FigureWorkbench.put].
## A move with a Godot tool is an entry of the editor: it moves the node,
## and [method FigureWorkbench.sync_from_nodes] writes the place into the
## file. A field that the author drags makes one entry, not one for each
## step.
##
## ## Saving
##
## Ctrl+S saves the scene, and the editor then calls
## [method _save_external_data], which writes each changed figure file. The
## editor also asks about unsaved figure files when it closes.
##
## A save of a rig or of a worn look of the repository also writes the
## served `figure.json` again, through [FigurePipeline] on a thread. The
## check of the model pipeline fails on a stale one.
##
## ## One job at a time
##
## The pipeline runs share one [FigureJob], through [method _start_job].
## While it runs, the button that started it is off, and the status box
## says so. A second run waits for the author.
##
## ## The two scenes
##
## The figure workbench and the gear editor are two scenes on the same
## figure files. "Open gear editor" and "Open figure workbench" switch.
## With unsaved files, the switch asks to save them first. A plugin that
## takes its scene again reads the files again when the other scene wrote
## them.

## The mouse can move this many pixels between a press and a release, and
## the two are still a click.
const CLICK_SLOP := 4.0

## The first line of the hint: the keys. R scales a part here. In the
## terrain editor, R is no key of a tool.
const HINT_KEYS := "Click a part to select it, or a shape of it. W: move. E: turn. " \
	+ "R: scale (not a radius). Ctrl+Z: undo. Ctrl+S: save."

## The second line of the hint for a selected part: the part, its look,
## its bone, and the body type. The fit note follows when the part has a
## fit row on that body type.
const HINT_PART := "%s / %s / on %s of %s"
const HINT_FIT := " (fit row)"

## The second line of the hint for a selected shape: the shape, then the
## part as above.
const HINT_SHAPE := "shape %d (%s) of "

## The second line of the hint with no selected part: the body type, and
## the count of the outfit.
const HINT_BODY := "%s, %d item(s) in the outfit"

## The second line of the hint for a selected bone mark.
const HINT_BONE := "the bone %s of %s: W moves the bone"

## The second line of the hint for a selected served model: the item, and
## the body type.
const HINT_SERVED := "the served model of %s, on %s"

## The status box says this when another node is selected.
const SELECT_BENCH_STATUS := "Select the %s node to use the dock."

## The question before a switch of the scene with unsaved files.
const SWITCH_QUESTION := "Save %d changed figure file(s) and open the other scene?"

## The name of the figure-set job, for the status box.
const JOB_FIGURE_SET := "the served figure.json"

const JOB_BUSY := "A build runs now: %s. Wait until it ends."

## The kinds of a figure file that the served `figure.json` holds.
const FIGURE_SET_KINDS := [FigureStore.KIND_RIG, FigureStore.KIND_LOOK,
	FigureStore.KIND_PALETTE]

const FIGURE_SET_WRITTEN := "Wrote the served figure.json again."
const FIGURE_SET_STALE := "The served figure.json is stale now. In blackout/, run: " \
	+ "python -m assets.pipeline figure-set"

var _dock: FigureDockBase

## The workbench that the editor edits now, or null.
var _bench: FigureWorkbench

## The last workbench that the editor edited. A save writes its files when
## another node is selected.
var _last_bench: FigureWorkbench

## The budget table of the Check tab ([FigureChecks]). The dock keeps it in
## its options file.
var _budgets := {}

## The mouse position of the last press, or null.
var _press: Variant = null

var _mouse := Vector2.ZERO

## The one job of the pipeline runs.
var _job := FigureJob.new()

## The undo seam, and what each handler may reach of this plugin.
var _history: FigureHistory
var _context: FigureHandlerContext


func _enter_tree() -> void:
	_dock = _make_dock()
	_dock.body_changed.connect(func(_body_key: String) -> void: _refresh_panels())
	_dock.save_requested.connect(_save)
	_dock.reload_requested.connect(_on_reload)
	_dock.open_requested.connect(func() -> void: _open_scene(_scene_path()))
	_dock.other_requested.connect(_on_other_requested)
	_history = FigureHistory.new(get_undo_redo(), _bench_or_null, _dock.set_status)
	_context = FigureHandlerContext.new(_dock, _history, _plugin_calls())
	_make_handlers()
	_wire_handlers()
	add_control_to_dock(DOCK_SLOT_RIGHT_UL, _dock)
	_after_enter_tree()
	EditorInterface.get_selection().selection_changed.connect(_on_selection_changed)


func _exit_tree() -> void:
	# A thread that nothing waits for gives an error at exit.
	_job.wait()
	EditorInterface.get_selection().selection_changed.disconnect(_on_selection_changed)
	remove_control_from_docks(_dock)
	_dock.queue_free()


# ─── The hooks of a subclass ────────────────────────────────────────────────

## The dock of this plugin. A subclass gives it.
func _make_dock() -> FigureDockBase:
	return FigureDockBase.new()


## The scene of this plugin, and the scene of the other plugin. A subclass
## gives them.
func _scene_path() -> String:
	return ""


func _other_scene_path() -> String:
	return ""


## True when this plugin edits `bench`. A subclass decides.
func _is_mine(_bench_node: FigureWorkbench) -> bool:
	return false


## The name of the workbench node, for the status box.
func _bench_name() -> String:
	return "FigureWorkbench"


## Make the handlers of each panel of the dock, and give each one its
## panel. A subclass gives both.
func _make_handlers() -> void:
	pass


func _wire_handlers() -> void:
	pass


## What a subclass adds to the tree after the dock.
func _after_enter_tree() -> void:
	pass


## Connect the signals of a workbench to the handlers, and disconnect
## them. A subclass gives both.
func _connect_bench(_bench_node: FigureWorkbench) -> void:
	pass


func _disconnect_bench(_bench_node: FigureWorkbench) -> void:
	pass


## The plugin edits a workbench: what a subclass shows before the refresh.
func _on_bench_taken() -> void:
	pass


## Each panel, the outfit bar, and the cost line, for the selected body
## type. A subclass gives it.
func _refresh_panels() -> void:
	pass


## The Colors tab only, and the Clips tab only. A subclass with the tab
## gives it.
func _refresh_colors() -> void:
	pass


func _refresh_clips() -> void:
	pass


## The budget line and the line of the selected item. A subclass gives it.
func _refresh_cost() -> void:
	pass


## A job runs, or ended: turn the buttons of the jobs off or on.
func _set_busy(_busy: bool) -> void:
	pass


## A file of the store got new content. A subclass adds what follows.
func _on_file_changed(_kind: String, _key: String) -> void:
	pass


## The editor selected one part, or one shape of it. `shape_index` is -1
## for the part. A subclass shows it in its panels.
func _show_selected(_look_key: String, _part_name: String, _shape_index: int,
		_body_key: String) -> void:
	pass


## The node to select again after a change left the selection empty, or
## null for the workbench. A subclass gives it.
func _node_to_reselect() -> Node3D:
	return null


# ─── The context of the handlers ────────────────────────────────────────────

## The routines of this plugin that a handler may call, by the keys of
## [FigureHandlerContext].
func _plugin_calls() -> Dictionary:
	return {
		FigureHandlerContext.BENCH: _bench_or_null,
		FigureHandlerContext.REFRESH_PANELS: _refresh_panels,
		FigureHandlerContext.REFRESH_COLORS: _refresh_colors,
		FigureHandlerContext.REFRESH_CLIPS: _refresh_clips,
		FigureHandlerContext.REFRESH_COST: _refresh_cost,
		FigureHandlerContext.SELECT_PART: _select_part,
		FigureHandlerContext.SELECT_SHAPE: _select_shape,
		FigureHandlerContext.SELECT_NODE: _select,
		FigureHandlerContext.RESELECT: _reselect,
		FigureHandlerContext.START_JOB: _start_job,
		FigureHandlerContext.BUDGETS: _budgets_of,
		FigureHandlerContext.SET_BUDGETS: _set_budgets,
	}


## The play bar follows the clip while it plays. An ended job gives its
## result to the author.
func _process(_delta: float) -> void:
	if _has_bench() and _bench.is_playing():
		_dock.play_bar().set_time(_bench.clip_time())

	if _job.is_done():
		_job.finish()
		_set_busy(false)


func _handles(object: Object) -> bool:
	var bench := FigureWorkbench.of(object)

	return bench != null and _is_mine(bench)


func _edit(object: Object) -> void:
	var bench := FigureWorkbench.of(object)

	if bench == _bench:
		return

	if _has_bench():
		_bench.changed.disconnect(_on_bench_changed)
		_bench.reloaded.disconnect(_refresh)
		_disconnect_bench(_bench)

	_bench = bench

	if _bench == null:
		return

	var again := _bench == _last_bench

	_last_bench = _bench
	_bench.changed.connect(_on_bench_changed)
	_bench.reloaded.connect(_refresh)
	_connect_bench(_bench)

	# The other scene can write the files while this one is away.
	if again:
		_bench.reload_if_changed()

	_restore_session()
	_budgets = _dock.saved_budgets()
	_dock.restore_folds()
	_on_bench_taken()
	_refresh()
	update_overlays()


## A workbench with no outfit gets the outfit of the last session. The
## colors and the kit of the character come back the same way.
func _restore_session() -> void:
	if _bench.outfit().is_empty():
		_bench.set_outfit(_dock.saved_outfit())

	if _bench.figure_colors().is_empty():
		_bench.set_figure_colors(_dock.saved_figure_colors())

	if _bench.kit().is_empty():
		_bench.set_kit(_dock.saved_kit())


func _has_bench() -> bool:
	return _bench != null and is_instance_valid(_bench)


## The workbench that the editor edits now, or null. The handlers and the
## undo seam read the bench through this routine.
func _bench_or_null() -> FigureWorkbench:
	if not _has_bench():
		return null

	return _bench


func _budgets_of() -> Dictionary:
	return _budgets


func _set_budgets(budgets: Dictionary) -> void:
	_budgets = budgets


# ─── Saving and loading ─────────────────────────────────────────────────────

func _save_external_data() -> void:
	if is_instance_valid(_last_bench) and _last_bench.has_unsaved_changes():
		_save()


func _get_unsaved_status(_for_scene: String) -> String:
	if not is_instance_valid(_last_bench) or not _last_bench.has_unsaved_changes():
		return ""

	return "The %s has unsaved figure files. Save them?" % _bench_name()


func _save() -> void:
	if not is_instance_valid(_last_bench):
		return

	var saved := _last_bench.save()
	var lines := PackedStringArray(["Saved %d figure file(s): %s" % [saved.size(),
		", ".join(saved)]])

	lines.append_array(_last_bench.store.errors)
	_dock.set_unsaved(_last_bench.unsaved_names())

	if _last_bench.writes_repo_figures() and _in_figure_set(saved):
		_start_figure_set(lines)
		return

	_dock.set_status("\n".join(lines))


## True when a saved file is a rig, a worn look, or the palette. The served
## `figure.json` holds those three kinds. `saved` holds the names of
## [method FigureStore.name_of].
static func _in_figure_set(saved: PackedStringArray) -> bool:
	for file_name: String in saved:
		if FigureStore.kind_of_name(file_name) in FIGURE_SET_KINDS:
			return true

	return false


## Write the served `figure.json` again, on a thread. `lines` is the report
## of the save, and the result of the pipeline joins it when the job ends.
func _start_figure_set(lines: PackedStringArray) -> void:
	var started := _job.start(JOB_FIGURE_SET, FigurePipeline.write_figure_set,
		func(result: Dictionary) -> void:
			lines.append(_figure_set_line(result))
			_dock.set_status("\n".join(lines)))

	if not started:
		lines.append(FIGURE_SET_STALE)
		lines.append(JOB_BUSY % _job.label)

	_show_job(lines)


## The line of the status box for a result of the figure-set pipeline.
static func _figure_set_line(result: Dictionary) -> String:
	if result["ok"]:
		return FIGURE_SET_WRITTEN

	return FIGURE_SET_STALE + "\n" + str(result["output"])


## Run `work` on the one job, with `on_done` for its result. `lines` go to
## the status box, with the busy line when the job is taken. The handlers
## start a job here.
func _start_job(label: String, work: Callable, on_done: Callable,
		lines := PackedStringArray()) -> void:
	var started := _job.start(label, work, on_done)

	if not started:
		lines.append(JOB_BUSY % _job.label)

	_show_job(lines)


## Show `lines` and the running job in the status box, and turn the
## buttons of the jobs off while it runs.
func _show_job(lines: PackedStringArray) -> void:
	var shown := lines.duplicate()

	if _job.is_running():
		shown.append(_job.busy_text())
		_set_busy(true)

	_dock.set_status("\n".join(shown))


## "Revert". The store drops each unsaved change, so the entries of the
## undo history have nothing to return to.
func _on_reload() -> void:
	if not _has_bench():
		return

	var history := get_undo_redo()
	var dropped := _bench.unsaved_names()

	_bench.reload()
	history.clear_history(history.get_object_history_id(_bench))
	_dock.set_status("Read each figure file again. Dropped %d unsaved file(s)." % dropped.size())


## Open one of the two scenes, and select its workbench node.
func _open_scene(path: String) -> void:
	EditorInterface.open_scene_from_path(path)
	await get_tree().process_frame

	var root := EditorInterface.get_edited_scene_root()

	if root == null:
		return

	for child: Node in root.get_children():
		if child is FigureWorkbench:
			_select(child)


## "Open the other scene". With unsaved files, it asks to save them first.
## The plugin of the other scene reads the files again when it takes them.
func _on_other_requested() -> void:
	if not is_instance_valid(_last_bench) or not _last_bench.has_unsaved_changes():
		_open_scene(_other_scene_path())
		return

	_dock.confirm(SWITCH_QUESTION % _last_bench.unsaved_names().size(), func() -> void:
		_save()
		_open_scene(_other_scene_path()))


# ─── The dock ───────────────────────────────────────────────────────────────

## The body types, each panel, and the report of the store.
func _refresh() -> void:
	if not _has_bench():
		return

	var lines := PackedStringArray(["%d body type(s) in %s." % [
		_bench.body_keys().size(), _bench.directory()]])

	if not _bench.writes_repo():
		lines.append("A scratch directory: nothing here reaches the repository.")

	lines.append_array(_bench.store.errors)
	_dock.set_bodies(_bench.body_keys())
	_dock.set_unsaved(_bench.unsaved_names())
	_refresh_panels()
	_dock.set_status("\n".join(lines))


## A file of the store got new content: from the dock, from the undo
## history, or from a moved node. The Save button counts the unsaved
## files.
func _on_bench_changed(kind: String, key: String) -> void:
	if kind == FigureStore.KIND_RIG:
		_dock.set_bodies(_bench.body_keys())

	_dock.set_unsaved(_bench.unsaved_names())
	_on_file_changed(kind, key)
	_refresh_panels()
	_reselect()
	update_overlays()


# ─── The selection ──────────────────────────────────────────────────────────

func _forward_3d_gui_input(camera: Camera3D, event: InputEvent) -> int:
	if not _has_bench():
		return AFTER_GUI_INPUT_PASS

	if event is InputEventMouseMotion:
		_mouse = event.position
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			_press = event.position
		elif _press != null and event.position.distance_to(_press) <= CLICK_SLOP:
			_pick_after_click(_bench, camera.project_ray_origin(event.position),
				camera.project_ray_normal(event.position))

	# The editor gets each event also: a drag of a gizmo is its work.
	return AFTER_GUI_INPUT_PASS


func _forward_3d_draw_over_viewport(overlay: Control) -> void:
	if _has_bench():
		ToolHint.draw(overlay, _hint(), "", _mouse)


## The three lines of the hint: the keys, the selected part or the body
## type, and the last line of the status box.
func _hint() -> String:
	var status := _dock.status().get_slice("\n", 0)

	return "\n".join(PackedStringArray([HINT_KEYS, _hint_subject(), status]))


## The second line of the hint. For a selected part: "part / look / on
## bone of body (fit row)". For a selected shape: the shape, then the part.
## For a selected bone mark: the bone and the body type. With none: the
## body type and the outfit.
func _hint_subject() -> String:
	var nodes := EditorInterface.get_selection().get_selected_nodes()
	var node: Node = nodes[0] if nodes.size() == 1 else null
	var shape := FigureBuilder.shape_id(node)
	var id: Array = shape.slice(0, 2) if not shape.is_empty() else FigureBuilder.part_id(node)

	if node != null and node.name == FigureWorkbench.MARK_NAME:
		return HINT_BONE % [_bench.marked_bone(), _bench.body_of(node)]

	if not id.is_empty() and id[1] == FigureLook.SERVED_PART:
		return HINT_SERVED % [id[0], _bench.body_of(node)]

	if id.is_empty() or not _bench.store.has(FigureStore.KIND_LOOK, id[0]):
		return HINT_BODY % [_dock.active_body(), _bench.outfit().size()]

	var body_key := _bench.body_of(node)
	var look: FigureLook = _bench.store.looks[id[0]]
	var row: Dictionary = look.resolved(_bench.store.looks).part(id[1])
	var line := HINT_PART % [id[1], id[0], row.get("bone", "?"), body_key]

	if not look.fit_row(body_key, id[1]).is_empty():
		line += HINT_FIT

	if not shape.is_empty():
		var shapes: Array = row.get("shapes", [])
		var kind: String = "?" if shape[2] >= shapes.size() else shapes[shape[2]].get("shape", "?")

		line = HINT_SHAPE % [shape[2], kind] + line

	return line


## Select the node below a click: the shape, the part on a second click on
## the same shape, the part at once for a model, or the workbench for a
## click on no part. The editor handles the click first, and it clears the
## selection for a click on a node with no owner. Thus, this routine waits
## one frame.
func _pick_after_click(bench: FigureWorkbench, origin: Vector3,
		direction: Vector3) -> void:
	var selected := EditorInterface.get_selection().get_selected_nodes()
	var before: Node = selected[0] if selected.size() == 1 else null

	await get_tree().process_frame

	if not is_instance_valid(bench):
		return

	var instance := bench.shape_at(origin, direction)

	if instance == null:
		_select(bench)
	elif FigureBuilder.shape_id(instance).is_empty() or instance == before:
		_select(instance.get_parent())
	else:
		_select(instance)


## Select the node of one part of one worn look, on the stand of the
## selected body type.
func _select_part(look_key: String, part_name: String) -> void:
	if not _has_bench():
		return

	var node := _bench.part_node(_dock.active_body(), look_key, part_name)

	if node != null:
		_select(node)


## Select the node of one shape of one part, on the stand of the selected
## body type.
func _select_shape(look_key: String, part_name: String, shape_index: int) -> void:
	if not _has_bench():
		return

	var node := _bench.shape_node(_dock.active_body(), look_key, part_name, shape_index)

	if node != null:
		_select(node)


static func _select(node: Node) -> void:
	var selection := EditorInterface.get_selection()
	var nodes := selection.get_selected_nodes()

	if nodes.size() == 1 and nodes[0] == node:
		return

	selection.clear()
	selection.add_node(node)


## Select the part or the shape of the dock again when its node left the
## selection. A part that moves to another bone leaves the tree for a
## moment, and the editor then drops it from the selection. A part of an
## item that leaves the outfit has no node, and the workbench then stays
## selected.
func _reselect() -> void:
	if not _has_bench() or not EditorInterface.get_selection().get_selected_nodes().is_empty():
		return

	var node := _node_to_reselect()

	_select(_bench if node == null else node)


## The editor selected a node: show its part, or its shape, in the dock.
##
## With no workbench, the editor stopped editing it. An empty selection
## then selects the last workbench again, so the dock stays alive. A
## selection of another node tells the author what to select.
func _on_selection_changed() -> void:
	var nodes := EditorInterface.get_selection().get_selected_nodes()

	if not _has_bench():
		_keep_dock_alive(nodes)
		return

	if nodes.size() != 1 or FigureWorkbench.of(nodes[0]) != _bench:
		return

	update_overlays()

	var shape := FigureBuilder.shape_id(nodes[0])
	var id: Array = shape.slice(0, 2) if not shape.is_empty() \
		else FigureBuilder.part_id(nodes[0])

	if id.is_empty():
		return

	var body_key := _bench.body_of(nodes[0])

	if _dock.active_body() != body_key:
		_dock.select_body(body_key)
		_refresh_panels()

	_show_selected(id[0], id[1], shape[2] if not shape.is_empty() else -1, body_key)


## The editor edits no workbench now. An empty selection selects the last
## workbench again. Another node gets a line in the status box.
func _keep_dock_alive(nodes: Array[Node]) -> void:
	var alive := is_instance_valid(_last_bench) and _last_bench.is_inside_tree()

	if nodes.is_empty() and alive:
		_select(_last_bench)
	elif not nodes.is_empty():
		_dock.set_status(SELECT_BENCH_STATUS % _bench_name())
