class_name SkillPalette
extends RefCounted
## What a skill category LOOKS like. Presentation, and nothing else.
##
## ## Why this is a client file and not a generated one
##
## It is the same split [MapPalette] sits on, and the same one
## `clientexport.py` states at length: **Python owns what is TRUE about the
## game; JavaScript and GDScript own what it looks like.** Which categories
## exist is the server's — a skill class declares its own — and it arrives on
## `char_skills` beside every row. What colour Gathering is drawn in is not a
## fact about the game at all, so generating it would move authorship of the
## interface into a language that cannot see it.
##
## ## The asymmetry, which is the whole reason a test guards this
##
## **A key here naming no real category is a BUG.** It colours nothing, and the
## category it was meant for silently draws the fallback instead — which looks
## like a styling mistake rather than a typo, and is exactly how the dead
## "Pole clearing" room kind survived in two clients until a test found it.
## `test_client_constants.py` reads this file and fails on such a key.
##
## **A category with no entry here is FINE.** It draws [constant FALLBACK] and
## the grid is complete without it, which is what lets a skill added on the
## server reach this pane with no client edit — the same guarantee
## [SkillsState] makes about rows.

## Category name -> the swatch drawn beside every skill in it.
##
## The names are the `category` values Blackout's skill classes declare. The
## hues are chosen to separate the categories at a glance in a small cell, not
## to mean anything: a player reads the NAME, and the colour is only what makes
## one band of the grid distinguishable from the next while scanning it.
##
## `BaseSkill.category` defaults to "General" and is deliberately NOT here. No
## shipped skill declares it, so an entry for it would be a key colouring
## nothing — which is exactly what the guard on this file exists to catch, and
## did, on its first run.
const SKILL_CATEGORY_COLORS := {
	"Combat": Color("c0574a"),
	"Gathering": Color("4f9d5a"),
	"Processing": Color("c08a3a"),
	"Production": Color("5a7fc0"),
}

## Drawn for a category this file has never heard of. See the class docstring:
## this is what makes a server-side addition safe.
const FALLBACK := Color("7a8290")


## The swatch for one category name.
static func color_for(category: String) -> Color:
	return SKILL_CATEGORY_COLORS.get(category, FALLBACK)
