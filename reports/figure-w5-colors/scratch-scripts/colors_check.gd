@tool
extends EditorPlugin
## Phase W5 check of DESIGN-0014, in a real editor window. It runs only in a
## scratch copy of the project, with a scratch copy of the figure files and
## of the model pipeline beside it. It opens the figure workbench, makes
## three tiers of one helm, changes the palette, gives the character a hair
## color, gives a greatsword a stance, moves a part of a tier with the
## gizmo, and saves. It writes each answer to
## `res://colors_check_result.json`. Then it closes the editor.

const SCENE := "res://addons/blackout_figure/figure_workbench.tscn"
const RESULT := "res://colors_check_result.json"
const PICTURES := "res://colors_check_%s.png"

const LOOK := FigureStore.KIND_LOOK

## Three tiers of one helm. The first two take the parts of the slot shape.
## The third one is a tier of the first one: a tier of a tier.
const RUSTY := "rusty_scrap_great_helm"
const SCRAP := "scrap_great_helm"
const COPPER := "copper_great_helm"
const PLAN := [
	[RUSTY, "head", {"metal": "rust"}],
	[SCRAP, "head", {"metal": "iron"}],
	[COPPER, RUSTY, {"metal": "copper", "trim": "copper_dark"}],
]

const SWORD := "copper_greatsword"
const SWORD_TYPE := "greatsword"

## The colors of one drag in the color picker.
const DRAG := ["c07a3a", "c88040", "d08848"]

## The move arrow of the gizmo, in units of the gizmo size. From
## `node_3d_editor_plugin.cpp`: the arrow offset is 1.4, and its size is 0.35.
const ARROW_CENTRE := 1.575
const DRAG_PIXELS := 60.0
const DRAG_STEPS := 6

var _results := {}
var _last := Vector2.ZERO
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
	dock.select_body("body_1")
	dock.body_changed.emit("body_1")
	await _frames(4)
	_results["store errors"] = Array(bench.store.errors)
	_results["the workbench writes its repository"] = bench.writes_repo()
	_results["the palette at the start"] = "%d color(s), %d role(s)" % [
		bench.store.palette().colors().size(), bench.store.palette().roles().size()]
	_results["the default clip set at the start"] = bench.store.stances().default_set()
	_results["the stance file"] = bench.stances_path()
	# The builder has no `@tool`, so the editor runs no static initializer of
	# it. This answer says if its material cache is a table there.
	_results["the material cache of the builder is a table in the editor"] = \
		typeof(FigureBuilder._role_materials) == TYPE_DICTIONARY

	await _the_tiers(bench, dock)
	await _the_palette(bench, dock)
	await _the_character(bench, dock)
	await _the_stances(bench, dock)
	await _a_tier_part_moves(bench, dock)
	await _a_save(bench, dock)

	var file := FileAccess.open(RESULT, FileAccess.WRITE)

	file.store_string(JSON.stringify(_results, "  "))
	file.close()
	get_tree().quit()


# ─── The tiers ──────────────────────────────────────────────────────────────

