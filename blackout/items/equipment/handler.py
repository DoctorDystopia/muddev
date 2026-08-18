"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: EquipmentHandler — per-character wield-slot state and the
             skill gate applied at equip time.
"""

from evennia.utils import logger

from .constants import WieldLocation, MAX_INVENTORY_SLOTS
from .skill_requirements import ARMOR_SKILL_MAP, WEAPON_SKILL_MAP



class EquipmentError(TypeError):
    """Custom exception for equipment failures like full inventory."""
    pass



class EquipmentHandler:
    save_attribute = "inventory_slots"


    def __init__(self, obj):
        self.obj = obj
        self._load()


    def _load(self):
        """Loads the slot storage from the database, migrating old data if needed."""
        self.slots = self.obj.attributes.get(
            self.save_attribute,
            category="inventory",
            default={
                WieldLocation.MAIN_HAND: None,
                WieldLocation.OFF_HAND: None,
                WieldLocation.TWO_HANDS: None,
                WieldLocation.BODY: None,
                WieldLocation.HEAD: None,
                WieldLocation.BACK: None,
                WieldLocation.LEGS: None,
                WieldLocation.FEET: None,
                WieldLocation.NECK: None,
                WieldLocation.MAIN_HAND_FINGER: None,
                WieldLocation.OFF_HAND_FINGER: None,
            },
        )
        needs_save = False

        # Migration: BACK was previously a list (backpack storage).
        # Restore those items to Evennia inventory and set BACK to None.
        back_value = self.slots.get(WieldLocation.BACK)
        if isinstance(back_value, list):
            for obj in back_value:
                if obj and obj.id:
                    obj.location = self.obj
            self.slots[WieldLocation.BACK] = None
            needs_save = True

        # Migration: ensure all enum slots exist in the stored dict
        for slot in WieldLocation:
            if slot not in self.slots:
                self.slots[slot] = None
                needs_save = True

        if needs_save:
            self._save()


    def _save(self):
        """Saves the current slot state to the database."""
        self.obj.attributes.add(self.save_attribute, self.slots, category="inventory")


    def _return_to_inventory(self, obj):
        """
        Put an item back in the character's contents AND in a grid slot.

        Both halves are needed. Assigning `location` directly does not fire
        at_object_receive -- see CLAUDE.md, "create_object(location=...) does
        not fire at_object_receive; move_to does" -- so the hook that would
        normally register the item in an InventoryHandler slot never runs. The
        item lands in contents with no slot, and stays that way until
        something happens to call sync().

        That was invisible while the only reader was the text grid, which
        syncs before it renders. It stops being invisible the moment a slot
        NUMBER is addressable: `unequip main hand` followed by `swap 1 5`
        would refer to an item the grid did not yet know it held.

        equip() has always done the mirror of this explicitly for the outbound
        direction (`inventory.remove_item`), so the missing inbound call was an
        asymmetry rather than a decision.
        """
        obj.location = self.obj

        inventory = getattr(self.obj, "inventory", None)

        if inventory is not None:
            inventory.add_item(obj)


    def _publish(self):
        """
        Tell any graphical client that this character's gear changed.

        Here rather than in the commands, because the EvMenu in
        systems/menus/equipment_menu.py reaches equip() and unequip() without
        passing through a command at all -- so a command-side emit would leave
        the 3D inventory pane stale for anyone using the menu, which is the
        path most players use.

        Note the asymmetry with InventoryHandler, which deliberately does NOT
        publish from its own mutators. Those run mid-move, inside
        at_object_receive, at a point where a stack merge may be about to
        delete the object being added -- a snapshot taken there would describe
        a half-applied move. The character's move hooks publish instead, after
        the move has completed.

        Imported inside the method. This package is reached from typeclass
        import time, and a module-scope import of the feed would couple the
        two systems' import order for no benefit.
        """
        from systems.statefeed import events as feed

        feed.emit_inventory(self.obj)


    def _refresh_combat(self):
        """
        Tell an in-progress fight that this character's gear changed.

        BlackoutCombatHandler snapshots weapon stats, active style, attack
        speed, and rule contributors into ndb once and only rebuilds them
        when _refresh_weapon() runs (systems/combat/combat.py). That method
        is already called by the mid-combat 'wield' action and by
        (re)entering combat, but equip()/unequip()/remove() are a second,
        independent path onto the same slots -- so a mid-fight `equip 3`
        left the combat handler swinging with the old weapon's style and
        damage until combat was broken and restarted. Calling it here from
        the single choke point every slot mutation passes through (the same
        reasoning as _publish() above) closes that gap for every caller:
        commands, the equipment EvMenu, and the 3D pane alike.

        self.obj.combat is a lazy_property that returns None outside of
        combat, so this is a no-op except mid-fight.
        """
        combat_handler = self.obj.combat
        if combat_handler is not None:
            combat_handler._refresh_weapon()


    def count_equipped(self):
        """Returns the number of items currently equipped in all slots."""
        return sum(1 for slot_obj in self.slots.values() if slot_obj is not None)


    def count_inventory(self):
        """
        Returns the number of inventory SLOTS currently occupied.

        Prefers the InventoryHandler's slot map, which counts a whole stack as
        one slot. Falls back to a raw contents count only when no handler is
        attached. Previously this always returned len(contents) while
        validate_inventory_space consulted the slot map, so the two disagreed
        for any character holding a stack -- equip() could refuse a swap the
        capacity check had just approved.
        """
        inventory = getattr(self.obj, "inventory", None)
        if inventory is not None:
            return inventory.count_used()
        return len(self.obj.contents)


    def free_inventory_slots(self):
        """Returns how many inventory slots remain open."""
        used = self.count_inventory()
        return MAX_INVENTORY_SLOTS - used


    def validate_inventory_space(self, count=1):
        """
        Ensures the character has room for `count` more inventory slots.
        Raises EquipmentError when they do not.
        """
        free = self.free_inventory_slots()
        if free < count:
            raise EquipmentError("Your inventory is completely full.")
        return True


    def is_equipped(self, obj):
        """Returns True if the given item is currently equipped in any slot."""
        slot = self.get_current_slot(obj)
        return slot is not None


    def get_current_slot(self, obj):
        """Returns the WieldLocation slot an item is equipped in, or None."""
        for slot_key, slot_obj in self.slots.items():
            if slot_obj is not None and slot_obj.id == obj.id:
                return slot_key
        return None


    def all(self):
        """Returns a list of all equipped items across all slots."""
        return [slot_obj for slot_obj in self.slots.values() if slot_obj is not None]


    def total_combat_stat_bonuses(self) -> dict:
        """
        Purpose: Sum the combat_stat_bonuses dict carried by every currently
        equipped item, across every slot.

        Entry:
            No conditions. An item with no combat_stat_bonuses attribute (a
            gathering tool, a trinket) is skipped rather than treated as
            all-zero, so it cannot zero out a key another equipped item set.

        Exit/Returns:
            dict[str, int]. A key absent from every equipped item's stat
            block is simply absent here too -- callers that need a fixed key
            set (e.g. the unarmed baseline) merge this on top of their own
            default dict rather than relying on this method to supply one.

        Module Globals:
            None.

        Methodology:
            Plain per-key accumulation over self.all(). This handler carries
            no knowledge of what the keys mean (that vocabulary belongs to
            systems/combat/constants.py) -- it only knows how to add two
            equipped items' numbers together, which is what keeps this
            module free of a systems/combat import.

        Notes/References:
            This is the seam combat.combat_profile() reads to let armour and
            an off-hand weapon contribute alongside the main weapon, instead
            of only the single held weapon.

        Author: Nick Hobar
        Creation date: 08/04/2026
        """
        totals = {}
        for equipped_obj in self.all():
            item_bonuses = getattr(equipped_obj.db, "combat_stat_bonuses", None)
            if not item_bonuses:
                continue

            for stat_key, stat_value in item_bonuses.items():
                totals[stat_key] = totals.get(stat_key, 0) + stat_value

        return totals


    def equip(self, obj):
        """
        Equips an item from the character's inventory.
        Removes it from contents (location=None) and places it in its slot.
        Displaced items are returned to inventory (location=character).
        """
        if obj not in self.obj.contents:
            raise EquipmentError("You must be carrying that to equip it.")

        use_slot = getattr(obj, "inventory_use_slot", None)
        if use_slot is None:
            raise EquipmentError("That item cannot be equipped.")

        # Tool Tier Requirement Check — dispatched through WEAPON_SKILL_MAP and
        # ARMOR_SKILL_MAP so new weapon/tool/armor categories can register
        # their required skill without re-touching this branch block
        # (data-driven tool-tier gate).
        if hasattr(obj, "db"):
            tool_type_value = obj.db.tool_type
            if tool_type_value:
                # An UNREGISTERED tool_type fails closed; a tool_type mapped to
                # None is explicitly exempt. Distinguishing the two is what
                # keeps a renamed weapon category from silently losing its
                # level check on objects already spawned in the DB.
                if tool_type_value in WEAPON_SKILL_MAP:
                    required_skill = WEAPON_SKILL_MAP[tool_type_value]
                elif tool_type_value in ARMOR_SKILL_MAP:
                    required_skill = ARMOR_SKILL_MAP[tool_type_value]
                else:
                    logger.log_err(
                        f"EquipmentHandler.equip: {obj} has unregistered "
                        f"tool_type {tool_type_value!r}; add it to "
                        f"WEAPON_SKILL_MAP or ARMOR_SKILL_MAP."
                    )
                    raise EquipmentError("You don't know how to use that.")

                if required_skill is not None:
                    req_level = obj.db.req_level or 0
                    meets_req = self.obj.skills.meets_prerequisite(required_skill, req_level)
                    if not meets_req:
                        skill_label = required_skill.capitalize()
                        raise EquipmentError(
                            f"You need a {skill_label} level of {req_level} to equip this."
                        )

        # Determine which items will be displaced
        to_unequip = []
        if use_slot == WieldLocation.TWO_HANDS:
            to_unequip = [self.slots[WieldLocation.MAIN_HAND], self.slots[WieldLocation.OFF_HAND]]
        elif use_slot in (WieldLocation.MAIN_HAND, WieldLocation.OFF_HAND):
            to_unequip = [self.slots[WieldLocation.TWO_HANDS], self.slots[use_slot]]
        else:
            to_unequip = [self.slots[use_slot]]

        displaced_count = sum(1 for o in to_unequip if o is not None)
        available = MAX_INVENTORY_SLOTS - self.count_inventory()
        # Equipping frees 1 slot (item leaves inventory), displaced items consume slots
        if displaced_count - 1 > available:
            raise EquipmentError("Your inventory is too full to swap equipment.")

        # Remove from inventory and free its slot
        obj.location = None
        if hasattr(self.obj, "inventory"):
            self.obj.inventory.remove_item(obj)

        if use_slot == WieldLocation.TWO_HANDS:
            self.slots[WieldLocation.MAIN_HAND] = None
            self.slots[WieldLocation.OFF_HAND] = None
            self.slots[use_slot] = obj
        elif use_slot in (WieldLocation.MAIN_HAND, WieldLocation.OFF_HAND):
            self.slots[WieldLocation.TWO_HANDS] = None
            self.slots[use_slot] = obj
        else:
            self.slots[use_slot] = obj

        # Return displaced items to inventory
        for old_obj in to_unequip:
            if old_obj:
                self._return_to_inventory(old_obj)

        self._save()
        self._publish()
        self._refresh_combat()


    def unequip(self, obj_or_slot):
        """
        Unequips an item and returns it to the character's inventory.
        Accepts either a WieldLocation enum or an item object.
        """
        if isinstance(obj_or_slot, WieldLocation):
            slot_key = obj_or_slot
            obj = self.slots.get(slot_key)
            if obj is None:
                raise EquipmentError("Nothing is equipped in that slot.")
        else:
            obj = obj_or_slot
            slot_key = self.get_current_slot(obj)
            if slot_key is None:
                raise EquipmentError("That item is not equipped.")

        if self.count_inventory() >= MAX_INVENTORY_SLOTS:
            raise EquipmentError("Your inventory is completely full—cannot unequip.")

        self.slots[slot_key] = None
        self._return_to_inventory(obj)
        self._save()
        self._publish()
        self._refresh_combat()
        return obj


    def remove(self, obj_or_slot):
        """
        Removes an item from its slot without returning it to inventory.
        Useful for item destruction or transfer.
        """
        if isinstance(obj_or_slot, WieldLocation):
            slot_key = obj_or_slot
            obj = self.slots.get(slot_key)
        else:
            obj = obj_or_slot
            slot_key = self.get_current_slot(obj)

        if slot_key is not None and obj is not None:
            self.slots[slot_key] = None
            self._save()
            self._publish()
            self._refresh_combat()
            return obj
        return None
