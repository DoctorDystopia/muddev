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



# Max number of unequipped items a character can carry in their Evennia inventory (contents).
# Equipped items (tracked by the handler) do not count against this limit.
MAX_INVENTORY_SLOTS = 32