func _the_tiers(bench: FigureWorkbench, dock: FigureDock) -> void:
	var gear := dock.gear_panel()
	var part: String = bench.store.looks["head"].parts()[0]["name"]

	dock.show_tab(FigureDock.TAB_GEAR)
	await _frames(4)
	_results["lines of the slot shape file"] = bench.store.looks["head"].to_text().count("\n")

	for row: Array in PLAN:
		var key: String = row[0]

		_pick_row(gear, key)
		await _frames(6)
		_results["%s: the figure shows, before" % key] = bench.source_of("body_1", "head")
		FigureFields.select_text(gear._copy_from, row[1])
		gear._tier.pressed.emit()
		await _frames(6)
		_results["%s: status after the tier button" % key] = dock._status.text

		for role: String in row[2]:
			_pick_color(gear, role, row[2][role])
			await _frames(6)

		var look: FigureLook = bench.store.looks.get(key)

		if look == null:
			continue

		_results["%s: the file" % key] = look.to_text()
		_results["%s: lines of the file" % key] = look.to_text().count("\n")
		_results["%s: the figure shows, after" % key] = bench.source_of("body_1", "head")
		_results["%s: the row" % key] = gear._rows.get_item_text(_row_of(gear, key))
		_results["%s: the note" % key] = gear._note.text
		_results["%s: the color labels" % key] = _labels(gear)
		_results["%s: parts in the part editor" % key] = gear.parts_panel()._parts.item_count
		_results["%s: the metal on the two stands" % key] = [
			_hex(bench, "body_1", key, part, 0), _hex(bench, "body_2", key, part, 0)]
		_results["%s: the trim on body_1" % key] = _hex(bench, "body_1", key, part, 5)
		_results["%s: the cost" % key] = dock._cost.text
		await _pictures(dock, FigureDock.TAB_GEAR, key)

	_results["hair parts of the body that show below the copper helm"] = _shown_in(bench, "hair")
	_results["the hair box of the copper helm: ticked, and the author cannot change it"] = \
		_box_state(gear, "hair")

	_undo(bench)
	await _frames(6)
	_results["undo takes the trim of the copper helm back"] = \
		bench.store.looks[COPPER].colors()
	_redo(bench)
	await _frames(6)
	_results["redo gives it again"] = bench.store.looks[COPPER].colors()

	_pick_row(gear, RUSTY)
	await _frames(4)
	gear._remove_look.pressed.emit()
	await _frames(4)
	_results["a remove of the look that a tier names"] = dock._status.text
	_results["the look stays"] = bench.store.has(LOOK, RUSTY)

	var scroll := gear.get_parent() as ScrollContainer

	_pick_row(gear, COPPER)
	await _frames(6)
	scroll.scroll_vertical = int(gear._note.position.y) - 20
	await _frames(4)
	get_tree().root.get_texture().get_image().save_png(PICTURES % "window_gear_tier")
	scroll.scroll_vertical = 0


## Pick one color in the color table of the Gear tab, by the name of its
## color role.
func _pick_color(gear: FigureGearPanel, role: String, color: String) -> void:
	for index in range(0, gear._colors.get_child_count(), 2):
		var label := (gear._colors.get_child(index) as Label).text

		if label.trim_prefix(FigureGearPanel.OWN_MARK) == role:
			var list := gear._colors.get_child(index + 1) as OptionButton

			FigureFields.select_text(list, color)
			list.item_selected.emit(list.selected)
			return

	_results["no color list for the role %s" % role] = true


func _labels(gear: FigureGearPanel) -> Array:
	var labels := []

	for index in range(0, gear._colors.get_child_count(), 2):
		labels.append((gear._colors.get_child(index) as Label).text)

	return labels


func _box_state(gear: FigureGearPanel, region: String) -> Array:
	for child: Node in gear._hides.get_children():
		var box := child as CheckBox

		if box.text == region:
			return [box.button_pressed, box.disabled]

	return []


## The names of the body parts of one region that show on the stand of
## `body_1`.
func _shown_in(bench: FigureWorkbench, region: String) -> Array:
	var shown := []

	for row: Dictionary in bench.store.looks["body_1"].parts():
		if row["region"] == region and bench.part_node("body_1", "body_1", row["name"]) != null:
			shown.append(row["name"])

	return shown


## The color of one shape of one part on one stand, as six hex digits. ""
## for a part that the stand does not show.
func _hex(bench: FigureWorkbench, body_key: String, look_key: String, part: String,
		shape: int) -> String:
	var node := bench.part_node(body_key, look_key, part)

	if node == null or shape >= node.get_child_count():
		return ""

	var material := (node.get_child(shape) as MeshInstance3D).material_override

	return (material as StandardMaterial3D).albedo_color.to_html(false)


# ─── The palette ────────────────────────────────────────────────────────────

