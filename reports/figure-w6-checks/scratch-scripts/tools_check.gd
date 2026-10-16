@tool
extends EditorPlugin
## Phase W6 check of DESIGN-0014, in a real editor window. It runs only in a
## scratch copy of the project, with a scratch copy of the figure files and
## of the model pipeline beside it. It opens the figure workbench and uses
## each tool of Phase W6: the rotation of a socket, the mirror move of a
## bone, a region, a kit part, the other side of a part, the color of the
## palette for a color role, a new name for a color, the outfit of an NPC
## def, the checks, the budgets, and a save. It writes each answer to
## `res://tools_check_result.json`. Then it closes the editor.

const SCENE := "res://addons/blackout_figure/figure_workbench.tscn"
const RESULT := "res://tools_check_result.json"
const PICTURES := "res://tools_check_%s.png"

const LOOK := FigureStore.KIND_LOOK
const RIG := FigureStore.KIND_RIG
const KIT := "hair_spiky"

var _results := {}
var _undo_count := 0


func _enter_tree() -> void:
	_run.call_deferred()


func _run() -> void:
	await get_tree().create_timer(5.0).timeout
	EditorInterface.open_scene_from_path(SCENE)
	EditorInterface.set_main_screen_editor("3D")
	await get_tree().create_timer(2.0).timeout

	var root := EditorInterface.get_edited_scene_root()
	var bench := root.get_node("FigureWorkbench") as FigureWorkbench
	var selection := EditorInterface.get_selection()
	var dock := _find_dock(EditorInterface.get_base_control())

	selection.clear()
	selection.add_node(bench)
	await _frames(10)
	bench.set_outfit({})
	bench.set_figure_colors({})
	bench.set_kit({})
	dock.select_body("body_1")
	dock.body_changed.emit("body_1")
	await _frames(4)
	_results["store errors"] = Array(bench.store.errors)
	_results["the workbench writes its repository"] = bench.writes_repo()
	_results["the tabs"] = _tab_titles(dock)
	_results["the budget line at the start"] = dock._cost.text

	await _the_rig_tab(bench, dock)
	await _the_kit(bench, dock)
	await _the_other_side(bench, dock)
	await _the_colors(bench, dock)
	await _the_npc(bench, dock)
	await _the_checks(bench, dock)
	await _a_save(bench, dock)

	var file := FileAccess.open(RESULT, FileAccess.WRITE)

	file.store_string(JSON.stringify(_results, "  "))
	file.close()
	get_tree().quit()


func _tab_titles(dock: FigureDock) -> Array:
	var titles := []

	for index in dock._tabs.get_tab_count():
		titles.append(dock._tabs.get_tab_title(index))

	return titles


# ─── The Rig tab ────────────────────────────────────────────────────────────

