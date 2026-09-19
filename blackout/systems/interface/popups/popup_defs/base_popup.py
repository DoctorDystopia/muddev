"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: BasePopup, the shape every pop-up definition fills, and the
             helpers that turn a quantity mode into a slot's actions.

             A pop-up definition answers three questions and nothing else:
             what is its title, is its anchor still usable, and what grids
             does it show. Opening, closing, the quantity mode and the send
             belong to service.py, so a new pop-up is one file under
             popup_defs/ and no edit anywhere else.
"""

from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed.inventory import _prompted_action
from systems.interface.statefeed.serializers import _classify, _item_family

from .. import constants as popup_const


# ─── Private helper routines ─────────────────────────────────────────────────

def _mode_label(mode) -> str:
    """Name one quantity mode the way a button shows it: "5" or "All"."""
    if mode == popup_const.QUANTITY_ALL:
        return popup_const.QUANTITY_LABEL_ALL

    return str(mode)


def _mode_argument(mode) -> str:
    """Spell one quantity mode the way `deposit` and `withdraw` parse it."""
    if mode == popup_const.QUANTITY_ALL:
        return popup_const.QUANTITY_ALL

    return str(int(mode))


def _whole_action(verb_label: str, template: str, mode) -> dict:
    """Render one action that needs no prompt, for example "Withdraw 5"."""
    label = f"{verb_label} {_mode_label(mode)}"
    command = _fill(template, _mode_argument(mode))

    return {"label": label, "command": command}


def _fill(template: str, amount) -> str:
    """Put an amount where the template carries the placeholder token.

    str.replace, not str.format: the template already holds an item name, and
    a name with a brace in it must not break the render.
    """
    return template.replace(feed_const.ACTION_AMOUNT_PLACEHOLDER, str(amount))


def _ordered_modes(mode) -> list:
    """List the whole-number modes a slot offers, the active mode first.

    The first action is what a left click sends, so the active mode goes to
    the top. A custom mode from the X button joins the fixed ones, because
    OSRS offers "Withdraw 23" in the menu after X was set to 23.
    """
    modes = list(popup_const.QUANTITY_FIXED_MODES)

    if mode != popup_const.QUANTITY_ALL and mode not in modes:
        modes.append(mode)

    modes.append(popup_const.QUANTITY_ALL)
    modes.remove(mode)
    modes.insert(0, mode)

    return modes


# ─── Public routines ─────────────────────────────────────────────────────────

def quantity_actions(verb_label: str, template: str, mode, units: int,
                     prompt: str) -> list:
    """
    Purpose: Render the actions of one slot for one verb, with the active
             quantity mode first.

    Entry:
        verb_label - the label stem, for example "Withdraw".
        template   - the command, with ACTION_AMOUNT_PLACEHOLDER where the
                     count goes.
        mode       - the active quantity mode: an int, or QUANTITY_ALL.
        units      - how many units the verb can reach from this slot.
        prompt     - what the X box asks.

    Exit/Returns:
        Returns a list of action dicts. The first one is what a left click
        sends.

    Module Globals:
        popup_const.QUANTITY_* read. feed_const.ACTION_* read.

    Methodology:
        1. If the slot holds one unit, return one bare action with count 1.
        2. Else, render each whole-number mode, the active mode first.
        3. Put the prompted X action after the whole numbers and before All.

    Notes/References:
        The X action uses the statefeed's own prompted shape, so the client
        that already asks "Deposit how many?" asks this too with no new code.
        The inventory pane makes the same split on units, not on one stack.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    if units <= feed_const.ACTION_QUANTITY_SINGLE:
        command = _fill(template, feed_const.ACTION_QUANTITY_SINGLE)

        return [{"label": verb_label, "command": command}]

    actions = []

    for each_mode in _ordered_modes(mode):
        actions.append(_whole_action(verb_label, template, each_mode))

    prompted_label = f"{verb_label} {popup_const.QUANTITY_LABEL_X}"
    prompted = _prompted_action(prompted_label, template, prompt, units)
    actions.insert(len(actions) - 1, prompted)

    return actions


