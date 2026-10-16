extends Node
## Tests for the palette, the colors of a figure, and the tiers of an item
## (DESIGN-0014 Phase W5): [FigurePalette], [FigureBuilder],
## [FigureOutfit], and [FigureSet].
##
##     godot --headless --path godot res://tests/test_figure_palette.tscn
##
## Needs nothing running and no editor. It writes only into a scratch
## directory under `user://`. It reads the figure files of the repository,
## and it never writes one. The cases:
##
## 1. A palette text that is read and written gives the same bytes. The
##    writer leaves out a matte finish.
## 2. The reader refuses a file with a bad form, and a newer format.
## 3. A color role takes its named color in the order of the class: the
##    figure, the look, the palette, then the role itself.
## 4. A named color that the palette does not have takes its color from
##    the start colors.
## 5. A figure draws each shape in the color of its palette. A change of
##    one named color draws the part again, and no other change does.
## 6. A shape has the finish of its named color, and a shape with a finish
##    of its own keeps it.
## 7. The colors of a figure go over the colors of each look.
## 8. A surface of a model takes the color of its color role from the
##    palette, and two surfaces of one color share one material.
## 9. THE PROOF OF THE PHASE: three tiers of one item draw from one mesh
##    and three small files.
## 10. The figure set gives its palette, and a set with none has an empty
##     one.
## 11. The palette of the repository reads, and it is in its canonical
##     text. Each color that a look of the repository names is in it.

const LOOK := FigureStore.KIND_LOOK
const PALETTE := FigureStore.KIND_PALETTE

## The three tiers of the proof, and the metal of each one.
const TIERS := {"rusty_scrap_sword": "rust", "scrap_sword": "iron", "copper_sword": "copper"}

## A tier file has fewer lines than this. The look with the parts has more
## than ten times as many.
const SMALL_FILE_LINES := 10

var _failures := 0
var _scratch := ""


func _ready() -> void:
	_scratch = ProjectSettings.globalize_path("user://figure_palette_test_%d"
		% Time.get_ticks_usec())

	_a_palette_text_gives_the_same_bytes()
	_the_reader_refuses_a_bad_form()
	_a_role_takes_its_color_in_order()
	_a_figure_draws_in_the_colors_of_its_palette()
	_a_shape_has_the_finish_of_its_color()
	_the_colors_of_a_figure_go_over_each_look()
	_a_model_surface_takes_a_palette_color()
	_three_tiers_draw_from_one_mesh()
	_the_figure_set_gives_its_palette()
	_the_repository_palette_reads()
	_remove_scratch(_scratch)

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_palette")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _rig() -> FigureRig:
	return FigureEdits.rig_from_profile("body_1")


## A palette with three colors and two color roles.
func _palette(steel := "b9c6d2") -> FigurePalette:
	return FigurePalette.from_data({"format": 1,
		"colors": {"steel": {"color": steel, "finish": "metal"},
			"brass": {"color": "b5a642"}, "tan": {"color": "d2b48c"}},
		"roles": {"metal": "steel", "skin": "tan"}})


## A look with one part of one box, in the color role `role`.
func _box_look(key: String, role: String, colors := {}) -> FigureLook:
	return FigureLook.from_data({"format": 1, "key": key, "colors": colors,
		"parts": [{"name": "item", "bone": "hand_r", "shapes": [
			{"shape": FamilyShapes.SHAPE_BOX, "color": role}]}]})


## The material of the first mesh of one part of a figure.
func _material_of(figure: Node3D, look_key: String, part_name := "item") -> StandardMaterial3D:
	var part := FigureBuilder.part_node(figure, look_key, part_name)
	var instance := part.get_child(0) as MeshInstance3D

	return instance.material_override as StandardMaterial3D


