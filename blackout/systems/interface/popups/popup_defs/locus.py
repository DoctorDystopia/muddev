"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/09/2026
Description: The Augmentation Locus pop-up: every sample in one grid, and
             the quantity row under it. The model is the crafting pop-up at
             the anvil (crafting.py), and the OSRS altar is the pace.

             EVERY SAMPLE SHOWS (Nick, 11/09/2026). A sample that the player
             does not carry is dim, as a recipe that the player cannot make
             is dim at the anvil. The grid tells what the skill takes. A
             click on a dim slot sends the graft anyway, and the server
             answers that the player carries none.

             IT GRAFTS NOTHING. A sample slot carries
             `graft <sample key> <count>`, the line that a telnet player
             types anywhere. The graft channel (graft_channel.py) paces the
             count, one graft each GRAFT_TICKS ticks. The Stop button sends
             `graft stop`.

             ROOM-BOUND. The anchor is the Locus. A walk closes the pop-up,
             and the walk also ends the channel.
"""

from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import graft as graft_service
from systems.gameplay.augmentation import graft_channel
from systems.interface.statefeed import constants as feed_const

from .base_popup import (
    BasePopup,
    definition_row,
    grid,
    quantity_actions,
)


# ─── Public constant definitions ─────────────────────────────────────────────

LOCUS_POPUP_KEY: str = "locus"

# The grid. The key is a stable name that a client test can find it by.
SAMPLES_GRID_KEY: str = "samples"

# A sample slot names its sample by the ItemDef KEY, which holds no space
# and never collides. graft.sample_def_for reads the key first.
GRAFT_TEMPLATE: str = (
    f"{aug_const.GRAFT_COMMAND_KEY} {{sample}} {feed_const.ACTION_AMOUNT_PLACEHOLDER}")

# Between the lines of a tooltip.
INFO_SEPARATOR: str = "\n"


# ─── Private helper routines ─────────────────────────────────────────────────

def _xp_here(caller, item_def, units: int) -> int:
    """The XP that one graft of this sample pays at the Locus. A carried
    unit decides, because the graft reads the attribute of the unit. With
    none carried, the ItemDef decides."""
    unit = None

    if units > 0:
        unit = graft_service.next_unit(caller, item_def.name)

    if unit is None:
        xp = graft_service.def_xp(item_def, at_locus=True)
    else:
        xp = graft_service.xp_for(unit, at_locus=True)

    return xp


def _sample_info(item_def, units: int, xp: int) -> str:
    """The tooltip of one sample: its text, the count carried, and the two
    rates."""
    base = graft_service.def_xp(item_def, at_locus=False)
    lines = [
        str(item_def.desc),
        aug_const.LOCUS_CARRIED_INFO.format(count=units),
        aug_const.LOCUS_RATE_INFO.format(xp=xp, base=base),
    ]

    return INFO_SEPARATOR.join(line for line in lines if line)


def _sample_row(caller, item_def, index: int, mode) -> dict:
    """
    Purpose: Render the slot of one sample.

    Entry:
        caller   - the grafting Character.
        item_def - a sample ItemDef (graft.sample_defs).
        index    - its position in the grid.
        mode     - the active quantity mode.

    Exit/Returns:
        Returns one row dict in the shape of definition_row.

    Module Globals:
        GRAFT_TEMPLATE read.

    Methodology:
        1. Count the units carried. That bounds X and All, and the corner
           of the slot draws it.
        2. With no unit, draw the slot dim and keep one Graft action.
        3. Show the XP of one graft here under the name, and both rates on
           the tooltip.

    Notes/References:
        graft.units_carried is what the command counts too, so a lit slot
        starts a graft.

    Author: Nick Hobar
    Creation date: 11/09/2026
    """
    units = graft_service.units_carried(caller, item_def.name)
    xp = _xp_here(caller, item_def, units)
    template = GRAFT_TEMPLATE.replace("{sample}", item_def.key)
    actions = quantity_actions(aug_const.LOCUS_GRAFT_LABEL, template, mode,
                               max(units, aug_const.GRAFT_COUNT_MIN),
                               aug_const.LOCUS_GRAFT_PROMPT)
    detail = aug_const.LOCUS_XP_DETAIL.format(xp=xp)
    info = _sample_info(item_def, units, xp)

    return definition_row(item_def, index, units, actions, name=item_def.name,
                          detail=detail, enabled=units > 0, info=info)


# ─── Public classes ──────────────────────────────────────────────────────────

class LocusPopup(BasePopup):
    """
    Purpose: Show every sample at an Augmentation Locus, with a count row.

    Entry:
        The anchor is the Locus, in the room of the caller.

    Exit/Returns:
        No conditions.

    Module Globals:
        LOCUS_POPUP_KEY read.

    Methodology:
        The rows come from graft.sample_defs, and the counts come from the
        graft module. The status and the Stop button read the graft
        channel. Thus, the pop-up, the command, and the channel read one
        fact each.

    Notes/References:
        Each graft sends the inventory, and emit_inventory marks this pop-up
        out of date. Thus, the counts and the status follow the channel.

    Author: Nick Hobar
    Creation date: 11/09/2026
    """

    key = LOCUS_POPUP_KEY
    title = aug_const.LOCUS_POPUP_TITLE
    room_bound = True
    uses_quantity = True

    def status(self, caller, anchor) -> str:
        """The running count, or the idle line."""
        report = graft_channel.channel_report(caller)

        if report is None:
            return aug_const.LOCUS_IDLE_STATUS

        status = aug_const.LOCUS_BUSY_STATUS.format(**report)

        return status

    def grids(self, caller, anchor, mode) -> list:
        """One grid: a slot for each sample in the game, in ITEM_DB order."""
        rows = []

        for item_def in graft_service.sample_defs():
            rows.append(_sample_row(caller, item_def, len(rows), mode))

        samples = grid(SAMPLES_GRID_KEY, aug_const.LOCUS_SAMPLES_TITLE, len(rows), rows)

        return [samples]

    def actions(self, caller, anchor) -> list:
        """Stop grafting, while a count runs."""
        report = graft_channel.channel_report(caller)

        if report is None:
            return []

        return [{"label": aug_const.LOCUS_STOP_LABEL,
                 "command": aug_const.GRAFT_STOP_COMMAND}]
