"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/03/2026
Description: Base aura class defining the standard interface for every toggled
             damage aura.

An aura is DATA plus three small hooks. Subclasses set the numbers as class
attributes and normally override nothing: the handler in auras/aura_handler.py
reads radius/cadence off the class and calls damage_for / xp_for / can_activate.
That keeps "adding an aura" to "adding one file", per the repo convention.
"""

import math

from systems.gameplay.combat import constants as const


# Public constant definitions

# Placeholder key on this base class. registry.py refuses to register any
# subclass still carrying it, so a definition that forgets to set `key` is
# reported loudly instead of shadowing a real aura.
BASE_AURA_KEY = "base"

# An aura with this unlock level imposes no skill requirement.
NO_UNLOCK_REQUIREMENT = 0

# A self-burn share that burns nothing.
NO_SELF_BURN = 0.0


# Private constant definitions

# The decimal places that self_burn_for keeps before it rounds up. Far
# below one HP, and far above the noise of a float product: 0.07 * 100 is
# 7.000000000000001, and its ceiling is 8.
_BURN_ROUNDING_DIGITS = 9



class BaseAura:
    """
    Purpose: Defines the standard interface and default behaviours for a toggled
    damage aura.
    """

    key = BASE_AURA_KEY
    name = "Base Aura"
    description = "Base aura description."

    # Radius in grid tiles. 0 confines the aura to the caster's own room.
    radius = 0

    # Ticks between damage pulses. The tick engine calls the handler every
    # TICK_SECONDS (0.6s); this is the multiplier on top of that.
    tick_interval = const.AURA_DEFAULT_TICK_INTERVAL

    # Share of the caster's scaling-skill level dealt per pulse, as a fraction.
    damage_pct = 0.0

    # The skill whose level sets this aura's damage, and the skill that earns
    # experience from it. Two separate names because they need not be the same
    # skill for a future aura, even though Righteous Fire uses one for both.
    scaling_skill = None
    xp_skill = None

    # Level of `scaling_skill` required before the aura can be switched on.
    unlock_level = NO_UNLOCK_REQUIREMENT

    # What KIND of damage a pulse deals, threaded into at_damage so death
    # attribution can tell a burn from a sword. Lives on the aura class rather
    # than being hard-coded in the handler so a future toxin aura stays a
    # one-file change.
    damage_type = const.DAMAGE_TYPE_BURN

    # Share of the max HP of the caster that each pulse burns from the
    # caster, as a fraction. The burn lands on every pulse, with or without a target,
    # and it can kill the caster (Nick, 10/20/2026). The `cost` property
    # turns this number into the tip sentence.
    self_burn_pct = NO_SELF_BURN


    @property
    def cost(self) -> str:
        """
        Purpose: Say what the aura costs the caster, as one sentence for the
        ability rail and the tip.

        Entry:
            No conditions.

        Exit/Returns:
            Returns the sentence, or an empty string when the aura costs
            nothing.

        Module Globals:
            const.AURA_SELF_BURN_COST_TEMPLATE, NO_SELF_BURN read.

        Methodology:
            The sentence comes from self_burn_pct, the number that the burn
            reads. Thus, a retune of the burn changes the tip with it.

        Notes/References:
            An aura with a cost of another kind sets its own sentence as a
            class attribute. That attribute hides this property.

        Author: Nick Hobar
        Creation date: 10/20/2026
        """
        if self.self_burn_pct <= NO_SELF_BURN:
            return ""

        percent = self.self_burn_pct * 100
        sentence = const.AURA_SELF_BURN_COST_TEMPLATE.format(percent=percent)

        return sentence


    def self_burn_for(self, caster: object, carry: float) -> tuple:
        """
        Purpose: Compute the burn of one pulse on the caster.

        Entry:
            caster - an entity exposing max_hp.
            carry  - what earlier pulses burned over their share, as zero or a
                     negative fraction. 0.0 on the first pulse.

        Exit/Returns:
            Returns (burn: int, carry: float). The caller keeps the carry and
            passes it in on the next pulse. The burn is 0 when self_burn_pct
            is 0.

        Module Globals:
            _BURN_ROUNDING_DIGITS read.

        Methodology:
            The burn rounds UP, and the carry gives the extra back on a later
            pulse. Thus, the mean burn is exactly self_burn_pct of max HP at
            every level. A share of 0.5 HP burns 1 HP on every second pulse.

            Up, not down, because the aura pulses at once when it is lit. A
            burn that rounded down would let a player relight the aura before
            each pulse and never pay.

        Notes/References:
            Reads max_hp, not the scaling skill. Max HP is Fortitude today, but
            a later item that changes max HP changes the burn with it.

        Author: Nick Hobar
        Creation date: 10/20/2026
        """
        max_hp = getattr(caster, "max_hp", 0) or 0
        owed = round(carry + max_hp * self.self_burn_pct, _BURN_ROUNDING_DIGITS)
        burn = max(0, math.ceil(owed))

        return burn, owed - burn


    def damage_for(self, caster: object) -> int:
        """
        Purpose: Compute one pulse's damage for a given caster.

        Entry:
            caster - an entity exposing a `skills` handler.

        Exit/Returns:
            Returns the integer damage for a single pulse, never below
            const.AURA_MIN_DAMAGE.

        Module Globals:
            const.AURA_MIN_DAMAGE read.

        Methodology:
            Damage scales off the CASTER's skill level, not the target's health,
            so one number describes the aura against every enemy and the effect
            grows with the character rather than with what it is pointed at.

            The AURA_MIN_DAMAGE floor is load-bearing: a character spawns at
            Fortitude 10, so any share below 10% truncates to zero and the aura
            would appear broken at exactly the levels a new player has.

        Notes/References:
            Returns the floor when the caster has no skills handler (e.g. an
            NPC-run aura), rather than raising inside the tick loop.

        Author: Nick Hobar
        Creation date: 08/03/2026
        """
        skills = getattr(caster, "skills", None)

        if skills is None or self.scaling_skill is None:
            return const.AURA_MIN_DAMAGE

        skill_level = skills.get_level(self.scaling_skill)
        raw_damage = int(skill_level * self.damage_pct)

        return max(const.AURA_MIN_DAMAGE, raw_damage)


    def xp_for(self, damage: int) -> int:
        """
        Purpose: Compute the experience one pulse's damage earns.

        Entry:
            damage - HP actually removed from a target by this pulse.

        Exit/Returns:
            Returns integer experience to award to `xp_skill`. Zero when the
            aura names no XP skill or nothing was dealt.

        Module Globals:
            const.XP_PER_DAMAGE_BY_SKILL, const.XP_PER_DAMAGE_FORTITUDE read.

        Methodology:
            Reuses the SAME per-damage rate table the melee swing path uses, so
            aura damage and weapon damage cannot drift apart on what a point of
            damage is worth. Fortitude's 1.33/damage rate is already the
            documented cross-style rate in constants.py, and an aura earning it
            keeps the aura from becoming a cheaper route to the same levels.

        Notes/References:
            Rounds rather than truncates, matching _plan_style_xp in combat.py.
            Awards nothing for a zero-damage pulse so an overkill pulse against
            a 1-HP target cannot pay out for damage that never landed.

        Author: Nick Hobar
        Creation date: 08/03/2026
        """
        if self.xp_skill is None or damage <= 0:
            return 0

        rate = const.XP_PER_DAMAGE_BY_SKILL.get(
            self.xp_skill, const.XP_PER_DAMAGE_FORTITUDE
        )
        award = int(round(rate * damage))

        return max(0, award)


    def can_activate(self, character: object) -> tuple:
        """
        Purpose: Report whether a character may switch this aura on.

        Entry:
            character - the entity attempting to activate the aura.

        Exit/Returns:
            Returns (allowed: bool, reason: str). `reason` is empty when
            allowed, and is a player-facing sentence when not.

        Module Globals:
            NO_UNLOCK_REQUIREMENT read.

        Methodology:
            Returns the refusal text alongside the verdict so the command layer
            does not have to reconstruct WHY the check failed -- the same shape
            the gathering skills use to report a missing tool or level.

        Notes/References:
            Subclasses that need extra conditions (an item, a location) should
            call super() first and add to it.

        Author: Nick Hobar
        Creation date: 08/03/2026
        """
        if self.unlock_level <= NO_UNLOCK_REQUIREMENT:
            return True, ""

        skills = getattr(character, "skills", None)
        if skills is None:
            return False, f"You cannot channel {self.name}."

        if not skills.meets_prerequisite(self.scaling_skill, self.unlock_level):
            return (
                False,
                f"{self.name} requires {self.scaling_skill.title()} "
                f"level {self.unlock_level}.",
            )

        return True, ""
