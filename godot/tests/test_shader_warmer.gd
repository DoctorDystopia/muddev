extends Node
## Unit tests for ShaderWarmer, and for how MeshResolver counts it as art still
## in flight.
##
##     godot --headless --path godot res://tests/test_shader_warmer.tscn
##
## Needs nothing running. Headless draws nothing, so no shader is ever compiled
## here -- what is checked is everything that decides whether one WOULD be:
## that a model is really on a stage in the right world, out of the player's
## view, for long enough, and that the veil is told to wait for it.

var _failures := 0

## The frames a test waits beyond the warmer's hold, so a queued free has
## certainly landed before it looks.
const SETTLE_FRAMES := 2

## Where the world pane's camera lives in its scene. Read for its far plane, so
## a camera given a longer reach later fails this test instead of quietly
## putting the stage on screen.
const WORLD_SCENE := "res://scenes/world.tscn"
const WORLD_CAMERA := "Camera/SpringArm3D/Camera3D"


func _ready() -> void:
	await _a_warmed_model_is_held_and_then_freed()
	await _a_kept_model_outlives_its_hold_hidden()
	_every_model_is_warmed_as_terrain_draws_it_too()
	_the_stage_is_beyond_the_world_cameras_reach()
	_the_stage_draws_in_the_world_it_warms_for()
	await _warming_holds_the_veil()
	_a_prefetch_waits_on_the_manifest()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: shader_warmer")
	get_tree().quit(0)


func _a_warmed_model_is_held_and_then_freed() -> void:
	var warmer := _new_warmer()
	var model := Node3D.new()

	warmer.warm(model)

	_expect(warmer.pending_count() == 1, "a warmed model is pending")
	_expect(model.is_inside_tree(), "and is on the stage, where it can be drawn")
	_expect(warmer.render_target_update_mode == SubViewport.UPDATE_ALWAYS,
		"and the stage is rendering")

	await _frames(ShaderWarmer.HOLD_FRAMES + SETTLE_FRAMES)

	_expect(warmer.pending_count() == 0, "once its frames are up it is done")
	_expect(not is_instance_valid(model), "and freed -- its prototype holds the shader")
	_expect(warmer.render_target_update_mode == SubViewport.UPDATE_DISABLED,
		"and an empty stage stops rendering")

	warmer.queue_free()


## The palette's one keepalive. Freed, the shared shader would go with it the
## first time a room held no primitive.
func _a_kept_model_outlives_its_hold_hidden() -> void:
	var warmer := _new_warmer()
	var model := Node3D.new()

	warmer.warm(model, true)
	await _frames(ShaderWarmer.HOLD_FRAMES + SETTLE_FRAMES)

	_expect(is_instance_valid(model), "a kept model survives its hold")
	_expect(is_instance_valid(model) and not model.visible,
		"hidden, so it stops being drawn once it has been")
	_expect(warmer.pending_count() == 0, "and no longer counts as pending")

	warmer.queue_free()


## The ground is a MultiMesh, and instancing is a variant of its own. A model
## warmed only as a MeshInstance3D would leave every terrain tile to compile on
## the first map load after the veil.
func _every_model_is_warmed_as_terrain_draws_it_too() -> void:
	var warmer := _new_warmer()
	var model := MeshBuilder.build(FamilyShapes.parts_for("no_such_family"))
	var meshes := ModelLoader.mesh_parts(model).size()

	warmer.warm(model)

	var twins := 0

	for child: Node in model.get_children():
		if child is MultiMeshInstance3D:
			twins += 1

	_expect(meshes > 0, "the model has meshes; if this fails the check below is inert")
	_expect(twins == meshes, "one instanced twin per mesh (%d of %d)" % [twins, meshes])

	warmer.free()


func _the_stage_is_beyond_the_world_cameras_reach() -> void:
	var world: Node = load(WORLD_SCENE).instantiate()
	var camera := world.get_node(WORLD_CAMERA) as Camera3D
	var warmer := _new_warmer()
	var depth := absf(warmer.stage_origin().y)

	_expect(camera != null, "the world scene still has its camera where expected")

	if camera != null:
		_expect(depth - ShaderWarmer.CAMERA_SPAN > camera.far,
			"the stage (%.0f down) is past the world camera's far plane (%.0f)"
			% [depth, camera.far])

	world.free()
	warmer.free()


## A shader is compiled for the lighting it is drawn under. A private world
## would warm variants nobody draws.
func _the_stage_draws_in_the_world_it_warms_for() -> void:
	var warmer := _new_warmer()

	_expect(not warmer.own_world_3d, "the warmer does not make a world of its own")
	_expect(warmer.find_world_3d() == get_viewport().find_world_3d(),
		"it draws in the world of the viewport it is placed in")

	warmer.free()


## What the prefetch is for: the veil lifts on in_flight_count, so a model that
## has arrived but not been drawn must still count, or the player meets its
## compile as lag instead of as loading.
func _warming_holds_the_veil() -> void:
	var resolver := MeshResolver.new(ModelRegistry.new(), "")
	var warmer := _new_warmer()

	add_child(resolver)
	resolver.bind_warmer(warmer)

	_expect(resolver.in_flight_count() == 1,
		"binding hands over the palette's keepalive, which is pending")

	await _frames(ShaderWarmer.HOLD_FRAMES + SETTLE_FRAMES)

	_expect(resolver.in_flight_count() == 0, "drawn, it stops holding the veil")

	warmer.warm(Node3D.new())

	_expect(resolver.in_flight_count() == 1, "and a new arrival holds it again")

	resolver.queue_free()
	warmer.queue_free()


## The veil can go up before the manifest lands. With nothing yet requested the
## in-flight count would read zero and the veil would lift on a prefetch that
## has not started.
func _a_prefetch_waits_on_the_manifest() -> void:
	var resolver := MeshResolver.new(ModelRegistry.new(), "")

	add_child(resolver)

	_expect(resolver.in_flight_count() == 0, "nothing is outstanding before a prefetch")

	resolver.prefetch_all()

	_expect(resolver.in_flight_count() == 1,
		"a prefetch waiting on the manifest holds the veil")

	# A FAILED fetch settles the wait too, the way the loader reports one: a
	# manifest that is never coming must not hold the veil to its ceiling.
	resolver._loader.manifest_ready.emit(0)

	_expect(resolver.in_flight_count() == 0,
		"and a manifest settling -- even empty -- releases it")

	resolver.queue_free()


func _new_warmer() -> ShaderWarmer:
	var warmer := ShaderWarmer.new()

	add_child(warmer)

	return warmer


func _frames(count: int) -> void:
	for frame: int in count:
		await get_tree().process_frame


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
