extends Node
## Tests for the panel of the figure workbench (DESIGN-0014 Phases W1 to
## W6): [FigureDock], [FigureRigPanel], [FigureBodyPanel],
## [FigureClipsPanel], [FigureColorsPanel], [FigureFamiliesPanel], and
## [FigureOutfitBar]. The Gear dock has its own test,
## `test_gear_dock.tscn`, and the part editor has `test_part_editor.tscn`.
##
##     godot --headless --path godot res://tests/test_figure_dock.tscn
##
## Needs nothing running and no editor. The dock does not persist here, so
## the test writes no file. The cases:
##
## 1. The dock has the six tabs and no Gear tab, and it shows the body
##    types, the cost, and the line of the selected item.
## 2. The Rig tab shows each bone. A selected bone shows its position, and
##    a changed field sends the new position.
## 3. The Rig tab has one row for each slot, and a new choice sends the slot
##    and its bone.
## 4. The Body tab shows each part in the tree. A selected part shows its
##    place, and a changed field sends the place of the part.
## 5. The Body tab shows the fields of the selected shape, and a changed
##    field sends the value as the file holds it.
## 6. A panel that shows new content sends no signal.
## 7. The Clips tab shows each clip and each clip list. Its play bar and
##    its clip form send what the author chose.
## 8. The outfit bar has one cell for each slot. It shows an outfit, and a
##    cell sends its slot and the chosen key.
## 9. The Body tab has no fit control, and it sends the file of a
##    reference body.
## 10. The Colors tab shows each named color and each color role (Phase
##     W5). It sends a new color, a finish, a role, and a color of the
##     character. A palette with a file has no "New palette" button.
## 11. The Clips tab shows the stance of each tool type. A clip list sends
##     its action and its clip, and a play button plays the clip that the
##     stance has for its action.
## 12. The top strip counts the unsaved files on the Save button, and the
##     revert question names them (ENG-0011). The play bar of the dock
##     sends a play, a seek, and nothing for a shown time.
## 13. The session goes to the session file, and the budgets go to the
##     repository file. The folds keep their state.
## 14. A part rename goes out when the field loses the focus. Each vector
##     field names its axis. The rotation row of the Rig tab is off for a
##     bone of the body.
## 15. The Families tab lists each family, and it sends a chosen family,
##     a new row, a removed row, and a model.

const TOLERANCE := 0.0001

## The length of the test clip, in seconds.
const WALK_LENGTH := 2.0

## The items of the test catalog.
const SWORD := "iron_sword"
const STICK := "wood_sword"
const HELM := "iron_helm"

## The height of the fit that one case gives a part.
const FIT_HEIGHT := 0.25

var _failures := 0
var _sent := []


func _ready() -> void:
	_the_dock_shows_the_body_types()
	_the_rig_tab_shows_and_sends_a_bone()
	_the_rig_tab_has_a_row_for_each_slot()
	_the_body_tab_shows_and_sends_a_part()
	_the_body_tab_shows_and_sends_a_shape()
	_the_clips_tab_shows_and_sends_a_clip()
	_the_outfit_bar_shows_and_sends_a_slot()
	_the_body_tab_sends_a_reference_body()
	_the_colors_tab_shows_and_sends_a_color()
	_the_clips_tab_shows_and_sends_a_stance()
	_the_top_strip_and_the_play_bar_send()
	_the_session_and_the_budgets_have_their_files()
	_a_rename_goes_out_on_a_focus_loss()
	_the_colors_tab_shows_and_sends_a_finish()
	_the_families_tab_shows_and_sends_a_family()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_dock")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _rig() -> FigureRig:
	return FigureEdits.rig_from_profile("body_1")


## Keep each argument list that a signal of a panel sends.
func _record(sent: Signal, name_of: String) -> void:
	sent.connect(func(a: Variant = null, b: Variant = null, c: Variant = null,
			d: Variant = null) -> void:
		_sent.append([name_of, a, b, c, d]))


func _the_dock_shows_the_body_types() -> void:
	var dock := FigureDock.new()
	var tabs: TabContainer = dock._tabs

	dock.persist = false
	add_child(dock)
	_expect(tabs.get_tab_title(0) == FigureDock.TAB_RIG
		and tabs.get_tab_title(1) == FigureDock.TAB_BODY
		and tabs.get_tab_title(2) == FigureDock.TAB_COLORS
		and tabs.get_tab_title(3) == FigureDock.TAB_FAMILIES
		and tabs.get_tab_title(4) == FigureDock.TAB_CLIPS
		and tabs.get_tab_title(5) == FigureDock.TAB_CHECK and tabs.get_tab_count() == 6,
		"the dock has the Rig, Body, Colors, Families, Clips, and Check tabs, and no Gear tab")
	_expect(dock.active_body().is_empty(), "a dock with no rig has no body type")

	dock.set_bodies(PackedStringArray(["body_1", "body_2"]))
	_expect(dock.active_body() == "body_1", "the first body type is the choice")
	dock.select_body("body_2")
	dock.set_bodies(PackedStringArray(["body_0", "body_1", "body_2"]))
	_expect(dock.active_body() == "body_2", "a new list keeps the choice")
	dock.set_bodies(PackedStringArray(["body_1"]))
	_expect(dock.active_body() == "body_1", "a choice that left goes to the first body type")

	dock.set_cost({"parts": 18, "draws": 30, "triangles": 1200})
	_expect(dock._cost.text.contains("18") and dock._cost.text.contains("30")
		and dock._cost.text.contains("1200"), "the cost line gives the three counts")
	dock.set_status("ready")
	_expect(dock._status.text == "ready", "the status box shows the status")
	_expect(not dock._item_line.visible, "a dock with no selected item shows no item line")
	dock.set_item_line("iron sword, slot main_hand")
	_expect(dock._item_line.visible and dock._item_line.text.contains("iron sword"),
		"the item line shows the selected item")
	_expect(dock.shown_tab() == FigureDock.TAB_RIG, "the first tab shows at first")
	dock.show_tab(FigureDock.TAB_CLIPS)
	_expect(dock.shown_tab() == FigureDock.TAB_CLIPS and dock.clips_panel() != null
		and dock.outfit_bar() != null, "the dock shows a tab by its title")
	_expect(dock.saved_outfit().is_empty(), "a dock that does not persist has no saved outfit")
	dock.queue_free()


