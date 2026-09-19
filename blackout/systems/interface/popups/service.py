"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: The life of one pop-up: open it, keep it current, close it.

             THE CHARACTER HOLDS AT MOST ONE POP-UP. OSRS shows one interface
             in the game view at a time, and so does this: opening the bank
             while something else is open replaces it.

             WHO GETS ONE. A pop-up opens only for a character that a session
             watches through CHANNEL_CHAR_POPUP. Everyone else, telnet
             included, gets the EvMenu as before. The caller asks
             wants_popup() and picks. This module never starts a menu.

             WHERE IT LIVES. The open pop-up is an ndb pair {key, anchor}. It
             holds the anchor OBJECT, so a lookup is not needed at each build.
             The KEY names the definition, and the definition lives in code.
             No import path goes into a database row: see CLAUDE.md, "An import
             path belongs in the code, never in a database row".

             HOW IT STAYS CURRENT. Every change that a bank pop-up shows moves
             an item on or off the character, and every such move reaches
             statefeed.events.emit_inventory. That emitter marks the pop-up
             stale, and the buffer builds it one time after the last change.
             The pop-up needs no call beside each write.
"""

from evennia.utils import logger

from systems.interface.statefeed import constants as feed_const

from . import constants as popup_const


# ─── Private helper routines ─────────────────────────────────────────────────

def _registry():
    """Import the registry late. See registry.py on why it must be lazy."""
    from . import registry

    return registry


def _closed_snapshot() -> dict:
    """The snapshot of a character with nothing open."""
    return {
        "open": False,
        "key": "",
        "title": "",
        "status": "",
        "grids": [],
        "quantity": [],
        "actions": [],
        "text": "",
        "choices": [],
        "input": {},
        "timers": {},
        "close_command": "",
    }


def _open_pair(caller):
    """Return the stored {key, anchor} dict, or None."""
    stored = getattr(caller.ndb, popup_const.OPEN_POPUP_ATTR, None)

    if not isinstance(stored, dict):
        return None

    return stored


def _forget(caller) -> None:
    """Clear the stored pop-up. Leaves the send to the caller."""
    setattr(caller.ndb, popup_const.OPEN_POPUP_ATTR, None)


def _publish(caller) -> None:
    """Send the pop-up snapshot now. Never raises, like every feed call."""
    from systems.interface.statefeed import events as feed

    try:
        feed.emit_popup(caller)
    except Exception:
        logger.log_trace()


def _publish_inventory(caller) -> None:
    """Send the inventory pane again, because its row actions follow the open
    pop-up: Deposit leads while the vault is open. See carried_lens."""
    from systems.interface.statefeed import events as feed

    try:
        feed.emit_inventory(caller)
    except Exception:
        logger.log_trace()


def _mode_button(mode, active: bool) -> dict:
    """Render one fixed quantity button: 1, 5, 10 or All."""
    if mode == popup_const.QUANTITY_ALL:
        label = popup_const.QUANTITY_LABEL_ALL
    else:
        label = str(mode)

    command = popup_const.POPUP_QUANTITY_TEMPLATE.replace(
        feed_const.ACTION_AMOUNT_PLACEHOLDER, str(mode))

    return {"label": label, "command": command, "active": bool(active)}


def _custom_button(mode) -> dict:
    """
    Purpose: Render the X button, which asks for its amount.

    Entry:
        mode - the active quantity mode.

    Exit/Returns:
        Returns a prompted action dict with an `active` flag.

    Module Globals:
        popup_const.QUANTITY_* read.

    Methodology:
        X is active when the mode is a number that no fixed button shows. Its
        label then shows that number, as the OSRS X button does after a
        player sets it.

    Notes/References:
        The prompted shape is the one statefeed/inventory.py defines, so the
        client asks for the amount with the box it already has.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    from systems.interface.statefeed.inventory import _prompted_action

    custom = (mode != popup_const.QUANTITY_ALL
              and mode not in popup_const.QUANTITY_FIXED_MODES)
    label = str(mode) if custom else popup_const.QUANTITY_LABEL_X

    button = _prompted_action(
        label,
        popup_const.POPUP_QUANTITY_TEMPLATE,
        popup_const.QUANTITY_PROMPT,
        popup_const.QUANTITY_MAX_CUSTOM,
    )
    button["active"] = custom

    return button


