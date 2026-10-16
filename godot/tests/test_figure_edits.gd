extends Node
## Tests for the rules of the Rig tab, the Body tab, and the Gear tab
## (DESIGN-0014 Phases W1 and W3): [FigureEdits].
##
##     godot --headless --path godot res://tests/test_figure_edits.tscn
##
## Needs nothing running and no editor. It writes no file. The cases:
##
## 1. A socket joins a rig and leaves it. A bad name, a name in use, and a
##    socket that a slot uses each give a reason.
## 2. A bone moves, and a slot takes another bone.
## 3. The mannequin has one part for each body row, in prisms. A limb has
##    the length of its bone, and the girth scales its width. A new rig has
##    the arm places of the low-poly look.
## 4. A part joins a look with a free name and the region of its bone. It
##    leaves, and it takes a new name.
## 5. A part that moves to another bone stays where it is on the figure.
## 6. A shape joins a part and leaves it, and a field takes a value.
## 7. A field with no key gives the value that the builder uses.
## 8. A slot shape stands on the bones of its part rows. A slot shape that
##    hides a region is wider than the body part there. Each color role of
##    a slot shape has a color.
## 9. A new look starts from another look, and a look takes the parts of
##    another look.
## 10. A color role takes a color, and a free color role leaves.
## 11. A region joins the hide list and leaves it (Phase W4). A copied look
##     takes the fit with the parts.
## 12. A look becomes a tier of another look (Phase W5). It keeps only the
##     colors that differ. A base that is not there, the look itself, and
##     two looks that name each other each give a reason. A copied look is
##     no tier after that.
## 13. A new palette has each color that a new body and a new slot shape
##     name. A named color and a color role each take a value and leave. A
##     color that a look or a role names stays.
## 14. An action of a stance takes a clip, and a stance with no action
##     leaves the table. A shape gives its finish back to its color.
##
## `tests/test_figure_models.tscn` tests the other rules of Phase W4: the
## parts of a model, the bone of a node, and the fit of a body type.

const TOLERANCE := 0.0001

var _failures := 0


func _ready() -> void:
	_a_socket_joins_and_leaves()
	_a_bone_moves_and_a_slot_takes_a_bone()
	_the_mannequin_has_a_part_for_each_row()
	_a_part_joins_leaves_and_takes_a_name()
	_a_part_on_another_bone_stays_in_place()
	_a_shape_joins_leaves_and_takes_a_value()
	_a_field_with_no_key_gives_the_builder_value()
	_a_slot_shape_stands_on_the_bones_of_its_slot()
	_a_look_starts_from_another_look()
	_a_color_role_takes_a_color_and_leaves()
	_a_region_joins_the_hide_list_and_leaves()
	_a_look_becomes_a_tier()
	_a_palette_takes_a_color_and_a_role()
	_a_stance_takes_a_clip()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_edits")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _rig() -> FigureRig:
	return FigureEdits.rig_from_profile("body_1")


func _a_socket_joins_and_leaves() -> void:
	var data: Dictionary = _rig().data.duplicate(true)
	var count: int = data["bones"].size()

	_expect(not FigureEdits.add_socket(data, "Sheath L", "Hips").is_empty(),
		"a socket name with a space gives a reason")
	_expect(not FigureEdits.add_socket(data, "hand_r", "Hips").is_empty(),
		"a name in use gives a reason")
	_expect(not FigureEdits.add_socket(data, "sheath_l", "NoSuchBone").is_empty(),
		"an unknown parent gives a reason")
	_expect(data["bones"].size() == count, "a refused socket changes nothing")

	_expect(FigureEdits.add_socket(data, "sheath_l", "Hips", Vector3(0.1, 0.0, 0.0)).is_empty(),
		"a socket joins the rig")

	var rig := FigureRig.from_data(data)

	_expect(rig.error.is_empty() and rig.is_socket("sheath_l")
		and rig.bone("sheath_l")["parent"] == "Hips"
		and rig.rest_of("sheath_l").origin.is_equal_approx(Vector3(0.1, 0.0, 0.0)),
		"the new socket is a bone on its parent: " + rig.error)

	_expect(not FigureEdits.remove_socket(data, "Hips").is_empty(),
		"a body bone is not a socket to remove")
	_expect(not FigureEdits.remove_socket(data, "hand_r").is_empty(),
		"a socket that a slot uses stays")
	_expect(FigureEdits.remove_socket(data, "sheath_l").is_empty(), "a free socket leaves")
	_expect(data["bones"].size() == count and not "sheath_l" in data["sockets"],
		"the rig is as before")

	FigureEdits.add_socket(data, "strap", "Hips")
	FigureEdits.add_socket(data, "pouch", "strap")
	_expect(not FigureEdits.remove_socket(data, "strap").is_empty(),
		"a socket with a bone on it stays")
	_expect(FigureEdits.remove_socket(data, "pouch").is_empty()
		and FigureEdits.remove_socket(data, "strap").is_empty(),
		"the two leave from the end")


