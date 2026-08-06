"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Toy sword — swaps the uniform OSRS damage roll for a d20, where
             a 1 hurts the wielder instead of the target.
"""

from systems.combat import constants as const

from .base_rules import BaseActionRules


# Public constant definitions

# The die. Twenty sides, read straight off the design note.
TOY_SWORD_DIE_MIN = 1
TOY_SWORD_DIE_MAX = 20

# The face that turns the swing on its owner.
TOY_SWORD_FUMBLE_ROLL = 1

# Damage the wielder takes on a fumble. Small on purpose: the fumble is a
# 5% joke, not a build-ending risk.
TOY_SWORD_FUMBLE_DAMAGE = 1


class ToySwordRules(BaseActionRules):
    """
    Purpose: Replace only the damage roll with a twenty-sided die.

    Entry:
        No conditions. Applies whenever an equipped item names this key.

    Exit/Returns:
        Not applicable — a rules definition.

    Module Globals:
        TOY_SWORD_DIE_MIN, TOY_SWORD_DIE_MAX, TOY_SWORD_FUMBLE_ROLL,
        TOY_SWORD_FUMBLE_DAMAGE read.

    Methodology:
        Overrides roll_damage and nothing else, so accuracy, the effective
        levels, and every modifier channel still apply exactly as they would
        for any other weapon -- this sword is inaccurate or accurate for the
        same reasons a real one is, it just hits for a different distribution.

        Deliberately does NOT call super() and does NOT consult max_hit. The
        OSRS ceiling is a function of Brawn and gear, and a d20 that got
        clamped to it would be a d20 in name only: at low Brawn every roll
        above the ceiling would flatten to the same number.

        RULES_PRIORITY_WEAPON: this is a weapon behaving as itself, which
        should beat a generic modifier but lose to a whole-action override.

    Notes/References:
        Draws one rng.randint, in the same position the default damage roll
        occupies, so the accuracy draw still comes first and a seeded action
        stays reproducible.

        The design note's "20 does something special (extra xp, stun)" is NOT
        implemented: those are trigger hooks, a later cut. The die and the
        fumble work standalone.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """

    key = "toy_sword"
    name = "Toy Sword"
    description = "Rolls a d20 for damage. A one finds the wielder instead."
    priority = const.RULES_PRIORITY_WEAPON

    def roll_damage(self, context, result) -> None:
        """Roll the d20, sending a natural 1 back at the wielder."""
        roll = context.rng.randint(TOY_SWORD_DIE_MIN, TOY_SWORD_DIE_MAX)

        if roll == TOY_SWORD_FUMBLE_ROLL:
            result.damage = 0
            result.self_damage = TOY_SWORD_FUMBLE_DAMAGE

            return

        result.damage = roll
