extends Node
## Tests for the tools that Phase W6 of DESIGN-0014 gave the author: the
## other side of a part, a copy of a part, the rest rotation of a socket,
## the regions of a rig, the kit parts, a new name for a color, and the
## outfit of an NPC def.
##
##     godot --headless --path godot res://tests/test_figure_tools.tscn
##
## Needs nothing running and no editor. It writes only below `user://`. The
## cases:
##
## 1. A socket takes a rest rotation, and a bone of the body refuses one. A
##    bone moves with the bone of the other side.
## 2. A region joins a rig, takes a bone, and leaves. A region that a look
##    names stays.
## 3. A name gives the name of its other side.
## 4. The other side of a part is its mirror picture. A part with a model
##    refuses. A fit row gets its mirror picture also.
## 5. A part and a shape each get a copy.
## 6. A part that moves to another bone keeps its place on each body type
##    with a fit.
## 7. A color role leaves a look when the palette has a color for it. The
##    roles of a look are those of its table, its shapes, and its models.
## 8. A named color takes a new name in the palette and in each look.
## 9. A kit part reads, joins its kit group, and dresses a figure. A look
##    file with a color that is no text does not read.
## 10. The item catalog gives each tool type and each NPC def with an
##     outfit. An older catalog reads.
## 11. Each new control of the dock sends its signal.
## 12. The workbench shows the kit of a character, gives several files new
##     content in one step, and runs the checks.

const TOLERANCE := 0.0001
const SETTLE_FRAMES := 2

const RIG := FigureStore.KIND_RIG
const LOOK := FigureStore.KIND_LOOK

var _failures := 0
var _scratch := ""


func _ready() -> void:
	_scratch = ProjectSettings.globalize_path("user://figure_tools_test_%d"
		% Time.get_ticks_usec())

	_a_socket_takes_a_rotation()
	_a_region_joins_and_leaves()
	_a_name_gives_its_other_side()
	_the_other_side_of_a_part_is_its_mirror_picture()
	_a_part_and_a_shape_get_a_copy()
	_a_part_on_another_bone_keeps_its_fit()
	_a_color_role_leaves_for_the_palette()
	_a_named_color_takes_a_new_name()
	_a_kit_part_reads_and_dresses_a_figure()
	_the_catalog_gives_tool_types_and_npc_defs()
	_each_new_control_sends_its_signal()
	await _the_workbench_shows_a_kit_and_runs_the_checks()
	_remove_scratch(_scratch)

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_tools")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _frames(count: int) -> void:
	for _frame in count:
		await get_tree().process_frame


func _rig() -> FigureRig:
	return FigureEdits.rig_from_profile("body_1")


## The middle of each shape of one part, in the space of the figure.
func _shape_points(rig: FigureRig, row: Dictionary) -> Array:
	var points := []
	var place := rig.global_rest_of(row["bone"]) * FigureLook.part_transform(row)

	for shape: Dictionary in row.get("shapes", []):
		points.append(place * FigureJson.vector3(shape.get("offset")))

	return points


## The row of one part of the content of a look, or an empty dictionary.
func _part(look: Dictionary, part_name: String) -> Dictionary:
	for row: Dictionary in look.get("parts", []):
		if row["name"] == part_name:
			return row

	return {}


## Press the button with one text below `node`. Returns false for no such
## button.
func _press(node: Node, text: String) -> bool:
	for child: Node in node.get_children():
		if child is Button and (child as Button).text == text:
			(child as Button).pressed.emit()
			return true

		if _press(child, text):
			return true

	return false


## Keep each argument list that a signal sends.
func _record(sent: Signal, into: Array) -> void:
	sent.connect(func(a: Variant = null, b: Variant = null, c: Variant = null) -> void:
		into.append([a, b, c]))


## The same, for a signal with four arguments. The row keeps the first
## three, so the cases read as the rows of [method _record].
func _record_four(sent: Signal, into: Array) -> void:
	sent.connect(func(a: Variant, b: Variant, c: Variant, _d: Variant) -> void:
		into.append([a, b, c]))


# ─── The rig ────────────────────────────────────────────────────────────────