func _a_bone_moves_and_a_slot_takes_a_bone() -> void:
	var data: Dictionary = _rig().data.duplicate(true)
	var slot: String = data["slots"].keys()[0]

	_expect(FigureEdits.set_bone_position(data, "hand_r", Vector3(0.0, 0.2, 0.0)).is_empty()
		and FigureRig.from_data(data).rest_of("hand_r").origin.is_equal_approx(
			Vector3(0.0, 0.2, 0.0)), "a bone moves on its parent")
	_expect(not FigureEdits.set_bone_position(data, "NoSuchBone", Vector3.ZERO).is_empty(),
		"an unknown bone gives a reason")
	_expect(FigureEdits.set_slot_bone(data, slot, "Hips").is_empty()
		and data["slots"][slot] == "Hips", "a slot takes another bone")
	_expect(not FigureEdits.set_slot_bone(data, slot, "NoSuchBone").is_empty(),
		"a slot refuses an unknown bone")


func _the_mannequin_has_a_part_for_each_row() -> void:
	var rig := _rig()
	var body := FigureEdits.mannequin(rig)
	var wide := FigureEdits.mannequin(rig, 2.0)

	_expect(body.error.is_empty() and body.parts().size() == _part_count(FigureShapes.BODY),
		"the mannequin has one part for each body row and each side: " + body.error)

	for row: Dictionary in body.parts():
		_expect(rig.has_bone(row["bone"]) and rig.regions().has(row["region"]),
			"the part %s is on a bone and in a region of the rig" % row["name"])

		for shape: Dictionary in row["shapes"]:
			_expect(shape["shape"] == FamilyShapes.SHAPE_PRISM and not shape.has("finish"),
				"each shape of %s is a matte prism" % row["name"])
			_expect(body.colors().has(shape["color"]),
				"the body gives the color role %s a color" % shape["color"])

	_a_limb_follows_its_bone(rig, body, wide)
	_expect(body.part("sleeve_l")["region"] == "torso" and body.part("boot_l")["region"] == "feet"
		and body.part("hips")["region"] == "legs",
		"the clothes of a body are in the region that a worn look hides")
	_expect(body.colors().has(FigureEdits.SKIN_ROLE)
		and MeshPalette.COLORS.has(body.colors()[FigureEdits.SKIN_ROLE]),
		"the body gives the skin a color of the palette")


## The count of the parts that a table of part rows makes: two for a row
## with a side.
func _part_count(rows: Array) -> int:
	var count := 0

	for row: Dictionary in rows:
		count += 2 if str(row["bone"]).contains(FigureShapes.SIDE_BONE) else 1

	return count


func _a_limb_follows_its_bone(rig: FigureRig, body: FigureLook, wide: FigureLook) -> void:
	var arm: Dictionary = body.part("upper_arm_l")["shapes"][0]
	var other: Dictionary = body.part("upper_arm_r")["shapes"][0]
	var length := rig.rest_of("LeftLowerArm").origin.length()
	var long_rig := FigureEdits.rig_from_profile("long", 2.0)
	var long_arm: Dictionary = FigureEdits.mannequin(long_rig).part("upper_arm_l")["shapes"][0]

	_expect(arm["size"][1] > length and arm["size"][1] < length * 1.2,
		"a limb reaches from its joint to a little past the next joint: %s" % [arm["size"]])
	_expect(is_equal_approx(long_arm["size"][1] - arm["size"][1], length),
		"a limb gets longer with its bone")
	_expect(is_equal_approx(long_arm["size"][0], arm["size"][0]),
		"the length of a bone does not change the width of a limb")
	_expect(is_equal_approx(wide.part("upper_arm_l")["shapes"][0]["size"][0], arm["size"][0] * 2.0)
		and is_equal_approx(wide.part("upper_arm_l")["shapes"][0]["size"][1], arm["size"][1]),
		"the girth scales the width of a limb, and not its length")
	_expect(arm["size"] == other["size"], "the two sides have the same shapes")

	var left := rig.global_rest_of("LeftUpperArm") * FigureJson.vector3(arm["offset"])
	var right := rig.global_rest_of("RightUpperArm") * FigureJson.vector3(other["offset"])

	_expect(left.is_equal_approx(Vector3(-right.x, right.y, right.z)),
		"the right side is the mirror of the left side: %s, %s" % [left, right])
	_expect(is_equal_approx(rig.rest_of("LeftUpperArm").origin.length(),
		FigureEdits.ARM_PLACES["UpperArm"])
		and is_equal_approx(rig.rest_of("RightHand").origin.length(),
			FigureEdits.ARM_PLACES["Hand"]),
		"a new rig has the arm places of the low-poly look")


