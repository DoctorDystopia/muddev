extends Node
## Unit tests for MeshPalette, FamilyShapes and MeshBuilder — the FAMILY tiers
## of the mesh ladder, and the one question MeshResolver answers about them
## that needs no network.
##
##     godot --headless --path godot res://tests/test_family_shapes.tscn
##
## Everything here is asserted as a RELATIONSHIP over the table rather than as a
## census of it. A test that listed the eleven families by name would fail the
## day a twelfth is added as intended, which trains everyone to edit the test
## instead of reading it.

var _failures := 0

## How far outside the unit box a part may reach before it is a bug.
##
## Not zero: a torus at the edge of its ring, or a rotated cone, legitimately
## pokes a little past the nominal half-unit. Generous enough to allow that and
## tight enough to catch a part authored at ten times its intended size, which
## is the mistake that actually happens when transcribing a table.
const BOX_TOLERANCE := 0.35


func _ready() -> void:
	_the_table_was_actually_found()
	_every_family_has_parts()
	_every_part_is_well_formed()
	_every_family_builds()
	_every_family_fits_the_unit_box()
	_an_unknown_family_still_draws()
	_materials_are_never_shared()
	_the_palette_is_well_formed()
	_the_two_figures_differ_only_in_colour()
	_no_family_names_something_the_server_cannot_send()
	_no_family_model_names_something_the_server_cannot_send()
	_every_family_model_names_an_asset_key()
	_a_family_with_no_model_says_so()
	_art_redraws_the_entities_it_actually_draws()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: family_shapes")
	get_tree().quit(0)


## The guard that stops every test below from passing vacuously.
##
## Every check here iterates [method FamilyShapes.families]. If that returns
## nothing — a renamed table, a parse error in the shapes file, a static var
## that failed to initialise — every loop below runs zero times and the whole
## module goes green while checking nothing. This is the test that fails
## instead. It is the same guard `test_client_constants.py` carries, and it was
## earned the same way: the first run of this file reported PASS while every
## single case was erroring out.
func _the_table_was_actually_found() -> void:
	var families := FamilyShapes.families()

	_expect(not families.is_empty(),
		"FamilyShapes declares at least one family; if this fails every other "
		+ "check in this module is inert")

	# The generic block is what tier 3 draws, so an empty one is a family that
	# renders as nothing rather than as a box.
	_expect(not FamilyShapes.GENERIC.is_empty(),
		"the generic block has parts")


func _every_family_has_parts() -> void:
	for family: String in FamilyShapes.families():
		_expect(not FamilyShapes.parts_for(family).is_empty(),
			"%s has at least one part" % family)
		_expect(FamilyShapes.has_shape(family),
			"%s reports that it has a shape" % family)


## Derived from the table, so a part added tomorrow is checked with no edit.
func _every_part_is_well_formed() -> void:
	var shapes := [
		FamilyShapes.SHAPE_BOX, FamilyShapes.SHAPE_SPHERE,
		FamilyShapes.SHAPE_CYLINDER, FamilyShapes.SHAPE_CONE,
		FamilyShapes.SHAPE_TORUS, FamilyShapes.SHAPE_FACETED,
	]

	for family: String in FamilyShapes.families():
		for part: Dictionary in FamilyShapes.parts_for(family):
			var shape := str(part.get("shape", ""))
			var role := str(part.get("color", ""))

			_expect(shapes.has(shape),
				"%s: '%s' is a shape the builder knows" % [family, shape])
			_expect(MeshPalette.COLORS.has(role),
				"%s: '%s' is a colour the palette knows" % [family, role])

			if part.has("finish"):
				_expect(MeshPalette.FINISHES.has(str(part["finish"])),
					"%s: '%s' is a known finish" % [family, part["finish"]])


func _every_family_builds() -> void:
	for family: String in FamilyShapes.families():
		var node := MeshBuilder.build(FamilyShapes.parts_for(family))

		_expect(node != null, "%s builds to a node" % family)
		_expect(node.get_child_count() == FamilyShapes.parts_for(family).size(),
			"%s builds one instance per part" % family)

		for child: Node in node.get_children():
			var instance := child as MeshInstance3D

			_expect(instance != null, "%s: every child is a MeshInstance3D" % family)
			_expect(instance.mesh != null, "%s: every instance has a mesh" % family)
			_expect(instance.material_override != null,
				"%s: every instance owns a material" % family)

		node.free()


