class_name FamilyShapes
extends RefCounted
## What each family LOOKS like, as data. The whole table, and nothing else.
##
## This is tier 2 of the mesh ladder — the shape drawn for anything the server
## names that has no real art. Adding a family is adding one entry here, in the
## same way adding an item is adding one entry to `world/item_database.py`.
## Nothing else in the client needs an edit: [MeshResolver] looks the family up
## rather than branching on it, and [MeshBuilder] reads the parts without
## knowing what a weapon is.
##
## ## Why the key space holds two vocabularies
##
## The keys below are six ITEM FAMILIES (`weapon`, `armor`, ...) and four ASSET
## KINDS (`npc`, `character`, `station`, `gatherable`) in one namespace. That is
## not an accident of this file — it mirrors the server, which collapses them
## deliberately: `_mesh_family` in `systems/statefeed/serializers.py` returns
## the item's family for an item and the KIND itself for anything else, and
## `serialize_entity` sends the result in one `family` field. One lookup key on
## the wire, one table here.
##
## ## Why data and not a builder function per family
##
## The browser writes each of these as twenty lines of imperative geometry
## reaching into a palette block, which makes "what a weapon looks like" and
## "how to build a mesh" the same code. Splitting them means the shapes can be
## read, diffed and adjusted without touching mesh construction, and
## [MeshBuilder] can be tested against parts that describe nothing in
## particular.
##
## ## Everything is roughly one unit across
##
## Every shape here fits inside a unit box, longest axis about 1.0, centred on
## the origin. Tier 1 models are normalised to the same box by [ModelLoader], so
## all three tiers hand back something the same size and each CALLER applies one
## scale for its own screen. That is the fix for the browser's `ENTITY_SCALE` /
## `TILE_PROP_SCALE` / `ITEM_SCALE` spread across three files.
##
## ## The part vocabulary
##
## Every part is a dictionary. `shape` and `color` are required; the rest are
## optional and defaulted by [MeshBuilder]:
##
##     shape         one of the SHAPE_* constants
##     color         a role from [MeshPalette]
##     finish        a FINISH_* from [MeshPalette]; defaults to matte
##     size          Vector3, for SHAPE_BOX
##     radius        float, for sphere / cylinder / cone / faceted shapes
##     radius_top    float, for a tapered cylinder; defaults to `radius`
##     height        float, for cylinder / cone
##     inner         float, for SHAPE_TORUS
##     outer         float, for SHAPE_TORUS
##     offset        Vector3 position within the unit box
##     rotation      Vector3 of radians
##     scale         Vector3, for squashing a primitive out of round
##     open          bool, for a cylinder drawn as a shell (armour)
##     segments      int, to make a primitive deliberately faceted

## Server-owned names, generated from `blackout/systems/statefeed/constants.py`.
##
## The keys of [member SHAPES] are these constants and NOT string literals, for
## the reason CLAUDE.md gives in full: a literal that already has a named
## constant is how "Metalsmith" versus "Metalsmithing" hid every anvil recipe.
## A family renamed server-side breaks this file loudly at parse time instead of
## silently drawing every weapon as a generic box.
const _Const := preload("res://autoload/blackout_constants.gd")

const SHAPE_BOX := "box"
const SHAPE_SPHERE := "sphere"
const SHAPE_CYLINDER := "cylinder"
const SHAPE_CONE := "cone"
const SHAPE_TORUS := "torus"

## A low-segment sphere standing in for a polyhedron.
##
## Godot has no OctahedronMesh or IcosahedronMesh, which the browser uses for
## gems and ore. A SphereMesh with few segments is faceted in the same way and
## reads identically at the size these are drawn — the JS says it plainly, that
## a silhouette is doing all the work and detail is not the point. Recorded as a
## substitution rather than passed off as a match.
const SHAPE_FACETED := "faceted"

