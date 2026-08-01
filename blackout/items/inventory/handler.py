"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: InventoryHandler — the 32-slot grid backing a character's
             carried items, including stack merging.
"""

from items.equipment.constants import MAX_INVENTORY_SLOTS

SLOTS_TOTAL = MAX_INVENTORY_SLOTS
GRID_COLS = 4
GRID_ROWS = SLOTS_TOTAL // GRID_COLS


class InventoryError(Exception):
    pass


class InventoryHandler:
    save_attribute = "_inventory_slots"

    def __init__(self, obj):
        self.obj = obj
        self._load()

    def _load(self):
        self.slots = self.obj.attributes.get(
            self.save_attribute,
            category="inventory",
            default={},
        )
        needs_save = False

        for i in range(SLOTS_TOTAL):
            if i not in self.slots:
                self.slots[i] = None
                needs_save = True

        for i in range(SLOTS_TOTAL):
            item_id = self.slots.get(i)
            if item_id is not None:
                obj = self._get_item_by_id(item_id)
                if obj is None:
                    self.slots[i] = None
                    needs_save = True

        if needs_save:
            self._save()

    def _save(self):
        self.obj.attributes.add(self.save_attribute, self.slots, category="inventory")

    def _get_item_by_id(self, item_id):
        if item_id is None:
            return None
        for obj in self.obj.contents:
            if obj.id == item_id:
                return obj
        return None

    def get_slot_content(self, slot_idx):
        if slot_idx < 0 or slot_idx >= SLOTS_TOTAL:
            return None
        item_id = self.slots.get(slot_idx)
        if item_id is None:
            return None
        return self._get_item_by_id(item_id)

    def find_slot(self, obj):
        for i in range(SLOTS_TOTAL):
            if self.slots.get(i) is not None and obj is not None and self.slots[i] == obj.id:
                return i
        return -1

    def count_used(self):
        return sum(1 for i in range(SLOTS_TOTAL) if self.get_slot_content(i) is not None)

    def has_free_slots(self, count=1):
        return SLOTS_TOTAL - self.count_used() >= count

    def validate_space(self, count=1):
        if not self.has_free_slots(count):
            raise InventoryError("Your inventory is completely full.")
        return True

    def _find_first_free(self):
        for i in range(SLOTS_TOTAL):
            if self.slots.get(i) is None:
                return i
        return -1

    def _find_existing_stack(self, obj):
        if not getattr(obj, "is_stackable", False):
            return None
        for i in range(SLOTS_TOTAL):
            existing = self.get_slot_content(i)
            if existing is not None and existing.key == obj.key and getattr(existing, "is_stackable", False):
                return i
        return None

    def add_item(self, obj):
        if obj is None:
            return -1

        current_slot = self.find_slot(obj)
        if current_slot >= 0:
            return current_slot

        if getattr(obj, "is_stackable", False):
            stack_slot = self._find_existing_stack(obj)
            if stack_slot is not None:
                existing = self.get_slot_content(stack_slot)
                if existing is not None and existing.id != obj.id:
                    additional = getattr(obj, "quantity", 1)
                    existing.quantity += additional
                    obj.delete()
                    self._save()
                    return stack_slot

        free = self._find_first_free()
        if free < 0:
            raise InventoryError("Your inventory is completely full.")

        self.slots[free] = obj.id
        self._save()
        return free

    def remove_item(self, obj_or_slot, count=None):
        if isinstance(obj_or_slot, int):
            slot_idx = obj_or_slot
            obj = self.get_slot_content(slot_idx)
        else:
            obj = obj_or_slot
            slot_idx = self.find_slot(obj)

        if slot_idx < 0 or obj is None:
            return None

        is_stackable = getattr(obj, "is_stackable", False)

        if is_stackable and count is not None and count > 0:
            current = getattr(obj, "quantity", 1)
            if count >= current:
                self.slots[slot_idx] = None
                self._save()
                obj.delete()
                return None
            else:
                obj.quantity = current - count
                self._save()
                return obj
        else:
            self.slots[slot_idx] = None
            self._save()
            return obj

    def all_items(self):
        result = []
        for i in range(SLOTS_TOTAL):
            obj = self.get_slot_content(i)
            if obj is not None:
                result.append((i, obj))
        return result

    def sync(self):
        needs_save = False

        content_ids = {obj.id for obj in self.obj.contents}

        for i in range(SLOTS_TOTAL):
            if self.slots[i] is not None and self.slots[i] not in content_ids:
                self.slots[i] = None
                needs_save = True

        for obj in self.obj.contents:
            if self.find_slot(obj) < 0:
                free = self._find_first_free()
                if free >= 0:
                    self.slots[free] = obj.id
                    needs_save = True

        if needs_save:
            self._save()
