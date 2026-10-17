extends Node3D
## The crowd cost of the figure of the game (DESIGN-0014 section 20).
##
##     godot --path godot --rendering-driver opengl3 res://tests/figure_crowd_bench.tscn -- counts=1,11,25,50,80,120
##
## It needs a renderer, so it opens a window. It is no headless test, as
## `spike_figure_bench` is none. It builds each figure as the game builds
## it: [FigureLibrary] with the served `figure.json` of the repository, one
## [FigureBuilder] node for each figure (the attached version), each figure
## in the walk clip, at its own time. The stage has a sun with a shadow, as
## `scenes/world.tscn` has.
##
## Each count prints one `FIGURE_CROWD` line of JSON: the mean frame time
## and the worst frame time in milliseconds, the draw calls, and the
## objects. `out=<path>` also writes the lines to a file.
##
## `--rendering-driver opengl3_angle` gives the path of a browser on
## Windows. For the web export, export this scene in a scratch copy, as
## section 12.6 of DESIGN-0014 says for the spike.

const DEFAULT_COUNTS := [1, 11, 25, 50, 80, 120]
const WARM_FRAMES := 40
const SAMPLE_FRAMES := 180

## The figures stand in a grid, one tile apart, as on the tile world.
const SPACING := 1.0

var _camera: Camera3D
var _crowd: Node3D
var _library := FigureLibrary.new()
var _lines := PackedStringArray()


func _ready() -> void:
	var options := _options()
	var counts: Array = options.get("counts", DEFAULT_COUNTS)
	var text := FileAccess.get_file_as_string(FigureStore.repo_models_directory()
		.path_join(FigureSet.FILE_NAME))

	# The frame time of the work, not of the screen: no vsync, no frame cap.
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	add_child(_library)
	_build_stage()

	if not _library.take_text(text):
		printerr("FAIL: the figure set does not read")
		get_tree().quit(1)
		return

	_report("driver", {"name": RenderingServer.get_current_rendering_driver_name(),
		"method": RenderingServer.get_current_rendering_method(),
		"adapter": RenderingServer.get_video_adapter_name()})

	for count: int in counts:
		_report("crowd", await _measure(count))

	if options.has("out"):
		var file := FileAccess.open(options["out"], FileAccess.WRITE)

		file.store_string("\n".join(_lines) + "\n")
		file.close()

	get_tree().quit(0)


## `key=value` arguments after `--`. `counts` is a list of numbers.
func _options() -> Dictionary:
	var found := {}

	for argument: String in OS.get_cmdline_user_args():
		var pair := argument.split("=", true, 1)

		if pair.size() != 2:
			continue

		if pair[0] == "counts":
			found["counts"] = Array(pair[1].split(",")).map(func(n: String) -> int: return int(n))
		else:
			found[pair[0]] = pair[1]

	return found


## Stand `count` figures in a grid, each in the walk clip at its own time,
## and measure the frames.
func _measure(count: int) -> Dictionary:
	var side := ceili(sqrt(float(count)))
	var body_types := _library.figure_set.rigs.keys()

	for child: Node in _crowd.get_children():
		child.free()

	for index in count:
		var holder := _library.build(body_types[index % body_types.size()], {})

		holder.position = Vector3((index % side - side / 2.0) * SPACING, 0.0,
			(index / side - side / 2.0) * SPACING)
		_crowd.add_child(holder)
		FigureLibrary.play(holder, FigureStances.ACTION_WALK)
		FigureClips.player_of(FigureLibrary.figure_of(holder)).seek(randf(), true)

	_look_at_crowd(side * SPACING)
	await _frames(WARM_FRAMES)

	return await _sample(count)


func _sample(count: int) -> Dictionary:
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

	return {"figures": count, "frame_ms": snappedf(mean, 0.01),
		"worst_frame_ms": snappedf(worst / 1000.0, 0.01),
		"fps": snappedf(1000.0 / maxf(mean, 0.001), 0.1), "draw_calls": draws,
		"objects": int(RenderingServer.get_rendering_info(
			RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME))}


func _build_stage() -> void:
	var sun := DirectionalLight3D.new()
	var world := WorldEnvironment.new()
	var environment := Environment.new()

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
	_crowd = Node3D.new()
	add_child(_crowd)


func _look_at_crowd(extent: float) -> void:
	_camera.position = Vector3(0.0, extent * 0.75 + 1.5, extent * 0.85 + 1.5)
	_camera.look_at(Vector3.ZERO)


func _frames(count: int) -> void:
	for _index in count:
		await get_tree().process_frame


func _report(case: String, values: Dictionary) -> void:
	values["case"] = case

	var line := "FIGURE_CROWD " + JSON.stringify(values)

	print(line)
	_lines.append(line)
