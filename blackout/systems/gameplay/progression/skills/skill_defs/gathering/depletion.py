"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/20/2026
Description: Per-player node depletion -- who has stripped a node, and until
             when.

Why the state lives on the NODE
-------------------------------
The row is {character_id: expiry} on the node's own Attribute. It could as
easily have been {node_id: expiry} on the character, and that version is
wrong for two reasons:

  * A deleted node must take the fact with it. A map rebuild deletes and
    recreates every tile in the game (see CLAUDE.md, "A deleted room destroys
    what stands on it"), and a character-side list would keep naming ids that
    no longer exist, forever, growing for the life of the account.
  * "Is this node spent for you" is a question about the node. Asking it of
    the character means the serializer, which already holds the node, has to
    go and fetch the observer's list to answer.

Why depletion is per player at all
----------------------------------
Global depletion is the OSRS rule and it brings OSRS's competition with it.
Blackout is a MUD, and two players at one pole is a normal Tuesday rather
than a contested resource. Per-player keeps the node standing where it is --
nothing vanishes under anyone's feet -- and costs one Attribute read on the
serializer's path.

The cost of that choice is real and is paid in one place: the entity list a
client draws is no longer the same for every observer. See
systems/interface/statefeed/serializers.py serialize_entity, which grew an
`observer` argument for this and for nothing else.
"""



import time

from collections.abc import Mapping

from evennia.utils import logger

from systems.gameplay.progression.skills.skill_defs.gathering import (
    constants as gather_constants,
)



def _rows(node) -> dict:
    """
    Purpose: The node's spent-until map, or an empty one.

    Entry:
        node is any object. It need not be a gathering node, and it need not
        have the Attribute.

    Exit/Returns:
        Returns a dict of {character_id: expiry}. A COPY is never made: the
        caller must not mutate what it gets back unless it writes it again.

    Module Globals:
        gather_constants.SPENT_ATTRIBUTE read.

    Methodology:
        Read through `attributes.get` so this is safe on an object that has
        no Attribute handler at all. The serializer calls this for every
        entity in the neighbourhood on every move, and most of them are
        people.

        THE TYPE CHECK IS Mapping, NOT dict. Evennia hands a stored dict back
        as a `_SaverDict`, which subclasses MutableMapping and NOT dict -- so
        `isinstance(stored, dict)` is False for every row this module ever
        writes, and the whole depletion system read as "nothing is ever
        spent". Checked here rather than assumed, because a hand-edited
        Attribute can still be any type at all.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    attributes = getattr(node, "attributes", None)

    if attributes is None:
        return {}

    stored = attributes.get(gather_constants.SPENT_ATTRIBUTE, default=None)

    if not isinstance(stored, Mapping):
        return {}

    return stored



def _prune(node, rows: dict, now: float) -> dict:
    """
    Purpose: Drop expired rows, but only when there are enough to be worth a
    write.

    Entry:
        node is the node holding the rows.
        rows is its spent-until map.
        now is the current unix time.

    Exit/Returns:
        Returns the map as it now stands. Writes the Attribute only when it
        actually removed something past the threshold.

    Module Globals:
        gather_constants.SPENT_ATTRIBUTE and SPENT_PRUNE_THRESHOLD read.

    Methodology:
        A busy node collects one row per harvester and each row is dead
        within a minute. Pruning on every read would be correct and would
        cost a database write per swing per player, on the serializer's path.
        Pruning past a threshold is equally correct and costs nothing in the
        common case, because an expired row answers "not spent" whether it is
        still in the dict or not.

        The threshold counts EXPIRED rows, not total rows. A node worked by
        thirty live players holds thirty live rows and must keep all of them.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    expired = [key for key, until in rows.items() if until <= now]

    if len(expired) < gather_constants.SPENT_PRUNE_THRESHOLD:
        return rows

    remaining = {
        key: until for key, until in rows.items() if until > now
    }

    node.attributes.add(gather_constants.SPENT_ATTRIBUTE, remaining)

    return remaining



def spent_until(node, character) -> float:
    """
    Purpose: When this node comes back for this character.

    Entry:
        node is any object.
        character is any object with an id.

    Exit/Returns:
        Returns a unix timestamp in the future, or 0.0 when the node is not
        spent for them.

    Module Globals:
        None.

    Methodology:
        Returns the TIME rather than a bool because two callers want
        different things from one lookup: the refusal message wants to know
        whether to refuse, and a future countdown display wants the number.
        A predicate that throws the number away forces the second caller to
        read the Attribute again.

    Notes/References:
        is_spent_for is the predicate built on this.

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    rows = _rows(node)

    if not rows:
        return 0.0

    character_id = getattr(character, "id", None)
    until = rows.get(character_id, 0.0)
    now = time.time()

    if until <= now:
        return 0.0

    return until



def is_spent_for(node, character) -> bool:
    """
    Purpose: Whether this character has already stripped this node.

    Entry:
        node is any object. character is any object with an id.

    Exit/Returns:
        Returns True while the node is spent for them.

    Module Globals:
        None.

    Methodology:
        One call into spent_until, so the two answers cannot disagree.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    until = spent_until(node, character)

    return until > 0.0



def mark_spent(node, character, seconds: int) -> float:
    """
    Purpose: Strip this node for this character, and make both ends of that
    reach their client.

    Entry:
        node is a live gathering node.
        character is the harvester.
        seconds is how long the node stays spent. A value of zero or less
            does nothing and is not an error -- a node that cannot deplete
            reaches here only through a caller that did not check, and a
            refusal would turn a harmless call into a broken harvest.

    Exit/Returns:
        Returns the expiry timestamp, or 0.0 when nothing was marked.

    Module Globals:
        gather_constants.SPENT_ATTRIBUTE read.

    Methodology:
        Writes the row, then schedules BOTH refreshes: one now, because the
        node just stopped affording anything, and one at the expiry, because
        it starts affording again with no event to announce it.

        The second one is the whole reason this routine exists rather than
        the caller writing the Attribute itself. A node that comes back
        without telling the client is exactly the stale pane CLAUDE.md
        describes under "Every pane follows its facts": nothing moves at the
        moment of the change, so only a scheduled mark can catch it. The
        pattern is refresh_summary(obj, delay=...) and this is the same
        shape, on the entity list.

        The refresh import is deferred. The statefeed reaches into the skill
        system in several places and a module-level import here would close
        that ring.

    Notes/References:
        systems/interface/statefeed/events.py refresh_room_contents.

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    if seconds <= 0:
        return 0.0

    now = time.time()
    rows = _rows(node)
    pruned = _prune(node, rows, now)
    character_id = getattr(character, "id", None)
    expiry = now + seconds
    updated = dict(pruned)

    updated[character_id] = expiry
    node.attributes.add(gather_constants.SPENT_ATTRIBUTE, updated)

    _schedule_refresh(character, seconds)

    return expiry



def _schedule_refresh(character, seconds: int) -> None:
    """
    Purpose: Tell this character's client that the node went, and that it
    came back.

    Entry:
        character is the harvester.
        seconds is when the node returns.

    Exit/Returns:
        No conditions. Never raises.

    Module Globals:
        None.

    Methodology:
        Wrapped, because the feed is a bystander to the harvest. A client
        with no subscription, a session that just dropped, or a broken
        builder must not cost the player the chunk they just earned. Same
        posture _record_stat takes around a broken stat tracker.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    from systems.interface.statefeed.events import refresh_room_contents

    try:
        refresh_room_contents(character)
        refresh_room_contents(character, delay=seconds)
    except Exception as exc:
        logger.log_err(f"depletion._schedule_refresh failed: {exc!r}")
