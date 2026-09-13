"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Builder commands for putting words into the world.

             `sign` and `marker` are the fast path: one line typed in-game and
             the text is standing on the tile, drawn by the Godot client, with
             no map edit and no server restart. That speed is the whole point
             of them -- annotating a broken tile or labelling a landmark while
             you are looking at it should cost less than opening a file.

             What they create lives in the DATABASE, not in the map, and that
             is deliberate rather than a gap. `scripts/map_sync.py` rebuilds a
             map from `world/maps/*.py` and destroys the rooms it no longer
             recognises, taking their contents with them -- so a sign typed
             here lasts exactly as long as the tile it stands on. An
             annotation about work in progress SHOULD be that fragile.
             Permanent signage belongs in the map module, where it is
             regenerated with everything else.

             Deletion is not here. Evennia's own `destroy` already removes an
             object by name and is the one writer of that path; a second verb
             doing the same thing is a second thing to keep correct.
"""

from evennia import CmdSet
from evennia import create_object

from commands.command import Command
from commands.constants import HELP_CATEGORY_ADMIN
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import labels
from typeclasses.signs import Marker, Sign

# Every line these commands send is the server speaking as itself, so the
# routing tag is bound once rather than repeated at each call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/interface/statefeed/constants.py.
_MSG_SYSTEM = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_SYSTEM}

_NAME_SEPARATOR: str = "="


class CmdSign(Command):
    """
    Put up a sign, or list the ones standing here.

    Usage:
      sign                       -- what is labelled in this room
      sign <text>                -- put up a sign reading <text>
      sign <name> = <text>       -- ...and call the object <name>

    The text is capped and stripped of colour codes, because it is drawn
    floating in the world rather than printed. Say more in the object's desc.

    Remove one with Evennia's own `destroy <name>`.
    """
    key = "sign"
    aliases = ["@sign"]
    locks = "cmd:perm(Builder)"
    help_category = HELP_CATEGORY_ADMIN

    # Which typeclass this command stands up. Declared rather than hardcoded
    # in func, so CmdMarker below is one attribute's worth of subclass instead
    # of a copy of the whole routine.
    sign_class = Sign

    # What the created object is called when the builder named none, and the
    # label was all whitespace by the time it was normalised.
    fallback_key = "sign"


    def func(self) -> None:
        """
        Purpose: List this room's labels, or stand up a new one.

        Entry:
            self.caller stands in a room. self.args is the text, optionally
            prefixed with `<name> =`.

        Exit/Returns:
            No conditions. Messages the caller either way.

        Module Globals:
            _MSG_SYSTEM read.

        Methodology:
            Bare invocation LISTS rather than erroring. A builder who has
            walked back to a tile they annotated last week wants to know what
            it says before they add a second one, and a usage string is the
            least useful thing to print at someone standing in the answer.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        caller = self.caller
        room = caller.location

        if room is None:
            caller.msg(("You are nowhere. Nothing to sign.", _MSG_SYSTEM))

            return

        typed = self.args.strip()

        if not typed:
            self._listing(room)

            return

        self._create(room, typed)


    # ─── Private helper routines ─────────────────────────────────────────────

    def _create(self, room, typed: str) -> None:
        """
        Purpose: Stand a new sign on the caller's tile.

        Entry:
            room  - where it goes.
            typed - the raw argument string, `<name> = <text>` or just <text>.

        Exit/Returns:
            No conditions. Messages the caller with what was put up.

        Module Globals:
            _MSG_SYSTEM read.

        Methodology:
            Built DETACHED and then moved, never created into the room. Only
            `move_to` fires the room's at_object_receive, and that hook is
            what publishes the arrival to the statefeed -- a sign created
            straight into a location is invisible to every client already
            standing there until it next moves. CLAUDE.md lists this as
            gotcha 5 and it is exactly the shape this command would hit.

            The label is assigned through the property, so labels.normalise
            runs once and the stored value is already clean for every reader.
            An empty result is refused rather than stood up: a sign with
            nothing on it is indistinguishable from scenery.

            Nothing here writes a `desc`. Sign.at_object_creation sets one off
            its own class, so a Marker describes itself as a Marker and this
            command does not have to know there are two of them.

        Notes/References:
            typeclasses/rooms.py at_object_receive is the hook in question.

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        caller = self.caller
        name, text = self._split_name(typed)
        label = labels.normalise(text)

        if not label:
            caller.msg(("That leaves nothing to read.", _MSG_SYSTEM))

            return

        key = name or self._key_from(label)
        sign = create_object(self.sign_class, key=key, location=None)
        sign.world_label = label
        sign.move_to(room, quiet=True, move_type="teleport")

        caller.msg((f"{sign.key} now reads: {label}", _MSG_SYSTEM))


    def _listing(self, room) -> None:
        """
        Purpose: Tell the caller what in this room carries a label.

        Entry:
            room - the caller's location.

        Exit/Returns:
            No conditions. Messages the caller.

        Module Globals:
            _MSG_SYSTEM read.

        Methodology:
            Asks every object for a `world_label` rather than filtering on the
            Sign typeclass. The label is a field ANY entity may declare -- the
            serializer reads it the same blind way -- so a listing that knew
            about signs would go quietly wrong the first time something else
            grew something to say.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        lines = []

        for obj in room.contents:
            label = getattr(obj, "world_label", "")

            if not label:
                continue

            flat = label.replace("\n", " / ")
            lines.append(f"  {obj.key}: {flat}")

        if not lines:
            self.caller.msg(("Nothing here is labelled.", _MSG_SYSTEM))

            return

        body = "\n".join(lines)
        self.caller.msg((f"Labelled here:\n{body}", _MSG_SYSTEM))


    def _split_name(self, typed: str) -> tuple:
        """
        Purpose: Separate an optional object name from the sign's text.

        Entry:
            typed - the raw argument string.

        Exit/Returns:
            Returns (name, text). `name` is "" when none was given, and the
            whole string is the text.

        Module Globals:
            _NAME_SEPARATOR read.

        Methodology:
            Split ONCE, on the first separator. A sign reading `Fuel = Credits`
            is a thing a builder may reasonably want, and splitting on every
            occurrence would silently eat half of it.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        if _NAME_SEPARATOR not in typed:
            return "", typed

        name, _, text = typed.partition(_NAME_SEPARATOR)

        return name.strip(), text.strip()


    def _key_from(self, label: str) -> str:
        """
        Purpose: Name an object after what it says, when nobody named it.

        Entry:
            label - an already normalised label.

        Exit/Returns:
            Returns the label's first line, or `fallback_key` when that is
            empty.

        Module Globals:
            None.

        Methodology:
            The first LINE and not the first word. A key is what `look`,
            `destroy` and every other command matches against, so it should be
            the thing a builder would actually type -- and for a one-line sign
            that is the sign. The label cap already bounds it.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        first = label.splitlines()[0].strip()

        if not first:
            return self.fallback_key

        return first


class CmdMarker(CmdSign):
    """
    Leave a note to the developers, standing in the world.

    Usage:
      marker                     -- what is labelled in this room
      marker <text>              -- leave a marker reading <text>
      marker <name> = <text>     -- ...and call the object <name>

    A marker is drawn differently from a sign on purpose: it is a note ABOUT
    the game, not a piece of it, and no player should mistake one for the
    other.

    Remove one with Evennia's own `destroy <name>`.
    """
    key = "marker"
    aliases = ["@marker"]
    sign_class = Marker
    fallback_key = "marker"


class BuildCmdSet(CmdSet):
    """
    Purpose: The builder commands that put words into the world.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        Both commands carry `cmd:perm(Builder)`, so the cmdset is safe to hang
        on every character -- the lock is what decides who sees them, checked
        once per command, which is the arrangement CmdEgg's own permission
        story argues for.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    key = "BuildCmdSet"


    def at_cmdset_creation(self) -> None:
        """
        Purpose: Populate the cmdset.

        Entry:
            No conditions.

        Exit/Returns:
            No conditions.

        Module Globals:
            None.

        Methodology:
            Straight adds.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        self.add(CmdSign())
        self.add(CmdMarker())
