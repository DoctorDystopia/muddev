// The material of a ghost plane in the terrain editor: a plane other than
// the edited plane, in the ghost colour, and see-through. A player never
// sees it. TerrainOverlay.ghost_material makes it.
//
// The mesh format is that of terrain.gdshader: the vertex colour is the
// albedo, and CUSTOM0 is the baked lamp light. The tint is the "ghost"
// mark of the Look tab. Only its colour counts. The World tab sets the
// opacity.
//
// The ghost writes no depth. Thus each ghost surface shows through the
// ghost surfaces in front of it: the walls of a room on the plane above
// show through its roof. The opaque ground of the edited plane still hides
// a ghost under it, because the depth test stays on.
shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_back;

uniform vec4 tint : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform float opacity : hint_range(0.0, 1.0) = 0.4;

varying vec3 lamp;

void vertex() {
	lamp = CUSTOM0.rgb;
}

void fragment() {
	vec3 albedo = COLOR.rgb * tint.rgb;

	ALBEDO = albedo;
	ROUGHNESS = 1.0;
	METALLIC = 0.0;
	EMISSION = lamp * albedo;
	ALPHA = opacity;
}