func _the_palette(bench: FigureWorkbench, dock: FigureDock) -> void:
	var colors := dock.colors_panel()
	var part: String = bench.store.looks["head"].parts()[0]["name"]
	var before := bench.store.palette().hex_of("copper")

	bench.wear("head", COPPER)
	dock.show_tab(FigureDock.TAB_COLORS)
	await _frames(6)
	_results["the Colors tab: rows, role rows, rows of the character"] = [
		colors._colors.item_count, colors._roles.get_child_count() / 2,
		colors._figure.get_child_count() / 2]
	_results["the palette button with a palette"] = colors._new_palette.disabled
	_click_color(colors, "copper")
	await _frames(4)
	_results["the users line of copper"] = colors._users.text
	_results["the picker shows copper"] = colors._picker.color.to_html(false)

	for hex: String in DRAG:
		colors._picker.color_changed.emit(Color(hex))
		await _frames(2)

	_results["copper in the palette after the drag"] = bench.store.palette().hex_of("copper")
	_results["the metal of the copper helm after the drag"] = _hex(bench, "body_1", COPPER, part, 0)
	_results["the row of copper after the drag"] = colors._colors.get_item_text(
		_color_row(colors, "copper"))
	_undo(bench)
	await _frames(6)
	_results["one undo brings the color of before the drag back"] = \
		bench.store.palette().hex_of("copper") == before
	_redo(bench)
	await _frames(6)

	FigureFields.select_text(colors._finish, MeshPalette.FINISH_METAL)
	colors._finish.item_selected.emit(colors._finish.selected)
	await _frames(6)
	_results["status after the finish"] = dock._status.text
	_results["the finish of copper in the file"] = bench.store.palette().finish_of("copper")
	_results["the metallic value of the copper helm"] = _metallic(bench, COPPER, part)
	await _pictures(dock, FigureDock.TAB_COLORS, "copper_metal")

	colors._remove.pressed.emit()
	await _frames(4)
	_results["a remove of a color that a look names"] = dock._status.text

	colors._new_name.text = "brass"
	colors._add_color.pressed.emit()
	await _frames(6)
	_results["a new named color"] = [bench.store.palette().has_color("brass"),
		colors.selected_color()]
	colors._remove.pressed.emit()
	await _frames(6)
	_results["a free color leaves"] = not bench.store.palette().has_color("brass")

	colors._new_role.text = "glow"
	colors._add_role.pressed.emit()
	await _frames(6)
	_results["a new color role"] = bench.store.palette().roles().get("glow", "")
	_results["status after the new role"] = dock._status.text

	var scroll := colors.get_parent() as ScrollContainer

	scroll.scroll_vertical = int(colors._roles.position.y) - 60
	await _frames(4)
	get_tree().root.get_texture().get_image().save_png(PICTURES % "window_colors_roles")
	scroll.scroll_vertical = 0


func _color_row(colors: FigureColorsPanel, color_name: String) -> int:
	for index in colors._colors.item_count:
		if colors._colors.get_item_metadata(index) == color_name:
			return index

	return -1


## Select one row of the color list, as a click does.
func _click_color(colors: FigureColorsPanel, color_name: String) -> void:
	var row := _color_row(colors, color_name)

	colors._colors.select(row)
	colors._colors.item_selected.emit(row)


func _metallic(bench: FigureWorkbench, look_key: String, part: String) -> float:
	var node := bench.part_node("body_1", look_key, part)
	var material := (node.get_child(0) as MeshInstance3D).material_override

	return (material as StandardMaterial3D).metallic


# ─── The colors of the character ────────────────────────────────────────────

func _the_character(bench: FigureWorkbench, dock: FigureDock) -> void:
	var colors := dock.colors_panel()
	var body_text: String = bench.store.looks["body_1"].to_text()

	bench.set_outfit({})
	await _frames(6)
	_results["the hair before"] = _hex(bench, "body_1", "body_1", "hair", 0)

	for index in range(0, colors._figure.get_child_count(), 2):
		if (colors._figure.get_child(index) as Label).text == "hair":
			var list := colors._figure.get_child(index + 1) as OptionButton

			FigureFields.select_text(list, "rust")
			list.item_selected.emit(list.selected)

	await _frames(6)
	_results["the colors of the character"] = bench.figure_colors()
	_results["the hair on the two stands"] = [_hex(bench, "body_1", "body_1", "hair", 0),
		_hex(bench, "body_2", "body_2", "hair", 0)]
	_results["the body file stays"] = bench.store.looks["body_1"].to_text() == body_text
	_results["the options file keeps the colors"] = dock.saved_figure_colors()

	var scroll := colors.get_parent() as ScrollContainer

	scroll.scroll_vertical = int(colors._figure.position.y) - 200
	await _frames(4)
	await _pictures(dock, FigureDock.TAB_COLORS, "character", false)
	scroll.scroll_vertical = 0
	bench.set_figure_colors({})
	await _frames(4)
	_results["the hair after the colors go"] = _hex(bench, "body_1", "body_1", "hair", 0)


# ─── The stances ────────────────────────────────────────────────────────────

