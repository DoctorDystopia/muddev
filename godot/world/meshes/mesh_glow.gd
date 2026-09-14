class_name MeshGlow
extends RefCounted
## Makes a material able to glow without ever changing which shader draws it.
##
## ## Why emission is never switched off
##
## `emission_enabled` is not a value the shader reads. It is part of the key
## [BaseMaterial3D] builds its shader from, so flipping it moves the material to
## a DIFFERENT shader -- and Godot frees a shader the moment its last user moves
## off it. Hover used to flip it both ways, so every hover-on built one shader
## and every hover-off built the other one back.
##
## On the web that build is synchronous and it is not small. Measured 09/13/2026
## in a Chromium WebGL 2 export of Godot 4.7.1: a variant nothing had drawn yet
## stalled one frame for ~1.9 s, and re-hovering a procedural part cost ~52 ms
## on every hover. Writing only the emission colour and energy on a material
## that already had emission on stalled nothing, ever -- those are uniforms,
## the same kind of write the hit flash's albedo tween makes.
##
## So a material is made glow-ready ONCE, where it is created, and every glow
## after that is a uniform write.
##
## ## Resting is the AUTHORED emission, not none
##
## A model exported with an emissive surface keeps it: [method prepare] records
## what the material emitted before this file touched it, and [method rest] puts
## exactly that back. For nearly every material that is black at zero energy,
## which draws identically to emission switched off.
##
## ## Two callers, one rule
##
## Materials come from two places -- [MeshPalette] builds them for procedural
## parts, [ModelLoader] duplicates them off fetched art -- and both call
## [method prepare]. [method light] deliberately does NOT switch emission on for
## a material that skipped it: that would quietly reintroduce the compile.
## `test_entity_pool` asserts every material a drawn entity carries is ready.

## Where a material's resting emission is remembered.
##
## Metadata rather than a side table, because it has to travel with the
## material: [method Resource.duplicate] copies it, so a prepared prototype's
## copies rest correctly too.
##
## Plain strings, not `&"..."` literals: `test_theme` reads every StringName
## literal in the project as a theme type variation, and these are not one.
const _META_REST_COLOR := "blackout_glow_rest_color"
const _META_REST_ENERGY := "blackout_glow_rest_energy"

## What a material that authored no emission rests at.
const _NO_EMISSION_COLOR := Color.BLACK
const _NO_EMISSION_ENERGY := 0.0


## Switch emission on for good, resting at whatever the material authored.
##
## Safe to call twice: a material already prepared keeps its recorded rest
## rather than recording its current glow as the new one.
static func prepare(material: BaseMaterial3D) -> void:
	if material == null or is_ready(material):
		return

	var authored := material.emission_enabled
	var rest_color := material.emission if authored else _NO_EMISSION_COLOR
	var rest_energy := (material.emission_energy_multiplier if authored
		else _NO_EMISSION_ENERGY)

	material.set_meta(_META_REST_COLOR, rest_color)
	material.set_meta(_META_REST_ENERGY, rest_energy)
	material.emission = rest_color
	material.emission_energy_multiplier = rest_energy
	material.emission_enabled = true


## Whether a material can glow without a shader change.
static func is_ready(material: BaseMaterial3D) -> bool:
	if material == null:
		return false

	var recorded := material.has_meta(_META_REST_ENERGY)

	return recorded and material.emission_enabled


## Glow in `color` at `energy`. A uniform write only.
static func light(material: BaseMaterial3D, color: Color,
		energy: float) -> void:
	if not is_ready(material):
		return

	material.emission = color
	material.emission_energy_multiplier = energy


## Put the authored emission back. A uniform write only.
static func rest(material: BaseMaterial3D) -> void:
	if not is_ready(material):
		return

	material.emission = material.get_meta(_META_REST_COLOR, _NO_EMISSION_COLOR)
	material.emission_energy_multiplier = material.get_meta(
		_META_REST_ENERGY, _NO_EMISSION_ENERGY)


## Whether a material is glowing above its rest right now.
static func is_lit(material: BaseMaterial3D) -> bool:
	if not is_ready(material):
		return false

	var rest_energy: float = material.get_meta(_META_REST_ENERGY,
		_NO_EMISSION_ENERGY)
	var rest_color: Color = material.get_meta(_META_REST_COLOR,
		_NO_EMISSION_COLOR)
	var energy_moved := not is_equal_approx(
		material.emission_energy_multiplier, rest_energy)
	var colour_moved := not material.emission.is_equal_approx(rest_color)

	return energy_moved or colour_moved
