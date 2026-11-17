"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The combat modifiers of the lit augments (DESIGN-0015, Phase
             2). One rules instance for each lit augment joins the
             contributors of its holder at the action, as the Exterminator
             buffs do. It adds the augment bonus of the augment to its
             channel, and `effective_level` reads it with no edit.

             The collector reads the handler AT THE ACTION. Thus, the swing
             reads the lit set at its own tick, the rule of flicking in
             combat/constants.py.

             Phase 5 added the three reads of a modifier: the roll of a
             strength modifier (Overclock) joins the bonus of every other
             lit augment, `reach_bonus` gives the aura handler its tiles,
             and `regen_interval_share` gives the regen sweep its share.
             On 11/14/2026, `tile_bonus` gave the walk the tiles of Nitro.
"""

from fractions import Fraction

from systems.gameplay.combat import constants as combat_const
from systems.gameplay.combat.rules.rule_defs.base_rules import BaseActionRules

from . import constants as aug_const
from . import pool
from .handler import BlackoutAugmentHandler, get_augment_handler_for, lit_augments_of


# The key prefix of an augment rules instance. The key names the augment,
# so `@combatrules` and merge_contributors tell two augments apart.
_RULES_KEY_PREFIX: str = "augment:"


class AugmentModifierRules(BaseActionRules):
    """
    Purpose: Add the bonus of one lit augment to its channel.

    Entry:
        augment is an instance of AUGMENT_REGISTRY.
        bonus is the float that augment.bonus_for gave for the holder.

    Exit/Returns:
        Not applicable. A rules definition.

    Module Globals:
        _RULES_KEY_PREFIX read.

    Methodology:
        Overrides contribute_modifiers only, so it composes with every
        gear rule: a modifier never loses a priority contest. The action
        computes the bonus from the level and the power level at that tick.
        The instance keeps the bonus. The channel comes from the augment at
        contribution time, because the accuracy and the damage channels
        follow the style of the action.

    Notes/References:
        An instance is built for each action, never registered. The rules
        registry walks rule_defs/ for the gear, and an augment is not gear.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """

    name = "Augment"
    description = "The bonus of a lit augment."
    priority = combat_const.RULES_PRIORITY_MODIFIER

    def __init__(self, augment, bonus: float) -> None:
        self.augment = augment
        self.bonus = bonus
        self.key = f"{_RULES_KEY_PREFIX}{augment.key}"
        self.name = augment.name
        self.description = augment.description

    def contribute_modifiers(self, context, bag) -> None:
        """Add the bonus of the augment into the bag of its holder. The
        augment picks its channel and its side."""
        self.augment.contribute(context, bag, self.bonus)


def active_rules(entity) -> tuple:
    """
    Purpose: The rules instances of every augment lit on an entity.

    Entry:
        entity is any object. It may have no handler.

    Exit/Returns:
        Returns a tuple of AugmentModifierRules, in the order of the rail.
        Empty when nothing burns.

    Module Globals:
        None.

    Methodology:
        1. Read the lit set from the handler.
        2. Read the Augmentation level one time.
        3. Sum the rolls of the lit strength modifiers, at their power levels.
        4. Build one instance for each pair that reaches an action, with
           the bonus of its power level plus the rolls. A modifier builds none.

    Notes/References:
        _build_context in combat.py merges these for both sides of an
        action, beside the Exterminator buffs.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    lit = lit_augments_of(entity)

    if not lit:
        return ()

    held_level = pool.level(entity)
    extra = strength_roll(entity)
    rules = []

    for augment, power_level in lit:
        if augment.family == aug_const.FAMILY_MODIFIER:
            continue

        share = augment.power_level_share(power_level)
        bonus = augment.bonus_for(held_level, power_level) + extra * share
        rules.append(AugmentModifierRules(augment, bonus))

    return tuple(rules)


