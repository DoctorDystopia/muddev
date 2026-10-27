extends Node
## Tests for the look files: [LookFile], [TerrainPalette], and the file
## side of [AreaLook] and of the palettes that read them.
##
##     godot --headless --path godot res://tests/test_look_files.tscn
##
## Needs nothing running. It writes under `user://` only, and it gives the
## readers their content through the cache, so no file of the repository
## changes. The cases:
##
## 1. A write and a read give the same content, and a missing file reads as
##    empty.
## 2. A colour of the file wins over the table. A row that the file lacks
##    draws the table colour, and a name that nothing has draws the hashed
##    hue or the default style.
## 3. The wall height comes from the file, then from the table, then from
##    the default style.
## 4. An area row of the file wins over the table, field by field. A reset
##    row gives the table back.
## 5. The look files of the repository read, and each key names a row of
##    the server table.
## 6. A family row of the file wins over the table of [FamilyShapes]. A
##    family with no row draws the table (ENG-0011, step L5). The place of
##    a part goes into its shapes.
## 7. A presentation row of the file wins over the table of
##    [ModelRegistry]. A model with no row draws the table (step L6).
## 8. The shadow minimum comes from the file, then from the default. A
##    value out of range clamps, and a value that is no number gives the
##    default. The value of the repository is in range.

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_a_write_reads_back()
	_the_file_wins_over_the_table()
	_the_wall_height_falls_back()
	_an_area_row_wins_field_by_field()
	_the_shadow_minimum_falls_back()
	_a_family_row_wins_over_the_table()
	_a_presentation_row_wins_over_the_table()
	_a_variant_choice_picks_a_served_key()
	_the_repository_files_read()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: look_files")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("FAIL: " + what)


func _a_write_reads_back() -> void:
	var path := "user://look_test_%d.json" % Time.get_ticks_usec()
	var content := {"format": 1, "floors": {"sand": "aabbcc"}}

	_expect(LookFile.read(path).is_empty(), "a missing file reads as empty")
	LookFile.forget(path)
	_expect(LookFile.write(path, content) == OK, "the write succeeds")
	LookFile.forget(path)
	_expect(LookFile.read(path) == content, "the read gives the written content")
	_expect(LookFile.color_of("aabbcc", Color.RED) == Color("aabbcc"), "a hex text is a colour")
	_expect(LookFile.color_of("not a colour", Color.RED) == Color.RED,
		"a bad text gives the fallback")
	_expect(LookFile.hex_of(Color("aabbcc")) == "aabbcc", "a colour gives six hex digits")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	LookFile.forget(path)


func _the_file_wins_over_the_table() -> void:
	var sand: String = FloorPalette.COLORS.keys()[0]

	LookFile.put(TerrainPalette.PATH, {"format": 1, "floors": {sand: "112233"},
		"walls": {"brick": {"color": "445566", "height": 7}}, "cliff": "778899"})

	_expect(FloorPalette.color_of(sand) == Color("112233"), "a floor colour of the file wins")
	_expect(FloorPalette.color_of("dirt") == FloorPalette.COLORS["dirt"],
		"a floor with no row draws the table colour")
	_expect(FloorPalette.color_of("no_such_floor") != FloorPalette.COLORS["dirt"],
		"a floor nothing has draws a hashed hue")
	_expect(FloorPalette.cliff() == Color("778899"), "the cliff colour of the file wins")
	_expect(FloorPalette.water() == FloorPalette.WATER_COLOR,
		"the water colour falls back to the table")
	_expect(WallPalette.side_color("brick") == Color("445566"), "a wall colour of the file wins")
	_expect(WallPalette.side_color("plain") == WallPalette.COLORS["plain"],
		"a wall style with no row draws the table colour")
	_expect(WallPalette.side_color("no_such_style") == WallPalette.side_color(
		_Const.TILE_DEFAULT_WALL_STYLE), "a style nothing has draws the default style")
	LookFile.forget(TerrainPalette.PATH)


