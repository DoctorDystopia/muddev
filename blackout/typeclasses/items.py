"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: Item typeclasses. Stats come from ITEM_DB definitions; these
             classes carry only behaviour and derived properties.
"""

from typeclasses.objects import Object
from items.equipment.constants import WieldLocation
from systems.combat.combat_msg import format_combat_stat_bonuses



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

    def get_display_desc(self, looker, **kwargs):
        """
        Purpose: Append this item's combat stat bonuses (if any) to the desc
        shown by 'look', so a player can read what an item does without
        opening the equipment menu.

        Entry:
            looker - the Object doing the looking (Evennia's return_appearance
                     contract; unused here beyond the super() call).

        Exit/Returns:
            The base desc string, unchanged, when the item has no non-zero
            combat_stat_bonuses (every non-combat item, and any gadget whose
            bonuses are all zero). Otherwise the base desc plus a
            "Combat Bonuses:" block.

        Module Globals:
            None.

        Methodology:
            Delegates the base text to super().get_display_desc so a future
            change to Evennia's default/desc fallback is inherited rather
            than duplicated, then reuses
            systems.combat.combat_msg.format_combat_stat_bonuses -- the same
            formatter the equipment menu uses -- so the two screens can never
            disagree on how a bonus is labelled or coloured.

        Author: Nick Hobar
        Creation date: 08/04/2026
        """
        base_desc = super().get_display_desc(looker, **kwargs)

        item_bonuses = self.db.combat_stat_bonuses
        if not item_bonuses:
            return base_desc

        bonus_lines = format_combat_stat_bonuses(item_bonuses)
        if not bonus_lines:
            return base_desc

        bonus_block = "\n".join(bonus_lines)

        return f"{base_desc}\n\nCombat Bonuses:\n{bonus_block}"



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


class CurrencyItem(BaseItem):
    """
    Base typeclass for currency items. Currency-generic code (banking, shop
    pricing) should check against this class rather than a specific
    currency's subclass, so a second currency can be added later without
    touching that code.

    Every ItemDef for a currency must carry a ("<key>", "currency") tag --
    that tag key is the single source of truth for which currency an
    instance is, read back via currency_key.
    """

    @property
    def currency_key(self):
        return self.tags.get(category="currency")


class CreditsItem(CurrencyItem):
    """
    Stackable currency item representing Blackout credits (chips), the
    game's primary currency. Only one stack of CreditsItem should
    exist in a character's inventory.

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


class ArmorItem(EquippableItem):
    """
    Tiered armor like chest pieces and shields.

    As with ToolItem, all attributes come from the spawning ItemDef. Note the
    armor kind is stored under 'tool_type', not 'armor_type' -- the removed
    default wrote a 'armor_type' of "generic" that no consumer ever read,
    leaving a stale phantom attribute on every armor piece in the game.
    """