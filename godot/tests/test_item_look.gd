extends Node
## Tests for the picture of an item in a cell: the worn look of the gear
## editor, alone (10/17/2026). [method FigureBuilder.build_item],
## [method FigureLibrary.build_item], and the first choice of [ItemStage].
##
##     godot --headless --path godot res://tests/test_item_look.tscn
##
## Needs nothing running and no editor. It reads the served `figure.json` of
## the repository and writes no file. The cases:
##
## 1. A look on one bone stands in the space of that bone. Each part has its
##    place on the bone.
## 2. A look on several bones keeps the rest places of its bones.
## 3. The picture of each item look of the served set has each part of its
##    look, and it fills the unit box of the mesh ladder.
## 4. A tier draws the parts of its base.
## 5. No figure set, no look of the key, and a tier with no base each give
##    no picture.
## 6. The stage draws the served model of the key first, then the worn look,
##    then the rest of the mesh ladder.
## 7. A bag that the figure set reaches after its first draw draws the look.
## 8. The ground ([EntityPool]) uses the order of the stage. The look of a
##    chunk object still picks the variant of the served model.
## 9. Each item look on the ground rests on its tile.
## 10. Two items of one look on the ground share no material, also with a
##     model part. The hit flash of one leaves the other.
## 11. The ground follows its facts: the figure set, the model of a part,
##     and the served model of the key.
## 12. Each item fills its cell at the widest turn of its spin, and no turn
##     draws past the edge of the cell: a worn look, a served model, and a
##     family shape.

const _Const := preload("res://autoload/blackout_constants.gd")

const TOLERANCE := 0.001

const NO_SUCH_ITEM := "no_such_item"

const BROKEN_TIER := "broken_tier"

const GONE_BASE := "gone_base"

## The key of a look that a case of the ground makes, with a model part.
const MODEL_LOOK := "model_look"

## The one tile of the cases of the ground, and where it stands. Above
## zero, so a lift that forgets the tile shows.
const GROUND_TILE := [7.0, 1.0, "oasis"]
const TILE_ORIGIN := Vector3(0.0, 0.4, 0.0)

## The id of the first row of a case of the ground.
const FIRST_ROW := 501

## The path of the model tree below its directory: none, because the
## directory is the model tree itself. The figure workbench does the same.
const MODEL_TREE_ROOT := "/"

## How many served models the cell case draws. A served model has some
## thousands of triangles, so two keep the case short.
const SERVED_CELL_CASES := 2

## The turns of the spin that the cell case measures, over half a turn. The
## second half of a turn mirrors the first.
const SPIN_SAMPLES := 24

var _failures := 0
var _text := ""


func _ready() -> void:
	_text = FileAccess.get_file_as_string(
		FigureStore.repo_models_directory().path_join(FigureSet.FILE_NAME))

	_a_look_on_one_bone_stands_in_its_space()
	_a_look_on_several_bones_keeps_the_rest()
	_each_item_look_fills_the_unit_box()
	_a_tier_draws_the_parts_of_its_base()
	_no_look_gives_no_picture()
	_the_stage_draws_the_served_model_first()
	_a_bag_draws_the_look_when_the_set_arrives()
	_the_ground_draws_the_served_model_first()
	_each_item_look_rests_on_its_tile()
	_items_on_the_ground_own_their_materials()
	_the_ground_follows_its_facts()
	_each_item_fills_its_cell()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: item_look")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


## A library with the served figure set in hand.
func _library() -> FigureLibrary:
	var library := FigureLibrary.new()

	library.take_text(_text)

	return library


## The rig that an item stands on: the first rig, by key.
func _item_rig(library: FigureLibrary) -> FigureRig:
	var keys := library.figure_set.rigs.keys()

	keys.sort()

	return library.figure_set.rigs[keys[0]]


## The keys of each look of the served set that dresses an item: neither a
## rig, nor a slot, nor a kit part, and with parts after its bases.
func _item_keys(library: FigureLibrary) -> PackedStringArray:
	var looks: Dictionary = library.figure_set.looks
	var rig := _item_rig(library)
	var found := PackedStringArray()
	var keys := looks.keys()

	keys.sort()

	for key: String in keys:
		var look: FigureLook = looks[key]

		if library.figure_set.rigs.has(key) or rig.slots().has(key) \
				or not look.kit().is_empty():
			continue

		if not look.resolved(looks).parts().is_empty():
			found.append(key)

	return found


