class_name MeshPalette
extends RefCounted
## What procedural meshes are made of: colours, and how shiny they are.
##
## One owner for both, and nothing else lives here. The browser pane keeps the
## same two tables at the top of `blackout_meshes.js`, and README rule 5 is why
## they have to agree: the two clients get put side by side on the same
## character, so a shopkeeper who is purple in one and grey in the other reads
## as a bug rather than as a style.
##
## ## Colours are named by ROLE, not by family
##
## `STEEL`, not `WEAPON_BLADE`. A sword's blade and a tool's head are the same
## metal and must stay the same metal, so the name has to be the material — the
## moment a colour is named after the thing that uses it, the second user of it
## copies the value instead of the name. That is the "one owner per fact" rule
## CLAUDE.md states, applied to a hex code.
##
## ## Finishes, and why they are named rather than numeric
##
## Every part in [FamilyShapes] says `FINISH_METAL` or `FINISH_MATTE` instead of
## carrying a metalness and a roughness. Two reasons: the pair is one decision
## and splitting it across two numbers invites half of it being changed, and a
## part table full of `0.65, 0.35` is a table nobody can read. The browser
## reached the same shape with its `metal()` and `matte()` helpers.

## Material roles. Keys into [constant COLORS].
const STEEL := "steel"
const RUST := "rust"
const GOLD := "gold"
const GEM := "gem"
const STONE := "stone"
const WOOD := "wood"
const GENERIC := "generic"
const NPC := "npc"
const CHARACTER := "character"
const STATION := "station"
const GATHERABLE := "gatherable"
const PANEL := "panel"

## Role to colour. Hex strings, matching `blackout_meshes.js` exactly.
const COLORS := {
	STEEL: "b9c6d2",
	RUST: "9c5a35",
	GOLD: "f0c674",
	GEM: "7fb3ff",
	STONE: "8a8f98",
	WOOD: "6b4b32",
	GENERIC: "7a8894",

	NPC: "ff5f56",
	CHARACTER: "7fb3ff",
	STATION: "9d7bd8",
	GATHERABLE: "7ac74f",
	PANEL: "35e0c0",
}

## Surface finishes. See the class comment on why these are names.
const FINISH_METAL := "metal"
const FINISH_MATTE := "matte"
const FINISH_GEM := "gem"
const FINISH_PANEL := "panel"

## Finish to [metalness, roughness], matching the browser's helpers.
const FINISHES := {
	FINISH_METAL: [0.65, 0.35],
	FINISH_MATTE: [0.05, 0.85],
	FINISH_GEM: [0.2, 0.1],
	FINISH_PANEL: [0.1, 0.4],
}

## Drawn when a role is not in the table.
##
## Magenta on purpose. Every other colour here is a muted industrial tone, so
## an unmatched role is instantly visible rather than blending in as a slightly
## wrong grey — which is the failure this default exists to make loud.
const MISSING_COLOR := Color("ff00ff")


## The colour for a role.
static func color_of(role: String) -> Color:
	if not COLORS.has(role):
		push_warning("MeshPalette: no colour for role '%s'" % role)
		return MISSING_COLOR

	return Color(COLORS[role])


## A ready material for one role and finish.
##
## A NEW material every call, deliberately. Sharing one per role would be
## cheaper, and would mean the hit flash on a single raider repainted every
## raider in the room — which is the exact bug `takeOwnMaterials` exists to
## work around on the browser side. Here it is simply never created.
static func material_for(role: String, finish: String) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	var values: Array = FINISHES.get(finish, FINISHES[FINISH_MATTE])

	material.albedo_color = color_of(role)
	material.metallic = values[0]
	material.roughness = values[1]

	return material
