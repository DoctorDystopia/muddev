extends Node
## Tests for the outfit of a figure (DESIGN-0014 Phase W3): [FigureOutfit],
## [FigureCatalog], and the item catalog of the repository.
##
##     godot --headless --path godot res://tests/test_figure_outfit.tscn
##
## Needs nothing running and no editor. It writes no file. It reads the
## figure files and the item catalog of the repository. The cases:
##
## 1. The worn look of an item draws first, then the slot shape of its
##    slot, then the family shape. A slot with no bone draws nothing.
## 2. The looks of a figure are the body, then one look for each slot. A
##    look goes into the list one time.
## 3. A family shape is one part on the default bone of its slot, and it
##    builds.
## 4. A catalog with a bad form gives a reason. A good one gives its slots
##    in their order and the items of a slot by tier.
## 5. An item in a slot empties each slot that it clears.
## 6. An outfit keeps only what the catalog has, and it holds no two items
##    that clear each other.
## 7. The item catalog of the repository reads. Each slot name that the
##    workbench types is a slot of it.
## 8. Each item of the catalog draws on each body type of the repository.
##    An item with a served model of the repository draws that model.
## 9. A served model in hand wins over the worn look (10/17/2026). It takes
##    the box of the stand-in, or the place of its `served` row, and the
##    hide list and the colors of the look. A look that names the model
##    draws as it is. A look with only a `served` row gives the slot shape
##    as the stand-in. A model with no bone to hold it draws nothing.

const SWORD := "iron_sword"
const STICK := "wood_sword"
const PIKE := "iron_pike"
const HELM := "iron_helm"
const HAT := "odd_hat"
const TAIL_RING := "tail_ring"

## A slot of the test catalog that no rig has a bone for.
const TAIL := "tail"

## The rounding of a place in a look file, and a little more.
const PLACE_TOLERANCE := 0.001

var _failures := 0


func _ready() -> void:
	_the_look_of_an_item_draws_first()
	_the_looks_are_the_body_then_each_slot()
	_a_family_shape_stands_on_the_slot_bone()
	_a_catalog_reads_or_gives_a_reason()
	_an_item_clears_its_slots()
	_an_outfit_keeps_what_the_catalog_has()
	_the_repository_catalog_reads()
	_each_item_of_the_repository_draws()
	_a_served_model_wins()
	_a_served_model_takes_its_place()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_outfit")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _rig() -> FigureRig:
	return FigureEdits.rig_from_profile("body_1")


func _item(key: String, slot: String, tier: int, family: String) -> Dictionary:
	return {"key": key, "name": key.replace("_", " "), "slot": slot, "tool_type": "",
		"tier": tier, "family": family}


func _catalog_data() -> Dictionary:
	return {
		"format": 1,
		"slots": [
			{"key": "main_hand", "label": "Main Hand", "clears": ["two_hands"]},
			{"key": "off_hand", "label": "Off Hand", "clears": ["two_hands"]},
			{"key": "two_hands", "label": "Two Hands", "clears": ["main_hand", "off_hand"]},
			{"key": "head", "label": "Head", "clears": []},
			{"key": TAIL, "label": "Tail", "clears": []},
		],
		"items": [
			_item(SWORD, "main_hand", 1, "weapon"),
			_item(STICK, "main_hand", 0, "weapon"),
			_item(PIKE, "two_hands", 1, "weapon"),
			_item(HELM, "head", 1, "armor"),
			_item(HAT, "head", 0, "no_such_family"),
			_item(TAIL_RING, TAIL, 0, "jewellery"),
		],
	}


func _catalog() -> FigureCatalog:
	return FigureCatalog.from_data(_catalog_data())


## The looks of a store: the body, the look of the sword and of the helm,
## and the slot shape of the main hand.
func _looks(rig: FigureRig) -> Dictionary:
	var slot_shape := FigureEdits.slot_shape(rig, "main_hand")

	return {
		rig.key(): FigureEdits.mannequin(rig),
		"main_hand": slot_shape,
		SWORD: FigureLook.from_data(FigureEdits.look_from(SWORD, slot_shape)),
		HELM: FigureLook.from_data(FigureEdits.look_from(HELM,
			FigureEdits.slot_shape(rig, "head"))),
	}


