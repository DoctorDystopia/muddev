"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: Item typeclasses. Stats come from ITEM_DB definitions; these
             classes carry only behaviour and derived properties.
"""

from typeclasses.objects import Object
from items.equipment.constants import WieldLocation



def _resolve_use_slot(value):
    """
    Coerce a stored use_slot value into a WieldLocation enum member.
    Accepts WieldLocation, its string name ("MAIN_HAND"), or its value ("main_hand").
    """
    if value is None:
        return None
    
    if isinstance(value, WieldLocation):
        return value
    
    if isinstance(value, str):
        try:
            return WieldLocation[value]
        except KeyError:
            try:
                return WieldLocation(value)
            except ValueError:
                return None
            
    return None



class BaseItem(Object):
    """The foundation for all items in Blackout."""

    @property
    def item_value(self):
        return self.attributes.get("value", default=0)

    @property
    def item_weight(self):
        return self.attributes.get("weight", default=0.0)

    @property
    def is_tradeable(self):
        return self.attributes.get("tradeable", default=True)

    @property
    def is_stackable(self):
        return self.attributes.get("stackable", default=False)

    @property
    def quantity(self):
        if not self.is_stackable:
            return 1
        return self.attributes.get("quantity", default=1)

    @quantity.setter
    def quantity(self, value):
        if not self.is_stackable:
            return
        if value < 0:
            value = 0
        self.attributes.add("quantity", int(value))



class EquippableItem(BaseItem):
    """Items that can be worn or wielded."""
    
    @property
    def inventory_use_slot(self):
        """Returns the slot this item occupies when equipped, or None if not equippable."""
        raw = self.attributes.get("use_slot", category=None, default=None)
        return _resolve_use_slot(raw)



class ToolItem(EquippableItem):
    """
    Tiered tools like axes and pickaxes.

    Carries no attribute defaults of its own. Every value it relies on --
    'use_slot', 'tool_type', 'tier', 'req_level' -- comes from the spawning
    ItemDef in world/item_database.py, which is the single source of truth.
    Hardcoding them here restated the ItemDef and had already drifted: the
    literal tier of 0 contradicted rusty_scrap_axe's tier of 1, and every
    write was immediately overwritten on the ItemDef path anyway.
    """


class CreditsItem(BaseItem):
    """
    Stackable currency item representing Blackout credits (chips).
    Only one stack of CreditsItem should exist in a character's inventory.

    Spawn via ITEM_DB["credits"], which supplies stackable, tradeable, value
    and the ("credits", "currency") tag.
    """


class WeaponItem(EquippableItem):
    """
    Tiered weapons like swords and spears.

    As with ToolItem, all attributes come from the spawning ItemDef. Note the
    weapon kind is stored under 'tool_type', not 'weapon_type' -- the removed
    default wrote a 'weapon_type' of "generic" that no consumer ever read,
    leaving a stale phantom attribute on every weapon in the game.
    """