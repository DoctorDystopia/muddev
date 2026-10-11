"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: The bank pop-up: the vault in one grid, its tabs above it, and
             the quantity row under it. Modelled on the OSRS bank interface.

             YOUR INVENTORY IS THE PANE, NOT A SECOND GRID. While the vault is
             open, carried_actions puts the Deposit actions FIRST on each row
             of the inventory pane, so a left click there deposits, as it does
             in OSRS. The pop-up does not draw a copy of the bag.

             IT MOVES NOTHING. Every slot carries `withdraw` and `deposit`
             lines, the same ones a telnet player types at the terminal, and
             the commands in typeclasses/bank_nodes.py do the transfer. So the
             pop-up, the EvMenu and the typed commands are three ways into one
             routine, and none of them can bank an item differently.

             THE TABS (10/08/2026). The grid sends EVERY slot, in main-view
             order, and each row names its tab. The grid also sends the tab
             buttons, the viewed tab, and two drag templates. The client
             shows the rows of the viewed tab, or all of them under the main
             tab, and it filters them by the text of its search box. Thus, a
             search covers the whole vault, as in OSRS, with no round trip
             for each key press. A tab click sends `bank view <n>`, because a
             new item goes into the viewed tab, and that is a rule of the
             server. systems/gameplay/banking/layout.py owns the layout.
"""

from items.inventory.handler import SLOTS_TOTAL
from systems.gameplay.banking import constants as bank_const
from systems.gameplay.banking import layout as vault_layout
from systems.gameplay.banking.handler import BANK_MAX_UNIQUE_KEYS
from typeclasses.bank_nodes import DEPOSIT_COMMAND_KEY, WITHDRAW_COMMAND_KEY
from world.item_database import ITEM_DB

from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed.serializers import _classify, _item_family

from .base_popup import (BasePopup, definition_family, definition_row, grid,
                         item_row, quantity_actions, text_action)


# ─── Public constant definitions ─────────────────────────────────────────────

BANK_POPUP_KEY: str = "bank"
BANK_POPUP_TITLE: str = "Bank Vault"

# The grid key is a stable name a client test can find the grid by.
VAULT_GRID_KEY: str = "vault"
VAULT_GRID_TITLE: str = "Vault"

VERB_WITHDRAW_LABEL: str = "Withdraw"
VERB_DEPOSIT_LABEL: str = "Deposit"

PROMPT_WITHDRAW: str = "Withdraw how many?"

# A vault slot names its item by KEY, because the vault has no slot numbers
# that `withdraw` parses. The key matches exactly: find_items_by_name tries an
# exact match before a prefix, so "rusty scrap" never reaches "rusty scrap
# metal" when both are stored.
WITHDRAW_TEMPLATE: str = (
    f"{WITHDRAW_COMMAND_KEY} {{name}} {feed_const.ACTION_AMOUNT_PLACEHOLDER}")

# A carried slot names its item by slot NUMBER, the form `deposit` parses as
# "this slot for one, the whole group for more". The inventory pane's Deposit
# actions use the same form, so the two cannot mean different items.
DEPOSIT_TEMPLATE: str = (
    f"{DEPOSIT_COMMAND_KEY} {{slot}} {feed_const.ACTION_AMOUNT_PLACEHOLDER}")

STATUS_TEMPLATE: str = "Vault {used}/{maximum} slots   Carried {carried}/{total}"

# The extra fields of the vault grid and its rows. Named once, because a
# client test and the Godot pop-up read them by these names.
GRID_TABS_FIELD: str = "tabs"
GRID_VIEW_FIELD: str = "view"
GRID_SEARCH_FIELD: str = "searchable"
GRID_DRAG_FIELD: str = "drag"
DRAG_ONTO_SLOT: str = "onto_slot"
DRAG_ONTO_TAB: str = "onto_tab"
ROW_TAB_FIELD: str = "tab"
ROW_DRAG_KEY_FIELD: str = "drag_key"
ROW_PLACEHOLDER_FIELD: str = "placeholder"

# The tab buttons. The main tab shows text, a named tab shows its name, and
# any other tab shows the mesh of its first item.
MAIN_TAB_LABEL: str = "All"
MAIN_TAB_TITLE: str = "Main tab"
TAB_TITLE: str = "Tab {index}"
NEW_TAB_LABEL: str = "+"
NEW_TAB_TITLE: str = "Drag an item here to make a new tab"

# The entries of a tab button's right-click list.
LABEL_VIEW: str = "View"
LABEL_RENAME: str = "Rename"
LABEL_CLEAR_NAME: str = "Clear name"
PROMPT_RENAME: str = "Name this tab:"

# The move entries of a slot's right-click list.
LABEL_MOVE_TO: str = "Move to {tab}"
LABEL_MOVE_TO_NEW: str = "Move to new tab"
LABEL_REMOVE_FROM_TAB: str = "Remove from tab"

# A placeholder slot. Its first action has an empty command, so a left click
# does nothing. A left click must never release a slot by mistake.
PLACEHOLDER_DETAIL: str = "Placeholder"
LABEL_PLACEHOLDER: str = "Placeholder"
LABEL_RELEASE: str = "Release"
PLACEHOLDER_QUANTITY: int = 0

# The footer buttons.
LABEL_PLACEHOLDERS_ON: str = "Placeholders: On"
LABEL_PLACEHOLDERS_OFF: str = "Placeholders: Off"
LABEL_RELEASE_ALL: str = "Release all placeholders"


# ─── Private helper routines ─────────────────────────────────────────────────

def _vault_groups(stored) -> dict:
    """
    Purpose: Fold the vault's objects into one entry per item name.

    Entry:
        stored - the vault's objects, in the order the bank lists them.

    Exit/Returns:
        Returns a dict of lowercased name -> (first object, total units).

    Module Globals:
        None.

    Methodology:
        Keyed on the lowercased key. That is the vault's own slot rule
        (BankHandler.used_slots), so the pop-up draws exactly as many slots as
        the vault counts. Eleven scrap plates are eleven objects and one slot.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    firsts = {}
    totals = {}

    for obj in stored:
        name = str(obj.key).lower()

        if name not in firsts:
            firsts[name] = obj
            totals[name] = 0

        totals[name] += int(getattr(obj, "quantity", 1) or 1)

    return {name: (firsts[name], totals[name]) for name in firsts}


