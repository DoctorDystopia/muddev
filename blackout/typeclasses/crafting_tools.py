"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: Crafting tool typeclasses. Item stats come from ITEM_DB; these
             classes carry only behaviour.
"""

from evennia import DefaultObject

from typeclasses.items import ToolItem
from typeclasses.objects import ObjectParent


class Hammer(ToolItem):
    """
    The metalsmithing hammer.

    Everything this class used to set in at_object_creation -- the
    ("hammer", "crafting_tool") tag, use_slot, tool_type, tier, req_level and
    desc -- is already declared by ITEM_DB["hammer"], down to the same desc
    string. The typeclass exists so the ItemDef has a path to name.
    """


class Anvil(ObjectParent, DefaultObject):
    def at_object_creation(self):
        super().at_object_creation()
        self.tags.add("anvil", category="crafting_tool")
        self.locks.add("get:false()")
        self.db.desc = "A solid steel anvil."
