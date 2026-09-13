"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Implementation of the Gastronomy production skill.
"""



from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill



class Gastronomy(BaseSkill):
    """
    Purpose: Manages the mechanics and unlock requirements for Gastronomy.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        Recipe-driven, so there is no `execute` -- Metalsmith's shape, which is
        the right comparison: Gastronomy is to the food chain what Metalsmith is
        to the metal one, the production skill that turns components into the
        thing a player actually uses.

        It is the only stage of the food chain with nothing unusual about it.
        Butchery needed a body because working a corpse happens in the world;
        Curing needed a handler because its output arrives later. A meal is made
        at a bench out of things already in the bag, which is what the crafting
        contrib has always modelled.

    Notes/References:
        Recipes in systems/gameplay/crafting/recipes/gastronomy_recipes.py, and
        they are the first in the game taking two DIFFERENT inputs.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    key = skill_constants.GASTRONOMY_SKILL_KEY
    name = "Gastronomy"
    category = "Production"
    description = "Skill in turning preserved and rendered meat into food worth eating."
