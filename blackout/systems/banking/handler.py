"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: BankHandler — per-character storage, implemented as a hidden
             room used as a container.
"""

from dataclasses import dataclass

from evennia import create_object

from items import stacking
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
# A vault holds this many SLOTS. One slot holds one item name, however many
# objects or units that name covers: a stack of 5000 credits and eleven
# separate scrap plates each occupy exactly one.
#
# This used to be compared against len(room.contents), which counts OBJECTS,
# so a run of non-stackables burned one slot per copy and the vault filled up
# roughly eleven times too fast. The "already stored" exemption below existed
# to paper over that; under slot counting it is simply the rule.
BANK_MAX_UNIQUE_KEYS = 100

# Why a transfer delivered nothing. Returned on the result rather than
# messaged from here: the handler is the domain layer, and a future web or
# Godot client must be able to reuse it without stripping telnet colour codes
# out of a storage routine. systems/banking/messages.py owns the wording that
# reaches a player; shop_service.py is the service this shape follows.
VAULT_FULL_ERROR = f"Your bank vault is full ({BANK_MAX_UNIQUE_KEYS} slots max)."
NOT_STORED_ERROR = "You don't have that item stored in the bank."
NOTHING_GIVEN_ERROR = "There is nothing to move."


@dataclass
class TransferResult:
    """The outcome of one deposit or withdrawal.

    success     — whether ANY units moved
    moved_count — units actually moved, which may be short of what was asked
                  for when the destination filled up partway
    item_name   — the key of the item moved, captured before any delete
    item        — the surviving object at the destination, or None. May be a
                  merged stack rather than the object passed in
    error       — why nothing (or not everything) moved; "" on full success

    Mirrors shop_service.BuyResult / SellResult deliberately, so the two
    services a client has to consume report failure the same way.
    """

    success: bool = False
    moved_count: int = 0
    item_name: str = ""
    item: object = None
    error: str = ""


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


    def _find_existing_stack_for(self, item):
        """Return the vault stack `item` may merge into, or None.

        Takes the ITEM rather than its key so the mergeability rule can live
        in items/stacking.py alongside the inventory grid's copy of it -- the
        two used to disagree about case.
        """
        room = self._get_bank_room()
        existing = stacking.find_mergeable(room.contents, item)

        return existing


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

    def _has_existing_stack(self, item_key):
        """Check if bank already has an entry under this item key.

        Deliberately NOT the stacking module's mergeability rule: this asks
        whether the vault's 100-unique-key budget is already spending a slot
        on that name, which is true for a non-stackable entry too.
        """
        room = self._get_bank_room()
        wanted = item_key.lower()

        for obj in room.contents:
            if obj.key.lower() == wanted:
                return True

        return False


    def _vault_has_room_for(self, item_key) -> bool:
        """Whether `item_key` can be stored without exceeding the slot cap.

        A name already in the vault costs no new slot, so it is always
        accepted; a new name needs a free one.
        """
        already_stored = self._has_existing_stack(item_key)

        if already_stored:
            return True

        used = self.used_slots()

        return used < BANK_MAX_UNIQUE_KEYS


    def _deposit_whole_stack(self, item, item_qty: int) -> TransferResult:
        """Move an entire stackable object into the vault."""
        item_key = item.key
        existing_stack = self._find_existing_stack_for(item)

        if existing_stack is not None:
            # merge() destroys the source, so the key is read above.
            stacking.merge(existing_stack, item)

            return TransferResult(True, item_qty, item_key, existing_stack)

        if not self._vault_has_room_for(item_key):
            return TransferResult(False, 0, item_key, None, VAULT_FULL_ERROR)

        room = self._get_bank_room()
        item.move_to(room, quiet=True)

        return TransferResult(True, item_qty, item_key, item)


    def _deposit_partial_stack(self, item, deposit_qty: int) -> TransferResult:
        """Move `deposit_qty` units off a stackable object into the vault."""
        item_key = item.key
        existing_stack = self._find_existing_stack_for(item)

        if existing_stack is not None:
            # Two existing objects, no third created: add plus reduce, not a
            # split.
            stacking.add_units(existing_stack, deposit_qty)
            stacking.reduce_units(item, deposit_qty)

            return TransferResult(True, deposit_qty, item_key, existing_stack)

        if not self._vault_has_room_for(item_key):
            return TransferResult(False, 0, item_key, None, VAULT_FULL_ERROR)

        room = self._get_bank_room()
        # split() reduces the source itself -- never decrement again.
        deposited = stacking.split(item, deposit_qty, location=room)

        return TransferResult(True, deposit_qty, item_key, deposited)


    def _deposit_single(self, item) -> TransferResult:
        """Move one non-stackable object into the vault."""
        item_key = item.key

        if not self._vault_has_room_for(item_key):
            return TransferResult(False, 0, item_key, None, VAULT_FULL_ERROR)

        room = self._get_bank_room()
        item.move_to(room, quiet=True)

        return TransferResult(True, stacking.SINGLE_UNIT, item_key, item)


    def deposit(self, item, count=None) -> TransferResult:
        """
        Purpose: Move an item, or part of a stack, from the character into
                 the vault.

        Entry:
            item is a carried object. If it is equipped it is unequipped
            first.
            count is the number of units to move, or None for all of them.
            A count at or above the stack size moves the whole stack.

        Exit/Returns:
            Returns a TransferResult. It reports failure through `error`
            rather than messaging the character -- see TransferResult.

        Module Globals:
            VAULT_FULL_ERROR read.

        Methodology:
            Three cases, one routine each: a whole stack, part of a stack,
            and a non-stackable. The dispatch is all that lives here, which
            is what took this back under the 50-line cap.

        Notes/References:
            Used to print its own success and failure lines. The messaging
            now lives in systems/banking/messages.py, so the menu and the
            `deposit` command share one wording and a non-telnet client can
            use this untouched.

        Author: Nick Hobar
        Creation date: 06/17/2026
        """
        if self.obj.equipment.is_equipped(item):
            self.obj.equipment.remove(item)

        if not stacking.is_stackable(item):
            return self._deposit_single(item)

        item_qty = stacking.quantity_of(item)
        deposit_qty = item_qty if count is None else min(count, item_qty)

        if deposit_qty >= item_qty:
            return self._deposit_whole_stack(item, item_qty)

        return self._deposit_partial_stack(item, deposit_qty)


    def _transfer_many(self, items, count, move_one) -> TransferResult:
        """
        Purpose: Draw `count` units from a run of interchangeable objects,
                 handing each slice to a single-object transfer.

        Entry:
            items is an iterable of objects the player considers the same
            thing. A stackable contributes its whole stack, a non-stackable
            one unit.
            count is the number of units to move, or None for all of them.
            move_one is (obj, take) -> TransferResult.

        Exit/Returns:
            Returns one aggregate TransferResult whose moved_count is the
            units that actually landed. Falls short of `count` when the
            destination filled up partway, and carries that refusal in
            `error` so the caller can say why it stopped.

        Module Globals:
            NOTHING_GIVEN_ERROR read.

        Methodology:
            Take as much from each object as it holds or as much as remains,
            whichever is smaller, and stop at the first refusal. moved_count
            is summed from what each transfer REPORTS moving rather than what
            was asked of it, so a partial success cannot overcount.

        Notes/References:
            Deposit and withdraw ran two copies of this walk. The only thing
            that differed was which single-object routine to call, which is
            now the `move_one` parameter.

        Author: Nick Hobar
        Creation date: 08/14/2026
        """
        targets = list(items)

        if not targets:
            return TransferResult(False, 0, "", None, NOTHING_GIVEN_ERROR)

        item_key = targets[0].key
        remaining = count
        moved = 0
        landed = None
        refusal = ""

        for item in targets:
            if remaining is not None and remaining <= 0:
                break

            available = stacking.quantity_of(item)
            take = available if remaining is None else min(remaining, available)

            outcome = move_one(item, take)

            if not outcome.success:
                refusal = outcome.error
                break

            moved += outcome.moved_count
            landed = outcome.item

            if remaining is not None:
                remaining -= outcome.moved_count

        return TransferResult(moved > 0, moved, item_key, landed, refusal)


    def deposit_many(self, items, count=None) -> TransferResult:
        """Deposit `count` units drawn from a run of interchangeable carried
        items, so eleven separate scrap plates bank in one action.

        Cannot partially fail on vault capacity: the cap exempts a key the
        vault already holds, so once the first item of a same-key run lands,
        the rest follow. It is all-or-nothing here, unlike withdraw_many,
        which fills inventory slots one object at a time and genuinely can
        stop partway.
        """
        def _move(item, take):
            return self.deposit(item, take)

        return self._transfer_many(items, count, _move)


    def _reserve_inventory_space(self, obj, count: int) -> str:
        """Confirm the character can accept this withdrawal.

        Returns "" when there is room, or the refusal text otherwise. A stack
        occupies ONE inventory slot regardless of how many units it holds, so
        reserving `count` slots for one wrongly refused any large withdrawal.
        """
        stackable = stacking.is_stackable(obj)
        slots_needed = 1 if stackable else count

        try:
            if hasattr(self.obj, "inventory"):
                self.obj.inventory.validate_space(slots_needed)
            else:
                self.obj.equipment.validate_inventory_space(slots_needed)
        except (EquipmentError, InventoryError) as err:
            return str(err)

        return ""


    def withdraw(self, item_id, count=None) -> TransferResult:
        """
        Purpose: Move a stored item, or part of a stored stack, back to the
                 character.

        Entry:
            item_id is the dbid of a stored object. Callers holding a name
            resolve it through find_item_by_name first -- matching is on id
            only here.
            count is the number of units to move, or None for all of them.
            Mirrors deposit(), which has always treated None as "the whole
            stack"; defaulting to 1 instead made the two halves of the same
            operation behave differently.

        Exit/Returns:
            Returns a TransferResult. `item` may be a merged stack rather
            than the object withdrawn, because the destination's
            at_object_receive merges same-key stackables on arrival.

        Module Globals:
            NOT_STORED_ERROR read.

        Methodology:
            Resolve, clamp the count to what is stored, check inventory space,
            then either split the stack or move the whole object.

        Notes/References:
            Used to print its own lines; see deposit() for where that went.

        Author: Nick Hobar
        Creation date: 06/17/2026
        """
        obj = self.get_item_by_id(item_id)

        if obj is None:
            return TransferResult(False, 0, "", None, NOT_STORED_ERROR)

        obj_key = obj.key
        stored_quantity = stacking.quantity_of(obj)

        # None means the whole stack; anything above it clamps down.
        if count is None or count > stored_quantity:
            count = stored_quantity

        refusal = self._reserve_inventory_space(obj, count)

        if refusal:
            return TransferResult(False, 0, obj_key, None, refusal)

        if stacking.is_stackable(obj) and 0 < count < stored_quantity:
            # split() reduces the bank stack itself.
            withdrawn = stacking.split(obj, count, location=self.obj)

            return TransferResult(True, count, obj_key, withdrawn)

        obj.move_to(self.obj, quiet=True)

        return TransferResult(True, count, obj_key, obj)


    def withdraw_many(self, items, count=None) -> TransferResult:
        """Retrieve `count` units drawn from a run of interchangeable stored
        items -- the mirror of deposit_many, needed because non-stackables
        are banked as one entry per object.

        Takes objects rather than dbids, unlike withdraw(), because every
        caller that needs a group already holds them -- from
        find_items_by_name or list_items.
        """
        def _move(item, take):
            return self.withdraw(item.id, take)

        return self._transfer_many(items, count, _move)


    def list_items(self):
        """Return a list of all item objects currently stored in the bank."""
        room = self._get_bank_room()

        return list(room.contents)


    def count_items(self):
        """Return the number of item OBJECTS currently stored in the bank.

        Not the same as used_slots(): eleven separate scrap plates are eleven
        objects in one slot. This is the object count, which is what the
        listing and most tests reason about.
        """
        room = self._get_bank_room()

        return len(room.contents)


    def used_slots(self) -> int:
        """Return how many of the vault's slots are occupied.

        One slot per distinct item name, matched case-insensitively so it
        agrees with _has_existing_stack and with the stacking rules in
        items/stacking.py. This is the number BANK_MAX_UNIQUE_KEYS caps.
        """
        room = self._get_bank_room()
        names = {obj.key.lower() for obj in room.contents}

        return len(names)


    def free_slots(self) -> int:
        """Return how many vault slots are still available."""
        used = self.used_slots()

        return max(0, BANK_MAX_UNIQUE_KEYS - used)


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