func _the_rig_tab(bench: FigureWorkbench, dock: FigureDock) -> void:
	var rig := dock.rig_panel()

	dock.show_tab(FigureDock.TAB_RIG)
	rig.select_bone("hand_r")
	rig.bone_chosen.emit("hand_r")
	await _frames(2)

	var grip: Array = _rig(bench).bone("hand_r")["rotation"].duplicate()
	var field := rig._rotation.get_child(1) as SpinBox

	field.value = field.value + 10.0
	await _frames(4)
	_results["rig: a rotation field turns the socket"] = \
		_rig(bench).bone("hand_r")["rotation"] != grip
	_results["rig: the tree keeps the socket after the turn"] = rig.selected_bone()
	_undo(bench)
	await _frames(4)
	_results["rig: an undo gives the grip back"] = \
		_rig(bench).bone("hand_r")["rotation"] == grip

	rig.select_bone("Head")
	rig.bone_chosen.emit("Head")
	await _frames(2)
	field.value = field.value + 10.0
	await _frames(4)
	_results["rig: a body bone refuses a rotation"] = dock._status.text

	rig.select_bone("LeftUpperArm")
	rig.bone_chosen.emit("LeftUpperArm")
	rig._mirror.button_pressed = true
	await _frames(2)

	var right := _rig(bench).global_rest_of("RightUpperArm").origin
	var move := rig._position.get_child(0) as SpinBox

	move.value = move.value + 0.02
	await _frames(4)

	var after: FigureRig = _rig(bench)

	_results["rig: the mirror moves the bone of the other side"] = \
		after.global_rest_of("RightUpperArm").origin.distance_to(right) > 0.001
	_results["rig: the two sides are a mirror picture"] = \
		after.global_rest_of("RightUpperArm").origin.distance_to(
			after.global_rest_of("LeftUpperArm").origin * Vector3(-1.0, 1.0, 1.0)) < 0.0001
	_undo(bench)
	rig._mirror.button_pressed = false
	await _frames(4)

	rig._region_name.text = "cape"
	_press(rig, "Add the region")
	await _frames(4)
	rig.select_bone("back")
	rig.bone_chosen.emit("back")
	FigureFields.select_text(rig._region, "cape")
	rig._region.item_selected.emit(rig._region.selected)
	await _frames(4)
	_results["rig: a new region takes a bone"] = _rig(bench).region_of("back")
	await _pictures(dock, FigureDock.TAB_RIG, "rig")
	FigureFields.select_text(rig._region, "hair")
	_press(rig, "Remove the region of the selected bone")
	await _frames(4)
	_results["rig: a region that a look names stays"] = dock._status.text
	_undo(bench)
	_undo(bench)
	await _frames(4)
	_results["rig: two undos take the region away"] = \
		not _rig(bench).regions().has("cape")


# ─── The kit parts ──────────────────────────────────────────────────────────

func _the_kit(bench: FigureWorkbench, dock: FigureDock) -> void:
	var body := dock.body_panel()
	var hair_parts := _parts_in(bench, "body_1", "hair")

	dock.show_tab(FigureDock.TAB_BODY)
	await _frames(2)
	FigureFields.select_text(body._new_bone, "head_top")
	body._kit_key.text = KIT
	body._kit_group.text = "hair"
	_press(body, "New kit part")
	await _frames(6)

	var look: FigureLook = bench.store.looks.get(KIT)

	_results["kit: the status after a new kit part"] = dock._status.text
	_results["kit: the store has the kit part"] = look != null
	_results["kit: its group, its hide list, and its first color"] = [] if look == null \
		else [look.kit(), look.hides(), look.parts()[0]["shapes"][0]["color"]]
	_results["kit: the stands wear it"] = bench.kit()
	_results["kit: the part editor shows it, with the fit controls"] = \
		[body.edited_look(), body._fit.visible, body._hides.visible]
	_results["kit: body hair parts at the start, and now"] = \
		[hair_parts.size(), _parts_in(bench, "body_1", "hair").size()]
	_results["kit: a node on each stand"] = \
		[bench.part_node("body_1", KIT, "head_top") != null,
		bench.part_node("body_2", KIT, "head_top") != null]

	# Give the hair a height, so it shows in the picture.
	var top := body._field_controls.get("size") as HBoxContainer

	body.select_part("head_top")
	await _frames(2)
	top = body._field_controls.get("size") as HBoxContainer

	if top != null:
		(top.get_child(1) as SpinBox).value = 0.22
		(top.get_child(0) as SpinBox).value = 0.2

	await _frames(4)
	dock.show_tab(FigureDock.TAB_GEAR)
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(bench.part_node("body_2", KIT, "head_top"))
	await _frames(6)
	_results["kit: a selected kit part goes to the Body tab"] = \
		[dock.shown_tab(), dock.active_body(), body.edited_look(), body.selected_part()]
	await _pictures(dock, FigureDock.TAB_BODY, "kit")

	(body._kit_grid.get_child(1) as OptionButton).select(0)
	(body._kit_grid.get_child(1) as OptionButton).item_selected.emit(0)
	await _frames(6)
	_results["kit: the body as it is gives the hair back"] = \
		[bench.kit(), _parts_in(bench, "body_1", "hair").size()]
	(body._kit_grid.get_child(1) as OptionButton).select(1)
	(body._kit_grid.get_child(1) as OptionButton).item_selected.emit(1)
	await _frames(6)
	body._edited.select(0)
	body._edited.item_selected.emit(0)
	await _frames(4)
	_results["kit: the part editor goes back to the body"] = \
		[body.edited_look(), body._fit.visible, body._hides.visible]


