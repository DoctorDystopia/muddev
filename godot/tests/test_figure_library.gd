extends Node
## Tests for the figure of a player character in the game (DESIGN-0014
## section 20): [FigureLibrary], and the figure rows of [EntityPool].
##
##     godot --headless --path godot res://tests/test_figure_library.tscn
##
## Needs nothing running and no editor. It reads the served `figure.json` of
## the repository and writes no file. The cases:
##
## 1. A text that is no figure set changes nothing.
## 2. The served figure set reads, and the same text a second time builds no
##    figure again.
## 3. A figure stands on its feet, with the box of FIGURE_HEIGHT, and it has
##    each part of its body.
## 4. A body type with no rig gets the first rig, not a block.
## 5. The figure colors of a character color its skin.
## 6. Two figures share no material, so a hit flash lights one figure only.
## 7. A figure walks and idles with the clips of the stance table.
## 8. A pool row with a body type draws a figure. A row with none draws its
##    asset key. A new figure set draws the row again.
## 9. A change of the colors of a row is a change of its look.

const TOLERANCE := 0.001

const _Const := preload("res://autoload/blackout_constants.gd")

## A pool row of a player character, in the shape of `serialize_entity`.
const PLAYER_ID := 41.0
const OBJECT_ID := 42.0
const TILE := [3.0, 4.0, "oasis"]

var _failures := 0
var _text := ""


func _ready() -> void:
	_text = FileAccess.get_file_as_string(
		FigureStore.repo_models_directory().path_join(FigureSet.FILE_NAME))

	_a_bad_text_changes_nothing()
	_the_served_set_reads_one_time()
	_a_figure_stands_on_its_feet()
	_an_unknown_body_type_gets_the_first_rig()
	_the_figure_colors_color_the_skin()
	_two_figures_share_no_material()
	await _a_figure_walks_and_idles()
	_a_pool_row_with_a_body_type_is_a_figure()
	await _two_figures_in_one_parent_both_walk()
	_new_colors_are_a_new_look()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_library")
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


func _a_bad_text_changes_nothing() -> void:
	var library := FigureLibrary.new()
	var emitted := [0]

	library.changed.connect(func() -> void: emitted[0] += 1)

	_expect(not library.take_text("{\"format\": 1}"), "a set with no rig does not read")
	_expect(not library.has_set(), "a library with no set has none")
	_expect(library.build("body_1", {}) == null, "no set gives no figure")
	_expect(emitted[0] == 0, "a bad text emits nothing")
	library.free()


func _the_served_set_reads_one_time() -> void:
	var library := FigureLibrary.new()
	var emitted := [0]

	library.changed.connect(func() -> void: emitted[0] += 1)

	_expect(library.take_text(_text), "the served figure set reads")
	_expect(library.take_text(_text), "the same text reads again")
	_expect(emitted[0] == 1, "the same text emits one time, not two (%d)" % emitted[0])
	library.free()


func _a_figure_stands_on_its_feet() -> void:
	var library := _library()

	for body_type: String in library.figure_set.rigs:
		var holder := library.build(body_type, {})
		var figure := FigureLibrary.figure_of(holder)
		var box := ModelLoader.bounds_of(holder)
		var body: FigureLook = library.figure_set.looks.get(body_type)

		_expect(figure != null, "%s: the holder holds a figure" % body_type)
		_expect(absf(box.position.y) < TOLERANCE, "%s: the feet are at the origin" % body_type)
		_expect(box.size.y <= FigureLibrary.FIGURE_HEIGHT + TOLERANCE and box.size.y > 0.0,
			"%s: the figure is no taller than FIGURE_HEIGHT (%.3f)" % [body_type, box.size.y])
		_expect(body != null and FigureBuilder.part_nodes(figure).size() == body.parts().size(),
			"%s: the figure has each part of its body" % body_type)
		holder.free()

	library.free()


func _an_unknown_body_type_gets_the_first_rig() -> void:
	var library := _library()
	var holder := library.build("no_such_body_type", {})

	_expect(holder != null and FigureLibrary.figure_of(holder) != null,
		"a body type with no rig still draws a figure")

	if holder != null:
		holder.free()

	library.free()


## The first part of the body whose first shape has the role `role`, or {}.
func _part_with_role(look: FigureLook, role: String) -> Dictionary:
	for row: Dictionary in look.parts():
		var shapes: Array = row.get("shapes", [])

		if not shapes.is_empty() and shapes[0].get("color", "") == role:
			return row

	return {}


func _the_figure_colors_color_the_skin() -> void:
	var library := _library()
	var body_type: String = library.figure_set.rigs.keys()[0]
	var palette := library.figure_set.palette
	var row := _part_with_role(library.figure_set.looks[body_type], "skin")
	var colors := palette.color_names()
	var chosen := colors[colors.size() - 1]

	_expect(not row.is_empty(), "the body has a part with the skin role")

	if row.is_empty():
		library.free()
		return

	var holder := library.build(body_type, {"skin": chosen})
	var part := FigureBuilder.part_node(FigureLibrary.figure_of(holder), body_type, row["name"])
	var shape := part.get_child(0) as MeshInstance3D
	var albedo := (shape.material_override as StandardMaterial3D).albedo_color

	_expect(albedo.is_equal_approx(palette.color_of(chosen)),
		"the skin of the figure has the color %s" % chosen)
	holder.free()
	library.free()


