class_name TerrainMaterial
extends RefCounted
## The material of the tile world, and the mesh format that it reads.
##
## The client ([TerrainView]) and the terrain editor ([TerrainWorld]) both
## draw the ground, the walls, the water, and the props with one shader,
## `terrain.gdshader`. The vertex colour is the albedo. The CUSTOM0 array of
## a mesh is its baked lamp light ([TileLights]), and the shader sends it
## out as emission. Thus a lamp lights the ground in a dark area, where the
## sun gives the albedo nothing.
##
## Until 10/18/2026, both drew with a StandardMaterial3D that took the vertex
## colour as the albedo. A StandardMaterial3D has no emission from a vertex
## array, so the lamp light needed a shader.
##
## ## Why a bake
##
## The project runs the Compatibility renderer, for the web export. There,
## at most 8 omni lights can light one mesh, and the ground of one chunk is
## one mesh of 64 by 64 tiles. Thus a street of 20 lamps gets light from 8
## of them. The bake has no limit, and it costs nothing at runtime. The few
## real lights go to the figures alone ([FigureLights]).

const SHADER := preload("res://world/terrain/terrain.gdshader")

## The format flag of a mesh with a lamp array: three floats for each
## vertex, in CUSTOM0.
const LAMP_FORMAT := Mesh.ARRAY_CUSTOM_RGB_FLOAT << Mesh.ARRAY_FORMAT_CUSTOM0_SHIFT

## The name of the tint uniform of the shader.
const TINT := "tint"


## A new material of the tile world. The game draws with the white tint.
## The editor tints a ghost plane.
static func make(tint := Color.WHITE) -> ShaderMaterial:
	var material := ShaderMaterial.new()

	material.shader = SHADER
	set_tint(material, tint)

	return material


## Change the tint of a material of [method make].
static func set_tint(material: ShaderMaterial, tint: Color) -> void:
	material.set_shader_parameter(TINT, tint)


## Add one triangle surface with a lamp array to `mesh`. `arrays` has the
## vertices, the normals, the colours, and the lamp array in
## [constant Mesh.ARRAY_CUSTOM0]. A surface with no vertex is not added,
## because Godot refuses an empty surface.
static func add_surface(mesh: ArrayMesh, arrays: Array) -> void:
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]

	if vertices.is_empty():
		return

	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays, [], {}, LAMP_FORMAT)


## The surface arrays of a mesh under construction, in the shape that
## [method add_surface] takes.
static func arrays_of(vertices: PackedVector3Array, normals: PackedVector3Array,
		colors: PackedColorArray, lamp: PackedFloat32Array) -> Array:
	var arrays := []

	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_COLOR] = colors
	arrays[Mesh.ARRAY_CUSTOM0] = lamp

	return arrays


## The lamp colour of vertex `index` of a surface, from its arrays. For a
## test.
static func lamp_at(arrays: Array, index: int) -> Color:
	var lamp: PackedFloat32Array = arrays[Mesh.ARRAY_CUSTOM0]
	var at := index * 3

	return Color(lamp[at], lamp[at + 1], lamp[at + 2], 1.0)
