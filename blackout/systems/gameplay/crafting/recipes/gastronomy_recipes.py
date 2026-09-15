"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Skill category Production - Gastronomy recipe definitions.

             The end of the food chain, and the first recipes in the game that
             take two DIFFERENT inputs.

             Every recipe before this one consumed N of a single thing -- the
             battleaxe's three rusty scrap metal are three entries naming the
             same tag. A steak is one tallow AND one fatless meat, which is the
             same mechanism read the other way: consumable_tags is a list of
             UNITS, so two different tags in it ask for one of each. Nothing in
             BlackoutRecipe needed changing to express that, which is worth
             saying out loud because it looks like it should have.

             What the multi-input shape buys is the only real decision in the
             chain. Rendering offers tallow OR fatless meat from one chuck, and
             a steak needs both -- so a steak costs TWO chucks and two renders,
             and the player who spent every chuck on tallow has a bag full of
             fat and nothing to sear in it.

             Levels and XP are transcribed from the crafting spreadsheet, which
             is the source of truth for this chain wherever it and the
             skill-tree map disagree.
"""



from systems.gameplay.progression.skills import constants as skill_constants

from ..blackout_recipe import BlackoutRecipe
from ..constants import CRAFT_CATEGORY_GASTRONOMY



class _GastronomyRecipe(BlackoutRecipe):
    """
    Purpose: Shared declarations for every Gastronomy recipe.

    Entry:
        Subclasses set name, required_level, xp_reward, the consumable pairs
        and the output.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        Declares no `name`, so the recipe registry's placeholder filter keeps it
        out of the craft menu -- the same arrangement _RenderingRecipe uses, and
        test_registry's discovery helper filters for it explicitly.

    Notes/References:
        Unlike CuringRecipe this sets no deferred_handler, so a meal is made the
        moment it is ordered. Gastronomy is production, not preservation: there
        is nothing to wait for once the ingredients are on the bench.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    category = CRAFT_CATEGORY_GASTRONOMY
    required_skill = skill_constants.SKILL_KEY_GASTRONOMY
    skill_category = skill_constants.SKILL_CATEGORY_PRODUCTION

    tool_tags = ["gastro_worktable"]
    tool_names = ["gastro worktable"]



class MutantRaiderSteakRecipe(_GastronomyRecipe):
    "Sear lean meat in its own rendered fat."

    name = "mutant raider steak"
    required_level = 0
    xp_reward = 25

    consumable_tags = ["mutant_raider_tallow", "mutant_raider_fatless_meat"]
    consumable_names = ["mutant raider tallow", "mutant raider fatless meat"]

    output_item_keys = ["mutant_raider_steak"]

    success_message = (
        "The tallow hits the pan and the meat goes in after it. You plate a steak."
    )



class MutantRaiderCuredMeatSandwichRecipe(_GastronomyRecipe):
    """Press two kinds of cured meat together.

    No bread, and there will not be any until something in the wastes grows
    grain -- so the meat is the bread. The sheet promises this heals more than
    cured meat eaten raw, which is what the second Curing level is for.
    """

    name = "mutant raider cured meat sandwich"
    required_level = 2
    xp_reward = 35

    consumable_tags = [
        "mutant_raider_cured_chuck",
        "mutant_raider_cured_fatless_meat",
    ]
    consumable_names = [
        "mutant raider cured chuck",
        "mutant raider cured fatless meat",
    ]

    output_item_keys = ["mutant_raider_cured_meat_sandwich"]

    success_message = (
        "You press the two cured cuts together into something you can eat "
        "walking."
    )



class MutantRaiderPrimeSteakRecipe(_GastronomyRecipe):
    "Sear a prime cut in prime fat."

    name = "mutant raider prime steak"
    required_level = 10
    xp_reward = 45

    consumable_tags = [
        "mutant_raider_prime_tallow",
        "mutant_raider_prime_meat",
    ]
    consumable_names = [
        "mutant raider prime tallow",
        "mutant raider prime meat",
    ]

    output_item_keys = ["mutant_raider_prime_steak"]

    success_message = "The prime tallow barely smokes. You plate a prime steak."



class MutantRaiderPrimeCuredMeatSandwichRecipe(_GastronomyRecipe):
    """The deepest item in the chain.

    Both halves are cured, and one of them was rendered before that -- so this
    single sandwich is two corpses' worth of Butchery, a render, and two cures.
    """

    name = "mutant raider prime cured meat sandwich"
    required_level = 12
    xp_reward = 45

    consumable_tags = [
        "mutant_raider_cured_prime_meat",
        "mutant_raider_cured_filet",
    ]
    consumable_names = [
        "mutant raider cured prime meat",
        "mutant raider cured filet",
    ]

    output_item_keys = ["mutant_raider_prime_cured_meat_sandwich"]

    success_message = (
        "Cured prime meat against a cured filet. You have never made anything "
        "this deliberate."
    )
