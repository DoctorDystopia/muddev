class_name ShaderWarmer
extends SubViewport
## Draws a model once where the player cannot see it, so its shaders compile now.
##
## ## Why a model has to be DRAWN
##
## The Compatibility renderer compiles a material's shader the first time
## something is drawn with it, not when the material is made, and on the web
## that compile is synchronous and slow. Measured 09/13/2026 in a Chromium
## WebGL 2 export of Godot 4.7.1: today's twenty models cost 13.5 s of frozen
## frames to draw once, most of it six compiles of 1-5 s. There is no call that
## compiles without drawing, so the only way to move a freeze is to move the
## draw -- here, behind the loading veil. See [method MeshResolver.prefetch_all].
##
## ## In the world pane's world, out of its camera's reach
##
## `own_world_3d` stays FALSE, the opposite of [ItemStage] and on purpose. A
## shader is compiled for the lighting it is drawn under, so warming a model
## under some other sun would compile something nobody draws. Sharing the world
## means sharing its camera's scene too, so the stage stands [constant
## STAGE_DEPTH] below the map -- past the far plane of the world camera, which is
## Camera3D's default of 4000 -- where no orbit or zoom can bring it into view.
## `test_shader_warmer` reads that far plane out of `world.tscn` rather than
## trusting this comment.
##
## ## Two ways a model is drawn, so two things to warm
##
## An entity or prop is a plain MeshInstance3D. The ground is not: the world pane
## stamps terrain with a MultiMesh, and instanced drawing is its own shader
## variant. So every model is warmed with a one-instance MultiMesh beside it,
## built the way `WorldView._new_multimesh` builds terrain (transforms, no
## colours).
##
## ## Held, then freed -- or kept
##
## A model stays on the stage for [constant HOLD_FRAMES] frames and is freed.
## Keeping it would keep its shaders alive, but fetched art needs no help: its
## prototype holds them (see [method ModelLoader._prepare_materials]). The
## procedural palette has no prototype, so [method MeshResolver.bind_warmer]
## hands over one block to KEEP, hidden once drawn.

## How far below the map the stage stands. Far enough past the world camera's
## far plane that nothing the player does brings it into view, and close enough
## that float precision still places a unit-sized model to a few millimetres.
const STAGE_DEPTH := -20000.0

## How many frames a model stays on the stage.
##
## A compile happens during the draw, and the draw follows the process step. A
## model mounted part-way through one frame's processing is drawn at the end of
## that frame or the next, so two frames is exactly enough and three is margin
## against a mount that lands after this node's own _process has already run.
const HOLD_FRAMES := 3

## The render target's side in pixels. Nothing ever reads the picture; it only
## has to be a real draw, and drawing four pixels compiles the same shaders as
## drawing a whole screen.
const TARGET_PIXELS := 4

## Where the stage camera stands and how much it frames. Every model is
## normalised into a unit box centred on its origin, so an orthographic view two
## units across frames all of it. A surface the camera culls is a surface whose
## shader is not compiled, so a model must never be cropped out.
const CAMERA_DISTANCE := 3.0
const CAMERA_SPAN := 2.0

## Instances in a warming MultiMesh. One draw call is all a compile needs.
const _TWIN_INSTANCES := 1

## Where every warmed model is mounted.
var _stage: Node3D

## One entry per model on the stage: [node, frames_left, keep].
var _held: Array = []


func _init() -> void:
	size = Vector2i(TARGET_PIXELS, TARGET_PIXELS)

	# Nothing to draw until something is handed over, so no render pass is paid
	# for an empty stage for the rest of the session.
	render_target_update_mode = SubViewport.UPDATE_DISABLED

	_stage = Node3D.new()
	_stage.position = Vector3(0.0, STAGE_DEPTH, 0.0)
	add_child(_stage)

	var camera := Camera3D.new()

	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = CAMERA_SPAN
	camera.position = Vector3(0.0, 0.0, CAMERA_DISTANCE)
	_stage.add_child(camera)


## Put a model on the stage long enough to be drawn.
##
## Takes ownership. The model is freed once drawn, unless `keep` -- then it is
## hidden and stays for as long as the warmer does, holding its shaders alive.
func warm(model: Node3D, keep := false) -> void:
	if model == null:
		return

	_add_instanced_twin(model)
	_stage.add_child(model)
	_held.append([model, HOLD_FRAMES, keep])
	render_target_update_mode = SubViewport.UPDATE_ALWAYS


## How many models are still waiting to be drawn.
##
## Counted by [method MeshResolver.in_flight_count], which is what keeps the
## veil up until the compiles are behind the player rather than ahead of them.
func pending_count() -> int:
	return _held.size()


## Where the stage stands, for a test to check it against the world camera.
func stage_origin() -> Vector3:
	return _stage.global_position


func _process(_delta: float) -> void:
	if _held.is_empty():
		return

	var still_held: Array = []

	for entry: Array in _held:
		entry[1] -= 1

		if entry[1] > 0:
			still_held.append(entry)
		else:
			_release(entry)

	_held = still_held

	if _held.is_empty():
		render_target_update_mode = SubViewport.UPDATE_DISABLED


# ─── Private ─────────────────────────────────────────────────────────────────

## Free a drawn model, or hide it if it is being kept.
func _release(entry: Array) -> void:
	var model: Node3D = entry[0]
	var keep: bool = entry[2]

	if not is_instance_valid(model):
		return

	if keep:
		model.visible = false
	else:
		model.queue_free()


## Hang a one-instance MultiMesh of each of the model's meshes under it.
##
## Under the model rather than beside it, so it is freed and hidden with it and
## needs no bookkeeping of its own. Transformed by the part's place inside the
## model, as terrain is, so it stands where the camera is looking.
func _add_instanced_twin(model: Node3D) -> void:
	var parts := ModelLoader.mesh_parts(model)

	for part: Array in parts:
		var multi := MultiMesh.new()

		multi.transform_format = MultiMesh.TRANSFORM_3D
		multi.use_colors = false
		multi.mesh = part[0]
		multi.instance_count = _TWIN_INSTANCES
		multi.set_instance_transform(0, part[1])

		var twin := MultiMeshInstance3D.new()

		twin.multimesh = multi
		model.add_child(twin)
