extends Node
## Unit tests for MeshGlow -- that a glow is a uniform write and never a shader
## change, and that every place materials are born makes them ready.
##
##     godot --headless --path godot res://tests/test_mesh_glow.tscn
##
## Needs nothing running and no renderer: every check reads material properties,
## which is exactly where the bug lived. `emission_enabled` is part of the key a
## BaseMaterial3D builds its shader from, so a flipped flag here is a compile on
## the web -- measured at ~1.9 s for a variant nothing had drawn yet.

var _failures := 0

## An authored glow, the shape `map_transition.glb` imports with.
const AUTHORED_COLOR := Color(1.0, 0.2, 0.1)
const AUTHORED_ENERGY := 2.0

const HOVER_COLOR := Color(0.6, 0.7, 0.85)
const HOVER_ENERGY := 0.6


func _ready() -> void:
	_a_prepared_material_glows_nothing_until_lit()
	_lighting_and_resting_never_touch_the_flag()
	_an_authored_glow_is_what_it_rests_at()
	_preparing_twice_does_not_forget_the_rest()
	_an_unprepared_material_is_left_alone()
	_palette_materials_are_born_ready()
	_a_fetched_models_copies_own_ready_materials()
	_a_fetched_models_prototype_holds_the_same_variant()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: mesh_glow")
	get_tree().quit(0)


func _a_prepared_material_glows_nothing_until_lit() -> void:
	var material := StandardMaterial3D.new()

	MeshGlow.prepare(material)

	_expect(material.emission_enabled, "prepare switches emission on")
	_expect(is_zero_approx(material.emission_energy_multiplier),
		"at zero energy, so it draws as if emission were off")
	_expect(MeshGlow.is_ready(material), "and reports itself ready")
	_expect(not MeshGlow.is_lit(material), "and not lit")


## The whole point. Anything else here could regress and cost a wrong colour;
## this regressing costs a frozen frame on every hover.
func _lighting_and_resting_never_touch_the_flag() -> void:
	var material := StandardMaterial3D.new()

	MeshGlow.prepare(material)
	MeshGlow.light(material, HOVER_COLOR, HOVER_ENERGY)

	_expect(MeshGlow.is_lit(material), "light makes it lit")
	_expect(material.emission_enabled, "with emission still on")

	MeshGlow.rest(material)

	_expect(not MeshGlow.is_lit(material), "rest puts it out")
	_expect(material.emission_enabled,
		"and emission is STILL on -- switching it off is a shader change")


## The old hover switched emission off on the way out, which erased a model's
## own glow the first time the cursor crossed it.
func _an_authored_glow_is_what_it_rests_at() -> void:
	var material := StandardMaterial3D.new()

	material.emission_enabled = true
	material.emission = AUTHORED_COLOR
	material.emission_energy_multiplier = AUTHORED_ENERGY
	MeshGlow.prepare(material)

	_expect(material.emission.is_equal_approx(AUTHORED_COLOR),
		"prepare keeps an authored emission colour")
	_expect(not MeshGlow.is_lit(material), "and does not count it as lit")

	MeshGlow.light(material, HOVER_COLOR, HOVER_ENERGY)
	MeshGlow.rest(material)

	_expect(material.emission.is_equal_approx(AUTHORED_COLOR),
		"rest restores the authored colour")
	_expect(is_equal_approx(material.emission_energy_multiplier, AUTHORED_ENERGY),
		"and the authored energy")


## prepare() on a lit material must not record the hover as the new rest, or
## the glow could never be put out.
func _preparing_twice_does_not_forget_the_rest() -> void:
	var material := StandardMaterial3D.new()

	MeshGlow.prepare(material)
	MeshGlow.light(material, HOVER_COLOR, HOVER_ENERGY)
	MeshGlow.prepare(material)
	MeshGlow.rest(material)

	_expect(not MeshGlow.is_lit(material),
		"a second prepare kept the original rest")


## light() refusing is deliberate: switching emission on for a material that
## skipped prepare would glow correctly and quietly bring the compile back.
func _an_unprepared_material_is_left_alone() -> void:
	var material := StandardMaterial3D.new()

	MeshGlow.light(material, HOVER_COLOR, HOVER_ENERGY)

	_expect(not material.emission_enabled,
		"light does not switch emission on for an unprepared material")
	_expect(not MeshGlow.is_lit(material), "so it is not lit")


func _palette_materials_are_born_ready() -> void:
	var material := MeshPalette.material_for(MeshPalette.STEEL,
		MeshPalette.FINISH_METAL)

	_expect(MeshGlow.is_ready(material),
		"MeshPalette hands out glow-ready materials")


## Tier 1's materials live on the shared MESH and are copied per instance, so
## tinting one copy must not tint the rest -- and the copy must still be ready.
func _a_fetched_models_copies_own_ready_materials() -> void:
	var shared := StandardMaterial3D.new()
	var root := _model_with(shared)
	var instance := root.get_child(0) as MeshInstance3D

	ModelLoader._take_own_materials(root)

	var own := instance.get_surface_override_material(0) as StandardMaterial3D

	_expect(own != null and own != shared, "the copy owns its material")
	_expect(MeshGlow.is_ready(own), "and it is glow-ready")

	root.free()


## The prototype's materials outlive every copy, and a shader stays compiled
## only while a material of its EXACT variant exists. So the prototype must be
## glow-ready like its copies, or it holds alive a shader nothing draws and the
## warmed one is freed with the last copy.
func _a_fetched_models_prototype_holds_the_same_variant() -> void:
	var shared := StandardMaterial3D.new()
	var root := _model_with(shared)
	var instance := root.get_child(0) as MeshInstance3D

	ModelLoader._prepare_materials(root)

	_expect(MeshGlow.is_ready(shared),
		"the prototype's own material is glow-ready, holding the copies' variant")

	ModelLoader._take_own_materials(root)

	var own := instance.get_surface_override_material(0) as StandardMaterial3D

	_expect(MeshGlow.is_ready(own) and own.emission_enabled == shared.emission_enabled,
		"and a copy made from it is the same variant")

	root.free()


## A one-mesh model whose material lives on the mesh, as a glTF's does.
func _model_with(material: StandardMaterial3D) -> Node3D:
	var mesh := BoxMesh.new()
	var root := Node3D.new()
	var instance := MeshInstance3D.new()

	mesh.material = material
	instance.mesh = mesh
	root.add_child(instance)

	return root


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
