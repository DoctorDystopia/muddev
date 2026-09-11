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
_CHUCK_TIER_SECONDS = 15.0
_PRIME_TIER_SECONDS = 30.0



class MutantRaiderCuredChuckRecipe(CuringRecipe):
    "Salt and hang a raw chuck until it keeps."

    name = "mutant raider cured chuck"
    required_level = 0
    xp_reward = 10
    cure_seconds = _CHUCK_TIER_SECONDS

    consumable_tags = ["mutant_raider_raw_chuck"]
    consumable_names = ["mutant raider raw chuck"]

    output_item_keys = ["mutant_raider_cured_chuck"]

    success_message = "You draw the cured chuck out of the chamber."



class MutantRaiderCuredFatlessMeatRecipe(CuringRecipe):
    """Cure meat the cooker has already rendered lean.

    The second processing pass: input is a Rendering OUTPUT, not a Butchery
    cut, so reaching this recipe at all means having levelled two skills.
    """

    name = "mutant raider cured fatless meat"
    required_level = 2
    xp_reward = 10
    cure_seconds = _CHUCK_TIER_SECONDS

    consumable_tags = ["mutant_raider_fatless_meat"]
    consumable_names = ["mutant raider fatless meat"]

    output_item_keys = ["mutant_raider_cured_fatless_meat"]

    success_message = "You draw the cured fatless meat out of the chamber."



class MutantRaiderCuredFiletRecipe(CuringRecipe):
    "Cure a raw filet whole, which takes twice as long and is worth it."

    name = "mutant raider cured filet"
    required_level = 10
    xp_reward = 20
    cure_seconds = _PRIME_TIER_SECONDS

    consumable_tags = ["mutant_raider_raw_filet"]
    consumable_names = ["mutant raider raw filet"]

    output_item_keys = ["mutant_raider_cured_filet"]

    success_message = "You draw the cured filet out of the chamber."



class MutantRaiderCuredPrimeMeatRecipe(CuringRecipe):
    "Cure the cooker's prime cut -- the chain's longest route to one item."

    name = "mutant raider cured prime meat"
    required_level = 12
    xp_reward = 20
    cure_seconds = _PRIME_TIER_SECONDS

    consumable_tags = ["mutant_raider_prime_meat"]
    consumable_names = ["mutant raider prime meat"]

    output_item_keys = ["mutant_raider_cured_prime_meat"]

    success_message = "You draw the cured prime meat out of the chamber."