func _the_stances(bench: FigureWorkbench, dock: FigureDock) -> void:
	var clips := dock.clips_panel()

	dock.show_tab(FigureDock.TAB_CLIPS)
	bench.wear("two_hands", SWORD)
	await _frames(8)
	_results["the stance list after the outfit holds a greatsword"] = clips.selected_stance()
	_results["the stance note, before"] = clips._stance_note.text
	_results["rows of the stance table"] = clips._stance_grid.get_child_count() \
		/ FigureClipsPanel.STANCE_COLUMNS
	_results["the first choice of the walk list"] = _stance_list(clips, "walk").get_item_text(0)

	FigureFields.select_text(_stance_list(clips, "walk"), "idle")
	_stance_list(clips, "walk").item_selected.emit(_stance_list(clips, "walk").selected)
	await _frames(8)
	_results["status after the stance"] = dock._status.text
	_results["the stance of a greatsword"] = bench.store.stances().stances().get(SWORD_TYPE, {})
	_results["the stance note, after"] = clips._stance_note.text
	_results["the stance list keeps its choice"] = clips.selected_stance()
	_results["the row of the stance list"] = clips._stance.get_item_text(clips._stance.selected)

	_stance_button(clips, "walk").pressed.emit()
	await get_tree().create_timer(0.4).timeout
	_results["the play button plays"] = [bench.is_playing(), bench.shown_clip()]
	_results["the run button with no clip"] = _stance_button(clips, "run").disabled

	var scroll := clips.get_parent() as ScrollContainer

	scroll.scroll_vertical = int(clips._stance.position.y) - 60
	await _frames(4)
	await _pictures(dock, FigureDock.TAB_CLIPS, "stance", false)
	scroll.scroll_vertical = 0
	bench.stop_clip()
	await _frames(4)

	_undo(bench)
	await _frames(6)
	_results["undo takes the stance away"] = not bench.store.stances().has_stance(SWORD_TYPE)
	_redo(bench)
	await _frames(6)
	_results["redo brings the stance back"] = bench.store.stances().has_stance(SWORD_TYPE)


func _stance_list(clips: FigureClipsPanel, action: String) -> OptionButton:
	return clips._stance_grid.get_child(FigureStances.ACTIONS.find(action)
		* FigureClipsPanel.STANCE_COLUMNS + 1) as OptionButton


func _stance_button(clips: FigureClipsPanel, action: String) -> Button:
	return clips._stance_grid.get_child(FigureStances.ACTIONS.find(action)
		* FigureClipsPanel.STANCE_COLUMNS + 2) as Button


# ─── A move of a part of a tier ─────────────────────────────────────────────

func _a_tier_part_moves(bench: FigureWorkbench, dock: FigureDock) -> void:
	var gear := dock.gear_panel()
	var part: String = bench.store.looks["head"].parts()[0]["name"]
	var tier_text: String = bench.store.looks[COPPER].to_text()
	var rusty_text: String = bench.store.looks[RUSTY].to_text()

	dock.show_tab(FigureDock.TAB_GEAR)
	bench.set_outfit({})
	bench.wear("head", COPPER)
	await _frames(8)

	var node := bench.part_node("body_1", COPPER, part)
	var other := bench.part_node("body_2", COPPER, part)
	var before := node.position

	await _click(_screen_point((node.get_child(0) as Node3D).global_position))
	_results["a click selects the part of a tier"] = _only(node)
	_results["the Gear tab goes to the row of the tier"] = gear.selected_key()
	await _drag_arrow(node)
	await _frames(6)
	_results["the gizmo moves the part of the tier"] = str(node.position - before)
	_results["the move is in the slot shape"] = FigureLook.part_transform(
		bench.store.looks["head"].part(part)).origin.distance_to(node.position) < 0.0001
	_results["the two tier files stay"] = bench.store.looks[COPPER].to_text() == tier_text \
		and bench.store.looks[RUSTY].to_text() == rusty_text
	_results["the part follows on the other stand"] = \
		other.position.distance_to(node.position) < 0.0001
	await _click(_screen_point(Vector3(0.0, 0.0, 1.5)))


# ─── The save ───────────────────────────────────────────────────────────────

func _a_save(bench: FigureWorkbench, dock: FigureDock) -> void:
	_results["scene save"] = EditorInterface.save_scene()
	await _frames(5)
	_results["unsaved after the save"] = bench.has_unsaved_changes()
	_results["dock status after the save"] = dock._status.text

	var figure_set := FigureSet.read_file(
		bench.served_models_directory().path_join(FigureSet.FILE_NAME))
	var tiers := {}

	for key: String in [RUSTY, SCRAP, COPPER]:
		tiers[key] = figure_set.looks.has(key) \
			and figure_set.looks[key].to_text() == bench.store.looks[key].to_text()

	_results["the served figure set has each tier"] = tiers
	_results["the served figure set has the palette"] = \
		figure_set.palette.to_text() == bench.store.palette().to_text()
	_results["errors of the served figure set"] = Array(figure_set.errors)
	_results["the palette file has the metal finish"] = FileAccess.get_file_as_string(
		bench.store.path_of(FigureStore.KIND_PALETTE, FigureStore.KIND_PALETTE)) \
		.contains("\"finish\": \"metal\"")
	_results["the stance file"] = FileAccess.get_file_as_string(bench.stances_path())
	_results["the saved scene holds no skeleton"] = \
		not FileAccess.get_file_as_string(SCENE).contains(FigureBuilder.SKELETON_NAME)