func _a_socket_takes_a_rotation() -> void:
	var data := _rig().data.duplicate(true)
	var turn := Quaternion(Vector3.UP, 0.4)

	_expect(FigureEdits.set_bone_rotation(data, "hand_r", turn).is_empty(),
		"a socket takes a rest rotation")
	_expect(FigureRig.from_data(data).rest_of("hand_r").basis.get_rotation_quaternion()
		.angle_to(turn) < TOLERANCE, "the rig has the rotation of the socket")
	_expect(not FigureEdits.set_bone_rotation(data, "Head", turn).is_empty()
		and not FigureEdits.set_bone_rotation(data, "no_bone", turn).is_empty(),
		"a bone of the body and an unknown bone each refuse a rotation")

	var before := FigureRig.from_data(data)
	var moved := before.rest_of("LeftUpperArm").origin + Vector3(0.03, 0.01, 0.0)

	FigureEdits.set_bone_position(data, "LeftUpperArm", moved, true)

	var after := FigureRig.from_data(data)
	var left := after.global_rest_of("LeftUpperArm").origin
	var right := after.global_rest_of("RightUpperArm").origin

	_expect(left.distance_to(right * Vector3(-1.0, 1.0, 1.0)) < TOLERANCE
		and right.distance_to(before.global_rest_of("RightUpperArm").origin) > TOLERANCE,
		"a bone moves with the bone of the other side, as a mirror shows it")

	FigureEdits.set_bone_position(data, "LeftLowerArm", Vector3(0.0, 0.3, 0.0))
	_expect(FigureRig.from_data(data).rest_of("RightLowerArm").origin
		.is_equal_approx(after.rest_of("RightLowerArm").origin),
		"with no mirror, the bone of the other side stays")


func _a_region_joins_and_leaves() -> void:
	var data := _rig().data.duplicate(true)
	var body := FigureEdits.mannequin(_rig())
	var looks := {"body_1": body}

	_expect(FigureEdits.add_region(data, "cape").is_empty() and data["regions"].has("cape"),
		"a region joins a rig")
	_expect(not FigureEdits.add_region(data, "cape").is_empty()
		and not FigureEdits.add_region(data, "Bad Name").is_empty(),
		"a region in use and a bad name each give a reason")
	_expect(FigureEdits.set_bone_region(data, "back", "cape").is_empty()
		and FigureRig.from_data(data).region_of("back") == "cape",
		"a bone goes into a region")
	_expect(FigureEdits.set_bone_region(data, "Head", "cape").is_empty()
		and not "Head" in data["regions"]["head"],
		"a bone that goes into a region leaves its old region")
	_expect(FigureEdits.set_bone_region(data, "Head", "").is_empty()
		and FigureRig.from_data(data).region_of("Head").is_empty(), "a bone goes into no region")
	_expect(not FigureEdits.set_bone_region(data, "Head", "no_region").is_empty(),
		"an unknown region gives a reason")

	var users := FigureEdits.looks_in_region(looks, "hair")

	_expect(users == PackedStringArray(["body_1"]) and
		FigureEdits.looks_in_region(looks, "cape").is_empty(),
		"a look names a region when a part of it is in that region")
	_expect(not FigureEdits.remove_region(data, "hair", users).is_empty()
		and data["regions"].has("hair"), "a region that a look names stays")
	_expect(FigureEdits.remove_region(data, "cape").is_empty() and not data["regions"].has("cape"),
		"a region that no look names leaves")
	_expect(FigureEdits.looks_on_bone(looks, "Head") == PackedStringArray(["body_1"])
		and FigureEdits.looks_on_bone(looks, "back").is_empty(),
		"a look is on a bone when a part of it is")


# ─── The other side, and a copy ─────────────────────────────────────────────

func _a_name_gives_its_other_side() -> void:
	for pair: Array in [["LeftUpperArm", "RightUpperArm"], ["hand_r", "hand_l"],
			["sleeve_l", "sleeve_r"], ["Hips", "Hips"], ["collar", "collar"]]:
		_expect(FigureEdits.mirror_name(pair[0]) == pair[1]
			and FigureEdits.mirror_name(pair[1]) == pair[0],
			"the other side of %s is %s" % [pair[0], pair[1]])


