@tool
extends EditorPlugin
## The Blackout figure workbench: routes a click in the 3D view to the part
## below it, each change of the dock to the editor history, and each save
## to the figure files.
##
## DESIGN-0014, Phases W1 to W6. Open
## `res://addons/blackout_figure/figure_workbench.tscn` and select the
## [FigureWorkbench] node to start. The panel is [FigureDock]. The rules
## live in the scripts under `edits/` and in the other `Figure*` classes,
## and the `tests/test_figure_*.tscn` scenes test them with no editor.
##
## This script keeps the editor contract only: the dock, the selection,
## the hint, the save, the jobs, and the refresh of each tab. One script
## under `handlers/` holds the handlers of each tab, [FigureHistory] holds
## the undo seam, and each handler reaches the plugin through one
## [FigureHandlerContext].
##
## ## A click selects a part
##
## The editor does not select a node with no owner on a click, and each
## part is such a node. Thus, this plugin finds the part below the mouse,
## and it selects the node by code. The Godot move, turn, and scale tools
## then work on the part. This plugin needs no gizmo of its own.
##
## A click on no part selects the workbench node again. The editor clears
## the selection on such a click, and the dock would then stop. An empty
## selection of any other kind selects the workbench again too. When the
## author selects another node, the status box says so.
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
## The three pipeline runs share one [FigureJob], through [method _start_job].
## While it runs, the button that started it is off, and the status box
## says so. A second run waits for the author.

const WORKBENCH_SCENE := "res://addons/blackout_figure/figure_workbench.tscn"

## The mouse can move this many pixels between a press and a release, and
## the two are still a click.
const CLICK_SLOP := 4.0

## The first line of the hint: the keys. R scales a part here. In the
## terrain editor, R is no key of a tool.
const HINT_KEYS := "Click a part to select it. W: move. E: turn. R: scale (not a radius). " \
	+ "Ctrl+Z: undo. Ctrl+S: save."

## The second line of the hint for a selected part: the part, its look,
## its bone, and the body type. The fit note follows when the part has a
## fit row on that body type.
const HINT_PART := "%s / %s / on %s of %s"
const HINT_FIT := " (fit row)"

## The second line of the hint with no selected part: the body type, and
## the count of the outfit.
const HINT_BODY := "%s, %d item(s) in the outfit"

## The second line of the hint for a selected bone mark.
const HINT_BONE := "the bone %s of %s: W moves the bone"

## The status box says this when another node is selected.
const SELECT_BENCH_STATUS := "Select the FigureWorkbench node to use the dock."

## The check runs this long after the last change of a file, in seconds.
const CHECK_DELAY := 0.5

## The name of the figure-set job, for the status box.
const JOB_FIGURE_SET := "the served figure.json"

const JOB_BUSY := "A build runs now: %s. Wait until it ends."

## The kinds of a figure file that the served `figure.json` holds.
const FIGURE_SET_KINDS := [FigureStore.KIND_RIG, FigureStore.KIND_LOOK,
	FigureStore.KIND_PALETTE]

const FIGURE_SET_WRITTEN := "Wrote the served figure.json again."
const FIGURE_SET_STALE := "The served figure.json is stale now. In blackout/, run: " \
	+ "python -m assets.pipeline figure-set"

var _dock: FigureDock

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

## The timer of the check after a change.
var _check_timer := Timer.new()

## The undo seam, and what each handler may reach of this plugin.
var _history: FigureHistory
var _context: FigureHandlerContext

## The handlers of each tab of the dock.
var _rig: FigureRigHandlers
var _body: FigureBodyHandlers
var _parts: FigurePartHandlers
var _gear: FigureGearHandlers
var _colors: FigureColorHandlers
var _families: FigureFamilyHandlers
var _clips: FigureClipHandlers
var _check: FigureCheckHandlers


func _enter_tree() -> void:
	_dock = FigureDock.new()
	_dock.body_changed.connect(func(_body_key: String) -> void: _refresh_panels())
	_dock.save_requested.connect(_save)
	_dock.reload_requested.connect(_on_reload)
	_dock.open_requested.connect(_on_open_requested)
	_history = FigureHistory.new(get_undo_redo(), _bench_or_null, _dock.set_status)
	_context = FigureHandlerContext.new(_dock, _history, _plugin_calls())
	_make_handlers()
	_wire_handlers()
	add_control_to_dock(DOCK_SLOT_RIGHT_UL, _dock)
	_check_timer.one_shot = true
	_check_timer.wait_time = CHECK_DELAY
	_check_timer.timeout.connect(func() -> void: _check.run_checks(false))
	add_child(_check_timer)
	EditorInterface.get_selection().selection_changed.connect(_on_selection_changed)


