"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Glass cannon amulet — converts surplus Brawn over Defense into
             extra effective Brawn.
"""

from systems.combat import constants as const
from systems.progression.skills.constants import (
    BRAWN_SKILL_KEY,
    DEFENSE_SKILL_KEY,
)

from .base_rules import BaseActionRules


# Public constant definitions

# How much surplus Brawn buys one bonus level, and what one step is worth.
GLASS_CANNON_BRAWN_PER_STEP = 5
GLASS_CANNON_BONUS_PER_STEP = 1


class GlassCannonAmuletRules(BaseActionRules):
    """
    Purpose: Grant bonus Brawn for every whole step of Brawn above Defense.

    Entry:
        No conditions. Applies whenever an equipped item names this key.

    Exit/Returns:
        Not applicable — a rules definition.

    Module Globals:
        GLASS_CANNON_BRAWN_PER_STEP, GLASS_CANNON_BONUS_PER_STEP read.

    Methodology:
        Overrides contribute_modifiers only, so it composes with everything:
        a player can wear this AND wield a d20 sword, and both apply. That is
        the whole reason modifiers are a separate mechanism from seams --
        modifiers never lose a priority contest.

        The bonus goes into flat_pre rather than flat_post, so it enters
        BEFORE the multiplier stages and is scaled by any Augmentation the
        wearer has up. That makes it behave exactly like a potion boost,
        which is the right class of effect for a passive stat conversion.

        Reads levels through context.levels_for(bag), NOT
        context.attacker_levels. The same amulet can be worn by the defender
        in the same action, and reading the attacker unconditionally would
        make a defender's amulet key off its opponent's stats.

    Notes/References:
        The surplus is FLOORED AT ZERO, deliberately diverging from the design
        note's literal `floor((basebrawn - defense) / 5)`. Python's // floors
        toward negative infinity, so a character at Brawn 10 / Defense 50
        would take an eight-level Brawn PENALTY from equipping a support item.
        Per design decision 08/04: no penalty, the amulet is pure upside and a
        low-Brawn wearer simply gets nothing.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """

    key = "glass_cannon_amulet"
    name = "Glass Cannon"
    description = "Turns Brawn you have over Defense into more Brawn."
    priority = const.RULES_PRIORITY_MODIFIER

    def contribute_modifiers(self, context, bag) -> None:
        """Add one bonus Brawn level per whole step of surplus over Defense."""
        levels = context.levels_for(bag)
        surplus = levels[BRAWN_SKILL_KEY] - levels[DEFENSE_SKILL_KEY]

        if surplus < GLASS_CANNON_BRAWN_PER_STEP:
            return

        steps = surplus // GLASS_CANNON_BRAWN_PER_STEP
        bonus = steps * GLASS_CANNON_BONUS_PER_STEP

        bag.add_flat_pre(const.CHANNEL_BRAWN_LEVEL, bonus)
