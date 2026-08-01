"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Implementation of the Fortitude combat skill (max HP scaling).
"""

from systems.progression.skills.skill_defs.base_skill import BaseSkill


class Fortitude(BaseSkill):
    """
    Purpose: Defines the Fortitude skill. Blackout's hitpoint stat. A
    character's max_hp equals their Fortitude level (OSRS Hitpoints
    analog — call it Hitpoints-equivalent in the math, but the in-world
    stat name is Fortitude, a post-apocalyptic resilience concept).

    Passive skill: no standalone `execute` action and no unlock gate, so
    BaseSkill's defaults are inherited rather than restated.

    Notes/References:
        Seed level 10 at character creation (per constants). Like OSRS,
        Fortitude is the one skill that does NOT start at the global
        DEFAULT_START_LEVEL (which is 0 here).

    Author: Nick Hobar
    Creation date: 07/26/2026
    """

    key = "fortitude"
    name = "Fortitude"
    category = "Combat"
    description = "Constitution and resilience. Determines maximum hitpoints."
