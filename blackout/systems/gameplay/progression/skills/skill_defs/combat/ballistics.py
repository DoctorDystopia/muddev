"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/17/2026
Description: Implementation of the Ballistics combat skill (projectile damage axis).
"""



from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill



class Ballistics(BaseSkill):
    """
    Purpose: Defines the Ballistics skill. Blackout's projectile-damage axis —
    feeds combat_calc.effective_level on the ballistics skill axis.
    OSRS puts accuracy and damage for a bow on one skill. Blackout splits
    them, the same way it splits melee into Strike and Brawn.

    Guns is the accuracy half. This is the damage half, and the rapid and
    penetrate styles are the two that train it.

    Passive skill: no standalone `execute` action and no unlock gate, so
    BaseSkill's defaults are inherited rather than restated. The projectile
    action rules read character.skills.get_level('ballistics') when they
    compute the effective strength level.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """

    key = skill_constants.SKILL_KEY_BALLISTICS
    name = "Ballistics"
    category = skill_constants.SKILL_CATEGORY_COMBAT
    description = "Projectile power. Determines how hard a shot lands."