## The bones of the parts of one look.
func _bones_of(look: FigureLook) -> Dictionary:
	var bones := {}

	for row: Dictionary in look.parts():
		bones[row["bone"]] = true

	return bones


## The first item look whose parts sit on one bone (`single` true) or on
## several bones (`single` false), or null.
func _look_with_bones(library: FigureLibrary, single: bool) -> FigureLook:
	var looks: Dictionary = library.figure_set.looks

	for key: String in _item_keys(library):
		var look: FigureLook = looks[key].resolved(looks)

		if (_bones_of(look).size() == 1) == single:
			return look

	return null


## The part node of one part of a built item, or null.
func _part_of(item: Node3D, look: FigureLook, part_name: String) -> Node3D:
	for child: Node in item.get_children():
		if FigureBuilder.part_id(child) == [look.key(), part_name]:
			return child

	return null


func _a_look_on_one_bone_stands_in_its_space() -> void:
	var library := _library()
	var rig := _item_rig(library)
	var look := _look_with_bones(library, true)

	_expect(look != null, "the served set has an item look on one bone")

	if look == null:
		library.free()
		return

	var item := FigureBuilder.build_item(rig, look, library.models, library.figure_set.palette)

	for row: Dictionary in look.parts():
		var part := _part_of(item, look, row["name"])

		_expect(part != null, "%s has its part %s" % [look.key(), row["name"]])
		_expect(part != null and part.transform.is_equal_approx(
			look.place_of(row["name"], rig.key())),
			"the part %s of %s has its place on the bone" % [row["name"], look.key()])

	item.free()
	library.free()


func _a_look_on_several_bones_keeps_the_rest() -> void:
	var library := _library()
	var rig := _item_rig(library)
	var look := _look_with_bones(library, false)

	_expect(look != null, "the served set has an item look on several bones")

	if look == null:
		library.free()
		return

	var item := FigureBuilder.build_item(rig, look, library.models, library.figure_set.palette)

	for row: Dictionary in look.parts():
		var part := _part_of(item, look, row["name"])
		var wanted := rig.global_rest_of(row["bone"]) * look.place_of(row["name"], rig.key())

		_expect(part != null and part.transform.is_equal_approx(wanted),
			"the part %s of %s stands where the rest puts it" % [row["name"], look.key()])

	item.free()
	library.free()


func _each_item_look_fills_the_unit_box() -> void:
	var library := _library()
	var looks: Dictionary = library.figure_set.looks
	var keys := _item_keys(library)

	_expect(not keys.is_empty(), "the served set has the look of an item")

	for key: String in keys:
		var holder := library.build_item(key)

		_expect(holder != null, "%s has a picture" % key)

		if holder == null:
			continue

		var item := holder.get_child(0) as Node3D
		var bounds := ModelLoader.bounds_of(holder)
		var longest := maxf(bounds.size.x, maxf(bounds.size.y, bounds.size.z))

		_expect(item.get_child_count() == looks[key].resolved(looks).parts().size(),
			"the picture of %s has each part of its look" % key)
		_expect(absf(longest - ModelLoader.UNIT) < TOLERANCE,
			"the picture of %s is one unit on its longest side" % key)
		_expect(bounds.get_center().length() < TOLERANCE,
			"the picture of %s is centered" % key)
		_expect(holder.transform.is_equal_approx(Transform3D.IDENTITY),
			"the holder of %s has no place of its own" % key)
		holder.free()

	library.free()


func _a_tier_draws_the_parts_of_its_base() -> void:
	var library := _library()
	var looks: Dictionary = library.figure_set.looks
	var tier := ""

	for key: String in _item_keys(library):
		if not looks[key].base().is_empty():
			tier = key
			break

	_expect(not tier.is_empty(), "the served set has a tier of an item")

	if tier.is_empty():
		library.free()
		return

	var holder := library.build_item(tier)
	var root: FigureLook = looks[tier].base_chain(looks)[-1]

	_expect(holder != null and holder.get_child(0).get_child_count() == root.parts().size(),
		"the tier %s draws each part of its base" % tier)

	if holder != null:
		holder.free()

	library.free()


