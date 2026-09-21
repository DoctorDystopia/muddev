"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Skill category Processing - Curing recipe definitions.

             Four recipes and two of them take a RENDERED component rather
             than a gathered cut -- the skill-tree map's "second processing
             pass". That is the whole reason Curing sits beside Rendering
             rather than after it: a chuck can go straight into the chamber,
             or through the cooker first and into the chamber after, and the
             two routes make two different foods.

             Levels and XP are transcribed from the crafting spreadsheet,
             which is the source of truth for this chain wherever it and the
             skill-tree map disagree. The DURATIONS are not in the sheet --
             see _CHUCK_TIER_SECONDS below.
"""



from systems.gameplay.curing.recipe import CuringRecipe



# Private constant definitions

# How long a cure takes, by tier.
#
# NOT from the spreadsheet -- it has no duration column, and these are the
# numbers to argue with when the stage feels wrong. Two of them rather than
# four because the tier is what the wait expresses: a filet is the better cut
# and the longer commitment, and the two recipes within a tier are a choice
# between foods rather than between waits.
#
# chosen so a cure is something a player sets going and leaves,
# long enough that the chamber is a place you come back to, short
# enough that it is not a once-a-session errand.
_CHUCK_TIER_SECONDS = 5.0
_PRIME_TIER_SECONDS = 10.0

# The same two waits for the giant, doubled. A giant cut is bigger and takes
# longer to keep, which is the only thing the tier needs the duration to say.
# Still inside one visit to the chamber at both tiers, so the stage stays a
# place the player comes back to rather than a once-a-session errand.
_GIANT_CHUCK_TIER_SECONDS = 10.0
_GIANT_PRIME_TIER_SECONDS = 20.0



class MutantRaiderCuredChuckRecipe(CuringRecipe):
    "Salt and hang a raw chuck until it keeps."

    name = "mutant raider cured chuck"
    required_level = 0
    xp_reward = 25
    cure_seconds = _CHUCK_TIER_SECONDS

    consumable_tags = ["mutant_raider_raw_chuck"]
    consumable_names = ["mutant raider raw chuck"]

    output_item_keys = ["mutant_raider_cured_chuck"]

    success_message = "You draw the cured chuck out of the chamber."



class MutantRaiderSinewRecipe(CuringRecipe):
    "Salt and hang a raw chuck until it keeps."

    name = "mutant raider sinew"
    required_level = 0
    xp_reward = 25
    cure_seconds = _CHUCK_TIER_SECONDS

    consumable_tags = ["mutant_raider_raw_hide"]
    consumable_names = ["mutant raider raw hide"]

    output_item_keys = ["mutant_raider_sinew"]

    success_message = "You draw the sinew out of the chamber."



class MutantRaiderCuredHideRecipe(CuringRecipe):
    "Salt and hang a raw chuck until it keeps."

    name = "mutant raider cured hide"
    required_level = 1
    xp_reward = 25
    cure_seconds = _CHUCK_TIER_SECONDS

    consumable_tags = ["mutant_raider_raw_hide"]
    consumable_names = ["mutant raider raw hide"]

    output_item_keys = ["mutant_raider_cured_hide"]

    success_message = "You draw the cured hide out of the chamber."



class MutantRaiderPrimeSinewRecipe(CuringRecipe):
    """Draw a whole prime hide down into one even cord.

    The tier 2 string, and the Gunsmith's only reason to level Curing. It
    sits at the same level the filet does, and takes the hide the same cut
    yields, so one corpse at Butchery 10 feeds the food chain and the
    projectile chain alike.
    """

    name = "mutant raider prime sinew"
    required_level = 10
    xp_reward = 50
    cure_seconds = _PRIME_TIER_SECONDS

    consumable_tags = ["mutant_raider_prime_raw_hide"]
    consumable_names = ["mutant raider prime raw hide"]

    output_item_keys = ["mutant_raider_prime_sinew"]

    success_message = "You draw the prime sinew out of the chamber."



class MutantRaiderCuredFatlessMeatRecipe(CuringRecipe):
    """Cure meat the cooker has already rendered lean.

    The second processing pass: input is a Rendering OUTPUT, not a Butchery
    cut, so reaching this recipe at all means having levelled two skills.
    """

    name = "mutant raider cured fatless meat"
    required_level = 2
    xp_reward = 25
    cure_seconds = _CHUCK_TIER_SECONDS

    consumable_tags = ["mutant_raider_fatless_meat"]
    consumable_names = ["mutant raider fatless meat"]

    output_item_keys = ["mutant_raider_cured_fatless_meat"]

    success_message = "You draw the cured fatless meat out of the chamber."



class MutantRaiderCuredFiletRecipe(CuringRecipe):
    "Cure a raw filet whole, which takes twice as long and is worth it."

    name = "mutant raider cured filet"
    required_level = 10
    xp_reward = 50
    cure_seconds = _PRIME_TIER_SECONDS

    consumable_tags = ["mutant_raider_raw_filet"]
    consumable_names = ["mutant raider raw filet"]

    output_item_keys = ["mutant_raider_cured_filet"]

    success_message = "You draw the cured filet out of the chamber."



class MutantRaiderCuredPrimeMeatRecipe(CuringRecipe):
    "Cure the cooker's prime cut -- the chain's longest route to one item."

    name = "mutant raider cured prime meat"
    required_level = 12
    xp_reward = 70
    cure_seconds = _PRIME_TIER_SECONDS

    consumable_tags = ["mutant_raider_prime_meat"]
    consumable_names = ["mutant raider prime meat"]

    output_item_keys = ["mutant_raider_cured_prime_meat"]

    success_message = "You draw the cured prime meat out of the chamber."



class MutantRaiderPrimeCuredHideRecipe(CuringRecipe):
    """Cure a whole prime hide flat instead of drawing it into a cord.

    THE RECIPE THAT WAS MISSING. `mutant_raider_prime_cured_hide` has had an
    ItemDef since the capes shipped, and two Metalsmith recipes consume it --
    scrap hide cape at level 11 and copper hide cape at 21. Nothing produced
    it. Both capes were uncraftable from the day they were written until
    09/21/2026, and no test caught it because a recipe that consumes a tag
    nothing outputs is a valid recipe.

    It takes the SAME prime raw hide that prime sinew takes, at the same
    level, so one hide is either a bowstring or a cape panel. That is the
    decision the tier is for: the Gunsmith and the Metalsmith compete for one
    cut off one corpse, the way the tallow-or-fatless-meat choice makes
    Rendering a decision rather than a step.
    """

    name = "mutant raider prime cured hide"
    required_level = 10
    xp_reward = 50
    cure_seconds = _PRIME_TIER_SECONDS

    consumable_tags = ["mutant_raider_prime_raw_hide"]
    consumable_names = ["mutant raider prime raw hide"]

    output_item_keys = ["mutant_raider_prime_cured_hide"]

    success_message = "You draw the prime cured hide out of the chamber, flat and stiff."



# ─── Mutant giant tier ──────────────────────────────────────────────────────
# The same six shapes one tier up, at 20 to 32 against the raider's 0 to 12.
# Every XP value is twice the raider counterpart, which is the rule the giant
# entries in world/item_defs/ follow for value, weight and heal.
#
# SIX RECIPES, NOT SEVEN. The giant has no prime sinew and no prime cured
# hide, because nothing would consume either one -- the copper shortbow takes
# giant sinew and the copper hide cape takes giant cured hide, and there is no
# metal above copper to hang a fourth tier on. The corpse still yields a giant
# prime raw hide, and the tier that needs it adds the two recipes then. See
# gatherables.py for the line drawn between a gathered orphan and a crafted
# one.


class MutantGiantCuredChuckRecipe(CuringRecipe):
    "Salt and hang a giant chuck until it keeps."

    name = "mutant giant cured chuck"
    required_level = 20
    xp_reward = 50
    cure_seconds = _GIANT_CHUCK_TIER_SECONDS

    consumable_tags = ["mutant_giant_raw_chuck"]
    consumable_names = ["mutant giant raw chuck"]

    output_item_keys = ["mutant_giant_cured_chuck"]

    success_message = "You haul the cured giant chuck out of the chamber."



class MutantGiantSinewRecipe(CuringRecipe):
    """Draw a giant hide down into cord.

    The Gunsmith's reason to level Curing past the raider. It strings the
    copper shortbow, which completes the metal bow ladder: rusty at 0, scrap
    at 10, copper at 20.
    """

    name = "mutant giant sinew"
    required_level = 20
    xp_reward = 50
    cure_seconds = _GIANT_CHUCK_TIER_SECONDS

    consumable_tags = ["mutant_giant_raw_hide"]
    consumable_names = ["mutant giant raw hide"]

    output_item_keys = ["mutant_giant_sinew"]

    success_message = "You draw the giant sinew out of the chamber."



class MutantGiantCuredHideRecipe(CuringRecipe):
    """Cure a giant hide stiff.

    The copper hide cape takes this. It used to take the raider's prime cured
    hide, which the scrap hide cape also takes -- so the two capes shared one
    input and the copper tier asked nothing new of the player. See
    metalsmith_recipes.py.
    """

    name = "mutant giant cured hide"
    required_level = 21
    xp_reward = 50
    cure_seconds = _GIANT_CHUCK_TIER_SECONDS

    consumable_tags = ["mutant_giant_raw_hide"]
    consumable_names = ["mutant giant raw hide"]

    output_item_keys = ["mutant_giant_cured_hide"]

    success_message = "You draw the giant cured hide out of the chamber."



class MutantGiantCuredFatlessMeatRecipe(CuringRecipe):
    """Cure giant meat the cooker has already rendered lean.

    The giant tier's second processing pass, and the deepest thing the player
    can reach at level 22: the input is a Rendering output, so this needs
    Butchery 20, Rendering 22 and Curing 22 together.
    """

    name = "mutant giant cured fatless meat"
    required_level = 22
    xp_reward = 50
    cure_seconds = _GIANT_CHUCK_TIER_SECONDS

    consumable_tags = ["mutant_giant_fatless_meat"]
    consumable_names = ["mutant giant fatless meat"]

    output_item_keys = ["mutant_giant_cured_fatless_meat"]

    success_message = "You draw the cured giant fatless meat out of the chamber."



class MutantGiantCuredFiletRecipe(CuringRecipe):
    "Cure a giant filet whole, which takes twice as long and is worth it."

    name = "mutant giant cured filet"
    required_level = 30
    xp_reward = 100
    cure_seconds = _GIANT_PRIME_TIER_SECONDS

    consumable_tags = ["mutant_giant_raw_filet"]
    consumable_names = ["mutant giant raw filet"]

    output_item_keys = ["mutant_giant_cured_filet"]

    success_message = "You draw the cured giant filet out of the chamber."



class MutantGiantCuredPrimeMeatRecipe(CuringRecipe):
    "Cure the cooker's prime giant cut -- the deepest single item in the game."

    name = "mutant giant cured prime meat"
    required_level = 32
    xp_reward = 140
    cure_seconds = _GIANT_PRIME_TIER_SECONDS

    consumable_tags = ["mutant_giant_prime_meat"]
    consumable_names = ["mutant giant prime meat"]

    output_item_keys = ["mutant_giant_cured_prime_meat"]

    success_message = "You draw the cured giant prime meat out of the chamber."
