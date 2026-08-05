"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Named modifier channels — the additive side of pluggable combat
             math. Pure: no Evennia imports, no DB.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from systems.combat import combat_calc
from systems.combat import constants as const


# ─── Private constant definitions ────────────────────────────────────────────

# Neutral multiplier bonus. A contributor declares "+0.10" meaning +10%, so an
# empty channel must contribute exactly 0.0 and the stage multiplier resolves
# to the AUGMENTATION_DEFAULT_MULT / SET_DEFAULT_MULT baseline.
_NO_BONUS = 0.0

# Neutral flat contribution.
_NO_FLAT = 0


# ─── Public routines ─────────────────────────────────────────────────────────

@dataclass
class ChannelAccumulator:
    """
    Purpose: The four numbers every contributor can add into for one channel.

    Entry:
        flat_pre      - added BEFORE the multiplier stages.
        augment_bonus - summed into multiplier stage 1.
        set_bonus     - summed into multiplier stage 2.
        flat_post     - added AFTER both stages, unscaled by either.

    Exit/Returns:
        Not applicable — a data carrier.

    Module Globals:
        _NO_BONUS, _NO_FLAT read (defaults).

    Methodology:
        These four fields map ONE-TO-ONE onto combat_calc.effective_level's
        four parameters -- potion_boost, augmentation_mult, set_mult,
        stance_bonus. That mapping is the whole reason the shape is four fields
        and not, say, a list of callables: it is what finally wires up the three
        parameters that have been declared-and-dead on effective_level since
        07/26, without editing combat_calc at all.

        There are EXACTLY TWO multiplier stages, deliberately, not N applied in
        priority order. With N, floor(floor(floor(b*m1)*m2)*m3) depends on which
        item happened to be equipped first, so two amulets plus a set bonus give
        different totals for unrelated reasons -- an unfalsifiable balance bug.
        The two OSRS stages are also semantically distinct (Augmentation vs
        equipment Set), and naming them fixes where the load-bearing
        intermediate floor falls.

        WITHIN a stage, bonuses are ADDITIVE: two +10% sources give x1.20, not
        x1.21. Additive is order-independent, does not compound out of control,
        and is what a designer means when they write "+10%".

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """

    flat_pre: int = _NO_FLAT
    augment_bonus: float = _NO_BONUS
    set_bonus: float = _NO_BONUS
    flat_post: int = _NO_FLAT

    def augment_mult(self) -> float:
        """Resolve multiplier stage 1 from its accumulated bonus."""
        return const.AUGMENTATION_DEFAULT_MULT + self.augment_bonus

    def set_mult(self) -> float:
        """Resolve multiplier stage 2 from its accumulated bonus."""
        return const.SET_DEFAULT_MULT + self.set_bonus


class ModifierBag:
    """
    Purpose: Per-entity collection of ChannelAccumulators, one per channel.

    Entry:
        No conditions.

    Exit/Returns:
        Not applicable — a container.

    Module Globals:
        const.ACTION_MODIFIER_CHANNELS read.

    Methodology:
        Channels are created lazily on first write and every read returns an
        accumulator, so a caller never has to test for absence. Every add_*
        method VALIDATES the channel key against ACTION_MODIFIER_CHANNELS and
        raises: a typo'd channel would otherwise accumulate happily into a
        number nothing ever reads, which is the exact failure mode that hid
        every anvil recipe behind "Metalsmith" vs "Metalsmithing".

        Contributors are applied in priority order by the pipeline, so the
        summation order here is already deterministic run to run -- float
        addition is not associative and an unordered sum would make an
        end-to-end damage assertion flaky.

    Notes/References:
        See ChannelAccumulator for why a channel has four fields.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """

    def __init__(self) -> None:
        self._channels: dict = {}
        self._written: set = set()

    def channel(self, channel_key: str) -> ChannelAccumulator:
        """Return the accumulator for a channel, creating it if absent.

        Reading a channel does NOT mark it written, every seam reads its
        channels on every action, so counting reads would make
        touched_channels report all nine and tell nobody anything.
        """
        self._validate(channel_key)
        existing = self._channels.get(channel_key)

        if existing is None:
            existing = ChannelAccumulator()
            self._channels[channel_key] = existing

        return existing

    def add_flat_pre(self, channel_key: str, amount: int) -> None:
        """Add a flat amount applied BEFORE both multiplier stages."""
        accumulator = self._writable(channel_key)
        accumulator.flat_pre += amount

    def add_augment_bonus(self, channel_key: str, bonus: float) -> None:
        """Add a fractional bonus into multiplier stage 1 (+0.10 is +10%)."""
        accumulator = self._writable(channel_key)
        accumulator.augment_bonus += bonus

    def add_set_bonus(self, channel_key: str, bonus: float) -> None:
        """Add a fractional bonus into multiplier stage 2 (+0.10 is +10%)."""
        accumulator = self._writable(channel_key)
        accumulator.set_bonus += bonus

    def add_flat_post(self, channel_key: str, amount: int) -> None:
        """Add a flat amount applied AFTER both stages, scaled by neither."""
        accumulator = self._writable(channel_key)
        accumulator.flat_post += amount

    def touched_channels(self) -> tuple:
        """Return the channels a contributor has WRITTEN to, for diagnostics.

        Ordered by ACTION_MODIFIER_CHANNELS rather than by insertion, so the
        introspection command renders the same list every time.
        """
        return tuple(
            channel_key
            for channel_key in const.ACTION_MODIFIER_CHANNELS
            if channel_key in self._written
        )

    def _writable(self, channel_key: str) -> ChannelAccumulator:
        """Return a channel's accumulator and record that it was written to."""
        accumulator = self.channel(channel_key)
        self._written.add(channel_key)

        return accumulator

    def _validate(self, channel_key: str) -> None:
        """Reject a channel key that is not a declared constant."""
        if channel_key in const.ACTION_MODIFIER_CHANNELS:
            return

        raise ValueError(
            f"{channel_key!r} is not an action modifier channel. Declared "
            f"channels are {const.ACTION_MODIFIER_CHANNELS}. Add it to "
            f"systems/combat/constants.py if it is new."
        )


