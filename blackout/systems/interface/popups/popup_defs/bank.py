"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: The bank pop-up: the vault in one grid and the quantity row
             under it. Modelled on the OSRS bank interface.

             YOUR INVENTORY IS THE PANE, NOT A SECOND GRID. While the vault is
             open, carried_actions puts the Deposit actions FIRST on each row
             of the inventory pane, so a left click there deposits, as it does
             in OSRS. The pop-up does not draw a copy of the bag.

             IT MOVES NOTHING. Every slot carries `withdraw` and `deposit`
             lines, the same ones a telnet player types at the terminal, and
             the commands in typeclasses/bank_nodes.py do the transfer. So the
             pop-up, the EvMenu and the typed commands are three ways into one
             routine, and none of them can bank an item differently.
"""

from items.inventory.handler import SLOTS_TOTAL
from systems.gameplay.banking.handler import BANK_MAX_UNIQUE_KEYS
from typeclasses.bank_nodes import DEPOSIT_COMMAND_KEY, WITHDRAW_COMMAND_KEY

from systems.interface.statefeed import constants as feed_const

from .base_popup import BasePopup, grid, item_row, quantity_actions


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


# ─── Private helper routines ─────────────────────────────────────────────────

def _vault_groups(stored) -> list:
    """
    Purpose: Fold the vault's objects into one entry per item name.

    Entry:
        stored - the vault's objects, in the order the bank lists them.

    Exit/Returns:
        Returns a list of (first object, total units) pairs, first-seen order.

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

    return [(firsts[name], totals[name]) for name in firsts]


def _vault_rows(stored, mode) -> list:
    """Render one row for each vault slot, with its Withdraw actions."""
    rows = []

    for index, (item, units) in enumerate(_vault_groups(stored)):
        template = WITHDRAW_TEMPLATE.replace("{name}", str(item.key))
        actions = quantity_actions(
            VERB_WITHDRAW_LABEL, template, mode, units, PROMPT_WITHDRAW)
        rows.append(item_row(item, index, units, actions))

    return rows


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
        Purpose: Build the vault grid.

        Entry:
            caller - a Character with a bank and an inventory handler.
            anchor - the bank terminal. Not read: the vault is the caller's
                     own, whichever terminal opened it.
            mode   - the active quantity mode.

        Exit/Returns:
            Returns one grid dict.

        Module Globals:
            None.

        Methodology:
            Draw the vault with only its filled slots. The carried items are
            the inventory pane's, and carried_actions gives them Deposit.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 09/18/2026
        """
        stored = caller.bank.list_items()
        vault_rows = _vault_rows(stored, mode)
        vault = grid(VAULT_GRID_KEY, VAULT_GRID_TITLE, len(vault_rows), vault_rows)

        return [vault]

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
