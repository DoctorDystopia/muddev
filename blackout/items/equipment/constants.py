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
    NECK = "neck"
    MAIN_HAND_FINGER = "main_hand_finger"
    OFF_HAND_FINGER = "off_hand_finger"

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
    WieldLocation.NECK,
    WieldLocation.MAIN_HAND_FINGER,
    WieldLocation.OFF_HAND_FINGER,
)

# Max number of unequipped items a character can carry in their Evennia inventory (contents).
# Equipped items (tracked by the handler) do not count against this limit.

# Slots that must ALSO be emptied to put an item into a given slot, besides
# that slot itself.
#
# A table because the rule was previously written out twice inside
# EquipmentHandler.equip -- once to work out what would be displaced, once to
# clear the slots -- and the two copies did not agree. The "what is displaced"
# copy omitted the two-hand slot from its own conflict list, so equipping a
# two-hander over a two-hander orphaned the old one: its location was already
# None, and nothing returned it to the inventory. No two-handed item exists in
# ITEM_DB yet, which is the only reason that never lost anyone an item.
#
# Slots not listed here conflict with nothing but themselves.
SLOT_CONFLICTS: dict = {
    WieldLocation.TWO_HANDS: (WieldLocation.MAIN_HAND, WieldLocation.OFF_HAND),
    WieldLocation.MAIN_HAND: (WieldLocation.TWO_HANDS,),
    WieldLocation.OFF_HAND: (WieldLocation.TWO_HANDS,),
}


def slots_displaced_by(use_slot) -> tuple:
    """Every slot emptied by equipping into `use_slot`, including it.

    Used both to collect what will be displaced and to clear those slots, so
    the two can no longer disagree.
    """
    conflicts = SLOT_CONFLICTS.get(use_slot, ())

    return (use_slot,) + conflicts

MAX_INVENTORY_SLOTS = 32
