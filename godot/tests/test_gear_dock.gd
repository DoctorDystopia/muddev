extends Node
## Tests for the panel of the gear editor (DESIGN-0014 section 22):
## [GearDock], [GearItemsPanel], and [GearLookPanel]. The part editor has
## its own test, `test_part_editor.tscn`.
##
##     godot --headless --path godot res://tests/test_gear_dock.tscn
##
## Needs nothing running and no editor. The dock does not persist here,
## so the test writes no file, except in the session case, which writes
## below `user://`. The cases:
##
## 1. The dock has the three zones, the clip list, and the outfit bar, and
##    it names each fold.
## 2. The item list has one row for each slot shape and for each item. A
##    row says what the figure shows, and the three filters keep their
##    rows. A picked row sends its key and its slot.
## 3. The look panel shows the look of a row, and it sends the look
##    buttons and the color table.
## 4. The look panel has one box for each region, and a box sends its
##    region (Phase W4). The model form sends its row, its model key, its
##    file, and its author.
## 5. The look panel shows a tier: the colors of its base, a mark on each
##    color of its own, and no part. A region that the base hides has a
##    box that the author cannot change. The tier button sends the row and
##    the base.
## 6. The copy list names a tier. A button that needs a row is off, with
##    the reason in its tooltip.
## 7. The presentation fields are off for a row with no served model, show
##    the row of the file for one with a model, and send a changed field.
## 8. The session file of the dock keeps the row, the body type, and the
##    folds, and it is not the session file of the Figure dock.
## 9. A row whose served model wins says so, in the list and in the note
##    (10/17/2026). Its import is off until the model field names another
##    key. "Fit served model to look" is on for a moved model only.

## The items of the test catalog.
const SWORD := "iron_sword"
const STICK := "wood_sword"
const HELM := "iron_helm"

var _failures := 0
var _sent := []


func _ready() -> void:
	_the_dock_has_three_zones()
	_the_item_list_shows_each_row()
	_the_look_panel_shows_and_sends_a_look()
	_the_look_panel_has_the_hide_list_and_a_model()
	_the_look_panel_shows_a_tier()
	_the_copy_list_names_a_tier_and_a_button_needs_a_row()
	_the_look_panel_shows_and_sends_a_presentation()
	_the_session_has_its_own_file()
	_a_served_model_row_says_so()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: gear_dock")
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


func _gear_looks(rig: FigureRig) -> Dictionary:
	var slot_shape := FigureEdits.slot_shape(rig, "main_hand")

	return {"main_hand": slot_shape,
		SWORD: FigureLook.from_data(FigureEdits.look_from(SWORD, slot_shape))}


func _row_of(panel: GearItemsPanel, key: String) -> int:
	for index in panel._rows.item_count:
		if panel._rows.get_item_metadata(index) == key:
			return index

	return -1


func _row_text(panel: GearItemsPanel, key: String) -> String:
	var index := _row_of(panel, key)

	return "" if index < 0 else panel._rows.get_item_text(index)


## The text of each role label of the color table of a look panel.
func _color_labels(panel: GearLookPanel) -> Array:
	var labels := []

	for index in range(0, panel._colors.get_child_count(), 2):
		labels.append((panel._colors.get_child(index) as Label).text)

	return labels


## The box of one region in the hide list of a look panel, or null.
func _hide_box(panel: GearLookPanel, region: String) -> CheckBox:
	for child: Node in panel._hides.get_children():
		if (child as CheckBox).text == region:
			return child

	return null