func _the_wall_height_falls_back() -> void:
	LookFile.put(TerrainPalette.PATH, {"format": 1,
		"walls": {"brick": {"color": "445566", "height": 7}}})

	_expect(WallPalette.height_steps("brick") == 7, "a wall height of the file wins")
	_expect(WallPalette.height_steps("rubble") == WallPalette.HEIGHTS["rubble"],
		"a style with no row takes the table height")
	_expect(WallPalette.height_steps("no_such_style")
		== WallPalette.height_steps(_Const.TILE_DEFAULT_WALL_STYLE),
		"a style nothing has takes the height of the default style")
	LookFile.forget(TerrainPalette.PATH)


func _an_area_row_wins_field_by_field() -> void:
	var area: String = AreaLook.LOOKS.keys()[0]

	LookFile.put(AreaLook.PATH, {"format": 1, "areas": {area: {"fog_color": "123456",
		"fog_end": 99}}})

	var look := AreaLook.look_for(area)

	_expect(look["fog_color"] == Color("123456"), "a colour of the file wins")
	_expect(look["fog_end"] == 99.0 and look["fog_end"] is float, "a number of the file is a float")
	_expect(look["sun_energy"] == AreaLook.LOOKS[area]["sun_energy"],
		"a field the row lacks comes from the table")
	_expect(AreaLook.look_for("no_such_area") == AreaLook.FALLBACK.duplicate(),
		"an area nothing has gets the fallback")
	LookFile.forget(AreaLook.PATH)


func _the_shadow_minimum_falls_back() -> void:
	var key := AreaLook.KEY_SHADOW_MINIMUM

	LookFile.put(AreaLook.PATH, {"format": 1, "areas": {}, key: 0.65})
	_expect(is_equal_approx(AreaLook.shadow_minimum(), 0.65), "the shadow minimum of the file wins")
	LookFile.put(AreaLook.PATH, {"format": 1, "areas": {}})
	_expect(AreaLook.shadow_minimum() == AreaLook.SHADOW_MINIMUM_DEFAULT,
		"a file with no shadow minimum gives the default")
	LookFile.put(AreaLook.PATH, {"format": 1, key: 1.5})
	_expect(AreaLook.shadow_minimum() == 1.0, "a shadow minimum over 1 clamps to 1")
	LookFile.put(AreaLook.PATH, {"format": 1, key: -0.5})
	_expect(AreaLook.shadow_minimum() == 0.0, "a shadow minimum under 0 clamps to 0")
	LookFile.put(AreaLook.PATH, {"format": 1, key: "dark"})
	_expect(AreaLook.shadow_minimum() == AreaLook.SHADOW_MINIMUM_DEFAULT,
		"a shadow minimum that is no number gives the default")
	LookFile.forget(AreaLook.PATH)


