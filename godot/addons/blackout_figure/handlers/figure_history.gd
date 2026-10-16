@tool
class_name FigureHistory
extends RefCounted
## The undo seam of the figure workbench: each change of a figure file goes
## into the editor history through this class.
##
## A change from the dock is one entry: it gives the old or the new content
## of one figure file to [method FigureWorkbench.put]. A field that the
## author drags makes one entry, not one for each step ([method change]
## with `merge`). A change of several files is one entry too
## ([method commit_many]), so one undo brings each file back.
##
## The plugin gives this class its [EditorUndoRedoManager], a getter of
## the workbench, and the status box. Nothing here reads a control.

## What the status box says for a change to a file that the store does not
## have, by the kind of the file.
const NO_FILE_STATUS := {
	FigureStore.KIND_RIG: "Make a rig first, on the Rig tab.",
	FigureStore.KIND_LOOK: "Make the look first: a body on the Body tab, or a look "
		+ "for the row on the Gear tab.",
	FigureStore.KIND_CLIPS: "Select a clip list first.",
	FigureStore.KIND_PALETTE: "Make a palette first, on the Colors tab.",
	FigureStore.KIND_STANCES: "This workbench has no stance file.",
	FigureStore.KIND_FAMILY: "Make a shape for the family first, on the Families tab.",
	FigureStore.KIND_PRESENTATION: "Select a row with a served model first.",
}

var _manager: EditorUndoRedoManager

## Gives the workbench that the editor edits now, or null.
var _bench_of: Callable

## Puts one text in the status box.
var _status: Callable


func _init(manager: EditorUndoRedoManager, bench_of: Callable, status: Callable) -> void:
	_manager = manager
	_bench_of = bench_of
	_status = status


## Change one figure file through `edit`, as one undo entry. `edit` gets a
## copy of the content, changes it, and returns "" or the reason for a
## refusal. `merge` joins the entry with the entry before it of the same
## name: one drag of a field is then one entry.
func change(kind: String, key: String, label: String, edit: Callable,
		merge := false) -> void:
	var bench: FigureWorkbench = _bench_of.call()

	if bench == null or not bench.store.has(kind, key):
		_status.call(NO_FILE_STATUS[kind])
		return

	var before := bench.store.data_of(kind, key)
	var after := before.duplicate(true)
	var problem: String = edit.call(after)

	if not problem.is_empty():
		_status.call(problem)
		return

	commit(kind, key, before, after, label, merge)


## Change one figure file through `edit`, as [method change] does. A file
## that the store does not have starts from `start`, so the first change
## makes the file.
func change_or_new(kind: String, key: String, start: Dictionary, label: String,
		edit: Callable, merge := false) -> void:
	var bench: FigureWorkbench = _bench_of.call()

	if bench == null:
		return

	var before := bench.store.data_of(kind, key)
	var after := start.duplicate(true) if before.is_empty() else before.duplicate(true)
	var problem: String = edit.call(after)

	if not problem.is_empty():
		_status.call(problem)
		return

	commit(kind, key, before, after, label, merge)


## Change one worn look, as one undo entry. A look key of the Families tab
## names a family ([constant FamilyLooks.LOOK_PREFIX]), and the change then
## goes into the row of that family in the family file.
func change_look(look_key: String, label: String, edit: Callable, merge := false) -> void:
	var family := FamilyLooks.family_of_key(look_key)

	if family.is_empty():
		change(FigureStore.KIND_LOOK, look_key, label, edit, merge)
		return

	change(FigureStore.KIND_FAMILY, FigureStore.KIND_FAMILY, "%s, of the family %s" % [label,
		family], func(content: Dictionary) -> String:
			var look := FamilyLooks.look_data(content, family)
			var problem: String = edit.call(look)

			if problem.is_empty():
				FamilyLooks.put_look(content, family, look)

			return problem, merge)


## Put one change of one figure file in the editor history, and apply it.
func commit(kind: String, key: String, before: Dictionary, after: Dictionary,
		label: String, merge := false) -> void:
	if after == before:
		return

	# The store refuses every content for a file that did not read. An entry
	# for it would report a change that nothing made.
	var problem := _refusal_or_form_problem(kind, key, after)

	if not problem.is_empty():
		_status.call(problem)
		return

	var bench: FigureWorkbench = _bench_of.call()
	var mode := UndoRedo.MERGE_ENDS if merge else UndoRedo.MERGE_DISABLE

	_manager.create_action("Figure: " + label, mode, bench)
	_manager.add_do_method(bench, "put", kind, key, after)
	_manager.add_undo_method(bench, "put", kind, key, before)
	_manager.commit_action()
	# Only the first letter changes. `capitalize` also takes each `_` out of
	# a key, and the status must give a key as the file has it.
	_status.call(label.left(1).to_upper() + label.substr(1) + ".")


## Put one change of several figure files in the editor history as one
## entry, and apply it. Each row of `changes` is `[kind, key, before,
## after]`. One undo then brings each file back.
func commit_many(changes: Array, label: String) -> void:
	for change_row: Array in changes:
		var problem := _refusal_or_form_problem(change_row[0], change_row[1], change_row[3])

		if not problem.is_empty():
			_status.call(problem)
			return

	var bench: FigureWorkbench = _bench_of.call()
	var new_rows := []
	var old_rows := []

	for change_row: Array in changes:
		new_rows.append([change_row[0], change_row[1], change_row[3]])
		old_rows.append([change_row[0], change_row[1], change_row[2]])

	# One call for each direction: the stands then draw one time, after each
	# file has the name.
	_manager.create_action("Figure: " + label, UndoRedo.MERGE_DISABLE, bench)
	_manager.add_do_method(bench, "put_many", new_rows)
	_manager.add_undo_method(bench, "put_many", old_rows)
	_manager.commit_action()
	_status.call("%s, in %d file(s)." % [label.left(1).to_upper() + label.substr(1),
		changes.size()])


## Why the store refuses the key, else why the content does not read, or "".
func _refusal_or_form_problem(kind: String, key: String, after: Dictionary) -> String:
	var bench: FigureWorkbench = _bench_of.call()
	var refused := bench.store.refusal(kind, key)

	if not refused.is_empty():
		return "No change: " + refused + "."

	return _form_problem(kind, after)


## Why the content of a figure file does not read, or "". Empty content
## removes the file, and that reads.
static func _form_problem(kind: String, data: Dictionary) -> String:
	if data.is_empty():
		return ""

	return FigureStore.item_from(kind, data).error
