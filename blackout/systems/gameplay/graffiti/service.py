"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: The effects: writing a scrawl, spending a charge, and taking the
             old ones away again.

             Nothing here is scheduled and nothing here is a command. Every
             routine is callable from a test, a fixture or a future menu with
             no session, no EvMenu and no clock running -- the same rule the
             moderator egg's actions.py follows, and for the same reason: the
             `write` command, the hourly sweep and the moderator's Erase row
             are three callers of one set of effects, and an effect that could
             only be reached through one of them is one the other two have to
             re-implement.

             WHAT COUNTS AS GRAFFITI IS THIS MODULE'S ANSWER. Both the sweep
             and the moderator's erase filter on the Graffiti typeclass, which
             is a stronger guard than a tag would be: Sign and Marker are its
             SIBLINGS rather than its subclasses, so map-authored signage and a
             builder's notes are structurally out of reach of anything here. A
             tag could be stamped on a signpost by mistake; a typeclass cannot.
"""



import time

from django.conf import settings
from evennia import create_object
from evennia.utils import logger

from systems.interface.statefeed import labels
from typeclasses.signs import Graffiti

from . import constants as const



# ─── Public interface ────────────────────────────────────────────────────────

def write(writer, text) -> tuple:
    """
    Purpose: Leave a player's words standing in the room they are in.

    Entry:
        writer - a Character, standing somewhere, carrying a medium.
        text   - what they typed.

    Exit/Returns:
        Returns (succeeded, message). The message is always something worth
        showing the writer, including on every refusal -- a silent failure
        here is a player who thinks the command is broken.

    Module Globals:
        const read throughout.

    Methodology:
        Ordered so nothing is spent on a write that will not happen. The text
        is normalised and checked against the refusal list BEFORE the medium
        is charged, because a player who is told no keeps their charge -- and
        the reverse, charging for a refusal, is the version that reads as the
        game stealing from them.

        Built DETACHED and then moved, never created into the room. Only
        `move_to` fires the room's at_object_receive, and that hook is what
        publishes the arrival to the statefeed -- otherwise the writer stands
        looking at a wall they just wrote on and sees nothing. CLAUDE.md lists
        this as gotcha 5.

        The room is told, and the writer is named in what it is told. Writing
        on a wall in front of other people is a public act; a silent one would
        let a player deny it to the face of someone who watched.

    Notes/References:
        The cap and the markup rules are labels.normalise's, shared with every
        other kind of world label.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    room = writer.location

    if room is None:
        return False, const.MSG_NOWHERE

    label = labels.normalise(text)

    if not label:
        return False, const.MSG_NOTHING_TO_WRITE

    if is_refused(label):
        return False, const.MSG_REFUSED

    medium = medium_of(writer)

    if medium is None:
        return False, const.MSG_NO_MEDIUM

    if charges_left(medium) < 1:
        return False, const.MSG_EMPTY_MEDIUM.format(medium=medium.key)

    _stand_up(writer, room, label)

    return True, _spend_one(medium)



def medium_of(writer):
    """
    Purpose: The thing in a writer's hands that can write, if any.

    Entry:
        writer - a Character.

    Exit/Returns:
        Returns the first carried object tagged as a medium, or None.

    Module Globals:
        const.GRAFFITI_MEDIUM_CATEGORY read.

    Methodology:
        Found by TAG CATEGORY, not by typeclass or key. A second medium -- a
        paint stick, a welding torch -- is then one ItemDef entry and no edit
        here, which is the same bargain `_has_tool_available` strikes for
        crafting tools and `_is_staff_item` for the egg.

        FIRST match rather than the fullest. A player carrying two half-empty
        cans wants the command to work, not to be asked which one; an empty
        one is refused by the caller and they can drop it.

    Notes/References:
        world/item_defs/tools.py stamps the tag.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    for carried in writer.contents:
        tagged = carried.tags.get(
            category=const.GRAFFITI_MEDIUM_CATEGORY, return_list=True)

        if tagged:
            return carried

    return None



def charges_left(medium) -> int:
    """
    Purpose: How many more times a medium can be used.

    Entry:
        medium - an object carrying the medium tag.

    Exit/Returns:
        Returns a non-negative integer. A medium that has never been used
        reports const.DEFAULT_CHARGES.

    Module Globals:
        const.CHARGES_ATTR and const.DEFAULT_CHARGES read.

    Methodology:
        The default is applied on READ rather than stamped at creation, which
        is what lets an item declare the medium tag and nothing else and still
        work at the standard capacity. A can wanting its own number sets the
        attribute; every other item in the game needs no ItemDef field for a
        system it has nothing to do with.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    stored = medium.attributes.get(const.CHARGES_ATTR, default=None)

    if stored is None:
        return const.DEFAULT_CHARGES

    try:
        return max(0, int(stored))
    except (TypeError, ValueError):
        logger.log_err(
            f"graffiti.charges_left: {medium} has a non-numeric charge count "
            f"{stored!r}; treating it as empty.")

        return 0