def apply_to_level(bag: ModifierBag, channel_key: str, base_level: int,
                   stance_bonus: int) -> int:
    """
    Purpose: Run one skill level through the full OSRS effective-level pipeline
    with a channel's modifiers folded into it.

    Entry:
        bag          - the accumulator collection to read from.
        channel_key  - one of CHANNEL_STRIKE_LEVEL / _BRAWN_LEVEL /
                       _DEFENSE_LEVEL.
        base_level   - the entity's unbuffed skill level (0..127).
        stance_bonus - the active style's invisible level boost for this axis.

    Exit/Returns:
        Integer effective level, floored exactly as OSRS floors.

    Module Globals:
        None.

    Methodology:
        Delegates to combat_calc.effective_level rather than reimplementing it.
        combat_calc is the OSRS oracle and stays untouched: the four
        accumulator fields become its four parameters, so an empty bag makes
        this function the identity on effective_level(base, stance_bonus=...).
        That identity is asserted by test_modifiers, and is what lets the whole
        default action path be proved equivalent to the old one.

        flat_post is folded into stance_bonus because both are post-multiplier
        flat integers; effective_level has exactly one such slot and there is
        no behavioural difference between them.

    Notes/References:
        L_eff = floor( floor( (base + potion) * augmentation ) * set )
                + stance + 8

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    accumulator = bag.channel(channel_key)
    augment_mult = accumulator.augment_mult()
    set_mult = accumulator.set_mult()
    post_bonus = stance_bonus + accumulator.flat_post

    return combat_calc.effective_level(
        base_level,
        potion_boost=accumulator.flat_pre,
        augmentation_mult=augment_mult,
        set_mult=set_mult,
        stance_bonus=post_bonus,
    )


def apply_to_int(bag: ModifierBag, channel_key: str, base_value: int) -> int:
    """
    Purpose: Apply a channel's modifiers to a plain integer combat number —
    an equipment bonus, a max hit, or a damage roll.

    Entry:
        bag         - the accumulator collection to read from.
        channel_key - any declared channel.
        base_value  - the unmodified integer.

    Exit/Returns:
        Integer result. NOT floored at zero: a defense bonus is legitimately
        negative, so the caller decides whether its channel has a floor.

    Module Globals:
        None.

    Methodology:
        floor( (base + flat_pre) * (1 + augment) * (1 + set) ) + flat_post

        Same shape as apply_to_level with one floor instead of two, so there
        is one rule to remember and no per-channel exception to look up. Flat
        before mult gives a designer both "a percentage of the pre-buffed
        number" and "a flat that percentages cannot scale".

    Notes/References:
        The single floor is deliberate. Only the level pipeline nests floors,
        because only there does OSRS's engine floor between the two stages.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    accumulator = bag.channel(channel_key)
    scaled = (base_value + accumulator.flat_pre)
    scaled = scaled * accumulator.augment_mult() * accumulator.set_mult()

    return math.floor(scaled) + accumulator.flat_post


def apply_to_scalar(bag: ModifierBag, channel_key: str,
                    base_value: float) -> float:
    """
    Purpose: Apply a channel's modifiers to a float combat number — today only
    the hit chance.

    Entry:
        bag         - the accumulator collection to read from.
        channel_key - any declared channel.
        base_value  - the unmodified float.

    Exit/Returns:
        Float result, unclamped. The caller clamps, because the sane bounds
        differ per channel.

    Module Globals:
        None.

    Methodology:
        Identical to apply_to_int without the floor.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    accumulator = bag.channel(channel_key)
    scaled = (base_value + accumulator.flat_pre)
    scaled = scaled * accumulator.augment_mult() * accumulator.set_mult()

    return scaled + accumulator.flat_post


def clamp_damage(value: int) -> int:
    """
    Purpose: Hold a damage or max-hit number at or above the damage floor.

    Entry:
        value - a post-modifier integer that may have gone negative.

    Exit/Returns:
        max(ACTION_DAMAGE_FLOOR, value).

    Module Globals:
        const.ACTION_DAMAGE_FLOOR read.

    Methodology:
        A modifier that drives damage negative must land on zero, never heal
        the target -- at_damage clamps a negative to 0 anyway, but doing it
        here keeps the ActionResult honest for the message layer, which reads
        `damage` directly.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    return max(const.ACTION_DAMAGE_FLOOR, value)


def clamp_hit_chance(value: float) -> float:
    """
    Purpose: Re-impose OSRS's accuracy bounds after modifiers have run.

    Entry:
        value - a post-modifier probability that may be out of band.

    Exit/Returns:
        Float clamped to [HIT_CHANCE_FLOOR, HIT_CHANCE_CEILING].

    Module Globals:
        const.HIT_CHANCE_FLOOR read.
        const.HIT_CHANCE_CEILING read.

    Methodology:
        The bare OSRS curve is provably bounded -- an attacker never reaches
        1.0 and a defender never reaches 0.0 -- and combat_calc's tests assert
        that. A multiplier channel can drive the number anywhere, so the bounds
        have to be re-imposed once modifiers have had their say.

        The ceiling sits below 1.0 on purpose. "This weapon cannot miss" is a
        statement about the accuracy ROLL and belongs in the roll_accuracy
        seam, not in a multiplier that happens to saturate.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    floored = max(const.HIT_CHANCE_FLOOR, value)

    return min(const.HIT_CHANCE_CEILING, floored)
