"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: The seam conflict check of an Exterminator buff.

             A seam buff replaces one step of an action, for example the
             damage roll. An item can own the same step: the toy sword owns
             the damage roll. Against a creature of the task type, only one
             of the two can win. This module names each clash and its
             winner, so the pick card can warn the player (Nick, 10/06/2026:
             the offer shows such a buff, with the warning).

             A modifier never clashes. Every contributor's modifiers run,
             whatever the priority. Thus, contribute_modifiers is not in the
             compare. Without that rule, every modifier buff would warn
             against the Glass Cannon amulet. DESIGN-0012, Phase 3.
"""

from dataclasses import dataclass

from systems.gameplay.combat import constants as combat_const
from systems.gameplay.combat.rules.contributors import rules_of
from systems.gameplay.combat.rules.pipeline import MODIFIER_SEAM_NAME
from systems.gameplay.combat.rules.registry import OVERRIDDEN_SEAMS_ATTR



# What a rival is, in a SeamConflict.
RIVAL_ITEM: str = "item"
RIVAL_BUFF: str = "buff"

# The priority of a rules instance that declares none, as the collector reads it.
_UNRANKED_PRIORITY: int = combat_const.RULES_PRIORITY_DEFAULT



@dataclass(frozen=True)
class SeamConflict:
    """
    One clash between a buff and a rival on one seam. `rival_kind` is
    RIVAL_ITEM or RIVAL_BUFF. `rival_name` is the item key or the buff name.
    `rival_rules_key` is the rules key or the buff key. `buff_wins` is True
    when the buff owns the seam against a creature of the task type.
    """

    seam: str
    rival_kind: str
    rival_name: str
    rival_rules_key: str
    buff_wins: bool



# ─── Private helper routines ────────────────────────────────────────────────

def contested_seams(rules) -> frozenset:
    """The seams that a rules instance owns, without the modifier seam."""
    seams = getattr(rules, OVERRIDDEN_SEAMS_ATTR, frozenset())

    return frozenset(seams) - {MODIFIER_SEAM_NAME}


def _priority(rules) -> int:
    """The priority of a rules instance, as the collector reads it."""
    return getattr(rules, "priority", _UNRANKED_PRIORITY)


def _wins_over_gear(buff, rules) -> bool:
    """
    Say whether the buff wins a seam against a gear rules instance.

    merge_contributors puts a buff after the gear at equal priority, and the
    later entry wins. Thus, a tie goes to the buff.
    """
    return _priority(buff) >= _priority(rules)


def _wins_over_buff(buff, other) -> bool:
    """
    Say whether the buff wins a seam against another held buff.

    merge_contributors sorts the buffs by key, and the later entry wins.
    Thus, a tie of priority goes to the higher key.
    """
    if _priority(buff) != _priority(other):
        return _priority(buff) > _priority(other)

    return buff.key > other.key


def _item_conflicts(buff, character, buff_seams) -> list:
    """Each clash between the buff and an item that the character holds."""
    conflicts = []

    for item in character.contents:
        for rules in rules_of(item):
            shared = buff_seams & contested_seams(rules)

            for seam in sorted(shared):
                wins = _wins_over_gear(buff, rules)
                conflicts.append(SeamConflict(seam, RIVAL_ITEM, item.key, rules.key, wins))

    return conflicts


def _buff_conflicts(buff, character, buff_seams) -> list:
    """Each clash between the buff and another buff that the task holds."""
    from systems.gameplay.exterminator.buffs import BUFF_REGISTRY, buff_name

    handler = getattr(character, "exterminator", None)
    held = handler.held_buffs() if handler is not None else ()
    preceptor_key = handler.preceptor_key() if handler is not None else None
    conflicts = []

    for other_key in held:
        other = BUFF_REGISTRY.get(other_key)

        if other is None or other_key == buff.key:
            continue

        shared = buff_seams & contested_seams(other)

        for seam in sorted(shared):
            wins = _wins_over_buff(buff, other)
            rival_name = buff_name(other, preceptor_key)
            conflicts.append(SeamConflict(seam, RIVAL_BUFF, rival_name, other.key, wins))

    return conflicts



# ─── Public routines ────────────────────────────────────────────────────────

def seam_conflicts(buff, character) -> list:
    """
    Purpose: Name each seam where a buff clashes with the gear or the buffs
             of a character.

    Entry:
        buff is a stamped buff instance (buffs.instantiate).
        character is the player who would hold it.

    Exit/Returns:
        Returns a list of SeamConflict. Empty for a modifier buff.

    Module Globals:
        None.

    Methodology:
        1. Take the seams of the buff, without contribute_modifiers.
        2. If none is left, return no conflict.
        3. Compare with each rules instance of each item in the contents of
           the character. Equipped items are in the contents too.
        4. Compare with each other buff that the task holds.
        The winner comes from the priority, with the tie rule of
        merge_contributors.

    Notes/References:
        _resolve_winners in combat/rules/pipeline.py drops the modifier seam
        from the contest the same way.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    buff_seams = contested_seams(buff)

    if not buff_seams:
        return []

    item_conflicts = _item_conflicts(buff, character, buff_seams)
    buff_conflicts = _buff_conflicts(buff, character, buff_seams)

    return item_conflicts + buff_conflicts