func _a_palette_text_gives_the_same_bytes() -> void:
	var palette := _palette()
	var text := palette.to_text()
	var again := FigurePalette.from_text(text)

	_expect(palette.error.is_empty(), "a palette reads: " + palette.error)
	_expect(again.error.is_empty() and again.to_text() == text,
		"a read and a write give the same bytes: " + again.error)
	_expect(palette.key() == FigurePalette.KEY, "a palette has the key of its one file")
	_expect(palette.color_names() == PackedStringArray(["brass", "steel", "tan"])
		and palette.role_names() == PackedStringArray(["metal", "skin"]),
		"the names come in sorted order")
	_expect(palette.hex_of("brass") == "b5a642" and palette.hex_of("no_such") == "",
		"a named color gives its six digits")
	_expect(palette.finish_of("steel") == MeshPalette.FINISH_METAL
		and palette.finish_of("brass") == MeshPalette.FINISH_MATTE,
		"a named color with no finish is matte")

	var matte := FigurePalette.from_data({"format": 1,
		"colors": {"tan": {"color": "d2b48c", "finish": "matte"}}})

	_expect(matte.error.is_empty() and not matte.colors()["tan"].has("finish")
		and matte.to_text().contains("roles") and matte.to_text().contains("finishes"),
		"the writer leaves out a matte finish, and it keeps the three tables")
	_a_finish_comes_from_the_file_then_the_table()


## The finishes table of the file wins over MeshPalette (ENG-0011, step
## L4). A finish that the file lacks comes from MeshPalette. A material of
## a role goes through the roles table. MeshBuilder draws with the active
## palette.
func _a_finish_comes_from_the_file_then_the_table() -> void:
	var palette := FigurePalette.from_data({"format": 1,
		"colors": {"steel": {"color": "112233", "finish": "chrome"}},
		"roles": {"metal": "steel"},
		"finishes": {"chrome": {"metalness": 0.9, "roughness": 0.1}}})
	var bad := FigurePalette.from_data({"format": 1,
		"finishes": {"chrome": {"metalness": 2.0, "roughness": 0.1}}})

	_expect(palette.error.is_empty(), "a palette with a finishes table reads: " + palette.error)
	_expect(not bad.error.is_empty(), "a finish out of the range does not read")
	_expect(palette.finish_values("chrome") == [0.9, 0.1], "a finish of the file gives its numbers")
	_expect(palette.finish_values(MeshPalette.FINISH_GEM) == MeshPalette.FINISHES[MeshPalette.FINISH_GEM],
		"a finish the file lacks comes from MeshPalette")
	_expect(palette.has_finish("chrome") and palette.has_finish(MeshPalette.FINISH_METAL)
		and not palette.has_finish("no_such"), "has_finish knows the file and the table")
	_expect("chrome" in palette.finish_names() and MeshPalette.FINISH_MATTE in palette.finish_names(),
		"the finish names hold the file and the table")
	_expect(palette.colors_with_finish("chrome") == PackedStringArray(["steel"]),
		"a finish names the colors that have it")

	var material := palette.material_for_role("metal")

	_expect(material.albedo_color.is_equal_approx(Color("112233"))
		and is_equal_approx(material.metallic, 0.9),
		"a role draws with the named color of the roles table and its finish")

	FigurePalette.active = palette

	var part := MeshBuilder.build_part({"shape": FamilyShapes.SHAPE_BOX, "color": "metal"})
	var rust := MeshBuilder.build_part({"shape": FamilyShapes.SHAPE_BOX, "color": MeshPalette.RUST})

	_expect((part.material_override as StandardMaterial3D).albedo_color.is_equal_approx(
		Color("112233")), "MeshBuilder draws a part with the active palette")
	_expect((rust.material_override as StandardMaterial3D).albedo_color.is_equal_approx(
		MeshPalette.color_of(MeshPalette.RUST)), "a name the palette lacks comes from MeshPalette")
	FigurePalette.active = null
	part.free()
	rust.free()
	_expect(FigurePalette.new().colors().is_empty() and FigurePalette.new().roles().is_empty(),
		"a palette with no file has no color and no color role")