func _the_other_side_of_a_part_is_its_mirror_picture() -> void:
	var rig := _rig()
	var look: Dictionary = FigureEdits.mannequin(rig).data.duplicate(true)
	var source := _part(look, "sleeve_l")

	_expect(not source.is_empty() and not _part(look, "sleeve_r").is_empty(),
		"the mannequin has a sleeve on each side")
	source["shapes"][0]["lean_x"] = 0.02
	source["shapes"][0]["offset"] = [0.01, 0.02, 0.03]
	source["shapes"][0]["rotation"] = [0.1, 0.2, 0.3]
	FigureEdits.set_part_fit(look, "body_2", "sleeve_l", true)
	FigureEdits.remove_part(look, "sleeve_r")

	var count: int = look["parts"].size()
	var made := FigureEdits.mirror_part(look, "sleeve_l", rig)
	var copy := _part(look, made)

	_expect(made == "sleeve_r" and look["parts"].size() == count + 1,
		"the other side of a part has the name of the other side")
	_expect(copy.get("bone", "") == FigureEdits.mirror_name(source["bone"]),
		"the other side is on the bone of the other side")
	_expect(FigureLook.from_data(look).error.is_empty(), "the look with the other side reads")

	var points := _shape_points(rig, source)
	var mirrored := _shape_points(rig, copy)

	for index in points.size():
		_expect(mirrored[index].distance_to(points[index] * Vector3(-1.0, 1.0, 1.0)) < TOLERANCE,
			"shape %d of the other side is at the mirror place" % index)

	_expect(is_equal_approx(copy["shapes"][0]["lean_x"], -0.02),
		"the lean of a prism goes to the other side")
	_expect(not FigureLook.from_data(look).fit_row("body_2", "sleeve_r").is_empty(),
		"a fit row of the part gives the other side a fit row")

	FigureEdits.mirror_part(look, "sleeve_l", rig)
	_expect(look["parts"].size() == count + 1, "a second run takes the place of the first copy")

	var hips := FigureEdits.add_part(look, rig, "Hips")
	var middle := FigureEdits.mirror_part(look, hips, rig)

	_expect(middle == hips + FigureEdits.MIRROR_SUFFIX and _part(look, middle)["bone"] == "Hips",
		"a part with no side gets a new name, on the same bone")
	_part(look, hips)["model"] = "any_model"
	_expect(FigureEdits.mirror_part(look, hips, rig).is_empty()
		and not FigureEdits.mirror_problem(look, hips, rig).is_empty()
		and not FigureEdits.mirror_problem(look, "no_part", rig).is_empty(),
		"a part with a model and an unknown part each give a reason")


func _a_part_and_a_shape_get_a_copy() -> void:
	var look: Dictionary = FigureEdits.mannequin(_rig()).data.duplicate(true)
	var count: int = look["parts"].size()
	var made := FigureEdits.duplicate_part(look, "head")
	var shapes: int = _part(look, "head")["shapes"].size()

	_expect(made == "head" + FigureEdits.COPY_SUFFIX and look["parts"].size() == count + 1,
		"a copy of a part has a new name")
	_expect(_part(look, made)["shapes"] == _part(look, "head")["shapes"]
		and _part(look, made)["position"] == _part(look, "head")["position"],
		"the copy has the shapes and the place of its part")
	_expect(FigureEdits.duplicate_part(look, "no_part").is_empty(), "an unknown part gets no copy")
	_expect(FigureEdits.duplicate_shape(look, "head", 0) == 1
		and _part(look, "head")["shapes"].size() == shapes + 1
		and _part(look, "head")["shapes"][1] == _part(look, "head")["shapes"][0],
		"a copy of a shape comes after its shape")
	_expect(FigureEdits.duplicate_shape(look, "head", 99) == -1, "an unknown shape gets no copy")
	_expect(FigureLook.from_data(look).error.is_empty(), "the look with the copies reads")


