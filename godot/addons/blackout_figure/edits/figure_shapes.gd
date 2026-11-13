@tool
class_name FigureShapes
extends RefCounted
## The low-poly shapes of a new body and of a new slot shape (DESIGN-0014
## section 16).
##
## [FigureLookEdits] makes a new body and a new slot shape from the tables
## here. A table gives part rows, and a part row gives prism rows.
## [method parts_for] turns each prism row into one prism of a shape list,
## in the space of the bone of its part.
##
## The tables are a start, not the design. A look file holds plain shapes,
## and the author changes each one in the Body tab or the Gear tab (Nick,
## 10/12/2026). Nothing reads a table after its look file exists.
##
## ## A part row
##
##     name    the name of the part
##     bone    the bone of the part
##     region  optional: the region. The default is the region of the bone
##     toward  optional: [from bone, to bone], the direction of the part
##     length  optional: a bone. The length of the part is the distance
##             from `bone` to it. The default is no length
##     origin  optional: the bone where the prism rows start. The default
##             is `bone`
##     depth   optional: DEPTH_FRONT or DEPTH_UP. The default is the front
##     prisms  the prism rows
##
## A row with `{S}` in a bone name makes one part for each side: `{S}`
## becomes "Left" and "Right", and `{s}` becomes "l" and "r".
##
## ## The frame of a part
##
## A part with `toward` has three directions in the rest pose of the
## figure. "Along" goes from the first bone to the second bone. "Depth"
## goes to the front of the figure, or up. "Across" is at a right angle to
## the two. For an arm in the rest pose, across is down. For a leg, across
## is to the middle of the figure. A part of the right side gets its
## across numbers with the other sign, so one row serves the two sides.
##
## A part with no `toward` uses the axes of its bone: X, Y, and Z. A held
## item uses them, because a hand socket has the grip.
##
## ## A prism row
##
##     role       the color role
##     at         [across, along, depth]: the middle of the first face
##     at_bone    optional: this part of the length joins the along number
##     span       the length of the prism
##     span_bone  optional: this part of the length joins the span
##     bottom     [width, depth]: the first face
##     top        optional: [width, depth] of the second face
##     lean       optional: [across, depth], the second face moves this far
##     sides      the count of sides
##     axis       optional: AXIS_ALONG, AXIS_DEPTH, or AXIS_ACROSS
##     diamond    optional: a corner on each axis of the face, not a side
##
## The girth of a body scales each width, each depth, and each across and
## depth number of `at`. It scales no length.

const DEPTH_FRONT := "front"
const DEPTH_UP := "up"
const DEPTHS := {DEPTH_FRONT: Vector3(0.0, 0.0, 1.0), DEPTH_UP: Vector3(0.0, 1.0, 0.0)}

const AXIS_ALONG := "along"
const AXIS_DEPTH := "depth"
const AXIS_ACROSS := "across"

## The two sides of a mirrored part row: the bone word, the name letter,
## and the sign of each across number.
const SIDES := [["Left", "l", 1.0], ["Right", "r", -1.0]]
const SIDE_BONE := "{S}"
const SIDE_NAME := "{s}"

## The keys of a part row that hold a bone name or a part name.
const SIDE_KEYS := ["name", "bone", "length", "origin"]

const DEFAULT_SIDES := 6

## The color roles of a body, and the color of [MeshPalette] that a new
## body gives each one. The default clothes are roles of the body, as the
## kit colors of an OSRS figure are.
const ROLE_SKIN := "skin"
const ROLE_HAIR := "hair"
const ROLE_EYES := "eyes"
const ROLE_SHIRT := "shirt"
const ROLE_TROUSERS := "trousers"
const ROLE_BELT := "belt"
const ROLE_WRISTBAND := "wristband"
const ROLE_BOOTS := "boots"
const ROLE_BOOT_CUFF := "boot_cuff"

const BODY_COLORS := {
	ROLE_SKIN: MeshPalette.SKIN,
	ROLE_HAIR: MeshPalette.HAIR_GREY,
	ROLE_EYES: MeshPalette.SHADOW,
	ROLE_SHIRT: MeshPalette.CLOTH_GREY,
	ROLE_TROUSERS: MeshPalette.CLOTH_PALE,
	ROLE_BELT: MeshPalette.CLOTH_RED,
	ROLE_WRISTBAND: MeshPalette.LINEN,
	ROLE_BOOTS: MeshPalette.LEATHER_GREY,
	ROLE_BOOT_CUFF: MeshPalette.LEATHER_OLIVE,
}