func _the_look_of_an_item_draws_first() -> void:
	var rig := _rig()
	var looks := _looks(rig)

	_expect(FigureOutfit.source_of(rig, "main_hand", SWORD, looks) == FigureOutfit.SOURCE_LOOK
		and FigureOutfit.look_of(rig, "main_hand", SWORD, looks) == looks[SWORD],
		"an item with a worn look draws that look")
	_expect(FigureOutfit.source_of(rig, "main_hand", STICK, looks)
		== FigureOutfit.SOURCE_SLOT_SHAPE
		and FigureOutfit.look_of(rig, "main_hand", STICK, looks) == looks["main_hand"],
		"an item with no worn look draws the slot shape of its slot")
	_expect(FigureOutfit.source_of(rig, "main_hand", "main_hand", looks)
		== FigureOutfit.SOURCE_LOOK, "the key of a slot draws its slot shape")
	_expect(FigureOutfit.source_of(rig, "two_hands", PIKE, looks) == FigureOutfit.SOURCE_FAMILY,
		"a slot with no slot shape draws the family shape")
	_expect(FigureOutfit.source_of(rig, TAIL, TAIL_RING, looks) == FigureOutfit.SOURCE_NOTHING
		and FigureOutfit.look_of(rig, TAIL, TAIL_RING, looks) == null,
		"a slot with no bone and no look draws nothing")
	_expect(FigureOutfit.source_of(rig, "main_hand", "", looks) == FigureOutfit.SOURCE_NOTHING,
		"an empty slot draws nothing")


func _the_looks_are_the_body_then_each_slot() -> void:
	var rig := _rig()
	var looks := _looks(rig)
	var worn := {"main_hand": STICK, "head": HELM, TAIL: TAIL_RING}

	_expect(_keys(FigureOutfit.looks_for(rig, worn, looks)) == [rig.key(), HELM, "main_hand"],
		"the body is first, then one look for each slot in sorted order: %s"
			% [_keys(FigureOutfit.looks_for(rig, worn, looks))])
	_expect(_keys(FigureOutfit.looks_for(rig, {}, looks)) == [rig.key()],
		"a figure with no outfit wears its body")

	looks.erase(rig.key())
	_expect(_keys(FigureOutfit.looks_for(rig, {"head": HELM}, looks)) == [HELM],
		"a rig with no body wears only the outfit")
	_expect(_keys(FigureOutfit.looks_for(rig, {"head": HELM, "main_hand": HELM}, looks))
		== [HELM], "a look that two slots name goes into the list one time")

	var family := FigureOutfit.looks_for(rig, {"two_hands": PIKE}, looks, {PIKE: "weapon"})

	_expect(family.size() == 1
		and family[0].key() == FigureOutfit.FAMILY_KEY_PREFIX + "two_hands",
		"an item with no look and no slot shape gets a family shape look")


func _keys(looks: Array) -> Array:
	var keys := []

	for look: FigureLook in looks:
		keys.append(look.key())

	return keys


func _a_family_shape_stands_on_the_slot_bone() -> void:
	var rig := _rig()
	var look := FigureOutfit.family_look(rig, "main_hand", "weapon")
	var wanted: Array = FamilyShapes.parts_for("weapon")

	_expect(look.error.is_empty() and look.parts().size() == 1,
		"a family shape look reads, with one part: " + look.error)

	if look.parts().size() != 1:
		return

	var row: Dictionary = look.parts()[0]

	_expect(row["bone"] == rig.slots()["main_hand"],
		"the part is on the default bone of the slot")
	_expect(row["shapes"].size() == wanted.size(), "the part has each shape of the family")
	_expect(FigureJson.is_numbers(row["shapes"][0]["size"], FigureJson.VECTOR_SIZE),
		"a vector of a family shape is an [x, y, z] array")
	_expect(FigureLook.part_transform(row).basis.get_scale().is_equal_approx(
		Vector3.ONE * FigureOutfit.FAMILY_SCALE), "the part has the scale of a family shape")

	var figure := FigureBuilder.build(rig, [look])
	var node := FigureBuilder.part_node(figure, look.key(), FigureOutfit.FAMILY_PART)

	_expect(node != null and node.get_child_count() == wanted.size(),
		"the family shape builds, with one mesh for each shape")
	figure.free()

	_expect(FigureOutfit.family_look(rig, "head", "no_such_family").parts()[0]["shapes"].size()
		== FamilyShapes.GENERIC.size(), "an unknown family gets the generic shape")


