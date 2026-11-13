// The brightness of the world pane: a gamma curve over the finished picture
// of the 3D world. WorldBrightness puts it on the SubViewportContainer of the
// pane. Thus, the HUD over the pane keeps its colours.
//
// COLOR holds the picture of the viewport here, in sRGB. A brightness of 1.0
// changes no pixel. A brightness above 1.0 lifts the dark tones the most, and
// white stays white. ClientSettings clamps the value. The floor below only
// keeps a brightness of 0 from a division by zero.
shader_type canvas_item;

const float LOWEST_BRIGHTNESS = 0.01;

uniform float brightness = 1.0;

void fragment() {
	float exponent = 1.0 / max(brightness, LOWEST_BRIGHTNESS);

	COLOR.rgb = pow(COLOR.rgb, vec3(exponent));
}