func _the_rig_tab_shows_and_sends_a_bone() -> void:
	var panel := FigureRigPanel.new()
	var rig := _rig()

	add_child(panel)
	_sent.clear()
	_record(panel.bone_chosen, "bone_chosen")
	_record(panel.bone_moved, "bone_moved")
	panel.set_rig(rig)
	_expect(_count_items(panel._bones.get_root()) == rig.bones().size(),
		"the tree has one item for each bone")
	_expect(panel.selected_bone().is_empty(), "no bone is selected at first")

	panel.select_bone("hand_r")
	_expect(panel.selected_bone() == "hand_r", "a bone is selected by its name")
	_expect(panel._bones.get_selected().get_text(0) == "[hand_r]", "a socket is in brackets")
	_expect(FigureFields.vector_of(panel._position).is_equal_approx(
		rig.rest_of("hand_r").origin), "the fields show the position of the bone")
	_expect(_sent.is_empty(), "a selection by code sends nothing: %s" % [_sent])

	(panel._position.get_child(1) as SpinBox).value = 0.25
	_expect(_sent.size() == 1 and _sent[0][0] == "bone_moved" and _sent[0][1] == "hand_r"
		and is_equal_approx(_sent[0][2].y, 0.25)
		and is_equal_approx(_sent[0][2].x, rig.rest_of("hand_r").origin.x),
		"a changed field sends the bone and its new position: %s" % [_sent])

	_sent.clear()
	panel.set_rig(rig)
	_expect(panel.selected_bone() == "hand_r" and _sent.is_empty(),
		"the same rig keeps the selection and sends nothing")
	panel.set_rig(null)
	_expect(panel.selected_bone().is_empty() and _sent.is_empty(), "no rig shows no bone")
	panel.queue_free()


func _count_items(item: TreeItem) -> int:
	var count := 0

	for child: TreeItem in item.get_children():
		count += 1 + _count_items(child)

	return count


func _the_rig_tab_has_a_row_for_each_slot() -> void:
	var panel := FigureRigPanel.new()
	var rig := _rig()
	var slots := rig.slots().keys()

	add_child(panel)
	_sent.clear()
	_record(panel.slot_changed, "slot_changed")
	panel.set_rig(rig)
	slots.sort()
	_expect(panel._slots.get_child_count() == slots.size() * 2,
		"the slot table has one label and one list for each slot")

	for index in slots.size():
		var list := panel._slots.get_child(index * 2 + 1) as OptionButton

		_expect((panel._slots.get_child(index * 2) as Label).text == slots[index]
			and FigureFields.text_of(list) == rig.slots()[slots[index]],
			"the row of %s shows its bone" % slots[index])

	var first := panel._slots.get_child(1) as OptionButton

	_expect(_sent.is_empty(), "a filled slot table sends nothing")
	FigureFields.select_text(first, "Hips")
	first.item_selected.emit(first.selected)
	_expect(_sent.size() == 1 and _sent[0][1] == slots[0] and _sent[0][2] == "Hips",
		"a new choice sends the slot and its bone: %s" % [_sent])
	panel.queue_free()


func _the_body_tab_shows_and_sends_a_part() -> void:
	var panel := FigureBodyPanel.new()
	var rig := _rig()
	var body := FigureEdits.mannequin(rig)

	add_child(panel)
	_sent.clear()
	_record(panel.part_chosen, "part_chosen")
	_record(panel.part_placed, "part_placed")
	_record(panel.part_region_changed, "part_region_changed")
	panel.set_content(rig, body)
	_expect(panel.part_count() == body.parts().size()
		and panel._tree.get_root().get_child_count() == body.parts().size(),
		"the tree has one row for each part")
	_expect(panel.selected_part().is_empty(), "no part is selected at first")

	panel.select_part("head")
	_expect(panel.selected_part() == "head" and panel._name.text == "head"
		and FigureFields.text_of(panel._bone) == "Head"
		and FigureFields.text_of(panel._region) == "head",
		"a selected part shows its name, its bone, and its region")
	_expect(_sent.is_empty(), "a selection by code sends nothing: %s" % [_sent])

	(panel._place_rotation.get_child(1) as SpinBox).value = 90.0
	(panel._place_position.get_child(0) as SpinBox).value = 0.1
	_expect(_sent.size() == 2 and _sent[1][0] == "part_placed" and _sent[1][1] == "head",
		"each changed place field sends the place of the part: %s" % [_sent])

	var place: Transform3D = _sent[1][2]

	_expect(place.origin.is_equal_approx(Vector3(0.1, 0.0, 0.0))
		and place.basis.x.distance_to(Vector3(0.0, 0.0, -1.0)) < TOLERANCE,
		"the place has the position, and the turn in radians")

	_sent.clear()
	panel._region.select(0)
	panel._region.item_selected.emit(0)
	_expect(_sent.size() == 1 and _sent[0][2] == "", "the first region choice is no region")

	_sent.clear()
	panel._tree.get_root().get_child(0).select(PartEditor.COLUMN_NAME)
	_expect(_sent.size() == 1 and _sent[0][0] == "part_chosen"
		and _sent[0][1] == body.parts()[0]["name"], "a picked row sends its part")

	_sent.clear()
	panel.set_content(rig, null)
	_expect(panel.part_count() == 0 and panel.selected_part().is_empty()
		and _sent.is_empty(), "a body type with no body shows no part")
	panel.queue_free()


