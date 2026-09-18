"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/17/2026
Description: Projectile combat-level branch -- Guns (accuracy) + Ballistics
             (damage), Blackout's Ranged analog.
"""

from systems.gameplay.combat.combat_level.branch_defs.base_branch import CombatBranch
from systems.gameplay.progression.skills.constants import (
    SKILL_KEY_BALLISTICS,
    SKILL_KEY_GUNS,
)


class ProjectileBranch(CombatBranch):
    """
    Purpose: Defines the projectile branch of combat level.

    A PAIRED BRANCH, NOT A SOLO ONE. OSRS gives Ranged the solo-skill
    multiplier because one skill there carries accuracy and damage together.
    Blackout splits those across Guns and Ballistics, exactly as it splits
    melee across Strike and Brawn, so this branch names two skills and their
    levels sum raw -- the same arithmetic MeleeBranch gets, which is what
    keeps a bow build and a sword build on one scale.

    Until this file existed, a character who trained nothing but Guns had a
    combat level built from Fortitude and Defense alone. The skill they had
    levelled contributed nothing, and nothing raised an error about it.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """

    key = "projectile"
    name = "Projectile"
    skill_keys = (SKILL_KEY_GUNS, SKILL_KEY_BALLISTICS)