func _a_part_joins_leaves_and_takes_a_name() -> void:
	var rig := _rig()
	var data: Dictionary = FigureEdits.mannequin(rig).data.duplicate(true)
	var count: int = data["parts"].size()
	var first := FigureEdits.add_part(data, rig, "Head")
	var second := FigureEdits.add_part(data, rig, "Head")
	var look := FigureLook.from_data(data)

	_expect(look.error.is_empty() and look.parts().size() == count + 2,
		"two parts join the look: " + look.error)
	_expect(first == "head_2" and second == "head_3",
		"a new part takes a free name: %s, %s" % [first, second])
	_expect(look.part(first)["region"] == "head" and look.part(first)["shapes"].size() == 1,
		"a new part has the region of its bone and one shape")
	_expect(FigureEdits.add_part(data, rig, "hand_r") == "hand_r_2",
		"a part on a socket takes the name of the socket, with a number when it is in use")

	_expect(not FigureEdits.rename_part(data, first, "Bad Name").is_empty(),
		"a bad part name gives a reason")
	_expect(not FigureEdits.rename_part(data, first, "head").is_empty(),
		"a part name in use gives a reason")
	_expect(FigureEdits.rename_part(data, first, "hair_tuft").is_empty()
		and not FigureLook.from_data(data).part("hair_tuft").is_empty(), "a part takes a name")
	_expect(FigureEdits.set_part_region(data, "hair_tuft", "hair").is_empty()
		and FigureLook.from_data(data).part("hair_tuft")["region"] == "hair",
		"a part takes a region")
	_expect(FigureEdits.remove_part(data, "hair_tuft").is_empty()
		and FigureLook.from_data(data).part("hair_tuft").is_empty(), "a part leaves")
	_expect(not FigureEdits.remove_part(data, "hair_tuft").is_empty(),
		"an unknown part gives a reason")


func _a_part_on_another_bone_stays_in_place() -> void:
	var rig := _rig()
	var data: Dictionary = FigureEdits.mannequin(rig).data.duplicate(true)
	var place := Transform3D(Basis.from_euler(Vector3(0.2, 0.4, -0.3)), Vector3(0.02, 0.1, 0.0))

	FigureEdits.set_part_place(data, "hand_r", place)

	var before: Transform3D = rig.global_rest_of("RightHand") \
		* FigureLook.part_transform(FigureLook.from_data(data).part("hand_r"))

	_expect(FigureEdits.set_part_bone(data, "hand_r", "hand_r", rig).is_empty(),
		"a part moves to another bone")

	var row := FigureLook.from_data(data).part("hand_r")
	var after: Transform3D = rig.global_rest_of("hand_r") * FigureLook.part_transform(row)

	_expect(row["bone"] == "hand_r", "the part is on the new bone")
	_expect(after.origin.distance_to(before.origin) < TOLERANCE,
		"the part is at the same position on the figure")

	for axis in 3:
		_expect(after.basis[axis].distance_to(before.basis[axis]) < TOLERANCE,
			"axis %d of the part points the same way on the figure" % axis)

	_expect(not FigureEdits.set_part_bone(data, "hand_r", "NoSuchBone", rig).is_empty(),
		"an unknown bone gives a reason")