def _quantity_buttons(mode) -> list:
    """Render the whole quantity row: 1, 5, 10, X, All."""
    buttons = []

    for fixed in popup_const.QUANTITY_FIXED_MODES:
        buttons.append(_mode_button(fixed, fixed == mode))

    buttons.append(_custom_button(mode))
    all_active = mode == popup_const.QUANTITY_ALL
    buttons.append(_mode_button(popup_const.QUANTITY_ALL, all_active))

    return buttons


def _parse_mode(raw: str):
    """Read a typed quantity mode. Returns an int, QUANTITY_ALL, or None."""
    text = (raw or "").strip().lower()

    if text == popup_const.QUANTITY_ALL:
        return popup_const.QUANTITY_ALL

    if not text.isdigit():
        return None

    amount = int(text)

    if amount < 1 or amount > popup_const.QUANTITY_MAX_CUSTOM:
        return None

    return amount


# ─── Public routines ─────────────────────────────────────────────────────────

def wants_popup(caller) -> bool:
    """Say whether any session of `caller` can draw a pop-up."""
    from systems.interface.statefeed import subscriptions

    return subscriptions.has_channel_subscribers(
        caller, feed_const.CHANNEL_CHAR_POPUP)


def is_open(caller) -> bool:
    """Say whether `caller` has a pop-up open."""
    return _open_pair(caller) is not None


def open_popup(caller, popup_key: str, anchor) -> bool:
    """
    Purpose: Open one pop-up for `caller` and send it.

    Entry:
        caller    - a puppeted Character.
        popup_key - a key in POPUP_REGISTRY.
        anchor    - the object that opened it, for example the terminal.

    Exit/Returns:
        Returns True when the pop-up opened. False for an unknown key or an
        anchor the definition refuses. Messages nothing.

    Module Globals:
        popup_const.OPEN_POPUP_ATTR written.

    Methodology:
        1. Find the definition. If there is none, refuse.
        2. If the anchor is not usable, refuse.
        3. Store the pair, replacing any pop-up already open, and send.

    Notes/References:
        The send is immediate, not a stale mark. The player just asked, and
        the text of the command arrives in the same reactor turn.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    popup = _registry().get_popup(popup_key)

    if popup is None:
        logger.log_err(f"[POPUP] No pop-up is registered as {popup_key!r}.")
        return False

    usable = popup.anchor_is_usable(caller, anchor)

    if not usable:
        return False

    stored = {
        popup_const.OPEN_KEY_FIELD: popup_key,
        popup_const.OPEN_ANCHOR_FIELD: anchor,
    }
    setattr(caller.ndb, popup_const.OPEN_POPUP_ATTR, stored)
    _publish(caller)
    _publish_inventory(caller)

    return True


def close_popup(caller) -> str:
    """
    Purpose: Close whatever pop-up `caller` has open, and send the closed
             state.

    Entry:
        caller - a puppeted Character.

    Exit/Returns:
        Returns the title of the pop-up that closed, or "" when nothing was
        open. Messages nothing.

    Module Globals:
        popup_const.OPEN_POPUP_ATTR written.

    Methodology:
        The closed state is a snapshot like any other, so a client that missed
        the close learns it from the next resync.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    pair = _open_pair(caller)

    if pair is None:
        return ""

    popup = _registry().get_popup(pair.get(popup_const.OPEN_KEY_FIELD, ""))
    # The CLASS title, not title_for: "You close the shop." reads right, and
    # "You close the shopkeeper." does not.
    title = popup.title if popup is not None else ""

    _forget(caller)
    _publish(caller)
    _publish_inventory(caller)

    return title


