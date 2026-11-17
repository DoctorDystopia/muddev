"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/09/2026
Description: The graft channel: a graft of several samples on the global
             tick. It grafts one unit each GRAFT_TICKS ticks, the pace of
             the OSRS altar (Nick, 11/09/2026). The channel ends when the
             count is done or the samples run out. It also ends when the
             player walks, when a fight starts, and on `graft stop`.

             THE PACE HOLDS FOR EVERY GRAFT. A new channel grafts its first
             unit at once, so `graft mutant gland` answers as before. After
             each graft, the channel stays for GRAFT_TICKS ticks, also with
             nothing left to graft. A second command in that time joins the
             wait. Thus, a click on "Graft 1" again and again is not faster
             than "Graft All".

             IT GRAFTS NOTHING ITSELF. graft.graft consumes the unit, pays
             the XP, and tells the quests. This module owns the cadence and
             the reasons that a channel ends. The model is GatheringHandler
             in skill_defs/gathering/gather_handler.py.

             A reload wipes a channel, as it wipes every tickable. The
             player stands at the Locus and clicks again.
"""

from evennia.utils import logger

from systems.core.tick import states
from systems.core.tick.tickable import (
    TickableHandler,
    ensure_handler,
    get_handler_for,
    register_tickable,
)
from systems.interface.statefeed import constants as feed_const

from . import constants as aug_const
from . import graft as graft_service


# Every line this module sends a player is progression, so the routing tag is
# bound one time here.
_MSG_PROGRESSION = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_PROGRESSION}


# ─── Public constant definitions ─────────────────────────────────────────────

# The script key of the handler. @register_tickable files the class under
# it, and the boot sweep of the engine finds leftovers by it.
GRAFT_HANDLER_KEY: str = "blackout_graft_handler"

# Why a channel ends. _END_MESSAGES names the line of each reason that has
# one. The other reasons speak for themselves: a walk shows the new room,
# and the last graft of a count already sent the done line.
END_DONE: str = "done"
END_OUT: str = "out"
END_MOVED: str = "moved"
END_FIGHT: str = "fight"
END_GONE: str = "gone"


# ─── Private constant definitions ────────────────────────────────────────────

_END_MESSAGES: dict = {
    END_OUT: aug_const.GRAFT_HALT_MESSAGE,
    END_FIGHT: aug_const.GRAFT_FIGHT_MESSAGE,
}

# The report keys. The message templates and the Locus status read them.
_REPORT_NAME: str = "name"
_REPORT_GRAFTED: str = "grafted"
_REPORT_TOTAL: str = "total"


# ─── Private helper routines ─────────────────────────────────────────────────

def _refresh_popup(character) -> None:
    """Send the bag again, for a change that moves no item.

    Two panes read the channel. The Locus pop-up shows the count and the
    Stop button, and the bag puts Stop on the row of the sample
    (11/12/2026). emit_inventory marks an open pop-up out of date too, so
    one send reaches both.

    The import is local: the pop-up registry imports the Locus pop-up, and
    that pop-up imports this module.
    """
    from systems.interface.statefeed import events as feed

    try:
        feed.emit_inventory(character)
    except Exception:
        logger.log_trace()


def _room_id(character):
    """The id of the room of a character, or None."""
    location = getattr(character, "location", None)

    return getattr(location, "id", None)


# ─── Public classes ──────────────────────────────────────────────────────────

@register_tickable
class GraftHandler(TickableHandler):
    """
    Purpose: Graft the units of one sample, one each GRAFT_TICKS ticks.

    Entry:
        The owner is a Character. ensure_handler creates and arms it.

    Exit/Returns:
        No conditions.

    Module Globals:
        GRAFT_HANDLER_KEY read.

    Methodology:
        Every field lives on ndb, like every other tickable. The sample is
        a group name, never an object, because a graft deletes the last
        unit of a stack.

        The state machine: a queue moves IDLE to ACTIVE. A graft moves
        ACTIVE to RECOVERING, and the end of the wait moves it back. A
        queue in RECOVERING stays in RECOVERING, so a new command never
        cuts the wait.

    Notes/References:
        systems/core/tick/states.py holds the transition table.

    Author: Nick Hobar
    Creation date: 11/09/2026
    """

    HANDLER_KEY = GRAFT_HANDLER_KEY
    ACCESSOR_NAME = "grafting"
    HANDLER_DESC = "Per-grafter graft channel"

    def init_runtime_state(self) -> None:
        """(Re)seed the counters that tick() reads. The sample name and the
        room stay None until a command queues a count."""
        if self.ndb.ticks_until_graft is None:
            self.ndb.ticks_until_graft = 0

        if self.ndb.remaining is None:
            self.ndb.remaining = 0

        if self.ndb.grafted is None:
            self.ndb.grafted = 0

        if self.ndb.total is None:
            self.ndb.total = 0

    # ── starting and stopping ────────────────────────────────────────────

    def begin(self, name: str, display: str, count: int) -> None:
        """
        Purpose: Queue a count of one sample on this channel.

        Entry:
            name is the group name of the sample (graft.group_name).
            display is the name that the lines show.
            count is at least GRAFT_COUNT_MIN, and the command already
            clamped it to the units that the player carries.

        Exit/Returns:
            No conditions.

        Module Globals:
            None.

        Methodology:
            1. Read whether the channel is new BEFORE the queue event.
            2. Replace the count, the sample, and the room.
            3. A new channel grafts its first unit now. A channel that
               waits keeps its wait, and its next tick grafts.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 11/09/2026
        """
        self.init_runtime_state()

        fresh = self.state is states.ActivityState.IDLE

        self.ndb.sample_name = name
        self.ndb.display = display
        self.ndb.total = count
        self.ndb.remaining = count
        self.ndb.grafted = 0
        self.ndb.room_id = _room_id(self.obj)

        self.dispatch(states.ActivityEvent.ACTION_QUEUED)

        if fresh:
            self._graft_next(self.obj)

    def report(self):
        """The running count as {name, grafted, total}, or None when no
        count runs. A channel that only waits reports None."""
        remaining = self.ndb.remaining or 0

        if remaining <= 0:
            return None

        return {
            _REPORT_NAME: self.ndb.display,
            _REPORT_GRAFTED: self.ndb.grafted or 0,
            _REPORT_TOTAL: self.ndb.total or 0,
        }

    def halt(self):
        """End the count and keep the wait. Returns the report of the count
        that ended, or None when no count ran. A stop and a new command thus
        cannot cut the wait."""
        report = self.report()

        if report is not None:
            self.ndb.remaining = 0

        return report

    def end(self, reason: str) -> None:
        """
        Purpose: End this channel, say why, and take it apart.

        Entry:
            reason is one of the END_* values.

        Exit/Returns:
            No conditions. Never raises. The engine drops a handler from
            its rotation on an exception. A dropped channel then blocks the
            next graft until a reload.

        Module Globals:
            _END_MESSAGES read.

        Methodology:
            Announce, then unregister, stop, and delete, in that order: the
            line reads the count, and this handler holds it. Then mark an
            open pop-up out of date, because its status reads the channel.
            The accessor pop is CLAUDE.md gotcha 7.

        Notes/References:
            GatheringHandler.stop_gathering is the model.

        Author: Nick Hobar
        Creation date: 11/09/2026
        """
        owner = self.obj

        if owner is not None:
            self._announce_end(owner, reason)
            owner.__dict__.pop(self.ACCESSOR_NAME, None)

        try:
            from systems.core.tick.engine import get_tick_engine

            get_tick_engine().unregister(self)
        except Exception as exc:
            logger.log_err(f"GraftHandler failed to unregister: {exc!r}")

        try:
            self.stop()
        except Exception as exc:
            logger.log_err(f"GraftHandler failed stop: {exc!r}")

        try:
            self.delete()
        except Exception as exc:
            logger.log_err(f"GraftHandler failed delete: {exc!r}")

        if owner is not None:
            _refresh_popup(owner)

    def _announce_end(self, owner, reason: str) -> None:
        """Say why a running count ended. A reason with no line, or a
        channel that only waits, sends nothing."""
        template = _END_MESSAGES.get(reason, "")
        report = self.report()

        if not template or report is None:
            return

        try:
            owner.msg((template.format(**report), _MSG_PROGRESSION))
        except Exception as exc:
            logger.log_err(f"GraftHandler._announce_end failed: {exc!r}")

    # ── the tick ─────────────────────────────────────────────────────────

    def tick(self) -> None:
        """
        Purpose: Advance this channel by one tick.

        Entry:
            The global BlackoutTickEngine calls it.

        Exit/Returns:
            No conditions. Every failure ends the channel, and nothing
            raises, for the reason that end() gives.

        Module Globals:
            None.

        Methodology:
            1. End the channel when its owner is gone, dead, in a fight, or
               off the tile where the count began.
            2. Count the wait down.
            3. At the end of the wait, graft the next unit. With no count
               left, the wait is over, and the channel ends.

        Notes/References:
            The counter re-arms to GRAFT_TICKS - 1 in _graft_next, for the
            reason that GatheringHandler._swing gives.

        Author: Nick Hobar
        Creation date: 11/09/2026
        """
        owner = self.obj

        if owner is None:
            self.end(END_GONE)
            return

        # A reload wipes ndb. Reseed before any read below.
        self.init_runtime_state()

        reason = self._blocking_reason(owner)

        if reason:
            self.end(reason)
            return

        if self.ndb.ticks_until_graft > 0:
            self.ndb.ticks_until_graft -= 1
            return

        if self.ndb.remaining <= 0:
            self.end(END_DONE)
            return

        self.dispatch(states.ActivityEvent.COOLDOWN_EXPIRED)
        self._graft_next(owner)

    def _blocking_reason(self, owner) -> str:
        """The END_* reason that stops this channel now, or "". Each check
        is about the grafter, never about the sample. _graft_next handles a
        missing unit."""
        alive_check = getattr(owner, "is_alive", None)
        is_alive = True if alive_check is None else alive_check()

        if not is_alive:
            return END_GONE

        if getattr(owner, "in_combat", False):
            return END_FIGHT

        here = _room_id(owner)

        if here != self.ndb.room_id:
            return END_MOVED

        return ""

    def _graft_next(self, owner) -> None:
        """
        Purpose: Graft one unit, and close the count when it is the last.

        Entry:
            owner is the grafter, already checked.

        Exit/Returns:
            No conditions.

        Module Globals:
            aug_const.GRAFT_TICKS, GRAFT_COUNT_MIN, GRAFT_DONE_MESSAGE read.

        Methodology:
            1. Find the next unit by the group name. With none, the count
               halts.
            2. Re-arm the wait and move the counters BEFORE the graft. The
               graft sends the inventory, and the pop-up that it marks must
               read the new count.
            3. Graft. The done line of a count of more than one follows the
               graft line of its last unit.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 11/09/2026
        """
        item = graft_service.next_unit(owner, self.ndb.sample_name or "")

        if item is None:
            self.end(END_OUT)
            return

        self.ndb.ticks_until_graft = max(0, aug_const.GRAFT_TICKS - 1)
        self.ndb.remaining -= 1
        self.ndb.grafted += 1

        try:
            graft_service.graft(owner, item)
        except Exception:
            logger.log_trace()
            self.end(END_GONE)
            return

        self.dispatch(states.ActivityEvent.ACTION_RESOLVED)

        is_last = self.ndb.remaining <= 0
        is_count = (self.ndb.total or 0) > aug_const.GRAFT_COUNT_MIN

        if is_last and is_count:
            owner.msg((aug_const.GRAFT_DONE_MESSAGE.format(
                name=self.ndb.display, grafted=self.ndb.grafted,
                total=self.ndb.total), _MSG_PROGRESSION))


# ─── Public routines ─────────────────────────────────────────────────────────

def get_graft_handler(character):
    """The live graft channel of a character, or None."""
    handler = get_handler_for(character, GraftHandler)

    return handler


def start_grafting(character, name: str, display: str, count: int) -> None:
    """
    Purpose: Queue a count of one sample, and start the channel if needed.

    Entry:
        character is a Character that carries at least one unit.
        name is the group name of the sample.
        display is the name that the lines show.
        count is at least GRAFT_COUNT_MIN, clamped to the units carried.

    Exit/Returns:
        No conditions.

    Module Globals:
        aug_const.GRAFT_BEGIN_MESSAGE, GRAFT_COUNT_MIN read.

    Methodology:
        1. Announce a count of more than one BEFORE the first graft. Then
           the log reads in order, the lesson of craft_batch.start_batch.
        2. Find or create the channel, and queue the count on it.
        3. Mark an open pop-up out of date. A queue on a waiting channel
           moves no item, and the status must show the count.

    Notes/References:
        ensure_handler arms the script and registers it with the engine.

    Author: Nick Hobar
    Creation date: 11/09/2026
    """
    if count > aug_const.GRAFT_COUNT_MIN:
        character.msg((aug_const.GRAFT_BEGIN_MESSAGE.format(
            name=display, count=count), _MSG_PROGRESSION))

    handler = ensure_handler(character, GraftHandler)
    handler.begin(name, display, count)

    _refresh_popup(character)


def stop_grafting(character) -> bool:
    """
    Purpose: End the running count of a character, on `graft stop`.

    Entry:
        character is any Character.

    Exit/Returns:
        Returns True when a count ran. Sends one line on every exit.

    Module Globals:
        aug_const.GRAFT_STOP_MESSAGE, GRAFT_NOTHING_TO_STOP_MESSAGE read.

    Methodology:
        The channel keeps its wait (GraftHandler.halt), so a stop and a new
        command cannot cut the pace.

    Notes/References:
        The Stop button of the Locus pop-up sends GRAFT_STOP_COMMAND.

    Author: Nick Hobar
    Creation date: 11/09/2026
    """
    handler = get_graft_handler(character)
    report = None

    if handler is not None:
        handler.init_runtime_state()
        report = handler.halt()

    if report is None:
        character.msg((aug_const.GRAFT_NOTHING_TO_STOP_MESSAGE, _MSG_PROGRESSION))
        return False

    character.msg((aug_const.GRAFT_STOP_MESSAGE.format(**report), _MSG_PROGRESSION))
    _refresh_popup(character)

    return True


def channel_report(character):
    """The running count of a character as {name, grafted, total}, or None.
    The Locus pop-up reads it for its status line and its Stop button."""
    handler = get_graft_handler(character)

    if handler is None:
        return None

    handler.init_runtime_state()
    report = handler.report()

    return report


def running_sample(character) -> str:
    """The group name of the sample that a running count grafts, or "".
    The inventory pane reads it to put Stop on the row of that sample. A
    channel that only waits runs no count, and gives ""."""
    handler = get_graft_handler(character)

    if handler is None:
        return ""

    handler.init_runtime_state()
    report = handler.report()

    if report is None:
        return ""

    return str(handler.ndb.sample_name or "")


def end_grafting(character) -> None:
    """End the channel of a character at once, with no line. For a test
    teardown, and for a caller that takes the grafter out of the world."""
    handler = get_graft_handler(character)

    if handler is not None:
        handler.end(END_GONE)
