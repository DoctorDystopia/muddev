"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/20/2026
Description: The interfaces combat duck-types on, written down.

Why these exist
---------------
Combat calls methods on objects it never checks the type of. Two of those
contracts were held together by ``hasattr`` probes and a docstring:

``.skills`` — two implementations, because a monster and a player do not
store the same thing. ``SkillHandler`` (characters) derives a level from
accumulated XP; ``StatBlockSkills`` (NPCs) stores the level itself and has no
XP at all. Combat reads levels off both without checking which it holds.

Before the split below there was one protocol and a read-only NPC facade whose
own docstring described the failure mode exactly:

    The shim must cover every method combat code calls on `.skills`, not just
    the ones NPCs meaningfully implement. Combat duck-types on this interface,
    so a missing method raises inside the tick loop, which the tick engine
    catches by discarding the handler -- the NPC would silently stop fighting
    with no error surfaced to the player.

That is a contract with no way to check it. Adding a method to SkillHandler and
forgetting the shim produced an NPC that stopped fighting mid-action, and the
only trace was a swallowed traceback.

``is_alive`` — probed with ``hasattr`` at nine sites, all of them meaning "is
this thing a combatant?". One name standing in for a type.

What a Protocol buys, and what it does not
------------------------------------------
``runtime_checkable`` makes ``isinstance`` check that the METHODS EXIST. It
does not check signatures, so at any single call site this is not stronger
than the hasattr probes it replaces.

The value is elsewhere: the contract is stated in one place, and
tests/test_protocols.py asserts that every implementation satisfies it. A
missing method becomes a failing test at the moment it is forgotten, rather
than an NPC that quietly stops fighting weeks later.

That test compares ``inspect.signature`` against each protocol member, not
just the method NAMES. Name-set comparison passed an implementation whose
``get_level`` took different parameters from the one combat calls, which is
the same silent breakage one step further in.
"""

from typing import Protocol, runtime_checkable

# ─── The contracts ──────────────────────────────────────────────────────────


@runtime_checkable
class SkillSource(Protocol):
    """What combat and equipment require of an entity's ``.skills``.

    Reading and writing LEVELS, which every combatant has. Implemented by
    systems/progression/skills/handler.SkillHandler for characters and by
    systems/progression/skills/stat_block.StatBlockSkills for NPCs. Adding a
    method here without adding it to both is what test_protocols.py catches.

    Deliberately says nothing about XP -- see XpEarner below.
    """

    def get_level(self, skill_key: str) -> int:
        """Return the entity's current level in a skill."""
        ...

    def set_level(self, skill_key: str, level: int) -> int:
        """Set a skill's level directly, clamped to the legal range.

        Returns the level actually stored. This is the write path a stat
        drain or a builder command needs; it is NOT how a character earns a
        level, which is add_xp's job.
        """
        ...

    def modify_level(self, skill_key: str, delta: int) -> int:
        """Shift a skill's level by `delta`, clamped. Returns the new level."""
        ...


@runtime_checkable
class XpEarner(Protocol):
    """What the progression system requires of an entity that can EARN.

    Implemented by SkillHandler only. An NPC has no XP -- not "zero XP", none:
    there is no curve behind its levels, and awarding it experience is
    meaningless rather than merely wasteful.

    Splitting this out of SkillSource is what lets a caller ask the question it
    actually means. `getattr(killer, "skills", None) is not None` was standing
    in for "is this an XP earner?" at the killer-XP gate in
    CombatEntity.at_death and in the combat handler's per-hit XP planner, and
    it answered TRUE for every NPC -- harmless only for as long as the NPC-side
    add_xp stayed a no-op. `isinstance(x, XpEarner)` asks it directly, so the
    NPC implementation is free to simply not have the method.
    """

    def add_xp(self, skill_key: str, amount: int) -> None:
        """Grant experience, levelling the skill if the curve is cleared."""
        ...

    def get_total_xp(self, skill_key: str) -> int:
        """Return lifetime experience in a skill."""
        ...

    def meets_prerequisite(self, skill_key: str, required_level: int) -> bool:
        """Report whether the entity clears a level requirement."""
        ...


@runtime_checkable
class Combatant(Protocol):
    """What combat requires of anything it can perform actions on or that can perform actions.

    Implemented by the CombatEntity mixin, so both Character and HostileNPC
    satisfy it. Replaces ``hasattr(target, "is_alive")``, which was one method
    name standing in for a type at nine call sites.
    """

    def is_alive(self) -> bool:
        """Report whether this entity can still act and be acted on."""
        ...

    def at_damage(self, amount: int, **kwargs) -> int:
        """Apply damage and return the amount actually taken."""
        ...