func _the_dock_has_three_zones() -> void:
	var dock := GearDock.new()

	dock.persist = false
	add_child(dock)
	_expect(dock.items_panel() != null and dock.part_editor() != null
		and dock.look_panel() != null and dock.outfit_bar() != null and dock.play_bar() != null,
		"the dock has the items, the part editor, the look, the outfit bar, and the play bar")
	_expect(dock.shown_tab().is_empty(), "the dock has no tab")
	dock.set_clip_names(PackedStringArray(["idle", "walk"]))
	_expect(dock.chosen_clip().is_empty() and dock._clip_list.item_count == 3,
		"the clip list starts on the rest pose, with each clip after it")
	FigureFields.select_text(dock._clip_list, "walk")
	_expect(dock.chosen_clip() == "walk", "the clip list gives its clip")
	dock.set_bodies(PackedStringArray(["body_1", "body_2"]))
	_expect(dock.active_body() == "body_1", "the first body type is the choice")
	dock.set_cost({"parts": 18, "draws": 30, "triangles": 1200})
	_expect(dock._cost.text.contains("30"), "the budget line gives the counts")
	_expect(dock.folds().has(PartEditor.FOLD_PARTS) and dock.folds().has(GearLookPanel.FOLD_LOOK)
		and dock.folds().has(GearLookPanel.FOLD_MODEL) and dock.folds().has(PartEditor.FOLD_MODEL),
		"the dock names each fold of the part editor and of the look panel")
	_expect(dock._save.text == FigureDockBase.SAVE_TEXT, "the Save button says Save with no change")
	dock.set_unsaved(PackedStringArray(["looks/a.json"]))
	_expect(dock._save.text == FigureDockBase.SAVE_CHANGED_TEXT % 1,
		"the Save button counts the unsaved files")
	dock.queue_free()


func _the_item_list_shows_each_row() -> void:
	var panel := GearItemsPanel.new()
	var rig := _rig()
	var catalog := _catalog()

	add_child(panel)
	_sent.clear()
	_record(panel.row_chosen, "row_chosen")
	panel.set_content(catalog, rig, _gear_looks(rig))
	_expect(panel._rows.item_count == catalog.slot_keys().size() + catalog.items().size(),
		"the list has one row for each slot shape and for each item")
	_expect(_row_text(panel, SWORD).contains("worn look")
		and _row_text(panel, STICK).contains("slot shape")
		and _row_text(panel, HELM).contains("family shape"),
		"an item row says what the figure shows for it")
	_expect(_row_text(panel, "main_hand").contains("Main Hand")
		and _row_text(panel, "head").contains("family shape"),
		"a slot shape row has the label of its slot, and it says when no slot shape exists")
	_expect(panel.selected_key().is_empty() and panel.item_line().is_empty(),
		"no row is selected at first")

	FigureFields.select_text(panel._slot_filter, "head")
	panel._slot_filter.item_selected.emit(panel._slot_filter.selected)
	_expect(panel._rows.item_count == 2 and _row_of(panel, HELM) == 1,
		"the slot filter keeps the slot shape and the items of one slot")
	panel._slot_filter.select(0)
	panel._slot_filter.item_selected.emit(0)
	panel._missing_only.button_pressed = true
	_expect(_row_of(panel, SWORD) < 0 and _row_of(panel, "main_hand") < 0
		and _row_of(panel, STICK) >= 0 and _row_of(panel, "head") >= 0,
		"the other filter keeps the rows with no worn look")

	panel.select_row(SWORD)
	_expect(panel.selected_key() == SWORD and _row_of(panel, SWORD) >= 0
		and not panel._missing_only.button_pressed,
		"a selected row that the filter hides takes the filter off")
	_expect(panel.item_line().contains("iron sword") and panel.item_line().contains("main_hand")
		and panel.item_line().contains("worn look"),
		"the item line gives the item, its slot, and what the figure shows")
	panel.select_row(HELM)
	panel._text_filter.text = "HELM"
	panel._text_filter.text_changed.emit("HELM")
	_expect(panel._rows.item_count == 1 and _row_of(panel, HELM) == 0,
		"the text filter keeps the rows with its text, with no regard to the case")
	panel.select_row(SWORD)
	_expect(panel._text_filter.text.is_empty() and _row_of(panel, SWORD) >= 0,
		"a selected row that the filter hides clears the text filter")
	_expect(_sent.is_empty(), "a filter and a selection by code send nothing: %s" % [_sent])

	panel._rows.select(_row_of(panel, STICK))
	panel._rows.item_selected.emit(_row_of(panel, STICK))
	panel._rows.select(_row_of(panel, "head"))
	panel._rows.item_selected.emit(_row_of(panel, "head"))
	_expect(_sent == [["row_chosen", STICK, "main_hand", null, null],
			["row_chosen", "head", "head", null, null]] and panel.item_line().contains("head"),
		"a picked row sends its key and its slot, and a slot shape row sends the slot: %s"
			% [_sent])
	panel.set_content(null, null, {})
	_expect(panel._rows.item_count == 0 and panel.selected_key().is_empty(),
		"no catalog shows no row")
	panel.queue_free()