def _fill(template: str, **values) -> str:
    """Put each value at its `{token}` in a template. str.replace, not
    str.format, for the reason base_popup._fill gives."""
    filled = template

    for token, value in values.items():
        filled = filled.replace("{" + token + "}", str(value))

    return filled


def _tab_name(current, index: int) -> str:
    """Name one tab in a menu entry: its own name, or "tab 2"."""
    if current.names[index]:
        return current.names[index]

    if index == bank_const.MAIN_TAB:
        return MAIN_TAB_TITLE.lower()

    return TAB_TITLE.format(index=index).lower()


def _move_actions(current, name: str) -> list:
    """
    Purpose: Render the entries that move one slot to another tab.

    Entry:
        current - the vault layout.
        name    - the slot name.

    Exit/Returns:
        Returns a list of action dicts: one for each other tab, then the new
        tab, then the removal from a tab when the slot is in one.

    Module Globals:
        bank_const.MOVE_TEMPLATE, the LABEL_MOVE_* constants read.

    Methodology:
        Each entry is the command that a drop on that tab sends. Thus, the
        menu and the drag cannot move a slot differently.

    Notes/References:
        The list grows with the tabs. The vault has no limit on tabs, but the
        slot cap bounds them, because an empty tab disappears.

    Author: Nick Hobar
    Creation date: 10/08/2026
    """
    own_tab = vault_layout.tab_of(current, name)
    key = vault_layout.display_key(current, name)
    actions = []

    for index in range(bank_const.FIRST_TAB, len(current.tabs)):
        if index == own_tab:
            continue

        command = _fill(bank_const.MOVE_TEMPLATE, source=key, target=index)
        label = LABEL_MOVE_TO.format(tab=_tab_name(current, index))
        actions.append({"label": label, "command": command})

    new_command = _fill(bank_const.MOVE_TEMPLATE, source=key,
                        target=bank_const.NEW_TAB_WORD)
    actions.append({"label": LABEL_MOVE_TO_NEW, "command": new_command})

    if own_tab != bank_const.MAIN_TAB:
        out_command = _fill(bank_const.MOVE_TEMPLATE, source=key,
                            target=bank_const.MAIN_TAB)
        actions.append({"label": LABEL_REMOVE_FROM_TAB, "command": out_command})

    return actions


def _stored_row(current, name: str, slot: int, group, mode) -> dict:
    """Render one slot that holds items: Withdraw first, then the moves."""
    item, units = group
    template = WITHDRAW_TEMPLATE.replace("{name}", str(item.key))
    actions = quantity_actions(
        VERB_WITHDRAW_LABEL, template, mode, units, PROMPT_WITHDRAW)
    actions.extend(_move_actions(current, name))

    return item_row(item, slot, units, actions)


