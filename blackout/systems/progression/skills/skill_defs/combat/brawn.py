"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Implementation of the Brawn combat skill (damage axis).
"""

from systems.progression.skills.skill_defs.base_skill import BaseSkill


class Brawn(BaseSkill):
    """
    Purpose: Defines the Brawn skill. Blackout's melee-damage axis — feeds
    combat_calc.effective_level on the brawn skill axis. OSRS
    calls this "Strength"; we name it Brawn because Blackout already has
    a "Strength" Augmentation concept pending.

    Passive skill: no standalone `execute` action and no unlock gate, so
    BaseSkill's defaults are inherited rather than restated. The combat
    handler reads character.skills.get_level('brawn') when computing
    attacker_eff_str.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """

    key = "brawn"
    name = "Brawn"
    category = "Combat"
    description = "Raw melee power. Determines how hard you hit."
