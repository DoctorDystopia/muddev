"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The rig pop-up (DESIGN-0015, section 6.6). The sockets of the
             body in one grid, and every known augment in a second. Each
             cell carries whole commands: `socket <augment> <socket>` on an
             augment, `unsocket <socket>` on a filled socket. A telnet
             player types the same lines.

             IT MOVES NOTHING. The commands do the work, and the sockets
             module sends the pop-up again after each write.

             NOT ROOM-BOUND. The anchor is the character. A socket swap
             happens anywhere, out of combat (Nick, 10/30/2026), so the
             pop-up stays open while the player walks.

             THE DRAG (11/09/2026). An augment cell and a filled socket
             carry a drag key. An open socket and an augment cell carry a
             drop table: drag key -> whole command. A drop on a socket
             sends `socket/swap <augment> <socket>` for each augment that
             fits it. A filled socket that drops on any augment cell sends
             `unsocket <socket>` (Nick, 11/09/2026). The table names no
             augment that does not fit, so the client refuses that drop
             with no rule of its own.
"""

from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import detail as augment_detail
from systems.gameplay.augmentation import pool
from systems.gameplay.augmentation import sockets
from systems.gameplay.augmentation.registry import AUGMENT_REGISTRY, augments_in_order
from systems.interface.popups import constants as popup_const
from systems.interface.statefeed import constants as feed_const

from .base_popup import BasePopup, grid


# ─── Public constant definitions ─────────────────────────────────────────────

RIG_POPUP_KEY: str = "rig"

# The two grids. The keys are stable names that a client test can find a
# grid by.
SOCKETS_GRID_KEY: str = "sockets"
SOCKETS_GRID_TITLE: str = "Sockets"
AUGMENTS_GRID_KEY: str = "augments"
AUGMENTS_GRID_TITLE: str = "Augments"

# Between the lines of a tooltip.
INFO_SEPARATOR: str = "\n"

# No object stands behind a cell, so every row is id 0 with the generic
# look. The client draws the generic card.
_NO_OBJECT_ID: int = 0
_ONE: int = 1


# ─── Private helper routines ─────────────────────────────────────────────────

def _row(slot: int, name: str, actions: list, detail: str, enabled: bool,
         info: str) -> dict:
    """One cell, in the shape that base_popup.item_row gives."""
    return {
        "id": _NO_OBJECT_ID,
        "slot": int(slot),
        "name": str(name),
        "asset": feed_const.ASSET_KEY_GENERIC,
        "family": feed_const.ITEM_FAMILY_GENERIC,
        "quantity": _ONE,
        "stackable": False,
        "equip_slot": "",
        "actions": actions,
        "detail": str(detail),
        "enabled": bool(enabled),
        "info": str(info),
    }


def _unsocket_action(socket_key: str) -> dict:
    """The one action of a filled socket."""
    return {
        "label": aug_const.RIG_UNSOCKET_ACTION_LABEL,
        "command": aug_const.UNSOCKET_TEMPLATE.format(socket=socket_key),
    }


def _socket_action(augment, socket_key: str) -> dict:
    """One `socket` action of an augment, for one socket."""
    label = aug_const.RIG_SOCKET_ACTION_LABEL.format(
        socket=aug_const.SOCKET_NAMES[socket_key])

    return {
        "label": label,
        "command": aug_const.SOCKET_TEMPLATE.format(name=augment.name, socket=socket_key),
    }


def _socket_drag_key(socket_key: str) -> str:
    """The drag key of a filled socket."""
    return aug_const.RIG_DRAG_SOCKET_KEY.format(key=socket_key)


def _augment_drag_key(augment_key: str) -> str:
    """The drag key of an augment cell."""
    return aug_const.RIG_DRAG_AUGMENT_KEY.format(key=augment_key)


def _swap_command(augment, socket_key: str) -> str:
    """The line that a drop of one augment on one socket sends."""
    return aug_const.SOCKET_SWAP_TEMPLATE.format(name=augment.name, socket=socket_key)


def _socket_drops(target: str, held: dict) -> dict:
    """
    The drop table of one open socket: drag key -> whole command.

    Each augment cell that fits the socket, and each OTHER filled socket
    whose augment fits it. The augment that already sits there gets no
    entry, so a drop of a socket on itself sends nothing.
    """
    drops = {}

    for augment in augments_in_order():
        if target in augment.sockets and held.get(target) != augment.key:
            drops[_augment_drag_key(augment.key)] = _swap_command(augment, target)

    for source, augment_key in held.items():
        augment = AUGMENT_REGISTRY[augment_key]

        if source != target and target in augment.sockets:
            drops[_socket_drag_key(source)] = _swap_command(augment, target)

    return drops


def _augment_drops(held: dict) -> dict:
    """The drop table of an augment cell: a filled socket that drops here
    leaves the rig."""
    return {
        _socket_drag_key(socket_key): aug_const.UNSOCKET_TEMPLATE.format(socket=socket_key)
        for socket_key in held
    }


def _socket_row(slot: int, socket_key: str, held: dict, opened: list, level: int) -> dict:
    """The cell of one socket, with the socket key as its place on the doll.
    An open socket takes a drop. A filled socket drags."""
    row = _socket_cell(slot, socket_key, held, opened, level)
    row[popup_const.ROW_PLACE_FIELD] = socket_key

    if socket_key in opened:
        row[popup_const.ROW_DROPS_FIELD] = _socket_drops(socket_key, held)

    if socket_key in held:
        row[popup_const.ROW_DRAG_KEY_FIELD] = _socket_drag_key(socket_key)

    return row


def _socket_cell(slot: int, socket_key: str, held: dict, opened: list, level: int) -> dict:
    """The cell of one socket: the augment in it, empty, or locked."""
    label = aug_const.SOCKET_NAMES[socket_key]

    if socket_key not in opened:
        needed = sockets.unlock_level(socket_key)
        detail = aug_const.RIG_LOCKED_DETAIL.format(level=needed)

        return _row(slot, label, [], detail, False, detail)

    augment_key = held.get(socket_key)

    if augment_key is None:
        name = aug_const.RIG_EMPTY_NAME.format(socket=label)

        return _row(slot, name, [], aug_const.RIG_EMPTY_DETAIL, True, "")

    augment = AUGMENT_REGISTRY[augment_key]
    info = INFO_SEPARATOR.join(augment_detail.catalogue_tip(augment, level))

    return _row(slot, augment.name, [_unsocket_action(socket_key)], label, True, info)


def _augment_row(slot: int, augment, holder, held: dict, opened: list, level: int) -> dict:
    """
    The cell of one augment: where it sits, or where it can go.

    A locked augment gives the short form of a locked socket, "Augmentation
    20". The full sentence of `can_activate` names the augment again, and a
    cell already shows the name. The client cuts a detail line at the width of
    a slot (11/09/2026).
    """
    in_socket = sockets.socket_of(holder, augment.key)
    allowed, _reason = augment.can_activate(holder)
    info = INFO_SEPARATOR.join(augment_detail.catalogue_tip(augment, level))
    actions = []

    for socket_key in augment.sockets:
        if socket_key in opened and socket_key not in held:
            actions.append(_socket_action(augment, socket_key))

    if in_socket:
        actions.insert(0, _unsocket_action(in_socket))
        detail = aug_const.RIG_IN_SOCKET_DETAIL.format(
            socket=aug_const.SOCKET_NAMES[in_socket])
    elif not allowed:
        detail = aug_const.RIG_LOCKED_DETAIL.format(level=augment.unlock_level)
    else:
        detail = aug_const.RIG_FITS_DETAIL.format(fits=augment.socket_labels())

    row = _row(slot, augment.name, actions, detail, allowed or bool(in_socket), info)
    row[popup_const.ROW_DRAG_KEY_FIELD] = _augment_drag_key(augment.key)
    row[popup_const.ROW_DROPS_FIELD] = _augment_drops(held)

    return row


# ─── Public classes ──────────────────────────────────────────────────────────

class RigPopup(BasePopup):
    """
    Purpose: Show the rig of one character: the sockets and the catalogue.

    Entry:
        The anchor is the character itself.

    Exit/Returns:
        No conditions.

    Module Globals:
        RIG_POPUP_KEY read.

    Methodology:
        Every fact comes from the sockets module and the registry, the same
        reads that `rig` prints as text. Thus, the pop-up and the text
        cannot describe the rig differently.

    Notes/References:
        The sockets module sends the pop-up again on each write.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """

    key = RIG_POPUP_KEY
    title = aug_const.RIG_TITLE
    room_bound = False
    uses_quantity = False

    def anchor_is_usable(self, caller, anchor) -> bool:
        """The anchor is the caller, and the caller still exists."""
        if anchor is None or getattr(anchor, "pk", None) is None:
            return False

        return anchor == caller

    def status(self, caller, anchor) -> str:
        """How many sockets are open, and the level."""
        opened = sockets.open_sockets(caller)

        return aug_const.RIG_STATUS.format(
            open=len(opened), total=len(aug_const.SOCKETS), level=pool.level(caller))

    def grids(self, caller, anchor, mode) -> list:
        """
        Purpose: The sockets grid and the augments grid.

        Entry:
            caller is the character.

        Exit/Returns:
            Returns two grids. The sockets grid has one cell for each
            socket, in rig order, locked ones dim. The augments grid has
            one cell for each augment, in registry order.

        Module Globals:
            SOCKETS_GRID_*, AUGMENTS_GRID_* read.

        Methodology:
            The level, the assignments, and the open sockets are read one
            time. Each cell is built from them.

        Notes/References:
            The sockets grid names the rig layout, and each socket cell
            names its socket as its place. The client draws the sockets
            as a body doll, the shape of the paper doll (11/09/2026).
            Where each socket sits is a client fact.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        level = pool.level(caller)
        held = sockets.assignments(caller)
        opened = sockets.open_sockets(caller)

        socket_rows = [
            _socket_row(slot, socket_key, held, opened, level)
            for slot, socket_key in enumerate(aug_const.SOCKETS)
        ]
        augment_rows = [
            _augment_row(slot, augment, caller, held, opened, level)
            for slot, augment in enumerate(augments_in_order())
        ]
        socket_grid = grid(SOCKETS_GRID_KEY, SOCKETS_GRID_TITLE, len(socket_rows), socket_rows)
        socket_grid[popup_const.GRID_LAYOUT_FIELD] = popup_const.POPUP_LAYOUT_RIG
        augment_grid = grid(AUGMENTS_GRID_KEY, AUGMENTS_GRID_TITLE, len(augment_rows), augment_rows)

        return [socket_grid, augment_grid]
