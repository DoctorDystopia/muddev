@tool
extends FigureEditorBase
## The Blackout gear editor: the worn look of each item on the figure
## (DESIGN-0014 section 22).
##
## Open `res://addons/blackout_gear/gear_workbench.tscn` and select the
## [GearWorkbench] node to start, or click "Open gear editor" on the
## Figure dock. The panel is [GearDock]: the items, the part editor, and
## the look. The rules live in `addons/blackout_figure/edits/`, and the
## handlers are those of the figure workbench: [FigureGearHandlers] for a
## row and its look, [FigurePartHandlers] for the part editor, and
## [FigureFamilyHandlers] for the presentation of a served model.
##
## [FigureEditorBase] keeps the editor contract: the dock, the selection,
## the hint, the save, and the jobs. This script gives the dock, the
## handlers, the refresh of the three zones, and the clip of the bar.
##
## The editor reads and writes the figure files of the figure workbench.
## A body and a kit part belong to that workbench: a click on such a part
## here says so in the status box.

const GEAR_SCENE := "res://addons/blackout_gear/gear_workbench.tscn"
const WORKBENCH_SCENE := "res://addons/blackout_figure/figure_workbench.tscn"

## What the status box says for a selected part of a body or of a kit part.
const BODY_PART_STATUS := "The part %s belongs to %s, a body or a kit part. Open the figure " \
	+ "workbench to change it."

## What the status box says for a selected served model.
const SERVED_STATUS := "The served model of %s. W moves it, E turns it, and R scales one " \
	+ "axis. Scale in the hand, in the Model fold, scales the whole model. The look file of " \
	+ "the item keeps its place."

## The handlers of the dock.
var _gear: FigureGearHandlers
var _parts: FigurePartHandlers
var _families: FigureFamilyHandlers


func _make_dock() -> FigureDockBase:
	return GearDock.new()


func _scene_path() -> String:
	return GEAR_SCENE


func _other_scene_path() -> String:
	return WORKBENCH_SCENE


## This plugin edits a gear workbench only.
func _is_mine(bench_node: FigureWorkbench) -> bool:
	return bench_node is GearWorkbench


func _bench_name() -> String:
	return "GearWorkbench"


## The dock of the gear editor.
func _gear_dock() -> GearDock:
	return _dock as GearDock


func _make_handlers() -> void:
	_gear = FigureGearHandlers.new(_context)
	_parts = FigurePartHandlers.new(_context)
	_families = FigureFamilyHandlers.new(_context)


func _wire_handlers() -> void:
	var dock := _gear_dock()

	_gear.connect_items(dock.items_panel())
	_gear.connect_look_panel(dock.look_panel())
	_gear.connect_outfit_bar(dock.outfit_bar())
	_parts.connect_panel(dock.part_editor(), dock.look_panel().edited_look)
	_families.connect_presentation(dock.look_panel())
	_connect_play_bar(dock)


## The play bar plays the clip of the bar on each stand. A pause keeps
## the moment, and the rest pose stops the clip.
func _connect_play_bar(dock: GearDock) -> void:
	var bar := dock.play_bar()

	bar.play_requested.connect(func(speed: float) -> void:
		if _has_bench() and not dock.chosen_clip().is_empty():
			bar.set_clip_length(_bench.clip_length(dock.chosen_clip()))
			_bench.play_clip(dock.chosen_clip(), _bench.clip_time(), speed))
	bar.pause_requested.connect(func() -> void:
		if _has_bench() and not dock.chosen_clip().is_empty():
			_bench.show_clip(dock.chosen_clip(), _bench.clip_time()))
	bar.stop_requested.connect(func() -> void:
		if _has_bench():
			_bench.stop_clip()
			bar.set_time(0.0))
	bar.seek_requested.connect(func(time: float) -> void:
		if _has_bench() and not dock.chosen_clip().is_empty():
			_bench.show_clip(dock.chosen_clip(), time))