func _no_look_gives_no_picture() -> void:
	var empty := FigureLibrary.new()
	var library := _library()
	var keys := _item_keys(library)

	_expect(keys.is_empty() or empty.build_item(keys[0]) == null,
		"no figure set gives no picture")
	_expect(library.build_item(NO_SUCH_ITEM) == null,
		"an item with no look gives no picture")

	library.figure_set.looks[BROKEN_TIER] = FigureLook.from_data({
		"format": FigureLook.FORMAT, "key": BROKEN_TIER, "base": GONE_BASE})
	_expect(library.build_item(BROKEN_TIER) == null,
		"a tier with no base gives no picture")
	empty.free()
	library.free()


## A mesh ladder with an empty registry: each item draws its family shape,
## and nothing goes on the network.
func _resolver() -> MeshResolver:
	var resolver := MeshResolver.new(ModelRegistry.new(), "")

	add_child(resolver)

	return resolver


## A resolver that reads the served model tree of the repository from disk.
## The caller frees its models, then the resolver.
func _served_resolver() -> MeshResolver:
	return MeshResolver.from_directory(FigureStore.repo_models_directory(), MODEL_TREE_ROOT)


## The first key of the manifest whose model reads from disk, or "".
func _served_key(resolver: MeshResolver) -> String:
	var keys := _served_keys(resolver, 1)

	return keys[0] if not keys.is_empty() else ""


## The first `count` keys of the manifest whose models read from disk, by
## key. Fewer when the tree has fewer.
func _served_keys(resolver: MeshResolver, count: int) -> PackedStringArray:
	var keys := resolver._registry.known_keys()
	var found := PackedStringArray()

	keys.sort()

	for key: String in keys:
		var model := resolver.resolve_own_art(key)

		if model != null:
			model.free()
			found.append(key)

		if found.size() == count:
			break

	return found


## Give `key` a worn look: a copy of the look of `item_key` with that key.
func _give_look(library: FigureLibrary, key: String, item_key: String) -> void:
	var looks: Dictionary = library.figure_set.looks
	var data: Dictionary = looks[item_key].resolved(looks).data.duplicate(true)

	data["key"] = key
	looks[key] = FigureLook.from_data(data)


## The served model of the key, the worn look, and then the rest of the mesh
## ladder. The key with a model gets a look of its own here, so the case
## does not depend on which items have both today.
func _the_stage_draws_the_served_model_first() -> void:
	var library := _library()
	var resolver := _served_resolver()
	var model_key := _served_key(resolver)
	var look_key := ""

	for key: String in _item_keys(library):
		if not resolver.may_have_art(key):
			look_key = key
			break

	_expect(not model_key.is_empty(), "the served tree has a model that reads")
	_expect(not look_key.is_empty(), "the served set has an item look with no model")

	if model_key.is_empty() or look_key.is_empty():
		resolver.free_models()
		resolver.free()
		library.free()
		return

	_give_look(library, model_key, look_key)
	_expect(library.build_item(model_key) != null, "%s has a worn look also" % model_key)
	_check_stage_order(library, resolver, model_key, look_key)
	resolver.free_models()
	resolver.free()
	library.free()


func _check_stage_order(library: FigureLibrary, resolver: MeshResolver,
		model_key: String, look_key: String) -> void:
	var stage := ItemStage.new()

	add_child(stage)
	stage.reserve(4)
	stage.place(0, model_key, _Const.FAMILY_GENERIC, resolver, library)
	stage.place(1, look_key, _Const.FAMILY_GENERIC, resolver, library)
	stage.place(2, NO_SUCH_ITEM, _Const.FAMILY_GENERIC, resolver, library)
	stage.place(3, look_key, _Const.FAMILY_GENERIC, resolver)

	_expect(_drawn(stage, 0) != null
		and _drawn(stage, 0).has_meta(ModelLoader.PRESENTATION_SCALE_META),
		"the served model of %s wins over its worn look" % model_key)
	_expect(_drawn_name(stage, 1) == FigureLibrary.ITEM_HOLDER_NAME,
		"an item with a worn look and no model draws its look")
	_expect(_is_ladder(_drawn(stage, 2)), "an item with no look draws through the mesh ladder")
	_expect(_is_ladder(_drawn(stage, 3)), "a stage with no library draws through the mesh ladder")
	remove_child(stage)
	stage.free()


