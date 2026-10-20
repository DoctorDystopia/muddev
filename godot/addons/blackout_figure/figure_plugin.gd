@tool
extends FigureEditorBase
## The Blackout figure workbench: the rigs, the bodies, the kit parts, the
## palette, the families, the clips, and the checks.
##
## DESIGN-0014, Phases W1 to W6. Open
## `res://addons/blackout_figure/figure_workbench.tscn` and select the
## [FigureWorkbench] node to start. The panel is [FigureDock]. The rules
## live in the scripts under `edits/` and in the other `Figure*` classes,
## and the `tests/test_figure_*.tscn` scenes test them with no editor.
##
## [FigureEditorBase] keeps the editor contract: the dock, the selection,
## the hint, the save, and the jobs. This script gives the dock, the
## handlers of each tab, and the refresh of each tab. One script under
## `handlers/` holds the handlers of each tab, [FigureHistory] holds the
## undo seam, and each handler reaches the plugin through one
## [FigureHandlerContext].
##
## The worn look of an item is the work of the gear editor
## (`addons/blackout_gear/`, DESIGN-0014 section 22). A click on the part
## of an item here says so in the status box.

const WORKBENCH_SCENE := "res://addons/blackout_figure/figure_workbench.tscn"
const GEAR_SCENE := "res://addons/blackout_gear/gear_workbench.tscn"

## The check runs this long after the last change of a file, in seconds.
const CHECK_DELAY := 0.5

## What the status box says for a selected part of the look of an item.
const GEAR_PART_STATUS := "The part %s belongs to the look of %s. Open the gear editor to " \
	+ "change it."

## The timer of the check after a change.
var _check_timer := Timer.new()

## The handlers of each tab of the dock.
var _rig: FigureRigHandlers
var _body: FigureBodyHandlers
var _parts: FigurePartHandlers
var _gear: FigureGearHandlers
var _colors: FigureColorHandlers
var _families: FigureFamilyHandlers
var _clips: FigureClipHandlers
var _check: FigureCheckHandlers


func _make_dock() -> FigureDockBase:
	return FigureDock.new()


func _scene_path() -> String:
	return WORKBENCH_SCENE


func _other_scene_path() -> String:
	return GEAR_SCENE


## This plugin edits each workbench that is no gear workbench.
func _is_mine(bench_node: FigureWorkbench) -> bool:
	return not bench_node is GearWorkbench


func _bench_name() -> String:
	return "FigureWorkbench"


## The dock of the figure workbench.
func _figure_dock() -> FigureDock:
	return _dock as FigureDock


func _make_handlers() -> void:
	_rig = FigureRigHandlers.new(_context)
	_gear = FigureGearHandlers.new(_context)
	_body = FigureBodyHandlers.new(_context, _gear)
	_parts = FigurePartHandlers.new(_context)
	_colors = FigureColorHandlers.new(_context)
	_families = FigureFamilyHandlers.new(_context)
	_clips = FigureClipHandlers.new(_context)
	_check = FigureCheckHandlers.new(_context, _rig, _clips)


## Give each handler its panel. The two part editors share one handler,
## and each one tells it which worn look it shows.
func _wire_handlers() -> void:
	var dock := _figure_dock()

	_clips.connect_play_bar(dock.play_bar())
	_rig.connect_panel(dock.rig_panel())
	_body.connect_panel(dock.body_panel())
	_parts.connect_panel(dock.body_panel(), dock.body_panel().edited_look)
	_gear.connect_outfit_bar(dock.outfit_bar())
	_colors.connect_panel(dock.colors_panel())
	_families.connect_panel(dock.families_panel())
	_parts.connect_panel(dock.families_panel(), dock.families_panel().edited_look)
	_clips.connect_panel(dock.clips_panel())
	_check.connect_panel(dock.check_panel())


## The check runs a short time after the last change of a file.
func _after_enter_tree() -> void:
	_check_timer.one_shot = true
	_check_timer.wait_time = CHECK_DELAY
	_check_timer.timeout.connect(func() -> void: _check.run_checks(false))
	add_child(_check_timer)


func _connect_bench(bench_node: FigureWorkbench) -> void:
	bench_node.outfit_changed.connect(_gear.on_outfit_changed)
	bench_node.figure_colors_changed.connect(_colors.on_figure_colors_changed)
	bench_node.kit_changed.connect(_body.on_kit_changed)