func _a_family_row_wins_over_the_table() -> void:
	var weapon := _Const.ITEM_FAMILY_WEAPON
	var content := {"format": 1, "families": {}, "models": {}}
	var box := {"shape": FamilyShapes.SHAPE_BOX, "size": [0.2, 0.2, 0.2], "offset": [0.1, 0.0, 0.0],
		"color": MeshPalette.RUST}

	content["families"][weapon] = {"parts": [{"name": "block", "bone": FamilyLooks.ROOT_BONE,
		"position": [0.0, 0.3, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0],
		"shapes": [box]}]}
	content["families"]["new_family"] = FamilyLooks.row_from_parts(FamilyShapes.GENERIC)
	content["models"][weapon] = "a_sword"
	_expect(FamilyLooks.from_data(content).error.is_empty(), "the family file of the case reads")
	LookFile.put(FamilyLooks.PATH, content)

	var parts := FamilyShapes.parts_for(weapon)

	_expect(parts.size() == 1 and parts[0]["offset"].is_equal_approx(Vector3(0.1, 0.3, 0.0))
		and parts[0]["size"] is Vector3, "a family row of the file wins, with the place of its part")
	_expect(FamilyShapes.parts_for(_Const.ITEM_FAMILY_ARMOR)
		== FamilyShapes.SHAPES[_Const.ITEM_FAMILY_ARMOR], "a family with no row draws the table")
	_expect(FamilyShapes.has_shape("new_family") and "new_family" in FamilyShapes.families()
		and FamilyShapes.has_shape(_Const.ITEM_FAMILY_ARMOR),
		"the families are those of the file and of the table")
	_expect(FamilyShapes.model_for(weapon) == "a_sword"
		and FamilyShapes.model_for(_Const.FAMILY_CORPSE) == FamilyShapes.MODELS[_Const.FAMILY_CORPSE]
		and weapon in FamilyShapes.modelled_families(),
		"a model of the file wins, and a family with no row keeps the table model")

	var node := MeshBuilder.build(FamilyShapes.parts_for("new_family"))

	_expect(node.get_child_count() == FamilyShapes.GENERIC.size(),
		"a row made from the generic block builds the same parts")
	node.free()
	LookFile.put(FamilyLooks.PATH, {"format": 1})
	_expect(FamilyShapes.parts_for(weapon) == FamilyShapes.SHAPES[weapon]
		and FamilyShapes.model_for(weapon).is_empty(),
		"a file with no row gives the table back")
	LookFile.forget(FamilyLooks.PATH)


func _a_presentation_row_wins_over_the_table() -> void:
	var registry := ModelRegistry.new()
	var content := {"format": 1, "models": {"corpse_skeleton": {"scale": 2.0, "turn": [90.0, 0.0, 0.0]},
		"an_alias_file": {"offset": [0.0, 0.5, 0.0]}}}

	registry.ingest_manifest({"an_alias": "items/an_alias_file.glb", "big_mutant": "npcs/big_mutant.glb"})
	_expect(ModelPresentation.from_data(content).error.is_empty(), "the presentation of the case reads")
	LookFile.put(ModelPresentation.PATH, content)
	_expect(is_equal_approx(registry.scale_for("corpse_skeleton"), 2.0)
		and registry.rotation_for("corpse_skeleton").is_equal_approx(Vector3(PI / 2.0, 0.0, 0.0))
		and registry.offset_for("corpse_skeleton") == Vector3.ZERO,
		"a row of the file wins over the table, field by field")
	_expect(is_equal_approx(registry.scale_for("big_mutant"),
		ModelRegistry.PRESENTATION["big_mutant"]["scale"]), "a model with no row draws the table")
	_expect(registry.offset_for("an_alias").is_equal_approx(Vector3(0.0, 0.5, 0.0)),
		"an alias takes the row of its file")
	_expect(ModelPresentation.shown_row("big_mutant", content)["scale"]
		== ModelRegistry.PRESENTATION["big_mutant"]["scale"]
		and ModelPresentation.shown_row("corpse_skeleton", content)["scale"] == 2.0,
		"the shown row is the file over the table")
	LookFile.put(ModelPresentation.PATH, {"format": 1})
	_expect(is_equal_approx(registry.scale_for("corpse_skeleton"), 1.0)
		and registry.rotation_for("corpse_skeleton")
			== ModelRegistry.PRESENTATION["corpse_skeleton"]["rotation"],
		"a file with no row gives the table back")
	LookFile.forget(ModelPresentation.PATH)


