extends Node
## Tests for [FigureGlow] and [AugmentLook] (DESIGN-0015, Phase 3): the
## lit augments of a character glow on the parts of its figure.
##
##     godot --headless --path godot res://tests/world/figure/test_figure_glow.tscn
##
## Needs nothing running. It builds a mannequin from the body profile and
## reads the emission of each part back. The cases:
##
## 1. A lit augment lights each part that its look names, in its colour,
##    and no other part.
## 2. An empty lit set puts every part to rest.
## 3. A key with no look draws nothing and raises nothing.
## 4. The look file of the repository reads, and each part it names is a
##    part of the mannequin.

var _failures := 0


func _ready() -> void:
	_a_lit_augment_lights_its_parts_alone()
	_an_empty_set_rests_every_part()
	_an_unknown_key_draws_nothing()
	_a_holder_and_a_bare_mesh_are_handled()
	_the_repository_file_names_real_parts()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_glow")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _figure() -> Node3D:
	var rig := FigureEdits.rig_from_profile("body_1")
	var body := FigureEdits.mannequin(rig)

	return FigureBuilder.build(rig, [body])


## The emission colour of the first material of one part, or BLACK with
## no lit material.
func _glow_of(figure: Node3D, part_name: String) -> Color:
	for part: Node3D in FigureBuilder.part_nodes(figure):
		if FigureBuilder.part_id(part)[1] != part_name:
			continue

		for material: BaseMaterial3D in FigureGlow._materials_of(part):
			if MeshGlow.is_lit(material):
				return material.emission

	return Color.BLACK


func _a_lit_augment_lights_its_parts_alone() -> void:
	var figure := _figure()
	var key := AugmentLook.keys()[0]
	var look := AugmentLook.look_of(key)

	FigureGlow.apply(figure, [key])

	for part: String in look[AugmentLook.FIELD_PARTS]:
		_expect(_glow_of(figure, part) == look[AugmentLook.FIELD_COLOR],
			"the part %s glows in the colour of %s" % [part, key])

	var other := ""

	for part: Node3D in FigureBuilder.part_nodes(figure):
		var name_of_part: String = FigureBuilder.part_id(part)[1]

		if not look[AugmentLook.FIELD_PARTS].has(name_of_part):
			other = name_of_part
			break

	_expect(not other.is_empty() and _glow_of(figure, other) == Color.BLACK,
		"a part that the augment does not name stays at rest: " + other)
	figure.free()


func _an_empty_set_rests_every_part() -> void:
	var figure := _figure()
	var key := AugmentLook.keys()[0]

	FigureGlow.apply(figure, [key])
	FigureGlow.apply(figure, [])

	for part: Node3D in FigureBuilder.part_nodes(figure):
		_expect(_glow_of(figure, FigureBuilder.part_id(part)[1]) == Color.BLACK,
			"every part rests after the set empties")

	figure.free()


func _an_unknown_key_draws_nothing() -> void:
	var figure := _figure()

	FigureGlow.apply(figure, ["no_such_augment"])

	_expect(FigureGlow.glowing_parts(["no_such_augment"]).is_empty(),
		"a key with no look names no part")
	_expect(AugmentLook.look_of("no_such_augment").is_empty(), "and has no look")
	figure.free()


## The pool and the avatar hold the figure inside a holder. The avatar is
## a bare mesh until the figure set arrives. The second raised in the
## editor on 10/30/2026.
func _a_holder_and_a_bare_mesh_are_handled() -> void:
	var holder := Node3D.new()
	var figure := _figure()
	holder.add_child(figure)
	var key := AugmentLook.keys()[0]
	var look := AugmentLook.look_of(key)

	FigureGlow.apply(holder, [key])

	var part: String = look[AugmentLook.FIELD_PARTS][0]
	_expect(_glow_of(figure, part) == look[AugmentLook.FIELD_COLOR],
		"a figure inside a holder glows")
	holder.free()

	var mesh := MeshInstance3D.new()
	FigureGlow.apply(mesh, [key])
	_expect(FigureGlow.part_nodes_under(mesh).is_empty(), "a bare mesh has no part and raises nothing")
	mesh.free()


func _the_repository_file_names_real_parts() -> void:
	LookFile.forget(AugmentLook.PATH)
	var data := AugmentLook.data()
	var rig := FigureEdits.rig_from_profile("body_1")
	var names := FigureEdits.mannequin(rig).part_names()

	_expect(not data.is_empty(), "the augment looks of the repository read")

	for key: String in data.get(AugmentLook.KEY_AUGMENTS, {}):
		var look := AugmentLook.look_of(key)

		_expect(not look[AugmentLook.FIELD_PARTS].is_empty(), "%s names a part" % key)

		for part: String in look[AugmentLook.FIELD_PARTS]:
			_expect(names.has(part), "the part %s of %s is a part of the body" % [part, key])
