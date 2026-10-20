// The material of the ground, the walls, the water, and the props of the
// tile world. The client and the terrain editor both draw with it, through
// TerrainMaterial.
//
// The vertex colour is the albedo, as the StandardMaterial3D before it. The
// surface is rough, and the flat shading comes from the mesh, which gives
// each triangle its own normal.
//
// CUSTOM0 is the baked lamp light of the vertex: the colour that the lamps
// near it add, from TileLights. It goes out as emission, so it shows in a
// dark area, where the sun and the ambient light give the albedo nothing.
// A mesh with no CUSTOM0 array reads zeros, and draws as before.
//
// The tint is the colour of a ghost plane in the editor. The game leaves it
// white.
shader_type spatial;

uniform vec4 tint : source_color = vec4(1.0, 1.0, 1.0, 1.0);

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
}