func _a_catalog_reads_or_gives_a_reason() -> void:
	var catalog := _catalog()
	var newer := _catalog_data()
	var no_items := _catalog_data()
	var bad_item := _catalog_data()

	newer["format"] = FigureCatalog.FORMAT + 1
	no_items.erase("items")
	bad_item["items"].append({"key": "no_slot", "name": "no slot", "family": "weapon"})

	_expect(catalog.error.is_empty(), "a good catalog reads: " + catalog.error)
	_expect(not FigureCatalog.from_data({}).error.is_empty()
		and not FigureCatalog.from_data(newer).error.is_empty()
		and not FigureCatalog.from_data(no_items).error.is_empty()
		and not FigureCatalog.from_data(bad_item).error.is_empty(),
		"a catalog with a bad form gives a reason")
	_expect(not FigureCatalog.read_file("res://tests/no_such_catalog.json").error.is_empty(),
		"a catalog file that is not there gives a reason")

	_expect(catalog.slot_keys() == PackedStringArray(["main_hand", "off_hand", "two_hands",
		"head", TAIL]), "the slots keep the order of the file")
	_expect(catalog.label_of("main_hand") == "Main Hand" and catalog.label_of("none") == "none",
		"a slot gives its label, and an unknown slot gives its key")
	_expect(catalog.has_item(SWORD) and catalog.slot_of(SWORD) == "main_hand"
		and catalog.slot_of("none").is_empty() and not catalog.has_item("main_hand"),
		"an item gives its slot")

	var hand := catalog.items_of("main_hand")

	_expect(hand.size() == 2 and hand[0]["key"] == STICK and hand[1]["key"] == SWORD,
		"the items of a slot are in the order of their tiers")
	_expect(catalog.families()[HELM] == "armor"
		and catalog.families().size() == catalog.items().size(),
		"the catalog gives the family of each item")


func _an_item_clears_its_slots() -> void:
	var catalog := _catalog()
	var empty := {}
	var one := catalog.wear(empty, "main_hand", SWORD)
	var both := catalog.wear(one, "off_hand", "off_hand")
	var pike := catalog.wear(both, "two_hands", PIKE)

	_expect(empty.is_empty() and one == {"main_hand": SWORD}, "wear gives a new outfit")
	_expect(both == {"main_hand": SWORD, "off_hand": "off_hand"},
		"the two hand slots hold an item each")
	_expect(pike == {"two_hands": PIKE}, "a two-handed item empties the two hand slots")
	_expect(catalog.wear(pike, "main_hand", STICK) == {"main_hand": STICK},
		"an item in one hand empties the two-handed slot")
	_expect(catalog.wear(one, "head", HELM) == {"main_hand": SWORD, "head": HELM},
		"a slot that clears nothing leaves each other slot")
	_expect(catalog.wear(one, "main_hand", "").is_empty(), "an empty key empties the slot")


func _an_outfit_keeps_what_the_catalog_has() -> void:
	var catalog := _catalog()
	var outfit := {"main_hand": SWORD, "head": "head", "off_hand": HELM, "arm": SWORD,
		"two_hands": "gone_item", TAIL: 7}

	_expect(catalog.valid_outfit(outfit) == {"main_hand": SWORD, "head": "head"},
		"an outfit keeps an item in its slot and the key of a slot: %s"
			% [catalog.valid_outfit(outfit)])
	_expect(FigureCatalog.new().valid_outfit(outfit).is_empty(),
		"a catalog that did not read keeps nothing")
	_expect(catalog.valid_outfit({"main_hand": SWORD, "off_hand": "off_hand", "two_hands": PIKE})
		== {"two_hands": PIKE},
		"an outfit holds no two items that clear each other: the later slot wins")
	_expect(catalog.valid_outfit({"main_hand": SWORD, "head": HELM})
		== {"main_hand": SWORD, "head": HELM}, "slots that clear nothing both hold")


## The item catalog of the repository. This case writes nothing.
func _the_repository_catalog_reads() -> void:
	var catalog := FigureCatalog.read_file()

	_expect(catalog.error.is_empty(), "the item catalog of the repository reads: "
		+ catalog.error)
	_expect(not catalog.items().is_empty() and not catalog.slot_keys().is_empty(),
		"the item catalog has slots and items")

	for row: Dictionary in catalog.items():
		_expect(catalog.has_slot(row["slot"]),
			"the item %s is in a slot of the catalog" % row["key"])

	# A slot name that the workbench types and that the server does not have
	# is a shape that nothing draws.
	for table: Dictionary in [FigureEdits.SLOTS, FigureShapes.SLOTS,
			FigureShapes.SLOT_HIDES, FigureShapes.SLOT_COLORS]:
		for slot: String in table:
			_expect(catalog.has_slot(slot), "%s is a slot of the item catalog" % slot)


