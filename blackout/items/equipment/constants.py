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



MAX_INVENTORY_SLOTS = 32