extends SceneTree
## Pictures of each clip, for DESIGN-0014 Phase W2. Each picture shows one
## body type at eight moments of one clip, with the probe of
## `FigureClearance` in each hand.
##
##     godot --path godot -s <this file> -- <clip directory> <output directory>
##
## It needs a window, because it draws. It writes
## `<clip>_<body type>_<view>.png` for the front view and the side view.

const MOMENTS := 8
const SPACING := 1.5
const PIXELS := Vector2i(2400, 520)
const VIEW_HEIGHT := 2.5
const VIEWS := {"front": 0.0, "side": -PI / 2.0}
const SETTLE_FRAMES := 3


func _init() -> void:
	_run.call_deferred()


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	var store := FigureStore.new(FigureStore.repo_directory())
	var library := FigureClips.library_from(args[0])

	store.load_all()
	DirAccess.make_dir_recursive_absolute(args[1])

	for clip_name: String in FigureClips.names_of(library):
		for body_key: String in store.keys_of(FigureStore.KIND_RIG):
			for view: String in VIEWS:
				var image := await _picture(store, body_key, library.get_animation(clip_name),
					VIEWS[view])

				image.save_png(args[1].path_join("%s_%s_%s.png" % [clip_name, body_key, view]))

	quit()


## One picture: `MOMENTS` figures in a row, each at its moment of the clip.
func _picture(store: FigureStore, body_key: String, clip: Animation,
		turn: float) -> Image:
	var viewport := SubViewport.new()
	var rig: FigureRig = store.rigs[body_key]
	var looks := [store.looks[body_key], FigureClearance.probe_look(rig)]

	viewport.size = PIXELS
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.msaa_3d = Viewport.MSAA_4X
	root.add_child(viewport)
	_add_stage(viewport)

	for moment in MOMENTS:
		var figure := FigureBuilder.build(rig, looks)

		figure.position.x = (moment - (MOMENTS - 1) * 0.5) * SPACING
		figure.rotation.y = turn
		viewport.add_child(figure)
		FigureClips.pose(FigureBuilder.skeleton_of(figure), clip, clip.length * moment / MOMENTS)

	for _frame in SETTLE_FRAMES:
		await process_frame

	await RenderingServer.frame_post_draw

	var image := viewport.get_texture().get_image()

	viewport.queue_free()

	return image


func _add_stage(viewport: SubViewport) -> void:
	var camera := Camera3D.new()
	var sun := DirectionalLight3D.new()
	var floor_node := MeshInstance3D.new()
	var floor_mesh := PlaneMesh.new()
	var floor_material := StandardMaterial3D.new()
	var environment := WorldEnvironment.new()

	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = VIEW_HEIGHT
	camera.position = Vector3(0.0, 0.95, 6.0)
	sun.rotation = Vector3(-0.9, 0.6, 0.0)
	sun.shadow_enabled = true
	floor_mesh.size = Vector2(MOMENTS * SPACING + 2.0, 6.0)
	floor_material.albedo_color = FigureWorkbench.FLOOR_COLOR
	floor_node.mesh = floor_mesh
	floor_node.material_override = floor_material
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color(0.2, 0.22, 0.27)
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color(0.6, 0.6, 0.65)

	for node: Node in [camera, sun, floor_node, environment]:
		viewport.add_child(node)