func _a_part_on_another_bone_keeps_its_fit() -> void:
	var first := _rig()
	var second := FigureEdits.rig_from_profile("body_2", 0.9)
	var rigs := {"body_1": first, "body_2": second}
	var look := {"format": 1, "key": "test"}
	var part_name := FigureEdits.add_part(look, first, "LeftLowerArm")

	FigureEdits.set_part_fit(look, "body_2", part_name, true)
	FigureEdits.set_part_place(look, part_name,
		Transform3D(Basis.IDENTITY, Vector3(0.0, 0.05, 0.0)), "body_2")

	var read := FigureLook.from_data(look)
	var before := second.global_rest_of("LeftLowerArm") * read.place_of(part_name, "body_2")
	var kept := look.duplicate(true)

	_expect(FigureEdits.set_part_bone(look, part_name, "LeftHand", first, rigs).is_empty(),
		"a part with a fit goes to another bone")

	var after := second.global_rest_of("LeftHand") \
		* FigureLook.from_data(look).place_of(part_name, "body_2")

	_expect(after.origin.distance_to(before.origin) < TOLERANCE,
		"the part stays where it is on the body type of its fit row")
	FigureEdits.set_part_bone(kept, part_name, "LeftHand", first)
	_expect(not kept.has("fit"), "with no rig for its body type, a fit row leaves the look")


# ─── The colors ─────────────────────────────────────────────────────────────

func _a_color_role_leaves_for_the_palette() -> void:
	var palette := FigureEdits.new_palette()
	var look := {"format": 1, "key": "test", "colors": {"metal": "iron", "ore": "iron"},
		"parts": [{"name": "a", "bone": "Head", "shapes": [
			{"shape": "box", "color": "metal"}, {"shape": "box", "color": "ore"},
			{"shape": "box", "color": "iron"}]}]}

	_expect(not FigureEdits.remove_color(look, "metal").is_empty(),
		"with no palette, a role that a shape names stays")
	_expect(FigureEdits.remove_color(look, "metal", palette).is_empty()
		and not look["colors"].has("metal"),
		"a role that the palette has a color for leaves the look")
	_expect(not FigureEdits.remove_color(look, "ore", palette).is_empty(),
		"a role that the palette has no color for stays")

	var roles := FigureEdits.roles_of_look(FigureLook.from_data(look), null, palette)

	_expect("metal" in roles and "ore" in roles and not "iron" in roles,
		"the roles of a look are those of its table and of its shapes, and no named color: %s"
		% [roles])


func _a_named_color_takes_a_new_name() -> void:
	var palette: Dictionary = FigureEdits.new_palette().data.duplicate(true)
	var roles := PackedStringArray(palette["roles"].keys())
	var old: String = palette["roles"]["metal"]
	var look := {"format": 1, "key": "test", "colors": {"trim": old},
		"parts": [{"name": "a", "bone": "Head", "shapes": [
			{"shape": "box", "color": old}, {"shape": "box", "color": "metal"}]}]}

	_expect(not FigureEdits.rename_named_color(palette, old, "Bad Name").is_empty()
		and not FigureEdits.rename_named_color(palette, "no_color", "new_iron").is_empty()
		and not FigureEdits.rename_named_color(palette, old, "metal").is_empty(),
		"a bad name, an unknown color, and the name of a color role each give a reason")
	_expect(FigureEdits.rename_named_color(palette, old, "new_iron").is_empty()
		and palette["colors"].has("new_iron") and not palette["colors"].has(old)
		and palette["roles"]["metal"] == "new_iron",
		"a named color takes a new name, and each color role follows")
	_expect(FigurePalette.from_data(palette).error.is_empty(), "the palette reads after that")
	_expect(FigureEdits.rename_color_in_look(look, old, "new_iron", roles)
		and look["colors"]["trim"] == "new_iron"
		and look["parts"][0]["shapes"][0]["color"] == "new_iron"
		and look["parts"][0]["shapes"][1]["color"] == "metal",
		"a look follows in its color table and in each shape that names the color")
	_expect(not FigureEdits.rename_color_in_look(look, old, "new_iron", roles),
		"a look that does not name the color does not change")


