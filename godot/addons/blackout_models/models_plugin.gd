@tool
extends EditorPlugin
## The Blackout model form: the Models dock ([ModelForm]). It adds one 3D
## model to the model pipeline with no terminal, with the steps of
## `python -m assets.pipeline add` (Nick, 11/02/2026).
##
## The dock asks, and [ModelPipeline] runs the commands of the pipeline on
## one thread ([FigureJob]), so the editor stays usable. One command runs
## at a time. A command that comes while one runs waits. A newer check
## takes the place of a check that waits. A check never takes the place of
## a write that waits, because `add-write` checks the plan again itself.

const DOCK_NAME := "Models"

const JOB_OPTIONS := "the lists of the model form"
const JOB_CHECK := "the check of the plan"
const JOB_LOOK_UP := "the Poly Haven lookup"
const JOB_WRITE := "Writing and building %s ... The editor stays usable."

## What the busy text names for a plan whose asset key is its default.
const UNNAMED_KEY := "the model"

## The kind of a command that waits. Only a check can take the place of a
## check.
const KIND_CHECK := "check"
const KIND_OTHER := "other"

var _scroll: ScrollContainer
var _form: ModelForm
var _job := FigureJob.new()

## The command that waits for the job: `{label, kind, work, on_done}`, or
## {}.
var _waiting := {}


func _enter_tree() -> void:
	_form = ModelForm.new()
	_form.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_form.options_wanted.connect(_on_options_wanted)
	_form.check_wanted.connect(_on_check_wanted)
	_form.look_up_wanted.connect(_on_look_up_wanted)
	_form.write_wanted.connect(_on_write_wanted)
	_scroll = ScrollContainer.new()
	_scroll.name = DOCK_NAME
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_scroll.add_child(_form)
	add_control_to_dock(DOCK_SLOT_RIGHT_UL, _scroll)
	_on_options_wanted()


func _exit_tree() -> void:
	_waiting = {}
	_job.wait()
	remove_control_from_docks(_scroll)
	_scroll.queue_free()


func _process(_delta: float) -> void:
	if not _job.is_done():
		return

	_job.finish()

	var next := _waiting

	_waiting = {}

	if not next.is_empty():
		_queue(next)


func _on_options_wanted() -> void:
	_queue({"label": JOB_OPTIONS, "kind": KIND_OTHER, "work": ModelPipeline.options,
		"on_done": func(result: Dictionary) -> void:
			_form.show_options(result["answer"], result["output"])})


func _on_check_wanted(plan: Dictionary) -> void:
	_queue({"label": JOB_CHECK, "kind": KIND_CHECK, "work": ModelPipeline.check.bind(plan),
		"on_done": func(result: Dictionary) -> void:
			_form.show_answer(result["answer"], result["output"])})


func _on_look_up_wanted(typed: String) -> void:
	_queue({"label": JOB_LOOK_UP, "kind": KIND_OTHER, "work": ModelPipeline.look_up.bind(typed),
		"on_done": func(result: Dictionary) -> void:
			_form.show_look_up(result["answer"], result["output"])})


func _on_write_wanted(plan: Dictionary) -> void:
	var typed: String = plan.get(ModelPipeline.FIELD_ASSET_KEY, "")
	var key := typed if not typed.is_empty() else UNNAMED_KEY

	_form.set_busy(JOB_WRITE % key)
	_queue({"label": JOB_WRITE % key, "kind": KIND_OTHER,
		"work": ModelPipeline.write.bind(plan),
		"on_done": func(result: Dictionary) -> void:
			_form.show_written(result["answer"], result["output"])})


## Start a command now, or keep it until the job ends. See the class
## description for which waiting command a new one replaces.
func _queue(entry: Dictionary) -> void:
	if _job.is_done():
		_job.finish()

	if not _job.is_running():
		_job.start(entry["label"], entry["work"], entry["on_done"])
		return

	var keeps_write: bool = not _waiting.is_empty() and _waiting["kind"] != KIND_CHECK

	if entry["kind"] == KIND_CHECK and keeps_write:
		return

	_waiting = entry