## The color roles of gear (DESIGN-0014 section 8.5), and the color of
## [MeshPalette] that a new look gives each one.
const ROLE_METAL := "metal"
const ROLE_TRIM := "trim"
const ROLE_CLOTH := "cloth"
const ROLE_LEATHER := "leather"
const ROLE_DETAIL := "detail"
const ROLE_GAP := "gap"

const GEAR_COLORS := {
	ROLE_METAL: MeshPalette.IRON,
	ROLE_TRIM: MeshPalette.IRON_DARK,
	ROLE_CLOTH: MeshPalette.RUST,
	ROLE_LEATHER: MeshPalette.WOOD,
	ROLE_DETAIL: MeshPalette.GOLD,
	ROLE_GAP: MeshPalette.SHADOW,
}

## The named colors of a new palette (Phase W5). A new body and a new slot
## shape name these colors. The list also has the metal of each tier.
##
## A new palette takes the color of each name from [MeshPalette], with a
## matte finish. The author then changes each one on the Colors tab.
const PALETTE_COLORS := [
	MeshPalette.SKIN, MeshPalette.HAIR_GREY, MeshPalette.SHADOW,
	MeshPalette.CLOTH_GREY, MeshPalette.CLOTH_PALE, MeshPalette.CLOTH_RED,
	MeshPalette.LINEN, MeshPalette.LEATHER_GREY, MeshPalette.LEATHER_OLIVE,
	MeshPalette.IRON, MeshPalette.IRON_DARK, MeshPalette.COPPER, MeshPalette.COPPER_DARK,
	MeshPalette.STEEL, MeshPalette.RUST, MeshPalette.GOLD, MeshPalette.GEM,
	MeshPalette.STONE, MeshPalette.WOOD, MeshPalette.GENERIC,
]

## The color of a color role in the slot shape of a slot, where it is not
## the color of [constant GEAR_COLORS].
const SLOT_COLORS := {
	"main_hand": {ROLE_METAL: MeshPalette.STEEL},
	"two_hands": {ROLE_METAL: MeshPalette.STEEL},
	"neck": {ROLE_METAL: MeshPalette.GOLD, ROLE_TRIM: MeshPalette.GEM},
	"main_hand_finger": {ROLE_METAL: MeshPalette.GOLD},
	"off_hand_finger": {ROLE_METAL: MeshPalette.GOLD},
	"ammo": {ROLE_TRIM: MeshPalette.LINEN},
}

## The regions that the slot shape of a slot hides. The parts of the slot
## shape take the place of the body parts there, so no body part shows
## through at a bent joint.
const SLOT_HIDES := {
	"head": ["hair"],
	"body": ["torso", "arms"],
	"legs": ["legs"],
	"feet": ["feet"],
}

# ─── The body ───────────────────────────────────────────────────────────────