# ─── The kit parts ──────────────────────────────────────────────────────────

func _a_kit_part_reads_and_dresses_a_figure() -> void:
	var rig := _rig()
	var body := FigureEdits.mannequin(rig)
	var taken := PackedStringArray(["body_1", "head"])

	_expect(FigureEdits.kit_problem("hair_short", "hair", rig, "head_top", taken).is_empty(),
		"a new key in a kit group is a kit part")
	_expect(not FigureEdits.kit_problem("head", "hair", rig, "head_top", taken).is_empty()
		and not FigureEdits.kit_problem("Bad", "hair", rig, "head_top", taken).is_empty()
		and not FigureEdits.kit_problem("hair_short", "", rig, "head_top", taken).is_empty()
		and not FigureEdits.kit_problem("hair_short", "hair", rig, "no_bone", taken).is_empty(),
		"a key in use, a bad name, no group, and no bone each give a reason")

	var data := FigureEdits.new_kit_part("hair_short", "hair", rig, "head_top")

	FigureEdits.set_hide(data, "hair", true)

	var hair := FigureLook.from_data(data)
	var looks := {"body_1": body, "hair_short": hair}

	_expect(hair.error.is_empty() and hair.kit() == "hair" and hair.parts().size() == 1,
		"a kit part reads, with its kit group and one part: " + hair.error)
	_expect(FigureLook.from_text(hair.to_text()).to_text() == hair.to_text(),
		"a kit part gives the same bytes after one read and one write")
	_expect(FigureOutfit.kit_groups(looks) == {"hair": PackedStringArray(["hair_short"])},
		"the kit groups are the groups that a look names")

	var worn := FigureOutfit.looks_for(rig, {}, looks, {}, {"hair": "hair_short"})

	_expect(worn.size() == 2 and worn[0].key() == "body_1" and worn[1].key() == "hair_short",
		"the kit part of a character comes after the body")
	_expect(FigureOutfit.looks_for(rig, {}, looks, {}, {"beard": "hair_short"}).size() == 1
		and FigureOutfit.looks_for(rig, {}, looks, {}, {"hair": "no_look"}).size() == 1
		and FigureOutfit.looks_for(rig, {}, looks).size() == 1,
		"a kit part of another group, an unknown key, and no kit each draw the body only")

	var figure := FigureBuilder.build(rig, worn)
	var body_hair := 0

	for row: Dictionary in body.parts():
		if row["region"] == "hair":
			body_hair += 1
			_expect(FigureBuilder.part_node(figure, "body_1", row["name"]) == null,
				"a kit part that hides the hair takes the place of the hair of the body")

	_expect(body_hair > 0 and FigureBuilder.part_node(figure, "hair_short",
		hair.parts()[0]["name"]) != null, "the figure draws the kit part")
	figure.free()

	_expect(FigureEdits.set_kit(data, "").is_empty() and not data.has("kit")
		and not FigureEdits.set_kit(data, "Bad Group").is_empty(),
		"a look leaves its kit group, and a bad group name gives a reason")

	for bad: Dictionary in [{"format": 1, "key": "a", "kit": "Bad Group"},
			{"format": 1, "key": "a", "kit": 3},
			{"format": 1, "key": "a", "colors": {"metal": 3}},
			{"format": 1, "key": "a", "parts": [{"name": "p", "bone": "Head",
				"shapes": [{"shape": "box", "color": 3}]}]}]:
		_expect(not FigureLook.from_data(bad).error.is_empty(),
			"a look file with a bad name does not read: %s" % [bad])


# ─── The item catalog ───────────────────────────────────────────────────────

func _catalog_data() -> Dictionary:
	return {"format": 1,
		"slots": [{"key": "main_hand", "label": "Main Hand", "clears": []},
			{"key": "head", "label": "Head", "clears": []}],
		"items": [{"key": "stick", "name": "Stick", "slot": "main_hand", "tool_type": "club",
			"tier": 0, "family": "weapon"}],
		"tool_types": ["spear", "sword"],
		"npcs": [{"key": "guard", "name": "A guard",
			"outfit": {"main_hand": "stick", "head": "gone_helm"}}]}