def item_row(item, slot: int, quantity: int, actions: list,
             detail: str = "", enabled: bool = True, info: str = "") -> dict:
    """
    Purpose: Render one slot of a pop-up grid.

    Entry:
        item     - the live object the slot shows. For a group, any member.
        slot     - the 0-based position in the grid.
        quantity - the number the slot draws in its corner.
        actions  - the slot's actions, the default first.
        detail   - one short line under the name, for example a price.
                   "" draws the quantity there.
        enabled  - False draws the slot dim, for a thing the player cannot
                   do yet. `detail` then says why.
        info     - more lines for the tooltip, for example what a recipe
                   consumes. "" adds nothing.

    Exit/Returns:
        Returns a dict in the shape of a char_items_list row, so the client
        draws it with the code that already draws an inventory slot.

    Module Globals:
        None.

    Methodology:
        Reads the mesh facts through the same two serializer routines the
        inventory uses, so a sword in the vault looks like the sword in the
        bag.

    Notes/References:
        No `desc`, for the reason statefeed/inventory.py gives.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    _kind, asset_key = _classify(item)
    family = _item_family(item)

    return {
        "id": item.id,
        "slot": int(slot),
        "name": str(item.key),
        "asset": asset_key,
        "family": family,
        "quantity": int(quantity),
        "stackable": bool(getattr(item, "is_stackable", False)),
        "equip_slot": "",
        "actions": actions,
        "detail": str(detail),
        "enabled": bool(enabled),
        "info": str(info),
    }


def definition_family(item_def) -> str:
    """
    Purpose: Name the mesh family of an item that does not exist yet.

    Entry:
        item_def - an ItemDef from ITEM_DB.

    Exit/Returns:
        One of the ITEM_FAMILY_* values, or ITEM_FAMILY_GENERIC.

    Module Globals:
        feed_const.ITEM_FAMILY_PRIORITY read.

    Methodology:
        The rule of serializers._item_family, applied to the tags the ItemDef
        WILL stamp: walk ITEM_FAMILY_PRIORITY, never the tag order. So a
        recipe output and the item that the recipe makes pick one family.

    Notes/References:
        A shop's endless stock and a recipe's output are ItemDefs, not
        objects. That is the only reason this routine exists.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    categories = {category for _tag_key, category in item_def.tags}

    for family in feed_const.ITEM_FAMILY_PRIORITY:
        if family in categories:
            return str(family)

    return feed_const.ITEM_FAMILY_GENERIC


def definition_row(item_def, slot: int, quantity: int, actions: list,
                   name: str = "", detail: str = "",
                   enabled: bool = True, info: str = "") -> dict:
    """Render one slot for an ItemDef, in the shape item_row gives.

    The asset key is the ItemDef's key, because that is the prototype key a
    spawned copy carries, and the prototype key is what _classify reports.
    `id` is 0: nothing in the database stands behind the slot yet.
    """
    return {
        "id": 0,
        "slot": int(slot),
        "name": str(name or item_def.name),
        "asset": str(item_def.key),
        "family": definition_family(item_def),
        "quantity": int(quantity),
        "stackable": bool(item_def.stackable),
        "equip_slot": "",
        "actions": actions,
        "detail": str(detail),
        "enabled": bool(enabled),
        "info": str(info),
    }


def grid(key: str, title: str, slots_total: int, rows: list) -> dict:
    """Render one grid of a pop-up: a title, a slot count, and the rows.

    Empty slots are omitted, as in char_items_list. `slots_total` says how
    many frames to draw, so a bag keeps its 32 squares and a vault draws only
    what it holds.
    """
    return {
        "key": str(key),
        "title": str(title),
        "slots_total": int(slots_total),
        "items": rows,
    }


# ─── Public classes ──────────────────────────────────────────────────────────

class BasePopup:
    """
    The shape of one pop-up definition. Subclass it in a module under
    popup_defs/ and set `key`. The registry finds it.

    key          - the stable name, stored on the character while it is open
    title        - the heading the client shows
    room_bound   - True when walking away from the anchor closes the pop-up
    uses_quantity - True when the pop-up shows the 1 / 5 / 10 / X / All row
    """

    key: str = ""
    title: str = ""
    room_bound: bool = True
    uses_quantity: bool = True

    def anchor_is_usable(self, caller, anchor) -> bool:
        """Say whether the anchor still supports this pop-up.

        The default rule: the anchor still exists, and when the pop-up is
        room-bound, it stands in the caller's room. A shop counter and a bank
        vault are things you STAND at.
        """
        if anchor is None or getattr(anchor, "pk", None) is None:
            return False

        if not self.room_bound:
            return True

        here = getattr(caller, "location", None)

        return here is not None and anchor.location == here

    def title_for(self, caller, anchor) -> str:
        """The heading for this anchor. The class title by default.

        A crafting station names itself, so one definition serves the
        furnace and the anvil.
        """
        return self.title

    def status(self, caller, anchor) -> str:
        """The one line under the title. Empty by default."""
        return ""

    def grids(self, caller, anchor, mode) -> list:
        """The grids to show. A subclass must override this."""
        raise NotImplementedError

    def actions(self, caller, anchor) -> list:
        """Buttons under the grids, as {label, command} dicts. None by default.

        For a thing the pop-up affords as a whole, not one slot: cancel a
        craft, collect a cure.
        """
        return []

    def carried_actions(self, caller, anchor, item, slot_index, units, mode) -> list:
        """The actions that go FIRST on one row of the inventory pane while
        this pop-up is open. None by default.

        A pop-up does not draw a copy of the bag. The bank gives each carried
        row Deposit, and the shop gives it Sell, so a left click in the pane
        does what a left click in the OSRS bag does beside the interface.
        statefeed/inventory.py asks this through service.carried_lens.
        """
        return []

    def carried_detail(self, caller, anchor, item) -> str:
        """One short line for a carried row while this pop-up is open, for
        example the price a shop pays. "" by default."""
        return ""

    def timers(self, caller, anchor) -> dict:
        """The side panel of timed slots, or {} for none. None by default.

        A station whose work finishes later, not in the command that started
        it, shows its slots here: `{title, total, slots}`, each slot
        `{name, ready, remaining, duration}` in seconds. The curing chamber
        is the first. See crafting.py.
        """
        return {}