## The name of each part node of one region of the body on one stand.
func _parts_in(bench: FigureWorkbench, body_key: String, region: String) -> Array:
	var names := []

	for row: Dictionary in _look(bench, body_key).parts():
		if row["region"] == region and bench.part_node(body_key, body_key, row["name"]) != null:
			names.append(row["name"])

	return names


# ─── The other side of a part, and a copy ───────────────────────────────────

func _the_other_side(bench: FigureWorkbench, dock: FigureDock) -> void:
	var body := dock.body_panel()
	var before := bench.part_node("body_1", "body_1", "sleeve_r").global_transform
	var count: int = _look(bench, "body_1").parts().size()

	dock.select_body("body_1")
	dock.body_changed.emit("body_1")
	dock.show_tab(FigureDock.TAB_BODY)
	await _frames(4)
	body.select_part("sleeve_r")
	body.part_chosen.emit("sleeve_r")
	_press(body, "Remove the selected part")
	await _frames(4)
	_results["mirror: the right sleeve is gone"] = \
		bench.part_node("body_1", "body_1", "sleeve_r") == null
	body.select_part("sleeve_l")
	body.part_chosen.emit("sleeve_l")
	_press(body, "Make the part of the other side")
	await _frames(6)

	var made := bench.part_node("body_1", "body_1", "sleeve_r")

	_results["mirror: the status"] = dock._status.text
	_results["mirror: the other side is there, and selected"] = \
		[made != null, body.selected_part(), _only(made)]

	if made != null:
		_results["mirror: distance from the sleeve that the mannequin had"] = \
			snappedf(made.global_transform.origin.distance_to(before.origin), 0.00001)
		_results["mirror: the largest difference of an axis"] = snappedf(maxf(maxf(
			made.global_transform.basis.x.distance_to(before.basis.x),
			made.global_transform.basis.y.distance_to(before.basis.y)),
			made.global_transform.basis.z.distance_to(before.basis.z)), 0.00001)

	await _pictures(dock, FigureDock.TAB_BODY, "mirror")
	body.select_part("head")
	body.part_chosen.emit("head")
	_press(body, "Copy the selected part")
	await _frames(4)
	_results["copy: a copy of the head, selected"] = \
		[_look(bench, "body_1").parts().size() == count + 1, body.selected_part()]
	_press(body, "Copy the selected shape")
	await _frames(4)
	_results["copy: the copy of a shape is selected"] = body.selected_shape()
	_undo(bench)
	_undo(bench)
	_undo(bench)
	_undo(bench)
	await _frames(4)
	_results["mirror: four undos give the first body back"] = \
		_look(bench, "body_1").parts().size() == count \
		and not _look(bench, "body_1").part("sleeve_r").is_empty()


# ─── The colors ─────────────────────────────────────────────────────────────

