"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: InventoryHandler — the 32-slot grid backing a character's
             carried items, including stack merging.
"""

from items import stacking
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


    def can_accept(self, obj):
        """
        Whether `obj` can enter this grid without exceeding SLOTS_TOTAL.

        Mirrors add_item's own decision tree (already-slotted, then
        mergeable stack, then free slot) so the two can never disagree
        about whether a pickup fits. Meant to be checked from
        at_pre_object_receive, before the object has moved -- add_item
        itself runs after the move and has nowhere to put a rejected
        object back.
        """
        current_slot = self.find_slot(obj)
        if current_slot >= 0:
            return True

        stack_slot = self._find_existing_stack(obj)
        if stack_slot is not None:
            return True

        return self.has_free_slots()


    def _find_first_free(self):
        for i in range(SLOTS_TOTAL):
            if self.slots.get(i) is None:
                return i
        return -1


    def _find_existing_stack(self, obj):
        """Return the slot index holding a stack `obj` may merge into, or None.

        The mergeability rule itself lives in items/stacking.py -- this used
        to compare keys case-SENSITIVELY while the bank compared them
        case-insensitively, so the same two objects could merge in a vault
        and refuse to merge in a backpack.
        """
        for i in range(SLOTS_TOTAL):
            existing = self.get_slot_content(i)
            mergeable = stacking.is_mergeable(existing, obj)

            if mergeable:
                return i

        return None


    def add_item(self, obj):
        if obj is None:
            return -1

        current_slot = self.find_slot(obj)
        if current_slot >= 0:
            return current_slot

        stack_slot = self._find_existing_stack(obj)
        if stack_slot is not None:
            existing = self.get_slot_content(stack_slot)
            # `obj` was never slotted on this path, so the delete inside merge
            # re-enters at_object_leave -> remove_item harmlessly (find_slot
            # returns -1 for it).
            stacking.merge(existing, obj)
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

        is_stackable = stacking.is_stackable(obj)

        if is_stackable and count is not None and count > 0:
            current = stacking.quantity_of(obj)

            # The slot must be cleared BEFORE the object is destroyed. delete()
            # fires Character.at_object_leave, which calls back into this very
            # routine; clearing first makes that re-entry a no-op instead of a
            # second removal against a half-updated map.
            if count >= current:
                self.slots[slot_idx] = None
                self._save()
                stacking.reduce_units(obj, current)
                return None

            stacking.reduce_units(obj, count)
            self._save()
            return obj

        self.slots[slot_idx] = None
        self._save()
        return obj


    def move_slot(self, from_idx, to_idx):
        """
        Move the item in `from_idx` to `to_idx`, swapping if the target is
        occupied.

        Swap rather than displace-and-repack: the grid is the player's to
        arrange, and any rule that shuffles a third slot to make room would
        undo an arrangement they chose deliberately.

        Stacks are NOT merged when one is dropped onto another. add_item
        already merges on pickup, so two slots holding the same stackable key
        should not coexist in the first place -- and a merge here would delete
        an object as a side effect of a cosmetic rearrange, which is a far
        worse failure than a no-op if that invariant is ever broken.

        Raises InventoryError on an out-of-range index. Returns True when
        anything changed, False when the move was a no-op.
        """
        for idx in (from_idx, to_idx):
            if idx < 0 or idx >= SLOTS_TOTAL:
                raise InventoryError(
                    f"Slot {idx + 1} is outside your inventory."
                )

        if from_idx == to_idx:
            return False

        source = self.slots.get(from_idx)
        target = self.slots.get(to_idx)

        if source is None and target is None:
            return False

        self.slots[from_idx] = target
        self.slots[to_idx] = source
        self._save()

        return True


    def all_items(self):
        result = []
        for i in range(SLOTS_TOTAL):
            obj = self.get_slot_content(i)
            if obj is not None:
                result.append((i, obj))
        return result


    def sync(self, ignore=None):
        """
        Purpose: Reconcile the slot map against what the character actually
            carries, in both directions.

        Entry:
            ignore - an object to treat as ALREADY GONE even though it is
                     still in `self.obj.contents`, or None.

        Exit/Returns:
            No return value. Saves only when something changed.

        Module Globals:
            SLOTS_TOTAL read.

        Methodology:
            `contents` is the truth and the slot map follows it: a slot
            pointing at something no longer carried is cleared, and anything
            carried without a slot is adopted into the first free one. That
            adoption is load-bearing -- `create_object(location=...)` does
            NOT fire `at_object_receive` (CLAUDE.md gotcha 5), so a spawner-
            placed loadout gets its slots here or nowhere.

            `ignore` exists because there is exactly one window where
            `contents` LIES: Evennia's move_to calls
            `source_location.at_object_leave` at step 4 but does not reassign
            `self.location` until step 5, so a departing object is still in
            contents while that hook runs. Without this, the hook's own
            `remove_item` is undone one line later by the adoption loop --
            the item is re-adopted into a free slot, a corrupted map is
            persisted mid-move, and the state-feed snapshot published from
            that hook describes an inventory the player no longer has.

            Matching is by id, not identity, because that is what the slot
            map stores.

        Notes/References:
            typeclasses/characters.py at_object_leave is the one caller that
            passes `ignore`. See evennia.objects.objects.DefaultObject.move_to
            for the full hook order.

        Author: Nick Hobar
        Creation date: 06/17/2026
        """
        needs_save = False
        ignore_id = getattr(ignore, "id", None)

        content_ids = {
            obj.id for obj in self.obj.contents if obj.id != ignore_id
        }

        for i in range(SLOTS_TOTAL):
            if self.slots[i] is not None and self.slots[i] not in content_ids:
                self.slots[i] = None
                needs_save = True

        for obj in self.obj.contents:
            if obj.id == ignore_id:
                continue
            if self.find_slot(obj) < 0:
                free = self._find_first_free()
                if free >= 0:
                    self.slots[free] = obj.id
                    needs_save = True

        if needs_save:
            self._save()
