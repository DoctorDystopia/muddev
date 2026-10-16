@tool
class_name FigureClipHandlers
extends RefCounted
## The handlers of the Clips tab and of the play bar of the figure dock: a
## clip, the play, the probe, the stance table, the clip lists, the clip
## build, and the clips of a source.
##
## The play bar of the dock plays the clip of the Clips tab on each stand
## through [FigureWorkbench]. A change of a clip list is an undo entry, as
## each other change of a figure file. "Build the clips" writes the clip
## files on a thread, and no undo entry brings an old clip file back.
##
## The stance table is a figure file also. The first change of a stance
## makes the file.

const JOB_CLIPS := "the clips"
const JOB_SOURCE_CLIPS := "the clip list of the source %s"

var _context: FigureHandlerContext


func _init(context: FigureHandlerContext) -> void:
	_context = context


func connect_panel(panel: FigureClipsPanel) -> void:
	panel.stance_clip_set.connect(_on_stance_clip_set)
	panel.clip_chosen.connect(on_clip_chosen)
	panel.play_requested.connect(_on_play_requested)
	panel.probe_toggled.connect(_on_probe_toggled)
	panel.animation_editor_requested.connect(_on_animation_editor_requested)
	panel.clip_set.connect(_on_clip_set)
	panel.clip_removed.connect(_on_clip_removed)
	panel.source_clips_requested.connect(_on_source_clips_requested)
	panel.build_asked.connect(_on_build_asked)
	panel.build_requested.connect(_on_build_requested)


func connect_play_bar(bar: FigurePlayBar) -> void:
	bar.play_requested.connect(_on_play_requested_from_bar)
	bar.pause_requested.connect(_on_pause_requested)
	bar.stop_requested.connect(_on_stop_requested)
	bar.seek_requested.connect(_on_seek_requested)


## A selected clip shows its first moment, and the clearance of a held item.
## The play bar gets the length of the clip. The Check tab calls this for a
## finding on a clip.
func on_clip_chosen(clip_name: String) -> void:
	var bench := _context.bench()

	if bench == null:
		return

	bench.show_clip(clip_name, 0.0)
	_context.dock().play_bar().set_clip_length(bench.clip_length(clip_name))
	_context.dock().clips_panel().set_clearance(bench.clearance_lines(clip_name))


## A play button of the stance table: play the clip of that action, at the
## speed of the play bar.
func _on_play_requested(clip_name: String) -> void:
	var bench := _context.bench()

	if bench != null and not bench.play_clip(clip_name, 0.0, _context.dock().play_bar().speed()):
		_context.status("Select a clip first.")


## "Play" of the play bar: play the clip that the Clips tab selects.
func _on_play_requested_from_bar(speed: float) -> void:
	var bench := _context.bench()
	var clips_panel := _context.dock().clips_panel()

	if bench != null and not bench.play_clip(clips_panel.selected_clip(), 0.0, speed):
		_context.status("Select a clip on the Clips tab first.")


func _on_pause_requested() -> void:
	var bench := _context.bench()

	if bench != null and not bench.shown_clip().is_empty():
		bench.show_clip(bench.shown_clip(), bench.clip_time())


func _on_stop_requested() -> void:
	var bench := _context.bench()

	if bench != null:
		bench.stop_clip()
		_context.dock().play_bar().set_time(0.0)


func _on_seek_requested(time: float) -> void:
	var bench := _context.bench()

	if bench != null:
		bench.show_clip(_context.dock().clips_panel().selected_clip(), time)


func _on_probe_toggled(shown: bool) -> void:
	var bench := _context.bench()

	if bench != null:
		bench.show_probe = shown
		_context.dock().set_cost(bench.counts_of(_context.dock().active_body()),
			_context.budgets())


## Select the clip player of the selected body type. The Godot animation
## editor then shows its tracks.
func _on_animation_editor_requested() -> void:
	var bench := _context.bench()

	if bench == null:
		return

	var player := bench.player_of(_context.dock().active_body())

	if player == null:
		_context.status("Make a rig first, on the Rig tab.")
		return

	var selected := _context.dock().clips_panel().selected_clip()

	if bench.clips.has_animation(selected):
		player.assigned_animation = selected

	_context.select_node(player)