func _the_catalog_gives_tool_types_and_npc_defs() -> void:
	var catalog := FigureCatalog.from_data(_catalog_data())
	var older := _catalog_data()

	_expect(catalog.error.is_empty(), "a catalog with the tables of Phase W6 reads")
	_expect(catalog.tool_types() == PackedStringArray(["club", "spear", "sword"]),
		"the tool types are those of the server and those of the items")
	_expect(catalog.npc_keys() == PackedStringArray(["guard"])
		and catalog.npc_name("guard") == "A guard" and catalog.npc_name("none") == "none",
		"the catalog names each NPC def with an outfit")
	_expect(catalog.npc_outfit("guard").size() == 2 and catalog.npc_outfit("none").is_empty()
		and catalog.valid_outfit(catalog.npc_outfit("guard")) == {"main_hand": "stick"},
		"the outfit of an NPC def is slot -> item, and an unknown item does not dress")

	older.erase("tool_types")
	older.erase("npcs")

	var old := FigureCatalog.from_data(older)

	_expect(old.error.is_empty() and old.npc_keys().is_empty()
		and old.tool_types() == PackedStringArray(["club"]),
		"a catalog of before Phase W6 reads, with the tool types of its items")

	for bad: Array in [["npcs", "text"], ["npcs", [{"key": "a"}]], ["tool_types", [1]]]:
		var broken := _catalog_data()

		broken[bad[0]] = bad[1]
		_expect(not FigureCatalog.from_data(broken).error.is_empty(),
			"a catalog with a bad %s does not read" % bad[0])


# ─── The controls ───────────────────────────────────────────────────────────

func _each_new_control_sends_its_signal() -> void:
	_the_rig_tab_sends()
	_the_part_editor_sends()
	_the_body_tab_sends()
	_the_outfit_bar_sends()
	_the_colors_and_clips_tabs_send()


func _the_rig_tab_sends() -> void:
	var panel := FigureRigPanel.new()
	var moved := []
	var turned := []
	var regions := []

	add_child(panel)
	panel.set_rig(_rig())
	panel.select_bone("hand_r")
	_record_four(panel.bone_moved, moved)
	_record(panel.bone_turned, turned)
	_record(panel.bone_region_changed, regions)
	_record(panel.region_requested, regions)
	_record(panel.region_removed, regions)
	panel._mirror.button_pressed = true
	(panel._position.get_child(0) as SpinBox).value = 0.2
	_expect(moved.size() == 1 and moved[0][0] == "hand_r" and moved[0][2] == true,
		"a moved bone sends its mirror choice")
	(panel._rotation.get_child(1) as SpinBox).value = 30.0
	_expect(turned.size() == 1 and turned[0][0] == "hand_r" and turned[0][1] is Quaternion,
		"a rotation field sends the rest rotation of the socket")
	panel.select_bone("Head")
	_expect(FigureFields.text_of(panel._region) == "head",
		"the region list shows the region of the selected bone")
	panel._region.select(0)
	panel._region.item_selected.emit(0)
	panel._region_name.text = "cape"
	_press(panel, "Add region")
	FigureFields.select_text(panel._region, "head")
	_press(panel, "Remove region")
	_expect(regions == [["Head", "", null], ["cape", null, null], ["head", null, null]],
		"the region controls send the bone, the new region, and the region to remove: %s"
		% [regions])
	panel.queue_free()


func _the_part_editor_sends() -> void:
	var panel := PartEditor.new()
	var sent := []

	add_child(panel)
	panel.set_content(_rig(), FigureEdits.mannequin(_rig()), null, FigureEdits.new_palette())
	panel.select_part("head")
	_record(panel.part_copied, sent)
	_record(panel.part_mirrored, sent)
	_record(panel.shape_copied, sent)
	_press(panel, "Copy part")
	_press(panel, "Mirror part")
	_press(panel, "Copy shape")
	_expect(sent == [["head", null, null], ["head", null, null], ["head", 0, null]],
		"the part editor sends a copy, the other side, and a copy of a shape: %s" % [sent])
	_expect((panel._field_controls["color"] as OptionButton).get_item_icon(0) != null,
		"each row of the color list of a shape has a color mark")
	_expect(not panel.new_part_bone().is_empty(), "the part editor gives the bone of a new part")
	panel.queue_free()