## The stage fits each item on its outline over the spin (10/21/2026). The
## case reads each triangle of each mesh, not a hull, and it turns the item
## as the stage does. Thus, it does not repeat the rule that it tests.
func _each_item_fills_its_cell() -> void:
	var library := _library()
	var served := _served_resolver()
	var ladder := _resolver()
	var keys := _item_keys(library)
	var stage := ItemStage.new()
	var half := ItemStage.CELL_WORLD * 0.5
	# The widest turn can fall between two samples.
	var slack := cos(PI / SPIN_SAMPLES * 0.5)
	var fill := ItemStage.ITEM_FILL * ItemStage.CELL_WORLD * slack

	keys.append_array(_served_keys(served, SERVED_CELL_CASES))
	add_child(stage)
	stage.reserve(keys.size() + 1)

	for index: int in keys.size():
		stage.place(index, keys[index], _Const.FAMILY_GENERIC, served, library)

	# The ladder has no model and no look, so it draws a family shape.
	stage.place(keys.size(), NO_SUCH_ITEM, _Const.FAMILY_GENERIC, ladder)
	keys.append(NO_SUCH_ITEM)

	for index: int in keys.size():
		var node := _drawn(stage, index)

		_expect(node != null, "the stage draws %s" % keys[index])

		if node == null:
			continue

		var box := _swept_cell_box(node, stage.cell_centre(index))
		var reach := maxf(box.end.x, maxf(-box.position.y, box.end.y))

		_expect(reach <= half + TOLERANCE,
			"no turn of %s draws past its cell" % keys[index])
		_expect(maxf(box.size.x, box.size.y) >= fill - TOLERANCE,
			"%s fills its cell at its widest turn" % keys[index])

	remove_child(stage)
	stage.free()
	served.free_models()
	served.free()
	ladder.free()
	library.free()


## The outline that one placed item sweeps over half a turn, from the
## centre of its cell. The item turns as `_process` of the stage turns it.
func _swept_cell_box(node: Node3D, centre: Vector3) -> Rect2:
	var points := PackedVector3Array()
	var reach := 0.0
	var low := INF
	var high := -INF

	for part: Array in ModelLoader.mesh_parts(node):
		var mesh: Mesh = part[0]
		var to_node: Transform3D = part[1]

		for point: Vector3 in mesh.get_faces():
			points.append(to_node * point)

	for _step in SPIN_SAMPLES:
		node.rotate_y(PI / SPIN_SAMPLES)

		for point: Vector3 in points:
			var seen := node.transform * point - centre

			reach = maxf(reach, absf(seen.x))
			low = minf(low, seen.y)
			high = maxf(high, seen.y)

	return Rect2(-reach, low, reach * 2.0, high - low)


## True for a node of the mesh ladder that is no served model and no
## picture of a worn look: a family shape.
func _is_ladder(node: Node3D) -> bool:
	return node != null and str(node.name) != FigureLibrary.ITEM_HOLDER_NAME \
		and not node.has_meta(ModelLoader.PRESENTATION_SCALE_META) \
		and not _is_worn_look(node)


## True for a picture of [method FigureLibrary.build_item]. The case reads
## the child, because a parent with two pictures gives one another name.
func _is_worn_look(node: Node3D) -> bool:
	return node != null and node.get_child_count() > 0 \
		and str(node.get_child(0).name) == FigureBuilder.ITEM_NAME


## True for a served model of the mesh ladder.
func _is_served(node: Node3D) -> bool:
	return node != null and node.has_meta(ModelLoader.PRESENTATION_SCALE_META)


## The node that the stage draws at one index, or null.
func _drawn(stage: ItemStage, index: int) -> Node3D:
	return stage._items.get(index)


## The name of the node that the stage draws at one index, or "".
func _drawn_name(stage: ItemStage, index: int) -> String:
	var node := _drawn(stage, index)

	return "" if node == null else str(node.name)


## The library of the case gets the figure set only after the first draw.
## The item key comes from a library of its own.
func _a_bag_draws_the_look_when_the_set_arrives() -> void:
	var served := _library()
	var keys := _item_keys(served)

	served.free()
	_expect(not keys.is_empty(), "the served set has the look of an item to carry")

	if keys.is_empty():
		return

	var library := FigureLibrary.new()
	var resolver := _resolver()
	var state := InventoryState.new()
	var view := InventoryView.new()

	state.ingest(_Const.CH_CHAR_ITEMS, _bag_with(keys[0]))
	add_child(view)
	add_child(library)
	view.bind(state, resolver)
	view.bind_figures(library)
	_expect(_drawn_name(view._stage, 0) != FigureLibrary.ITEM_HOLDER_NAME,
		"before the figure set, the bag draws through the mesh ladder")

	library.take_text(_text)
	_expect(_drawn_name(view._stage, 0) == FigureLibrary.ITEM_HOLDER_NAME,
		"the arrival of the figure set draws the look of %s" % keys[0])
	view.queue_free()
	library.queue_free()
	resolver.queue_free()