func _the_colors(bench: FigureWorkbench, dock: FigureDock) -> void:
	var gear := dock.gear_panel()
	var colors := dock.colors_panel()

	dock.show_tab(FigureDock.TAB_GEAR)
	_pick_row(gear, "head")
	await _frames(6)

	var labels := []
	var marks := 0

	for index in gear._colors.get_child_count() / 2:
		var list := gear._colors.get_child(index * 2 + 1) as OptionButton

		labels.append("%s=%s" % [(gear._colors.get_child(index * 2) as Label).text,
			list.get_item_text(list.selected)])
		marks += 1 if list.get_item_icon(1) != null else 0

	_results["colors: the roles of the head slot shape"] = labels
	_results["colors: lists with a color mark"] = marks
	await _pictures(dock, FigureDock.TAB_GEAR, "gear_colors")

	var metal := gear._colors.get_child(1) as OptionButton
	var role := (gear._colors.get_child(0) as Label).text

	metal.select(0)
	metal.item_selected.emit(0)
	await _frames(6)
	_results["colors: the first choice gives the role to the palette"] = \
		[role, dock._status.text, _look(bench, "head").colors().has(role),
		metal.get_item_text(metal.selected)]
	_undo(bench)
	await _frames(4)

	var users := FigureEdits.looks_with_color(bench.store.looks, "iron")

	dock.show_tab(FigureDock.TAB_COLORS)
	colors.select_color("iron")
	colors._rename_text.text = "iron_plate"
	_press(colors, "Give the selected color this name")
	await _frames(6)
	_results["colors: the status after a new name"] = dock._status.text
	_results["colors: looks that named iron"] = Array(users)
	_results["colors: looks that name iron_plate now"] = \
		Array(FigureEdits.looks_with_color(bench.store.looks, "iron_plate"))
	_results["colors: the palette has the new name only"] = \
		[bench.store.palette().has_color("iron_plate"), bench.store.palette().has_color("iron")]
	_results["colors: the tab selects the new name"] = colors.selected_color()
	await _pictures(dock, FigureDock.TAB_COLORS, "colors")
	_undo(bench)
	await _frames(6)
	_results["colors: one undo gives each file its old name"] = \
		[bench.store.palette().has_color("iron"),
		Array(FigureEdits.looks_with_color(bench.store.looks, "iron")) == Array(users)]


# ─── The outfit of an NPC def ───────────────────────────────────────────────

func _the_npc(bench: FigureWorkbench, dock: FigureDock) -> void:
	var bar := dock.outfit_bar()

	_results["npc: the rows of the list"] = bar._npcs.item_count
	_results["npc: the list is open to the author"] = not bar._npcs.disabled

	if bar._npcs.item_count < 2:
		return

	bar._npcs.select(1)
	bar._npcs.item_selected.emit(1)
	await _frames(6)
	_results["npc: the outfit of the stands"] = bench.outfit()
	_results["npc: the bar names the NPC def"] = bar.shown_npc()
	_results["npc: the status"] = dock._status.text
	_results["npc: the budget line of the dressed figure"] = dock._cost.text
	await _pictures(dock, FigureDock.TAB_GEAR, "npc")


# ─── The checks ─────────────────────────────────────────────────────────────

func _the_checks(bench: FigureWorkbench, dock: FigureDock) -> void:
	var check := dock.check_panel()

	dock.show_tab(FigureDock.TAB_CHECK)
	_press(check, "Check the figure files")
	await _frames(6)

	var faults := FigureChecks.faults_of(check.findings())

	_results["check: the summary of the first check"] = check._summary.text
	_results["check: the faults of the first check"] = _lines(faults)

	var good := bench.store.data_of(LOOK, KIT)
	var bad := good.duplicate(true)

	bad["parts"][0]["bone"] = "Tail"
	bench.put(LOOK, KIT, bad)
	_press(check, "Check the figure files")
	await _frames(6)
	faults = FigureChecks.faults_of(check.findings())
	_results["check: the faults with a part on a bone of no rig"] = _lines(faults)
	await _pictures(dock, FigureDock.TAB_CHECK, "check")

	if not faults.is_empty():
		check.finding_chosen.emit(faults[0])
		await _frames(6)
		_results["check: a click on that finding shows its kit part"] = \
			[dock.shown_tab(), dock.body_panel().edited_look(), dock.body_panel().selected_part()]

	bench.put(LOOK, KIT, good)
	await _frames(4)

	for finding: Dictionary in check.findings():
		if FigureChecks.is_note(finding):
			check.finding_chosen.emit(finding)
			await _frames(6)
			_results["check: a click on a note shows its row"] = [finding["key"],
				dock.shown_tab(), dock.gear_panel().selected_key(),
				bench.outfit().values().has(finding["key"])]
			break

	var limit := check._fields[FigureChecks.BUDGET_TRIANGLES] as SpinBox

	dock.show_tab(FigureDock.TAB_CHECK)
	limit.value = 100
	await _frames(4)
	_results["check: the budget line with a low budget"] = dock._cost.text
	await _pictures(dock, FigureDock.TAB_CHECK, "budget", false)
	limit.value = FigureChecks.DEFAULT_BUDGETS[FigureChecks.BUDGET_TRIANGLES]
	await _frames(4)
	_results["check: the budget line with the start budget"] = dock._cost.text