func _the_body_tab_shows_and_sends_a_shape() -> void:
	var panel := FigureBodyPanel.new()
	var rig := _rig()
	var body := FigureEdits.mannequin(rig)
	var data: Dictionary = body.data.duplicate(true)

	# The second shape of the part is a ball, so the two shapes have other
	# fields.
	FigureEdits.add_shape(data, "upper_arm_l", FamilyShapes.SHAPE_SPHERE)
	body = FigureLook.from_data(data)

	var limb: Dictionary = body.part("upper_arm_l")["shapes"][0]

	add_child(panel)
	_sent.clear()
	_record(panel.shape_edited, "shape_edited")
	panel.set_content(rig, body)
	panel.select_part("upper_arm_l")
	_expect(panel._tree.get_selected().get_child_count() == 2 and panel.selected_shape() == 0
		and not panel.shape_row_selected(),
		"the tree shows each shape below its part, and the grid shows the first one")

	for field: String in FigureEdits.fields_of(limb):
		_expect(panel._field_controls.has(field), "the shape has a control for %s" % field)

	_expect(FigureFields.vector_of(panel._field_controls["size"]).is_equal_approx(
			FigureJson.vector3(limb["size"]))
		and is_equal_approx((panel._field_controls["top_width"] as SpinBox).value,
			limb["top_width"])
		and FigureFields.text_of(panel._field_controls["color"]) == limb["color"],
		"the controls show the values of the shape")
	_expect(not (panel._field_controls["diamond"] as CheckBox).button_pressed
		and (panel._field_controls["lean_x"] as SpinBox).min_value < 0.0,
		"a prism has a diamond flag, and its lean can go to each side")
	_expect(_sent.is_empty(), "a shown shape sends nothing: %s" % [_sent])

	(panel._field_controls["top_width"] as SpinBox).value = 0.07
	_expect(_sent.size() == 1
		and _sent[0] == ["shape_edited", "upper_arm_l", 0, "top_width", 0.07],
		"a changed length sends the part, the shape, the field, and the value: %s" % [_sent])

	_sent.clear()
	((panel._field_controls["rotation"] as HBoxContainer).get_child(2) as SpinBox).value = 180.0
	_expect(_sent.size() == 1 and _sent[0][3] == "rotation"
		and is_equal_approx(_sent[0][4].z, PI), "an angle goes out in radians: %s" % [_sent])

	_sent.clear()
	(panel._field_controls["segments"] as SpinBox).value = 12.0
	_expect(_sent.size() == 1 and typeof(_sent[0][4]) == TYPE_INT and _sent[0][4] == 12,
		"a count goes out as an integer: %s" % [_sent])

	_sent.clear()
	panel.select_shape(1)
	_expect(not panel._field_controls.has("size") and panel._field_controls.has("radius")
		and panel.shape_row_selected() and panel.selected_shape() == 1,
		"another shape shows the fields of its kind")
	_expect(_sent.is_empty(), "a selection by code sends nothing")
	panel.queue_free()


