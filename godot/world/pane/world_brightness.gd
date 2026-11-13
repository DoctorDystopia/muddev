class_name WorldBrightness
extends RefCounted
## How bright the world pane draws: the Brightness slider of Options, as a
## gamma curve over the finished picture of the 3D world.
##
## [ClientSettings] stores what the player chose. This file puts it on the
## pane. `world_brightness.gdshader` owns the curve.
##
## ## Why a curve over the picture
##
## A spike in the Compatibility renderer measured four ways on 10/29/2026.
## Only this one lifts the dark tones and keeps the edge of the fog:
##
## | Way | Result |
## |---|---|
## | `Environment.adjustment_*` | The scene goes through an 8-bit linear buffer. The dark tones lose most of their steps, at 1.0 too |
## | `tonemap_exposure` | The lit surfaces move, and the background does not. The background is the fog colour, so the horizon shows a seam |
## | The light energy of the look | The same seam. It also goes through [method AreaLook.apply_to], which the Look tab shares, and the baked lamp light does not follow it |
## | A shader on the pane | Every pixel of the pane moves on one curve, the background with the rest |
##
## The shader works on the SubViewportContainer, not on the SubViewport. The
## texture of the viewport does not change, so a reader of that texture does
## not see the setting.
##
## ## No material at 1.0
##
## A brightness of 1.0 takes the material off the pane. The default picture
## is then the same as before the setting, pixel for pixel, and it costs
## nothing. Any other value costs one `pow` for each pixel of the quad that
## the pane draws anyway.
##
## ## The material of the pane belongs to this file
##
## [method apply] replaces any material on the pane. Nothing else sets one.
##
## A RefCounted with only static members. Nothing makes an instance of it.

const SHADER := preload("res://world/pane/world_brightness.gdshader")

## The uniform of the shader that takes [member ClientSettings.brightness].
const PARAMETER := "brightness"

## The brightness that changes no pixel: x to the power 1 is x. It is a fact
## of the curve, not the shipped default. Thus, a new default still gets the
## material when it needs one.
const UNCHANGED := 1.0


## Put `brightness` on `pane`, the container of the world viewport. A second
## call keeps the material of the first, so a slider drag makes one material.
static func apply(pane: CanvasItem, brightness: float) -> void:
	if is_equal_approx(brightness, UNCHANGED):
		pane.material = null
		return

	var material := pane.material as ShaderMaterial

	if material == null or material.shader != SHADER:
		material = ShaderMaterial.new()
		material.shader = SHADER
		pane.material = material

	material.set_shader_parameter(PARAMETER, brightness)