## The parts of a new body. The hips part has the trousers, so it is in the
## `legs` region. A sleeve is in the `torso` region, and a boot is in the
## `feet` region. A worn look that hides a region then hides the clothes of
## that region.
const BODY := [
	{"name": "hips", "bone": "Hips", "region": "legs", "toward": ["Hips", "Spine"], "prisms": [
		{"role": ROLE_TROUSERS, "at": [0.0, -0.09, 0.0], "span": 0.14,
			"bottom": [0.17, 0.105], "top": [0.215, 0.14], "sides": 8},
	]},
	{"name": "belt", "bone": "Hips", "region": "torso", "toward": ["Hips", "Spine"], "prisms": [
		{"role": ROLE_BELT, "at": [0.0, 0.045, 0.0], "span": 0.035,
			"bottom": [0.224, 0.148], "sides": 8},
	]},
	{"name": "spine", "bone": "Spine", "toward": ["Spine", "Chest"], "length": "Chest", "prisms": [
		{"role": ROLE_SHIRT, "at": [0.0, -0.03, 0.0], "span": 0.04, "span_bone": 1.0,
			"bottom": [0.21, 0.135], "top": [0.25, 0.155], "sides": 8},
	]},
	{"name": "chest", "bone": "Chest", "toward": ["Chest", "UpperChest"], "length": "UpperChest",
		"prisms": [
		{"role": ROLE_SHIRT, "at": [0.0, -0.01, 0.0], "span": 0.02, "span_bone": 1.0,
			"bottom": [0.25, 0.155], "top": [0.30, 0.172], "sides": 8},
	]},
	{"name": "upper_chest", "bone": "UpperChest", "toward": ["UpperChest", "Neck"],
		"length": "Neck", "prisms": [
		{"role": ROLE_SHIRT, "at": [0.0, -0.01, 0.0], "span": 0.025, "span_bone": 1.0,
			"bottom": [0.30, 0.172], "top": [0.33, 0.16], "sides": 8},
		{"role": ROLE_SHIRT, "at": [0.0, 0.015, 0.0], "at_bone": 1.0, "span": 0.04,
			"bottom": [0.33, 0.16], "top": [0.13, 0.10], "sides": 8},
	]},
	{"name": "neck", "bone": "Neck", "toward": ["Neck", "Head"], "length": "Head", "prisms": [
		{"role": ROLE_SKIN, "at": [0.0, 0.0, 0.0], "span": 0.01, "span_bone": 1.0,
			"bottom": [0.075, 0.08], "top": [0.07, 0.075], "sides": 6},
	]},
	{"name": "head", "bone": "Head", "toward": ["Neck", "Head"], "prisms": [
		{"role": ROLE_SKIN, "at": [0.0, -0.035, 0.012], "span": 0.085, "lean": [0.0, -0.012],
			"bottom": [0.085, 0.10], "top": [0.15, 0.165], "sides": 8},
		{"role": ROLE_SKIN, "at": [0.0, 0.05, 0.0], "span": 0.10,
			"bottom": [0.15, 0.165], "top": [0.14, 0.16], "sides": 8},
		{"role": ROLE_SKIN, "at": [0.0, 0.15, 0.0], "span": 0.035,
			"bottom": [0.14, 0.16], "top": [0.08, 0.10], "sides": 8},
		{"role": ROLE_SKIN, "at": [0.0, 0.045, 0.078], "span": 0.045, "lean": [0.0, -0.002],
			"bottom": [0.034, 0.03], "top": [0.014, 0.012], "sides": 4},
		# The front face of the head is 0.06 wide. Each eye and each brow
		# starts inside the head and stays on that face.
		{"role": ROLE_EYES, "axis": AXIS_DEPTH, "at": [0.022, 0.095, 0.06], "span": 0.0245,
			"bottom": [0.02, 0.012], "sides": 4},
		{"role": ROLE_EYES, "axis": AXIS_DEPTH, "at": [-0.022, 0.095, 0.06], "span": 0.0245,
			"bottom": [0.02, 0.012], "sides": 4},
		{"role": ROLE_HAIR, "axis": AXIS_DEPTH, "at": [0.022, 0.112, 0.06], "span": 0.0255,
			"bottom": [0.026, 0.008], "sides": 4},
		{"role": ROLE_HAIR, "axis": AXIS_DEPTH, "at": [-0.022, 0.112, 0.06], "span": 0.0255,
			"bottom": [0.026, 0.008], "sides": 4},
	]},
	{"name": "hair", "bone": "head_top", "origin": "Head", "toward": ["Neck", "Head"], "prisms": [
		{"role": ROLE_HAIR, "at": [0.0, 0.125, -0.014], "span": 0.08, "lean": [0.0, -0.006],
			"bottom": [0.165, 0.19], "top": [0.10, 0.12], "sides": 8},
		{"role": ROLE_HAIR, "at": [0.0, 0.01, -0.06], "span": 0.14, "lean": [0.0, 0.01],
			"bottom": [0.125, 0.06], "top": [0.165, 0.09], "sides": 6},
	]},
	{"name": "sleeve_{s}", "bone": "{S}UpperArm", "region": "torso",
		"toward": ["{S}UpperArm", "{S}LowerArm"], "prisms": [
		{"role": ROLE_SHIRT, "at": [0.0, -0.02, 0.0], "span": 0.125,
			"bottom": [0.10, 0.135], "top": [0.115, 0.13], "sides": 6},
	]},
	{"name": "upper_arm_{s}", "bone": "{S}UpperArm", "toward": ["{S}UpperArm", "{S}LowerArm"],
		"length": "{S}LowerArm", "prisms": [
		{"role": ROLE_SKIN, "at": [0.0, 0.0, 0.0], "span": 0.01, "span_bone": 1.0,
			"bottom": [0.085, 0.09], "top": [0.075, 0.08], "sides": 6},
	]},
	{"name": "lower_arm_{s}", "bone": "{S}LowerArm", "toward": ["{S}LowerArm", "{S}Hand"],
		"length": "{S}Hand", "prisms": [
		{"role": ROLE_SKIN, "at": [0.0, -0.015, 0.0], "span": 0.02, "span_bone": 1.0,
			"bottom": [0.088, 0.092], "top": [0.058, 0.062], "sides": 6},
		{"role": ROLE_WRISTBAND, "at": [0.0, -0.05, 0.0], "at_bone": 1.0, "span": 0.047,
			"bottom": [0.07, 0.074], "top": [0.066, 0.07], "sides": 6},
	]},
	{"name": "hand_{s}", "bone": "{S}Hand", "toward": ["{S}LowerArm", "{S}Hand"], "prisms": [
		{"role": ROLE_SKIN, "at": [0.0, -0.01, 0.0], "span": 0.06,
			"bottom": [0.04, 0.062], "top": [0.046, 0.08], "sides": 4},
		{"role": ROLE_SKIN, "at": [0.0, 0.05, 0.0], "span": 0.055,
			"bottom": [0.046, 0.08], "top": [0.026, 0.055], "sides": 4},
	]},
	{"name": "upper_leg_{s}", "bone": "{S}UpperLeg", "toward": ["{S}UpperLeg", "{S}LowerLeg"],
		"length": "{S}LowerLeg", "prisms": [
		{"role": ROLE_TROUSERS, "at": [0.0, -0.03, 0.0], "span": 0.045, "span_bone": 1.0,
			"bottom": [0.115, 0.135], "top": [0.095, 0.105], "sides": 6},
	]},
	{"name": "lower_leg_{s}", "bone": "{S}LowerLeg", "toward": ["{S}LowerLeg", "{S}Foot"],
		"length": "{S}Foot", "prisms": [
		{"role": ROLE_TROUSERS, "at": [0.0, -0.02, 0.0], "span": -0.15, "span_bone": 1.0,
			"bottom": [0.10, 0.11], "top": [0.085, 0.09], "sides": 6},
	]},
	{"name": "boot_{s}", "bone": "{S}LowerLeg", "region": "feet",
		"toward": ["{S}LowerLeg", "{S}Foot"], "length": "{S}Foot", "prisms": [
		{"role": ROLE_BOOT_CUFF, "at": [0.0, -0.20, 0.0], "at_bone": 1.0, "span": 0.065,
			"bottom": [0.12, 0.128], "top": [0.095, 0.10], "sides": 6},
		{"role": ROLE_BOOTS, "at": [0.0, -0.15, 0.0], "at_bone": 1.0, "span": 0.15,
			"bottom": [0.085, 0.09], "top": [0.075, 0.085], "sides": 6},
	]},
	{"name": "foot_{s}", "bone": "{S}Foot", "toward": ["{S}Foot", "{S}Toes"], "depth": DEPTH_UP,
		"length": "{S}Toes", "prisms": [
		{"role": ROLE_BOOTS, "at": [0.0, -0.055, 0.036], "span": 0.075, "span_bone": 1.0,
			"lean": [0.0, -0.018], "bottom": [0.088, 0.072], "top": [0.075, 0.036], "sides": 4},
	]},
]

