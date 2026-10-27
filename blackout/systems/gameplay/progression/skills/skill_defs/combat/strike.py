"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Implementation of the Melee combat skill (accuracy axis).
"""



from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.skill_defs.base_skill import BaseSkill
from systems.interface.statefeed import constants as feed_const



class Strike(BaseSkill):
    """
    Purpose: Defines the Strike skill. Blackout's melee-accuracy axis —
    feeds combat_calc.effective_level on the strike skill axis.
    OSRS calls this "Attack".

    Passive skill: no standalone `execute` action and no unlock gate, so
    BaseSkill's defaults are inherited rather than restated. The combat
    handler reads character.skills.get_level('strike') when computing
    attacker_eff_atk.

    Each melee style reads Strike for accuracy, a fist included. Thus,
    `attack_moment` gives each melee swing its sound (10/26/2026).

    Author: Nick Hobar
    Creation date: 07/26/2026
    """

    key = skill_constants.SKILL_KEY_STRIKE
    name = "Strike"
    category = skill_constants.SKILL_CATEGORY_COMBAT
    description = "Proficiency with melee weapons. Determines attack accuracy with melee weapons."
    attack_moment = feed_const.MOMENT_MELEE_SWING