def strength_roll(entity) -> float:
    """
    Purpose: The roll that the lit strength modifiers add to every lit
             stat augment of an entity.

    Entry:
        entity is any object. It may have no handler.

    Exit/Returns:
        Returns a float, 0.0 when no strength modifier burns. Each roll
        is scaled by the power level of its modifier.

    Module Globals:
        aug_const.MODIFIES_STRENGTH read.

    Methodology:
        One walk of the lit set. The handler holds the roll of each light.

    Notes/References:
        detail.py shows the roll on the row through handler.roll_of.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    handler = get_augment_handler_for(entity)

    if handler is None:
        return 0.0

    total = 0.0

    for augment, power_level in handler.lit_augments():
        if augment.modifies == aug_const.MODIFIES_STRENGTH:
            total += handler.roll_of(augment.key) * augment.power_level_share(power_level)

    return total


def reach_bonus(entity) -> int:
    """
    Purpose: The tiles that the lit reach modifiers add to the ring of the
             lit aura of an entity.

    Entry:
        entity is any object. It may have no handler.

    Exit/Returns:
        Returns an int of at least 0.

    Module Globals:
        aug_const.MODIFIES_REACH read.

    Methodology:
        Sum `tiles_for(power_level)` over the lit augments that modify the
        reach.

    Notes/References:
        BlackoutAuraHandler.radius_for reads it at each pulse, and the
        handler of this package asks the aura handler to rebuild its ring
        when the lit set moves.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    tiles = 0

    for augment, power_level in lit_augments_of(entity):
        if augment.modifies == aug_const.MODIFIES_REACH:
            tiles += augment.tiles_for(power_level)

    return tiles


def tile_bonus(entity) -> Fraction:
    """
    Purpose: The tiles that the lit speed modifiers of an entity add to
             each tick of its walk.

    Entry:
        entity is any object. It may have no handler.

    Exit/Returns:
        Returns a Fraction of at least 0. A part of a tile is the share of
        a power level below the top.

    Module Globals:
        aug_const.MODIFIES_SPEED read.

    Methodology:
        1. Read the handler through the cached accessor of the entity, not
           through a scan of its scripts. The walk asks on every tick for
           every walker, and a scan is one database query.
        2. Sum `tiles_for(power_level)` over the lit augments that modify
           the speed.

    Notes/References:
        walk.speed reads it. The handler paths clear the accessor (see
        tickable.ensure_handler and stop_handler), so the cache follows a
        light and a put-out.

    Author: Nick Hobar
    Creation date: 11/14/2026
    """
    handler = getattr(entity, BlackoutAugmentHandler.ACCESSOR_NAME, None)
    tiles = Fraction(0)

    if handler is None:
        return tiles

    for augment, power_level in handler.lit_augments():
        if augment.modifies == aug_const.MODIFIES_SPEED:
            tiles += augment.tiles_for(power_level)

    return tiles


def regen_interval_share(entity) -> float:
    """
    Purpose: The share of the HP regen interval that an entity keeps, with
             its lit regen modifiers.

    Entry:
        entity is any object. It may have no handler.

    Exit/Returns:
        Returns a float in [AUG_REGEN_SHARE_FLOOR, 1.0]. 1.0 means the
        interval of today. 0.5 means twice the regen.

    Module Globals:
        aug_const.MODIFIES_REGEN, AUG_REGEN_SHARE_FLOOR read.

    Methodology:
        1 minus the sum of the bonuses of the lit regen modifiers, at the
        level and the power level of each, floored.

    Notes/References:
        combat/hp_regen.py reads it at each sweep.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    lit = lit_augments_of(entity)

    if not lit:
        return 1.0

    held_level = pool.level(entity)
    cut = 0.0

    for augment, power_level in lit:
        if augment.modifies == aug_const.MODIFIES_REGEN:
            cut += augment.bonus_for(held_level, power_level)

    share = 1.0 - cut

    return max(aug_const.AUG_REGEN_SHARE_FLOOR, min(1.0, share))
