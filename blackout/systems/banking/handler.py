"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: BankHandler — per-character storage, implemented as a hidden
             room used as a container.
"""

from evennia import create_object

from items.equipment.handler import EquipmentError
from items.inventory.handler import InventoryError

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


class BankError(Exception):
    """Raised when a banking operation cannot be completed.

    Mirrors EquipmentError / InventoryError so every handler in the project
    signals failure the same way.
    """
    pass


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

        The copy is built DETACHED (location=None) and only moved to its
        destination once it is fully populated. That ordering is load-bearing:
        creating it directly at the destination fires at_object_receive, and
        InventoryHandler.add_item merges same-key stackables by calling
        obj.delete() on the incoming object. The half-built copy was therefore
        deleted mid-construction, and the next attribute write failed with
        "needs to have a value for field id".

        Evennia's own DefaultObject.copy() / copy_object() hit the same wall
        for this reason -- they batch_add attributes after placing the object
        -- so this stays hand-rolled deliberately.
        """
        new_obj = create_object(
            item.typeclass_path,
            key=item.key,
            location=None,
        )

        for attr in item.attributes.all():
            new_obj.attributes.add(attr.key, attr.value, category=attr.category)

        new_obj.attributes.add("quantity", count)

        # Move only after the object is complete, so any merge logic on the
        # receiving side sees a fully-formed stack.
        if location is not None:
            new_obj.move_to(location, quiet=True)

        return new_obj


    def _copy_item_to(self, item, location):
        """Create a full-stack copy of an item at the given location."""
        return self._split_stack(item, getattr(item, "quantity", 1), location=location)


    def _has_existing_stack(self, item_key):
        """Check if bank already has a stack of this item key."""
        room = self._get_bank_room()

        return any(obj.key.lower() == item_key.lower() for obj in room.contents)


    def deposit(self, item, count=None, quiet=False):
        """
        Move an item from the character to the bank.

        Args:
            item: The item to deposit
            count: Quantity to deposit. None or >= item.quantity = deposit all.
                   For stackable items, count < quantity splits the stack.
            quiet: Suppress the success message. Set by deposit_many, which
                   reports one total instead of one line per object. Failure
                   messages are never suppressed.

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
                    if not quiet:
                        self.obj.msg(f"You deposit {item.key} (x{item_qty}) into the bank.")
                    return existing_stack
                else:
                    # Check bank capacity for new item type
                    room = self._get_bank_room()
                    if len(room.contents) >= BANK_MAX_UNIQUE_KEYS:
                        self.obj.msg("Your bank vault is full (100 item types max).")
                        return None

                    item.move_to(room, quiet=True)
                    if not quiet:
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

                item_key = item.key
                item.quantity -= deposit_qty
                if item.quantity <= 0:
                    item.delete()

                if not quiet:
                    self.obj.msg(f"You deposit {item_key} (x{deposit_qty}) into the bank.")

                return deposited_obj

        # Non-stackable item - store normally
        room = self._get_bank_room()
        if len(room.contents) >= BANK_MAX_UNIQUE_KEYS and not self._has_existing_stack(item.key):
            self.obj.msg("Your bank vault is full (100 item types max).")
            return None
        
        item.move_to(room, quiet=True)
        if not quiet:
            self.obj.msg(f"You deposit {item.key} into the bank.")

        return item


    def deposit_many(self, items, count=None):
        """
        Purpose: Deposit `count` units drawn from a run of interchangeable
                 items, so a player holding eleven separate scrap plates can
                 bank them in one action instead of eleven.

        Entry:
            items is an iterable of carried objects the player considers the
            same thing. A stackable object contributes its whole stack; a
            non-stackable one contributes a single unit.
            count is the number of units to move, or None for all of them.

        Exit/Returns:
            Returns the number of units actually deposited, which is short of
            `count` if the vault filled up partway.

        Module Globals:
            None

        Methodology:
            Draw from each object in turn, taking as much as it holds or as
            much as remains to be taken, whichever is smaller, and hand each
            slice to deposit(). Per-object success messages are suppressed in
            favour of one total, since the whole point is to not print eleven
            lines.

        Notes/References:
            Non-stackables occupy one bank entry each, so a large run can hit
            BANK_MAX_UNIQUE_KEYS. deposit() explains that itself; this stops
            at the first refusal and still reports what did move.

        Author: Nick Hobar
        Creation date: 08/14/2026
        """
        targets = list(items)

        if not targets:
            return 0

        item_key = targets[0].key
        remaining = count
        moved = 0

        for item in targets:
            if remaining is not None and remaining <= 0:
                break

            available = getattr(item, "quantity", 1)
            take = available if remaining is None else min(remaining, available)

            if self.deposit(item, take, quiet=True) is None:
                break

            moved += take
            if remaining is not None:
                remaining -= take

        if moved > 0:
            self.obj.msg(f"You deposit {item_key} (x{moved}) into the bank.")

        return moved


    def withdraw(self, item_id, count=None, quiet=False):
        """
        Retrieve a specific quantity of an item from the bank to the character's inventory.

        Checks inventory space before moving. Returns the item object
        on success or None if not found or inventory is full.

        Args:
            item_id: dbid of the stored object. Callers holding a name should
                     resolve it through find_item_by_name first.
            count: Quantity to withdraw. None or >= available = withdraw all.
                   Mirrors deposit(), which has always treated None as "the
                   whole stack" -- withdraw defaulting to 1 instead made the
                   two halves of the same operation behave differently.
            quiet: Suppress the success message. Set by withdraw_many, which
                   reports one total. Failure messages are never suppressed.
        """
        room = self._get_bank_room()

        for obj in room.contents:
            if obj.id == item_id:
                # Check available quantity
                is_stackable = getattr(obj, "is_stackable", False)
                current_quantity = getattr(obj, "quantity", 1)

                # None means the whole stack; anything above it clamps down.
                if count is None or count > current_quantity:
                    count = current_quantity

                # A stack occupies ONE inventory slot regardless of how many
                # units it holds, so reserving `count` slots for it wrongly
                # refused any large withdrawal.
                slots_needed = 1 if is_stackable else count

                try:
                    if hasattr(self.obj, "inventory"):
                        self.obj.inventory.validate_space(slots_needed)
                    else:
                        self.obj.equipment.validate_inventory_space(slots_needed)
                except (EquipmentError, InventoryError) as err:
                    self.obj.msg(str(err))
                    return None

                if is_stackable and count > 0 and count < current_quantity:
                    # Create a partial withdrawal (new item at character)
                    withdrawal_obj = self._split_stack(obj, count, location=self.obj)

                    # Reduce bank stack
                    obj.quantity -= count

                    if not quiet:
                        self.obj.msg(f"You withdraw {obj.key} (x{count}) from the bank.")
                    return withdrawal_obj
                else:
                    # Withdraw the entire stack or single item
                    obj.move_to(self.obj, quiet=True)
                    if not quiet:
                        self.obj.msg(f"You withdraw {obj.key} (x{count}) from the bank.")
                    return obj

        self.obj.msg("You don't have that item stored in the bank.")

        return None


    def withdraw_many(self, items, count=None):
        """
        Purpose: Retrieve `count` units drawn from a run of interchangeable
                 stored items -- the mirror of deposit_many, needed because
                 non-stackables are banked as one entry per object.

        Entry:
            items is an iterable of stored objects the player considers the
            same thing. count is the number of units to move, or None for all.

        Exit/Returns:
            Returns the number of units actually withdrawn, which is short of
            `count` if the inventory filled up partway.

        Module Globals:
            None

        Methodology:
            Same draw-from-each-in-turn walk as deposit_many, delegating each
            slice to withdraw(), which does the inventory-space check per
            object. Stops at the first refusal and reports the running total.

        Notes/References:
            Takes objects rather than dbids, unlike withdraw(), because every
            caller that needs a group already holds the objects -- from
            find_items_by_name or list_items.

        Author: Nick Hobar
        Creation date: 08/14/2026
        """
        targets = list(items)

        if not targets:
            return 0

        item_key = targets[0].key
        remaining = count
        moved = 0

        for item in targets:
            if remaining is not None and remaining <= 0:
                break

            available = getattr(item, "quantity", 1)
            take = available if remaining is None else min(remaining, available)

            if self.withdraw(item.id, take, quiet=True) is None:
                break

            moved += take
            if remaining is not None:
                remaining -= take

        if moved > 0:
            self.obj.msg(f"You withdraw {item_key} (x{moved}) from the bank.")

        return moved


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


    def find_items_by_name(self, item_key):
        """
        Purpose: Find every stored object matching a name, so a caller can act
                 on the whole run of them at once.

        Entry:
            item_key is a player-typed name, whole or partial.

        Exit/Returns:
            Returns a list of stored objects sharing one key, or an empty list.
            Never mixes keys: a prefix that reaches two different items
            resolves to the first one's key only, because "withdraw rusty 5"
            must not pull a mix of scrap metal and metal dust.

        Module Globals:
            None

        Methodology:
            Try an exact case-insensitive key match across the vault first,
            then fall back to a prefix match, and in either case return all
            objects sharing the matched key.

        Notes/References:
            Non-stackables are stored one object per item, so the "same item"
            a player sees is generally several rows here. find_item_by_name
            wraps this for callers that only want one.

        Author: Nick Hobar
        Creation date: 08/14/2026
        """
        room = self._get_bank_room()
        needle = item_key.lower().strip()

        exact = [obj for obj in room.contents if obj.key.lower() == needle]

        if exact:
            return exact

        prefixed = [obj for obj in room.contents if obj.key.lower().startswith(needle)]

        if not prefixed:
            return []

        matched_key = prefixed[0].key.lower()

        return [obj for obj in prefixed if obj.key.lower() == matched_key]


    def find_item_by_name(self, item_key):
        """
        Find a stored item by name. Returns the object or None.

        Matches the full key case-insensitively first, then falls back to a
        prefix match so `withdraw rusty` reaches "rusty scrap metal". Callers
        that hold a name (commands) use this to obtain the id that withdraw
        expects -- withdraw itself matches on obj.id only, and passing it a
        name silently never matched anything.
        """
        matches = self.find_items_by_name(item_key)

        if not matches:
            return None

        return matches[0]


    def has_item(self, item_key):
        """Check if an item with the given key exists in the bank."""
        match = self.find_item_by_name(item_key)
        return match is not None


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