# ─── The slot shapes ────────────────────────────────────────────────────────

## The parts of the slot shape of each slot.
##
## A held item has no `toward`, so its prism rows are in the axes of the
## hand socket: the length of the item along +Y, and the flat of a blade to
## +Z. The shield has `toward` from the hand to the elbow, so its long axis
## goes along the lower arm. Its depth is up in the rest pose: the back of
## the hand.
const SLOTS := {
	"main_hand": [{"name": "item", "bone": "hand_r", "prisms": [
		{"role": ROLE_METAL, "at": [0.0, 0.055, 0.0], "span": 0.445, "diamond": true,
			"bottom": [0.062, 0.018], "top": [0.05, 0.015], "sides": 4},
		{"role": ROLE_METAL, "at": [0.0, 0.50, 0.0], "span": 0.10, "diamond": true,
			"bottom": [0.05, 0.015], "top": [0.0, 0.0], "sides": 4},
		{"role": ROLE_TRIM, "axis": AXIS_ACROSS, "at": [-0.09, 0.045, 0.0], "span": 0.18,
			"bottom": [0.032, 0.036], "sides": 4},
		{"role": ROLE_LEATHER, "at": [0.0, -0.07, 0.0], "span": 0.105,
			"bottom": [0.03, 0.03], "sides": 6},
		{"role": ROLE_TRIM, "at": [0.0, -0.11, 0.0], "span": 0.022, "diamond": true,
			"bottom": [0.0, 0.0], "top": [0.048, 0.048], "sides": 4},
		{"role": ROLE_TRIM, "at": [0.0, -0.088, 0.0], "span": 0.022, "diamond": true,
			"bottom": [0.048, 0.048], "top": [0.02, 0.02], "sides": 4},
	]}],
	"two_hands": [{"name": "item", "bone": "hand_r", "prisms": [
		{"role": ROLE_METAL, "at": [0.0, 0.07, 0.0], "span": 0.70, "diamond": true,
			"bottom": [0.078, 0.02], "top": [0.062, 0.016], "sides": 4},
		{"role": ROLE_METAL, "at": [0.0, 0.77, 0.0], "span": 0.13, "diamond": true,
			"bottom": [0.062, 0.016], "top": [0.0, 0.0], "sides": 4},
		{"role": ROLE_TRIM, "axis": AXIS_ACROSS, "at": [-0.12, 0.055, 0.0], "span": 0.24,
			"bottom": [0.036, 0.04], "sides": 4},
		{"role": ROLE_LEATHER, "at": [0.0, -0.19, 0.0], "span": 0.23,
			"bottom": [0.032, 0.032], "sides": 6},
		{"role": ROLE_TRIM, "at": [0.0, -0.24, 0.0], "span": 0.026, "diamond": true,
			"bottom": [0.0, 0.0], "top": [0.056, 0.056], "sides": 4},
		{"role": ROLE_TRIM, "at": [0.0, -0.214, 0.0], "span": 0.026, "diamond": true,
			"bottom": [0.056, 0.056], "top": [0.024, 0.024], "sides": 4},
	]}],
	"off_hand": [{"name": "item", "bone": "hand_l", "toward": ["LeftHand", "LeftLowerArm"],
		"depth": DEPTH_UP, "prisms": [
		{"role": ROLE_METAL, "at": [0.0, -0.10, 0.045], "span": 0.32,
			"bottom": [0.30, 0.03], "top": [0.28, 0.03], "sides": 4},
		{"role": ROLE_METAL, "at": [0.0, -0.20, 0.045], "span": 0.10,
			"bottom": [0.16, 0.024], "top": [0.30, 0.03], "sides": 4},
		{"role": ROLE_TRIM, "at": [0.0, 0.19, 0.045], "span": 0.035,
			"bottom": [0.285, 0.04], "top": [0.275, 0.04], "sides": 4},
		{"role": ROLE_DETAIL, "axis": AXIS_DEPTH, "at": [0.0, 0.03, 0.058], "span": 0.014,
			"diamond": true, "bottom": [0.11, 0.11], "top": [0.08, 0.08], "sides": 4},
	]}],
	"head": [{"name": "helm", "bone": "Head", "toward": ["Neck", "Head"], "prisms": [
		{"role": ROLE_METAL, "at": [0.0, -0.045, 0.0], "span": 0.125,
			"bottom": [0.165, 0.185], "top": [0.19, 0.21], "sides": 8},
		{"role": ROLE_METAL, "at": [0.0, 0.08, 0.0], "span": 0.095,
			"bottom": [0.19, 0.21], "top": [0.15, 0.17], "sides": 8},
		{"role": ROLE_METAL, "at": [0.0, 0.175, 0.0], "span": 0.04,
			"bottom": [0.15, 0.17], "top": [0.05, 0.07], "sides": 8},
		{"role": ROLE_GAP, "axis": AXIS_DEPTH, "at": [0.0, 0.085, 0.09], "span": 0.018,
			"bottom": [0.12, 0.02], "sides": 4},
		{"role": ROLE_GAP, "axis": AXIS_DEPTH, "at": [0.0, 0.02, 0.085], "span": 0.017,
			"bottom": [0.016, 0.09], "sides": 4},
		{"role": ROLE_TRIM, "axis": AXIS_DEPTH, "at": [0.0, 0.20, -0.10], "span": 0.20,
			"bottom": [0.022, 0.07], "top": [0.022, 0.05], "sides": 4},
	]}],
	"body": [
		{"name": "spine", "bone": "Spine", "toward": ["Spine", "Chest"], "length": "Chest",
			"prisms": [
			{"role": ROLE_METAL, "at": [0.0, -0.03, 0.0], "span": 0.04, "span_bone": 1.0,
				"bottom": [0.227, 0.146], "top": [0.27, 0.167], "sides": 8},
		]},
		{"name": "chest", "bone": "Chest", "toward": ["Chest", "UpperChest"],
			"length": "UpperChest", "prisms": [
			{"role": ROLE_METAL, "at": [0.0, -0.01, 0.0], "span": 0.02, "span_bone": 1.0,
				"bottom": [0.27, 0.167], "top": [0.324, 0.186], "sides": 8},
			{"role": ROLE_TRIM, "at": [0.0, 0.04, 0.0], "span": 0.03,
				"bottom": [0.305, 0.19], "top": [0.31, 0.192], "sides": 8},
		]},
		{"name": "upper_chest", "bone": "UpperChest", "toward": ["UpperChest", "Neck"],
			"length": "Neck", "prisms": [
			{"role": ROLE_METAL, "at": [0.0, -0.01, 0.0], "span": 0.025, "span_bone": 1.0,
				"bottom": [0.324, 0.186], "top": [0.356, 0.173], "sides": 8},
			{"role": ROLE_METAL, "at": [0.0, 0.015, 0.0], "at_bone": 1.0, "span": 0.04,
				"bottom": [0.356, 0.173], "top": [0.13, 0.10], "sides": 8},
			{"role": ROLE_DETAIL, "axis": AXIS_DEPTH, "at": [0.0, 0.035, 0.085], "span": 0.014,
				"diamond": true, "bottom": [0.05, 0.05], "top": [0.04, 0.04], "sides": 4},
		]},
		{"name": "pauldron_{s}", "bone": "{S}UpperArm", "region": "torso",
			"toward": ["{S}UpperArm", "{S}LowerArm"], "prisms": [
			{"role": ROLE_METAL, "at": [-0.025, -0.065, 0.0], "span": 0.20, "lean": [0.015, 0.0],
				"bottom": [0.16, 0.20], "top": [0.11, 0.14], "sides": 6},
			{"role": ROLE_TRIM, "at": [-0.01, 0.12, 0.0], "span": 0.02,
				"bottom": [0.118, 0.148], "sides": 6},
		]},
		{"name": "upper_arm_{s}", "bone": "{S}UpperArm",
			"toward": ["{S}UpperArm", "{S}LowerArm"], "length": "{S}LowerArm", "prisms": [
			{"role": ROLE_METAL, "at": [0.0, 0.0, 0.0], "span": 0.01, "span_bone": 1.0,
				"bottom": [0.095, 0.10], "top": [0.084, 0.09], "sides": 6},
		]},
		{"name": "lower_arm_{s}", "bone": "{S}LowerArm", "toward": ["{S}LowerArm", "{S}Hand"],
			"length": "{S}Hand", "prisms": [
			{"role": ROLE_METAL, "at": [0.0, -0.015, 0.0], "span": 0.02, "span_bone": 1.0,
				"bottom": [0.099, 0.103], "top": [0.065, 0.07], "sides": 6},
			{"role": ROLE_TRIM, "at": [0.0, -0.05, 0.0], "at_bone": 1.0, "span": 0.047,
				"bottom": [0.078, 0.083], "top": [0.074, 0.078], "sides": 6},
		]},
	],
	"legs": [
		{"name": "hips", "bone": "Hips", "region": "legs", "toward": ["Hips", "Spine"],
			"prisms": [
			{"role": ROLE_METAL, "at": [0.0, -0.09, 0.0], "span": 0.14,
				"bottom": [0.187, 0.116], "top": [0.232, 0.151], "sides": 8},
		]},
		{"name": "upper_leg_{s}", "bone": "{S}UpperLeg",
			"toward": ["{S}UpperLeg", "{S}LowerLeg"], "length": "{S}LowerLeg", "prisms": [
			{"role": ROLE_METAL, "at": [0.0, -0.03, 0.0], "span": 0.045, "span_bone": 1.0,
				"bottom": [0.127, 0.149], "top": [0.105, 0.116], "sides": 6},
		]},
		{"name": "lower_leg_{s}", "bone": "{S}LowerLeg", "toward": ["{S}LowerLeg", "{S}Foot"],
			"length": "{S}Foot", "prisms": [
			{"role": ROLE_METAL, "at": [0.0, -0.02, 0.0], "span": -0.15, "span_bone": 1.0,
				"bottom": [0.11, 0.121], "top": [0.094, 0.099], "sides": 6},
			{"role": ROLE_TRIM, "at": [0.0, -0.04, 0.035], "span": 0.08,
				"bottom": [0.085, 0.07], "top": [0.075, 0.06], "sides": 4},
		]},
	],
	"feet": [
		{"name": "boot_{s}", "bone": "{S}LowerLeg", "region": "feet",
			"toward": ["{S}LowerLeg", "{S}Foot"], "length": "{S}Foot", "prisms": [
			{"role": ROLE_TRIM, "at": [0.0, -0.20, 0.0], "at_bone": 1.0, "span": 0.065,
				"bottom": [0.13, 0.138], "top": [0.103, 0.108], "sides": 6},
			{"role": ROLE_LEATHER, "at": [0.0, -0.15, 0.0], "at_bone": 1.0, "span": 0.15,
				"bottom": [0.092, 0.097], "top": [0.081, 0.092], "sides": 6},
		]},
		{"name": "foot_{s}", "bone": "{S}Foot", "toward": ["{S}Foot", "{S}Toes"],
			"depth": DEPTH_UP, "length": "{S}Toes", "prisms": [
			{"role": ROLE_LEATHER, "at": [0.0, -0.06, 0.039], "span": 0.085, "span_bone": 1.0,
				"lean": [0.0, -0.0195], "bottom": [0.095, 0.078], "top": [0.081, 0.039],
				"sides": 4},
		]},
	],
	# The back socket is behind the upper chest. The cape hangs in two
	# lengths, and the low one stands away from the legs.
	"back": [{"name": "item", "bone": "back", "prisms": [
		{"role": ROLE_CLOTH, "at": [0.0, -0.15, 0.0], "span": 0.25, "lean": [0.0, 0.03],
			"bottom": [0.33, 0.02], "top": [0.28, 0.02], "sides": 4},
		{"role": ROLE_CLOTH, "at": [0.0, -0.50, -0.07], "span": 0.35, "lean": [0.0, 0.07],
			"bottom": [0.40, 0.02], "top": [0.33, 0.02], "sides": 4},
	]}],
	# The two chains go from the gem up to each side of the neck.
	"neck": [{"name": "item", "bone": "neck_front", "prisms": [
		{"role": ROLE_METAL, "at": [0.0, -0.085, 0.03], "span": 0.085, "lean": [0.055, -0.07],
			"bottom": [0.012, 0.012], "sides": 4},
		{"role": ROLE_METAL, "at": [0.0, -0.085, 0.03], "span": 0.085, "lean": [-0.055, -0.07],
			"bottom": [0.012, 0.012], "sides": 4},
		{"role": ROLE_TRIM, "axis": AXIS_DEPTH, "at": [0.0, -0.095, 0.03], "span": 0.014,
			"diamond": true, "bottom": [0.045, 0.045], "top": [0.03, 0.03], "sides": 4},
	]}],
	# A ring is a band around the fingers of the hand. The hand of a body is
	# one block, with no finger.
	"main_hand_finger": [{"name": "item", "bone": "finger_r", "origin": "RightHand",
		"toward": ["RightLowerArm", "RightHand"], "prisms": [
		{"role": ROLE_METAL, "at": [0.0, 0.062, 0.0], "span": 0.016,
			"bottom": [0.052, 0.086], "sides": 4},
	]}],
	"off_hand_finger": [{"name": "item", "bone": "finger_l", "origin": "LeftHand",
		"toward": ["LeftLowerArm", "LeftHand"], "prisms": [
		{"role": ROLE_METAL, "at": [0.0, 0.062, 0.0], "span": 0.016,
			"bottom": [0.052, 0.086], "sides": 4},
	]}],
	# The quiver leans back, with the feathers of the arrows above it.
	"ammo": [{"name": "item", "bone": "hip_r", "prisms": [
		{"role": ROLE_LEATHER, "at": [-0.02, -0.14, -0.03], "span": 0.28, "lean": [0.0, -0.07],
			"bottom": [0.06, 0.06], "top": [0.08, 0.08], "sides": 6},
		{"role": ROLE_TRIM, "at": [-0.02, 0.14, -0.10], "span": 0.06, "lean": [0.0, -0.015],
			"bottom": [0.05, 0.05], "top": [0.06, 0.06], "sides": 4},
	]}],
}