func _exit_tree() -> void:
	# A thread that nothing waits for gives an error at exit.
	_job.wait()
	EditorInterface.get_selection().selection_changed.disconnect(_on_selection_changed)
	remove_control_from_docks(_dock)
	_dock.queue_free()


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
		FigureHandlerContext.SELECT_NODE: _select,
		FigureHandlerContext.RESELECT: _reselect,
		FigureHandlerContext.START_JOB: _start_job,
		FigureHandlerContext.BUDGETS: _budgets_of,
		FigureHandlerContext.SET_BUDGETS: _set_budgets,
	}


func _make_handlers() -> void:
	_rig = FigureRigHandlers.new(_context)
	_gear = FigureGearHandlers.new(_context)
	_body = FigureBodyHandlers.new(_context, _gear)
	_parts = FigurePartHandlers.new(_context)
	_colors = FigureColorHandlers.new(_context)
	_families = FigureFamilyHandlers.new(_context)
	_clips = FigureClipHandlers.new(_context)
	_check = FigureCheckHandlers.new(_context, _rig, _clips)


## Give each handler its panel. The three part editors share one handler,
## and each one tells it which worn look it shows.
func _wire_handlers() -> void:
	_clips.connect_play_bar(_dock.play_bar())
	_rig.connect_panel(_dock.rig_panel())
	_body.connect_panel(_dock.body_panel())
	_parts.connect_panel(_dock.body_panel(), _dock.body_panel().edited_look)
	_gear.connect_panel(_dock.gear_panel())
	_families.connect_presentation(_dock.gear_panel())
	_parts.connect_panel(_dock.gear_panel().parts_panel(), _dock.gear_panel().edited_look)
	_gear.connect_outfit_bar(_dock.outfit_bar())
	_colors.connect_panel(_dock.colors_panel())
	_families.connect_panel(_dock.families_panel())
	_parts.connect_panel(_dock.families_panel(), _dock.families_panel().edited_look)
	_clips.connect_panel(_dock.clips_panel())
	_check.connect_panel(_dock.check_panel())


## The play bar follows the clip while it plays. An ended job gives its
## result to the author.
func _process(_delta: float) -> void:
	if _has_bench() and _bench.is_playing():
		_dock.play_bar().set_time(_bench.clip_time())

	if _job.is_done():
		_job.finish()
		_dock.gear_panel().set_importing(false)
		_dock.clips_panel().set_building(false)


func _handles(object: Object) -> bool:
	return FigureWorkbench.of(object) != null


func _edit(object: Object) -> void:
	var bench := FigureWorkbench.of(object)

	if bench == _bench:
		return

	if _has_bench():
		_bench.changed.disconnect(_on_bench_changed)
		_bench.reloaded.disconnect(_refresh)
		_bench.outfit_changed.disconnect(_gear.on_outfit_changed)
		_bench.figure_colors_changed.disconnect(_colors.on_figure_colors_changed)
		_bench.kit_changed.disconnect(_body.on_kit_changed)

	_bench = bench

	if _bench == null:
		return

	_last_bench = _bench
	_bench.changed.connect(_on_bench_changed)
	_bench.reloaded.connect(_refresh)
	_bench.outfit_changed.connect(_gear.on_outfit_changed)
	_bench.figure_colors_changed.connect(_colors.on_figure_colors_changed)
	_bench.kit_changed.connect(_body.on_kit_changed)

	# A workbench with no outfit gets the outfit of the last session. The
	# colors and the kit of the character come back the same way.
	if _bench.outfit().is_empty():
		_bench.set_outfit(_dock.saved_outfit())

	if _bench.figure_colors().is_empty():
		_bench.set_figure_colors(_dock.saved_figure_colors())

	if _bench.kit().is_empty():
		_bench.set_kit(_dock.saved_kit())

	_budgets = _dock.saved_budgets()
	_dock.gear_panel().set_author(_dock.saved_author())
	_dock.restore_folds()

	_refresh()
	update_overlays()


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

	return "The figure workbench has unsaved figure files. Save them?"


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
		_dock.gear_panel().set_importing(true)
		_dock.clips_panel().set_building(true)

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