func _the_look_panel_shows_and_sends_a_look() -> void:
	var panel := GearLookPanel.new()
	var rig := _rig()
	var looks := _gear_looks(rig)

	add_child(panel)
	_sent.clear()

	for pair: Array in [[panel.look_requested, "look"], [panel.look_removed, "removed"],
			[panel.copy_requested, "copy"], [panel.color_changed, "color"],
			[panel.color_removed, "no_color"]]:
		_record(pair[0], pair[1])

	panel.set_content(_catalog(), rig, looks, SWORD)
	_expect(panel.edited_look() == SWORD and not panel.is_tier()
		and panel._note.text.contains("worn look"), "a row with a worn look names it")
	_expect(panel._colors.get_child_count() == looks[SWORD].colors().size() * 2,
		"the color table has one label and one list for each color role")

	var role: String = (panel._colors.get_child(0) as Label).text
	var list := panel._colors.get_child(1) as OptionButton

	_expect(FigureFields.text_of(list) == looks[SWORD].colors()[role],
		"a color list shows the color of its color role")
	_expect(_sent.is_empty(), "a shown look sends nothing: %s" % [_sent])
	FigureFields.select_text(list, MeshPalette.GOLD)
	list.item_selected.emit(list.selected)
	list.item_selected.emit(0)
	panel._new_role.text = " glow "
	panel._add_role.pressed.emit()
	_expect(_sent == [["color", SWORD, role, MeshPalette.GOLD, null],
			["no_color", SWORD, role, null, null],
			["color", SWORD, "glow", MeshPalette.GENERIC, null]],
		"the color table sends a color, a removed role, and a new role: %s" % [_sent])

	_sent.clear()
	panel.set_content(_catalog(), rig, looks, STICK)
	_expect(panel.edited_look().is_empty() and panel._note.text.contains("slot shape"),
		"a row with no worn look has no look, and the note says what the figure shows")
	FigureFields.select_text(panel._copy_from, SWORD)
	panel._new_look.pressed.emit()
	panel._copy.pressed.emit()
	panel._remove_look.pressed.emit()
	_expect(_sent == [["look", STICK, "main_hand", null, null],
			["copy", STICK, SWORD, null, null], ["removed", STICK, null, null, null]],
		"the look buttons send the row: %s" % [_sent])

	panel.set_content(_catalog(), rig, looks, "head")
	_expect(panel._note.text.contains("slot shape") and panel._note.text.contains("family"),
		"a slot shape row with no look says that the family shape draws")
	panel.queue_free()


## The sword look of the test with a model: its parts come from a model
## that is the look itself, as a reference body. The look hides the hands.
func _model_look(rig: FigureRig, looks: Dictionary, models: FigureModels) -> FigureLook:
	var data: Dictionary = looks[SWORD].data.duplicate(true)

	models.put_buffer(SWORD, FigureReference.buffer_of(rig, [looks[SWORD]]))
	FigureEdits.parts_from_model(data, rig, SWORD, models)
	FigureEdits.set_hide(data, "hands", true)

	return FigureLook.from_data(data)