## A bag with one item in its first slot, in the shape of
## `serialize_inventory`.
func _bag_with(asset_key: String) -> Dictionary:
	return {
		"slots_total": 4.0, "slots_used": 1.0,
		"items": [{"id": 201.0, "slot": 0.0, "name": asset_key, "asset": asset_key,
			"family": _Const.FAMILY_GENERIC, "quantity": 1.0, "stackable": false,
			"equip_slot": "main_hand", "actions": []}],
		"equipped": [],
		"equip_slots": [],
	}


# ─── The ground ─────────────────────────────────────────────────────────────

## The order of the stage, on the ground. The key with a model gets a look
## of its own, as in [method _the_stage_draws_the_served_model_first]. The
## last row has the look of a chunk object that picks a variant. Its base
## key has a worn look, and the variant still wins.
func _the_ground_draws_the_served_model_first() -> void:
	var library := _library()
	var resolver := _served_resolver()
	var served := _served_keys(resolver, 2)
	var look_key := _look_with_no_model(library, resolver)

	_expect(served.size() == 2, "the served tree has two models that read")
	_expect(not look_key.is_empty(), "the served set has an item look with no model")

	if served.size() < 2 or look_key.is_empty():
		_free_served(resolver)
		library.free()
		return

	var model_key := served[0]
	var variant_key := served[1]

	_give_look(library, model_key, look_key)
	resolver.ingest_variants({model_key: [variant_key]})

	var pool := _ground_pool(resolver, library)

	pool.replace_all([_ground_row(FIRST_ROW, model_key),
		_ground_row(FIRST_ROW + 1, look_key), _ground_row(FIRST_ROW + 2, NO_SUCH_ITEM),
		_ground_row(FIRST_ROW + 3, model_key, {_Const.LOOK_VARIANT_KEY: variant_key})])
	_expect(_is_served(pool.node_for(FIRST_ROW)),
		"on the ground, the served model of %s wins over its worn look" % model_key)
	_expect(_is_worn_look(pool.node_for(FIRST_ROW + 1)),
		"on the ground, an item with a worn look and no model draws its look")
	_expect(_is_ladder(pool.node_for(FIRST_ROW + 2)),
		"on the ground, an item with no look draws through the mesh ladder")
	_check_variant(pool.node_for(FIRST_ROW + 3), resolver, model_key, variant_key)
	_free_pool(pool)
	_free_served(resolver)
	library.free()


## The row with the look draws the mesh of the variant, not of the base.
func _check_variant(node: Node3D, resolver: MeshResolver, model_key: String,
		variant_key: String) -> void:
	var base := resolver.resolve_own_art(model_key)
	var variant := resolver.resolve_own_art(variant_key)

	_expect(_first_mesh(base) != _first_mesh(variant),
		"%s and %s have two meshes" % [model_key, variant_key])
	_expect(_is_served(node) and _first_mesh(node) == _first_mesh(variant),
		"the look of a chunk object on the ground still picks the variant %s" % variant_key)
	base.free()
	variant.free()


## The lowest point of each picture is on the tile: no picture floats, and
## no picture goes into the ground. A mesh ladder with no model draws each
## look, the served swords also.
func _each_item_look_rests_on_its_tile() -> void:
	var library := _library()
	var resolver := _resolver()
	var pool := _ground_pool(resolver, library)
	var keys := _item_keys(library)

	_expect(not keys.is_empty(), "the served set has the look of an item to drop")

	for key: String in keys:
		pool.replace_all([_ground_row(FIRST_ROW, key)])

		var node := pool.node_for(FIRST_ROW)

		_expect(_is_worn_look(node), "%s on the ground draws its look" % key)
		_expect(node != null and absf(_lowest_point(node) - TILE_ORIGIN.y) < TOLERANCE,
			"%s rests on its tile" % key)

	_free_pool(pool)
	resolver.queue_free()
	library.free()


