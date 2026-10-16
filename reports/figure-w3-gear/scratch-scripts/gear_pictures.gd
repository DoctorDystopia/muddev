extends SceneTree
## Pictures of dressed figures, for DESIGN-0014 Phase W3. Each picture shows
## each body type in one outfit, from four sides.
##
##     godot --path godot -s <this file> -- <output directory>
##
## It needs a window, because it draws. It reads the figure files and the
## item catalog of the repository, and it writes only the pictures.

const SPACING := 1.3
const PIXELS := Vector2i(3200, 760)
const MARGIN := 0.6
const TURNS := [0.0, -PI / 2.0, PI, PI / 2.0]
const SETTLE_FRAMES := 3

## Each outfit: its name, then slot -> asset key. A slot that names itself
## shows the slot shape with no item.
const OUTFITS := {
	"one_hand": {"main_hand": "main_hand", "off_hand": "off_hand", "head": "head",
		"body": "body", "legs": "legs", "feet": "feet", "back": "back", "neck": "neck",
		"main_hand_finger": "main_hand_finger", "off_hand_finger": "off_hand_finger",
		"ammo": "ammo"},
	"two_hands": {"two_hands": "two_hands", "head": "head", "feet": "feet"},
	"bare_gear": {"main_hand": "main_hand", "neck": "neck",
		"main_hand_finger": "main_hand_finger", "off_hand_finger": "off_hand_finger",
		"ammo": "ammo"},
}


func _init() -> void:
	_run.call_deferred()


func _run() -> void:
	var out: String = OS.get_cmdline_user_args()[0]
	var store := FigureStore.new(FigureStore.repo_directory())
	var catalog := FigureCatalog.read_file()
	var library := FigureClips.library()

	store.load_all()
	DirAccess.make_dir_recursive_absolute(out)

	for outfit_name: String in OUTFITS:
		var rest := await _picture(store, catalog, OUTFITS[outfit_name], null)

		rest.save_png(out.path_join("%s_rest.png" % outfit_name))

		if library.has_animation("walk"):
			var walk := await _picture(store, catalog, OUTFITS[outfit_name],
				library.get_animation("walk"))

			walk.save_png(out.path_join("%s_walk.png" % outfit_name))

	quit()


## One picture: each body type from each side of `TURNS`.
func _picture(store: FigureStore, catalog: FigureCatalog, worn: Dictionary,
		clip: Animation) -> Image:
	var viewport := SubViewport.new()
	var keys := store.keys_of(FigureStore.KIND_RIG)
	var count := keys.size() * TURNS.size()

	viewport.size = PIXELS
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.msaa_3d = Viewport.MSAA_4X
	root.add_child(viewport)
	_add_stage(viewport, count)

	for index in count:
		var rig: FigureRig = store.rigs[keys[index / TURNS.size()]]
		var figure := FigureBuilder.build(rig,
			FigureOutfit.looks_for(rig, worn, store.looks, catalog.families()))

		figure.position.x = (index - (count - 1) * 0.5) * SPACING
		figure.rotation.y = TURNS[index % TURNS.size()]
		viewport.add_child(figure)

		if clip != null:
			FigureClips.pose(FigureBuilder.skeleton_of(figure), clip,
				clip.length * (index % TURNS.size()) / TURNS.size())

	for _frame in SETTLE_FRAMES:
		await process_frame

	await RenderingServer.frame_post_draw

	var image := viewport.get_texture().get_image()

	viewport.queue_free()

	return image


func _add_stage(viewport: SubViewport, count: int) -> void:
	var camera := Camera3D.new()
	var sun := DirectionalLight3D.new()
	var floor_node := MeshInstance3D.new()
	var floor_mesh := PlaneMesh.new()
	var floor_material := StandardMaterial3D.new()
	var environment := WorldEnvironment.new()

	# The size is the width of the view, so each figure of the row shows.
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.keep_aspect = Camera3D.KEEP_WIDTH
	camera.size = count * SPACING + MARGIN
	camera.position = Vector3(0.0, 0.95, 6.0)
	sun.rotation = Vector3(-0.9, 0.6, 0.0)
	sun.shadow_enabled = true
	floor_mesh.size = Vector2(count * SPACING + 2.0, 6.0)
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
