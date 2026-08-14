"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Summary panel: credits, carried slots, and stored items.
"""

from evennia.utils import logger

from items.equipment.constants import MAX_INVENTORY_SLOTS
from systems.shop.shop_service import credits_in

from .. import constants as const
from .. import layout
from .base_panel import BasePanel


# Public constant definitions

PANEL_TITLE = "Holdings"

LABEL_CARRIED = "Credits"
LABEL_BANKED = "Banked"
LABEL_INVENTORY = "Inventory"
LABEL_EQUIPPED = "Equipped"
LABEL_STORAGE = "Bank items"

# Rendered when the bank cannot be read at all. Distinct from a bank holding
# nothing, which legitimately reads as zero.
STORAGE_UNAVAILABLE_TEXT = const.EMPTY_VALUE_TEXT


class HoldingsPanel(BasePanel):
    """
    Purpose: What the character owns and how much room is left to own more.

    Entry:
        character is a Character with inventory, equipment and bank handlers.

    Exit/Returns:
        Not applicable -- see render / data.

    Module Globals:
        MAX_INVENTORY_SLOTS read.

    Methodology:
        Counts only. Contents belong to the inventory and banking screens, and
        duplicating a list here would make this panel go stale the moment
        either of those changes shape.

        The 32-slot cap is read from items/equipment/constants.py rather than
        written out, since 02_Player/Player_Overview.md treats that number as a
        deliberate pacing knob that may be retuned.

    Notes/References:
        Bank access materialises a per-character bank room on first use, which
        is why the read is guarded -- a summary screen must never be the thing
        that creates game state as a side effect of being looked at.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """

    key = "holdings"
    title = PANEL_TITLE
    order = const.PANEL_ORDER_HOLDINGS
    public = False


    @classmethod
    def _bank_items(cls, character: object) -> list:
        """
        Purpose: Read the character's stored items, tolerating a bank failure.

        Entry:
            character is a Character with a bank handler.

        Exit/Returns:
            Returns a list of item objects, or None if the bank could not be
            read.

        Module Globals:
            None.

        Methodology:
            None and [] are deliberately different: an empty bank is a fact
            worth reporting as zero, whereas an unreadable one must not be
            reported as "you have nothing saved".

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        try:
            items = character.bank.list_items()
        except Exception as exc:
            logger.log_err(f"HoldingsPanel._bank_items failed: {exc!r}")

            return None

        return list(items)


    @classmethod
    def render(cls, character: object) -> list:
        """
        Purpose: Render the holdings band.

        Entry:
            character is a Character with inventory, equipment and bank
            handlers.

        Exit/Returns:
            Returns a list of display lines.

        Module Globals:
            LABEL_* read, MAX_INVENTORY_SLOTS read.

        Methodology:
            Carried credits come from the shop service's currency helper, which
            is the one thing in the codebase that knows what counts as money.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        character.inventory.sync()

        carried_credits = credits_in(character.contents)
        used_slots = character.inventory.count_used()
        equipped_count = character.equipment.count_equipped()

        bank_items = cls._bank_items(character)

        if bank_items is None:
            banked_credits_text = STORAGE_UNAVAILABLE_TEXT
            storage_text = STORAGE_UNAVAILABLE_TEXT
        else:
            banked_credits_text = f"{credits_in(bank_items):,}"
            storage_text = f"{len(bank_items):,}"

        pairs = [
            (LABEL_CARRIED, f"{carried_credits:,}"),
            (LABEL_BANKED, banked_credits_text),
            (LABEL_INVENTORY, f"{used_slots} / {MAX_INVENTORY_SLOTS}"),
            (LABEL_EQUIPPED, f"{equipped_count}"),
            (LABEL_STORAGE, storage_text),
        ]

        lines = layout.fields(pairs)

        return lines


    @classmethod
    def data(cls, character: object) -> dict:
        """
        Purpose: Structured form of the holdings band.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a dict of plain JSON-safe values. Bank figures are None
            when the bank could not be read.

        Module Globals:
            MAX_INVENTORY_SLOTS read.

        Methodology:
            Same None-vs-zero distinction as the text view, carried through to
            the wire so a client can grey the field rather than draw a zero.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        character.inventory.sync()
        bank_items = cls._bank_items(character)

        if bank_items is None:
            banked_credits = None
            stored_count = None
        else:
            banked_credits = credits_in(bank_items)
            stored_count = len(bank_items)

        payload = {
            "credits_carried": int(credits_in(character.contents)),
            "credits_banked": banked_credits,
            "inventory_used": int(character.inventory.count_used()),
            "inventory_slots": int(MAX_INVENTORY_SLOTS),
            "equipped_count": int(character.equipment.count_equipped()),
            "bank_items": stored_count,
        }

        return payload