func _the_look_panel_has_the_hide_list_and_a_model() -> void:
	var panel := GearLookPanel.new()
	var rig := _rig()
	var looks := _gear_looks(rig)
	var models := FigureModels.new()

	looks[SWORD] = _model_look(rig, looks, models)

	var regions := rig.regions().keys()

	add_child(panel)
	_sent.clear()

	for pair: Array in [[panel.hide_changed, "hide"], [panel.import_requested, "import"],
			[panel.model_parts_requested, "model_parts"]]:
		_record(pair[0], pair[1])

	regions.sort()
	panel.set_content(_catalog(), rig, looks, SWORD, models)
	_expect(looks[SWORD].error.is_empty() and panel._hides.get_child_count() == regions.size(),
		"the hide list has one box for each region of the rig: " + looks[SWORD].error)

	for index in regions.size():
		var box := panel._hides.get_child(index) as CheckBox

		_expect(box.text == regions[index] and box.button_pressed == (regions[index] == "hands")
			and not box.disabled, "the box of %s shows the hide list of the look" % regions[index])

	_expect(_sent.is_empty(), "a shown look sends nothing: %s" % [_sent])
	(panel._hides.get_child(0) as CheckBox).button_pressed = true
	_expect(_sent == [["hide", SWORD, regions[0], true, null]], "a box sends its region")

	_sent.clear()
	_expect(panel.model_key() == SWORD and panel._model_key.text.is_empty(),
		"the model of a row is the key of the row when the field is empty")
	panel._model_parts.pressed.emit()
	panel._model_key.text = " other_model "
	panel._author.text = " An Author "
	panel._open_dialog.file_selected.emit("C:/art/helm.glb")
	_expect(_sent == [["model_parts", SWORD, SWORD, null, null],
			["import", SWORD, "other_model", "C:/art/helm.glb", "An Author"]],
		"the model form sends its row, its model key, its file, and its author: %s" % [_sent])
	_expect(GearLookPanel.presented_model(looks, models, SWORD) == SWORD
		and GearLookPanel.presented_model(looks, models, STICK).is_empty(),
		"a row with a model in the served tree has a presented model, and a row with none has none")

	panel.set_content(_catalog(), rig, looks, STICK, models)
	_expect((panel._hides.get_child(0) as CheckBox).disabled,
		"a row with no worn look has no hide list to change")
	panel.set_content(_catalog(), rig, looks, "", models)
	_expect(panel._import.disabled and panel._model_parts.disabled, "the model form needs a row")
	panel.set_importing(true)
	_expect(panel._import.disabled and panel._import.tooltip_text.contains("build"),
		"a build turns the import button off, with the reason")
	panel.queue_free()


func _the_look_panel_shows_a_tier() -> void:
	var panel := GearLookPanel.new()
	var rig := _rig()
	var looks := _gear_looks(rig)
	var palette := FigureEdits.new_palette()
	var sword: Dictionary = looks[SWORD].data.duplicate(true)
	var own := GearLookPanel.OWN_MARK + FigureEdits.ROLE_METAL

	FigureEdits.set_hide(sword, "hands", true)
	looks[SWORD] = FigureLook.from_data(sword)
	looks[STICK] = FigureLook.from_data({"format": 1, "key": STICK, "base": SWORD,
		"colors": {FigureEdits.ROLE_METAL: MeshPalette.COPPER}})
	looks[HELM] = FigureLook.from_data({"format": 1, "key": HELM, "base": "no_such_look"})
	add_child(panel)
	_sent.clear()

	for pair: Array in [[panel.tier_requested, "tier"], [panel.color_changed, "color"],
			[panel.color_removed, "no_color"], [panel.hide_changed, "hide"]]:
		_record(pair[0], pair[1])

	panel.set_content(_catalog(), rig, looks, SWORD, null, palette)
	_expect((panel._colors.get_child(1) as OptionButton).get_item_text(0)
		== GearLookPanel.REMOVE_ROLE and not own in _color_labels(panel),
		"a look with parts has no mark, and the first choice of a list removes the role")

	panel.set_content(_catalog(), rig, looks, STICK, null, palette)

	var labels := _color_labels(panel)
	var metal := panel._colors.get_child(labels.find(own) * 2 + 1) as OptionButton
	var other: int = 0 if labels[0] != own else 1
	var other_list := panel._colors.get_child(other * 2 + 1) as OptionButton

	_expect(panel.edited_look() == STICK and panel.is_tier() and panel._note.text.contains(SWORD),
		"a tier is a tier, and the note names the look with the parts")
	_expect(labels.size() == looks[SWORD].colors().size() and own in labels,
		"a tier shows each color role of its base, with a mark on its own color")
	_expect(FigureFields.text_of(metal) == MeshPalette.COPPER
		and metal.get_item_text(0) == GearLookPanel.OF_THE_BASE
		and metal.item_count == palette.colors().size() + 1,
		"the list of a tier shows its own color, and it offers each color of the palette")
	_expect(FigureFields.text_of(other_list) == looks[SWORD].colors()[labels[other]],
		"a color role with no color of the tier shows the color of the base")
	_expect(_hide_box(panel, "hands").button_pressed and _hide_box(panel, "hands").disabled
		and not _hide_box(panel, "hair").button_pressed
		and not _hide_box(panel, "hair").disabled,
		"a region that the base hides has a ticked box that the author cannot change")
	_expect(_sent.is_empty(), "a shown tier sends nothing: %s" % [_sent])

	metal.select(0)
	metal.item_selected.emit(0)
	FigureFields.select_text(panel._copy_from, SWORD)
	panel._tier.pressed.emit()
	_expect(_sent == [["no_color", STICK, FigureEdits.ROLE_METAL, null, null],
			["tier", STICK, SWORD, null, null]],
		"the first choice gives the color of the base, and the tier button sends the base: %s"
			% [_sent])

	panel.set_content(_catalog(), rig, looks, HELM, null, palette)
	_expect(panel.is_tier() and panel._note.text.contains("no part"),
		"a tier of a look that is not there says that it draws no part")
	panel.queue_free()