## The variant choice of a look picks a served key (10/16/2026): the base
## for none, the variant for its key, the base or a variant for the auto
## variant, and the base for a key that is no variant of the base.
func _a_variant_choice_picks_a_served_key() -> void:
	var registry := ModelRegistry.new()

	registry.ingest_manifest({"pole": "props/pole.glb", "pole_bent": "props/pole_bent.glb",
		"pole_short": "props/pole_short.glb", "crate": "props/crate.glb"})
	_expect(registry.ingest_variants({"pole": ["pole_bent", "pole_short"], "bad": 7}) == 1,
		"a variant map reads its lists and drops a row that is no list")
	_expect(registry.variant_for("pole", "", "1,2,0") == "pole", "no choice gives the base")
	_expect(registry.variant_for("pole", "pole_bent", "1,2,0") == "pole_bent",
		"a variant key gives that variant")
	_expect(registry.variant_for("pole", "crate", "1,2,0") == "pole",
		"a key that is no variant of the base gives the base")
	_expect(registry.variant_for("crate", _Const.LOOK_VARIANT_ANY, "1,2,0") == "crate",
		"the auto variant of a model with no variant gives the base")

	var picked := {}

	for x: int in 60:
		picked[registry.variant_for("pole", _Const.LOOK_VARIANT_ANY, "%d,0,0" % x)] = true

	_expect(picked.size() == 3, "the auto variant reaches the base and each variant: %s" % [picked])
	_expect(registry.variant_for("pole", _Const.LOOK_VARIANT_ANY, "7,0,0")
		== registry.variant_for("pole", _Const.LOOK_VARIANT_ANY, "7,0,0"),
		"one seed gives one key")


func _the_repository_files_read() -> void:
	LookFile.forget(TerrainPalette.PATH)
	LookFile.forget(AreaLook.PATH)
	LookFile.forget(FamilyLooks.PATH)
	LookFile.forget(ModelPresentation.PATH)

	var palette := TerrainPalette.data()
	var looks := LookFile.read(AreaLook.PATH)
	var families := FamilyLooks.read_file(FamilyLooks.PATH)
	var presentation := ModelPresentation.read_file(ModelPresentation.PATH)

	_expect(not palette.is_empty() and palette.get("format") == LookFile.FORMAT,
		"the terrain palette of the repository reads")
	_expect(not looks.is_empty(), "the area looks of the repository read")

	if looks.has(AreaLook.KEY_SHADOW_MINIMUM):
		var minimum: Variant = looks[AreaLook.KEY_SHADOW_MINIMUM]
		var in_range: bool = typeof(minimum) in [TYPE_INT, TYPE_FLOAT] and minimum >= 0.0 \
			and minimum <= 1.0

		_expect(in_range, "the shadow minimum of the repository is a number from 0 to 1")
	_expect(families.error.is_empty() and not families.family_names().is_empty(),
		"the family file of the repository reads: " + families.error)
	_expect(presentation.error.is_empty() and not presentation.models().is_empty(),
		"the presentation file of the repository reads: " + presentation.error)
	_expect(families.to_text() == FileAccess.get_file_as_string(FamilyLooks.PATH)
		and presentation.to_text() == FileAccess.get_file_as_string(ModelPresentation.PATH),
		"the two files are in their canonical text")

	for family: String in families.family_names():
		_expect(family in _sendable_families(), "the family %s is one the server can send" % family)

	for family: String in families.models():
		_expect(family in _sendable_families(), "the modelled family %s is one the server can send"
			% family)

	for floor_name: String in palette.get("floors", {}):
		_expect(floor_name in _Const.TILE_FLOOR_TYPES, "the floor %s is a server floor type"
			% floor_name)

	for style: String in palette.get("walls", {}):
		_expect(style in _Const.TILE_WALL_STYLES, "the wall style %s is a server style" % style)

	for area: String in looks.get("areas", {}):
		_expect(area in _Const.TILE_AREAS, "the area %s is a server area" % area)


## Each family that the server can send: the item families, and the asset
## kinds. The same list as in `test_family_shapes.gd`.
func _sendable_families() -> PackedStringArray:
	var sendable := PackedStringArray(_Const.ITEM_FAMILIES)

	for kind: String in [_Const.FAMILY_NPC, _Const.FAMILY_CHARACTER, _Const.FAMILY_STATION,
			_Const.FAMILY_GATHERABLE, _Const.FAMILY_CORPSE, _Const.FAMILY_SIGN, _Const.FAMILY_ITEM,
			_Const.FAMILY_ROOM, _Const.FAMILY_GENERIC]:
		sendable.append(kind)

	return sendable