func _a_shape_joins_leaves_and_takes_a_value() -> void:
	var rig := _rig()
	var data: Dictionary = FigureEdits.mannequin(rig).data.duplicate(true)
	var count: int = FigureLook.from_data(data).part("head")["shapes"].size()

	for kind: String in FigureEdits.SHAPE_FIELDS:
		var index := FigureEdits.add_shape(data, "head", kind)
		var look := FigureLook.from_data(data)

		_expect(look.error.is_empty() and index == look.part("head")["shapes"].size() - 1
			and look.part("head")["shapes"][index]["shape"] == kind,
			"a %s joins the shape list: %s" % [kind, look.error])

		for field: String in FigureEdits.fields_of(look.part("head")["shapes"][index]):
			_expect(FigureEdits.FIELD_KINDS.has(field),
				"the field %s of a %s has a kind" % [field, kind])

	_expect(FigureEdits.add_shape(data, "head", "no_such_shape") == -1
		and FigureEdits.add_shape(data, "no_such_part", FamilyShapes.SHAPE_BOX) == -1,
		"an unknown shape and an unknown part add nothing")

	_expect(FigureEdits.set_shape_value(data, "head", 0, "offset", Vector3(0.0, 0.2, 0.0)).is_empty()
		and FigureEdits.set_shape_value(data, "head", 0, "segments", 12).is_empty()
		and FigureEdits.set_shape_value(data, "head", 0, "color", MeshPalette.STEEL).is_empty(),
		"a field takes a value")

	var shape: Dictionary = FigureLook.from_data(data).part("head")["shapes"][0]

	_expect(shape["offset"] == [0.0, 0.2, 0.0] and shape["segments"] == 12
		and shape["color"] == MeshPalette.STEEL, "the file has the vector as three numbers")
	_expect(typeof(shape["segments"]) == TYPE_INT, "a count stays an integer")
	_expect(not FigureEdits.set_shape_value(data, "head", 0, "no_such_field", 1.0).is_empty()
		and not FigureEdits.set_shape_value(data, "head", 99, "radius", 1.0).is_empty(),
		"an unknown field and an unknown shape each give a reason")

	_expect(FigureEdits.remove_shape(data, "head", count).is_empty()
		and not FigureEdits.remove_shape(data, "head", 99).is_empty(),
		"a shape leaves, and an unknown shape gives a reason")


func _a_field_with_no_key_gives_the_builder_value() -> void:
	var ball := {"shape": FamilyShapes.SHAPE_SPHERE, "radius": 0.3}
	var tube := {"shape": FamilyShapes.SHAPE_CYLINDER, "radius": 0.2,
		"rotation": [0.0, 0.5, 0.0]}

	_expect(FigureEdits.shape_value(ball, "radius") == 0.3, "a key gives its value")
	_expect(FigureEdits.shape_value(ball, "offset") == Vector3.ZERO
		and FigureEdits.shape_value(ball, "scale") == Vector3.ONE,
		"no offset is zero, and no scale is one")
	_expect(FigureEdits.shape_value(ball, "segments") == FigureLook.DEFAULT_SEGMENTS
		and FigureEdits.shape_value(ball, "rings")
			== FigureLook.DEFAULT_RINGS[FamilyShapes.SHAPE_SPHERE],
		"no count is the low count of a figure")
	_expect(FigureEdits.shape_value(tube, "radius_top") == 0.2,
		"a cylinder with no top radius is not tapered")
	_expect(FigureEdits.shape_value(tube, "rotation") == Vector3(0.0, 0.5, 0.0),
		"a vector key gives a vector")
	_expect(FigureEdits.shape_value(tube, "finish") == FigureEdits.FINISH_OF_COLOR
		and FigureEdits.shape_value(tube, "open") == false,
		"no finish is the finish of the color, and no open flag is closed")

	var block := {"shape": FamilyShapes.SHAPE_PRISM, "size": [0.2, 0.4, 0.1]}

	# A vector holds each number with fewer digits than a float has.
	_expect(is_equal_approx(FigureEdits.shape_value(block, "top_width"), 0.2)
		and is_equal_approx(FigureEdits.shape_value(block, "top_depth"), 0.1),
		"a prism with no top size is not tapered")
	_expect(FigureEdits.shape_value(block, "lean_x") == 0.0
		and FigureEdits.shape_value(block, "diamond") == false,
		"no lean is zero, and no diamond flag is a side on each axis")
	_expect(FigureEdits.unique_name("a", PackedStringArray(["a", "a_2"])) == "a_3",
		"a free name takes the first free number")


