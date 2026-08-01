"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: Equipment slot definitions and inventory sizing.
"""

from enum import Enum



class WieldLocation(Enum):
    MAIN_HAND = "main_hand"
    OFF_HAND = "off_hand"
    TWO_HANDS = "two_hands"
    BODY = "body"
    LEGS = "legs"
    HEAD = "head"
    BACK = "back"
    FEET = "feet"

    @property
    def label(self) -> str:
        """
        Purpose: Human-readable slot name for player-facing display.

        Entry:
            No conditions.

        Exit/Returns:
            Returns the member value in title case with underscores replaced
            by spaces -- "two_hands" renders as "Two Hands".

        Module Globals:
            None

        Methodology:
            Derived from the value rather than stored in a lookup table. The
            menu layer previously carried a hand-written slot->label dict that
            restated all eight members, so adding a slot meant editing two
            places and a missed edit silently fell back to the raw value.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/01/2026
        """
        spaced = self.value.replace("_", " ")

        return spaced.title()



# Public constant definitions

# Presentation order for equipment UIs: weapons first, then armour top-to-bottom.
# Deliberately NOT the declaration order, and kept here beside the enum so any
# future equipment screen renders slots the same way.
SLOT_DISPLAY_ORDER = (
    WieldLocation.MAIN_HAND,
    WieldLocation.OFF_HAND,
    WieldLocation.TWO_HANDS,
    WieldLocation.HEAD,
    WieldLocation.BODY,
    WieldLocation.LEGS,
    WieldLocation.FEET,
    WieldLocation.BACK,
)

# Max number of unequipped items a character can carry in their Evennia inventory (contents).
# Equipped items (tracked by the handler) do not count against this limit.
MAX_INVENTORY_SLOTS = 32