## The invariant the whole ladder rests on.
##
## Tier 1 is normalised into a unit box and tier 2 is authored inside one, so
## every caller can apply a single scale of its own. A family that quietly drew
## itself three units tall would tower over the room and nothing else would
## report it.
func _every_family_fits_the_unit_box() -> void:
	for family: String in FamilyShapes.families():
		var node := MeshBuilder.build(FamilyShapes.parts_for(family))
		var bounds := _bounds_of(node)
		var size := bounds.size
		var limit := 1.0 + BOX_TOLERANCE

		_expect(size.x <= limit and size.y <= limit and size.z <= limit,
			"%s fits the unit box (is %.2f x %.2f x %.2f)"
			% [family, size.x, size.y, size.z])

		node.free()


## A family with no entry is not an error. The server is free to name one this
## client has never heard of, and the answer must be a plain box rather than a
## gap in the room.
func _an_unknown_family_still_draws() -> void:
	var parts := FamilyShapes.parts_for("nothing_like_this_exists")

	_expect(parts == FamilyShapes.GENERIC, "an unknown family gets the generic block")
	_expect(not FamilyShapes.has_shape("nothing_like_this_exists"),
		"and says it has no shape of its own")

	var node := MeshBuilder.build(parts)

	_expect(node.get_child_count() > 0, "which still builds something visible")
	node.free()


## Guards the bug `takeOwnMaterials` exists to undo on the browser side: shared
## materials mean flashing one raider repaints every raider in the room.
func _materials_are_never_shared() -> void:
	var one := MeshPalette.material_for(MeshPalette.NPC, MeshPalette.FINISH_MATTE)
	var two := MeshPalette.material_for(MeshPalette.NPC, MeshPalette.FINISH_MATTE)

	_expect(one != two, "two asks for the same role give two materials")

	one.albedo_color = Color.WHITE

	_expect(two.albedo_color != Color.WHITE,
		"so tinting one does not tint the other")


func _the_palette_is_well_formed() -> void:
	for role: String in MeshPalette.COLORS:
		var colour := MeshPalette.color_of(role)

		_expect(colour != MeshPalette.MISSING_COLOR,
			"%s resolves to a real colour" % role)

	for finish: String in MeshPalette.FINISHES:
		var values: Array = MeshPalette.FINISHES[finish]

		_expect(values.size() == 2, "%s names a metalness and a roughness" % finish)


## Only the colour separates a wandering NPC from another player. If the two
## ever grew different geometry, the palette would stop being the distinction
## players actually read.
func _the_two_figures_differ_only_in_colour() -> void:
	var npc := FamilyShapes.parts_for("npc")
	var character := FamilyShapes.parts_for("character")

	_expect(npc.size() == character.size(), "both figures have the same parts")

	for index: int in npc.size():
		var a: Dictionary = npc[index]
		var b: Dictionary = character[index]

		_expect(a["shape"] == b["shape"], "part %d is the same shape" % index)
		_expect(a.get("radius") == b.get("radius"), "part %d is the same size" % index)
		_expect(a["color"] != b["color"], "part %d is a different colour" % index)


## The asymmetry CLAUDE.md states: a CLIENT key naming nothing is a bug; a
## server fact with no client entry is fine.
##
## So this checks one direction only. A family in the table that the server can
## never send is dead weight drawn for nothing — usually a typo, and one that
## would otherwise show up as an entity mysteriously rendering as a generic box.
## The reverse is deliberately allowed: a family added server-side falls through
## to the generic block, which is what lets content ship ahead of art.
func _no_family_names_something_the_server_cannot_send() -> void:
	var sendable := _sendable_families()

	for family: String in FamilyShapes.families():
		_expect(sendable.has(family),
			"'%s' is a family the server can actually send" % family)


## The same check over the MODELS table, and it earns its keep separately.
##
## A dead key here is worse than a dead key in SHAPES: a shape entry nobody can
## reach draws nothing and costs nothing, while a model entry nobody can reach
## means a packed `.glb` sitting in the served tree that no entity will ever
## ask for — art that was authored, packed, credited and then quietly orphaned
## by one wrong family name.
func _no_family_model_names_something_the_server_cannot_send() -> void:
	var sendable := _sendable_families()

	for family: String in FamilyShapes.modelled_families():
		_expect(sendable.has(family),
			"'%s' is a modelled family the server can actually send" % family)


