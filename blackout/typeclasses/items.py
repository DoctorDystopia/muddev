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
    Relies on prototype attributes: 'tool_type', 'tier', and 'req_level'.
    """
    
    def at_object_creation(self):
        super().at_object_creation()
        self.db.use_slot = WieldLocation.MAIN_HAND
        self.db.tool_type = "generic"
        self.db.tier = 0
        self.db.req_level = 0


class CreditsItem(BaseItem):
    """
    Stackable currency item representing Blackout credits (chips).
    Only one stack of CreditsItem should exist in a character's inventory.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.stackable = True
        self.db.tradeable = True
        self.db.value = 1
        self.db.quantity = 0


class WeaponItem(EquippableItem):
    """
    Tiered weapons like swords and spears.
    Relies on prototype attributes: 'weapon_type', 'tier', and 'req_level'.
    """
    
    def at_object_creation(self):
        super().at_object_creation()
        self.db.use_slot = WieldLocation.MAIN_HAND
        self.db.weapon_type = "generic"
        self.db.tier = 0
        self.db.req_level = 0