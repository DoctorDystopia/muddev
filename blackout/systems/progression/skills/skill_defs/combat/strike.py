"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Implementation of the Melee combat skill (accuracy axis).
"""

from systems.progression.skills.skill_defs.base_skill import BaseSkill


class Strike(BaseSkill):
    """
    Purpose: Defines the Strike skill. Blackout's melee-accuracy axis —
    feeds combat_calc.effective_level on the strike skill axis.
    OSRS calls this "Attack".

    Passive skill: no standalone `execute` action and no unlock gate, so
    BaseSkill's defaults are inherited rather than restated. The combat
    handler reads character.skills.get_level('strike') when computing
    attacker_eff_atk.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """

    key = "strike"
    name = "Strike"
    category = "Combat"
    description = "Proficiency with melee weapons. Determines attack accuracy."
