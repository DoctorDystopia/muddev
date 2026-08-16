"""
GNU License or generic module header.
Author: Danny Hered
Creation date: 08/15/2026
Description: Bit Blade - a gadget that hits for 0, 1, 2, 4, 8, 16, 32
             Does not scale with Brawn or gear

             roll for X where -1 <= X <= 5, the damage is 2^X, so the damage is:
             0, 1, 2, 4, 8, 16, 32

             all numbers speculative

             intended use:
             - Enemy weapon + gimmick player weapon
             - room to encode an arg into the damage pattern
             - part of a set
                - broken bit blade only hits 0, 1
                - raider bit blade hits up to 8
                - strong bit blade hits up to 32
                - excellent bit blade hits up to 64
                - legendary bit blade hits up to 128 note: near guaranteed to kill player
"""

from systems.combat import constants as const

from .base_rules import BaseActionRules


# Public constant definitions

# The die. Twenty sides, read straight off the design note.
BIT_BLADE_MAX_EXPONENT = 5
BIT_BLADE_MIN_EXPONENT = -1
BIT_BLADE_MAX_HIT = 2**BIT_BLADE_MAX_EXPONENT


class BitBladeRules(BaseActionRules):
    """
    Purpose: Replace only the damage roll with a bit blade's damage pattern.

    Entry:
        No conditions. Applies whenever an equipped item names this key.

    Exit/Returns:
        Not applicable — a rules definition.

    Module Globals:
        BIT_BLADE_MAX_EXPONENT, BIT_BLADE_MAX_HIT,


    Methodology:
        Overrides roll_damage and nothing else, so accuracy, the effective
        levels, and every modifier channel still apply exactly as they would
        for any other weapon -- this sword is inaccurate or accurate for the
        same reasons a real one is, it just hits for a different distribution.

        Deliberately does NOT call super() and does NOT consult max_hit. The
        OSRS ceiling is a function of Brawn and gear, and a dX that got
        clamped to it would be a dX in name only: at low Brawn every roll
        above the ceiling would flatten to the same number.

        RULES_PRIORITY_WEAPON: this is a weapon behaving as itself, which
        should beat a generic modifier but lose to a whole-action override.

    Notes/References:
        Draws one rng.randint, in the same position the default damage roll
        occupies, so the accuracy draw still comes first and a seeded action
        stays reproducible.

    Author: Danny Hered
    Creation date: 08/15/2026
    """

    key = "bit_blade"
    name = "Bit Blade"
    description = "0, 1, 2, 4, 8, 16, 32" #unsure where this description is used
    priority = const.RULES_PRIORITY_WEAPON

    def roll_damage(self, context, result) -> None:
        """2^X damage, where X is a roll from -1 to BIT_BLADE_MAX_EXPONENT inclusive.
           a roll of -1 is a fumble and does 0 damage, a roll of 0 does 1 damage, etc.
        """
        roll = context.rng.randint(BIT_BLADE_MIN_EXPONENT, BIT_BLADE_MAX_EXPONENT)

        if roll == BIT_BLADE_MIN_EXPONENT:
            result.damage = 0
            return
        
        result.damage = 2 ** roll