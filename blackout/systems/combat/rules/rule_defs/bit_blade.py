"""
GNU License or generic module header.
Author: Danny Hered
Creation date: 08/15/2026
Description: Bit Blade - a gadget that hits for 2**X - 1, i.e. 0, 1, 3, 7, 15, 31

             Does not scale with Brawn

            Formulas
            
            2**X
            x=0, max hit = 1
            x=1, max hit = 2
            x=2, max hit = 4
            x=3, max hit = 8
            x=4, max hit = 16
            x=5, max hit = 32
            x=6, max hit = 64
            x=7, max hit = 128

            2**X - 1 CURRENT FORMULA
            x=0, max hit = 0
            x=1, max hit = 1
            x=2, max hit = 3
            x=3, max hit = 7
            x=4, max hit = 15
            x=5, max hit = 31
            x=6, max hit = 63
            x=7, max hit = 127

            concept:
            some bitblades are X% corrupted, flavor as not /0 safe, or overflow or something
             - X% chance for bad outcome, damage?, destroyed -> broken_bit_blade
             - improve, fix bitblade through crafting, upgrade a tier or remove corruption
             - enemy progression, corrupted bit-blade -> bit-blade -> corrupted mk2 bit-blade, etc

             - Primarily a defining weapon of an enemy type or faction

             - gimmick player weapon, should NOT be bis because:
                - it doesn't scale with brawn, it has the potential to diminish value of the brawn stat
                - Standard OSRS weapon hits have more variability on hit, only 2-7 discrete outcomes for hits may break the enjoyability of combat

             - Possible to encode an arg into this weapon
"""

from systems.combat import constants as const

from .base_rules import BaseActionRules


# Public constant definitions


class BitBladeRules(BaseActionRules):
    """
    Purpose: Replace only the damage roll with a bit blade's damage pattern.

    Entry:
        No conditions. Applies whenever an equipped item names this key.

    Exit/Returns:
        Not applicable — a rules definition.

    Module Globals:


    Methodology:
        Overrides roll_damage 

        Implement a family of bit-blade weapons

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
    name = "bit-blade"
    MAX_EXPONENT = 3 # max hit 7
    description = "??? placeholder ???" # unsure where this description is used
    priority = const.RULES_PRIORITY_WEAPON

    def roll_damage(self, context, result) -> None:
        """2^X -1  damage, where X from 0 to MAX_EXPONENT is a roll from 0 to MAX_EXPONENT inclusive.
        """
        roll = context.rng.randint(0, self.MAX_EXPONENT)
        result.damage = 2 ** roll - 1

class BrokenBitBladeRules(BitBladeRules):
    key = "broken_bit_blade"
    name = "Broken bit-blade"
    MAX_EXPONENT = 1 # max hit 1

class Mk2BladeRules(BitBladeRules): # `#` in class name ok?
    key = "mk2_bit_blade"
    name = "MK.II bit-blade"
    MAX_EXPONENT = 5 # max hit 31

#0x7F = hexadecimal, 0b01111111 = binary, also the DEL ascii code is 127 https://ss64.com/ascii.html
class LegendaryBitBladeRules(BitBladeRules):
    key = "legendary_bit_blade"
    name = "0x7F" # is it fine for name to not match key?
    MAX_EXPONENT = 7 # max hit 127