## The proof of Phase W3: each item of the catalog draws on the figure. An
## item with a served model of the repository holds that model
## (10/17/2026): its look names the model, or the served part draws it.
func _each_item_of_the_repository_draws() -> void:
	var catalog := FigureCatalog.read_file()
	var store := FigureStore.new(FigureStore.repo_directory())
	var models := FigureModels.from_directory(FigureStore.repo_models_directory())

	store.load_all()

	for body_key: String in store.keys_of(FigureStore.KIND_RIG):
		var rig: FigureRig = store.rigs[body_key]
		var figure := FigureBuilder.build(rig, [])

		for slot: String in catalog.slot_keys():
			_expect(not FigureEdits.slot_shape(rig, slot).parts().is_empty(),
				"%s has a bone for the slot shape of %s" % [body_key, slot])

		for row: Dictionary in catalog.items():
			var worn := {row["slot"]: row["key"]}

			FigureBuilder.refresh(figure, rig,
				FigureOutfit.looks_for(rig, worn, store.looks, catalog.families(), {}, models),
				models)
			_expect(_worn_parts(figure, body_key) > 0,
				"%s draws on %s" % [row["key"], body_key])

			if models.has(row["key"]):
				_expect(_draws_model(figure, row["key"]),
					"%s holds its served model on %s" % [row["key"], body_key])

		figure.free()


## True when a part of a figure draws a model with the key `model_key`.
func _draws_model(figure: Node3D, model_key: String) -> bool:
	for node: Node3D in FigureBuilder.part_nodes(figure):
		var id := FigureBuilder.part_id(node)

		if node.get_meta(FigureBuilder.MODEL_META, false) \
				and (id[0] == model_key or id[1] == FigureLook.SERVED_PART):
			return true

	return false


## The served models of the test, one for each key of `keys`. Each one is
## a long box on the hand bone, ten units long and away from the origin, as
## a download is.
func _served_models(rig: FigureRig, keys: Array) -> FigureModels:
	var models := FigureModels.new()
	var download := FigureLook.from_data({"format": FigureLook.FORMAT, "key": "download",
		"parts": [{"name": "blade", "bone": rig.slots()["main_hand"],
			"position": [3.0, 2.0, 0.0],
			"shapes": [{"shape": FamilyShapes.SHAPE_BOX, "size": [1.0, 10.0, 0.5]}]}]})
	var body := FigureReference.buffer_of(rig, [download])

	for key: String in keys:
		_expect(models.put_buffer(key, body), "the served model of %s reads" % key)

	return models


## The place that a served model takes in the box of `stand_in`, on the
## bone of one slot.
func _box_place(rig: FigureRig, stand_in: FigureLook) -> Transform3D:
	var picture := FigureBuilder.build_item(rig, stand_in)
	var box := ModelLoader.bounds_of(picture)
	var longest := maxf(box.size.x, maxf(box.size.y, box.size.z))

	picture.free()

	return Transform3D(Basis.from_scale(Vector3.ONE * longest), box.get_center())


## True when two places differ by less than the rounding of a file.
func _near(first: Transform3D, second: Transform3D) -> bool:
	if first.origin.distance_to(second.origin) > PLACE_TOLERANCE:
		return false

	for axis in 3:
		if first.basis[axis].distance_to(second.basis[axis]) > PLACE_TOLERANCE:
			return false

	return true


