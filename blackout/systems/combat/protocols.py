"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/20/2026
Description: The interfaces combat duck-types on, written down.

Why these exist
---------------
Combat calls methods on objects it never checks the type of. Two of those
contracts were held together by ``hasattr`` probes and a docstring:

``.skills`` — ``_NpcSkillsShim`` (typeclasses/npc_combat.py) stands in for a
real SkillHandler on NPCs, and its own docstring describes the failure mode
exactly:

    The shim must cover every method combat code calls on `.skills`, not just
    the ones NPCs meaningfully implement. Combat duck-types on this interface,
    so a missing method raises inside the tick loop, which the tick engine
    catches by discarding the handler — the NPC would silently stop fighting
    with no error surfaced to the player.

That is a contract with no way to check it. Adding a method to SkillHandler and
forgetting the shim produced an NPC that stopped fighting mid-action, and the
only trace was a swallowed traceback.

``is_alive`` — probed with ``hasattr`` at nine sites, all of them meaning "is
this thing a combatant?". One name standing in for a type.

What a Protocol buys, and what it does not
------------------------------------------
``runtime_checkable`` makes ``isinstance`` check that the METHODS EXIST. It
does not check signatures, so this is not stronger than the hasattr probes it
replaces at any single call site.

The value is elsewhere: the contract is now stated in one place, and
tests/test_protocols.py asserts that every implementation satisfies it. A
missing method becomes a failing test at the moment it is forgotten, rather
than an NPC that quietly stops fighting weeks later.
"""

from typing import Protocol, runtime_checkable

# ─── The contracts ──────────────────────────────────────────────────────────


@runtime_checkable
class SkillSource(Protocol):
    """What combat and equipment require of an entity's ``.skills``.

    Implemented by systems/progression/skills/handler.SkillHandler for
    characters and by typeclasses/npc_combat._NpcSkillsShim for NPCs. Adding a
    method here without adding it to both is what test_protocols.py catches.
    """

    def get_level(self, skill_key: str) -> int:
        """Return the entity's current level in a skill."""
        ...

    def add_xp(self, skill_key: str, amount: int) -> None:
        """Grant experience. May be a no-op for entities that do not level."""
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
