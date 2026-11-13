"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The rig of one character (DESIGN-0015, Phase 5): the eight
             sockets of the body, and the augment in each. The rail shows
             the socketed augments only, and `aug set` lights them. A
             socket swap happens anywhere, out of combat (Nick,
             10/30/2026).

             This module is the one writer of SOCKETS_ATTR, a dict of
             socket key to augment key. Each write reaches the rail through
             refresh_abilities, and the open rig pop-up through the pop-up
             service. An unsocket puts the augment out if it burns.

             The level opens the sockets, through SOCKET_UNLOCK_LEVELS. A
             socket that closes again (a staff level cut) keeps its entry
             in the dict, and the readers treat the entry as absent until
             the socket opens again. Thus, nothing is lost, and the rail
             shows what the level allows.
"""

from evennia.utils import logger

from . import constants as aug_const
from . import pool
from .registry import AUGMENT_REGISTRY, augments_in_order


# ─── Private helper routines ─────────────────────────────────────────────────

def _stored(holder) -> dict:
    """The stored dict, as a copy. Empty for a holder with no rig yet."""
    attributes = getattr(holder, "attributes", None)

    if attributes is None:
        return {}

    stored = attributes.get(aug_const.SOCKETS_ATTR, default=None)

    if not stored:
        return {}

    return dict(stored)


def _write(holder, rig: dict) -> None:
    """Store the rig and tell each reader. The one write of SOCKETS_ATTR."""
    holder.attributes.add(aug_const.SOCKETS_ATTR, dict(rig))

    _publish(holder)


def _publish(holder) -> None:
    """Mark the rail stale, and send the rig pop-up again if it is open.
    Never raises: a feed send must never undo the write."""
    from systems.interface.popups import service as popup_service
    from systems.interface.statefeed import events as feed

    try:
        feed.refresh_abilities(holder)
        popup_service.publish_if_open(holder)
    except Exception as exc:
        logger.log_err(f"sockets._publish: {holder} feed send failed: {exc!r}")


def _in_combat(holder) -> bool:
    """Whether the holder fights now. A holder with no combat mixin does not."""
    return bool(getattr(holder, "in_combat", False))


def _label(socket_key: str) -> str:
    """The label of one socket."""
    return aug_const.SOCKET_NAMES.get(socket_key, socket_key)


def _put_out_if_lit(holder, augment_key: str) -> None:
    """Put an augment out when it burns, as an unsocket must."""
    from .handler import get_augment_handler_for

    handler = get_augment_handler_for(holder)

    if handler is None:
        return

    handler.put_out(augment_key)

    if not handler.lit_augments():
        handler.stop_handler()


def _place_refusal(holder, augment, socket_key: str) -> str:
    """The reason that no augment change may happen, or "". A fight, a
    closed socket, and a socket that the augment does not fit refuse."""
    if _in_combat(holder):
        return aug_const.SOCKET_IN_COMBAT_MESSAGE

    label = _label(socket_key)
    needed = unlock_level(socket_key)

    if needed > pool.level(holder):
        return aug_const.SOCKET_LOCKED_MESSAGE.format(socket=label, level=needed)

    if socket_key not in augment.sockets:
        return aug_const.SOCKET_NO_FIT_MESSAGE.format(
            name=augment.name, socket=label, fits=augment.socket_labels())

    return ""


def _take_out(rig: dict, augment_key: str) -> str:
    """Take an augment out of every socket of a rig dict. Returns the
    socket that it left, or "" when it sat in none."""
    left = ""

    for socket_key, held in list(rig.items()):
        if held == augment_key:
            rig.pop(socket_key)
            left = left or socket_key

    return left


def _rehome(holder, rig: dict, displaced, origin: str) -> str:
    """
    Find a new place for the augment that a swap pushed out of its socket.

    It moves to the socket that the new augment left, when that socket is
    open and it fits there. Else it leaves the rig and goes dark (Nick,
    11/09/2026). Returns the line that tells the player which one.
    """
    if origin and origin in displaced.sockets and origin in open_sockets(holder):
        rig[origin] = displaced.key

        return aug_const.SOCKET_SWAP_MOVED_MESSAGE.format(
            other=displaced.name, socket=_label(origin))

    _put_out_if_lit(holder, displaced.key)

    return aug_const.SOCKET_SWAP_OUT_MESSAGE.format(other=displaced.name)


# ─── Public routines ─────────────────────────────────────────────────────────

def socket_labels() -> str:
    """Every socket label, as one string for a usage line."""
    labels = [_label(key) for key in aug_const.SOCKETS]

    return aug_const.SOCKET_LIST_SEPARATOR.join(labels)


def find_socket(name: str) -> str:
    """
    Purpose: Resolve a typed socket name to a socket key.

    Entry:
        name is any string. May be empty.

    Exit/Returns:
        Returns the socket key, or "" for no match.

    Module Globals:
        aug_const.SOCKETS, SOCKET_NAMES read.

    Methodology:
        1. The key itself, with spaces as underscores, wins.
        2. Else the label, case-insensitive.
        3. Else one unique prefix of a label. Two matches give "".

    Notes/References:
        The shape of registry.find_augment.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    if not name:
        return ""

    needle = name.strip().lower()
    underscored = needle.replace(" ", "_")

    for key in aug_const.SOCKETS:
        if underscored == key or needle == _label(key).lower():
            return key

    prefix_matches = [key for key in aug_const.SOCKETS
                      if _label(key).lower().startswith(needle)]

    if len(prefix_matches) == 1:
        return prefix_matches[0]

    return ""