func _materials_of(root: Node) -> Array:
	var found := []

	for child: Node in root.get_children():
		var instance := child as MeshInstance3D

		if instance != null:
			found.append(instance.material_override)

			for surface in instance.get_surface_override_material_count():
				found.append(instance.get_surface_override_material(surface))

		found.append_array(_materials_of(child))

	return found.filter(func(material: Variant) -> bool: return material != null)


func _two_figures_share_no_material() -> void:
	var library := _library()
	var body_type: String = library.figure_set.rigs.keys()[0]
	var first := library.build(body_type, {})
	var second := library.build(body_type, {})
	var seen := {}
	var shared := 0

	for material: Material in _materials_of(first):
		seen[material.get_instance_id()] = true

	for material: Material in _materials_of(second):
		if seen.has(material.get_instance_id()):
			shared += 1

	_expect(not seen.is_empty(), "a figure has materials")
	_expect(shared == 0, "two figures share no material (%d shared)" % shared)
	first.free()
	second.free()
	library.free()


func _a_figure_walks_and_idles() -> void:
	var library := _library()
	var body_type: String = library.figure_set.rigs.keys()[0]
	var holder := library.build(body_type, {})
	var figure := FigureLibrary.figure_of(holder)
	var stances := FigureStances.read_file()

	add_child(holder)
	await get_tree().process_frame

	var player := FigureClips.player_of(figure)

	_expect(player.current_animation == stances.clip_for("", FigureStances.ACTION_IDLE),
		"a new figure idles")

	FigureLibrary.play(holder, FigureStances.ACTION_WALK)
	_expect(player.current_animation == stances.clip_for("", FigureStances.ACTION_WALK),
		"a figure that travels walks")

	FigureLibrary.play(holder, FigureStances.ACTION_WALK)
	_expect(player.is_playing(), "a second ask for the same action goes on with the clip")

	FigureLibrary.play(holder, FigureStances.ACTION_IDLE)
	_expect(player.current_animation == stances.clip_for("", FigureStances.ACTION_IDLE),
		"a figure on its tile idles again")

	holder.queue_free()
	library.free()


func _player_row() -> Dictionary:
	return {"id": PLAYER_ID, "name": "Tester", "kind": "character",
		"asset": _Const.ASSET_KEY_CHARACTER, "family": "character",
		"interact": "", "coords": TILE,
		_Const.ENTITY_BODY_TYPE_KEY: "body_1"}


func _object_row() -> Dictionary:
	return {"id": OBJECT_ID, "name": "a rock", "kind": "item", "asset": "generic",
		"family": "generic", "interact": "", "coords": TILE}


func _a_pool_row_with_a_body_type_is_a_figure() -> void:
	var resolver := MeshResolver.new(ModelRegistry.new(), "")
	var pool := EntityPool.new()
	var library := FigureLibrary.new()

	add_child(resolver)
	add_child(pool)
	pool.bind(resolver, func(_coords: Array) -> Variant: return Vector3.ZERO, 1.0)
	pool.set_animated(false)
	pool.bind_figures(library)
	pool.replace_all([_player_row(), _object_row()])

	_expect(FigureLibrary.figure_of(pool.node_for(int(PLAYER_ID))) == null,
		"before the figure set, the player draws through the mesh ladder")

	library.take_text(_text)

	_expect(FigureLibrary.figure_of(pool.node_for(int(PLAYER_ID))) != null,
		"the figure set draws the player as a figure")
	_expect(FigureLibrary.figure_of(pool.node_for(int(OBJECT_ID))) == null,
		"a row with no body type draws its asset key")

	pool.queue_free()
	resolver.queue_free()
	library.free()


## The pool holds each figure under one parent, so Godot gives the second
## holder another name. A figure must still find its clip.
func _two_figures_in_one_parent_both_walk() -> void:
	var library := _library()
	var parent := Node3D.new()
	var body_type: String = library.figure_set.rigs.keys()[0]
	var walk := FigureStances.read_file().clip_for("", FigureStances.ACTION_WALK)

	add_child(parent)

	for _index in 2:
		parent.add_child(library.build(body_type, {}))

	await get_tree().process_frame

	for holder: Node3D in parent.get_children():
		FigureLibrary.play(holder, FigureStances.ACTION_WALK)

		var figure := FigureLibrary.figure_of(holder)

		_expect(figure != null, "%s is a figure" % holder.name)
		_expect(figure != null and FigureClips.player_of(figure).current_animation == walk,
			"%s walks" % holder.name)

	parent.queue_free()
	library.free()


func _new_colors_are_a_new_look() -> void:
	var first := FigureLibrary.look_key("body_1", {})
	var second := FigureLibrary.look_key("body_1", {"skin": "gold"})

	_expect(first != second, "new colors are a new look")
	_expect(first == FigureLibrary.look_key("body_1", {}), "the same colors are the same look")
	_expect(first != FigureLibrary.look_key("body_2", {}), "another body type is a new look")
