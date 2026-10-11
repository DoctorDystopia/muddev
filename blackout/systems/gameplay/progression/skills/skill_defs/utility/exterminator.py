"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: Implementation of the Exterminator utility skill.
"""



from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill



class Exterminator(BaseSkill):
    """
    Purpose: Defines the Exterminator skill. A Preceptor gives the player a
    task to kill a count of one creature type. A task kill gives XP, and the
    player picks buffs during the task. OSRS calls a skill of this kind
    "Slayer".

    Passive skill: no standalone `execute` action and no unlock gate. Thus,
    the defaults of BaseSkill stay. The task system of DESIGN-0012 pays the
    XP. Exterminator does not count in the combat level (Nick, 10/06/2026).

    Notes/References:
        The vault note 03_Systems/Skills/Utility_Skills/Exterminator_Skill.md
        owns the rules. world/creature_types.py owns the creature types.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """

    key = skill_constants.SKILL_KEY_EXTERMINATOR
    name = "Exterminator"
    category = skill_constants.SKILL_CATEGORY_UTILITY
    description = "Tasks from a Preceptor to kill one kind of creature. Picks buffs during a task."
