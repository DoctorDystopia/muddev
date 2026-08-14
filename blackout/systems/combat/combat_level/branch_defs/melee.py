"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Melee combat-level branch -- Strike (accuracy) + Brawn (damage),
             Blackout's Attack+Strength analog.
"""

from systems.combat.combat_level.branch_defs.base_branch import CombatBranch


class MeleeBranch(CombatBranch):
    """
    Purpose: Defines the melee branch of combat level -- the only Combat
    Specialty implemented in code today. Guns, Psych, Convoke, and Toxin
    (see 03_Systems/Skills/Combat Skills/Combat_Specialty_Skills/ in the
    design vault) each get their own branch_defs/ file the day that skill
    ships; nothing here changes when they do.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """

    key = "melee"
    name = "Melee"
    skill_keys = ("strike", "brawn")