func _the_clips_tab_shows_and_sends_a_clip() -> void:
	var panel := FigureClipsPanel.new()
	var library := AnimationLibrary.new()
	var walk := Animation.new()
	var list := FigureClipList.from_data({"format": 1, "key": "pack", "file": "rig.glb",
		"skeleton": "Rig/Skeleton3D", "bones": {"Hips": "hips"},
		"clips": {"walk": {"from": "Walking", "loop": true}}})

	walk.length = WALK_LENGTH
	walk.loop_mode = Animation.LOOP_LINEAR
	library.add_animation("walk", walk)
	library.add_animation("bow", Animation.new())
	add_child(panel)
	_sent.clear()

	for pair: Array in [[panel.clip_chosen, "clip_chosen"], [panel.play_requested, "play"],
			[panel.probe_toggled, "probe"], [panel.clip_set, "clip_set"],
			[panel.clip_removed, "clip_removed"], [panel.source_clips_requested, "source"],
			[panel.build_asked, "build_asked"]]:
		_record(pair[0], pair[1])

	panel.set_clips(library)
	panel.set_clip_lists({"pack": list}, {"pack": PackedStringArray(["Running", "Walking"])})
	_expect(panel._clips.item_count == 2 and panel._clips.get_item_text(1).contains("loop")
		and not panel._clips.get_item_text(0).contains("loop"),
		"the clip list shows each clip, with its loop")
	_expect(panel._lists.text.contains("walk from Walking") and panel._from.item_count == 2,
		"the tab shows each clip list and the clips of its source")
	panel.select_clip("walk")
	_expect(panel.selected_clip() == "walk" and is_equal_approx(panel.selected_length(), WALK_LENGTH)
		and _sent.is_empty(), "a clip that code selects sends nothing: %s" % [_sent])

	panel._probe.button_pressed = true
	_expect(_sent == [["probe", true, null, null, null]] and panel.probe_shown(),
		"the probe box sends its state: %s" % [_sent])

	_sent.clear()
	panel._from.select(0)
	panel._from.item_selected.emit(0)
	panel._name.text = " run "
	panel._loop.button_pressed = true
	panel._put.pressed.emit()
	panel._take.pressed.emit()
	panel._list_source.pressed.emit()
	panel._build.pressed.emit()
	_expect(_sent == [["clip_set", "pack", "run", "Running", true],
			["clip_removed", "pack", "walk", null, null], ["source", "pack", null, null, null],
			["build_asked", null, null, null, null]],
		"the clip form sends the clip list, the name, the source clip, and the loop: %s"
			% [_sent])

	var question := FigureClipsPanel._overwrite_text(PackedStringArray(["a.res", "b.res"]))

	_expect(question.contains("2 clip file(s)") and question.contains("a.res")
		and FigureClipsPanel._overwrite_text(PackedStringArray()) == FigureClipsPanel.BUILD_NEW,
		"the build question counts and names the files that it writes over")
	panel.set_building(true)
	_expect(panel._build.disabled and panel._list_source.disabled
		and panel._build.tooltip_text == FigureClipsPanel.BUILD_BUSY,
		"a build turns the two build buttons off, with the reason")
	panel.set_building(false)
	_expect(not panel._build.disabled and panel._build.tooltip_text != FigureClipsPanel.BUILD_BUSY,
		"the end of a build turns them on again")
	panel.queue_free()


## A catalog of three slots and three items. The sword has a worn look, the
## stick has none, and the slot of the helm has no slot shape.
func _catalog() -> FigureCatalog:
	var items := []

	for row: Array in [[SWORD, "main_hand", 1], [STICK, "main_hand", 0], [HELM, "head", 1]]:
		items.append({"key": row[0], "name": row[0].replace("_", " "), "slot": row[1],
			"tool_type": "", "tier": row[2], "family": "weapon"})

	return FigureCatalog.from_data({"format": 1, "items": items, "slots": [
		{"key": "main_hand", "label": "Main Hand", "clears": ["two_hands"]},
		{"key": "two_hands", "label": "Two Hands", "clears": ["main_hand"]},
		{"key": "head", "label": "Head", "clears": []},
	]})


func _the_outfit_bar_shows_and_sends_a_slot() -> void:
	var bar := FigureOutfitBar.new()
	var catalog := _catalog()

	add_child(bar)
	_sent.clear()
	_record(bar.slot_set, "slot_set")
	_record(bar.cleared, "cleared")
	bar.set_catalog(catalog)
	_expect(bar._cells.size() == catalog.slot_keys().size()
		and bar._grid.get_child_count() == catalog.slot_keys().size() * 2,
		"the bar has one label and one cell for each slot")

	var hand: OptionButton = bar._cells["main_hand"]

	_expect(hand.item_count == 2 + catalog.items_of("main_hand").size()
		and hand.get_item_metadata(2) == STICK and hand.get_item_metadata(3) == SWORD,
		"a cell lists nothing, the slot shape, and each item of its slot by tier")
	bar.set_catalog(catalog)
	_expect(bar._cells["main_hand"] == hand, "the same catalog keeps the cells")

	bar.set_outfit({"main_hand": SWORD, "head": "head"})
	_expect(bar.shown_in("main_hand") == SWORD and bar.shown_in("head") == "head"
		and bar.shown_in("two_hands").is_empty() and _sent.is_empty(),
		"a shown outfit sends nothing: %s" % [_sent])

	hand.select(2)
	hand.item_selected.emit(2)
	hand.select(0)
	hand.item_selected.emit(0)
	bar._clear.pressed.emit()
	_expect(_sent == [["slot_set", "main_hand", STICK, null, null],
			["slot_set", "main_hand", "", null, null], ["cleared", null, null, null, null]],
		"a cell sends its slot and the chosen key, and the button clears: %s" % [_sent])
	bar.set_outfit({})
	_expect(bar.shown_in("head").is_empty(), "an empty outfit shows nothing in each cell")
	bar._fold.button_pressed = false
	_expect(not bar._rows.visible, "the fold hides the cells")
	bar.queue_free()


func _the_body_tab_sends_a_reference_body() -> void:
	var panel := FigureBodyPanel.new()
	var rig := _rig()

	add_child(panel)
	_sent.clear()
	_record(panel.reference_requested, "reference")
	panel.set_content(rig, FigureEdits.mannequin(rig))
	panel.set_reference_name(rig.key())
	_expect(not panel._fit.visible and not panel._fit_all.visible,
		"the Body tab has no fit control: a body serves one body type")
	_expect(panel._save_dialog.current_file == FigureReference.ROOT_PREFIX + rig.key()
		+ FigureReference.FILE_SUFFIX, "the save box starts with the name of the body type")
	panel._save_dialog.file_selected.emit("C:/art/reference_body_1.glb")
	_expect(_sent == [["reference", "C:/art/reference_body_1.glb", null, null, null]],
		"the Body tab sends the file of a reference body: %s" % [_sent])
	panel.queue_free()