## "Open the figure workbench": open the scene, and select its node.
func _on_open_requested() -> void:
	EditorInterface.open_scene_from_path(WORKBENCH_SCENE)
	await get_tree().process_frame

	var root := EditorInterface.get_edited_scene_root()

	if root == null:
		return

	for child: Node in root.get_children():
		if child is FigureWorkbench:
			_select(child)


# ─── The dock ───────────────────────────────────────────────────────────────

## The body types, the two tabs, and the report of the store.
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


## Each tab, the outfit bar, and the cost line, for the selected body type.
func _refresh_panels() -> void:
	if not _has_bench():
		return

	var body_key := _dock.active_body()
	var rig: FigureRig = _bench.store.rigs.get(body_key)
	var palette := _bench.store.palette()
	var body_panel := _dock.body_panel()

	_dock.rig_panel().set_rig(rig)
	# The kit parts first: they decide which look the part editor shows.
	body_panel.set_kit_content(body_key, _bench.store.looks, _bench.kit())
	body_panel.set_content(rig, _bench.store.looks.get(body_panel.edited_look()),
		_bench.models, palette)
	body_panel.set_reference_name(body_key)
	_dock.check_panel().set_budgets(_budgets, _bench.catalog.slot_keys())
	_dock.gear_panel().set_content(_bench.catalog, rig, _bench.store.looks, _bench.models,
		palette, _bench.store.presentation())
	_dock.families_panel().set_families(_bench.store.families(), palette)
	_dock.outfit_bar().set_catalog(_bench.catalog)
	_dock.outfit_bar().set_outfit(_bench.outfit())
	_refresh_colors()
	_refresh_cost()
	_refresh_clips()


## The Colors tab: the palette, the looks that name its colors, and the
## colors of the character. The table of the character has the color roles
## of the body of the selected body type, and of each kit part.
func _refresh_colors() -> void:
	if not _has_bench():
		return

	var store := _bench.store
	var owned := {}
	var keys := [_dock.active_body()]

	for group: String in FigureOutfit.kit_groups(store.looks):
		keys.append_array(Array(FigureOutfit.kit_groups(store.looks)[group]))

	for key: String in keys:
		if store.has(FigureStore.KIND_LOOK, key):
			for role: String in store.looks[key].resolved(store.looks).colors():
				owned[role] = true

	_dock.colors_panel().set_content(store.palette(),
		store.has(FigureStore.KIND_PALETTE, FigureStore.KIND_PALETTE), store.looks,
		owned.keys(), _bench.figure_colors())


## The budget line of the dressed figure, and the line of the selected item
## (requirement A8).
func _refresh_cost() -> void:
	_dock.set_cost(_bench.counts_of(_dock.active_body()), _budgets)
	_dock.set_item_line(_dock.gear_panel().item_line())


## The Clips tab: the clip library, and the clip lists with the clips of
## each source.
func _refresh_clips() -> void:
	if not _has_bench():
		return

	var source_clips := {}

	for key: String in _bench.store.keys_of(FigureStore.KIND_CLIPS):
		source_clips[key] = FigureClipImport.source_clips_of(key)

	_dock.clips_panel().set_clips(_bench.clips)
	_dock.clips_panel().set_clip_lists(_bench.store.clip_lists, source_clips)
	_dock.clips_panel().set_stances(_bench.store.stances(), _bench.catalog.tool_types(),
		_bench.stance_of_outfit())


## A file of the store got new content: from the dock, from the undo
## history, or from a moved node. The Save button counts the unsaved
## files, and the check runs again after a short wait.
func _on_bench_changed(kind: String, _key: String) -> void:
	if kind == FigureStore.KIND_RIG:
		_dock.set_bodies(_bench.body_keys())

	_dock.set_unsaved(_bench.unsaved_names())
	_check_timer.start()
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
## bone of body (fit row)". For a selected bone mark: the bone and the
## body type. With neither: the body type and the outfit.
func _hint_subject() -> String:
	var nodes := EditorInterface.get_selection().get_selected_nodes()
	var id: Array = FigureBuilder.part_id(nodes[0]) if nodes.size() == 1 else []

	if nodes.size() == 1 and nodes[0].name == FigureWorkbench.MARK_NAME:
		return HINT_BONE % [_bench.marked_bone(), _bench.body_of(nodes[0])]

	if id.is_empty() or not _bench.store.has(FigureStore.KIND_LOOK, id[0]):
		return HINT_BODY % [_dock.active_body(), _bench.outfit().size()]

	var body_key := _bench.body_of(nodes[0])
	var look: FigureLook = _bench.store.looks[id[0]]
	var row: Dictionary = look.resolved(_bench.store.looks).part(id[1])
	var line := HINT_PART % [id[1], id[0], row.get("bone", "?"), body_key]

	if not look.fit_row(body_key, id[1]).is_empty():
		line += HINT_FIT

	return line