# ─── From a table to a shape list ───────────────────────────────────────────

## The parts of a look for the part rows `rows`, on the bones of `rig`. A
## row on a bone that the rig does not have gives no part.
static func parts_for(rig: FigureRig, rows: Array, girth := 1.0) -> Array:
	var parts := []

	for row: Dictionary in rows:
		if not str(row["bone"]).contains(SIDE_BONE):
			_add_part(parts, rig, row, 1.0, girth)
			continue

		for side: Array in SIDES:
			_add_part(parts, rig, _row_of_side(row, side), side[2], girth)

	return parts


## The color table of a look: one row for each color role that a shape of
## `parts` names and that `defaults` has. `chosen` gives the color of a
## role, and `defaults` gives each other one.
static func colors_for(parts: Array, defaults: Dictionary, chosen := {}) -> Dictionary:
	var colors := {}

	for part: Dictionary in parts:
		for shape: Dictionary in part.get("shapes", []):
			var role: String = shape.get("color", "")

			if defaults.has(role):
				colors[role] = chosen.get(role, defaults[role])

	return colors


## A part row with the bone word and the name letter of one side.
static func _row_of_side(row: Dictionary, side: Array) -> Dictionary:
	var out := row.duplicate()

	for key: String in SIDE_KEYS:
		if out.has(key):
			out[key] = _text_of_side(out[key], side)

	if out.has("toward"):
		out["toward"] = [_text_of_side(row["toward"][0], side),
			_text_of_side(row["toward"][1], side)]

	return out


