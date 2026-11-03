extends Node
## Unit tests for WorldBrightness: the material that the brightness puts on
## the world pane.
##
##     godot --headless --path godot res://tests/test_world_brightness.tscn
##
## Needs nothing running. A headless run draws nothing, so this test checks
## the material and its uniform. It cannot check the pixels of the curve.

var _failures := 0


func _ready() -> void:
	_the_unchanged_brightness_puts_no_material_on_the_pane()
	_another_brightness_puts_the_shader_and_its_value_on_the_pane()
	_a_second_value_keeps_the_first_material()
	_the_unchanged_brightness_takes_the_material_off_again()
	_the_shader_names_the_uniform_that_the_owner_writes()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: world_brightness")
	get_tree().quit(0)


## The default picture is the picture from before the setting, at no cost.
func _the_unchanged_brightness_puts_no_material_on_the_pane() -> void:
	var pane := SubViewportContainer.new()

	WorldBrightness.apply(pane, WorldBrightness.UNCHANGED)
	_expect(pane.material == null, "a brightness of 1 puts no material on the pane")
	pane.free()


func _another_brightness_puts_the_shader_and_its_value_on_the_pane() -> void:
	var pane := SubViewportContainer.new()
	var brighter := ClientSettings.MAX_BRIGHTNESS

	WorldBrightness.apply(pane, brighter)

	var material := pane.material as ShaderMaterial

	_expect(material != null and material.shader == WorldBrightness.SHADER,
		"another brightness puts the brightness shader on the pane")
	_expect(material != null and is_equal_approx(
		float(material.get_shader_parameter(WorldBrightness.PARAMETER)), brighter),
		"with the brightness as its uniform")
	pane.free()


## A slider drag calls the owner on each step. One material for the drag,
## not one for each step.
func _a_second_value_keeps_the_first_material() -> void:
	var pane := SubViewportContainer.new()

	WorldBrightness.apply(pane, ClientSettings.MAX_BRIGHTNESS)

	var first := pane.material

	WorldBrightness.apply(pane, ClientSettings.MIN_BRIGHTNESS)

	var material := pane.material as ShaderMaterial

	_expect(material == first, "a second value keeps the first material")
	_expect(is_equal_approx(
		float(material.get_shader_parameter(WorldBrightness.PARAMETER)),
		ClientSettings.MIN_BRIGHTNESS), "and writes the new value into it")
	pane.free()


func _the_unchanged_brightness_takes_the_material_off_again() -> void:
	var pane := SubViewportContainer.new()

	WorldBrightness.apply(pane, ClientSettings.MAX_BRIGHTNESS)
	WorldBrightness.apply(pane, WorldBrightness.UNCHANGED)
	_expect(pane.material == null, "a return to 1 takes the material off")
	pane.free()


## A uniform name that the shader does not declare is a write that Godot
## drops with no warning. The slider then moves and the world does not.
func _the_shader_names_the_uniform_that_the_owner_writes() -> void:
	var names: Array[String] = []

	for uniform: Dictionary in WorldBrightness.SHADER.get_shader_uniform_list():
		names.append(str(uniform.get("name", "")))

	_expect(names.has(WorldBrightness.PARAMETER),
		"the shader declares the uniform %s" % WorldBrightness.PARAMETER)


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