func _a_slot_shape_stands_on_the_bones_of_its_slot() -> void:
	var rig := _rig()

	for slot: String in FigureShapes.SLOTS:
		var look := FigureEdits.slot_shape(rig, slot)
		var rows: Array = FigureShapes.SLOTS[slot]
		var on_slot_bone := false

		_expect(look.error.is_empty() and look.key() == slot
			and look.parts().size() == _part_count(rows),
			"the slot shape of %s has one part for each part row and each side: %s"
				% [slot, look.error])
		_expect(look.hides() == FigureShapes.SLOT_HIDES.get(slot, []),
			"the slot shape of %s hides the regions of its slot" % slot)

		for row: Dictionary in look.parts():
			on_slot_bone = on_slot_bone or row["bone"] == rig.slots()[slot]
			_expect(rig.has_bone(row["bone"]) and not row["shapes"].is_empty(),
				"the part %s of %s is on a bone of the rig, with a shape" % [row["name"], slot])

		# A one-part slot shape must be on the bone that the Rig tab gives the
		# slot, so a moved socket moves the item.
		_expect(on_slot_bone or rows.size() > 1,
			"the one part of %s is on the bone of the slot" % slot)

	for slot: String in FigureShapes.SLOT_HIDES:
		for region: String in FigureShapes.SLOT_HIDES[slot]:
			_expect(rig.regions().has(region), "%s hides a region of the rig: %s" % [slot, region])

	_a_shell_is_wider_than_the_body(rig)
	_a_slot_shape_has_a_color_for_each_role(rig)

	var odd := FigureEdits.slot_shape(rig, "no_such_slot")
	var data: Dictionary = rig.data.duplicate(true)

	_expect(odd.error.is_empty() and odd.parts().is_empty(),
		"a slot with no bone gets a slot shape with no part")
	data["slots"]["tail"] = "Hips"
	odd = FigureEdits.slot_shape(FigureRig.from_data(data), "tail")
	_expect(odd.parts().size() == 1 and odd.parts()[0]["bone"] == "Hips"
		and odd.parts()[0]["shapes"][0]["shape"] == FamilyShapes.SHAPE_BOX,
		"a slot that the workbench does not know gets one box on its bone")


func _a_shell_is_wider_than_the_body(rig: FigureRig) -> void:
	var body := FigureEdits.mannequin(rig)
	var shell := FigureEdits.slot_shape(rig, "legs")
	var limb: Dictionary = body.part("upper_leg_l")["shapes"][0]
	var cover: Dictionary = shell.part("upper_leg_l")["shapes"][0]

	_expect(cover["size"][0] > limb["size"][0] and cover["size"][2] > limb["size"][2]
		and is_equal_approx(cover["size"][1], limb["size"][1]),
		"a shell has the length of its body part, and it is wider")
	_expect(cover["offset"] == limb["offset"], "a shell is where its body part is")
	_expect(not limb.has("finish") and not cover.has("finish"),
		"a body part and a shell are matte: no finish key")


func _a_slot_shape_has_a_color_for_each_role(rig: FigureRig) -> void:
	for slot: String in FigureShapes.SLOTS:
		var look := FigureEdits.slot_shape(rig, slot)
		var named := {}

		for row: Dictionary in look.parts():
			for shape: Dictionary in row["shapes"]:
				named[shape["color"]] = true

		_expect(look.colors().keys().size() == named.size(),
			"the color table of %s has one row for each color role" % slot)

		for role: String in named:
			_expect(MeshPalette.COLORS.has(look.colors().get(role, "")),
				"the color role %s of %s has a color of the palette" % [role, slot])

	for slot: String in FigureShapes.SLOT_COLORS:
		for role: String in FigureShapes.SLOT_COLORS[slot]:
			_expect(FigureEdits.slot_shape(rig, slot).colors().get(role, "")
				== FigureShapes.SLOT_COLORS[slot][role],
				"%s gives the color role %s its own color" % [slot, role])


func _a_look_starts_from_another_look() -> void:
	var rig := _rig()
	var source := FigureEdits.slot_shape(rig, "main_hand")
	var data := FigureEdits.look_from("iron_sword", source)
	var look := FigureLook.from_data(data)

	_expect(look.error.is_empty() and look.key() == "iron_sword"
		and look.parts() == source.parts() and look.colors() == source.colors(),
		"a new look has the parts and the colors of its source: " + look.error)

	FigureEdits.set_shape_value(data, FigureEdits.ITEM_PART, 0, "radius", 0.5)
	_expect(not source.parts()[0]["shapes"][0].has("radius"),
		"a change to the new look leaves its source")

	var helm: Dictionary = FigureEdits.slot_shape(rig, "head").data.duplicate(true)

	helm["hides"] = ["hair"]
	_expect(FigureEdits.copy_look(data, helm).is_empty(), "a look takes another look")
	look = FigureLook.from_data(data)
	_expect(look.key() == "iron_sword" and look.parts() == helm["parts"]
		and look.hides() == ["hair"] and look.colors() == helm["colors"],
		"the look keeps its key, and it has the parts, the colors, and the hide list")
	_expect(FigureEdits.copy_look(data, source.data).is_empty()
		and not FigureLook.from_data(data).data.has("hides"),
		"a source with no hide list leaves none")
	_expect(not FigureEdits.copy_look(data, {"format": 1, "key": "bare"}).is_empty()
		and FigureLook.from_data(data).parts() == source.parts(),
		"a source with no part gives a reason, and the look stays")


