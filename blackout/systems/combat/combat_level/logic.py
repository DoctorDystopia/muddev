"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Combat level -- the derived "how tough is this combatant" number
             computed from Combat Specialty skill levels, OSRS-derived.
"""

import math

from systems.combat import constants as const
from systems.progression.skills.registry import SKILL_REGISTRY

from .registry import COMBAT_BRANCH_REGISTRY



def _skill_level(character: object, skill_key: str) -> int:
    """
    Purpose: Read a skill level for combat-level math without raising on a
    Combat Specialty that hasn't shipped yet.

    Entry:
        character - any object exposing a `skills` handler (Character's
        SkillHandler, or HostileNPC's StatBlockSkills).
        skill_key - a skill key that MAY or may not be registered.

    Exit/Returns:
        Returns the integer level, or 0 if skill_key is not (yet) in
        SKILL_REGISTRY.

    Module Globals:
        SKILL_REGISTRY read.

    Methodology:
        SkillHandler.get_level -> logic.get_level -> ensure_skill raises
        ValueError for any key outside SKILL_REGISTRY. That is correct for
        gameplay code operating on skills that are supposed to exist, but
        wrong here: combat level is deliberately built against Combat
        Specialty skills (Guns, Psych, Convoke, Toxin, Augmentation) that are
        still vault stubs today. A branch or base-skill entry naming one of
        them must contribute 0, not crash every combat_level read until that
        skill ships.

        StatBlockSkills.get_level never raises (an NPC that declares no level
        in a skill reads the absent-skill floor), so this guard changes
        behaviour only for real Characters -- which is exactly where it is
        needed.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    if skill_key not in SKILL_REGISTRY:
        return 0

    return character.skills.get_level(skill_key)


def get_combat_level(character: object) -> int:
    """
    Purpose: Compute a combatant's combat level.

    Entry:
        character - any object exposing a `skills` handler (Character or
        HostileNPC).

    Exit/Returns:
        Returns the integer combat level.

    Module Globals:
        const.COMBAT_LEVEL_BASE_WEIGHT, const.COMBAT_LEVEL_BASE_SKILLS,
        const.COMBAT_LEVEL_AUGMENTATION_SKILL,
        const.COMBAT_LEVEL_AUGMENTATION_DIVISOR read.
        COMBAT_BRANCH_REGISTRY read.

    Methodology:
        Base sums Fortitude + Defense (OSRS's Hitpoints + Defence) plus
        Augmentation halved (OSRS's Prayer/2) -- Blackout's Prayer analog is
        universal and buff-only, the same structural role, so it gets the
        same halving treatment before joining the flat base.

        Every registered CombatBranch computes its own score off the same
        guarded level lookup; only the HIGHEST one counts, exactly as OSRS
        counts only a character's best-trained combat style. Today that
        registry holds exactly one branch (melee), so max() has one
        candidate -- not a special case, just what an incomplete Combat
        Specialty roster looks like.

    Notes/References:
        Coefficients are OSRS's literal values (see constants.py). Blackout's
        0-127 skill range therefore produces a higher ceiling than OSRS's
        familiar 126 -- accepted, not corrected for.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    def _lookup(skill_key: str) -> int:
        return _skill_level(character, skill_key)

    base_levels = sum(_lookup(skill_key) for skill_key in const.COMBAT_LEVEL_BASE_SKILLS)
    augmentation_contribution = math.floor(
        _lookup(const.COMBAT_LEVEL_AUGMENTATION_SKILL) / const.COMBAT_LEVEL_AUGMENTATION_DIVISOR
    )

    base = const.COMBAT_LEVEL_BASE_WEIGHT * (base_levels + augmentation_contribution)

    branch_scores = [
        branch.compute_score(_lookup) for branch in COMBAT_BRANCH_REGISTRY.values()
    ]
    best_branch_score = max(branch_scores, default=0.0)

    combat_level = math.floor(base + best_branch_score)

    return combat_level
