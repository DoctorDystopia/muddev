class_name RarityPalette
extends RefCounted
## What a buff card rarity LOOKS like. Presentation, and nothing else.
##
## ## Why this is a client file and not a generated one
##
## It is the split of [SkillPalette]. The server owns which rarities exist
## (`RARITIES` in `systems/gameplay/exterminator/constants.py`) and sends the
## key of the rarity on each card row. The colour of a rarity is not a fact
## about the game, so the client owns it.
##
## ## The asymmetry, which a test guards
##
## **A key here that names no real rarity is a bug.** It colours nothing.
## `test_client_constants.py` reads this file and fails on such a key.
##
## **A rarity with no entry here is fine.** Its card draws with no colour, as
## a pop-up slot with no `rarity` field does.

## Rarity key -> the colour of the card border and the rarity line.
##
## The ladder of most loot games: green, blue, purple, orange (Nick,
## 10/08/2026).
const RARITY_COLORS := {
	"common": Color("3fbf4a"),
	"rare": Color("3d8fe0"),
	"epic": Color("a64ee8"),
	"legendary": Color("ff8a1f"),
}


## True when the palette has a colour for this rarity key.
static func has_color(rarity: String) -> bool:
	return RARITY_COLORS.has(rarity)


## The colour for one rarity key. Call [method has_color] first. An unknown
## key gives white.
static func color_for(rarity: String) -> Color:
	return RARITY_COLORS.get(rarity, Color.WHITE)