func _the_reader_refuses_a_bad_form() -> void:
	var bad := [
		[{"colors": {}}, "a palette needs a format"],
		[{"format": FigurePalette.FORMAT + 1}, "a newer format does not read"],
		[{"format": 1, "colors": []}, "colors is a table"],
		[{"format": 1, "colors": {"tan": "d2b48c"}}, "a named color is a table"],
		[{"format": 1, "colors": {"tan": {"color": "D2B48C"}}}, "a color is in lower case"],
		[{"format": 1, "colors": {"tan": {"color": "d2b4"}}}, "a color has six digits"],
		[{"format": 1, "colors": {"Tan": {"color": "d2b48c"}}}, "a color name is plain"],
		[{"format": 1, "colors": {"tan": {"color": "d2b48c", "finish": "shiny"}}},
			"a finish is a finish of the client"],
		[{"format": 1, "roles": {"skin": 3}}, "a color role names a color"],
		[{"format": 1, "roles": {"Skin": "tan"}}, "a role name is plain"],
	]

	_expect(not FigurePalette.from_text("[]").error.is_empty(), "a list is not a palette")

	for pair: Array in bad:
		_expect(not FigurePalette.from_data(pair[0]).error.is_empty(), pair[1])

	_expect(FigurePalette.from_data({"format": 1}).error.is_empty(),
		"a palette with no color reads")


func _a_role_takes_its_color_in_order() -> void:
	var palette := _palette()

	_expect(palette.named_for("metal", {"metal": "brass"}, {"metal": "tan"}) == "tan",
		"the color of the figure is first")
	_expect(palette.named_for("metal", {"metal": "brass"}) == "brass",
		"the color of the look is second")
	_expect(palette.named_for("metal", {}) == "steel", "the color of the palette is third")
	_expect(palette.named_for("brass", {}) == "brass",
		"a role with no color is a named color itself")
	_expect(palette.color_of("brass").is_equal_approx(Color("b5a642")),
		"a named color gives its color")
	_expect(palette.color_of(MeshPalette.GOLD).is_equal_approx(
		MeshPalette.color_of(MeshPalette.GOLD)),
		"a name that the palette does not have takes a start color")
	_expect(palette.material_key("steel") != palette.material_key("brass")
		and palette.material_key("steel") == _palette().material_key("steel"),
		"one color and one finish give one material key")
	_expect(palette.stamp() == _palette().stamp() and palette.stamp() != _palette("000000").stamp(),
		"the stamp follows the content")


func _a_figure_draws_in_the_colors_of_its_palette() -> void:
	var rig := _rig()
	var look := _box_look("sword", "metal")
	var figure := FigureBuilder.build(rig, [look], null, _palette())
	var part := FigureBuilder.part_node(figure, "sword", "item")
	var mesh_node := part.get_child(0)

	_expect(_material_of(figure, "sword").albedo_color.is_equal_approx(Color("b9c6d2")),
		"a color role with no color of its look takes the color of the palette")

	FigureBuilder.refresh(figure, rig, [look], null, _palette())
	_expect(part.get_child(0) == mesh_node, "the same palette keeps the mesh of a part")

	FigureBuilder.refresh(figure, rig, [look], null, _palette("101010"))
	_expect(FigureBuilder.part_node(figure, "sword", "item") == part
		and _material_of(figure, "sword").albedo_color.is_equal_approx(Color("101010")),
		"a new color of the palette draws the part again, and the part keeps its node")

	FigureBuilder.refresh(figure, rig, [_box_look("sword", "metal", {"metal": "brass"})],
		null, _palette())
	_expect(_material_of(figure, "sword").albedo_color.is_equal_approx(Color("b5a642")),
		"the color of the look goes over the color of the palette")

	FigureBuilder.refresh(figure, rig, [_box_look("sword", MeshPalette.GOLD)])
	_expect(_material_of(figure, "sword").albedo_color.is_equal_approx(
		MeshPalette.color_of(MeshPalette.GOLD)), "a figure with no palette has the start colors")
	figure.free()


func _a_shape_has_the_finish_of_its_color() -> void:
	var rig := _rig()
	var metal: Array = MeshPalette.FINISHES[MeshPalette.FINISH_METAL]
	var matte: Array = MeshPalette.FINISHES[MeshPalette.FINISH_MATTE]
	var figure := FigureBuilder.build(rig, [_box_look("sword", "metal")], null, _palette())

	_expect(is_equal_approx(_material_of(figure, "sword").metallic, metal[0])
		and is_equal_approx(_material_of(figure, "sword").roughness, metal[1]),
		"a shape has the finish of its named color")

	var own := FigureLook.from_data({"format": 1, "key": "sword", "parts": [
		{"name": "item", "bone": "hand_r", "shapes": [{"shape": FamilyShapes.SHAPE_BOX,
			"color": "metal", "finish": MeshPalette.FINISH_MATTE}]}]})

	FigureBuilder.refresh(figure, rig, [own], null, _palette())
	_expect(is_equal_approx(_material_of(figure, "sword").metallic, matte[0]),
		"a shape with a finish of its own keeps it")
	figure.free()


