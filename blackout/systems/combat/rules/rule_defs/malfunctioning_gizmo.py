"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Malfunctioning gizmo — a gadget that zaps four times in five and
             blows up in the wielder's hand the fifth.
"""

from systems.combat import constants as const

from ..context import ActionResult
from .base_rules import BaseActionRules


# Public constant definitions

# Faces on the outcome die.
GIZMO_ROLL_SIDES = 5

# Faces 1..n zap, the remaining face backfires.
GIZMO_ZAP_OUTCOMES = 4

# Flat damage to the target on a zap.
GIZMO_ZAP_DAMAGE = 5

# Flat damage to the WIELDER when it backfires.
GIZMO_BACKFIRE_DAMAGE = 5

# A gizmo discharge never rolls for accuracy, so its reported probability is certainty.
GIZMO_CERTAIN_HIT = 1.0


class MalfunctioningGizmoRules(BaseActionRules):
    """
    Purpose: Replace the whole action with a five-sided outcome roll.

    Entry:
        No conditions. Applies whenever an equipped item names this key.

    Exit/Returns:
        Not applicable — a rules definition.

    Module Globals:
        GIZMO_ROLL_SIDES, GIZMO_ZAP_OUTCOMES, GIZMO_ZAP_DAMAGE,
        GIZMO_BACKFIRE_DAMAGE, GIZMO_CERTAIN_HIT read.

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

    key = "malfunctioning_gizmo"
    name = "Malfunctioning Gizmo"
    description = "Spits wailing electric arcs. Surely this thing won't zap you. Feeling lucky?"
    priority = const.RULES_PRIORITY_OVERRIDE

    def resolve(self, context) -> ActionResult:
        """Roll the outcome die: zap the target, or blow up on the wielder.

        damage_type is ENERGY either way: the gizmo is an energy weapon, and
        a backfire is still that same gizmo discharging, just into its own
        wielder instead of the target. There is no separate "backfire" type.
        """
        result = ActionResult(
            hit=True,
            hit_prob=GIZMO_CERTAIN_HIT,
            damage_type=const.DAMAGE_TYPE_ENERGY,
        )
        roll = context.rng.randint(1, GIZMO_ROLL_SIDES)

        if roll <= GIZMO_ZAP_OUTCOMES:
            result.damage = GIZMO_ZAP_DAMAGE

            return result

        result.self_damage = GIZMO_BACKFIRE_DAMAGE

        return result
