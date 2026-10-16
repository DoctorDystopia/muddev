extends SceneTree
## Pictures of the low-poly look, for DESIGN-0014 section 16. Each row
## shows one body type in one outfit: five sides in a stand, then one
## moment of the walk clip.
##
##     godot --path godot -s <this file> -- <output directory>
##
## It needs a window, because it draws. It reads the figure files and the
## item catalog of the repository, and it writes only the pictures.

const PIXELS := Vector2i(2400, 700)
const SPACING := 1.15
const TURNS := [0.0, PI / 4.0, -PI / 4.0, -PI / 2.0, PI]
const SETTLE_FRAMES := 4

## The turn of each upper arm from the rest pose to the stand, in radians.
const ARM_DOWN := 1.40

## Each row: its file name, its body type, and slot -> asset key. A slot
## that names itself shows the slot shape with no item.
const ROWS := [
	["bare_body_1", "body_1", {}],
	["bare_body_2", "body_2", {}],
	["armor_body_1", "body_1", {"main_hand": "main_hand", "off_hand": "off_hand",
		"head": "head", "body": "body", "legs": "legs", "feet": "feet"}],
	["armor_body_2", "body_2", {"main_hand": "main_hand", "off_hand": "off_hand",
		"head": "head", "body": "body", "legs": "legs", "feet": "feet"}],
	["two_hands_body_1", "body_1", {"two_hands": "two_hands", "body": "body",
		"back": "back", "feet": "feet"}],
	["small_gear_body_1", "body_1", {"main_hand": "main_hand", "neck": "neck",
		"main_hand_finger": "main_hand_finger", "off_hand_finger": "off_hand_finger",
		"ammo": "ammo", "back": "back"}],
]


func _init() -> void:
	_run.call_deferred()


func _run() -> void:
	var out: String = OS.get_cmdline_user_args()[0]
	var store := FigureStore.new(FigureStore.repo_directory())
	var catalog := FigureCatalog.read_file()
	var walk := FigureClips.library().get_animation("walk")
	var sheet := Image.create(PIXELS.x, PIXELS.y * ROWS.size(), false, Image.FORMAT_RGBA8)

	store.load_all()
	DirAccess.make_dir_recursive_absolute(out)

	for index in ROWS.size():
		var row: Array = ROWS[index]
		var rig: FigureRig = store.rigs[row[1]]
		var looks := FigureOutfit.looks_for(rig, row[2], store.looks, catalog.families())
		var image := await _picture(rig, looks, walk, str(row[0]))

		image.save_png(out.path_join("%s.png" % row[0]))
		image.convert(Image.FORMAT_RGBA8)
		sheet.blit_rect(image, Rect2i(Vector2i.ZERO, PIXELS), Vector2i(0, PIXELS.y * index))

	sheet.save_png(out.path_join("look_sheet.png"))
	quit()


## One picture: the figure from each side of `TURNS`, then in the walk.
func _picture(rig: FigureRig, looks: Array, walk: Animation, title: String) -> Image:
	var viewport := SubViewport.new()
	var label := Label.new()
	var count := TURNS.size() + 1

	viewport.size = PIXELS
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.msaa_3d = Viewport.MSAA_4X
	root.add_child(viewport)
	_add_stage(viewport, count)
	label.text = title
	label.position = Vector2(40, 24)
	label.add_theme_font_size_override("font_size", 40)
	viewport.add_child(label)

	for index in count:
		var figure := FigureBuilder.build(rig, looks)

		figure.position.x = (index - (count - 1) * 0.5) * SPACING
		figure.rotation.y = TURNS[index] if index < TURNS.size() else PI / 4.0
		viewport.add_child(figure)

		if index < TURNS.size():
			_stand(figure, rig)
		else:
			FigureClips.pose(FigureBuilder.skeleton_of(figure), walk, walk.length * 0.25)

		if index == 0:
			print(title, " ", FigureBuilder.counts(figure))

	for _frame in SETTLE_FRAMES:
		await process_frame

	await RenderingServer.frame_post_draw

	var image := viewport.get_texture().get_image()

	viewport.queue_free()

	return image


## Turn each upper arm down from the rest pose. No clip has this pose.
func _stand(figure: Node3D, rig: FigureRig) -> void:
	var skeleton := FigureBuilder.skeleton_of(figure)

	for side: Array in [["Left", 1.0], ["Right", -1.0]]:
		var parent := rig.global_rest_of(side[0] + "Shoulder").basis
		var rest := rig.global_rest_of(side[0] + "UpperArm").basis
		var turn := Basis(Vector3(0.0, 0.0, 1.0), -side[1] * ARM_DOWN)
		var pose := parent.inverse() * turn * rest

		skeleton.set_bone_pose_rotation(skeleton.find_bone(side[0] + "UpperArm"),
			pose.get_rotation_quaternion())


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
	camera.size = count * SPACING + 0.4
	camera.position = Vector3(0.0, 0.8, 6.0)
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