func _the_colors_of_a_figure_go_over_each_look() -> void:
	var rig := _rig()
	var body := FigureLook.from_data({"format": 1, "key": "body_1",
		"colors": {"skin": "tan"}, "parts": [{"name": "head", "bone": "Head",
			"shapes": [{"shape": FamilyShapes.SHAPE_BOX, "color": "skin"}]}]})
	var sword := _box_look("sword", "metal")
	var figure := FigureBuilder.build(rig, [body, sword], null, _palette(), {"skin": "brass"})

	_expect(_material_of(figure, "body_1", "head").albedo_color.is_equal_approx(Color("b5a642")),
		"the skin of a figure takes the color of the figure, over the color of the body")
	_expect(_material_of(figure, "sword").albedo_color.is_equal_approx(Color("b9c6d2")),
		"a color role that the figure does not name keeps its color")

	FigureBuilder.refresh(figure, rig, [body, sword], null, _palette())
	_expect(_material_of(figure, "body_1", "head").albedo_color.is_equal_approx(Color("d2b48c")),
		"with no color of the figure, the body has its own color again")
	figure.free()


func _a_model_surface_takes_a_palette_color() -> void:
	var rig := _rig()
	var models := FigureModels.new()
	var shapes := FigureLook.from_data({"format": 1, "key": "helm", "parts": [
		{"name": "Dome", "bone": "Head", "shapes": [
			{"shape": FamilyShapes.SHAPE_BOX, "color": "metal"}]}]})

	_expect(models.put_buffer("helm_model",
		FigureReference.buffer_of(rig, [shapes], null, _palette())),
		"a reference body gives the bytes of a model")

	var node_name: String = models.node_names("helm_model")[0]
	var look := func(colors: Dictionary) -> FigureLook:
		return FigureLook.from_data({"format": 1, "key": "helm", "colors": colors,
			"parts": [{"name": "dome", "bone": "Head", "model": "helm_model",
				"node": node_name}]})
	var first := FigureBuilder.build(rig, [look.call({"metal": "brass"})], models, _palette())
	var second := FigureBuilder.build(rig, [look.call({"metal": "brass"})], models, _palette())
	var plain := FigureBuilder.build(rig, [look.call({})], models, _palette())
	var one := (FigureBuilder.part_node(first, "helm", "dome").get_child(0) as MeshInstance3D)
	var two := (FigureBuilder.part_node(second, "helm", "dome").get_child(0) as MeshInstance3D)
	var bare := (FigureBuilder.part_node(plain, "helm", "dome").get_child(0) as MeshInstance3D)
	var material := one.get_surface_override_material(0) as StandardMaterial3D

	_expect(material != null and material.albedo_color.is_equal_approx(Color("b5a642")),
		"a surface of a model takes the color of its color role from the palette")
	_expect(material == two.get_surface_override_material(0),
		"two surfaces of one color and one finish share one material")
	_expect(bare.get_surface_override_material(0) == null,
		"a surface whose role the look gives no color keeps the material of the model")
	first.free()
	second.free()
	plain.free()


