"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Skill category Processing - Rendering recipe definitions.

             Four recipes, two per Butchery cut: boil the fat out of it for
             tallow, or cook the fat off it and keep what is left. They are
             SEPARATE recipes rather than one recipe with two outputs, which is
             the whole economic decision of the stage -- a chuck spent on
             tallow is a chuck that yields no fatless meat, and the Gastronomy
             steak downstream needs one of each.

             Levels and XP are transcribed from the crafting spreadsheet
             (`Blackout - Crafting Recipes (3-tab restructure)`), which is the
             source of truth for this chain wherever it and the skill-tree map
             disagree. The +2 between a tier's tallow and its meat is
             deliberate: tallow is what the skill is learned on.
"""



from systems.gameplay.progression.skills import constants as skill_constants

from ..blackout_recipe import BlackoutRecipe
from ..constants import CATEGORY_RENDERING



# Private constant definitions

# Every recipe here is worked at the rendering cooker and every one teaches
# Rendering, so the three declarations that would otherwise be copied onto
# four classes are stated once. A recipe that needed a second tool would
# override tool_tags rather than this being widened.
_COOKER_TOOL_TAGS = ["rendering_cooker"]
_COOKER_TOOL_NAMES = ["rendering cooker"]



class _RenderingRecipe(BlackoutRecipe):
    """
    Purpose: Shared declarations for every Rendering recipe.

    Entry:
        Subclasses set name, required_level, xp_reward, the consumable pair and
        the output.

    Exit/Returns:
        No conditions.

    Module Globals:
        _COOKER_TOOL_TAGS, _COOKER_TOOL_NAMES read.

    Methodology:
        A base class, not a mixin and not four copies. It declares no `name`,
        so the recipe registry's placeholder-name filter drops it and it never
        reaches the craft menu -- the same way BlackoutRecipe itself is
        excluded from both recipe modules that import it.

    Notes/References:
        foundry_recipes.py restates these five lines on each of its four
        classes. That is fine at four and was the model for this module; the
        base class is the version that stays honest when the cooker gains a
        fifth recipe.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    category = CATEGORY_RENDERING
    required_skill = skill_constants.RENDERING_SKILL_KEY
    skill_category = "processing"

    tool_tags = _COOKER_TOOL_TAGS
    tool_names = _COOKER_TOOL_NAMES



class MutantRaiderTallowRecipe(_RenderingRecipe):
    "Boil the fat out of a raw chuck, leaving a cake of tallow."

    name = "mutant raider tallow"
    required_level = 0
    xp_reward = 10

    consumable_tags = ["mutant_raider_raw_chuck"]
    consumable_names = ["mutant raider raw chuck"]

    output_item_keys = ["mutant_raider_tallow"]

    success_message = "The chuck gives up its fat, and you skim off a cake of tallow."



class MutantRaiderFatlessMeatRecipe(_RenderingRecipe):
    "Cook a raw chuck down until nothing but lean meat is left."

    name = "mutant raider fatless meat"
    required_level = 2
    xp_reward = 15

    consumable_tags = ["mutant_raider_raw_chuck"]
    consumable_names = ["mutant raider raw chuck"]

    output_item_keys = ["mutant_raider_fatless_meat"]

    success_message = "You cook the chuck down to a lean, dry cut of fatless meat."



class MutantRaiderPrimeTallowRecipe(_RenderingRecipe):
    "Render a raw filet for the clean white fat a good cut carries."

    name = "mutant raider prime tallow"
    required_level = 10
    xp_reward = 20

    consumable_tags = ["mutant_raider_raw_filet"]
    consumable_names = ["mutant raider raw filet"]

    output_item_keys = ["mutant_raider_prime_tallow"]

    success_message = "The filet renders clean, and you set aside a block of prime tallow."



class MutantRaiderPrimeMeatRecipe(_RenderingRecipe):
    "Cook a raw filet down to its dense, close-grained core."

    name = "mutant raider prime meat"
    required_level = 12
    xp_reward = 30

    consumable_tags = ["mutant_raider_raw_filet"]
    consumable_names = ["mutant raider raw filet"]

    output_item_keys = ["mutant_raider_prime_meat"]

    success_message = "You render the filet down to a dense cut of prime meat."
