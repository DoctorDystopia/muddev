"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/27/2026
Description: Blood Sword - using bit blade rules for now. TODO: add blood sword specific rules.
"""



from systems.gameplay.combat import constants as const

from .base_rules import BaseActionRules



# Public constant definitions



class BloodSwordRules(BaseActionRules):
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

    Author: Nick Hobar
    Creation date: 10/27/2026
    """

    key = "blood_sword"
    name = "blood_sword"
    MAX_EXPONENT = 3 # max hit 7
    description = "Powered by the blood of my enemies." # unsure where this description is used
    priority = const.RULES_PRIORITY_WEAPON

    def roll_damage(self, context, result) -> None:
        """2^X -1  damage, where X from 0 to MAX_EXPONENT is a roll from 0 to MAX_EXPONENT inclusive.
        """
        roll = context.rng.randint(0, self.MAX_EXPONENT)
        result.damage = 2 ** roll - 1
        # The max hit is the top face of this blade. The hit line and the
        # hitsplat read the two through ActionResult.is_max_hit.
        result.max_hit = 2 ** self.MAX_EXPONENT - 1
        result.rolled = result.damage

# class BrokenBloodSwordRules(BloodSwordRules):
#     key = "broken_blood_sword"
#     name = "Broken blood sword"
#     MAX_EXPONENT = 1 # max hit 1

# class Mk2BloodSwordRules(BloodSwordRules): # `#` in class name ok?
#     key = "mk2_blood_sword"
#     name = "MK.II blood sword"
#     MAX_EXPONENT = 5 # max hit 31

# #0x7F = hexadecimal, 0b01111111 = binary, also the DEL ascii code is 127 https://ss64.com/ascii.html
# class LegendaryBloodSwordRules(BloodSwordRules):
#     key = "legendary_blood_sword"
#     name = "0x7F" # is it fine for name to not match key?
#     MAX_EXPONENT = 7 # max hit 127