## The proof of Phase W5: three tiers of one item draw from one mesh and
## three small files. The mesh is the slot shape of the hand. Each tier is
## a look file with a base and one color.
func _three_tiers_draw_from_one_mesh() -> void:
	var rig := _rig()
	var store := FigureStore.new(_scratch.path_join("tiers"))
	var palette := FigureEdits.new_palette()
	var slot_shape := FigureEdits.slot_shape(rig, "main_hand")
	var shape_lines := slot_shape.to_text().count("\n")
	var seen := {}

	store.put(FigureStore.KIND_RIG, rig.key(), rig.data)
	store.put(PALETTE, PALETTE, palette.data)
	store.put(LOOK, "main_hand", slot_shape.data)

	for tier: String in TIERS:
		var data := {"format": 1, "key": tier}

		_expect(FigureEdits.make_tier(data, "main_hand", store.looks).is_empty()
			and FigureEdits.set_color(data, FigureEdits.ROLE_METAL, TIERS[tier], palette).is_empty()
			and store.put(LOOK, tier, data).is_empty(), "%s is a tier of the slot shape" % tier)

	_expect(store.save().size() == TIERS.size() + 3 and store.errors.is_empty(),
		"a save writes the rig, the palette, the slot shape, and the three tiers")

	var read := FigureStore.new(store.directory)

	read.load_all()
	_expect(read.errors.is_empty(), "the files read again: %s" % [read.errors])

	for tier: String in TIERS:
		var text := FileAccess.get_file_as_string(read.path_of(LOOK, tier))
		var looks := FigureOutfit.looks_for(rig, {"main_hand": tier}, read.looks)
		var figure := FigureBuilder.build(rig, looks, null, read.palette())
		var blade := _material_of(figure, tier, FigureEdits.ITEM_PART)

		_expect(text.count("\n") < SMALL_FILE_LINES and text.count("\n") * 10 < shape_lines,
			"the file of %s has %d lines, and the slot shape has %d"
				% [tier, text.count("\n"), shape_lines])
		_expect(not text.contains("parts") and not text.contains("shapes"),
			"the file of %s holds no mesh" % tier)
		_expect(looks.size() == 1 and looks[0].key() == tier
			and looks[0].parts() == read.looks["main_hand"].parts(),
			"%s draws the parts of the one slot shape" % tier)
		_expect(blade.albedo_color.is_equal_approx(read.palette().color_of(TIERS[tier])),
			"the blade of %s has the metal of its tier" % tier)
		seen[blade.albedo_color.to_html(false)] = true
		figure.free()

	_expect(seen.size() == TIERS.size(), "the three tiers have three metals")


func _the_figure_set_gives_its_palette() -> void:
	var rig := _rig()
	var with := FigureSet.from_data({"format": 1, "rigs": {rig.key(): rig.data},
		"looks": {}, "palette": _palette().data})
	var without := FigureSet.from_data({"format": 1, "rigs": {rig.key(): rig.data}, "looks": {}})
	var bad := FigureSet.from_data({"format": 1, "rigs": {}, "looks": {},
		"palette": {"format": 1, "colors": {"tan": "not a table"}}})

	_expect(with.error.is_empty() and with.palette.to_text() == _palette().to_text(),
		"the figure set gives its palette: " + with.error)
	_expect(without.error.is_empty() and without.palette.colors().is_empty(),
		"a figure set with no palette has an empty one")
	_expect(bad.error.is_empty() and bad.palette.colors().is_empty() and bad.errors.size() == 1,
		"a palette that does not read stays out of the set, and the set names it")
	_expect(not FigureSet.from_data({"format": 1, "palette": []}).error.is_empty(),
		"a palette that is no table does not read")


func _the_repository_palette_reads() -> void:
	var store := FigureStore.new(FigureStore.repo_directory())

	store.load_all()

	var palette := store.palette()
	var path := store.path_of(PALETTE, PALETTE)

	_expect(store.has(PALETTE, PALETTE) and palette.error.is_empty(),
		"the repository has a palette that reads: %s" % [store.errors])
	_expect(FileAccess.get_file_as_string(path).replace("\r\n", "\n") == palette.to_text(),
		"the palette of the repository is in its canonical text")

	for role: String in palette.roles():
		_expect(palette.has_color(palette.roles()[role]),
			"the color role %s names a color of the palette" % role)

	for key: String in store.keys_of(LOOK):
		var look: FigureLook = store.looks[key]

		for role: String in look.colors():
			_expect(palette.has_color(look.colors()[role]),
				"the palette has the color %s of the look %s" % [look.colors()[role], key])

	var served := FigureSet.read_file(FigureStore.repo_models_directory()
		.path_join(FigureSet.FILE_NAME))

	_expect(served.error.is_empty() and served.palette.to_text() == palette.to_text(),
		"the served figure set has the palette of the repository: " + served.error)


func _remove_scratch(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return

	for directory: String in DirAccess.get_directories_at(path):
		_remove_scratch(path.path_join(directory))

	for file_name: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(file_name))

	DirAccess.remove_absolute(path)
