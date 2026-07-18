from evennia import DefaultObject
from evennia import create_object

from typeclasses.items import ToolItem
from typeclasses.objects import ObjectParent
from items.equipment.constants import WieldLocation


class Hammer(ToolItem):
    def at_object_creation(self):
        super().at_object_creation()
        self.tags.add("hammer", category="crafting_tool")
        self.db.use_slot = WieldLocation.MAIN_HAND
        self.db.tool_type = "hammer"
        self.db.tier = 1
        self.db.req_level = 0
        self.db.desc = "A heavy hammer used for hitting things."


class Anvil(ObjectParent, DefaultObject):
    def at_object_creation(self):
        super().at_object_creation()
        self.tags.add("anvil", category="crafting_tool")
        self.locks.add("get:false()")
        self.db.desc = "A solid steel anvil."