## The families with no art of their own, drawn when the server names one.
##
## Ordered as the browser lists them: the six item families first, then the four
## world kinds.
##
## A `static var` rather than a `const` because two entries are built by
## [method _figure], and a GDScript constant must be a constant expression —
## calling anything makes it "not a constant expression" at parse time. Treat it
## as read-only; nothing writes to it and nothing should start.
static var SHAPES: Dictionary = {
	_Const.ITEM_FAMILY_WEAPON: [
		{"shape": SHAPE_BOX, "size": Vector3(0.11, 0.66, 0.03),
			"offset": Vector3(0.0, 0.2, 0.0),
			"color": MeshPalette.STEEL, "finish": MeshPalette.FINISH_METAL},
		{"shape": SHAPE_BOX, "size": Vector3(0.34, 0.06, 0.06),
			"offset": Vector3(0.0, -0.14, 0.0),
			"color": MeshPalette.RUST, "finish": MeshPalette.FINISH_METAL},
		{"shape": SHAPE_CYLINDER, "radius": 0.045, "radius_top": 0.035,
			"height": 0.26, "segments": 8,
			"offset": Vector3(0.0, -0.3, 0.0),
			"color": MeshPalette.WOOD},
	],

	# An open-ended cylinder squashed on Z reads as a curved breastplate from
	# the front without a modelled torso behind it.
	_Const.ITEM_FAMILY_ARMOR: [
		{"shape": SHAPE_CYLINDER, "radius": 0.26, "radius_top": 0.3,
			"height": 0.5, "segments": 12, "open": true,
			"scale": Vector3(1.0, 1.0, 0.55),
			"color": MeshPalette.STEEL, "finish": MeshPalette.FINISH_METAL},
		{"shape": SHAPE_TORUS, "inner": 0.115, "outer": 0.185,
			"offset": Vector3(0.0, 0.26, 0.0),
			"rotation": Vector3(PI / 2.0, 0.0, 0.0),
			"scale": Vector3(1.0, 1.0, 0.55),
			"color": MeshPalette.RUST, "finish": MeshPalette.FINISH_METAL},
	],

	_Const.ITEM_FAMILY_JEWELLERY: [
		{"shape": SHAPE_TORUS, "inner": 0.195, "outer": 0.285,
			"color": MeshPalette.GOLD, "finish": MeshPalette.FINISH_METAL},
		{"shape": SHAPE_FACETED, "radius": 0.1, "segments": 4,
			"offset": Vector3(0.0, 0.26, 0.0),
			"color": MeshPalette.GEM, "finish": MeshPalette.FINISH_GEM},
	],

	# Two lumps rather than one, so an ore reads as a QUANTITY of raw stuff
	# rather than as a single carved object.
	_Const.ITEM_FAMILY_MATERIAL: [
		{"shape": SHAPE_FACETED, "radius": 0.26, "segments": 6,
			"rotation": Vector3(0.4, 0.8, 0.2),
			"color": MeshPalette.STONE},
		{"shape": SHAPE_FACETED, "radius": 0.14, "segments": 6,
			"offset": Vector3(0.22, -0.18, 0.1),
			"rotation": Vector3(0.9, 0.3, 0.5),
			"color": MeshPalette.RUST},
	],

	_Const.ITEM_FAMILY_TOOL: [
		{"shape": SHAPE_CYLINDER, "radius": 0.04, "height": 0.62, "segments": 8,
			"offset": Vector3(0.0, -0.08, 0.0),
			"color": MeshPalette.WOOD},
		{"shape": SHAPE_BOX, "size": Vector3(0.34, 0.15, 0.15),
			"offset": Vector3(0.0, 0.26, 0.0),
			"color": MeshPalette.STEEL, "finish": MeshPalette.FINISH_METAL},
	],

	# Three coins, fanned, so a pile reads as money rather than as one disc.
	_Const.ITEM_FAMILY_CURRENCY: [
		{"shape": SHAPE_CYLINDER, "radius": 0.22, "height": 0.045,
			"segments": 18, "offset": Vector3(0.0, -0.09, 0.0),
			"color": MeshPalette.GOLD, "finish": MeshPalette.FINISH_METAL},
		{"shape": SHAPE_CYLINDER, "radius": 0.22, "height": 0.045,
			"segments": 18, "rotation": Vector3(0.0, 0.4, 0.0),
			"color": MeshPalette.GOLD, "finish": MeshPalette.FINISH_METAL},
		{"shape": SHAPE_CYLINDER, "radius": 0.22, "height": 0.045,
			"segments": 18, "offset": Vector3(0.0, 0.09, 0.0),
			"rotation": Vector3(0.0, 0.8, 0.0),
			"color": MeshPalette.GOLD, "finish": MeshPalette.FINISH_METAL},
	],

	_Const.FAMILY_NPC: _figure(MeshPalette.NPC),
	_Const.FAMILY_CHARACTER: _figure(MeshPalette.CHARACTER),

	# A plinth with a screen tilted toward whoever is standing at it. Reads as
	# something you USE rather than something you pick up, which is the one
	# distinction a bank terminal has to make from a dropped item.
	_Const.FAMILY_STATION: [
		{"shape": SHAPE_BOX, "size": Vector3(0.46, 0.34, 0.34),
			"offset": Vector3(0.0, -0.26, 0.0),
			"color": MeshPalette.STATION},
		{"shape": SHAPE_BOX, "size": Vector3(0.42, 0.38, 0.07),
			"offset": Vector3(0.0, 0.12, 0.04),
			"rotation": Vector3(-0.34, 0.0, 0.0),
			"color": MeshPalette.STATION, "finish": MeshPalette.FINISH_METAL},
		{"shape": SHAPE_BOX, "size": Vector3(0.3, 0.24, 0.02),
			"offset": Vector3(0.0, 0.14, 0.11),
			"rotation": Vector3(-0.34, 0.0, 0.0),
			"color": MeshPalette.PANEL, "finish": MeshPalette.FINISH_PANEL},
	],

	# A rock with something growing out of it. Deliberately NOT the material
	# family's two lumps: an ore you can carry and a node you mine are different
	# affordances, and drawing them the same way is how the rusty pole came to
	# be offered as `get`.
	_Const.FAMILY_GATHERABLE: [
		{"shape": SHAPE_FACETED, "radius": 0.3, "segments": 6,
			"offset": Vector3(0.0, -0.2, 0.0),
			"rotation": Vector3(0.5, 0.3, 0.2),
			"color": MeshPalette.STONE},
		{"shape": SHAPE_CONE, "radius": 0.09, "height": 0.4, "segments": 6,
			"offset": Vector3(0.0, 0.22, 0.0),
			"rotation": Vector3(0.0, 0.0, 0.16),
			"color": MeshPalette.GATHERABLE},
		{"shape": SHAPE_CONE, "radius": 0.09, "height": 0.4, "segments": 6,
			"offset": Vector3(0.17, 0.05, -0.08),
			"rotation": Vector3(0.0, 0.0, -0.5),
			"scale": Vector3(0.62, 0.62, 0.62),
			"color": MeshPalette.GATHERABLE},
	],
}

