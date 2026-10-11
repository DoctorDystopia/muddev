"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: The one call that combat makes when a creature dies, so that
             each damage dealer's Exterminator task can count the kill.
"""

from evennia.utils import logger



# ─── Private helper routines ────────────────────────────────────────────────

def _shares(record: dict, max_hp: int) -> dict:
    """
    Purpose: Share the XP of one kill between the damage dealers.

    Entry:
        record is {attacker id: damage > 0}. It is not empty.
        max_hp >= 0. It is the XP of the whole kill.

    Exit/Returns:
        Returns {attacker id: XP share}. Each share is an int >= 0.

    Module Globals:
        None.

    Methodology:
        Integer math: share = max_hp * damage // total damage. A sole damage
        dealer gets max_hp. A very small share can round to 0. The kill
        still counts for that dealer.

    Notes/References:
        Nick, 10/06/2026: the XP is shared by damage.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    total_damage = sum(record.values())
    shares = {}

    for attacker_id, damage in record.items():
        shares[attacker_id] = max_hp * damage // total_damage

    return shares


def _dealers(attacker_ids) -> list:
    """Load the damage dealers that still exist, in one query."""
    from evennia.objects.models import ObjectDB

    found = ObjectDB.objects.filter(id__in=list(attacker_ids))

    return list(found)



# ─── Public routines ────────────────────────────────────────────────────────

def notify_exterminator(victim: object) -> None:
    """
    Purpose: Count a kill on the task of each player who damaged the victim.

    Entry:
        victim is the entity that just died, inside at_death and before
        respawn() deletes it. It can be anything, a player included.

    Exit/Returns:
        No conditions. Never raises.

    Module Globals:
        None.

    Methodology:
        1. Read the creature types of the victim. If it has none, stop. A
           player and an NPC with no type stop here.
        2. Read the record of damage dealers. If it is empty, stop.
        3. Share the max HP of the victim between the dealers, by damage.
        4. For each dealer with an `exterminator` handler, record the kill.
           A dealer with no handler (an NPC) is skipped.

        Anything that raises is logged and swallowed. A task bug must never
        abort the death that reported it, for the reason notify_quests gives.

    Notes/References:
        Nick, 10/06/2026: each player who did damage gets the kill, and the
        XP is the max HP, shared by damage. The imports are local, because
        typeclasses/mixins.py imports this module at startup.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    try:
        from world.npc_database import creature_types_of

        victim_types = creature_types_of(victim)

        if not victim_types:
            return

        record = victim.damage_record()

        if not record:
            return

        max_hp = int(getattr(victim, "max_hp", 0) or 0)
        shares = _shares(record, max_hp)

        dealers = _dealers(shares)
    except Exception as exc:
        logger.log_err(f"notify_exterminator: {victim} failed: {exc!r}")
        return

    # One try for each dealer, so a fault on one task does not cost the
    # other dealers their kill.
    for dealer in dealers:
        handler = getattr(dealer, "exterminator", None)

        if handler is None:
            continue

        try:
            handler.record_kill(victim_types, shares.get(dealer.id, 0))
        except Exception as exc:
            logger.log_err(f"notify_exterminator: {dealer} on {victim} failed: {exc!r}")