## The look has a model part. Each surface of a model shares the material of
## its model, so a picture with no materials of its own would flash with
## each other picture of the look.
func _items_on_the_ground_own_their_materials() -> void:
	var library := _library()
	var resolver := _resolver()
	var keys := _item_keys(library)
	var models := FigureModels.from_directory(FigureStore.repo_models_directory())
	var part_model := _model_with_a_node(models)

	_expect(not keys.is_empty() and part_model.size() == 2,
		"the served set has an item look, and the served tree has a model node")

	if keys.is_empty() or part_model.size() < 2:
		resolver.queue_free()
		library.free()
		return

	_give_model_look(library, keys[0], part_model)
	library.models = models

	var pool := _ground_pool(resolver, library)

	pool.replace_all([_ground_row(FIRST_ROW, MODEL_LOOK),
		_ground_row(FIRST_ROW + 1, MODEL_LOOK)])
	_check_own_materials(pool, _part_mesh(models, part_model), part_model[1])
	_free_pool(pool)
	resolver.queue_free()
	library.free()


func _check_own_materials(pool: EntityPool, part_mesh: Mesh, node_name: String) -> void:
	var first := pool.node_for(FIRST_ROW)
	var mine := EntityPool._materials_of(first)
	var theirs := EntityPool._materials_of(pool.node_for(FIRST_ROW + 1))
	var before: Array = theirs.map(func(material: StandardMaterial3D) -> Color:
		return material.albedo_color)

	_expect(_mesh_count_of(first, part_mesh) > 0,
		"the picture draws the model part %s" % node_name)
	_expect(not mine.is_empty() and mine.size() == theirs.size(),
		"the pool reaches each material of the two pictures")
	_expect(mine.all(func(material: StandardMaterial3D) -> bool:
		return MeshGlow.is_ready(material) and not theirs.has(material)),
		"each material of a picture is its own, and ready for a glow")
	pool.flash(FIRST_ROW)
	_expect(mine.all(func(material: StandardMaterial3D) -> bool:
		return material.albedo_color == Color.WHITE), "the hit flash reaches each surface")
	_expect(theirs.map(func(material: StandardMaterial3D) -> Color:
		return material.albedo_color) == before, "and it leaves the other picture")


## The mesh of the model part. Each instance of one node shares it.
func _part_mesh(models: FigureModels, part_model: Array) -> Mesh:
	var instance := models.instance_of(part_model[0], part_model[1])
	var mesh := instance.mesh

	instance.free()

	return mesh


## The figure set arrives, then the model of a part, then the served model
## of the key. Each one draws the item again. A row with no look keeps its
## node across each figure change, and so does a served model.
func _the_ground_follows_its_facts() -> void:
	var served := _library()
	var keys := _item_keys(served)

	served.free()

	var library := FigureLibrary.new()
	var resolver := _resolver()
	var pool := _ground_pool(resolver, library)

	_expect(not keys.is_empty(), "the served set has the look of an item to drop")

	if keys.is_empty():
		_free_pool(pool)
		resolver.queue_free()
		library.free()
		return

	pool.replace_all([_ground_row(FIRST_ROW, keys[0]), _ground_row(FIRST_ROW + 1, NO_SUCH_ITEM)])

	var bystander := pool.node_for(FIRST_ROW + 1)

	_expect(_is_ladder(pool.node_for(FIRST_ROW)),
		"before the figure set, an item on the ground draws through the mesh ladder")
	library.take_text(_text)
	_expect(_is_worn_look(pool.node_for(FIRST_ROW)),
		"the arrival of the figure set draws the look of %s on the ground" % keys[0])

	var drawn := pool.node_for(FIRST_ROW)

	library.changed.emit()
	_expect(pool.node_for(FIRST_ROW) != drawn and _is_worn_look(pool.node_for(FIRST_ROW)),
		"the model of a part draws the look on the ground again")
	_expect(pool.node_for(FIRST_ROW + 1) == bystander,
		"a row with no look keeps its node across each figure change")
	_the_served_model_arrives(pool, resolver, library, keys[0])
	_free_pool(pool)
	resolver.queue_free()
	library.free()