func _disconnect_bench(bench_node: FigureWorkbench) -> void:
	bench_node.outfit_changed.disconnect(_gear.on_outfit_changed)
	bench_node.figure_colors_changed.disconnect(_colors.on_figure_colors_changed)
	bench_node.kit_changed.disconnect(_body.on_kit_changed)


func _set_busy(busy: bool) -> void:
	_figure_dock().clips_panel().set_building(busy)


func _on_file_changed(_kind: String, _key: String) -> void:
	_check_timer.start()


# ─── The dock ───────────────────────────────────────────────────────────────

## Each tab, the outfit bar, and the cost line, for the selected body type.
func _refresh_panels() -> void:
	if not _has_bench():
		return

	var dock := _figure_dock()
	var body_key := dock.active_body()
	var rig: FigureRig = _bench.store.rigs.get(body_key)
	var palette := _bench.store.palette()
	var body_panel := dock.body_panel()

	dock.rig_panel().set_rig(rig)
	# The kit parts first: they decide which look the part editor shows.
	body_panel.set_kit_content(body_key, _bench.store.looks, _bench.kit())
	body_panel.set_content(rig, _bench.store.looks.get(body_panel.edited_look()),
		_bench.models, palette)
	body_panel.set_reference_name(body_key)
	dock.check_panel().set_budgets(_budgets, _bench.catalog.slot_keys())
	dock.families_panel().set_families(_bench.store.families(), palette)
	dock.outfit_bar().set_catalog(_bench.catalog)
	dock.outfit_bar().set_outfit(_bench.outfit())
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

	_figure_dock().colors_panel().set_content(store.palette(),
		store.has(FigureStore.KIND_PALETTE, FigureStore.KIND_PALETTE), store.looks,
		owned.keys(), _bench.figure_colors())


## The budget line of the dressed figure.
func _refresh_cost() -> void:
	_dock.set_cost(_bench.counts_of(_dock.active_body()), _budgets)


## The Clips tab: the clip library, and the clip lists with the clips of
## each source.
func _refresh_clips() -> void:
	if not _has_bench():
		return

	var source_clips := {}
	var clips_panel := _figure_dock().clips_panel()

	for key: String in _bench.store.keys_of(FigureStore.KIND_CLIPS):
		source_clips[key] = FigureClipImport.source_clips_of(key)

	clips_panel.set_clips(_bench.clips)
	clips_panel.set_clip_lists(_bench.store.clip_lists, source_clips)
	clips_panel.set_stances(_bench.store.stances(), _bench.catalog.tool_types(),
		_bench.stance_of_outfit())


# ─── The selection ──────────────────────────────────────────────────────────

## The part of the Body tab or of the Families tab again, or null.
func _node_to_reselect() -> Node3D:
	var dock := _figure_dock()
	var panel: PartEditor = dock.families_panel() \
		if dock.shown_tab() == FigureDock.TAB_FAMILIES else dock.body_panel()

	if panel == dock.families_panel():
		return null

	if panel.shape_row_selected():
		return _bench.shape_node(dock.active_body(), panel.edited_look(),
			panel.selected_part(), panel.selected_shape())

	return _bench.part_node(dock.active_body(), panel.edited_look(), panel.selected_part())


## A part of a body or of a kit part goes to the Body tab. A part of the
## look of an item belongs to the gear editor, and the status box says so.
func _show_selected(look_key: String, part_name: String, shape_index: int,
		body_key: String) -> void:
	var dock := _figure_dock()
	var look: FigureLook = _bench.store.looks.get(look_key)
	var is_kit := look != null and not look.kit().is_empty()

	if look_key != body_key and not is_kit:
		_dock.set_status(GEAR_PART_STATUS % [part_name, look_key])
		return

	if dock.body_panel().edited_look() != look_key:
		dock.body_panel().edit_kit(look_key if is_kit else "")
		_refresh_panels()

	# The Rig tab and the Clips tab stay. A click on a figure there does
	# not ask for the part editor.
	if dock.shown_tab() == FigureDock.TAB_FAMILIES:
		dock.show_tab(FigureDock.TAB_BODY)

	dock.body_panel().select_part(part_name)

	if shape_index >= 0:
		dock.body_panel().select_shape(shape_index)
