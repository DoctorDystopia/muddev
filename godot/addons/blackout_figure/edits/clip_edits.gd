@tool
class_name FigureClipEdits
extends RefCounted
## The rules of the Clips tab of the figure workbench (DESIGN-0014): the
## stance table, and the clips of a clip list.
##
## Each routine changes the content of one clip list file or of the stance
## table. The caller gives a copy, and the routine changes the copy. A
## routine that can refuse returns the reason, or "". Nothing here needs
## the editor.
##
## [method set_stance_clip] gives one action of one stance its clip (Phase
## W5). [method set_clip] and [method remove_clip] change the row of one
## clip in a clip list.


# ─── The Clips tab: a stance ────────────────────────────────────────────────

## The content of a stance table with no clip.
static func new_stances() -> Dictionary:
	return {"format": FigureStances.FORMAT, "default": {}, "stances": {}}


## Give one action of one stance its clip. An empty `tool_type` is the
## default clip set. An empty `clip_name` takes the action out, and the
## stance then uses the clip of the default clip set. A stance with no
## action left leaves the table.
static func set_stance_clip(table: Dictionary, tool_type: String, action: String,
		clip_name: String) -> String:
	var problem := FigureRigEdits.name_problem(action)

	if problem.is_empty() and not tool_type.is_empty():
		problem = FigureRigEdits.name_problem(tool_type)

	if problem.is_empty() and not clip_name.is_empty():
		problem = FigureRigEdits.name_problem(clip_name)

	if not problem.is_empty():
		return problem

	for own_key: String in ["default", "stances"]:
		if not table.has(own_key):
			table[own_key] = {}

	var clips: Dictionary = table["default"]

	if not tool_type.is_empty():
		clips = table["stances"].get(tool_type, {})
		table["stances"][tool_type] = clips

	if clip_name.is_empty():
		clips.erase(action)
	else:
		clips[action] = clip_name

	if not tool_type.is_empty() and clips.is_empty():
		table["stances"].erase(tool_type)

	return ""


# ─── The Clips tab ──────────────────────────────────────────────────────────

## Add one clip to a clip list, or change the row of a clip that the list
## has. `from` is the name of the clip in the source.
static func set_clip(list: Dictionary, clip_name: String, from: String,
		loop: bool) -> String:
	var problem := FigureRigEdits.name_problem(clip_name)

	if not problem.is_empty():
		return problem

	if from.is_empty():
		return "Give the name that the clip has in the source."

	if not list.has("clips"):
		list["clips"] = {}

	# A change of the source clip or of the loop keeps each other field of
	# the row: the held_in of a two-handed clip, for example.
	var row: Dictionary = list["clips"].get(clip_name, {}).duplicate()

	row["from"] = from
	row["loop"] = loop
	list["clips"][clip_name] = row

	return ""


## Remove one clip from a clip list. The clip file stays until the author
## deletes it.
static func remove_clip(list: Dictionary, clip_name: String) -> String:
	if not list.get("clips", {}).has(clip_name):
		return "The clip list has no clip %s." % clip_name

	list["clips"].erase(clip_name)

	return ""
