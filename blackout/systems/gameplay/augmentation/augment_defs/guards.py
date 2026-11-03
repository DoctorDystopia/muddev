"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The guard augments (DESIGN-0015, section 4.4, "Warden"): one
             for each damage type that a player takes. A guard cuts a
             percentage of the incoming damage of its type. No guard blocks
             in full (Nick, 10/30/2026). The three share one conflict
             group, so one guard burns at a time, as an OSRS overhead
             prayer does.

             A guard works on the DEFENDER side. The damage roll reads the
             damage channel of the attacker bag, and the pipeline applies
             the defender bag to the landed damage after every override
             (rules/pipeline.py, `_apply_defender_damage`). A guard
             contributes to the defender bag alone, and only when the
             damage type of the action is its own.

             Three guards in one file, because they differ in one field.
             The registry files each class under its own key.
"""

from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.combat import constants as combat_const

from .base_augment import BaseAugment


# One hundred, for a percent.
_PERCENT: float = 100.0


class BaseGuard(BaseAugment):
    """
    Purpose: The shape of a guard. A subclass sets `damage_type` and its
    own key, name, and description.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """

    abstract = True
    family = aug_const.FAMILY_GUARD
    conflict_group = aug_const.CONFLICT_GROUP_GUARD
    drain = 6.0
    pct_per_level = 0.004
    unlock_level = 20
    sockets = (aug_const.SOCKET_BODY, aug_const.SOCKET_SKELETON,
               aug_const.SOCKET_LEG_L, aug_const.SOCKET_LEG_R)

    # One of the DAMAGE_TYPE_* constants of combat. A subclass sets it.
    damage_type = ""

    def contribute(self, context, bag, bonus: float) -> None:
        """
        Purpose: Cut the incoming damage of this type, on the defender side.

        Entry:
            context is the ActionContext.
            bag is the attacker bag or the defender bag.
            bonus is the whole bonus at this action, a positive share.

        Exit/Returns:
            No conditions. Nothing is added on the attacker side, or for an
            action of another damage type.

        Module Globals:
            None.

        Methodology:
            1. Stop on the attacker bag. The attacker bag feeds the roll of
               the holder, and a guard must never cut the own damage.
            2. Stop when the damage type of the action differs.
            3. Add the NEGATIVE bonus into the damage channel. The
               multiplier stage reads 1 + bonus, so -0.2 is 80% damage.

        Notes/References:
            rules.py imports the combat constants at module scope too, so
            the import here closes no ring.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        if bag is not context.defender_bag:
            return

        action_type = context.damage_type()

        if action_type != self.damage_type:
            return

        bag.add_augment_bonus(combat_const.CHANNEL_DAMAGE, -bonus)

    def effect_line(self, level: int) -> str:
        """The cut at this level, as the tip says it."""
        percent = self.bonus_for(level, aug_const.AUG_STEPS) * _PERCENT

        return aug_const.AUG_TIP_GUARD.format(percent=percent, kind=self.damage_type)


class GuardMelee(BaseGuard):
    """Cut melee damage. Every number is a placeholder."""

    key = "guard_melee"
    name = "Guard: Melee"
    description = "Thickens the skin under a blade. Cuts the melee damage you take."
    damage_type = combat_const.DAMAGE_TYPE_MELEE


class GuardProjectile(BaseGuard):
    """Cut projectile damage. Every number is a placeholder."""

    key = "guard_projectile"
    name = "Guard: Projectile"
    description = "Turns a shot aside at the last inch. Cuts the projectile damage you take."
    damage_type = combat_const.DAMAGE_TYPE_PROJECTILE


class GuardEnergy(BaseGuard):
    """Cut energy damage. Every number is a placeholder."""

    key = "guard_energy"
    name = "Guard: Energy"
    description = "Grounds a discharge through the frame. Cuts the energy damage you take."
    damage_type = combat_const.DAMAGE_TYPE_ENERGY