func _a_served_model_wins() -> void:
	var rig := _rig()
	var looks := _looks(rig)
	var models := _served_models(rig, [SWORD, STICK, TAIL_RING])
	var hand: String = rig.slots()["main_hand"]
	var drawn := FigureOutfit.look_of(rig, "main_hand", SWORD, looks, {}, models)
	var row: Dictionary = drawn.part(FigureLook.SERVED_PART)

	_expect(FigureOutfit.source_of(rig, "main_hand", SWORD, looks, models)
		== FigureOutfit.SOURCE_MODEL and drawn.parts().size() == 1
		and row.get("model") == SWORD and row.get("node") == FigureModels.WHOLE_MODEL
		and row.get("bone") == hand,
		"a served model in hand wins over the worn look, as one part on the bone of the slot")
	_expect(FigureOutfit.source_of(rig, "main_hand", SWORD, looks) == FigureOutfit.SOURCE_LOOK
		and FigureOutfit.source_of(rig, "main_hand", HELM, looks, models)
			== FigureOutfit.SOURCE_LOOK,
		"with no models, or with no model of the key, the worn look draws")
	_expect(FigureOutfit.source_of(rig, TAIL, TAIL_RING, looks, models)
		== FigureOutfit.SOURCE_NOTHING, "a served model with no bone to hold it draws nothing")

	var named: Dictionary = looks[SWORD].data.duplicate(true)

	named["parts"][0]["model"] = SWORD
	named["parts"][0]["node"] = "blade"
	looks[SWORD] = FigureLook.from_data(named)
	_expect(FigureOutfit.source_of(rig, "main_hand", SWORD, looks, models)
		== FigureOutfit.SOURCE_LOOK, "a look that names the model draws as it is")

	var worn := FigureOutfit.looks_for(rig, {"main_hand": STICK}, looks, {}, {}, models)
	var figure := FigureBuilder.build(rig, worn, models)
	var node := FigureBuilder.part_node(figure, STICK, FigureLook.SERVED_PART)
	var instance: MeshInstance3D = null if node == null else node.get_child(0) as MeshInstance3D
	var box := AABB() if instance == null else instance.mesh.get_aabb()

	_expect(_keys(worn) == [rig.key(), STICK] and node != null
		and node.get_child_count() == 1 and FigureBuilder.part_nodes(figure).size()
			== looks[rig.key()].parts().size() + 1,
		"the figure draws the served model as one part, and no part of the stand-in")
	_expect(is_equal_approx(maxf(box.size.x, maxf(box.size.y, box.size.z)), FigureModels.UNIT)
		and box.get_center().length() < PLACE_TOLERANCE,
		"the served part draws the whole model in the unit box: %s" % [box])
	figure.free()


func _a_served_model_takes_its_place() -> void:
	var rig := _rig()
	var looks := _looks(rig)
	var models := _served_models(rig, [SWORD, STICK])
	var hand: String = rig.slots()["main_hand"]
	var sword_row := FigureOutfit.look_of(rig, "main_hand", SWORD, looks, {}, models) \
		.part(FigureLook.SERVED_PART)
	var stick_row := FigureOutfit.look_of(rig, "main_hand", STICK, looks, {}, models) \
		.part(FigureLook.SERVED_PART)

	_expect(_near(FigureLook.part_transform(sword_row), _box_place(rig, looks[SWORD])),
		"a served model takes the box of the worn look")
	_expect(_near(FigureLook.part_transform(stick_row), _box_place(rig, looks["main_hand"])),
		"an item with no worn look takes the box of the slot shape")

	var placed := Transform3D(Basis.from_scale(Vector3.ONE * 0.5), Vector3(0.0, 0.2, 0.0))
	var data := {"format": FigureLook.FORMAT, "key": STICK, "hides": ["hands"],
		"colors": {"metal": "gold"}}

	FigureLookEdits.set_served_place(data, hand, placed)
	looks[STICK] = FigureLook.from_data(data)

	var drawn := FigureOutfit.look_of(rig, "main_hand", STICK, looks, {}, models)

	_expect(_near(FigureLook.part_transform(drawn.part(FigureLook.SERVED_PART)), placed),
		"a served row gives the model its place")
	_expect(drawn.hides() == ["hands"] and drawn.colors().get("metal") == "gold",
		"the served part takes the hide list and the colors of the look")
	_expect(FigureOutfit.source_of(rig, "main_hand", STICK, looks)
		== FigureOutfit.SOURCE_SLOT_SHAPE,
		"a look with only a served row gives the slot shape as the stand-in")

	data["served"]["bone"] = "no_such_bone"
	looks[STICK] = FigureLook.from_data(data)
	drawn = FigureOutfit.look_of(rig, "main_hand", STICK, looks, {}, models)
	_expect(drawn.part(FigureLook.SERVED_PART)["bone"] == hand
		and _near(FigureLook.part_transform(drawn.part(FigureLook.SERVED_PART)),
			_box_place(rig, looks["main_hand"])),
		"a served row on a bone that the rig does not have gives the first place")
	_expect(FigureLookEdits.clear_served_place(data).is_empty() and not data.has("served")
		and not FigureLookEdits.clear_served_place(data).is_empty(),
		"the served row goes, and a second clear gives a reason")


## The count of the part nodes of a figure that are not of its body.
func _worn_parts(figure: Node3D, body_key: String) -> int:
	var count := 0

	for node: Node3D in FigureBuilder.part_nodes(figure):
		if FigureBuilder.part_id(node)[0] != body_key:
			count += 1

	return count