## Drawn for a family with no entry. Tier 3, and the reason nothing can fail to
## render: content can be added to the game without ever waiting on art.
static var GENERIC: Array = [
	{"shape": SHAPE_BOX, "size": Vector3(0.42, 0.42, 0.42),
		"color": MeshPalette.GENERIC},
]


## One head, one torso, one base — the same shape for both kinds of person.
##
## A function rather than two copied literals because they ARE the same shape:
## only the colour separates a wandering NPC from another player, which is the
## distinction the palette already draws and the one players already read. Two
## literals here would be two things to keep in step for no gain.
static func _figure(role: String) -> Array:
	return [
		{"shape": SHAPE_SPHERE, "radius": 0.15, "segments": 10,
			"offset": Vector3(0.0, 0.36, 0.0), "color": role},
		{"shape": SHAPE_CYLINDER, "radius": 0.2, "radius_top": 0.12,
			"height": 0.46, "segments": 10, "color": role},
		{"shape": SHAPE_CYLINDER, "radius": 0.24, "radius_top": 0.2,
			"height": 0.24, "segments": 10,
			"offset": Vector3(0.0, -0.35, 0.0), "color": role},
	]


## The parts for a family, or the generic block when it names nothing.
##
## Never empty: a family with no entry is not an error and must not be, because
## the server is free to name a family this client has never heard of and the
## answer to that is a plain box, not a gap in the room.
static func parts_for(family: String) -> Array:
	return SHAPES.get(family, GENERIC)


## Whether this family has a shape of its own.
##
## Separate from [method parts_for] because "has one" and "give me one" are
## different questions — a caller checking coverage wants the first and would
## get a misleading yes from the second.
static func has_shape(family: String) -> bool:
	return SHAPES.has(family)


## Every family this table draws. Derived, never restated.
static func families() -> PackedStringArray:
	var names := PackedStringArray(SHAPES.keys())
	names.sort()

	return names
