"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: The Exterminator task pop-up. The Task Writ opens it.

             The status line shows the task, the streak, and the points. A
             footer button skips the task. The pick cards show in a grid
             under the task, in this same pop-up (Nick, 10/06/2026).

             IT MOVES NOTHING. The skip button sends `task skip`, the line
             that a telnet player types. ExterminatorHandler does the work.

             NOT ROOM-BOUND. The anchor is the writ in the bag of the
             player, so the pop-up stays open while the player walks. It
             closes when the writ leaves the bag. DESIGN-0012, Phase 2.
"""

from systems.gameplay.exterminator import constants as ext_const
from systems.gameplay.exterminator.cards import card_views
from systems.interface.statefeed import constants as feed_const

from .base_popup import BasePopup, grid



# ─── Public constant definitions ─────────────────────────────────────────────

EXTERMINATOR_POPUP_KEY: str = "exterminator_task"
EXTERMINATOR_POPUP_TITLE: str = "Exterminator Task"  # TBD name

SKIP_ACTION_LABEL: str = "Skip task"

# Between the task line and the streak line in the one status line.
STATUS_SEPARATOR: str = "   "

# The grid of the pick cards. The key is a stable name that a client test
# can find the grid by.
CARDS_GRID_KEY: str = "cards"
CARDS_GRID_TITLE: str = "Pick a buff"  # TBD text
PICK_ACTION_LABEL: str = "Pick"

# Between the description and the warnings in the tooltip of a card.
CARD_INFO_SEPARATOR: str = "\n"



# ─── Private helper routines ─────────────────────────────────────────────────

def _card_row(view) -> dict:
    """
    One card as a grid row, in the shape that base_popup.item_row gives. No
    object stands behind a card, so `id` is 0, and the client draws the
    generic look. `rarity` is the key of the rarity. The client picks the
    colour of the card from it.
    """
    info_lines = [view.description] + list(view.warnings)

    return {
        "id": 0,
        "slot": view.number - 1,
        "name": view.name,
        "asset": feed_const.ASSET_KEY_GENERIC,
        "family": feed_const.ITEM_FAMILY_GENERIC,
        "quantity": 1,
        "stackable": False,
        "equip_slot": "",
        "actions": [{"label": PICK_ACTION_LABEL, "command": view.command}],
        "detail": view.rarity_name,
        "rarity": view.rarity,
        "enabled": True,
        "info": CARD_INFO_SEPARATOR.join(info_lines),
    }



# ─── Public classes ──────────────────────────────────────────────────────────

class ExterminatorPopup(BasePopup):
    """
    Purpose: Show one character's Exterminator task.

    Entry:
        The anchor is a Task Writ.

    Exit/Returns:
        No conditions.

    Module Globals:
        EXTERMINATOR_POPUP_KEY, EXTERMINATOR_POPUP_TITLE read.

    Methodology:
        Every fact comes from ExterminatorHandler.summary_lines, the same
        lines that `task` prints. Thus, the pop-up and the text cannot
        describe the task differently.

    Notes/References:
        The handler marks the pop-up stale on each write of the task.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """

    key = EXTERMINATOR_POPUP_KEY
    title = EXTERMINATOR_POPUP_TITLE
    room_bound = False
    uses_quantity = False

    def anchor_is_usable(self, caller, anchor) -> bool:
        """The writ still exists, and the caller carries it."""
        if anchor is None or getattr(anchor, "pk", None) is None:
            return False

        return anchor.location == caller

    def status(self, caller, anchor) -> str:
        """The task line and the streak line, as one line."""
        lines = caller.exterminator.summary_lines()

        return STATUS_SEPARATOR.join(lines)

    def grids(self, caller, anchor, mode) -> list:
        """
        Purpose: Show the cards of the open offer as one grid.

        Entry:
            caller has an `exterminator` handler.

        Exit/Returns:
            Returns [] when no offer is open. Else, one grid of card rows.

        Module Globals:
            CARDS_GRID_KEY, CARDS_GRID_TITLE, PICK_ACTION_LABEL read.

        Methodology:
            Each card is a row in the shape of an inventory slot, so the
            client draws it with the slot code that it has. The detail is
            the rarity. The tooltip holds the description and each conflict
            warning. The one action is `task pick <n>`.

        Notes/References:
            cards.card_views builds the views that `task` prints too.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        views = card_views(caller)

        if not views:
            return []

        rows = [_card_row(view) for view in views]

        return [grid(CARDS_GRID_KEY, CARDS_GRID_TITLE, len(rows), rows)]

    def actions(self, caller, anchor) -> list:
        """The skip button, while the caller has a task."""
        has_task = caller.exterminator.has_task()

        if not has_task:
            return []

        return [{"label": SKIP_ACTION_LABEL, "command": ext_const.TASK_SKIP_COMMAND}]