def _placeholder_row(current, name: str, slot: int) -> dict:
    """
    Purpose: Render one placeholder slot: dim, with a count of zero.

    Entry:
        current - the vault layout.
        name    - the slot name of the placeholder.
        slot    - its 0-based position in the grid.

    Exit/Returns:
        Returns a row dict in the shape item_row gives.

    Module Globals:
        ITEM_DB read.

    Methodology:
        Draw the mesh from the ItemDef of the prototype that the item had.
        An item with no ItemDef draws the generic mesh with its own name.

    Notes/References:
        The first action does nothing, so a left click cannot release the
        slot. Release and the moves are in the right-click list.

    Author: Nick Hobar
    Creation date: 10/08/2026
    """
    entry = current.meta.get(name, {})
    key = vault_layout.display_key(current, name)
    release = _fill(bank_const.RELEASE_TEMPLATE, name=key)
    actions = [{"label": LABEL_PLACEHOLDER, "command": ""},
               {"label": LABEL_RELEASE, "command": release}]
    actions.extend(_move_actions(current, name))
    item_def = ITEM_DB.get(entry.get(bank_const.META_PROTOTYPE, ""))

    if item_def is not None:
        return definition_row(item_def, slot, PLACEHOLDER_QUANTITY, actions,
                              name=key, detail=PLACEHOLDER_DETAIL, enabled=False)

    return {
        "id": 0, "slot": int(slot), "name": key,
        "asset": feed_const.ASSET_KEY_GENERIC,
        "family": feed_const.ITEM_FAMILY_GENERIC,
        "quantity": PLACEHOLDER_QUANTITY, "stackable": False, "equip_slot": "",
        "actions": actions, "detail": PLACEHOLDER_DETAIL,
        "enabled": False, "info": "",
    }


def _vault_rows(current, groups: dict, mode) -> list:
    """Render every slot in main-view order, each with its tab and the key a
    drag names it by."""
    rows = []

    for slot, name in enumerate(vault_layout.ordered_names(current)):
        group = groups.get(name)

        if group is None:
            row = _placeholder_row(current, name, slot)
        else:
            row = _stored_row(current, name, slot, group, mode)

        row[ROW_TAB_FIELD] = vault_layout.tab_of(current, name)
        row[ROW_DRAG_KEY_FIELD] = vault_layout.display_key(current, name)
        row[ROW_PLACEHOLDER_FIELD] = group is None
        rows.append(row)

    return rows


def _slot_art(current, name: str, groups: dict) -> tuple:
    """Return (asset, family) of one slot: from the stored object, or from
    the ItemDef of a placeholder."""
    group = groups.get(name)

    if group is not None:
        item = group[0]
        _kind, asset = _classify(item)

        return asset, _item_family(item)

    prototype = current.meta.get(name, {}).get(bank_const.META_PROTOTYPE, "")
    item_def = ITEM_DB.get(prototype)

    if item_def is None:
        return feed_const.ASSET_KEY_GENERIC, feed_const.ITEM_FAMILY_GENERIC

    return str(item_def.key), definition_family(item_def)


def _tab_actions(current, index: int) -> list:
    """The right-click list of one tab button: View, Rename, Clear name."""
    view = _fill(bank_const.VIEW_TEMPLATE, index=index)
    rename_template = _fill(bank_const.NAME_TEMPLATE, index=index)
    actions = [
        {"label": LABEL_VIEW, "command": view},
        text_action(LABEL_RENAME, rename_template, PROMPT_RENAME,
                    bank_const.TAB_NAME_MAX_LENGTH),
    ]

    if current.names[index]:
        clear = _fill(bank_const.CLEAR_NAME_TEMPLATE, index=index)
        actions.append({"label": LABEL_CLEAR_NAME, "command": clear})

    return actions


def _tab_button(current, index: int, groups: dict) -> dict:
    """
    Purpose: Render one tab button.

    Entry:
        current - the vault layout.
        index   - the tab number.
        groups  - the stored groups, as _vault_groups gives them.

    Exit/Returns:
        Returns {index, label, title, asset, family, active, drop_key,
        actions}.

    Module Globals:
        The MAIN_TAB_* and TAB_* constants read.

    Methodology:
        A named tab sends its name and no asset. An unnamed player tab sends
        the art of its first slot. The unnamed main tab sends "All". The
        client draws the mesh when there is an asset, and the label when
        there is not, so it decides nothing about a tab.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/08/2026
    """
    name = current.names[index]
    is_main = index == bank_const.MAIN_TAB
    title = MAIN_TAB_TITLE if is_main else TAB_TITLE.format(index=index)
    asset, family = "", ""
    label = name

    if name:
        title = f"{title}: {name}"
    elif is_main:
        label = MAIN_TAB_LABEL
    else:
        asset, family = _slot_art(current, current.tabs[index][0], groups)

    return {
        "index": index, "label": label, "title": title,
        "asset": asset, "family": family,
        "active": index == current.viewed, "drop_key": str(index),
        "actions": _tab_actions(current, index),
    }


