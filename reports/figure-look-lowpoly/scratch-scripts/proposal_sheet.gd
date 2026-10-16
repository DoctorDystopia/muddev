extends SceneTree
## Scratch: a prototype of an OSRS-style figure, for a look proposal.
## It writes pictures only. It changes no file of the repository.
##
##     godot --path godot -s <this file> -- <output directory>

const PIXELS := Vector2i(2400, 760)
const SPACING := 1.15
const TURNS := [0.0, PI / 4.0, -PI / 4.0, -PI / 2.0, PI]
const ARM_DOWN := 1.40
const REFERENCE := "C:/Users/NickR/source/repos/muddev/blackout/web/static/webclient/models/characters/player_character.glb"

const SKIN := Color("e3b48c")
const SHIRT := Color("55565d")
const TROUSERS := Color("dfdfda")
const BELT := Color("8e1b1b")
const CUFF := Color("6f6316")
const BOOT := Color("77777c")
const HAIR := Color("d6d6dc")
const DARK := Color("2a2420")
const BAND := Color("ececf0")
const STEEL := Color("7c8088")
const STEEL_DARK := Color("4d5058")
const BLADE := Color("b9bec8")
const LEATHER := Color("5e4129")
const GOLD := Color("c9a23f")

const FRONT := Vector3(0.0, 0.0, 1.0)
const UP := Vector3(0.0, 1.0, 0.0)

## "bone|space" -> SurfaceTool. The space is "figure" or "socket".
var _tools := {}
var _triangles := 0


func _init() -> void:
	_run.call_deferred()


func _run() -> void:
	var out: String = OS.get_cmdline_user_args()[0]
	var store := FigureStore.new(FigureStore.repo_directory())
	var catalog := FigureCatalog.read_file()
	var walk := FigureClips.library().get_animation("walk")

	store.load_all()
	DirAccess.make_dir_recursive_absolute(out)

	var old_rig: FigureRig = store.rigs["body_1"]
	var new_rig := _osrs_rig(old_rig)
	var rows := []

	rows.append(await _row("The OSRS placeholder model of today", func(index: int) -> Node3D:
		return _reference() if index < TURNS.size() else null))

	var worn := {"main_hand": "main_hand", "off_hand": "off_hand", "head": "head",
		"body": "body", "legs": "legs", "feet": "feet"}

	rows.append(await _row("The figure of today: bare, and with the slot shapes", func(index: int) -> Node3D:
		var dressed := index % 2 == 1 or index == TURNS.size()
		var figure := FigureBuilder.build(old_rig, FigureOutfit.looks_for(old_rig,
			worn if dressed else {}, store.looks, catalog.families()))

		figure.set_meta("pose", [old_rig, walk if index == TURNS.size() else null])
		return figure))

	rows.append(await _row("Proposal: the body", func(index: int) -> Node3D:
		var figure := _figure(new_rig, false)

		figure.set_meta("pose", [new_rig, walk if index == TURNS.size() else null])
		return figure))

	print("triangles of the proposed body: ", _triangles)

	rows.append(await _row("Proposal: rigid items on the body", func(index: int) -> Node3D:
		var figure := _figure(new_rig, true)

		figure.set_meta("pose", [new_rig, walk if index == TURNS.size() else null])
		return figure))

	print("triangles of the proposed dressed figure: ", _triangles)

	var sheet := Image.create(PIXELS.x, PIXELS.y * rows.size(), false, Image.FORMAT_RGBA8)

	for index in rows.size():
		var image: Image = rows[index]

		image.convert(Image.FORMAT_RGBA8)
		sheet.blit_rect(image, Rect2i(Vector2i.ZERO, PIXELS), Vector2i(0, PIXELS.y * index))
		image.save_png(out.path_join("row_%d.png" % index))

	sheet.save_png(out.path_join("look_sheet.png"))
	quit()


# ─── The proposal ───────────────────────────────────────────────────────────

