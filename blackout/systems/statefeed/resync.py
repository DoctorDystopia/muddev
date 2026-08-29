"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/07/2026
Description: The full-state snapshot — what "everything, from scratch" means.

             Two callers need it and must agree on it: the subscribe inputfunc
             (a client just connected and knows nothing) and
             ServerSession.at_sync (a reload just wiped every scrap of ndb the
             feed had). Keeping the definition here rather than in either
             caller is what stops those two paths from drifting into sending
             subtly different worlds.

             This is the "list" half of the list-then-delta pattern that both
             Aardwolf and the IRE games use across their whole GMCP surface:
             full state once, deltas thereafter. Every send here is forced past
             the rate caps, because a resync that gets dropped leaves a client
             permanently stale rather than a beat behind.
"""

from evennia.utils import logger

from . import events, mapexport
from .emit import emit


# ─── Private helper routines ─────────────────────────────────────────────────

def _send_map(observer) -> int:
    """Push every Z-level's grid to the observer, chunk by chunk."""
    chunks = mapexport.build_all_map_chunks()
    sent = 0

    for chunk in chunks:
        reached = emit(observer, chunk, force=True)
        sent += reached

    return sent


def _send_room(observer) -> int:
    """Push the observer's current room and its contents.

    Delegates to the same routines the ordinary arrival path uses, forced past
    the rate caps. Rebuilding the payloads here instead would give the game two
    definitions of "what a room looks like" that agree only until one is
    edited.
    """
    sent = events.emit_room_info(observer, force=True)
    sent += events.emit_room_contents(observer, force=True)

    return sent


def _send_self(observer) -> int:
    """Push the observer's own avatar, vitals and status.

    Delegates to the same emitters the live paths use, forced past the rate
    caps -- the choice _send_room already makes, for the reason given there.
    Vitals and status were assembled here by hand until 08/28/2026, which made
    this the second definition of both payloads and the only one that ran: no
    live emitter for char_status existed at all, so the levels a client drew
    were the ones it had at login for as long as it stayed connected.

    The avatar goes first, and it is the only ordering here that matters: it
    is the observer's identity, and vitals arriving before it describe a
    character the client cannot yet draw.
    """
    sent = events.emit_avatar(observer, force=True)
    sent += events.emit_vitals(observer, force=True)
    sent += events.emit_status(observer, force=True)

    return sent


# ─── Public routines ─────────────────────────────────────────────────────────

def send_full_state(observer) -> int:
    """
    Purpose: Push everything a graphical client needs to draw the world from
    nothing.

    Entry:
        observer - the puppeted Character, or None (a no-op, which is the
                   normal case for a session that has subscribed before
                   puppeting anything).

    Exit/Returns:
        Returns the total number of sends performed. Zero is normal and not an
        error: it means nothing on this observer was subscribed.

    Module Globals:
        None.

    Methodology:
        Map first, then room, then self. That order is not cosmetic -- a client
        that receives room_info before it has the grid has nowhere to put the
        highlight, and would either buffer or draw a floating tile.

        The dossier, the skill roster, the quest log and the inventory go last,
        and are the only sends here that can decline to happen: all four
        pre-check the subscription because building them is expensive -- the
        summary reads every handler on the character, the roster walks four
        unlock registries once per skill, the quest log walks every active
        step's objectives, and the inventory syncs the grid and walks every
        item's tags. Everything above them is cheap enough to build
        unconditionally.

        Wrapped, like every other feed path. at_sync runs on every single
        session sync, including during server startup; a failure here must
        never be able to stop a session connecting.

    Notes/References:
        Every send is forced past the rate caps. See the module docstring.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    if observer is None:
        return 0

    try:
        sent = _send_map(observer)
        sent += _send_room(observer)
        sent += _send_self(observer)
        sent += events.emit_summary(observer, force=True)
        sent += events.emit_skills(observer, force=True)
        sent += events.emit_quests(observer, force=True)
        sent += events.emit_inventory(observer, force=True)

        return sent
    except Exception:
        logger.log_trace()
        return 0