def close_if_left(caller) -> bool:
    """
    Purpose: Close a room-bound pop-up when its anchor is no longer here.

    Entry:
        caller - a Character that just moved.

    Exit/Returns:
        Returns True when a pop-up closed. Never raises.

    Module Globals:
        None.

    Methodology:
        Asks the definition, not the anchor's location directly, so a pop-up
        that is not room-bound stays open through the move.

    Notes/References:
        Called from Character.at_post_move, beside the room-bound EvMenu
        close. The two rules are the same rule.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    try:
        pair = _open_pair(caller)

        if pair is None:
            return False

        popup = _registry().get_popup(pair.get(popup_const.OPEN_KEY_FIELD, ""))
        anchor = pair.get(popup_const.OPEN_ANCHOR_FIELD)
        usable = popup is not None and popup.anchor_is_usable(caller, anchor)

        if usable:
            return False

        closed = close_popup(caller)

        return bool(closed)
    except Exception:
        logger.log_trace()
        return False


def refresh_anchor_viewers(anchor) -> int:
    """
    Purpose: Mark stale every open pop-up anchored to one object.

    Entry:
        anchor - the object a pop-up opens on, for example a shopkeep.

    Exit/Returns:
        Returns how many pop-ups it marked. Never raises.

    Module Globals:
        None.

    Methodology:
        Walk the anchor's room only. A room-bound pop-up closes when its
        viewer leaves the room, so every viewer stands there.

    Notes/References:
        For a fact of the anchor that no item move of the viewer reports: a
        shop's stock after another player buys, or a restock. emit_inventory
        covers the viewer's own trades.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    from systems.interface.statefeed import events as feed

    marked = 0

    try:
        room = getattr(anchor, "location", None)
        viewers = list(room.contents) if room is not None else []

        for viewer in viewers:
            pair = _open_pair(viewer)

            if pair is None or pair.get(popup_const.OPEN_ANCHOR_FIELD) != anchor:
                continue

            if feed.refresh_popup(viewer):
                marked += 1
    except Exception:
        logger.log_trace()

    return marked


def quantity_mode(caller, popup_key: str):
    """Return the stored quantity mode for one pop-up, or the default."""
    stored = caller.attributes.get(popup_const.QUANTITY_MODE_ATTR, default=None)

    if not stored:
        return popup_const.QUANTITY_DEFAULT_MODE

    mode = stored.get(popup_key, popup_const.QUANTITY_DEFAULT_MODE)
    parsed = _parse_mode(str(mode))

    if parsed is None:
        return popup_const.QUANTITY_DEFAULT_MODE

    return parsed


def set_quantity_mode(caller, raw: str) -> tuple:
    """
    Purpose: Set the quantity mode of the open pop-up from a typed argument.

    Entry:
        caller - a puppeted Character.
        raw    - "1", "5", "23", "all", or anything a player can type.

    Exit/Returns:
        Returns (succeeded, message). The message is plain text.

    Module Globals:
        popup_const.QUANTITY_MODE_ATTR read and written.

    Methodology:
        1. If nothing is open, refuse. A mode belongs to one pop-up.
        2. Parse the argument. If it is not a mode, refuse.
        3. Store it under the open pop-up's key, and send the new snapshot.

    Notes/References:
        The stored value is a plain dict of plain values, so a read gives
        back nothing that json.dumps cannot take.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    pair = _open_pair(caller)

    if pair is None:
        return False, popup_const.MSG_NOTHING_OPEN

    mode = _parse_mode(raw)

    if mode is None:
        message = popup_const.MSG_QUANTITY_BAD.format(
            maximum=popup_const.QUANTITY_MAX_CUSTOM)
        return False, message

    popup_key = pair.get(popup_const.OPEN_KEY_FIELD, "")
    stored = caller.attributes.get(popup_const.QUANTITY_MODE_ATTR, default=None)
    modes = dict(stored) if stored else {}
    modes[popup_key] = mode
    caller.attributes.add(popup_const.QUANTITY_MODE_ATTR, modes)
    _publish(caller)
    _publish_inventory(caller)

    return True, popup_const.MSG_QUANTITY_SET.format(mode=mode)


def forget_popup(caller) -> None:
    """Drop a grid pop-up with no pop-up send. BlackoutEvMenu calls this as
    it opens: the menu's first node sends the snapshot that replaces it. The
    inventory pane is sent, because its Deposit or Sell actions go too."""
    was_open = is_open(caller)
    _forget(caller)

    if was_open:
        _publish_inventory(caller)


def _open_menu(caller):
    """The caller's open BlackoutEvMenu when it has a node to show, or None.

    Read by duck type, not by class, so this module does not import the menu
    package, which imports EvMenu.
    """
    menu = getattr(caller.ndb, "_evmenu", None)

    if menu is None or not hasattr(menu, "popup_options"):
        return None

    return menu


def publish_if_open(caller) -> bool:
    """Send the open pop-up again, for a change no item move reports.

    A craft batch that is cancelled moves nothing, so emit_inventory never
    marks the pop-up. The command that cancels it calls this. Returns True
    when a pop-up was open.
    """
    if not is_open(caller):
        return False

    _publish(caller)

    return True


def build_snapshot(caller) -> dict:
    """
    Purpose: Describe the open pop-up as plain values, or the closed state.

    Entry:
        caller - a puppeted Character, or any object.

    Exit/Returns:
        Returns a dict with the fields of CharPopupPayload.

    Module Globals:
        None.

    Methodology:
        0. If an EvMenu is open, describe its node. It wins, because its
           cmdset takes every line a grid pop-up would send.
        1. If nothing is open, return the closed state.
        2. If the anchor is no longer usable, forget the pop-up and return the
           closed state. A deleted terminal closes its vault.
        3. Else, ask the definition for its status and grids.

    Notes/References:
        Step 2 writes, in a routine that mostly reads. The alternative is a
        snapshot that shows a vault for a terminal that is gone.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    menu = _open_menu(caller)

    if menu is not None:
        from . import menu as menu_popup

        return menu_popup.build_snapshot(menu)

    pair = _open_pair(caller)

    if pair is None:
        return _closed_snapshot()

    popup_key = pair.get(popup_const.OPEN_KEY_FIELD, "")
    anchor = pair.get(popup_const.OPEN_ANCHOR_FIELD)
    popup = _registry().get_popup(popup_key)
    usable = popup is not None and popup.anchor_is_usable(caller, anchor)

    if not usable:
        _forget(caller)
        return _closed_snapshot()

    mode = quantity_mode(caller, popup_key)
    buttons = _quantity_buttons(mode) if popup.uses_quantity else []

    return {
        "open": True,
        "key": popup_key,
        "title": popup.title_for(caller, anchor),
        "status": popup.status(caller, anchor),
        "grids": popup.grids(caller, anchor, mode),
        "quantity": buttons,
        "actions": popup.actions(caller, anchor),
        "text": "",
        "choices": [],
        "input": {},
        "timers": popup.timers(caller, anchor),
        "close_command": popup_const.POPUP_CLOSE_COMMAND,
    }