## The rig of body type 1 with the proportions of the proposal: the
## shoulders wider, and the arms shorter.
func _osrs_rig(rig: FigureRig) -> FigureRig:
	var data: Dictionary = rig.data.duplicate(true)

	for row: Dictionary in data["bones"]:
		var bone: String = row["name"]

		if bone.ends_with("UpperArm"):
			row["position"] = [0.0, 0.115, 0.0]
		elif bone.ends_with("LowerArm"):
			row["position"] = [0.0, 0.195, 0.0]
		elif bone in ["LeftHand", "RightHand"]:
			row["position"] = [0.0, 0.19, 0.0]

	return FigureRig.from_data(data)


func _figure(rig: FigureRig, dressed: bool) -> Node3D:
	var figure := FigureBuilder.build(rig, [])
	var skeleton := FigureBuilder.skeleton_of(figure)

	_tools = {}
	_triangles = 0
	_torso(dressed)
	_head(dressed)

	for side: float in [1.0, -1.0]:
		var word := "Left" if side > 0.0 else "Right"

		_arm(word, side, dressed)
		_leg(word, side, dressed)

	if dressed:
		_sword()
		_shield(rig)

	for key: String in _tools:
		var bone: String = key.get_slice("|", 0)
		var space: String = key.get_slice("|", 1)
		var attachment := BoneAttachment3D.new()
		var instance := MeshInstance3D.new()
		var material := StandardMaterial3D.new()

		material.vertex_color_use_as_albedo = true
		material.roughness = 1.0
		material.metallic = 0.0
		material.metallic_specular = 0.0
		instance.mesh = (_tools[key] as SurfaceTool).commit()
		instance.material_override = material

		if space == "figure":
			instance.transform = rig.global_rest_of(bone).affine_inverse()

		attachment.name = bone + "_" + space
		skeleton.add_child(attachment)
		attachment.bone_name = bone
		attachment.bone_idx = skeleton.find_bone(bone)
		attachment.add_child(instance)

	return figure


func _torso(dressed: bool) -> void:
	var top := STEEL if dressed else SHIRT
	var low := STEEL if dressed else TROUSERS
	var grow := 1.08 if dressed else 1.0

	_prism("Hips", low, Vector3(0, 0.63, 0), Vector3(0, 0.80, 0),
		Vector2(0.19, 0.125) * grow, Vector2(0.215, 0.14) * grow, 8)
	_prism("Hips", STEEL_DARK if dressed else BELT, Vector3(0, 0.795, 0), Vector3(0, 0.83, 0),
		Vector2(0.224, 0.148) * grow, Vector2(0.224, 0.148) * grow, 8)
	_prism("Spine", top, Vector3(0, 0.82, 0), Vector3(0, 0.96, 0),
		Vector2(0.21, 0.135) * grow, Vector2(0.25, 0.155) * grow, 8)
	_prism("Chest", top, Vector3(0, 0.94, 0), Vector3(0, 1.06, 0),
		Vector2(0.25, 0.155) * grow, Vector2(0.30, 0.172) * grow, 8)
	_prism("UpperChest", top, Vector3(0, 1.04, 0), Vector3(0, 1.165, 0),
		Vector2(0.30, 0.172) * grow, Vector2(0.33, 0.16) * grow, 8)
	_prism("UpperChest", top, Vector3(0, 1.165, 0), Vector3(0, 1.205, 0),
		Vector2(0.33, 0.16) * grow, Vector2(0.13, 0.10), 8)

	if dressed:
		# A trim band on the chest, as an OSRS platebody has.
		_prism("Chest", STEEL_DARK, Vector3(0, 0.99, 0.0), Vector3(0, 1.02, 0.0),
			Vector2(0.305, 0.19), Vector2(0.31, 0.192), 8)
		_prism("UpperChest", GOLD, Vector3(0, 1.085, 0.085), Vector3(0, 1.085, 0.097),
			Vector2(0.05, 0.05), Vector2(0.04, 0.04), 4, UP, -TAU / 8.0)


