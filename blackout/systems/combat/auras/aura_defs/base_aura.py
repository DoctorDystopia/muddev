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

from systems.combat import constants as const


# Public constant definitions

# Placeholder key on this base class. registry.py refuses to register any
# subclass still carrying it, so a definition that forgets to set `key` is
# reported loudly instead of shadowing a real aura.
BASE_AURA_KEY = "base"

# An aura with this unlock level imposes no skill requirement.
NO_UNLOCK_REQUIREMENT = 0



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
    # COMBAT_TICK_SECONDS (0.6s); this is the multiplier on top of that.
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
