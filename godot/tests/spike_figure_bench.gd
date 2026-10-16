extends Node3D
## The renderer half of the Phase W0 spike of DESIGN-0014.
##
## It needs a window, so it does not run with `--headless`:
##
##     godot --path godot --rendering-driver opengl3 res://tests/spike_figure_bench.tscn -- jobs=compare,shots,bench out=C:/some/dir
##     godot --path godot --rendering-driver opengl3_angle res://tests/spike_figure_bench.tscn -- jobs=bench
##
## On the web export, the page address gives the same words:
## `index.html?jobs=compare,bench&counts=50,100`.
##
## ## The jobs
##
## - `compare` draws one attached figure and one merged figure in the same
##   pose, and counts the pixels that differ.
## - `shots` saves pictures of the two body types in the walk clip, for a
##   person to judge.
## - `bench` draws a crowd in each version, and measures the frame time and
##   the draw calls.
##
## Each result is one `SPIKE_RESULT` line of JSON.

const Spike := preload("res://tests/spike_figure.gd")

const SWORD_MODEL := "web/static/webclient/models/items/rusty_scrap_shortsword.glb"

## The versions of a crowd. `shared` draws each part of the whole crowd with
## one [MultiMesh], so the draw count does not grow with the crowd. The
## `_still` suffix gives a version with no clip, to measure the cost of the
## moved pose alone.
const VERSION_ATTACHED := "attached"
const VERSION_MERGED := "merged"
const VERSION_SHARED := "shared"
const STILL := "_still"
const DEFAULT_VERSIONS := [VERSION_ATTACHED, VERSION_MERGED, VERSION_SHARED]

const DEFAULT_JOBS := ["compare", "bench"]
const DEFAULT_COUNTS := [50, 100, 200, 400]

const WINDOW_SIZE := Vector2i(1280, 720)
const WARM_FRAMES := 40
const SAMPLE_FRAMES := 180
const SETTLE_FRAMES := 4

## The size of a figure in the crowd, and the distance between two figures.
## A figure of the rig is about 1.6 units tall, and a tile is 1 unit.
const FIGURE_SCALE := 0.6
const SPACING := 1.0

## Half the side of the box that the engine uses to cull a shared part.
const SHARED_BOUNDS := 40.0

const LIMB_SCALE := 0.85
const COMPARE_SECONDS := 0.3
const SHOT_TIMES := [0.0, 0.125, 0.25, 0.375]

## A color channel must differ by more than this for a pixel to count.
const PIXEL_TOLERANCE := 12
const RGB := 3

var _camera: Camera3D
var _holder: Node3D
var _out := ""
var _random := RandomNumberGenerator.new()

## The `shared` version: the skeleton of each figure, the multimesh of each
## part, and the bone and the place of each part.
var _crowd: Array[Skeleton3D] = []
var _crowd_meshes: Array[MultiMesh] = []
var _crowd_bones := PackedInt32Array()
var _crowd_places: Array[Transform3D] = []


func _ready() -> void:
	var words := _words()
	var jobs: Array = words.get("jobs", DEFAULT_JOBS)

	_out = "" if not words.has("out") else str(words["out"][0])
	Spike.light_shapes = words.has("light")
	_random.seed = 20261012
	_build_stage()

	if not OS.has_feature("web"):
		get_window().size = WINDOW_SIZE
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)

	Engine.max_fps = 0
	await _frames(SETTLE_FRAMES)
	_report("info", {
		"adapter": RenderingServer.get_video_adapter_name(),
		"api": RenderingServer.get_video_adapter_api_version(),
		"driver": RenderingServer.get_current_rendering_driver_name(),
		"method": RenderingServer.get_current_rendering_method(),
		"os": OS.get_name(),
		"window": [get_viewport().size.x, get_viewport().size.y],
	})

	if jobs.has("compare"):
		await _compare()

	if jobs.has("shots"):
		await _shots()

	if jobs.has("bench"):
		await _bench(words.get("counts", DEFAULT_COUNTS),
			words.get("versions", DEFAULT_VERSIONS))

	print("SPIKE_DONE")

	if not OS.has_feature("web"):
		get_tree().quit(0)


# ─── The jobs ───────────────────────────────────────────────────────────────

func _compare() -> void:
	var rig := Spike.rig_from_profile("body_1")
	var sword := _load_sword()
	var parts := Spike.mannequin_parts(rig, sword)
	var library := Spike.walk_library(rig)
	var attached := Spike.build_attached(rig, parts, Spike.figure_material())
	var merged := Spike.build_merged(rig, parts, Spike.figure_material())

	_look_at_one_figure()

	for figure: Node3D in [attached, merged]:
		_holder.add_child(figure)
		_pose(figure, library, COMPARE_SECONDS)

	attached.visible = false
	merged.visible = false

	var empty := await _picture("")

	attached.visible = true

	var first := await _picture("compare_attached")

	attached.visible = false
	merged.visible = true

	var second := await _picture("compare_merged")
	var figure_pixels := _different_pixels(first, empty)
	var different := _different_pixels(first, second)

	_report("compare", {
		"model_part": sword != null,
		"figure_pixels": figure_pixels,
		"different_pixels": different,
		"merged_figure_pixels": _different_pixels(second, empty),
	})

	if sword != null:
		sword.free()

	_clear()