func _head(dressed: bool) -> void:
	_prism("Neck", SKIN, Vector3(0, 1.15, 0), Vector3(0, 1.26, 0),
		Vector2(0.075, 0.08), Vector2(0.07, 0.075), 6)

	if dressed:
		_prism("Head", STEEL, Vector3(0, 1.205, 0.0), Vector3(0, 1.33, 0),
			Vector2(0.165, 0.185), Vector2(0.19, 0.21), 8)
		_prism("Head", STEEL, Vector3(0, 1.33, 0), Vector3(0, 1.425, 0),
			Vector2(0.19, 0.21), Vector2(0.15, 0.17), 8)
		_prism("Head", STEEL, Vector3(0, 1.425, 0), Vector3(0, 1.465, 0),
			Vector2(0.15, 0.17), Vector2(0.05, 0.07), 8)
		# The slit of the visor, and the ridge of the helm.
		_prism("Head", DARK, Vector3(0, 1.335, 0.09), Vector3(0, 1.335, 0.108),
			Vector2(0.12, 0.02), Vector2(0.12, 0.02), 4, UP)
		_prism("Head", DARK, Vector3(0, 1.27, 0.085), Vector3(0, 1.27, 0.102),
			Vector2(0.016, 0.09), Vector2(0.016, 0.09), 4, UP)
		_prism("Head", STEEL_DARK, Vector3(0, 1.45, -0.1), Vector3(0, 1.45, 0.1),
			Vector2(0.022, 0.07), Vector2(0.022, 0.05), 4, UP)
		return

	_prism("Head", SKIN, Vector3(0, 1.215, 0.012), Vector3(0, 1.30, 0.0),
		Vector2(0.085, 0.10), Vector2(0.15, 0.165), 8)
	_prism("Head", SKIN, Vector3(0, 1.30, 0), Vector3(0, 1.40, 0),
		Vector2(0.15, 0.165), Vector2(0.14, 0.16), 8)
	_prism("Head", SKIN, Vector3(0, 1.40, 0), Vector3(0, 1.435, 0),
		Vector2(0.14, 0.16), Vector2(0.08, 0.10), 8)
	_prism("Head", SKIN, Vector3(0, 1.295, 0.078), Vector3(0, 1.34, 0.076),
		Vector2(0.034, 0.03), Vector2(0.014, 0.012), 4)

	for side: float in [1.0, -1.0]:
		_prism("Head", DARK, Vector3(side * 0.036, 1.345, 0.07), Vector3(side * 0.036, 1.345, 0.0845),
			Vector2(0.03, 0.012), Vector2(0.03, 0.012), 4, UP)
		_prism("Head", HAIR, Vector3(side * 0.036, 1.362, 0.07), Vector3(side * 0.036, 1.362, 0.086),
			Vector2(0.04, 0.009), Vector2(0.04, 0.009), 4, UP)

	# The hair is one part on the socket of the head top: the hair region.
	_prism("head_top", HAIR, Vector3(0, 1.375, -0.014), Vector3(0, 1.455, -0.02),
		Vector2(0.165, 0.19), Vector2(0.10, 0.12), 8)
	_prism("head_top", HAIR, Vector3(0, 1.26, -0.06), Vector3(0, 1.40, -0.05),
		Vector2(0.125, 0.06), Vector2(0.165, 0.09), 6)


