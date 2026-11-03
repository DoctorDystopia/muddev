"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The base class of every augment (DESIGN-0015, section 4.4).

             An augment is one effect that a player lights and puts out,
             and that drains Grit while it burns. The class is data plus a
             few routines: the channel it boosts, the bonus at a level and
             a step, the unlock check, the tip, and the contribution to an
             action. The handler reads the drain, and the rules module
             reads the bonus. The aura twin is auras/aura_defs/base_aura.py.

             Phase 5 added the sockets that an augment fits, the conflict
             group, the `modifies` field of a modifier, and `contribute`,
             which a guard overrides for the defender side.
"""

from systems.gameplay.augmentation import constants as aug_const


# Public constant definitions

# The placeholder key of the base class. The registry skips any class that
# still carries it.
BASE_AUGMENT_KEY: str = "base"


class BaseAugment:
    """
    Purpose: The interface and the defaults of one augment.

    Entry:
        A subclass sets `key`, `name`, `description`, `family`, `drain`,
        `pct_per_level`, `unlock_level`, and `sockets`. The family picks
        the channel through `channel_for`. A modifier sets `modifies`.

    Exit/Returns:
        Not applicable. An interface plus its defaults.

    Module Globals:
        None.

    Methodology:
        The level sets the strength: `pct_per_level x level` is the whole
        bonus, as `BaseAura.damage_for` reads the level for an aura. The
        step dial scales the bonus and the drain by the same share, so step
        1 of 3 gives a third of each. One augment for each axis, and no two
        rows are one effect at two strengths.

    Notes/References:
        The sustain event, the free window, the anneal, and the flick are
        on hold (Nick, 10/30/2026). A later phase adds `sustain_event` and
        `sustain_ticks` here.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """

    key = BASE_AUGMENT_KEY
    name = "Base Augment"
    description = "An augment with no effect."

    # True on a class that holds the shape of several augments and is no
    # augment itself. The registry skips it without a log line.
    abstract = True

    # One of the FAMILY_* constants. It names the channel of the action
    # that the augment boosts, or what else it does.
    family = ""

    # The drain of each tick at the top step, in counter units. The OSRS
    # drain effects run from 1 to 24 at a resistance of 60.
    drain = 0.0

    # The share of the level that the augment adds to its channel at the
    # top step. 0.002 x level 50 gives +10%.
    pct_per_level = 0.0

    # The Augmentation level that unlocks the augment. NO_UNLOCK_LEVEL
    # gates nothing.
    unlock_level = aug_const.NO_UNLOCK_LEVEL

    # The sockets of the rig that this augment fits (Nick, 10/30/2026: each
    # augment names its sockets). Keys of aug_const.SOCKETS. An augment
    # with no socket cannot be socketed, and so it never reaches the rail.
    sockets = ()

    # Two augments of one conflict group cannot burn at once. "" is no
    # group.
    conflict_group = ""

    # What a modifier changes, one of the MODIFIES_* constants. "" for an
    # augment that boosts its own channel and changes nothing else.
    modifies = ""

    # True for an augment that rolls a strength at each light (Overclock).
    # The handler keeps the roll, and the row shows it.
    rolls = False

    def step_share(self, step: int) -> float:
        """
        Purpose: The share of the strength and of the drain at one step.

        Entry:
            step is an int in [AUG_STEP_MIN, AUG_STEPS].

        Exit/Returns:
            Returns a float in (0, 1]. Step AUG_STEPS gives 1.0.

        Module Globals:
            aug_const.AUG_STEPS read.

        Methodology:
            One division. The bonus and the drain both read it, so the two
            cannot scale differently.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        return step / aug_const.AUG_STEPS

    def bonus_for(self, level: int, step: int) -> float:
        """
        Purpose: The augment bonus that the augment adds to its channel.

        Entry:
            level is the Augmentation level of the holder.
            step is an int in [AUG_STEP_MIN, AUG_STEPS].

        Exit/Returns:
            Returns a float. +0.10 means +10% on the channel, the form that
            ChannelAccumulator.augment_bonus takes.

        Module Globals:
            None.

        Methodology:
            pct_per_level x level x the step share.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        share = self.step_share(step)

        return self.pct_per_level * level * share

    def drain_for(self, step: int) -> float:
        """
        Purpose: The drain of one tick at one step.

        Entry:
            step is an int in [AUG_STEP_MIN, AUG_STEPS].

        Exit/Returns:
            Returns a float in counter units.

        Module Globals:
            None.

        Methodology:
            drain x the step share.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        share = self.step_share(step)

        return self.drain * share

    def channel_for(self, context) -> str:
        """
        Purpose: The modifier channel of the action that this augment boosts.

        Entry:
            context is an ActionContext.

        Exit/Returns:
            Returns a channel key of ACTION_MODIFIER_CHANNELS, or "" for an
            augment that boosts no channel of the action.

        Module Globals:
            None.

        Methodology:
            A table from the family to the accessor of the context. The
            accuracy and the damage channels follow the style, so one
            augment serves a sword and a bow, as `accuracy_vs_type` does.
            The defense channel is one for every action. A regen, an aura,
            or a modifier augment has no channel here.

        Notes/References:
            The combat constants are imported inside the routine. The
            combat package reaches this package through the rules module at
            the action, and a module-scope import would close a ring.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        from systems.gameplay.combat import constants as combat_const

        if self.family == aug_const.FAMILY_ACCURACY:
            return context.accuracy_channel()

        if self.family == aug_const.FAMILY_DAMAGE:
            return context.damage_channel()

        if self.family == aug_const.FAMILY_DEFENSE:
            return combat_const.CHANNEL_DEFENSE_LEVEL

        return ""

    def contribute(self, context, bag, bonus: float) -> None:
        """
        Purpose: Add the bonus of this augment into the bag of its holder,
                 at one action.

        Entry:
            context is the ActionContext.
            bag is the ModifierBag of the holder: the attacker bag or the
            defender bag.
            bonus is the whole bonus at this action, with the roll of a
            modifier already in it.

        Exit/Returns:
            No conditions. An augment with no channel adds nothing.

        Module Globals:
            None.

        Methodology:
            One add into the channel of the family. A guard overrides this,
            because it reads the side and the damage type.

        Notes/References:
            AugmentModifierRules.contribute_modifiers calls this.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        channel = self.channel_for(context)

        if not channel:
            return

        bag.add_augment_bonus(channel, bonus)

    def tip_lines(self, level: int) -> list:
        """
        Purpose: The lines of the tip of this augment, from its own data.

        Entry:
            level is the Augmentation level of the holder.

        Exit/Returns:
            Returns a list of strings. The first is the description.

        Module Globals:
            aug_const.AUG_TIP_* read.

        Methodology:
            The description, the effect line, the drain, the steps, the
            sockets, the conflict group, and the unlock. A subclass with a
            different effect overrides `effect_line` alone.

        Notes/References:
            The server says what an augment IS. The client draws the tip.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        lines = [str(self.description), self.effect_line(level)]

        lines.append(aug_const.AUG_TIP_DRAIN.format(drain=self.drain))
        lines.append(aug_const.AUG_TIP_STEPS.format(steps=aug_const.AUG_STEPS))
        lines.append(aug_const.AUG_TIP_SOCKETS.format(fits=self.socket_labels()))

        if self.conflict_group:
            lines.append(aug_const.AUG_TIP_CONFLICT.format(group=self.conflict_group))

        if self.unlock_level > aug_const.NO_UNLOCK_LEVEL:
            lines.append(aug_const.AUG_TIP_UNLOCK.format(level=self.unlock_level))

        return lines

    def effect_line(self, level: int) -> str:
        """The one line that says what the augment does at a level."""
        percent = self.bonus_for(level, aug_const.AUG_STEPS) * 100
        axis = aug_const.AUG_TIP_AXIS.get(self.family, self.family)

        return aug_const.AUG_TIP_BOOST.format(percent=percent, axis=axis)

    def socket_labels(self) -> str:
        """The labels of the sockets that this augment fits, as one string."""
        labels = [aug_const.SOCKET_NAMES.get(key, key) for key in self.sockets]

        return aug_const.SOCKET_LIST_SEPARATOR.join(labels)

    def can_activate(self, character) -> tuple:
        """
        Purpose: Say whether a character may light this augment, and why not.

        Entry:
            character is any object. It may have no skills handler.

        Exit/Returns:
            Returns (True, "") when the light is allowed. Returns (False,
            reason) otherwise, with the reason as player-facing text.

        Module Globals:
            aug_const.NO_UNLOCK_LEVEL read.
            aug_const.AUG_LOCKED_MESSAGE read.

        Methodology:
            The level gate alone. The Grit check is the handler's, because
            the pool moves on the tick and the gate must not read it twice.
            The socket check is the command's, because the rail shows the
            socketed augments only.

        Notes/References:
            The shape of BaseAura.can_activate. The skills constants are
            imported inside the routine, as pool.py does.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        from systems.gameplay.progression.skills.constants import SKILL_KEY_AUGMENTATION

        if self.unlock_level <= aug_const.NO_UNLOCK_LEVEL:
            return True, ""

        skills = getattr(character, "skills", None)

        if skills is None:
            return False, aug_const.AUG_LOCKED_MESSAGE.format(
                name=self.name, level=self.unlock_level)

        allowed = skills.meets_prerequisite(SKILL_KEY_AUGMENTATION, self.unlock_level)

        if not allowed:
            return False, aug_const.AUG_LOCKED_MESSAGE.format(
                name=self.name, level=self.unlock_level)

        return True, ""