class CarriedLens:
    """
    The open pop-up, as the inventory pane sees it: what goes first on each
    carried row, and one short line for it.

    Built one time for each inventory payload, as CommerceContext is, so a
    32-slot bag asks for the pop-up one time and not 32 times.
    """

    def __init__(self, popup, caller, anchor, mode):
        self.popup = popup
        self.caller = caller
        self.anchor = anchor
        self.mode = mode

    def actions(self, item, slot_index: int, units: int) -> list:
        """The actions that lead this row, or []. Never raises."""
        try:
            return list(self.popup.carried_actions(
                self.caller, self.anchor, item, slot_index, units, self.mode))
        except Exception:
            logger.log_trace()
            return []

    def detail(self, item) -> str:
        """The row's short line, for example a price, or "". Never raises."""
        try:
            return str(self.popup.carried_detail(self.caller, self.anchor, item))
        except Exception:
            logger.log_trace()
            return ""


def carried_lens(caller):
    """
    Purpose: Say how the open pop-up changes the inventory pane's rows.

    Entry:
        caller - a puppeted Character, or any object.

    Exit/Returns:
        Returns a CarriedLens, or None when no grid pop-up is open.

    Module Globals:
        None.

    Methodology:
        1. If an EvMenu is open, return None. Its cmdset takes every line,
           so a Deposit sent from the pane would reach the menu.
        2. If no usable grid pop-up is open, return None.
        3. Else, wrap the definition, the anchor and the quantity mode.

    Notes/References:
        statefeed/inventory.py calls this one time for each payload. open,
        close and a quantity change send the inventory again, so the pane
        follows the pop-up.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    if _open_menu(caller) is not None:
        return None

    pair = _open_pair(caller)

    if pair is None:
        return None

    popup_key = pair.get(popup_const.OPEN_KEY_FIELD, "")
    anchor = pair.get(popup_const.OPEN_ANCHOR_FIELD)
    popup = _registry().get_popup(popup_key)
    usable = popup is not None and popup.anchor_is_usable(caller, anchor)

    if not usable:
        return None

    mode = quantity_mode(caller, popup_key)

    return CarriedLens(popup, caller, anchor, mode)