func _a_color_role_takes_a_color_and_leaves() -> void:
	var data: Dictionary = FigureEdits.slot_shape(_rig(), "main_hand").data.duplicate(true)

	_expect(FigureEdits.set_color(data, FigureEdits.ROLE_METAL, MeshPalette.GOLD).is_empty()
		and data["colors"][FigureEdits.ROLE_METAL] == MeshPalette.GOLD,
		"a color role takes a color of the palette")
	_expect(not FigureEdits.set_color(data, FigureEdits.ROLE_METAL, "no_such_color").is_empty()
		and not FigureEdits.set_color(data, "Bad Role", MeshPalette.GOLD).is_empty()
		and data["colors"][FigureEdits.ROLE_METAL] == MeshPalette.GOLD,
		"an unknown color and a bad role name each give a reason")
	_expect(FigureEdits.set_color(data, "glow", MeshPalette.GEM).is_empty()
		and data["colors"]["glow"] == MeshPalette.GEM, "a new color role joins the table")
	_expect(FigureLook.from_data(data).error.is_empty(), "the look reads after the changes")

	_expect(not FigureEdits.remove_color(data, FigureEdits.ROLE_METAL).is_empty()
		and data["colors"].has(FigureEdits.ROLE_METAL),
		"a color role that a shape names stays")
	_expect(FigureEdits.remove_color(data, "glow").is_empty() and not data["colors"].has("glow"),
		"a free color role leaves")
	_expect(not FigureEdits.remove_color(data, "glow").is_empty(),
		"an unknown color role gives a reason")

	var bare := {"format": 1, "key": "bare"}

	_expect(FigureEdits.set_color(bare, "trim", MeshPalette.RUST).is_empty()
		and bare["colors"] == {"trim": MeshPalette.RUST},
		"a look with no color table gets one")


func _a_region_joins_the_hide_list_and_leaves() -> void:
	var rig := _rig()
	var data: Dictionary = FigureEdits.slot_shape(rig, "main_hand").data.duplicate(true)
	var part_name: String = data["parts"][0]["name"]

	_expect(FigureEdits.set_hide(data, "torso", true).is_empty()
		and FigureEdits.set_hide(data, "arms", true).is_empty()
		and data["hides"] == ["arms", "torso"], "a region joins the hide list, in sorted order")
	_expect(FigureEdits.set_hide(data, "arms", true).is_empty()
		and data["hides"] == ["arms", "torso"], "a region joins the hide list one time")
	_expect(FigureLook.from_data(data).hides() == ["arms", "torso"],
		"the look reads with its hide list")
	_expect(FigureEdits.set_hide(data, "arms", false).is_empty() and data["hides"] == ["torso"],
		"a region leaves the hide list")
	_expect(FigureEdits.set_hide(data, "torso", false).is_empty() and not data.has("hides"),
		"the last region takes the hide list with it")
	_expect(not FigureEdits.set_hide(data, "", true).is_empty(), "no region gives a reason")

	var copy := {"format": 1, "key": "copy"}

	FigureEdits.set_part_fit(data, "body_2", part_name, true)
	_expect(FigureEdits.copy_look(copy, data).is_empty()
		and FigureLook.from_data(copy).fit_row("body_2", part_name)
			== FigureLook.from_data(data).fit_row("body_2", part_name),
		"a copied look takes the fit with the parts")
	_expect(not FigureEdits.set_part_fit(data, "body_2", "no_such_part", true).is_empty()
		and not FigureEdits.set_part_fit(data, "", part_name, true).is_empty(),
		"a fit for an unknown part, and a fit for no body type, each give a reason")


