"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Implementation of the Rendering processing skill.
"""



from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill



class Rendering(BaseSkill):
    """
    Purpose: Manages the mechanics and unlock requirements for Rendering.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        The food chain's answer to Foundry, and it has the same shape for the
        same reason: a processing skill whose whole behaviour is its recipes.
        There is no `execute` here, no tool lookup and no cooldown, because a
        render is a craft at a facility -- BlackoutRecipe already gates on
        level, consumes the cut and awards the XP, so a body on this class
        would be a second place those things could be decided.

        Contrast Butchery, which IS a body (GatheringSkill): working a corpse
        with a blade happens in the world, against an object the player is
        standing next to, and nothing in the crafting contrib models that.
        The moment the cut is in the bag, the chain becomes recipes.

    Notes/References:
        Recipes in systems/gameplay/crafting/recipes/rendering_recipes.py;
        levels and XP come from the crafting spreadsheet, which is the source
        of truth for this chain wherever it and the skill-tree map disagree.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    key = skill_constants.RENDERING_SKILL_KEY
    name = "Rendering"
    category = "Processing"
    description = "Proficiency with cooking a carcass down into fat and lean meat."