func _arm(word: String, side: float, dressed: bool) -> void:
	var upper := word + "UpperArm"
	var lower := word + "LowerArm"
	var hand := word + "Hand"
	var limb := STEEL if dressed else SKIN
	var grow := 1.12 if dressed else 1.0

	if dressed:
		# The pauldron: the wide shoulder of an OSRS platebody.
		_prism(upper, STEEL, _x(side, 0.10, 1.175), _x(side, 0.30, 1.16),
			Vector2(0.16, 0.20), Vector2(0.11, 0.14), 6)
		_prism(upper, STEEL_DARK, _x(side, 0.285, 1.16), _x(side, 0.305, 1.16),
			Vector2(0.118, 0.148), Vector2(0.118, 0.148), 6)
	else:
		_prism(upper, SHIRT, _x(side, 0.12, 1.15), _x(side, 0.27, 1.15),
			Vector2(0.13, 0.15), Vector2(0.115, 0.13), 6)

	_prism(upper, limb, _x(side, 0.165, 1.15), _x(side, 0.37, 1.15),
		Vector2(0.085, 0.09) * grow, Vector2(0.075, 0.08) * grow, 6)
	_prism(lower, limb, _x(side, 0.345, 1.15), _x(side, 0.555, 1.15),
		Vector2(0.088, 0.092) * grow, Vector2(0.058, 0.062) * grow, 6)
	_prism(lower, STEEL_DARK if dressed else BAND, _x(side, 0.50, 1.15), _x(side, 0.547, 1.15),
		Vector2(0.07, 0.074) * grow, Vector2(0.066, 0.07) * grow, 6)
	_prism(hand, SKIN, _x(side, 0.54, 1.15), _x(side, 0.60, 1.15),
		Vector2(0.04, 0.062), Vector2(0.046, 0.08), 4)
	_prism(hand, SKIN, _x(side, 0.60, 1.15), _x(side, 0.655, 1.15),
		Vector2(0.046, 0.08), Vector2(0.026, 0.055), 4)


func _leg(word: String, side: float, dressed: bool) -> void:
	var upper := word + "UpperLeg"
	var lower := word + "LowerLeg"
	var foot := word + "Foot"
	var limb := STEEL if dressed else TROUSERS
	var grow := 1.1 if dressed else 1.0
	var x := side * 0.1

	_prism(upper, limb, Vector3(x, 0.36, 0), Vector3(x, 0.78, 0),
		Vector2(0.095, 0.105) * grow, Vector2(0.115, 0.135) * grow, 6)
	_prism(lower, limb, Vector3(x, 0.17, 0), Vector3(x, 0.395, 0),
		Vector2(0.085, 0.09) * grow, Vector2(0.10, 0.11) * grow, 6)

	if dressed:
		# The knee plate.
		_prism(lower, STEEL_DARK, Vector3(x, 0.335, 0.035), Vector3(x, 0.415, 0.035),
			Vector2(0.075, 0.06), Vector2(0.085, 0.07), 4)

	_prism(lower, STEEL_DARK if dressed else CUFF, Vector3(x, 0.135, 0), Vector3(x, 0.20, 0),
		Vector2(0.095, 0.10), Vector2(0.12, 0.128), 6)
	_prism(lower, STEEL if dressed else BOOT, Vector3(x, 0.0, 0), Vector3(x, 0.15, 0),
		Vector2(0.075, 0.085), Vector2(0.085, 0.09), 6)
	_prism(foot, STEEL if dressed else BOOT, Vector3(x, 0.036, -0.055), Vector3(x, 0.02, 0.17),
		Vector2(0.088, 0.072), Vector2(0.075, 0.036), 4, UP)