func _the_colors_tab_shows_and_sends_a_color() -> void:
	var panel := FigureColorsPanel.new()
	var palette := FigureEdits.new_palette()
	var looks := {"main_hand": FigureEdits.slot_shape(_rig(), "main_hand")}
	var steel: String = looks["main_hand"].colors()[FigureEdits.ROLE_METAL]

	add_child(panel)
	_sent.clear()

	for pair: Array in [[panel.palette_requested, "palette"], [panel.color_set, "color"],
			[panel.finish_changed, "finish"], [panel.color_removed, "removed"],
			[panel.role_changed, "role"], [panel.role_removed, "no_role"],
			[panel.figure_color_changed, "figure"]]:
		_record(pair[0], pair[1])

	panel.set_content(FigurePalette.new(), false, {}, [], {})
	_expect(not panel._new_palette.disabled and panel._colors.item_count == 0
		and panel._note.text == FigureColorsPanel.NO_PALETTE and panel._picker.disabled,
		"a store with no palette file offers a new palette, and it shows no color")
	panel._new_palette.pressed.emit()
	_expect(_sent == [["palette", null, null, null, null]],
		"the palette button asks for a palette: %s" % [_sent])

	_sent.clear()
	panel.set_content(palette, true, looks, ["skin", "hair"], {"skin": steel})
	_expect(panel._new_palette.disabled
		and panel._colors.item_count == palette.colors().size()
		and panel._roles.get_child_count() == palette.roles().size() * 2,
		"a palette shows one row for each named color and for each color role")
	_expect(panel._figure.get_child_count() == 4
		and FigureFields.text_of(panel._figure.get_child(3)) == steel
		and FigureFields.text_of(panel._figure.get_child(1)) == FigureColorsPanel.OF_THE_LOOK,
		"the table of the character has each color role of the body, in sorted order")

	panel.select_color(steel)
	_expect(panel.selected_color() == steel and not panel._picker.disabled
		and panel._picker.color.is_equal_approx(palette.color_of(steel))
		and panel._users.text.contains("main_hand"),
		"a selected color shows its color and each look that names it")
	_expect(_sent.is_empty(), "a shown palette and a color that code selects send nothing: %s"
		% [_sent])

	panel._picker.color_changed.emit(Color("102030"))
	FigureFields.select_text(panel._finish, MeshPalette.FINISH_METAL)
	panel._finish.item_selected.emit(panel._finish.selected)
	panel._remove.pressed.emit()
	panel._new_name.text = " brass "
	panel._add_color.pressed.emit()
	_expect(_sent == [["color", steel, Color("102030"), null, null],
			["finish", steel, MeshPalette.FINISH_METAL, null, null],
			["removed", steel, null, null, null],
			["color", "brass", FigureColorsPanel.NEW_COLOR, null, null]],
		"the color rows send a color, a finish, a removed color, and a new color: %s" % [_sent])

	var role: String = (panel._roles.get_child(0) as Label).text
	var role_list := panel._roles.get_child(1) as OptionButton
	var hair_list := panel._figure.get_child(1) as OptionButton

	_sent.clear()
	_expect(FigureFields.text_of(role_list) == palette.roles()[role],
		"a role list shows the named color of its color role")
	FigureFields.select_text(role_list, steel)
	role_list.item_selected.emit(role_list.selected)
	role_list.item_selected.emit(0)
	panel._new_role.text = " glow "
	panel._add_role.pressed.emit()
	FigureFields.select_text(hair_list, steel)
	hair_list.item_selected.emit(hair_list.selected)
	hair_list.item_selected.emit(0)
	_expect(_sent == [["role", role, steel, null, null], ["no_role", role, null, null, null],
			["role", "glow", MeshPalette.GENERIC, null, null],
			["figure", "hair", steel, null, null], ["figure", "hair", "", null, null]],
		"the role table and the table of the character each send a role and a color: %s"
			% [_sent])
	panel.queue_free()


## The Finishes section of the Colors tab (ENG-0011, step L4): one row for
## each finish of the file, the two numbers of the selected one, and the
## signals of a changed number, a new finish, and a removed finish.
func _the_colors_tab_shows_and_sends_a_finish() -> void:
	var panel := FigureColorsPanel.new()
	var palette := FigureEdits.new_palette()

	add_child(panel)
	_sent.clear()
	_record(panel.finish_set, "finish_set")
	_record(panel.finish_removed, "finish_removed")
	panel.set_content(palette, true, {}, [], {})
	_expect(panel._finishes.item_count == palette.finishes().size()
		and not panel._metalness.editable and panel._remove_finish.disabled,
		"the finish list has one row for each finish, and no finish is selected")
	_expect(panel._finish.item_count == palette.finish_names().size(),
		"the finish list of a color offers each finish of the palette")

	panel.select_finish(MeshPalette.FINISH_METAL)
	_expect(panel.selected_finish() == MeshPalette.FINISH_METAL and panel._metalness.editable
		and is_equal_approx(panel._metalness.value, MeshPalette.FINISHES[MeshPalette.FINISH_METAL][0])
		and panel._finish_users.text.contains(MeshPalette.FINISH_METAL),
		"a selected finish shows its two numbers")
	_expect(_sent.is_empty(), "a selected finish sends nothing: %s" % [_sent])

	panel._roughness.value = 0.5
	panel._remove_finish.pressed.emit()
	panel._new_finish_name.text = " chrome "
	panel._add_finish.pressed.emit()
	_expect(_sent == [["finish_set", MeshPalette.FINISH_METAL,
			MeshPalette.FINISHES[MeshPalette.FINISH_METAL][0], 0.5, null],
			["finish_removed", MeshPalette.FINISH_METAL, null, null, null],
			["finish_set", "chrome", FigureColorsPanel.NEW_FINISH[0],
				FigureColorsPanel.NEW_FINISH[1], null]],
		"the finish rows send a number, a removed finish, and a new finish: %s" % [_sent])
	panel.queue_free()


