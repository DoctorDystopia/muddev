class_name TrueTileMark
extends RefCounted
## What a TRUE TILE looks like: a square outline laid on the tile face.
##
## The true tile is the square the SERVER has a character standing on. It is
## the only position any command is resolved against, and while [StepAnimator]
## is sliding a figure between two of them, the figure is not on it. That gap
## is the whole cost of the animation, and this is what pays it back — the
## outline is on screen for exactly as long as the figure is away from the
## square, and goes out when it arrives.
##
## Modelled on the game square OSRS draws, and on the true tile indicator its
## players have used for years:
## <https://oldschool.runescape.wiki/w/Game_square>.
##
## ## One owner, two drawers
##
## [WorldView] draws the observer's own mark as a single node, because there is
## exactly one of them and it is the anchor the camera rig and the aura ring
## already hang off. It draws everyone ELSE's as one MultiMesh, because there
## may be a screenful and each is the same square in a different place. Both
## take their mesh and their material from here, so the two can differ in
## colour and in nothing else.
##
## Purely static builders. Nothing is cached here and the caller holds what it
## builds: two panes asking for one shared resource is how a material gets its
## colour written by whoever drew last.

## The observer's own square, matching the colour the marker has always been.
const COLOR_OBSERVER := Color(0.208, 0.878, 0.753)

## Everyone else's. Deliberately NOT the observer's colour: the one square a
## player needs to find in a fight is their own, and a screen of identical
## outlines is the state that hides it.
const COLOR_ENTITY := Color(0.988, 0.784, 0.310)

## How alpha the outline is drawn at. Visible over any room kind's colour, and
## faint enough that a crowd of them does not become the floor.
const ALPHA := 0.75

## How thick the outline is, in world units, drawn INWARD from the tile edge.
##
## Inward so that the square is the tile, exactly. An outline centred on the
## edge would overhang the neighbour by half its width, which reads as the
## figure being bound for either of two tiles.
const THICKNESS := 0.05

## How far ABOVE the tile face the outline is laid.
##
## The same problem [constant WorldView.TERRAIN_LIFT] solves and the same
## answer: a flat surface drawn exactly on another flat surface is coplanar,
## which is per-pixel flicker rather than a picture. Larger than the terrain's
## lift, because the outline has to sit above the terrain as well as above the
## slab.
const LIFT := 0.012


## One square outline, as a mesh with its own origin at the tile's centre.
##
## `size` is the full side of the tile, so the caller passes what it uses to
## lay tiles out and nothing here has to know how big a tile is.
static func build_mesh(size: float) -> ArrayMesh:
	var outer := size * 0.5
	var inner := maxf(outer - THICKNESS, 0.0)

	var points := PackedVector3Array([
		Vector3(-outer, LIFT, -outer),
		Vector3(outer, LIFT, -outer),
		Vector3(outer, LIFT, outer),
		Vector3(-outer, LIFT, outer),
		Vector3(-inner, LIFT, -inner),
		Vector3(inner, LIFT, -inner),
		Vector3(inner, LIFT, inner),
		Vector3(-inner, LIFT, inner),
	])

	# Four quads, one per side, each as two triangles. Written out rather than
	# built in a loop: eight lines that can be read against the point list beat
	# a loop with two modulo terms that cannot.
	var indices := PackedInt32Array([
		0, 1, 5, 0, 5, 4,
		1, 2, 6, 1, 6, 5,
		2, 3, 7, 2, 7, 6,
		3, 0, 4, 3, 4, 7,
	])

	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = points
	arrays[Mesh.ARRAY_INDEX] = indices

	var mesh := ArrayMesh.new()

	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)

	return mesh


## The material one drawer paints its marks with.
##
## UNSHADED, so the square is the same colour on a lit tile and a shadowed one:
## it is an instrument reading, not part of the scenery, and a player should
## not have to work out whether they are looking at a mark or at a highlight.
##
## CULL_DISABLED because the outline carries no normals — a flat surface built
## from a bare vertex list is front-facing from one side only, and which side
## that is depends on a winding this file should not have to reason about. The
## square is legible from below as well, which is where an orbit camera pitched
## under the horizon looks at it from.
static func build_material(colour: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()

	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.albedo_color = Color(colour, ALPHA)

	return material