func _shots() -> void:
	var first_rig := Spike.rig_from_profile("body_1")
	var second_rig := Spike.rig_from_profile("body_2", LIMB_SCALE)
	var library := Spike.walk_library(first_rig)
	var first := Spike.build_attached(first_rig, Spike.mannequin_parts(first_rig),
		Spike.figure_material())
	var second := Spike.build_attached(second_rig, Spike.mannequin_parts(second_rig),
		Spike.figure_material())

	_look_at_one_figure()
	first.position.x = -0.55
	first.rotation.y = 0.9
	second.position.x = 0.55
	second.rotation.y = 0.9
	_holder.add_child(first)
	_holder.add_child(second)

	for index in SHOT_TIMES.size():
		_pose(first, library, SHOT_TIMES[index])
		_pose(second, library, SHOT_TIMES[index])
		await _picture("walk_%d" % index)

	_clear()


func _bench(counts: Array, versions: Array) -> void:
	var rig := Spike.rig_from_profile("body_1")
	var parts := Spike.mannequin_parts(rig)
	var library := Spike.walk_library(rig)
	var mesh := Spike.merged_mesh(rig, parts)

	_report("figure", {
		"parts": parts.size(),
		"triangles": mesh.surface_get_array_index_len(0) / RGB,
		"vertices": mesh.surface_get_array_len(0),
		"light_shapes": Spike.light_shapes,
	})

	for count: Variant in counts:
		for version: Variant in versions:
			_fill(str(version), int(count), rig, parts, mesh, library)

			var result := await _measure(str(version), int(count))

			_report("bench", result)
			_clear()
			await _frames(SETTLE_FRAMES)


## Put `count` figures of one version on a square grid, each at its own time
## of the walk clip.
func _fill(version: String, count: int, rig: Dictionary, parts: Array,
		mesh: ArrayMesh, library: AnimationLibrary) -> void:
	var side := ceili(sqrt(count))
	var half := (side - 1) * SPACING * 0.5
	var kind := version.trim_suffix(STILL)

	if kind == VERSION_SHARED:
		_share_parts(rig, parts, count)

	for index in count:
		var figure: Node3D

		if kind == VERSION_MERGED:
			figure = Spike.build_merged(rig, parts, Spike.figure_material(), mesh)
		elif kind == VERSION_SHARED:
			figure = Spike.build_attached(rig, [], null)
			_crowd.append(figure.get_node(Spike.SKELETON_NAME) as Skeleton3D)
		else:
			figure = Spike.build_attached(rig, parts, Spike.figure_material())

		figure.scale = Vector3.ONE * FIGURE_SCALE
		figure.position = Vector3((index % side) * SPACING - half, 0.0,
			(index / side) * SPACING - half)
		_holder.add_child(figure)

		if version.ends_with(STILL):
			continue

		var player := Spike.add_player(figure, library)

		player.play(Spike.WALK_CLIP)
		player.seek(_random.randf() * Spike.WALK_SECONDS, true)

	_look_at_crowd(side * SPACING)


## Make one multimesh for each part, with one instance for each figure.
func _share_parts(rig: Dictionary, parts: Array, count: int) -> void:
	var skeleton := Spike.skeleton_from_rig(rig)
	var material := Spike.figure_material()

	for part: Dictionary in parts:
		var multimesh := MultiMesh.new()
		var instance := MultiMeshInstance3D.new()

		multimesh.transform_format = MultiMesh.TRANSFORM_3D
		multimesh.mesh = Spike.mesh_of_soup(part["soup"])
		multimesh.instance_count = count
		multimesh.custom_aabb = AABB(Vector3.ONE * -SHARED_BOUNDS,
			Vector3.ONE * SHARED_BOUNDS * 2.0)
		instance.multimesh = multimesh
		instance.material_override = material
		_holder.add_child(instance)
		_crowd_meshes.append(multimesh)
		_crowd_bones.append(skeleton.find_bone(part["bone"]))
		_crowd_places.append(part["xform"])

	skeleton.free()


## The `shared` version: give each instance of each part the pose of its
## bone. This is the work that a bone attachment does for the other version.
func _process(_delta: float) -> void:
	for figure in _crowd.size():
		var skeleton := _crowd[figure]
		var base := skeleton.global_transform

		for part in _crowd_meshes.size():
			_crowd_meshes[part].set_instance_transform(figure,
				base * skeleton.get_bone_global_pose(_crowd_bones[part])
				* _crowd_places[part])