static func _text_of_side(text: String, side: Array) -> String:
	return text.replace(SIDE_BONE, side[0]).replace(SIDE_NAME, side[1])


static func _add_part(parts: Array, rig: FigureRig, row: Dictionary, side: float,
		girth: float) -> void:
	var bone: String = row["bone"]

	if not rig.has_bone(bone):
		return

	var rest := rig.global_rest_of(bone)
	var origin := rest.origin
	var length := 0.0
	var shapes := []

	if rig.has_bone(row.get("origin", "")):
		origin = rig.global_rest_of(row["origin"]).origin

	if rig.has_bone(row.get("length", "")):
		length = rig.global_rest_of(row["length"]).origin.distance_to(rest.origin)

	var frame := _frame(rig, row, rest.basis)

	for prism: Dictionary in row["prisms"]:
		shapes.append(_shape(prism, Transform3D(frame, origin), length, Vector2(side, girth),
			rest.affine_inverse()))

	parts.append({
		"name": row["name"],
		"bone": bone,
		"region": row.get("region", rig.region_of(bone)),
		"shapes": shapes,
	})


## The frame of a part in the rest pose of the figure: across, along, and
## depth. A part with no `toward` gets the axes of its bone.
static func _frame(rig: FigureRig, row: Dictionary, bone_basis: Basis) -> Basis:
	var toward: Array = row.get("toward", [])

	if toward.size() != 2 or not rig.has_bone(toward[0]) or not rig.has_bone(toward[1]):
		return bone_basis.orthonormalized()

	var along := rig.global_rest_of(toward[1]).origin - rig.global_rest_of(toward[0]).origin
	var depth: Vector3 = DEPTHS[row.get("depth", DEPTH_FRONT)]

	if along.is_zero_approx():
		return bone_basis.orthonormalized()

	along = along.normalized()
	depth = (depth - along * depth.dot(along)).normalized()

	return Basis(along.cross(depth), along, depth)


