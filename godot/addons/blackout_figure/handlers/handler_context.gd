@tool
class_name FigureHandlerContext
extends RefCounted
## What a handler of one panel of the figure workbench or of the gear
## editor may reach of the plugin: the dock, the workbench, the undo seam,
## the refresh routines, the selection routines, the status box, and the
## jobs.
##
## The plugin builds one context and gives it to each handler. A handler
## reaches nothing else of the plugin. A handler that needs more says that
## the split is wrong there.
##
## The plugin gives each routine of its own as a [Callable], under the key
## that names it here. The context checks that each key is present.
##
## The two plugins share the handlers. A handler of a tab that only the
## Figure dock has asks [method figure_dock], and it runs in that plugin
## only.

const BENCH := "bench"
const REFRESH_PANELS := "refresh_panels"
const REFRESH_COLORS := "refresh_colors"
const REFRESH_CLIPS := "refresh_clips"
const REFRESH_COST := "refresh_cost"
const SELECT_PART := "select_part"
const SELECT_SHAPE := "select_shape"
const SELECT_NODE := "select_node"
const RESELECT := "reselect"
const START_JOB := "start_job"
const BUDGETS := "budgets"
const SET_BUDGETS := "set_budgets"

const KEYS := [BENCH, REFRESH_PANELS, REFRESH_COLORS, REFRESH_CLIPS, REFRESH_COST,
	SELECT_PART, SELECT_SHAPE, SELECT_NODE, RESELECT, START_JOB, BUDGETS, SET_BUDGETS]

var _dock: FigureDockBase
var _history: FigureHistory
var _calls: Dictionary


func _init(dock: FigureDockBase, history: FigureHistory, calls: Dictionary) -> void:
	for key: String in KEYS:
		assert(calls.has(key), "The handler context needs the routine %s." % key)

	_dock = dock
	_history = history
	_calls = calls


## The dock of the plugin: the Figure dock, or the Gear dock.
func dock() -> FigureDockBase:
	return _dock


## The Figure dock, or null in the gear editor. A handler of a tab that
## only the Figure dock has asks this.
func figure_dock() -> FigureDock:
	return _dock as FigureDock


## The workbench that the editor edits now, or null. The dock keeps its
## controls after the editor stops editing the workbench, so a handler can
## run with no bench.
func bench() -> FigureWorkbench:
	return _calls[BENCH].call()


func history() -> FigureHistory:
	return _history


## The rig of the selected body type, or null with no workbench.
func active_rig() -> FigureRig:
	var current := bench()

	if current == null:
		return null

	return current.store.rigs.get(_dock.active_body())


## Each panel, the outfit bar, and the cost line, for the selected body
## type.
func refresh_panels() -> void:
	_calls[REFRESH_PANELS].call()


## The Colors tab only.
func refresh_colors() -> void:
	_calls[REFRESH_COLORS].call()


## The Clips tab only.
func refresh_clips() -> void:
	_calls[REFRESH_CLIPS].call()


## The budget line and the line of the selected item.
func refresh_cost() -> void:
	_calls[REFRESH_COST].call()


## Select the node of one part of one worn look, on the stand of the
## selected body type.
func select_part(look_key: String, part_name: String) -> void:
	_calls[SELECT_PART].call(look_key, part_name)


## Select the node of one shape of one part, on the stand of the selected
## body type.
func select_shape(look_key: String, part_name: String, shape_index: int) -> void:
	_calls[SELECT_SHAPE].call(look_key, part_name, shape_index)


## Select one node in the editor.
func select_node(node: Node) -> void:
	_calls[SELECT_NODE].call(node)


## Select the part of the dock again when its node left the selection.
func reselect() -> void:
	_calls[RESELECT].call()


func status(text: String) -> void:
	_dock.set_status(text)


func show_tab(title: String) -> void:
	_dock.show_tab(title)


## Run `work` on the one job of the plugin, with `on_done` for its result.
## `lines` go to the status box, with the busy line when the job is taken.
func start_job(label: String, work: Callable, on_done: Callable,
		lines := PackedStringArray()) -> void:
	_calls[START_JOB].call(label, work, on_done, lines)


## The budget table of the Check tab ([FigureChecks]).
func budgets() -> Dictionary:
	return _calls[BUDGETS].call()


func set_budgets(budgets: Dictionary) -> void:
	_calls[SET_BUDGETS].call(budgets)