## The Families tab (ENG-0011, step L5): one row for each item family of the
## server and each family of the table, the note of a family with no row,
## the part editor of a family with a row, and the signals.
func _the_families_tab_shows_and_sends_a_family() -> void:
	var panel := FigureFamiliesPanel.new()
	var Const := preload("res://autoload/blackout_constants.gd")
	var content := {"format": 1, "families": {}, "models": {}}

	FamilyLooks.put_look(content, Const.ITEM_FAMILY_WEAPON,
		FamilyLooks.row_from_parts(FamilyShapes.SHAPES[Const.ITEM_FAMILY_WEAPON]))
	FamilyLooks.put_model(content, Const.ITEM_FAMILY_FOOD, "food_meat")

	var looks := FamilyLooks.from_data(content)

	add_child(panel)
	_sent.clear()

	for pair: Array in [[panel.family_chosen, "chosen"], [panel.row_requested, "row"],
			[panel.row_removed, "no_row"], [panel.model_changed, "model"]]:
		_record(pair[0], pair[1])

	_expect(looks.error.is_empty(), "the family file of the case reads: " + looks.error)
	panel.set_families(looks, FigureEdits.new_palette())

	var names := panel.family_names()

	for family: String in Const.ITEM_FAMILIES:
		_expect(family in names, "the list has the item family %s" % family)

	for family: String in FamilyShapes.families():
		_expect(family in names, "the list has the table family %s" % family)

	_expect(panel._families.item_count == names.size() and panel.selected_family().is_empty()
		and panel._new_row.disabled and panel.edited_look().is_empty(),
		"the list has one row for each family, and none is selected")

	panel.select_family(Const.ITEM_FAMILY_WEAPON)
	_expect(panel.source_of(Const.ITEM_FAMILY_WEAPON) == FigureFamiliesPanel.SOURCE_FILE
		and panel.edited_look() == FamilyLooks.LOOK_PREFIX + Const.ITEM_FAMILY_WEAPON
		and panel.part_count() == 1 and not panel._remove_row.disabled,
		"a family with a row shows its part in the part editor")
	panel.select_family(Const.ITEM_FAMILY_ARMOR)
	_expect(panel.source_of(Const.ITEM_FAMILY_ARMOR) == FigureFamiliesPanel.SOURCE_TABLE
		and panel.edited_look().is_empty() and panel.part_count() == 0
		and panel._remove_row.disabled and not panel._new_row.disabled
		and panel._family_note.text.contains("table"),
		"a family of the table shows a note and the new shape button")
	panel.select_family(Const.ITEM_FAMILY_FOOD)
	_expect(panel.source_of(Const.ITEM_FAMILY_FOOD) == FigureFamiliesPanel.SOURCE_NONE
		and panel._model_key.text == "food_meat" and panel._family_note.text.contains("generic"),
		"a family with no row anywhere says so, and the model field shows its model")
	_expect(_sent.is_empty(), "a family that code selects sends nothing: %s" % [_sent])

	panel._families.item_selected.emit(names.find(Const.ITEM_FAMILY_ARMOR))
	panel._new_row.pressed.emit()
	panel._remove_row.pressed.emit()
	panel._model_key.text = " meat "
	panel._set_model.pressed.emit()
	_expect(_sent == [["chosen", Const.ITEM_FAMILY_ARMOR, null, null, null],
			["row", Const.ITEM_FAMILY_ARMOR, null, null, null],
			["no_row", Const.ITEM_FAMILY_ARMOR, null, null, null],
			["model", Const.ITEM_FAMILY_ARMOR, "meat", null, null]],
		"the tab sends a chosen family, a new row, a removed row, and a model: %s" % [_sent])
	panel.queue_free()


## One cell of the stance table of a Clips tab: the label, the clip list,
## or the play button of one action.
func _stance_cell(panel: FigureClipsPanel, action: String, column: int) -> Control:
	return panel._stance_grid.get_child(FigureStances.ACTIONS.find(action)
		* FigureClipsPanel.STANCE_COLUMNS + column)