## Values are ASSET KEYS, not paths.
##
## ModelRegistry owns where a model is fetched from, so a path here would be a
## second place to be wrong about the served tree — and it would fail silently,
## because `_art_for` would simply never find "npcs/corpse_skeleton.glb" in the
## manifest and the family would keep its procedural shape.
##
## That the key names art the BUILD can produce is checked from the other side,
## in `systems/interface/statefeed/tests/test_client_constants.py`, which can
## read `assets/model_manifest.json` and this cannot.
func _every_family_model_names_an_asset_key() -> void:
	for family: String in FamilyShapes.modelled_families():
		var asset_key := FamilyShapes.model_for(family)

		_expect(not asset_key.is_empty(),
			"'%s' names a non-empty asset key" % family)
		_expect(not asset_key.contains("/"),
			"'%s' names an asset key and not a path (%s)" % [family, asset_key])
		_expect(not asset_key.ends_with(".glb"),
			"'%s' names an asset key and not a file (%s)" % [family, asset_key])


## A family with no model answers "", not the first entry or an error.
##
## The empty string is what MeshResolver tests before reaching for tier 2, so a
## family that has never been given art has to be able to say so plainly.
func _a_family_with_no_model_says_so() -> void:
	_expect(FamilyShapes.model_for("nothing_has_this_family").is_empty(),
		"an unknown family names no model")

	# A family with a procedural shape and no model is the NORMAL case, and the
	# one that would break if MODELS were ever confused with SHAPES.
	var Const := preload("res://autoload/blackout_constants.gd")

	_expect(FamilyShapes.model_for(Const.ITEM_FAMILY_WEAPON).is_empty(),
		"a family drawn from primitives names no model")


## The regression this tier arrived with.
##
## EntityPool redraws on `refreshed`, which names an ASSET KEY. An entity drawn
## at tier 2 does not carry that key — a corpse's asset is the dead NPC's — so
## the pool comparing the two directly meant `corpse_skeleton` landing matched
## nothing and every body on screen stayed a generic box until something
## unrelated rebuilt the room. `redraws_for` is where that question moved.
func _art_redraws_the_entities_it_actually_draws() -> void:
	var Const := preload("res://autoload/blackout_constants.gd")
	var resolver := MeshResolver.new(ModelRegistry.new(), "")
	var corpse_model := FamilyShapes.model_for(Const.FAMILY_CORPSE)

	_expect(resolver.redraws_for("floating_eye", Const.FAMILY_NPC,
			"floating_eye"),
		"art for an entity's own asset key redraws it")
	_expect(not resolver.redraws_for("floating_eye", Const.FAMILY_NPC,
			"player_character"),
		"art for an unrelated key leaves an entity alone")
	_expect(resolver.redraws_for("mutant_raider", Const.FAMILY_CORPSE,
			corpse_model),
		"art for a family's model redraws an entity of that family")
	_expect(not resolver.redraws_for("mutant_raider", Const.FAMILY_NPC,
			corpse_model),
		"a family's model leaves entities of other families alone")

	# A Node, and this test is not in a tree to reap it.
	resolver.free()


## Every family name the server is able to put in the `family` field.
##
## The item families plus the asset kinds: `_mesh_family` returns the item's
## family for an item and the KIND itself for anything else, so both
## vocabularies are legitimate. Built once for the two checks that need it —
## a second copy is a second thing to forget when a kind is added.
func _sendable_families() -> PackedStringArray:
	var Const := preload("res://autoload/blackout_constants.gd")
	var sendable := PackedStringArray(Const.ITEM_FAMILIES)

	for kind: String in [Const.FAMILY_NPC, Const.FAMILY_CHARACTER,
			Const.FAMILY_STATION, Const.FAMILY_GATHERABLE, Const.FAMILY_CORPSE,
			Const.FAMILY_ITEM, Const.FAMILY_ROOM, Const.FAMILY_GENERIC]:
		sendable.append(kind)

	return sendable


## The AABB of a built node, in its own space.
func _bounds_of(node: Node3D) -> AABB:
	var bounds := AABB()
	var first := true

	for child: Node in node.get_children():
		var instance := child as MeshInstance3D

		if instance == null or instance.mesh == null:
			continue

		var box: AABB = instance.transform * instance.mesh.get_aabb()

		bounds = box if first else bounds.merge(box)
		first = false

	return bounds


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