def _tab_buttons(current, groups: dict) -> list:
    """Every tab button in order, the main tab first, and the "+" last. The
    "+" takes a drop only: its drop key is the new-tab word."""
    buttons = [_tab_button(current, index, groups)
               for index in range(len(current.tabs))]
    buttons.append({
        "index": len(current.tabs), "label": NEW_TAB_LABEL,
        "title": NEW_TAB_TITLE, "asset": "", "family": "", "active": False,
        "drop_key": bank_const.NEW_TAB_WORD, "actions": [],
    })

    return buttons


# ─── Public classes ──────────────────────────────────────────────────────────

class BankPopup(BasePopup):
    """The vault, anchored to a terminal. The inventory pane deposits."""

    key = BANK_POPUP_KEY
    title = BANK_POPUP_TITLE
    room_bound = True
    uses_quantity = True

    def status(self, caller, anchor) -> str:
        """Vault slots used and carried slots used, on one line."""
        used = caller.bank.used_slots()
        carried = caller.inventory.count_used()

        return STATUS_TEMPLATE.format(
            used=used, maximum=BANK_MAX_UNIQUE_KEYS,
            carried=carried, total=SLOTS_TOTAL)

    def grids(self, caller, anchor, mode) -> list:
        """
        Purpose: Build the vault grid, with its tabs.

        Entry:
            caller - a Character with a bank and an inventory handler.
            anchor - the bank terminal. Not read: the vault is the caller's
                     own, whichever terminal opened it.
            mode   - the active quantity mode.

        Exit/Returns:
            Returns one grid dict, with the tab fields this module names.

        Module Globals:
            The GRID_* and DRAG_* constants read.

        Methodology:
            1. Read the layout. The read fits it to the vault, so it is
               current.
            2. Render every slot in main-view order, and the tab buttons.
            3. Add the viewed tab, the search flag and the drag templates.

        Notes/References:
            The carried items are the inventory pane's, and carried_actions
            gives them Deposit.

        Author: Nick Hobar
        Creation date: 09/18/2026
        """
        current = caller.bank.layout()
        groups = _vault_groups(caller.bank.list_items())
        vault_rows = _vault_rows(current, groups, mode)
        vault = grid(VAULT_GRID_KEY, VAULT_GRID_TITLE, len(vault_rows), vault_rows)

        vault[GRID_TABS_FIELD] = _tab_buttons(current, groups)
        vault[GRID_VIEW_FIELD] = current.viewed
        vault[GRID_SEARCH_FIELD] = True
        vault[GRID_DRAG_FIELD] = {
            DRAG_ONTO_SLOT: bank_const.SWAP_TEMPLATE,
            DRAG_ONTO_TAB: bank_const.MOVE_TEMPLATE,
        }

        return [vault]

    def actions(self, caller, anchor) -> list:
        """The footer: the placeholder switch, and Release all when any
        placeholder exists."""
        current = caller.bank.layout()
        keep = current.keep_placeholders
        switch = bank_const.SWITCH_OFF_WORD if keep else bank_const.SWITCH_ON_WORD
        label = LABEL_PLACEHOLDERS_ON if keep else LABEL_PLACEHOLDERS_OFF
        command = _fill(bank_const.PLACEHOLDERS_TEMPLATE, switch=switch)
        buttons = [{"label": label, "command": command}]

        if vault_layout.placeholder_names(current):
            release_all = _fill(bank_const.RELEASE_TEMPLATE,
                                name=bank_const.RELEASE_ALL_WORD)
            buttons.append({"label": LABEL_RELEASE_ALL, "command": release_all})

        return buttons

    def carried_actions(self, caller, anchor, item, slot_index, units, mode) -> list:
        """
        Purpose: Give one inventory-pane row its Deposit actions.

        Entry:
            caller     - the banking Character.
            anchor     - the bank terminal. Not read.
            item       - the carried object.
            slot_index - its 0-based slot in the carried grid.
            units      - the units of its whole group.
            mode       - the active quantity mode.

        Exit/Returns:
            Returns a list of action dicts, the active mode first.

        Module Globals:
            DEPOSIT_TEMPLATE, VERB_DEPOSIT_LABEL read.

        Methodology:
            The maximum is the units of the whole GROUP, the rule
            statefeed/inventory.py explains: eight separate chunks each offer
            Deposit 5, because `deposit 3 5` reaches all eight.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 09/18/2026
        """
        template = DEPOSIT_TEMPLATE.replace("{slot}", str(slot_index + 1))
        actions = quantity_actions(
            VERB_DEPOSIT_LABEL, template, mode, units,
            feed_const.ACTION_PROMPT_DEPOSIT)

        return actions