func _the_clips_tab_shows_and_sends_a_stance() -> void:
	var panel := FigureClipsPanel.new()
	var library := AnimationLibrary.new()
	var table := FigureStances.from_data({"format": 1,
		"default": {"idle": "idle", "walk": "walk"},
		"stances": {"spear": {"walk": "spear_walk"}}})
	var has_stance := FigureClipsPanel.HAS_STANCE.strip_edges()

	for clip_name: String in ["idle", "walk", "spear_walk"]:
		library.add_animation(clip_name, Animation.new())

	add_child(panel)
	_sent.clear()

	for pair: Array in [[panel.stance_clip_set, "stance"], [panel.play_requested, "play"],
			[panel.clip_chosen, "clip_chosen"]]:
		_record(pair[0], pair[1])

	panel.set_clips(library)
	panel.set_stances(table, PackedStringArray(["bow", "spear"]), "spear")
	_expect(panel._stance.item_count == 3 and panel.selected_stance().is_empty()
		and panel._stance.get_item_text(0) == FigureClipsPanel.DEFAULT_STANCE
		and panel._stance.get_item_text(2).contains(has_stance)
		and not panel._stance.get_item_text(1).contains(has_stance),
		"the stance list has the default clip set, then each tool type")
	_expect(panel._stance_note.text.contains("spear"),
		"the note names the stance that the outfit takes")
	_expect(panel._stance_grid.get_child_count()
		== FigureStances.ACTIONS.size() * FigureClipsPanel.STANCE_COLUMNS,
		"the stance table has one row for each action")
	_expect(FigureFields.text_of(_stance_cell(panel, "walk", 1)) == "walk"
		and FigureFields.text_of(_stance_cell(panel, "run", 1)) == FigureClipsPanel.NO_CLIP
		and (_stance_cell(panel, "run", 2) as Button).disabled
		and not (_stance_cell(panel, "walk", 2) as Button).disabled,
		"the default clip set shows its clips, and an action with no clip cannot play")

	panel.select_stance("spear")
	_expect(panel.selected_stance() == "spear"
		and FigureFields.text_of(_stance_cell(panel, "walk", 1)) == "spear_walk"
		and FigureFields.text_of(_stance_cell(panel, "idle", 1))
			== FigureClipsPanel.OF_DEFAULT % "idle"
		and not (_stance_cell(panel, "idle", 2) as Button).disabled,
		"a stance shows its own clip, and the clip of the default clip set for each other action")
	_expect(_sent.is_empty(), "a shown stance sends nothing: %s" % [_sent])

	var idle_list := _stance_cell(panel, "idle", 1) as OptionButton

	FigureFields.select_text(idle_list, "walk")
	idle_list.item_selected.emit(idle_list.selected)
	(_stance_cell(panel, "walk", 1) as OptionButton).item_selected.emit(0)
	(_stance_cell(panel, "walk", 2) as Button).pressed.emit()
	_expect(_sent == [["stance", "spear", "idle", "walk", null],
			["stance", "spear", "walk", "", null],
			["clip_chosen", "spear_walk", null, null, null],
			["play", "spear_walk", null, null, null]],
		"a clip list sends its action and its clip, and a play button plays the clip: %s"
			% [_sent])
	_expect(panel.selected_clip() == "spear_walk", "the played clip is the selected clip")

	panel.set_stances(table, PackedStringArray(["bow"]))
	_expect(panel._stance.item_count == 3 and panel.selected_stance() == "spear",
		"a stance of the file stays in the list, and the list keeps its choice")
	panel.select_stance("no_such_type")
	_expect(panel.selected_stance().is_empty(),
		"a tool type that the list does not have selects the default clip set")

	# The attack actions of the item catalog come after the actions of the
	# client, each with a row (10/25/2026).
	var swings := PackedStringArray([FigureStances.ATTACK_PREFIX + "one_hand_slash",
		FigureStances.ATTACK_PREFIX + "unarmed_crush"])
	var first_swing := FigureStances.ACTIONS.size() * FigureClipsPanel.STANCE_COLUMNS

	panel.set_stances(table, PackedStringArray(["bow"]), "", swings)
	_expect(panel._stance_grid.get_child_count()
		== (FigureStances.ACTIONS.size() + swings.size()) * FigureClipsPanel.STANCE_COLUMNS,
		"the stance table has one row for each attack action of the catalog")
	_expect((panel._stance_grid.get_child(first_swing) as Label).text == swings[0],
		"the attack actions follow the actions of the client")
	panel.queue_free()


func _the_top_strip_and_the_play_bar_send() -> void:
	var dock := FigureDock.new()
	var bar := dock.play_bar()

	dock.persist = false
	add_child(dock)
	_sent.clear()
	_record(dock.reload_requested, "reload")
	_record(dock.save_requested, "save")
	_record(bar.play_requested, "play")
	_record(bar.seek_requested, "seek")
	_expect(dock._save.text == FigureDock.SAVE_TEXT, "the Save button says Save with no change")
	dock.set_unsaved(PackedStringArray(["looks/a.json", "rigs/b.json"]))
	_expect(dock._save.text == FigureDock.SAVE_CHANGED_TEXT % 2,
		"the Save button counts the unsaved files: " + dock._save.text)

	var question := FigureDock.revert_question(PackedStringArray(["looks/a.json", "rigs/b.json"]))

	_expect(question.contains("2 unsaved") and question.contains("rigs/b.json"),
		"the revert question counts and names the unsaved files")
	dock.set_unsaved(PackedStringArray())
	dock.ask_reload()
	dock._save.pressed.emit()
	_expect(_sent == [["reload", null, null, null, null], ["save", null, null, null, null]],
		"with no unsaved file, Revert asks nothing, and Save sends: %s" % [_sent])

	_sent.clear()
	bar.set_clip_length(WALK_LENGTH)
	bar.set_time(1.0)
	_expect(is_equal_approx(bar._time.max_value, WALK_LENGTH) and _sent.is_empty(),
		"the slider takes the length of the clip, and a shown time sends nothing")
	bar._time.value = 0.5
	bar._speed.value = 2.0
	bar._play.pressed.emit()
	_expect(_sent == [["seek", 0.5, null, null, null], ["play", 2.0, null, null, null]],
		"the play bar sends a seek with its time, and a play with its speed: %s" % [_sent])
	_expect(not dock.folds().is_empty() and dock.folds().has(FigureDock.TAB_BODY + "/"
		+ PartEditor.FOLD_MODEL), "the dock names each fold by its tab and its title")
	dock.queue_free()


