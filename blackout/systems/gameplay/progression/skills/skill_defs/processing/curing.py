"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Implementation of the Curing processing skill.
"""



from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill



class Curing(BaseSkill):
    """
    Purpose: Manages the mechanics and unlock requirements for Curing.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        Recipe-driven like Foundry and Rendering, so there is no `execute`
        here. What makes Curing different from both is that its recipes do not
        finish when they are started, and that difference lives entirely in
        systems/gameplay/curing/ -- the slot table, the deadlines and the two
        halves of a cure. None of it is on this class, because a skill
        definition is what a skill IS and not how one of its stages is paced.

        The level curve does two things rather than one. It gates recipes, the
        way every other skill's does, and it also opens CURING SLOTS: one at
        level 0, a second at 10. That second job is why Curing is the first
        skill whose unlocks are not all recipes.

    Notes/References:
        Slots: systems/gameplay/curing/constants.py CURING_SLOT_LEVELS.
        Recipes: systems/gameplay/crafting/recipes/curing_recipes.py.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    key = skill_constants.CURING_SKILL_KEY
    name = "Curing"
    category = "Processing"
    description = "Proficiency with preserving meat so it keeps, and keeps its strength."
