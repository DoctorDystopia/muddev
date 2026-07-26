from evennia import create_object

from items.equipment.handler import EquipmentError

# NOTE: Banking currently uses a DefaultRoom as a hidden container.
# Future plan: transition to Evennia's contrib/game_systems/storage
# (tag-based storage with location=None). The contrib currently has
# a retrieval bug (does not restore obj.location) and lacks stacking
# support. Once fixed, bank items should be tagged and set to
# location=None rather than physically placed in a room.

BANK_ROOM_ATTR = "_bank_room"
BANK_TAG = "bank_vault"
BANK_TAG_CATEGORY = "banking"
BANK_MAX_UNIQUE_KEYS = 100


class BankHandler:
    """
    Manages a character's bank storage using a hidden container room.

    Each character gets a hidden DefaultRoom created on first deposit.
    Items are moved into this room on deposit and back on withdraw,
    preserving all object state (attributes, tags, etc.).

    Supports stackable items by tracking quantity in a db attribute
    and consolidating stacks of the same item key.
    """

    def __init__(self, obj):
        self.obj = obj

    def _find_existing_stack_in_bank(self, item_key):
        """
        Find or create a stack of the same item key in the bank room.
        Returns the existing stack object.
        """
        room = self._get_bank_room()
        
        # First try to find an existing stack
        for obj in room.contents:
            if (
                getattr(obj, "is_stackable", False)
                and obj.key.lower() == item_key.lower()
            ):
                return obj
        
        return None

    def _get_bank_room(self):
        room = self.obj.db._bank_room
        if room is not None:
            try:
                _ = room.id
                return room
            except Exception:
                pass

        room = create_object(
            "typeclasses.rooms.Room",
            key=f"{self.obj.key}'s Bank Vault",
            location=None,
        )
        room.tags.add(BANK_TAG, category=BANK_TAG_CATEGORY)
        room.locks.add("get:false()")
        room.db.desc = "A secure bank vault."
        self.obj.db._bank_room = room
        return room

    def _split_stack(self, item, count, location=None):
        """
        Create a new stack object with copied attributes from the original item.

        Uses create_object() to avoid the batch_add-on-unsaved bug in
        Evennia's DefaultObject.copy(). Copies all attributes from the
        source item, then sets quantity to the split amount.
        """
        new_obj = create_object(
            item.typeclass_path,
            key=item.key,
            location=location,
        )
        for attr in item.attributes.all():
            new_obj.attributes.add(attr.key, attr.value, category=attr.category)
        new_obj.attributes.add("quantity", count)
        return new_obj

    def _copy_item_to(self, item, location):
        """Create a full-stack copy of an item at the given location."""
        return self._split_stack(item, getattr(item, "quantity", 1), location=location)

    def _has_existing_stack(self, item_key):
        """Check if bank already has a stack of this item key."""
        room = self._get_bank_room()
        return any(obj.key.lower() == item_key.lower() for obj in room.contents)

    def deposit(self, item, count=None):
        """
        Move an item from the character to the bank.

        Args:
            item: The item to deposit
            count: Quantity to deposit. None or >= item.quantity = deposit all.
                   For stackable items, count < quantity splits the stack.

        If the item is currently equipped, it is unequipped first.
        """
        if self.obj.equipment.is_equipped(item):
            self.obj.equipment.remove(item)

        # Handle stackable items
        if getattr(item, "is_stackable", False):
            item_qty = getattr(item, "quantity", 1)
            deposit_qty = count if count is not None else item_qty
            deposit_qty = min(deposit_qty, item_qty)

            if deposit_qty >= item_qty:
                # Deposit entire stack
                existing_stack = self._find_existing_stack_in_bank(item.key)
                if existing_stack:
                    existing_stack.quantity += item_qty
                    item.delete()
                    self.obj.msg(f"You deposit {item.key} (x{item_qty}) into the bank.")
                    return existing_stack
                else:
                    # Check bank capacity for new item type
                    room = self._get_bank_room()
                    if len(room.contents) >= BANK_MAX_UNIQUE_KEYS:
                        self.obj.msg("Your bank vault is full (100 item types max).")
                        return None
                    item.move_to(room, quiet=True)
                    self.obj.msg(f"You deposit {item.key} (x{item_qty}) into the bank.")
                    return item
            else:
                # Split stack - deposit partial amount
                room = self._get_bank_room()
                existing_stack = self._find_existing_stack_in_bank(item.key)
                if existing_stack:
                    existing_stack.quantity += deposit_qty
                    deposited_obj = existing_stack
                else:
                    if len(room.contents) >= BANK_MAX_UNIQUE_KEYS:
                        self.obj.msg("Your bank vault is full (100 item types max).")
                        return None
                    deposited_obj = self._split_stack(item, deposit_qty, location=room)

                item.quantity -= deposit_qty
                if item.quantity <= 0:
                    item.delete()
                self.obj.msg(f"You deposit {item.key} (x{deposit_qty}) into the bank.")
                return deposited_obj

        # Non-stackable item - store normally
        room = self._get_bank_room()
        if len(room.contents) >= BANK_MAX_UNIQUE_KEYS and not self._has_existing_stack(item.key):
            self.obj.msg("Your bank vault is full (100 item types max).")
            return None
        item.move_to(room, quiet=True)
        self.obj.msg(f"You deposit {item.key} into the bank.")
        return item

    def withdraw(self, item_id, count=1):
        """
        Retrieve a specific quantity of an item from the bank to the character's inventory.

        Checks inventory space before moving. Returns the item object
        on success or None if not found or inventory is full.

        If count exceeds available quantity, withdraws all available.
        """
        room = self._get_bank_room()

        for obj in room.contents:
            if obj.id == item_id:
                # Check available quantity
                is_stackable = getattr(obj, "is_stackable", False)
                current_quantity = getattr(obj, "quantity", 1)

                # If requested count exceeds available, withdraw all available
                if count > current_quantity:
                    count = current_quantity

                try:
                    if hasattr(self.obj, "inventory"):
                        self.obj.inventory.validate_space(count)
                    else:
                        self.obj.equipment.validate_inventory_space()
                except (EquipmentError, Exception) as err:
                    self.obj.msg(str(err))
                    return None

                if is_stackable and count > 0 and count < current_quantity:
                    # Create a partial withdrawal (new item at character)
                    withdrawal_obj = self._split_stack(obj, count, location=self.obj)

                    # Reduce bank stack
                    obj.quantity -= count

                    self.obj.msg(f"You withdraw {obj.key} (x{count}) from the bank.")
                    return withdrawal_obj
                else:
                    # Withdraw the entire stack or single item
                    obj.move_to(self.obj, quiet=True)
                    self.obj.msg(f"You withdraw {obj.key} (x{count}) from the bank.")
                    return obj

        self.obj.msg("You don't have that item stored in the bank.")
        return None

    def list_items(self):
        """Return a list of all item objects currently stored in the bank."""
        room = self._get_bank_room()
        return list(room.contents)

    def count_items(self):
        """Return the number of items currently stored in the bank."""
        room = self._get_bank_room()
        return len(room.contents)

    def get_item_by_id(self, item_id):
        """Find a stored item by its database id. Returns the object or None."""
        room = self._get_bank_room()
        for obj in room.contents:
            if obj.id == item_id:
                return obj
        return None

    def has_item(self, item_key):
        """Check if an item with the given key exists in the bank."""
        room = self._get_bank_room()
        return any(obj.key.lower() == item_key.lower() for obj in room.contents)

    def delete_bank_room(self):
        """Delete the hidden bank room and all items in it, then clear the stored reference."""
        room = self.obj.db._bank_room
        if room is not None:
            try:
                for item in list(room.contents):
                    item.delete()
                room.delete()
            except Exception:
                pass
            self.obj.db._bank_room = None