func _connect_bench(bench_node: FigureWorkbench) -> void:
	bench_node.outfit_changed.connect(_gear.on_outfit_changed)
	bench_node.figure_colors_changed.connect(_refresh_cost)
	bench_node.kit_changed.connect(_refresh_cost)


func _disconnect_bench(bench_node: FigureWorkbench) -> void:
	bench_node.outfit_changed.disconnect(_gear.on_outfit_changed)
	bench_node.figure_colors_changed.disconnect(_refresh_cost)
	bench_node.kit_changed.disconnect(_refresh_cost)


## The author of the last import, and the row of the last session.
func _on_bench_taken() -> void:
	var dock := _gear_dock()

	dock.look_panel().set_author(dock.saved_author())
	dock.items_panel().set_content(_bench.catalog, _context.active_rig(), _bench.store.looks,
		_bench.models)
	dock.items_panel().select_row(dock.saved_row())

	var key := dock.items_panel().selected_key()

	if not key.is_empty():
		_bench.wear(dock.items_panel().selected_slot(), key)


func _set_busy(busy: bool) -> void:
	_gear_dock().look_panel().set_importing(busy)


# ─── The dock ───────────────────────────────────────────────────────────────

## The three zones, the clip list, the outfit bar, and the cost line, for
## the selected body type. The part editor shows the look of the row. A
## tier has no part of its own, so the editor shows none for it.
func _refresh_panels() -> void:
	if not _has_bench():
		return

	var dock := _gear_dock()
	var rig: FigureRig = _bench.store.rigs.get(dock.active_body())
	var palette := _bench.store.palette()
	var items := dock.items_panel()
	var look_panel := dock.look_panel()

	items.set_content(_bench.catalog, rig, _bench.store.looks, _bench.models)
	look_panel.set_content(_bench.catalog, rig, _bench.store.looks, items.selected_key(),
		_bench.models, palette, _bench.store.presentation())
	dock.part_editor().set_content(rig, null if look_panel.is_tier() \
		else _bench.store.looks.get(look_panel.edited_look()), _bench.models, palette)
	dock.set_clip_names(_bench.clip_names())
	dock.outfit_bar().set_catalog(_bench.catalog)
	dock.outfit_bar().set_outfit(_bench.outfit())
	_refresh_cost()


## The budget line of the dressed figure, and the line of the selected item
## (requirement A8).
func _refresh_cost() -> void:
	if not _has_bench():
		return

	_dock.set_cost(_bench.counts_of(_dock.active_body()), _budgets)
	_dock.set_item_line(_gear_dock().items_panel().item_line())


# ─── The selection ──────────────────────────────────────────────────────────

## The part or the shape of the part editor again, or null.
func _node_to_reselect() -> Node3D:
	var dock := _gear_dock()
	var editor := dock.part_editor()
	var look_key := dock.look_panel().edited_look()

	if editor.shape_row_selected():
		return _bench.shape_node(dock.active_body(), look_key, editor.selected_part(),
			editor.selected_shape())

	return _bench.part_node(dock.active_body(), look_key, editor.selected_part())


## A part of the look of an item goes to its row. A part of a body or of
## a kit part belongs to the figure workbench, and the status box says so.
## A part of a tier is a part of its base: the row of the base shows it.
## A served model goes to the row of its own item, because each item has
## its own model.
func _show_selected(look_key: String, part_name: String, shape_index: int,
		body_key: String) -> void:
	var dock := _gear_dock()
	var look: FigureLook = _bench.store.looks.get(look_key)
	var items := dock.items_panel()
	var served := part_name == FigureLook.SERVED_PART

	if look_key == body_key or (look != null and not look.kit().is_empty()):
		_dock.set_status(BODY_PART_STATUS % [part_name, look_key])
		return

	items.select_row(look_key if served else _bench.parts_owner(look_key))

	if items.selected_key().is_empty():
		return

	dock.save_row(items.selected_key())
	_refresh_panels()
	dock.part_editor().select_part(part_name)

	if shape_index >= 0:
		dock.part_editor().select_shape(shape_index)

	if served:
		_dock.set_status(SERVED_STATUS % look_key)

	_refresh_cost()