## One prism of a shape list for one prism row.
##
## `frame` is the frame of the part at the origin of its prism rows.
## `mirror` is the sign of the side and the girth. `to_bone` takes a place
## of the figure into the space of the bone.
static func _shape(prism: Dictionary, frame: Transform3D, length: float, mirror: Vector2,
		to_bone: Transform3D) -> Dictionary:
	var at: Array = prism.get("at", [0.0, 0.0, 0.0])
	var axis: String = prism.get("axis", AXIS_ALONG)
	var bottom: Array = prism["bottom"]
	var top: Array = prism.get("top", bottom)
	var lean: Array = prism.get("lean", [0.0, 0.0])
	var span: float = prism.get("span", 0.0) + prism.get("span_bone", 0.0) * length
	var along: float = at[1] + prism.get("at_bone", 0.0) * length
	var turn := _prism_basis(frame.basis, axis, mirror.x)
	var start := frame * Vector3(at[0] * mirror.x * mirror.y, along, at[2] * mirror.y)
	var lean_x: float = lean[0] * mirror.y * (mirror.x if axis == AXIS_ALONG else 1.0)
	var shape := {
		"shape": FamilyShapes.SHAPE_PRISM,
		"color": prism["role"],
		"segments": int(prism.get("sides", DEFAULT_SIDES)),
		"size": [bottom[0] * mirror.y, span, bottom[1] * mirror.y],
		"offset": FigureJson.from_vector3(to_bone * (start + turn.y * span * 0.5)),
	}

	_set_unless(shape, "rotation", FigureJson.from_vector3((to_bone.basis * turn).get_euler()),
		[0.0, 0.0, 0.0])
	_set_unless(shape, "top_width", top[0] * mirror.y, bottom[0] * mirror.y)
	_set_unless(shape, "top_depth", top[1] * mirror.y, bottom[1] * mirror.y)
	_set_unless(shape, "lean_x", lean_x, 0.0)
	_set_unless(shape, "lean_z", lean[1] * mirror.y, 0.0)
	_set_unless(shape, "diamond", prism.get("diamond", false), false)

	return shape


## The axes of a prism in the rest pose of the figure: its width, its
## length, and its depth. `frame` is the frame of its part.
static func _prism_basis(frame: Basis, axis: String, side: float) -> Basis:
	match axis:
		AXIS_DEPTH:
			return Basis(-frame.x, frame.z, frame.y)
		AXIS_ACROSS:
			return Basis(-frame.y * side, frame.x * side, frame.z)

	return frame


## Give a shape a key, but not for the value that the builder uses with no
## key. A look file then has no line for a default.
static func _set_unless(shape: Dictionary, key: String, value: Variant,
		default: Variant) -> void:
	if value != default:
		shape[key] = value
