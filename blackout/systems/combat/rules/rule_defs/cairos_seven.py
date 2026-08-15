"""
GNU License or generic module header.
Author: Danny Hered
Creation date: 08/14/2026
Description: Cairo's Seven — a gadget dagger with maxhit 6, 
             If you hit a 6
             one of several things can happen, 
             ideally they all have separate rolls and can all happen at once, 
             list of outcomes:
             0) a piece of junk falls off the dagger onto the ground and you lose 10 credits
             1) you get 100 credits
             2) you get 1000 credits
             3) you deal 12 damage to the target
             4) you deal 36 damage to the target
             5) teleport you within a circle of X radius of yourself
             6) spawn a mutant raider
"""

from systems.combat import constants as const

from ..context import ActionResult
from .base_rules import BaseActionRules


# Public constant definitions

# Faces on the outcome die.
CAIROS_SEVEN_ROLL_SIDES = 6

# Faces 1..n zap, the remaining face backfires.
CAIROS_SEVEN_JACKPOT = 6

# How many credits does it cost to swing?
CAIROS_SEVEN_COST = 0


class CairosSevenRules(BaseActionRules):
    """
    Purpose: Replace the whole action with a seven-sided outcome roll.

    Entry:
        No conditions. Applies whenever an equipped item names this key.

    Exit/Returns:
        Not applicable — a rules definition.

    Module Globals:
        CAIROS_SEVEN_ROLL_SIDES, CAIROS_SEVEN_JACKPOT, CAIROS_SEVEN_COST read.

    Methodology:
        Overrides `resolve`, which is the widest seam there is: accuracy, the
        effective levels, the max hit, and every modifier channel are all
        bypassed. That is correct HERE -- "4/5 chance to zap for 5" means
        exactly 5, not 5 filtered through the defender's armour -- but it is
        the wrong seam for anything that should still respect gear. A weapon
        that only changes the damage die overrides roll_damage instead.

        RULES_PRIORITY_OVERRIDE, because a definition that discards the whole
        pipeline has to outrank one that merely adjusts a step of it.

    Notes/References:
        Draws exactly one rng.randint and never rng.random, so the accuracy
        draw the default path makes does not happen. A seeded test therefore
        cannot compare this outcome sequence against a default action's.

        The design note's "turns into junk on explosion" is NOT implemented:
        transforming the item is a trigger hook (on_hit / on_kill), which is
        a later cut. The damage half works standalone.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    key = "cairos_seven"
    name = "cairos seven"
    description = "?" # not sure when this description is used?
    priority = const.RULES_PRIORITY_WEAPON

    def roll_damage(self, context, result) -> None:
        """Roll the d20, sending a natural 1 back at the wielder."""
        super().roll_damage(context, result)
        roll = context.rng.randint(TOY_SWORD_DIE_MIN, TOY_SWORD_DIE_MAX)

        if roll == TOY_SWORD_FUMBLE_ROLL:
            result.damage = 0
            result.self_damage = TOY_SWORD_FUMBLE_DAMAGE

            return

        result.damage = roll
    priority = const.RULES_PRIORITY_OVERRIDE

    def roll_damage(self, context, result) -> None:
        """Roll the outcome die: zap the target, or blow up on the wielder.

        damage_type is ENERGY either way: the gizmo is an energy weapon, and
        a backfire is still that same gizmo discharging, just into its own
        wielder instead of the target. There is no separate "backfire" type.
        """
        result = ActionResult(
            hit=True,
            max_hit=CAIROS_SEVEN_ROLL_SIDES,
            damage_type=const.DAMAGE_TYPE_ENERGY,
        )
        roll = context.rng.randint(0, CAIROS_SEVEN_ROLL_SIDES)

        if roll == CAIROS_SEVEN_JACKPOT:
            result.damage = CAIROS_SEVEN_COST

            return result

        return result