func _the_copy_list_names_a_tier_and_a_button_needs_a_row() -> void:
	var panel := GearLookPanel.new()
	var rig := _rig()
	var looks := _gear_looks(rig)

	looks[STICK] = FigureLook.from_data({"format": 1, "key": STICK, "base": SWORD})
	add_child(panel)
	panel.set_content(_catalog(), rig, looks, SWORD)
	FigureFields.select_text(panel._copy_from, GearLookPanel.TIER_ROW % [STICK, SWORD])
	_expect(panel.copy_source() == STICK, "the copy list names a tier, and it gives the key")
	_expect(not panel._copy.disabled and not panel._new_look.disabled,
		"the look buttons are on with a row")
	panel.set_content(_catalog(), rig, looks, "")
	_expect(panel._copy.disabled and panel._tier.disabled and panel._add_role.disabled
		and panel._copy.tooltip_text == GearLookPanel.NEEDS_ROW,
		"a button that needs a row is off with no row, with the reason")
	panel.set_content(_catalog(), rig, looks, STICK)
	_expect(not panel._remove_look.disabled, "the remove button is on for a row with a look")
	panel.set_content(_catalog(), rig, looks, HELM)
	_expect(panel._remove_look.disabled and panel._remove_look.tooltip_text.contains("no worn look"),
		"the remove button is off for a row with no look")
	panel.queue_free()


func _the_look_panel_shows_and_sends_a_presentation() -> void:
	var panel := GearLookPanel.new()
	var rig := _rig()
	var looks := _gear_looks(rig)
	var presentation := ModelPresentation.from_data({"format": 1, "models": {
		STICK: {"offset": [0.0, 0.25, 0.0], "turn": [0.0, 90.0, 0.0], "scale": 1.6}}})
	var models := FigureModels.new()

	add_child(panel)
	_sent.clear()
	# The signal has five arguments, one more than the record helper takes.
	panel.presentation_changed.connect(func(model_key: String, offset: Vector3, turn: Vector3,
			scale: float, _field: String) -> void:
		_sent.append(["present", model_key, offset, turn, scale]))
	_expect(presentation.error.is_empty(), "the presentation of the case reads: "
		+ presentation.error)
	panel.set_content(_catalog(), rig, looks, SWORD, models, null, presentation)
	_expect(not panel._present_scale.editable
		and panel._present_line.text == GearLookPanel.NO_SERVED_MODEL,
		"a row with no served model has the fields off")

	models.put_buffer(STICK, FigureReference.buffer_of(rig, [looks[SWORD]]))
	panel.set_content(_catalog(), rig, looks, STICK, models, null, presentation)
	_expect(panel._present_scale.editable and is_equal_approx(panel._present_scale.value, 1.6)
		and FigureFields.vector_of(panel._present_turn).is_equal_approx(Vector3(0.0, 90.0, 0.0)),
		"a row with a served model shows the row of the file")
	_expect(_sent.is_empty(), "a shown presentation sends nothing: %s" % [_sent])

	(panel._present_offset.get_child(1) as SpinBox).value = 0.5
	# The spin box rounds the scale to its step, so the number is near 1.6.
	_expect(_sent.size() == 1 and _sent[0][1] == STICK
		and _sent[0][2].is_equal_approx(Vector3(0.0, 0.5, 0.0))
		and _sent[0][3].is_equal_approx(Vector3(0.0, 90.0, 0.0)) and is_equal_approx(_sent[0][4], 1.6),
		"a changed field sends the model, the offset, the turn, and the scale: %s" % [_sent])
	panel.queue_free()