def author_id_of(scrawl) -> int:
    """
    Purpose: Which character wrote this, as a dbref id.

    Entry:
        scrawl - any object. Almost none were written by anybody.

    Exit/Returns:
        Returns the author's integer id, or 0 when nothing recorded one.

    Module Globals:
        const.AUTHOR_ID_ATTR read.

    Methodology:
        Zero is a safe "nobody", because Evennia object ids start at 1 -- the
        same convention EntityPool.pick uses for "no entity". It is also the
        honest answer for map-authored signage, which has no author and must
        never match a search for one.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    stored = scrawl.attributes.get(const.AUTHOR_ID_ATTR, default=0)

    try:
        return int(stored or 0)
    except (TypeError, ValueError):
        return 0



def is_refused(label: str) -> bool:
    """
    Purpose: Whether the server declines to write this at all.

    Entry:
        label - an already normalised label.

    Exit/Returns:
        True when the text contains a blocked word.

    Module Globals:
        const.BLOCKLIST_SETTING and const.BLOCKLIST_DEFAULT read, through
        Django settings.

    Methodology:
        ONE place, ahead of the writing. A check that ran after the object
        existed would have to delete it, and a check spread over the command
        and the service would be two rules that can disagree.

        Empty by default. A blocklist is an editorial decision about a
        particular community, and this module's job is to make turning one on
        a settings edit rather than a patch -- not to make the decision.

        Substring, case-insensitive, therefore over-blocking. That is the
        right direction to fail: a refused scrawl costs a player a charge they
        keep, and a permitted one costs a moderator a callout.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    blocked = getattr(
        settings, const.BLOCKLIST_SETTING, const.BLOCKLIST_DEFAULT)

    if not blocked:
        return False

    lowered = label.lower()

    for word in blocked:
        if str(word).lower() in lowered:
            return True

    return False



def expired(scrawl, now=None) -> bool:
    """
    Purpose: Whether a scrawl has outlived its welcome.

    Entry:
        scrawl - a Graffiti object.
        now    - the wall-clock seconds to measure against. Defaults to the
                 real one; passed explicitly by tests, which must not wait a
                 week.

    Exit/Returns:
        True when the scrawl is older than const.LIFETIME_SECONDS. True also
        for one carrying no timestamp at all.

    Module Globals:
        const.WRITTEN_AT_ATTR and const.LIFETIME_SECONDS read.

    Methodology:
        An UNSTAMPED scrawl counts as expired, which is the safe direction for
        a system whose whole job is that the world does not fill up. Anything
        without a timestamp was either written before this field existed or
        written by something that did not go through `write`, and in both cases
        keeping it forever is the outcome nobody asked for.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    written = scrawl.attributes.get(const.WRITTEN_AT_ATTR, default=None)

    if written is None:
        return True

    if now is None:
        now = time.time()

    try:
        age = float(now) - float(written)
    except (TypeError, ValueError):
        return True

    return age >= const.LIFETIME_SECONDS



def sweep(now=None) -> int:
    """
    Purpose: Destroy every scrawl that has expired.

    Entry:
        now - wall-clock seconds to measure against, for tests.

    Exit/Returns:
        Returns how many were destroyed.

    Module Globals:
        None.

    Methodology:
        Queried with `all_family`, which filters on the stored typeclass path
        -- so Sign and Marker, being SIBLINGS of Graffiti rather than
        subclasses, cannot be reached by this no matter how the lifetime is
        configured. That is the structural half of the guard; the other half
        is that nothing else in the game is a Graffiti.

        Materialised into a list before deleting. Deleting out of a live
        queryset is the shape of bug that silently skips every other row, and
        the cost here is a list of objects that are all about to be freed
        anyway.

        Each deletion is wrapped. A row mid-deletion or one whose room is
        already gone must not stop the sweep -- the next hour's run would
        start at the same object and stall there forever.

    Notes/References:
        Deleting the object publishes its removal to every subscribed client
        through ObjectParent.at_object_delete.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    if now is None:
        now = time.time()

    doomed = []

    for scrawl in list(Graffiti.objects.all_family()):
        if expired(scrawl, now=now):
            doomed.append(scrawl)

    return _destroy_all(doomed)



