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
        """Loads the slot storage from the database."""
        self.slots = self.obj.attributes.get(
            self.save_attribute,
            category="inventory",
            default={
                WieldLocation.MAIN_HAND: None,
                WieldLocation.OFF_HAND: None,
                WieldLocation.TWO_HANDS: None,
                WieldLocation.BODY: None,
                WieldLocation.HEAD: None,
                WieldLocation.BACK: [],
            },
        )
        # Clean up any None values in the backpack list
        self.slots[WieldLocation.BACK] = [
            obj for obj in self.slots[WieldLocation.BACK] if obj and obj.id
        ]


    def _save(self):
        """Saves the current slot state to the database."""
        self.obj.attributes.add(self.save_attribute, self.slots, category="inventory")


    def count_slots(self):
        """Calculates total items carried, treating each item as size 1."""
        slots = self.slots
        wield_usage = sum(
            1 for slot, slotobj in slots.items()
            if slot is not WieldLocation.BACK and slotobj is not None
        )
        backpack_usage = len(slots[WieldLocation.BACK])
        return wield_usage + backpack_usage


    def validate_slot_usage(self, obj):
        """Ensures the 32-slot limit is respected."""
        if self.count_slots() >= MAX_INVENTORY_SLOTS:
            raise EquipmentError("Your inventory is completely full.")
        return True


    def equip(self, obj):
        """
        Moves item from backpack to equipped slot. 
        Handles 2-handed vs 1-handed conflicts.
        """
        # Ensure it's in the backpack first
        if obj not in self.slots[WieldLocation.BACK]:
            raise EquipmentError("You must be carrying that to equip it.")

        use_slot = getattr(obj, "inventory_use_slot", WieldLocation.BACK)
        
        # Tool Tier Requirement Check 
        if hasattr(obj, "db") and obj.db.tool_type == "axe":
            req_level = obj.db.req_level or 0
            if not self.obj.skills.meets_prerequisite("cutting", req_level):
                raise EquipmentError(f"You need a Cutting level of {req_level} to wield this.")

        self.slots[WieldLocation.BACKPACK].remove(obj)
        to_backpack = []

        if use_slot == WieldLocation.TWO_HANDS:
            to_backpack = [self.slots[WieldLocation.MAIN_HAND], self.slots[WieldLocation.OFF_HAND]]
            self.slots[WieldLocation.MAIN_HAND] = None
            self.slots[WieldLocation.OFF_HAND] = None
            self.slots[use_slot] = obj
        elif use_slot in (WieldLocation.MAIN_HAND, WieldLocation.OFF_HAND):
            to_backpack = [self.slots[WieldLocation.TWO_HANDS]]
            self.slots[WieldLocation.TWO_HANDS] = None
            
            to_backpack.append(self.slots[use_slot])
            self.slots[use_slot] = obj
        else:
            to_backpack = [self.slots[use_slot]]
            self.slots[use_slot] = obj

        # Return unequipped items to the backpack
        for old_obj in to_backpack:
            if old_obj:
                self.slots[WieldLocation.BACK].append(old_obj)

        self._save()