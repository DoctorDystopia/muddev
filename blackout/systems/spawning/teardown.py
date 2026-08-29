"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: What a room takes with it when it is destroyed.

             ``systems/spawning/respawn.py`` owns what fills a room; this
             module owns what happens to that fill when the room goes away. It
             is the counterpart, and it is deliberately in the same package so
             the pair is obvious.

The bug this exists to close
----------------------------
``DefaultObject.delete()`` calls ``clear_contents()``, which does NOT delete a
room's contents -- it moves each of them to its ``home``, and rewrites that
home to ``settings.DEFAULT_HOME`` whenever the home *is* the room being
deleted. Nothing the spawners create passes ``home=``, so every gathering
node, facility, bank and NPC on the grid homes to Limbo (#2) and is *exiled*
there rather than destroyed on a map rebuild.

That is not a hypothetical. On 08/28/2026 the development database held 623
objects standing in Limbo with 197 more nested inside them, against 23 real
non-exit objects on the entire live grid -- roughly a third of the object
table, accumulated over the map rebuilds of a single development cycle.

The rule
--------
A room's contents split three ways when the room is destroyed:

  1. Player characters fall through to ``clear_contents`` and go to their home
     as they always have. A rebuild must never destroy a player.
  2. Anything held BY such a character travels with them, because it is not a
     direct content of the room at all.
  3. Everything else -- NPCs, nodes, facilities, and items lying on the floor
     -- is destroyed with the room.

Rule 3 is deliberately not keyed on a "this was spawned by the map" tag. A tag
has to be stamped at spawn time, so it can say nothing about the objects
already stranded, and it says the wrong thing about a sword a player dropped
on the floor -- which under a tag scheme would be exiled to Limbo and
reintroduce the same leak at a smaller scale. Rule 3 is the right reading of
both: an operator rebuilding the grid is razing the world, and litter in a
razed room goes with it. The tag below is therefore an EXEMPTION, defaulting
to nothing, in the shape ``DEV_TOOL_TAG_CATEGORY`` uses in
``systems/devtools/constants.py``.

Depth-first, and why it is not optional
---------------------------------------
``obj.delete()`` runs the same ``clear_contents`` on the object's OWN
contents. Deleting a shopkeep therefore evicts its stock into Limbo instead of
destroying it -- which is exactly how 197 of those 820 objects got there.
Contents must be destroyed before their container, never the other way round.

Exits are not this module's business
------------------------------------
``clear_exits()`` already destroys both the exits standing in the room and the
exits elsewhere that point AT it, and only it can see the second set. Anything
carrying a ``db_destination`` is skipped here so that fact keeps one owner.
"""

from django.conf import settings

from evennia.utils import logger

# ─── module constants ──────────────────────────────────────────────────────

# Stamp this on an object that must survive a map rebuild standing where it
# is. Nothing in the game carries it today; it exists so that a staff-placed
# prop or a future landmark has a way to say so that is not "edit teardown.py".
TEARDOWN_EXEMPT_TAG: str = "survives_rebuild"
TEARDOWN_EXEMPT_TAG_CATEGORY: str = "map_teardown"

# A container nested more deeply than this is treated as a cycle rather than as
# a very deep bag. Nothing in Blackout nests past 2 (room -> shopkeep -> stock);
# the bound exists so a corrupt location loop cannot spin the recursion forever
# in the middle of an operator's rebuild.
_MAX_TEARDOWN_DEPTH: int = 12


# ─── predicates ────────────────────────────────────────────────────────────


def is_player_character(obj) -> bool:
    """
    Purpose: True if `obj` is a player's character rather than world furniture.

    Entry:
        obj is any Evennia object, or None.

    Exit/Returns:
        Returns True for anything built on settings.BASE_CHARACTER_TYPECLASS,
        or carrying an account. False otherwise, including for None.

    Module Globals:
        None

    Methodology:
        Ask the typeclass first, then fall back to an attached account.

    Notes/References:
        The typeclass test is the load-bearing one and `db_account` is belt and
        braces. Blackout's NPCs descend from DefaultObject, not
        DefaultCharacter (see typeclasses/npcs.py and typeclasses/npc_combat.py),
        so the two populations do not overlap and this test cannot spare a
        mutant raider by accident.

        `has_account` is NOT usable here: it reports whether the object is
        puppeted *right now*, so a character standing in a room while its
        player is logged out would read as furniture and be destroyed.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    if obj is None:
        return False

    is_character = obj.is_typeclass(settings.BASE_CHARACTER_TYPECLASS, exact=False)
    if is_character:
        return True

    account = getattr(obj, "db_account", None)

    return account is not None


def survives_teardown(obj) -> bool:
    """
    Purpose: True if `obj` must be left standing when its room is destroyed.

    Entry:
        obj is any Evennia object, or None.

    Exit/Returns:
        Returns True for player characters, for exits, and for anything
        carrying the teardown exemption tag. False for everything else.

    Module Globals:
        TEARDOWN_EXEMPT_TAG, TEARDOWN_EXEMPT_TAG_CATEGORY read.

    Methodology:
        Three independent reprieves, cheapest first.

    Notes/References:
        An exit survives this module only in the sense that it is not this
        module's to destroy -- `clear_exits` takes it moments later, and is the
        only caller that can also find the exits pointing back at the room.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    if obj is None:
        return True

    is_character = is_player_character(obj)
    if is_character:
        return True

    destination = getattr(obj, "db_destination", None)
    if destination is not None:
        return True

    is_exempt = obj.tags.has(TEARDOWN_EXEMPT_TAG, category=TEARDOWN_EXEMPT_TAG_CATEGORY)

    return bool(is_exempt)


# ─── demolition ────────────────────────────────────────────────────────────


def demolish(obj, depth: int = 0) -> int:
    """
    Purpose: Destroy `obj` and everything inside it, innermost first.

    Entry:
        obj is a live Evennia object. depth is the current recursion level and
        is supplied by this routine itself; callers pass nothing.

    Exit/Returns:
        Returns the number of objects actually deleted. Never raises: a single
        stubborn object is logged and skipped so an operator's rebuild is not
        abandoned half-done.

    Module Globals:
        _MAX_TEARDOWN_DEPTH read.

    Methodology:
        Recurse into contents before deleting the container, because
        `delete()` on a container evicts its contents to their home rather
        than destroying them -- so a container deleted first leaks everything
        it held.

    Notes/References:
        Player characters are spared at every level, not only the top one, so
        a character somehow standing inside a container is still preserved.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    destroyed = 0

    if depth >= _MAX_TEARDOWN_DEPTH:
        logger.log_err(f"teardown: depth limit reached at {obj}; leaving it in place.")
        return destroyed

    held = list(obj.contents)

    for item in held:
        spared = is_player_character(item)
        if spared:
            continue
        destroyed += demolish(item, depth=depth + 1)

    try:
        deleted = obj.delete()
        if deleted:
            destroyed += 1
    except Exception:
        logger.log_trace()

    return destroyed


def demolish_contents(room) -> int:
    """
    Purpose: Destroy everything a room owns, leaving what must survive it.

    Entry:
        room is the room being deleted. It is still live and still holds its
        contents; this runs before Evennia empties it.

    Exit/Returns:
        Returns the number of objects deleted. The room itself is untouched.

    Module Globals:
        None

    Methodology:
        Partition the direct contents with survives_teardown, then demolish
        the remainder depth-first.

    Notes/References:
        Called from GridTile.at_object_delete, which Evennia runs BEFORE
        clear_exits and clear_contents (evennia/objects/objects.py:1549) --
        the only seam that catches every path a room is destroyed by:
        map_sync's purge, XYZGrid.remove_map, and the contrib's own removal of
        a tile that fell off the map in XYMap.spawn_nodes.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    destroyed = 0
    standing = list(room.contents)

    for obj in standing:
        spared = survives_teardown(obj)
        if spared:
            continue
        destroyed += demolish(obj)

    return destroyed
