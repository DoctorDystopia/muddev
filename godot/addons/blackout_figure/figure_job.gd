@tool
class_name FigureJob
extends RefCounted
## One piece of work of the figure workbench that runs on a thread, so the
## editor does not freeze: a model build, the served figure set, or a clip
## build (ENG-0011, item 3).
##
## The work is a Callable that returns its result. [method start] runs it
## on a [Thread]. The plugin asks [method is_done] from its `_process`, and
## it then takes the result with [method finish]. Each routine that a job
## runs stays a plain routine, so a headless test calls it with no thread.
##
## A job holds one thread. A thread that nothing waits for gives an error
## at exit, so the owner calls [method finish] or [method wait] before it
## goes.

## What the status box says while a job runs, with the name of the work.
const BUSY_TEXT := "Building %s ... The editor stays usable."

## The name of the work, for the status box.
var label := ""

var _thread: Thread

## What the author sees when the job ends: a Callable with the result.
var _on_done: Callable


## Run `work` on a thread. `label` names the work, and `on_done` gets the
## result when [method finish] runs. Returns false when a job runs now.
func start(name_of_work: String, work: Callable, on_done: Callable) -> bool:
	if is_running():
		return false

	label = name_of_work
	_on_done = on_done
	_thread = Thread.new()

	if _thread.start(work) != OK:
		_thread = null
		return false

	return true


## True while the thread runs.
func is_running() -> bool:
	return _thread != null and _thread.is_alive()


## True when the thread ended and nothing took its result yet.
func is_done() -> bool:
	return _thread != null and not _thread.is_alive()


## Take the result of an ended job, and give it to the `on_done` of
## [method start]. Returns false when no job ended.
func finish() -> bool:
	if not is_done():
		return false

	var result: Variant = _thread.wait_to_finish()

	_thread = null

	if _on_done.is_valid():
		_on_done.call(result)

	return true


## Wait for the job, and take its result. The editor calls this when the
## plugin leaves the tree while a job runs.
func wait() -> void:
	if _thread == null:
		return

	_thread.wait_to_finish()
	_thread = null


## The line for the status box while this job runs.
func busy_text() -> String:
	return BUSY_TEXT % label