func _on_clip_set(list_key: String, clip_name: String, from: String, loop: bool) -> void:
	_context.history().change(FigureStore.KIND_CLIPS, list_key,
		"put the clip %s in the clip list" % clip_name, func(list: Dictionary) -> String:
			return FigureClipEdits.set_clip(list, clip_name, from, loop))


func _on_clip_removed(list_key: String, clip_name: String) -> void:
	_context.history().change(FigureStore.KIND_CLIPS, list_key,
		"take the clip %s out of the clip list" % clip_name, func(list: Dictionary) -> String:
			return FigureClipEdits.remove_clip(list, clip_name))


## One action of one stance got a clip, or lost its own clip. The first
## change makes the stance table.
func _on_stance_clip_set(tool_type: String, action: String, clip_name: String) -> void:
	var bench := _context.bench()
	var stance := "the default clip set" if tool_type.is_empty() else "the stance of " + tool_type
	var edit := func(table: Dictionary) -> String:
		return FigureClipEdits.set_stance_clip(table, tool_type, action, clip_name)

	# The form of a new action sends the selected clip. With no clip, the
	# table would not change, and the author would see no reason.
	if clip_name.is_empty() and bench != null \
			and bench.store.stances().own_clip(tool_type, action).is_empty():
		_context.status("Select a clip of the clip list first. An action needs a clip.")
		return

	_context.history().change_or_new(FigureStore.KIND_STANCES, FigureStore.KIND_STANCES,
		FigureClipEdits.new_stances(), "set the clip of %s in %s" % [action, stance], edit)
	# A refused change leaves the list as the table has it.
	_context.refresh_clips()


## "Build the clips": ask first. The question names each clip file that
## the build writes over.
func _on_build_asked() -> void:
	var bench := _context.bench()

	if bench != null:
		_context.dock().clips_panel().confirm_build(bench.overwritten_clip_files())


## The author confirmed: make each clip file of each clip list again, on a
## thread.
func _on_build_requested() -> void:
	var bench := _context.bench()

	if bench == null:
		return

	var plan := bench.clip_build_plan()
	var lines: PackedStringArray = plan["lines"]

	_context.start_job(JOB_CLIPS, FigureWorkbench.run_clip_build.bind(plan["rows"]),
		func(built: PackedStringArray) -> void:
			lines.append_array(built)
			_on_build_done(lines), lines)


## The clip build ended: read the clip files again, and show the report.
func _on_build_done(lines: PackedStringArray) -> void:
	var bench := _context.bench()

	if bench == null:
		return

	bench.reload_clips()
	_context.status("\n".join(lines))
	_context.refresh_clips()

	# The editor learns of each new clip file through a scan.
	if bench.clips_directory().begins_with("res://"):
		EditorInterface.get_resource_filesystem().scan()


## "List source clips": run the import step of one source on a thread, and
## fill the list of its clips. This writes no clip file.
func _on_source_clips_requested(list_key: String) -> void:
	var bench := _context.bench()
	var arguments: Array = bench.source_clips_arguments(list_key) if bench != null else []

	if arguments.is_empty():
		_context.status("Select a clip list first, and make a rig on the Rig tab.")
		return

	var work := FigureClipImport.import_source.bind(arguments[0], arguments[1], arguments[2],
		PackedStringArray())

	_context.start_job(JOB_SOURCE_CLIPS % list_key, work, func(result: Dictionary) -> void:
		_on_source_clips_done(list_key, result))


## The import step ended: the Clips tab shows the clips of the source.
func _on_source_clips_done(list_key: String, result: Dictionary) -> void:
	if not result["error"].is_empty():
		_context.status("The source of %s did not import:\n%s" % [list_key, result["error"]])
		return

	_context.status("The source of %s has %d clip(s)." % [list_key,
		result["source_clips"].size()])
	_context.refresh_clips()
