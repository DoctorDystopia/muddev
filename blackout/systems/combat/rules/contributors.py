"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Collect the action rules an entity's gear contributes, in a
             deterministic priority order.
"""

from __future__ import annotations

from evennia.utils import logger

from items.equipment.constants import SLOT_DISPLAY_ORDER
from systems.combat import constants as const

from .registry import RULES_REGISTRY


# Private constant definitions

# Sort position for a contributor whose rules class declares no priority.
# Treated as the default tier so a malformed definition loses every seam
# contest rather than silently winning one.
_UNRANKED_PRIORITY = const.RULES_PRIORITY_DEFAULT


# Private helper routines

def _rules_keys(source) -> list:
    """Read the combat_rules key list off an object, tolerating its absence.

    Items spawned before combat_rules existed carry no such attribute, and
    nothing about that is an error -- they simply contribute nothing.
    """
    stored = getattr(source.db, const.COMBAT_RULES_ATTR, None)

    if not stored:
        return []

    if isinstance(stored, str):
        return [stored]

    return list(stored)


def _resolve_keys(source, slot_index: int) -> list:
    """Turn one object's combat_rules keys into (sort_key, rules) pairs."""
    resolved = []

    for key_index, rules_key in enumerate(_rules_keys(source)):
        rules = RULES_REGISTRY.get(rules_key)

        if rules is None:
            logger.log_err(
                f"[RULES] {source} declares unknown combat_rules key "
                f"{rules_key!r}; skipped. Known keys: {sorted(RULES_REGISTRY)}"
            )
            continue

        priority = getattr(rules, "priority", _UNRANKED_PRIORITY)
        resolved.append(((priority, slot_index, key_index, rules.key), rules))

    return resolved


def _rules_sources(entity) -> list:
    """Return the objects that may carry combat_rules for this entity.

    A Character's rules come from every equipped item, walked in
    SLOT_DISPLAY_ORDER rather than through EquipmentHandler.all(): the handler
    returns dict-ordered values, and an unstable order would make two
    equal-priority contributors take turns winning a seam.

    A HostileNPC has no equipment handler and carries its stat block on
    itself, so it contributes itself.
    """
    equipment = getattr(entity, "equipment", None)

    if equipment is None:
        return [entity]

    slots = equipment.slots
    sources = []

    for slot in SLOT_DISPLAY_ORDER:
        occupant = slots.get(slot)

        if occupant is not None:
            sources.append(occupant)

    return sources


# Public routines

def collect_contributors(entity) -> tuple:
    """
    Purpose: Gather every action rules definition an entity's gear contributes.

    Entry:
        entity - a CombatEntity. May be a Character with an equipment handler
                 or a HostileNPC without one; both are supported.

    Exit/Returns:
        Tuple of rules instances, sorted lowest priority first. The pipeline
        walks it in order, so a later entry wins any seam an earlier one also
        claims.

    Module Globals:
        RULES_REGISTRY read.
        _UNRANKED_PRIORITY read.

    Methodology:
        Walks the equipment slots in SLOT_DISPLAY_ORDER, reads each occupant's
        combat_rules key list, and resolves each key through the registry.
        An unknown key is logged and skipped rather than raised -- a stale key
        on one ring must not stop the wearer from acting.

        The sort key is (priority, slot index, key index, rules key). Priority
        is the only part with design meaning; the other three exist solely so
        two equal-priority contributors resolve the same way on every action.
        Without them, "which amulet wins" would depend on dict ordering and an
        end-to-end damage assertion would be flaky.

    Notes/References:
        This is an Attribute read per equipped item and runs on the 0.6s
        combat tick, so the result is cached on handler.ndb.active_rules and
        rebuilt only in _refresh_weapon -- equipment cannot change mid-fight
        by any other path.

        Deliberately reads ONLY combat_rules, not combat_stat_bonuses.
        Aggregating armour stats across slots changes every defence number in
        the game and belongs in its own change; when it lands it should be
        built as modifier contributors into CHANNEL_DEFENSE_BONUS rather than
        as a third mechanism.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    if entity is None:
        return ()

    sources = _rules_sources(entity)
    ranked = []

    for slot_index, source in enumerate(sources):
        ranked.extend(_resolve_keys(source, slot_index))

    ranked.sort(key=lambda pair: pair[0])

    return tuple(rules for _sort_key, rules in ranked)