func _measure(version: String, count: int) -> Dictionary:
	await _frames(WARM_FRAMES)

	var start := Time.get_ticks_usec()
	var worst := 0
	var draws := 0

	for _frame in SAMPLE_FRAMES:
		var before := Time.get_ticks_usec()

		await get_tree().process_frame
		worst = maxi(worst, Time.get_ticks_usec() - before)
		draws = maxi(draws, int(RenderingServer.get_rendering_info(
			RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)))

	var mean := float(Time.get_ticks_usec() - start) / SAMPLE_FRAMES / 1000.0

	return {
		"version": version,
		"figures": count,
		"frame_ms": snappedf(mean, 0.01),
		"worst_frame_ms": snappedf(worst / 1000.0, 0.01),
		"fps": snappedf(1000.0 / maxf(mean, 0.001), 0.1),
		"draw_calls": draws,
		"objects": int(RenderingServer.get_rendering_info(
			RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME)),
		"primitives": int(RenderingServer.get_rendering_info(
			RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)),
	}


# ─── The stage ──────────────────────────────────────────────────────────────

## A camera, a sun with a shadow, a sky color, and a ground. The sun of the
## game also has a shadow (`scenes/world.tscn`).
func _build_stage() -> void:
	var sun := DirectionalLight3D.new()
	var world := WorldEnvironment.new()
	var environment := Environment.new()
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	var soil := StandardMaterial3D.new()

	_camera = Camera3D.new()
	_camera.fov = 50.0
	add_child(_camera)
	_camera.make_current()

	sun.rotation = Vector3(-0.9, 0.6, 0.0)
	sun.shadow_enabled = true
	add_child(sun)

	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.2, 0.22, 0.26)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.6, 0.6, 0.65)
	world.environment = environment
	add_child(world)

	plane.size = Vector2(80.0, 80.0)
	soil.albedo_color = Color(0.32, 0.3, 0.27)
	ground.mesh = plane
	ground.material_override = soil
	add_child(ground)

	_holder = Node3D.new()
	add_child(_holder)


func _look_at_one_figure() -> void:
	_camera.position = Vector3(0.0, 1.0, 3.4)
	_camera.look_at(Vector3(0.0, 0.85, 0.0))


func _look_at_crowd(extent: float) -> void:
	_camera.position = Vector3(0.0, extent * 0.75 + 2.0, extent * 0.85 + 2.0)
	_camera.look_at(Vector3.ZERO)


## Put a figure in the walk clip at `seconds`, and stop it there.
func _pose(figure: Node3D, library: AnimationLibrary, seconds: float) -> void:
	var player := figure.get_node_or_null(Spike.PLAYER_NAME) as AnimationPlayer

	if player == null:
		player = Spike.add_player(figure, library)

	player.play(Spike.WALK_CLIP)
	player.seek(seconds, true)
	player.pause()


## The picture of the view after the scene settles. With a name and an
## output directory, the routine also saves it as a PNG file.
func _picture(file_name: String) -> Image:
	await _frames(SETTLE_FRAMES)
	await RenderingServer.frame_post_draw

	var image := get_viewport().get_texture().get_image()

	if not file_name.is_empty() and not _out.is_empty():
		image.save_png(_out.path_join(file_name + ".png"))

	image.convert(Image.FORMAT_RGB8)

	return image


func _different_pixels(first: Image, second: Image) -> int:
	var left := first.get_data()
	var right := second.get_data()
	var count := 0

	for pixel in left.size() / RGB:
		var at := pixel * RGB

		if absi(left[at] - right[at]) > PIXEL_TOLERANCE \
				or absi(left[at + 1] - right[at + 1]) > PIXEL_TOLERANCE \
				or absi(left[at + 2] - right[at + 2]) > PIXEL_TOLERANCE:
			count += 1

	return count


func _clear() -> void:
	_crowd.clear()
	_crowd_meshes.clear()
	_crowd_bones.clear()
	_crowd_places.clear()

	for child: Node in _holder.get_children():
		child.queue_free()


# ─── The words of the run ───────────────────────────────────────────────────

## The `name=a,b` words of the command line, or of the page address on the
## web export.
func _words() -> Dictionary:
	var raw := PackedStringArray()
	var words := {}

	if OS.has_feature("web"):
		var query := str(JavaScriptBridge.eval("window.location.search", true))

		raw = query.trim_prefix("?").split("&", false)
	else:
		raw = OS.get_cmdline_user_args()

	for word: String in raw:
		var pair := word.split("=")

		if pair.size() == 2:
			words[pair[0]] = Array(pair[1].split(",", false))

	return words


## The sword model from the served tree, or null. The web export has no
## disk, so it draws the shape list sword.
func _load_sword() -> Node3D:
	if OS.has_feature("web"):
		return null

	var project := ProjectSettings.globalize_path("res://")
	var game := project.path_join(ChunkFile.GAME_DIRECTORY_FROM_PROJECT)
	var document := GLTFDocument.new()
	var state := GLTFState.new()

	if document.append_from_file(game.path_join(SWORD_MODEL).simplify_path(), state) != OK:
		return null

	return document.generate_scene(state) as Node3D


func _frames(count: int) -> void:
	for _frame in count:
		await get_tree().process_frame


func _report(case: String, values: Dictionary) -> void:
	values["case"] = case
	print("SPIKE_RESULT ", JSON.stringify(values))