func _the_body_tab_sends() -> void:
	var panel := FigureBodyPanel.new()
	var rig := _rig()
	var hair := FigureLook.from_data(FigureEdits.new_kit_part("hair_short", "hair", rig,
		"head_top"))
	var looks := {"body_1": FigureEdits.mannequin(rig), "hair_short": hair}
	var sent := []
	var edited := []

	add_child(panel)
	panel.set_kit_content("body_1", looks, {"hair": "hair_short"})
	panel.set_content(rig, looks["body_1"])
	_expect(panel.edited_look() == "body_1" and not panel._fit.visible,
		"the Body tab starts on the body, with no fit control")
	_expect(panel._edited.item_count == 2 and panel._kit_grid.get_child_count() == 2
		and FigureFields.text_of(panel._kit_grid.get_child(1)) == "hair_short",
		"the Body tab lists each kit part, and it shows the kit of the figure")
	_record(panel.kit_part_chosen, sent)
	_record(panel.kit_requested, sent)
	_record(panel.kit_removed, sent)
	panel.edited_changed.connect(func() -> void: edited.append(panel.edited_look()))
	panel._edited.select(1)
	panel._edited.item_selected.emit(1)
	_expect(edited == ["hair_short"] and panel._fit.visible,
		"a picked kit part goes to the part editor, with the fit controls")
	(panel._kit_grid.get_child(1) as OptionButton).item_selected.emit(0)
	panel._kit_key.text = "beard_long"
	panel._kit_group.text = "beard"
	_press(panel, "New kit part")
	_press(panel, "Remove kit part")
	_expect(sent.size() == 3 and sent[0] == ["hair", "", null]
		and sent[1][0] == "beard_long" and sent[1][1] == "beard" and not sent[1][2].is_empty()
		and sent[2] == ["hair_short", null, null],
		"the kit controls send the choice, the new kit part, and the removal: %s" % [sent])
	panel.set_kit_content("body_1", {"body_1": looks["body_1"]}, {})
	_expect(panel.edited_look() == "body_1", "a kit part that is gone gives the body back")
	panel.queue_free()


func _the_outfit_bar_sends() -> void:
	var bar := FigureOutfitBar.new()
	var catalog := FigureCatalog.from_data(_catalog_data())
	var sent := []

	add_child(bar)
	bar.set_catalog(catalog)
	_record(bar.npc_chosen, sent)
	_expect(bar._npcs.item_count == 2 and not bar._npcs.disabled and bar.shown_npc().is_empty(),
		"the outfit bar lists each NPC def with an outfit")
	bar._npcs.item_selected.emit(1)
	_expect(sent == [["guard", null, null]], "a picked NPC def sends its key")
	bar.set_outfit(catalog.valid_outfit(catalog.npc_outfit("guard")))
	_expect(bar.shown_npc() == "guard", "the list names the NPC def whose outfit the bar shows")
	bar.set_outfit({})
	_expect(bar.shown_npc().is_empty(), "another outfit names no NPC def")

	var empty := _catalog_data()

	empty["npcs"] = []
	bar.set_catalog(FigureCatalog.from_data(empty))
	_expect(bar._npcs.disabled and bar._npcs.item_count == 1,
		"with no NPC outfit, the list says so")
	bar.queue_free()