## The looks of the tier cases: a helm with parts, and a copy of it with
## another metal and one more hidden region.
func _tier_looks() -> Dictionary:
	var helm: Dictionary = FigureEdits.slot_shape(_rig(), "head").data.duplicate(true)
	var copper := FigureEdits.look_from("copper_helm", FigureLook.from_data(helm))

	helm["key"] = "scrap_helm"
	FigureEdits.set_color(copper, FigureEdits.ROLE_METAL, MeshPalette.COPPER)
	FigureEdits.set_hide(copper, "head", true)

	return {"scrap_helm": FigureLook.from_data(helm),
		"copper_helm": FigureLook.from_data(copper)}


func _a_look_becomes_a_tier() -> void:
	var looks := _tier_looks()
	var scrap: FigureLook = looks["scrap_helm"]
	var data: Dictionary = looks["copper_helm"].data.duplicate(true)

	_expect(FigureEdits.make_tier(data, "scrap_helm", looks).is_empty(),
		"a look becomes a tier of another look")

	var tier := FigureLook.from_data(data)

	_expect(tier.error.is_empty() and tier.base() == "scrap_helm" and tier.parts().is_empty()
		and tier.fit().is_empty(), "a tier has a base and no part of its own: " + tier.error)
	_expect(tier.colors() == {FigureEdits.ROLE_METAL: MeshPalette.COPPER},
		"a tier keeps only the colors that differ from its base")
	_expect(tier.hides() == ["head"], "a tier keeps only the regions that its base does not hide")
	looks["copper_helm"] = tier
	_expect(tier.resolved(looks).parts() == scrap.parts(),
		"the figure draws the parts of the base for a tier")
	_expect(FigureEdits.tiers_of(looks, "scrap_helm") == PackedStringArray(["copper_helm"])
		and FigureEdits.tiers_of(looks, "copper_helm").is_empty(),
		"a look names each of its tiers")

	var fresh := {"format": 1, "key": "rusty_helm"}

	_expect(FigureEdits.make_tier(fresh, "scrap_helm", looks).is_empty()
		and fresh == {"format": 1, "key": "rusty_helm", "base": "scrap_helm"},
		"a new tier is a file of three lines")
	_expect(not FigureEdits.make_tier(fresh.duplicate(), "rusty_helm", looks).is_empty(),
		"a look cannot be its own base")
	_expect(not FigureEdits.make_tier(fresh.duplicate(), "no_such_look", looks).is_empty(),
		"a base that is not there gives a reason")
	_expect(not FigureEdits.make_tier(scrap.data.duplicate(true), "copper_helm", looks).is_empty(),
		"two looks cannot name each other")

	_expect(FigureEdits.copy_look(data, scrap.data).is_empty() and not data.has("base")
		and FigureLook.from_data(data).parts() == scrap.parts(),
		"a look that takes the parts of another look is no tier after that")

	# A tier is a legal source of a copy: the copy takes the look that the
	# tier draws (ENG-0011).
	var from_tier := {"format": 1, "key": "iron_helm"}
	var drawn: FigureLook = tier.resolved(looks)

	_expect(FigureEdits.copy_look(from_tier, drawn.data).is_empty() and not from_tier.has("base")
		and FigureLook.from_data(from_tier).parts() == scrap.parts()
		and FigureLook.from_data(from_tier).colors()[FigureEdits.ROLE_METAL] == MeshPalette.COPPER
		and "head" in FigureLook.from_data(from_tier).hides(),
		"a copy from a tier takes the parts of the base, and the colors and the hides of the tier")