func _lines(found: Array) -> Array:
	var lines := []

	for finding: Dictionary in found:
		lines.append(FigureChecks.describe(finding))

	return lines


# ─── The save ───────────────────────────────────────────────────────────────

func _a_save(bench: FigureWorkbench, dock: FigureDock) -> void:
	_results["save: unsaved files before the save"] = bench.has_unsaved_changes()
	dock.save_requested.emit()
	await _frames(6)
	_results["save: the status"] = dock._status.text
	_results["save: the kit part is a file"] = \
		FileAccess.file_exists(bench.store.path_of(LOOK, KIT))
	_results["save: nothing is left to save"] = not bench.has_unsaved_changes()

	var served := FigureSet.read_file(bench.served_models_directory().path_join(
		FigureSet.FILE_NAME))

	_results["save: the served figure.json has the kit part"] = \
		served.error if not served.error.is_empty() else served.looks.has(KIT)


# ─── Helpers ────────────────────────────────────────────────────────────────

func _rig(bench: FigureWorkbench) -> FigureRig:
	return bench.store.rigs["body_1"]


func _look(bench: FigureWorkbench, key: String) -> FigureLook:
	return bench.store.looks[key]


func _row_of(gear: FigureGearPanel, key: String) -> int:
	for index in gear._rows.item_count:
		if gear._rows.get_item_metadata(index) == key:
			return index

	return -1


func _pick_row(gear: FigureGearPanel, key: String) -> void:
	var index := _row_of(gear, key)

	gear._rows.select(index)
	gear._rows.item_selected.emit(index)


## Press the button with one text below `node`.
func _press(node: Node, text: String) -> bool:
	for child: Node in node.get_children():
		if child is Button and (child as Button).text == text:
			(child as Button).pressed.emit()
			return true

		if _press(child, text):
			return true

	return false


## Save the 3D view and the whole window. The Figure dock is in front, on
## one tab, so the window picture shows the controls of that tab.
func _pictures(dock: FigureDock, tab: String, name_of: String, with_view := true) -> void:
	var view := EditorInterface.get_editor_viewport_3d(0)
	var page: Node = dock

	while page != null and not page.get_parent() is TabContainer:
		page = page.get_parent()

	if page != null:
		(page.get_parent() as TabContainer).current_tab = page.get_index()

	dock.show_tab(tab)
	await _frames(4)

	if with_view:
		view.get_texture().get_image().save_png(PICTURES % ("view_" + name_of))

	get_tree().root.get_texture().get_image().save_png(PICTURES % ("window_" + name_of))


func _history(bench: FigureWorkbench) -> UndoRedo:
	var manager := EditorInterface.get_editor_undo_redo()

	return manager.get_history_undo_redo(manager.get_object_history_id(bench))


func _undo(bench: FigureWorkbench) -> void:
	_undo_count += 1
	_results["undo %d did something" % _undo_count] = _history(bench).undo()


func _find_dock(node: Node) -> FigureDock:
	if node is FigureDock:
		return node

	for child: Node in node.get_children():
		var found := _find_dock(child)

		if found != null:
			return found

	return null


func _frames(count: int) -> void:
	for _frame in count:
		await get_tree().process_frame


func _only(node: Node) -> bool:
	var nodes := EditorInterface.get_selection().get_selected_nodes()

	return nodes.size() == 1 and nodes[0] == node