func _the_colors_and_clips_tabs_send() -> void:
	var colors := FigureColorsPanel.new()
	var clips := FigureClipsPanel.new()
	var palette := FigureEdits.new_palette()
	var sent := []

	add_child(colors)
	add_child(clips)
	colors.set_content(palette, true, {}, ["skin"], {})
	colors.select_color(palette.color_names()[0])
	_record(colors.color_renamed, sent)
	colors._rename_text.text = "new_name"
	_press(colors, "Rename color")
	_expect(sent == [[palette.color_names()[0], "new_name", null]],
		"the Colors tab sends the new name of the selected color")
	_expect((colors._roles.get_child(1) as OptionButton).get_item_icon(1) != null,
		"each color of a role list has a color mark")
	sent.clear()
	_record(clips.stance_clip_set, sent)
	clips._new_action.text = "block"
	_press(clips, "Add action")
	_expect(sent == [["", "block", ""]], "the Clips tab sends a new action: %s" % [sent])
	colors.queue_free()
	clips.queue_free()


# ─── The workbench ──────────────────────────────────────────────────────────

func _the_workbench_shows_a_kit_and_runs_the_checks() -> void:
	var directory := _scratch.path_join("bench")
	var store := FigureStore.new(directory)
	var bench := FigureWorkbench.new()
	var rig := _rig()
	var seen := []

	store.put(RIG, "body_1", rig.data)
	store.put(LOOK, "body_1", FigureEdits.mannequin(rig).data)
	store.put(LOOK, "hair_short", FigureEdits.new_kit_part("hair_short", "hair", rig,
		"head_top"))
	store.save()
	bench.figure_directory = directory
	bench.clip_directory = _scratch.path_join("clips")
	bench.models_directory = _scratch.path_join("models")
	add_child(bench)
	await _frames(SETTLE_FRAMES)
	bench.kit_changed.connect(func() -> void: seen.append(bench.kit()))

	var bare: int = bench.counts_of("body_1")["parts"]
	var body_hair := 0

	for row: Dictionary in bench.store.looks["body_1"].parts():
		if row["region"] == "hair":
			body_hair += 1

	# A new kit part on the head top hides the hair of the body.
	bench.set_kit_part("hair", "hair_short")
	_expect(bench.store.looks["hair_short"].hides() == ["hair"],
		"a new kit part hides the region of its bone")
	_expect(seen == [{"hair": "hair_short"}]
		and bench.counts_of("body_1")["parts"] == bare + 1 - body_hair,
		"the kit part of the character shows on the stand, in the place of the hair")
	_expect(bench.part_node("body_1", "hair_short",
		bench.store.looks["hair_short"].parts()[0]["name"]) != null,
		"the stand has a node for the part of the kit part")
	bench.set_kit_part("hair", "hair_short")
	_expect(seen.size() == 1, "the same kit sends no second signal")
	bench.set_kit({"hair": "no_look", "": "x", "beard": ""})
	_expect(bench.kit() == {"hair": "no_look"} and bench.counts_of("body_1")["parts"] == bare,
		"a kit part that is not there draws nothing, and an empty entry stays out")
	bench.set_kit_part("hair", "")
	_expect(bench.kit().is_empty(), "an empty key takes the kit part of a group away")

	var body := bench.store.data_of(LOOK, "body_1")
	var hair := bench.store.data_of(LOOK, "hair_short")
	var changes := []

	bench.changed.connect(func(kind: String, key: String) -> void: changes.append(key))
	body["hides"] = ["feet"]
	hair["hides"] = ["feet"]
	_expect(bench.put_many([[LOOK, "body_1", body], [LOOK, "hair_short", hair]]).is_empty()
		and changes == ["body_1", "hair_short"]
		and bench.store.looks["body_1"].hides() == ["feet"]
		and bench.store.looks["hair_short"].hides() == ["feet"],
		"several files get new content in one step, with one signal for each")
	_expect(not bench.put_many([[LOOK, "body_1", {"format": 1, "key": "other"}]]).is_empty(),
		"a content that does not read gives a reason")

	var found := bench.run_checks()
	var rules := {}

	for finding: Dictionary in found:
		rules[finding["rule"]] = true

	_expect(not rules.has(FigureChecks.RULE_LOOK_KEY),
		"the checks of the workbench let a kit part through: %s" % [rules.keys()])
	bench.queue_free()


func _remove_scratch(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return

	for child: String in DirAccess.get_directories_at(path):
		_remove_scratch(path.path_join(child))

	for file_name: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(file_name))

	DirAccess.remove_absolute(path)
