"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Summary panel: what the character has working somewhere it is not
             standing -- meat in a curing chamber today, whatever the next
             deferred stage is tomorrow.
"""

from evennia.utils import logger

from systems.gameplay.crafting import crafting_service

from .. import constants as const
from .base_panel import BasePanel


# Public constant definitions

PANEL_TITLE = "Processing"


class ProcessingPanel(BasePanel):
    """
    Purpose: Every deferred stage the character has something sitting in.

    Entry:
        character is a Character. It need not have any deferred handler at all.

    Exit/Returns:
        Not applicable -- see render / data.

    Module Globals:
        None.

    Methodology:
        THE ANSWER TO "WHY CAN I NOT START ANOTHER CURE", asked away from the
        chamber. Curing is the first stage in the game whose output arrives
        later, which makes it the first whose state a player carries around
        with them -- a full chamber three rooms away is a fact about the
        character, and the dossier is where facts about the character live.

        The band draws NOTHING when nothing is in progress, which is most of
        the time for most players. An idle stage is not news: a row reading
        "Curing slots: 0/1" on a screen every player reads would be noise on
        every dossier in the game to spare one player one walk. render()
        returning [] takes the heading with it, which is service.py's own rule
        for an empty panel.

        It names no stage and counts no slot. The lines are the HANDLER's,
        through the protocol BlackoutRecipe.deferred_handler documents, and the
        roster of handlers is the recipe registry's -- so a second deferred
        stage appears on this screen the day a recipe declares one, with no
        edit here and none in a client. That is the same promise the dossier
        makes about panels generally: a client iterates them and never names
        one.

        Private, the default. What is in your chamber is no stranger's
        business, and `public = True` is a decision about a band rather than
        something it should inherit.

    Notes/References:
        systems/gameplay/curing/handler.py owns the slot state and its wording.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """

    key = "processing"
    title = PANEL_TITLE
    order = const.PANEL_ORDER_PROCESSING
    public = False


    @classmethod
    def _active_stages(cls, character: object) -> list:
        """
        Purpose: Every deferred stage this character has something in.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a list of (stage_name, handler, entries) tuples, skipping
            any stage holding nothing. Empty when nothing is in progress.

        Module Globals:
            None.

        Methodology:
            One read of pending() per stage, passed on to both output methods,
            so the text band and the wire payload describe the same slots from
            the same read rather than asking twice and possibly straddling a
            deadline.

            Guarded, because a panel must never be the thing that breaks the
            dossier -- service.py degrades one bad band to "(unavailable)", and
            a stage whose handler raised is better reported as no stage than as
            a screen that will not draw.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        try:
            stages = crafting_service.get_deferred_handlers(character)
        except Exception as exc:
            logger.log_err(f"ProcessingPanel._active_stages failed: {exc!r}")

            return []

        active = []

        for stage_name, handler in stages:
            entries = handler.pending()

            if not entries:
                continue

            active.append((stage_name, handler, entries))

        return active


    @classmethod
    def render(cls, character: object) -> list:
        """
        Purpose: Render the processing band.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a list of display lines, empty when nothing is in progress.

        Module Globals:
            None.

        Methodology:
            Prints what the handler rendered. The block is the same one the
            chamber's craft menu shows, which is the point: a player who read
            "2m 14s remaining" on the dossier and then walked to the chamber
            must not be met by a differently worded version of the same fact.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        lines = []

        for _stage_name, handler, _entries in cls._active_stages(character):
            lines.extend(handler.status_lines())

        return lines


    @classmethod
    def data(cls, character: object) -> dict:
        """
        Purpose: Structured form of the processing band.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns {"stages": [...]}, one entry per stage holding something,
            each carrying its machine name, its slot counts and its slots.

        Module Globals:
            None.

        Methodology:
            STRUCTURED, NOT RENDERED, the argument CHANNEL_CHAR_QUESTS makes at
            length: a client given a deadline in seconds can run its own
            countdown between updates, and one given "2m 14s remaining" can
            only print a number that is already wrong.

            `stage` is the handler's attribute name rather than a display word,
            for the reason every other machine token in the feed is one -- a
            client branches on it, and a copy edit to a sentence must not
            change a state name.

            The rendered block deliberately does NOT ride along beside it.
            status_lines() carries Evennia colour markup, which is telnet's
            business and would arrive at a graphical client as escape codes it
            has to strip before it can draw anything; and a payload carrying
            both a number and a sentence about that number is one where the two
            can disagree.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        stages = []

        for stage_name, handler, entries in cls._active_stages(character):
            stages.append({
                "stage": stage_name,
                "slots_used": int(handler.slot_used()),
                "slots_total": int(handler.slot_total()),
                "ready": int(handler.ready_count()),
                "slots": [cls._slot_data(entry) for entry in entries],
            })

        payload = {"stages": stages}

        return payload


    @classmethod
    def _slot_data(cls, entry: dict) -> dict:
        """One pending() entry as plain JSON-safe values."""
        slot = {
            "item": str(entry["item_name"]),
            "state": str(entry["state"]),
            "remaining": float(entry["remaining"]),
        }

        return slot