func _a_palette_takes_a_color_and_a_role() -> void:
	var start := FigureEdits.new_palette()
	var rig := _rig()
	var looks := {"body_1": FigureEdits.mannequin(rig),
		"main_hand": FigureEdits.slot_shape(rig, "main_hand")}

	_expect(start.error.is_empty() and not start.colors().is_empty(),
		"a new palette reads: " + start.error)

	for key: String in looks:
		for role: String in looks[key].colors():
			_expect(start.has_color(looks[key].colors()[role]),
				"a new palette has the color %s of %s" % [looks[key].colors()[role], key])
			_expect(start.roles().has(role), "a new palette has the color role %s" % role)

	var data: Dictionary = start.data.duplicate(true)
	var steel: String = looks["main_hand"].colors()[FigureEdits.ROLE_METAL]

	_expect(FigureEdits.set_named_color(data, "brass", Color("b5a642")).is_empty()
		and data["colors"]["brass"] == {"color": "b5a642"}, "a new named color joins the palette")
	_expect(FigureEdits.set_color_finish(data, "brass", MeshPalette.FINISH_METAL).is_empty()
		and FigureEdits.set_named_color(data, "brass", Color("c0b050")).is_empty()
		and data["colors"]["brass"] == {"color": "c0b050", "finish": MeshPalette.FINISH_METAL},
		"a named color takes a finish, and a new color keeps the finish")
	_expect(FigureEdits.set_color_finish(data, "brass", MeshPalette.FINISH_MATTE).is_empty()
		and not data["colors"]["brass"].has("finish"), "a matte finish leaves no key")
	_expect(not FigureEdits.set_named_color(data, "Bad Name", Color.WHITE).is_empty()
		and not FigureEdits.set_color_finish(data, "no_such_color", "matte").is_empty()
		and not FigureEdits.set_color_finish(data, "brass", "no_such_finish").is_empty(),
		"a bad name, an unknown color, and an unknown finish each give a reason")
	_expect(FigurePalette.from_data(data).error.is_empty(), "the palette reads after the changes")

	_expect(FigureEdits.looks_with_color(looks, steel) == PackedStringArray(["main_hand"]),
		"a named color names each look that has it")
	_expect(not FigureEdits.remove_named_color(data, steel, looks).is_empty()
		and data["colors"].has(steel), "a color that a look names stays")
	_expect(not FigureEdits.remove_named_color(data, data["roles"][FigureEdits.SKIN_ROLE], {})
		.is_empty(), "a color that a color role names stays")
	_expect(FigureEdits.remove_named_color(data, "brass", looks).is_empty()
		and not data["colors"].has("brass"), "a free color leaves")

	_expect(FigureEdits.set_role_color(data, "glow", steel).is_empty()
		and data["roles"]["glow"] == steel, "a new color role joins the palette")
	_expect(not FigureEdits.set_role_color(data, "glow", "no_such_color").is_empty()
		and data["roles"]["glow"] == steel, "a color role takes only a color of the palette")
	_expect(FigureEdits.remove_role(data, "glow", looks).is_empty()
		and not data["roles"].has("glow"), "a free color role leaves")

	var bare: Dictionary = looks["main_hand"].data.duplicate(true)

	bare.erase("colors")
	_expect(not FigureEdits.remove_role(data, FigureEdits.ROLE_METAL,
		{"main_hand": FigureLook.from_data(bare)}).is_empty(),
		"a color role stays while a look takes its color from the palette")
	_expect(FigureEdits.color_choices(start) == Array(start.color_names())
		and FigureEdits.color_choices(null).size() == MeshPalette.COLORS.size(),
		"a color list has the colors of the palette, or the start colors with no palette")


func _a_stance_takes_a_clip() -> void:
	var table := FigureEdits.new_stances()

	_expect(FigureStances.from_data(table).error.is_empty(), "a new stance table reads")
	_expect(FigureEdits.set_stance_clip(table, "", "walk", "walk").is_empty()
		and table["default"] == {"walk": "walk"}, "the default clip set takes a clip")
	_expect(FigureEdits.set_stance_clip(table, "spear", "walk", "spear_walk").is_empty()
		and table["stances"] == {"spear": {"walk": "spear_walk"}}, "a stance takes a clip")
	_expect(FigureEdits.set_stance_clip(table, "spear", "walk", "").is_empty()
		and table["stances"].is_empty(), "a stance with no action leaves the table")
	_expect(not FigureEdits.set_stance_clip(table, "Bad Type", "walk", "walk").is_empty()
		and not FigureEdits.set_stance_clip(table, "", "Bad Action", "walk").is_empty()
		and not FigureEdits.set_stance_clip(table, "", "walk", "Bad Clip").is_empty(),
		"a bad tool type, a bad action, and a bad clip name each give a reason")

	var data: Dictionary = FigureEdits.slot_shape(_rig(), "main_hand").data.duplicate(true)
	var part_name: String = data["parts"][0]["name"]

	FigureEdits.set_shape_value(data, part_name, 0, "finish", MeshPalette.FINISH_METAL)
	_expect(data["parts"][0]["shapes"][0]["finish"] == MeshPalette.FINISH_METAL,
		"a shape takes a finish of its own")
	FigureEdits.set_shape_value(data, part_name, 0, "finish", FigureEdits.FINISH_OF_COLOR)
	_expect(not data["parts"][0]["shapes"][0].has("finish"),
		"a shape gives its finish back to its named color")