func _a_served_model_row_says_so() -> void:
	var items := GearItemsPanel.new()
	var panel := GearLookPanel.new()
	var rig := _rig()
	var looks := _gear_looks(rig)
	var models := FigureModels.new()

	models.put_buffer(STICK, FigureReference.buffer_of(rig, [looks[SWORD]]))
	add_child(items)
	add_child(panel)
	_sent.clear()
	_record(panel.served_fit_requested, "fit")
	items.set_content(_catalog(), rig, looks, models)
	items.select_row(STICK)
	_expect(_row_text(items, STICK).contains("served model")
		and items.item_line().contains("served model")
		and _row_text(items, SWORD).contains("worn look"),
		"a row whose served model wins says so, in the list and in the item line")

	panel.set_content(_catalog(), rig, looks, STICK, models)
	_expect(panel.serves_model() and panel._note.text.contains("served model"),
		"the note says that the figure draws the served model")
	_expect(panel._import.disabled and panel._model_parts.disabled
		and panel._import.tooltip_text == GearLookPanel.SERVED_WINS,
		"the import is off for a row whose served model draws, with the reason")
	_expect(panel._served_fit.disabled and panel._served_fit.tooltip_text == GearLookPanel.NOT_MOVED,
		"a served model with its first place has nothing to fit")

	panel._model_key.text = "stick_figure_model"
	panel._model_key.text_changed.emit(panel._model_key.text)
	_expect(not panel._import.disabled and not panel._model_parts.disabled,
		"another key in the model field turns the import on")

	var data := {"format": FigureLook.FORMAT, "key": STICK}

	FigureLookEdits.set_served_place(data, rig.slots()["main_hand"], Transform3D.IDENTITY)
	looks[STICK] = FigureLook.from_data(data)
	panel.set_content(_catalog(), rig, looks, STICK, models)
	_expect(not panel._served_fit.disabled, "a moved served model can fit its look again")
	panel._served_fit.pressed.emit()
	_expect(_sent == [["fit", STICK, null, null, null]], "the fit button sends the row: %s" % [_sent])

	panel.set_content(_catalog(), rig, looks, SWORD, models)
	_expect(not panel.serves_model() and panel._served_fit.disabled
		and panel._served_fit.tooltip_text == GearLookPanel.NOT_SERVED,
		"a row with no served model has no fit button")
	items.queue_free()
	panel.queue_free()


func _the_session_has_its_own_file() -> void:
	var dock := GearDock.new()
	var scratch := "user://gear_dock_test_%d" % Time.get_ticks_usec()
	var session := ConfigFile.new()
	var fold := GearLookPanel.FOLD_LOOK

	_expect(GearDock.SESSION_PATH != FigureDock.SESSION_PATH,
		"the gear editor has a session file of its own")
	dock.session_path = scratch.path_join("session.cfg")
	dock.config_path = scratch.path_join("figure_editor.cfg")
	add_child(dock)
	dock.set_bodies(PackedStringArray(["body_1", "body_2"]))
	dock.select_body("body_2")
	dock.save_row(SWORD)
	dock.save_folds({fold: true})
	_expect(session.load(dock.session_path) == OK
		and session.get_value("workbench", "body", "") == "body_2"
		and session.get_value("workbench", "row", "") == SWORD,
		"the body type and the row go to the session file")
	_expect(dock.saved_row() == SWORD and dock.saved_folds() == {fold: true},
		"the dock reads each option from its file")
	(dock.folds()[fold] as FoldableContainer).folded = true
	dock.restore_folds()
	_expect(not (dock.folds()[fold] as FoldableContainer).folded,
		"a fold takes its state from the session file")
	dock.queue_free()
	DirAccess.remove_absolute(ProjectSettings.globalize_path(dock.session_path))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(scratch))