def erase_by_author(author) -> int:
    """
    Purpose: Destroy everything one character has ever written.

    Entry:
        author - the Character whose scrawls are to go.

    Exit/Returns:
        Returns how many were destroyed.

    Module Globals:
        None.

    Methodology:
        By AUTHOR rather than by room, because that is the question a
        moderator actually has. A player reported for one scrawl has almost
        never written only one, and clearing the tile they were reported on
        leaves the rest standing across the map with nothing to find them by.

        The author is matched on the recorded id and not on the object, so a
        character who has since been renamed is still found -- and a scrawl
        with no author, which is every piece of map signage, matches nobody.

    Notes/References:
        systems/devtools/actions.py erase_graffiti is the moderator-facing
        caller, and the one that writes the audit line.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    wanted = getattr(author, "id", 0) or 0

    if wanted < 1:
        return 0

    doomed = []

    for scrawl in list(Graffiti.objects.all_family()):
        if author_id_of(scrawl) == wanted:
            doomed.append(scrawl)

    return _destroy_all(doomed)



def written_by(author) -> int:
    """
    Purpose: How many scrawls one character has standing in the world.

    Entry:
        author - a Character.

    Exit/Returns:
        Returns the count, without destroying anything.

    Module Globals:
        None.

    Methodology:
        Exists so the moderator's confirmation can COUNT what it is about to
        destroy and name whose it is. "Erase 31 scrawls by Bob" catches a
        wrong target; "are you sure?" gets confirmed. That is the same
        argument the egg's inventory confirmation already makes, and the
        reason this is a separate read rather than a return value of the
        erase.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    wanted = getattr(author, "id", 0) or 0

    if wanted < 1:
        return 0

    found = 0

    for scrawl in Graffiti.objects.all_family():
        if author_id_of(scrawl) == wanted:
            found += 1

    return found



# ─── Private helper routines ─────────────────────────────────────────────────

def _stand_up(writer, room, label: str) -> None:
    """
    Purpose: Create the scrawl, stamp its provenance, and put it in the room.

    Entry:
        writer - the author.
        room   - where it goes.
        label  - the already normalised text.

    Exit/Returns:
        No return value. The room is messaged.

    Module Globals:
        const.GRAFFITI_KEY and the provenance attribute names read.

    Methodology:
        Author and timestamp are stamped BEFORE the move, so the arrival the
        move publishes describes a complete object. A client that received it
        mid-stamping would be drawing a scrawl nobody wrote.

        The id is stored and the NAME is not. The id is what erase matches
        on and it survives a rename, where a stored name would not -- and a
        name that can disagree with the character it points at is the one a
        moderator would read. Resolving it is one lookup, when it is wanted.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    scrawl = create_object(Graffiti, key=const.GRAFFITI_KEY, location=None)
    scrawl.world_label = label
    scrawl.attributes.add(const.AUTHOR_ID_ATTR, writer.id)
    scrawl.attributes.add(const.WRITTEN_AT_ATTR, time.time())
    scrawl.move_to(room, quiet=True, move_type="teleport")

    room.msg_contents(
        const.MSG_ROOM_WROTE.format(author=writer.key), exclude=[writer])



def _spend_one(medium) -> str:
    """
    Purpose: Take one charge off a medium, destroying it when that was the
             last.

    Entry:
        medium - the object that did the writing.

    Exit/Returns:
        Returns the line to show the writer, which differs on the last charge.

    Module Globals:
        const.CHARGES_ATTR, const.MSG_WROTE and const.MSG_WROTE_LAST read.

    Methodology:
        The medium is DESTROYED at zero rather than left in the bag empty. An
        empty can is litter a player has to notice and drop, and a bag slowly
        filling with them is a worse outcome than losing an object whose whole
        remaining value was zero.

        The message is read off the count BEFORE the object is deleted,
        because the name goes with it.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    name = medium.key
    left = charges_left(medium) - 1

    if left < 1:
        medium.delete()

        return const.MSG_WROTE_LAST.format(medium=name)

    medium.attributes.add(const.CHARGES_ATTR, left)

    return const.MSG_WROTE.format(left=left, medium=name)



def _destroy_all(doomed) -> int:
    """
    Purpose: Delete a list of scrawls, counting what actually went.

    Entry:
        doomed - a materialised list of objects.

    Exit/Returns:
        Returns how many deletions succeeded.

    Module Globals:
        None.

    Methodology:
        Per-object try/except, the same isolation bootstrap_all and the tick
        engine apply: one unlucky row must not stop the rest, and the
        traceback belongs in the log rather than in whatever called this.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    gone = 0

    for scrawl in doomed:
        try:
            scrawl.delete()
            gone += 1
        except Exception:
            logger.log_trace()

    return gone