## A sword in the right hand, in the space of the hand socket: the length
## along +Y, and the flat of the blade to +Z.
func _sword() -> void:
	var key := "hand_r|socket"
	var diamond := -TAU / 8.0

	_prism(key, BLADE, Vector3(0, 0.055, 0), Vector3(0, 0.50, 0),
		Vector2(0.062, 0.018), Vector2(0.05, 0.015), 4, FRONT, diamond)
	_prism(key, BLADE, Vector3(0, 0.50, 0), Vector3(0, 0.60, 0),
		Vector2(0.05, 0.015), Vector2(0.0, 0.0), 4, FRONT, diamond)
	_prism(key, STEEL_DARK, Vector3(-0.09, 0.045, 0), Vector3(0.09, 0.045, 0),
		Vector2(0.032, 0.036), Vector2(0.032, 0.036), 4)
	_prism(key, LEATHER, Vector3(0, -0.07, 0), Vector3(0, 0.035, 0),
		Vector2(0.03, 0.03), Vector2(0.03, 0.03), 6)
	_prism(key, STEEL_DARK, Vector3(0, -0.11, 0), Vector3(0, -0.088, 0),
		Vector2(0.0, 0.0), Vector2(0.048, 0.048), 4, FRONT, diamond)
	_prism(key, STEEL_DARK, Vector3(0, -0.088, 0), Vector3(0, -0.066, 0),
		Vector2(0.048, 0.048), Vector2(0.02, 0.02), 4, FRONT, diamond)


## A kite shield in the left hand. The long axis goes along the arm, and
## the face goes to +Z of the hand socket: out of the back of the hand.
func _shield(rig: FigureRig) -> void:
	var socket := rig.global_rest_of("hand_l").basis.orthonormalized()
	var along: Vector3 = socket.inverse() * Vector3(-1.0, 0.0, 0.0)
	var face := Vector3(0.0, 0.0, 1.0)
	var basis := Basis(along.cross(face), along, face)
	var origin := along * 0.09 + face * 0.045
	var key := "hand_l|socket"

	_prism(key, STEEL, origin, origin + basis * Vector3(0, 0.20, 0),
		Vector2(0.30, 0.03), Vector2(0.27, 0.03), 4, basis * FRONT)
	_prism(key, STEEL, origin, origin + basis * Vector3(0, -0.27, 0),
		Vector2(0.30, 0.03), Vector2(0.0, 0.02), 4, basis * FRONT)
	_prism(key, STEEL_DARK, origin + basis * Vector3(0, 0.17, 0.0),
		origin + basis * Vector3(0, 0.205, 0.0),
		Vector2(0.285, 0.04), Vector2(0.275, 0.04), 4, basis * FRONT)
	_prism(key, GOLD, origin + basis * Vector3(0, -0.02, 0.012),
		origin + basis * Vector3(0, -0.02, 0.026),
		Vector2(0.11, 0.11), Vector2(0.08, 0.08), 4, basis * UP, -TAU / 8.0)


func _x(side: float, x: float, y: float) -> Vector3:
	return Vector3(side * x, y, 0.0)


# ─── The one new shape ──────────────────────────────────────────────────────

## A tapered block with flat faces: `sides` sides, the size `bottom` at `a`
## and the size `top` at `b`. A size is the width and the depth. `front` is
## the direction of the depth.
func _prism(key: String, color: Color, a: Vector3, b: Vector3, bottom: Vector2,
		top: Vector2, sides: int, front := FRONT, turn := 0.0) -> void:
	if not key.contains("|"):
		key += "|figure"

	if not _tools.has(key):
		_tools[key] = SurfaceTool.new()
		_tools[key].begin(Mesh.PRIMITIVE_TRIANGLES)

	var tool: SurfaceTool = _tools[key]
	var axis := (b - a).normalized()
	var depth := (front - axis * front.dot(axis)).normalized()
	var width := axis.cross(depth)
	var low := PackedVector3Array()
	var high := PackedVector3Array()
	var most_cos := 0.0
	var most_sin := 0.0

	for index in sides:
		var angle := turn + (index + 0.5) * TAU / sides

		most_cos = maxf(most_cos, absf(cos(angle)))
		most_sin = maxf(most_sin, absf(sin(angle)))

	for index in sides:
		var angle := turn + (index + 0.5) * TAU / sides
		var unit := Vector2(cos(angle) / most_cos, sin(angle) / most_sin) * 0.5

		low.append(a + width * unit.x * bottom.x + depth * unit.y * bottom.y)
		high.append(b + width * unit.x * top.x + depth * unit.y * top.y)

	var centre := (a + b) * 0.5

	for index in sides:
		var next := (index + 1) % sides

		_triangle(tool, color, low[index], low[next], high[next], centre)
		_triangle(tool, color, low[index], high[next], high[index], centre)
		_triangle(tool, color, a, low[index], low[next], centre)
		_triangle(tool, color, b, high[index], high[next], centre)