## The file of the served model lands for the key: the pool draws it, and
## a figure change after keeps it. The loader gets a model of the served
## tree as the prototype of the key, as a fetch gives it.
func _the_served_model_arrives(pool: EntityPool, resolver: MeshResolver,
		library: FigureLibrary, key: String) -> void:
	var served := _served_resolver()
	var model_key := _served_key(served)

	_expect(not model_key.is_empty(), "the served tree has a model that reads")

	if model_key.is_empty():
		_free_served(served)
		return

	resolver._loader._prototypes[key] = served.resolve_own_art(model_key)
	resolver.refreshed.emit(key)
	_expect(_is_served(pool.node_for(FIRST_ROW)),
		"the served model of %s wins on the ground when its file arrives" % key)

	var drawn := pool.node_for(FIRST_ROW)

	library.changed.emit()
	_expect(pool.node_for(FIRST_ROW) == drawn, "a figure change keeps a served model")
	_free_served(served)


## A pool of the ground on one tile, with no walk. The rows draw from
## `resolver`, and from `library` when it is not null.
func _ground_pool(resolver: MeshResolver, library: FigureLibrary) -> EntityPool:
	var pool := EntityPool.new()

	add_child(pool)
	pool.bind(resolver, func(_coords: Array) -> Variant: return TILE_ORIGIN, 1.0)
	pool.set_animated(false)

	if library != null:
		pool.bind_figures(library)

	return pool


func _free_pool(pool: EntityPool) -> void:
	remove_child(pool)
	pool.free()


func _free_served(resolver: MeshResolver) -> void:
	resolver.free_models()
	resolver.free()


## One item on the ground, in the shape of `serialize_entity`.
func _ground_row(entity_id: int, asset_key: String, look: Dictionary = {}) -> Dictionary:
	var row := {"id": float(entity_id), "name": asset_key, "kind": "item",
		"asset": asset_key, "family": _Const.FAMILY_GENERIC, "interact": "",
		"coords": GROUND_TILE}

	if not look.is_empty():
		row[_Const.ENTITY_LOOK_KEY] = look

	return row


## The first item look whose key has no served model, or "".
func _look_with_no_model(library: FigureLibrary, resolver: MeshResolver) -> String:
	for key: String in _item_keys(library):
		if not resolver.may_have_art(key):
			return key

	return ""


## The first model of the served tree with a node that holds a mesh, as
## `[model key, node name]`, or an empty array.
func _model_with_a_node(models: FigureModels) -> Array:
	var text := FileAccess.get_file_as_string(
		FigureStore.repo_models_directory().path_join(FigureModels.MANIFEST_NAME))
	var manifest: Variant = JSON.parse_string(text)
	var keys: Array = manifest.keys() if manifest is Dictionary else []

	keys.sort()

	for key: String in keys:
		var names := models.node_names(key)

		if not names.is_empty():
			return [key, names[0]]

	return []


## Give [constant MODEL_LOOK] the look of `item_key`, with the model node of
## `part_model` on its first part.
func _give_model_look(library: FigureLibrary, item_key: String, part_model: Array) -> void:
	var looks: Dictionary = library.figure_set.looks
	var data: Dictionary = looks[item_key].resolved(looks).data.duplicate(true)

	data["key"] = MODEL_LOOK
	data["parts"][0]["model"] = part_model[0]
	data["parts"][0]["node"] = part_model[1]
	looks[MODEL_LOOK] = FigureLook.from_data(data)


## The first mesh under `root`, or null.
func _first_mesh(root: Node) -> Mesh:
	if root is MeshInstance3D and root.mesh != null:
		return root.mesh

	for child: Node in root.get_children():
		var found := _first_mesh(child)

		if found != null:
			return found

	return null


## How many mesh instances under `root` draw `mesh`.
func _mesh_count_of(root: Node, mesh: Mesh) -> int:
	var count := 1 if root is MeshInstance3D and root.mesh == mesh else 0

	for child: Node in root.get_children():
		count += _mesh_count_of(child, mesh)

	return count


## The lowest point of each mesh box under `node`, in world space. The node
## is in the tree, so each global transform holds.
func _lowest_point(node: Node3D) -> float:
	var lowest := INF
	var stack: Array[Node] = [node]

	while not stack.is_empty():
		var current: Node = stack.pop_back()
		var instance := current as MeshInstance3D

		if instance != null and instance.mesh != null:
			var box := instance.global_transform * instance.get_aabb()

			lowest = minf(lowest, box.position.y)

		stack.append_array(current.get_children())

	return lowest
