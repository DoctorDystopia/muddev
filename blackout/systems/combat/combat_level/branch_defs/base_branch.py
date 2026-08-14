"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Base combat-branch class -- the offensive/defensive contribution
             one or more Combat Specialty skills make toward combat level.

A branch is DATA plus one hook. Subclasses name the skill(s) they read;
compute_score's default covers both shapes OSRS's own three branches use -- a
two-skill sum (Attack+Strength) or a single skill scaled up to compensate for
having no partner (Ranged, Magic). A future Combat Specialty whose
contribution doesn't reduce to a skill level at all (Convoke's summon uptime,
say) overrides compute_score instead of forcing a new shape into this base
class. That keeps "adding a combat branch" at "adding one file", per the
repo convention.
"""

import math

from systems.combat import constants as const


# Public constant definitions

# Placeholder key on this base class. registry.py refuses to register any
# subclass still carrying it, so a definition that forgets to set `key` is
# reported loudly instead of shadowing a real branch.
BASE_BRANCH_KEY = "base"



class CombatBranch:
    """
    Purpose: Defines the standard interface and default behaviour for a
    competing combat-level branch.
    """

    key = BASE_BRANCH_KEY
    name = "Base Branch"

    # Skill key(s) this branch reads. Exactly one skill applies the OSRS
    # solo-skill multiplier (Ranged, Magic); two or more sum raw, matching
    # Attack+Strength. Order does not matter for the default compute_score.
    skill_keys: tuple = ()


    def compute_score(self, level_lookup) -> float:
        """
        Purpose: Compute this branch's weighted contribution to combat level.

        Entry:
            level_lookup - callable(skill_key: str) -> int. The caller (
            combat_level/logic.py) is responsible for guarding against
            skills that are not yet registered; this method assumes
            whatever it gets back is a valid level.

        Exit/Returns:
            Returns a float score, comparable against every other registered
            branch's score via max(). 0.0 for a branch that names no skills.

        Module Globals:
            const.COMBAT_LEVEL_BRANCH_WEIGHT,
            const.COMBAT_LEVEL_SOLO_SKILL_MULTIPLIER read.

        Methodology:
            len(skill_keys) == 1 mirrors OSRS Ranged/Magic: floor(level * 1.5)
            before the branch weight applies -- compensation for drawing on
            only one stat where a paired branch draws on two. len(skill_keys)
            >= 2 mirrors OSRS melee: the named levels sum raw, no per-skill
            scaling, before the branch weight applies. Both are the SAME
            formula shapes OSRS itself uses across its three branches;
            nothing here is a Blackout invention.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        levels = [level_lookup(skill_key) for skill_key in self.skill_keys]

        if not levels:
            return 0.0

        if len(levels) == 1:
            raw_contribution = math.floor(levels[0] * const.COMBAT_LEVEL_SOLO_SKILL_MULTIPLIER)
        else:
            raw_contribution = sum(levels)

        score = raw_contribution * const.COMBAT_LEVEL_BRANCH_WEIGHT

        return score