func _triangle(tool: SurfaceTool, color: Color, p0: Vector3, p1: Vector3, p2: Vector3,
		centre: Vector3) -> void:
	var normal := (p2 - p0).cross(p1 - p0)

	if normal.length() < 1e-9:
		return

	if normal.dot((p0 + p1 + p2) / 3.0 - centre) < 0.0:
		var keep := p1

		p1 = p2
		p2 = keep
		normal = -normal

	normal = normal.normalized()

	for point: Vector3 in [p0, p1, p2]:
		tool.set_color(color)
		tool.set_normal(normal)
		tool.add_vertex(point)

	_triangles += 1


# ─── The poses, the reference, and the stage ────────────────────────────────

## The walk clip at one moment, or a stand with each arm down.
func _pose(figure: Node3D, rig: FigureRig, clip: Animation) -> void:
	var skeleton := FigureBuilder.skeleton_of(figure)

	if clip != null:
		FigureClips.pose(skeleton, clip, clip.length * 0.25)
		return

	for side: float in [1.0, -1.0]:
		var word := "Left" if side > 0.0 else "Right"
		var parent := rig.global_rest_of(word + "Shoulder").basis
		var rest := rig.global_rest_of(word + "UpperArm").basis
		var turn := Basis(Vector3(0.0, 0.0, 1.0), -side * ARM_DOWN)
		var pose := parent.inverse() * turn * rest

		skeleton.set_bone_pose_rotation(skeleton.find_bone(word + "UpperArm"),
			pose.get_rotation_quaternion())


func _reference() -> Node3D:
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	var holder := Node3D.new()

	document.append_from_file(REFERENCE, state)

	var model: Node3D = document.generate_scene(state)
	# The bounds of the file, from the first run of this script.
	var low := -0.046885
	var height := 1.609385
	var size := 1.45 / height

	model.scale = Vector3.ONE * size
	model.position = Vector3(0.0, -low * size, -0.043 * size)
	holder.add_child(model)

	return holder


func _row(title: String, make: Callable) -> Image:
	var viewport := SubViewport.new()
	var count := TURNS.size() + 1
	var label := Label.new()

	viewport.size = PIXELS
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.msaa_3d = Viewport.MSAA_4X
	root.add_child(viewport)
	_add_stage(viewport, count)

	label.text = title
	label.position = Vector2(40, 30)
	label.add_theme_font_size_override("font_size", 44)
	viewport.add_child(label)

	for index in count:
		var figure: Node3D = make.call(index)

		if figure == null:
			continue

		figure.position.x = (index - (count - 1) * 0.5) * SPACING
		figure.rotation.y = TURNS[index] if index < TURNS.size() else PI / 4.0
		viewport.add_child(figure)

		if figure.has_meta("pose"):
			_pose(figure, figure.get_meta("pose")[0], figure.get_meta("pose")[1])

	for _frame in 4:
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

	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.keep_aspect = Camera3D.KEEP_WIDTH
	camera.size = count * SPACING + 0.4
	camera.position = Vector3(0.0, 0.8, 6.0)
	sun.rotation = Vector3(-0.9, 0.6, 0.0)
	sun.shadow_enabled = true
	floor_mesh.size = Vector2(count * SPACING + 2.0, 6.0)
	floor_material.albedo_color = Color(0.26, 0.28, 0.33)
	floor_node.mesh = floor_mesh
	floor_node.material_override = floor_material
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color(0.2, 0.22, 0.27)
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color(0.6, 0.6, 0.65)

	for node: Node in [camera, sun, floor_node, environment]:
		viewport.add_child(node)