func _the_session_and_the_budgets_have_their_files() -> void:
	var dock := FigureDock.new()
	var scratch := "user://figure_dock_test_%d" % Time.get_ticks_usec()
	var session := ConfigFile.new()
	var config := ConfigFile.new()
	var gear_look := FigureDock.TAB_BODY + "/" + PartEditor.FOLD_MODEL

	dock.session_path = scratch.path_join("session.cfg")
	dock.config_path = scratch.path_join("figure_editor.cfg")
	add_child(dock)
	dock.set_bodies(PackedStringArray(["body_1", "body_2"]))
	dock.select_body("body_2")
	dock.save_outfit({"head": HELM})
	dock.save_budgets({FigureChecks.BUDGET_DRAWS: 40})
	dock.save_folds({gear_look: true})
	_expect(session.load(dock.session_path) == OK and config.load(dock.config_path) == OK,
		"the dock writes the session file and the repository file")
	_expect(session.get_value("workbench", "body", "") == "body_2"
		and session.get_value("workbench", "outfit", {}) == {"head": HELM}
		and not session.has_section_key("workbench", "budgets"),
		"the body and the outfit go to the session file, and the budgets do not")
	_expect(config.get_value("workbench", "budgets", {}) == {FigureChecks.BUDGET_DRAWS: 40}
		and not config.has_section_key("workbench", "body"),
		"the budgets go to the repository file, and the session does not")
	_expect(dock.saved_budgets() == {FigureChecks.BUDGET_DRAWS: 40}
		and dock.saved_outfit() == {"head": HELM} and dock.saved_folds() == {gear_look: true},
		"the dock reads each option from its file")

	(dock.folds()[gear_look] as FoldableContainer).folded = true
	dock.apply_folds({gear_look: true})
	_expect(not (dock.folds()[gear_look] as FoldableContainer).folded
		and dock.fold_states()[gear_look], "a fold takes its state from a table")
	dock.apply_folds({gear_look: false})
	_expect(not dock.fold_states()[gear_look], "a fold closes from the table")
	_expect(dock.fold_states()[FigureDock.TAB_BODY + "/" + PartEditor.FOLD_PARTS]
		and not dock.fold_states()[FigureDock.TAB_BODY + "/" + FigureBodyPanel.FOLD_KIT],
		"the Parts fold starts open, and the Kit fold starts closed")
	dock.queue_free()
	DirAccess.remove_absolute(ProjectSettings.globalize_path(dock.session_path))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(dock.config_path))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(scratch))


func _a_rename_goes_out_on_a_focus_loss() -> void:
	var panel := FigureBodyPanel.new()
	var rig_panel := FigureRigPanel.new()
	var rig := _rig()

	add_child(panel)
	add_child(rig_panel)
	_sent.clear()
	_record(panel.part_renamed, "renamed")
	panel.set_content(rig, FigureEdits.mannequin(rig))
	panel.select_part("head")
	panel._name.text = " skull "
	panel._name.focus_exited.emit()
	panel._name.text = "head"
	panel._name.focus_exited.emit()
	_expect(_sent == [["renamed", "head", "skull", null, null]],
		"a focus loss sends the new name one time, and the same name sends nothing: %s" % [_sent])
	_expect((panel._place_position.get_child(1) as SpinBox).prefix == "y"
		and (panel._place_scale.get_child(2) as SpinBox).prefix == "z",
		"each vector field names its axis")
	_expect(panel._remove_part.disabled == false, "the part buttons are on with a part")
	panel.select_part("")
	_expect(panel._remove_part.disabled
		and panel._remove_part.tooltip_text == PartEditor.NEEDS_PART,
		"the part buttons are off with no part, with the reason")
	_expect(panel._remove_kit.disabled, "the kit button is off while the body shows")

	rig_panel.set_rig(rig)
	rig_panel.select_bone("hand_r")
	_expect((rig_panel._rotation.get_child(0) as SpinBox).editable
		and not rig_panel._remove_socket.disabled, "a socket takes a rotation, and it can go")
	rig_panel.select_bone("Hips")
	_expect(not (rig_panel._rotation.get_child(0) as SpinBox).editable
		and rig_panel._remove_socket.disabled
		and rig_panel._rotation.tooltip_text == FigureRigPanel.ONLY_SOCKET,
		"a bone of the body takes no rotation, and the reason is in the tooltip")
	panel.queue_free()
	rig_panel.queue_free()
