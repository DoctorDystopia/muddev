from typeclasses.objects import Object
from items.equipment.constants import WieldLocation



class BaseItem(Object):
    """The foundation for all items in Blackout."""
    pass



class EquippableItem(BaseItem):
    """Items that can be worn or wielded."""
    
    @property
    def inventory_use_slot(self):
        """Returns the slot this item occupies when equipped."""
        return self.attributes.get("use_slot", default=WieldLocation.BACKPACK)



class ToolItem(EquippableItem):
    """
    Tiered tools like axes and pickaxes.
    Relies on prototype attributes: 'tool_type', 'tier', and 'req_level'.
    """
    
    def at_object_creation(self):
        super().at_object_creation()
        # Ensure tools default to being wielded in the main hand
        self.db.use_slot = WieldLocation.MAIN_HAND
        self.db.tool_type = "generic"
        self.db.tier = 0
        self.db.req_level = 0