## Select the part below a click, or the workbench for a click on no part.
## The editor handles the click first, and it clears the selection for a
## click on a node with no owner. Thus, this routine waits one frame.
func _pick_after_click(bench: FigureWorkbench, origin: Vector3,
		direction: Vector3) -> void:
	await get_tree().process_frame

	if not is_instance_valid(bench):
		return

	var part := bench.part_at(origin, direction)

	_select(bench if part == null else part)


## Select the node of one part of one worn look, on the stand of the
## selected body type.
func _select_part(look_key: String, part_name: String) -> void:
	if not _has_bench():
		return

	var node := _bench.part_node(_dock.active_body(), look_key, part_name)

	if node != null:
		_select(node)


static func _select(node: Node) -> void:
	var selection := EditorInterface.get_selection()
	var nodes := selection.get_selected_nodes()

	if nodes.size() == 1 and nodes[0] == node:
		return

	selection.clear()
	selection.add_node(node)


## Select the part of the shown tab again when its node left the selection.
## A part that moves to another bone leaves the tree for a moment, and the
## editor then drops it from the selection. A part of an item that leaves
## the outfit has no node, and the workbench then stays selected.
func _reselect() -> void:
	if not _has_bench() or not EditorInterface.get_selection().get_selected_nodes().is_empty():
		return

	var gear := _dock.gear_panel()
	var node: Node3D = null

	if _dock.shown_tab() == FigureDock.TAB_GEAR:
		node = _bench.part_node(_dock.active_body(), gear.edited_look(),
			gear.parts_panel().selected_part())
	else:
		node = _bench.part_node(_dock.active_body(), _dock.body_panel().edited_look(),
			_dock.body_panel().selected_part())

	_select(_bench if node == null else node)


## The editor selected a node: show its part in the tab of its worn look.
## A part of a body goes to the Body tab. Each other part goes to the Gear
## tab, on the row of its look.
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

	var id := FigureBuilder.part_id(nodes[0])

	if id.is_empty():
		return

	var body_key := _bench.body_of(nodes[0])

	if _dock.active_body() != body_key:
		_dock.select_body(body_key)
		_refresh_panels()

	var look: FigureLook = _bench.store.looks.get(id[0])
	var is_kit := look != null and not look.kit().is_empty()

	# A part of the body or of a kit part goes to the Body tab.
	if id[0] == body_key or is_kit:
		if _dock.body_panel().edited_look() != id[0]:
			_dock.body_panel().edit_kit(id[0] if is_kit else "")
			_refresh_panels()

		_show_part_tab(FigureDock.TAB_BODY)
		_dock.body_panel().select_part(id[1])
		return

	_show_part_tab(FigureDock.TAB_GEAR)
	_dock.gear_panel().select_row(id[0])
	_dock.gear_panel().parts_panel().select_part(id[1])
	_refresh_cost()


## Go from the Body tab to the Gear tab, or back, for a selected part. The
## Rig tab and the Clips tab stay. A click on a figure there does not ask
## for the part editor.
func _show_part_tab(title: String) -> void:
	if _dock.shown_tab() in [FigureDock.TAB_BODY, FigureDock.TAB_GEAR]:
		_dock.show_tab(title)


## The editor edits no workbench now. An empty selection selects the last
## workbench again. Another node gets a line in the status box.
func _keep_dock_alive(nodes: Array[Node]) -> void:
	var alive := is_instance_valid(_last_bench) and _last_bench.is_inside_tree()

	if nodes.is_empty() and alive:
		_select(_last_bench)
	elif not nodes.is_empty():
		_dock.set_status(SELECT_BENCH_STATUS)
