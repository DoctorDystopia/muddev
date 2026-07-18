from .constants import WieldLocation, MAX_INVENTORY_SLOTS



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


    def count_equipped(self):
        """Returns the number of items currently equipped in all slots."""
        return sum(1 for slot_obj in self.slots.values() if slot_obj is not None)


    def count_inventory(self):
        """Returns the number of unequipped items in the character's inventory."""
        return len(self.obj.contents)


    def validate_inventory_space(self):
        """
        Ensures the character has room in their inventory.
        Raises EquipmentError if at MAX_INVENTORY_SLOTS.
        """
        if self.count_inventory() >= MAX_INVENTORY_SLOTS:
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

        # Tool Tier Requirement Check
        if hasattr(obj, "db") and obj.db.tool_type == "axe":
            req_level = obj.db.req_level or 0
            if not self.obj.skills.meets_prerequisite("cutting", req_level):
                raise EquipmentError(f"You need a Cutting level of {req_level} to wield this.")

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

        # Remove from inventory
        obj.location = None

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
                old_obj.location = self.obj

        self._save()


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
        obj.location = self.obj
        self._save()
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
            return obj
        return None