# ─── Helpers ────────────────────────────────────────────────────────────────

func _row_of(gear: FigureGearPanel, key: String) -> int:
	for index in gear._rows.item_count:
		if gear._rows.get_item_metadata(index) == key:
			return index

	return -1


func _pick_row(gear: FigureGearPanel, key: String) -> void:
	var index := _row_of(gear, key)

	gear._rows.select(index)
	gear._rows.item_selected.emit(index)


## Save the 3D view and the whole window. The Figure dock is in front, on
## one tab, so the window picture shows the controls of that tab. With
## `to_top` false, the tab keeps its scroll place.
func _pictures(dock: FigureDock, tab: String, name_of: String, to_top := true) -> void:
	var view := EditorInterface.get_editor_viewport_3d(0)
	var page: Node = dock

	while page != null and not page.get_parent() is TabContainer:
		page = page.get_parent()

	if page != null:
		(page.get_parent() as TabContainer).current_tab = page.get_index()

	dock.show_tab(tab)
	await _frames(4)

	if to_top:
		view.get_texture().get_image().save_png(PICTURES % ("view_" + name_of))

	get_tree().root.get_texture().get_image().save_png(PICTURES % ("window_" + name_of))


func _history(bench: FigureWorkbench) -> UndoRedo:
	var manager := EditorInterface.get_editor_undo_redo()

	return manager.get_history_undo_redo(manager.get_object_history_id(bench))


func _undo(bench: FigureWorkbench) -> void:
	_undo_count += 1
	_results["undo %d did something" % _undo_count] = _history(bench).undo()


func _redo(bench: FigureWorkbench) -> void:
	_history(bench).redo()


func _find_dock(node: Node) -> FigureDock:
	if node is FigureDock:
		return node

	for child: Node in node.get_children():
		var found := _find_dock(child)

		if found != null:
			return found

	return null


## The point of the editor window that shows a world point of the 3D view.
func _screen_point(world: Vector3) -> Vector2:
	var view := EditorInterface.get_editor_viewport_3d(0)
	var container := view.get_parent() as Control
	var camera := view.get_camera_3d()
	var scale := container.size / Vector2(view.size)

	return container.global_position + camera.unproject_position(world) * scale


func _click(at: Vector2) -> void:
	await _move(at)
	await _button(at, true)
	await _button(at, false)
	await _frames(6)


## Drag the X arrow of the move gizmo of a selected node.
func _drag_arrow(node: Node3D) -> void:
	var settings := EditorInterface.get_editor_settings()
	var size := float(settings.get_setting("editors/3d/manipulator_gizmo_size")) \
		* EditorInterface.get_editor_scale()
	var origin := _screen_point(node.global_position)
	var along := (_screen_point(node.global_position + Vector3.RIGHT * 0.2) - origin).normalized()
	var start := origin + along * size * ARROW_CENTRE

	await _move(start)
	await _button(start, true)

	for step in DRAG_STEPS:
		await _move(start + along * DRAG_PIXELS * (step + 1) / DRAG_STEPS, true)

	await _button(start + along * DRAG_PIXELS, false)
	await _frames(4)


func _move(at: Vector2, held := false) -> void:
	var event := InputEventMouseMotion.new()

	event.position = at
	event.global_position = at
	event.relative = at - _last
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if held else 0
	_last = at
	Input.parse_input_event(event)
	await _frames(2)


func _button(at: Vector2, pressed: bool) -> void:
	var event := InputEventMouseButton.new()

	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = pressed
	event.position = at
	event.global_position = at
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
	Input.parse_input_event(event)
	await _frames(2)


func _frames(count: int) -> void:
	for _frame in count:
		await get_tree().process_frame


func _only(node: Node) -> bool:
	var nodes := EditorInterface.get_selection().get_selected_nodes()

	return nodes.size() == 1 and nodes[0] == node