def unlock_level(socket_key: str) -> int:
    """The Augmentation level that opens one socket."""
    return int(aug_const.SOCKET_UNLOCK_LEVELS.get(socket_key, aug_const.NO_UNLOCK_LEVEL))


def open_sockets(holder) -> list:
    """The socket keys that the level of the holder opens, in rig order."""
    level = pool.level(holder)

    return [key for key in aug_const.SOCKETS if unlock_level(key) <= level]


def assignments(holder) -> dict:
    """
    Purpose: The augment in each OPEN socket of a holder.

    Entry:
        holder is any object. It may have no rig.

    Exit/Returns:
        Returns a dict of socket key to augment key, open sockets only, and
        only augments that the registry still knows.

    Module Globals:
        AUGMENT_REGISTRY read.

    Methodology:
        Filter the stored dict by the open sockets and the registry. A
        closed socket keeps its entry in the store, and this view hides
        it.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    opened = set(open_sockets(holder))
    view = {}

    for socket_key, augment_key in _stored(holder).items():
        if socket_key in opened and augment_key in AUGMENT_REGISTRY:
            view[socket_key] = augment_key

    return view


def socket_of(holder, augment_key: str) -> str:
    """The open socket that holds an augment, or ""."""
    for socket_key, held in assignments(holder).items():
        if held == augment_key:
            return socket_key

    return ""


def is_socketed(holder, augment_key: str) -> bool:
    """Whether an augment sits in an open socket of the holder."""
    return bool(socket_of(holder, augment_key))


def socketed_augments(holder) -> list:
    """The socketed augments of a holder, in the order of the registry."""
    held = set(assignments(holder).values())

    return [augment for augment in augments_in_order() if augment.key in held]


def place(holder, augment, socket_key: str, swap: bool = False) -> tuple:
    """
    Purpose: Put an augment into a socket.

    Entry:
        holder is the character.
        augment is an instance of AUGMENT_REGISTRY.
        socket_key is a key of aug_const.SOCKETS.
        swap is True for `socket/swap`: take a socket that another augment
            holds.

    Exit/Returns:
        Returns (True, message) on a write. Returns (False, reason)
        otherwise, with the reason as player-facing text. Nothing changes
        on a refusal.

    Module Globals:
        aug_const.SOCKET_* read.

    Methodology:
        1. Refuse in a fight, a closed socket, and a socket that the
           augment does not fit.
        2. Say so when the augment already sits there.
        3. Without swap, refuse a socket that another augment holds. The
           player unsockets first.
        4. Take the augment out of any other socket, and put it in.
        5. With swap, find a new place for the held augment: the socket
           that the new augment left, or out of the rig.
        6. Write one time.

    Notes/References:
        The level gate of the augment is not read here. A locked augment
        may sit in the rig, and the rail shows it locked until the level
        comes. Thus, a build survives a level cut. A drop on a socket in
        the rig pop-up sends the swap form (11/09/2026).

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    refusal = _place_refusal(holder, augment, socket_key)

    if refusal:
        return False, refusal

    label = _label(socket_key)
    rig = _stored(holder)
    held = rig.get(socket_key)

    if held == augment.key:
        return False, aug_const.SOCKET_SAME_MESSAGE.format(name=augment.name, socket=label)

    displaced = AUGMENT_REGISTRY.get(held) if held is not None else None

    if displaced is not None and not swap:
        return False, aug_const.SOCKET_TAKEN_MESSAGE.format(socket=label, other=displaced.name)

    origin = _take_out(rig, augment.key)
    rig[socket_key] = augment.key
    lines = [aug_const.SOCKET_DONE_MESSAGE.format(name=augment.name, socket=label)]

    if displaced is not None:
        lines.append(_rehome(holder, rig, displaced, origin))

    _write(holder, rig)

    return True, aug_const.SOCKET_MESSAGE_JOIN.join(lines)


def remove(holder, socket_key: str) -> tuple:
    """
    Purpose: Take the augment out of a socket, and put it out if it burns.

    Entry:
        holder is the character.
        socket_key is a key of aug_const.SOCKETS.

    Exit/Returns:
        Returns (True, message) on a write. Returns (False, reason) in a
        fight, or for an empty socket.

    Module Globals:
        aug_const.UNSOCKET_* read.

    Methodology:
        1. Refuse in a fight.
        2. Say so for an empty socket. A closed socket with an entry counts
           as held here, so a player can clear it.
        3. Pop the entry, put the augment out, and write.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    if _in_combat(holder):
        return False, aug_const.SOCKET_IN_COMBAT_MESSAGE

    label = _label(socket_key)
    rig = _stored(holder)
    held = rig.pop(socket_key, None)

    if held is None:
        return False, aug_const.UNSOCKET_EMPTY_MESSAGE.format(socket=label)

    augment = AUGMENT_REGISTRY.get(held)
    name = augment.name if augment is not None else str(held)

    _put_out_if_lit(holder, str(held))
    _write(holder, rig)

    return True, aug_const.UNSOCKET_DONE_MESSAGE.format(name=name, socket=label)
