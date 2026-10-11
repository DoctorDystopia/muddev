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

from . import constants as bank_const
from . import layout as vault_layout

# NOTE: Banking currently uses a DefaultRoom as a hidden container.
# Future plan: transition to Evennia's contrib/game_systems/storage
# (tag-based storage with location=None). The contrib currently has
# a retrieval bug (does not restore obj.location) and lacks stacking
# support. Once fixed, bank items should be tagged and set to
# location=None rather than physically placed in a room.

BANK_ROOM_ATTR = "_bank_room"
# Where the vault layout lives on the character: the tabs, the slot order,
# the tab names and the placeholders. One plain dict. See layout.py.
BANK_LAYOUT_ATTR = "_bank_layout"
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
#
# A placeholder is a slot too, as in OSRS. It keeps its place for an item
# that will come back, so it spends one of these until the player releases
# it.
BANK_MAX_UNIQUE_KEYS = 100

# Why a transfer delivered nothing. Returned on the result rather than
# messaged from here: the handler is the domain layer, and a future web or
# Godot client must be able to reuse it without stripping telnet colour codes
# out of a storage routine. systems/gameplay/banking/messages.py owns the wording that
# reaches a player; shop_service.py is the service this shape follows.
VAULT_FULL_ERROR = f"Your bank vault is full ({BANK_MAX_UNIQUE_KEYS} slots max)."
NOT_STORED_ERROR = "You don't have that item stored in the bank."
NOTHING_GIVEN_ERROR = "There is nothing to move."
NO_SUCH_SLOT_ERROR = "Your vault has nothing by that name."
NO_SUCH_TAB_ERROR = "Your vault has no tab with that number."
SAME_SLOT_ERROR = "Name two different items to swap."
NOT_A_PLACEHOLDER_ERROR = "That slot holds an item, not a placeholder."


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


    def _publish(self) -> None:
        """
        Tell any graphical client that this character's carried items changed.

        Here rather than in the commands, for the same reason
        EquipmentHandler._publish is: the EvMenu in
        systems/interface/menus/banking_menu.py reaches deposit_many() without passing
        through a command at all, and that is the path most players use.

        A deposit is the one item movement the character's own move hooks
        cannot see. Character.at_object_leave publishes when an object is
        moved off the character, but the three merging deposit paths never
        move anything off it: a whole stack folded into a vault stack is
        DELETED where it stands (stacking.merge), a partial deposit into an
        existing vault stack is a pair of quantity writes, and a partial
        deposit into an empty vault builds the new stack detached and then
        drains the carried one. Evennia's delete() clears db_location by
        assignment and fires no hook, and a bare quantity write fires none
        either -- so without this call the pane kept drawing an item the
        vault already held, until some later move happened to republish.

        Withdraw deliberately does not call this. Every withdraw path ends in
        a move_to onto the character, which fires at_object_receive and
        publishes there; calling it here as well would build a second
        identical snapshot for nothing.

        Imported inside the method. This module is reached from typeclass
        import time through the character's handlers, and a module-scope
        import of the feed would couple the two systems' import order.
        """
        from evennia.utils import logger

        from systems.interface.statefeed import events as feed

        try:
            feed.emit_inventory(self.obj)
        except Exception:
            logger.log_trace()


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
        """Check if the bank already has a slot under this item key.

        This is not the mergeability rule of the stacking module. It asks if
        the slot cap already counts a slot for that name. That is true for a
        non-stackable entry too. It is also true for a placeholder: a deposit
        fills the slot of the placeholder, so it needs no free slot.
        """
        wanted = item_key.lower()
        names = vault_layout.ordered_names(self.layout())

        return wanted in names


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


    def _deposit(self, item, count=None) -> TransferResult:
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
            Private because it does NOT publish. deposit() and deposit_many()
            are the public entry points and each publishes once when the
            whole action is done; see _publish for why that matters and why
            it cannot happen per item.

            Used to print its own success and failure lines. The messaging
            now lives in systems/gameplay/banking/messages.py, so the menu and the
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


    def deposit(self, item, count=None) -> TransferResult:
        """Deposit one carried item, or part of one stack, and refresh the
        graphical client.

        A thin wrapper over _deposit so that the single-item and many-item
        entry points publish exactly once each; see _publish for why the
        publish cannot be left to the character's move hooks.
        """
        result = self._deposit(item, count)
        self._fit_layout()
        self._publish()

        return result


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

        Calls _deposit rather than deposit so the whole run publishes one
        snapshot at the end instead of one per object -- an eleven-plate
        deposit would otherwise be eleven full inventory walks.
        """
        def _move(item, take):
            return self._deposit(item, take)

        result = self._transfer_many(items, count, _move)
        self._fit_layout()
        self._publish()

        return result


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
        self._fit_layout()

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

        result = self._transfer_many(items, count, _move)
        self._fit_layout()

        return result


    def list_items(self):
        """Return every item object stored in the bank, in the order of the
        vault layout: the main tab, then tab 1, tab 2, and so on.

        The order of the main view. Thus, the menu, `withdraw` and `balance`
        list the vault in the order that the pop-up draws it. The objects of
        one name stay together, in the order the room holds them.
        """
        room = self._get_bank_room()
        by_name = {}

        for obj in room.contents:
            by_name.setdefault(obj.key.lower(), []).append(obj)

        ordered = []

        for name in vault_layout.ordered_names(self.layout()):
            ordered.extend(by_name.get(name, []))

        return ordered


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
        items/stacking.py. Each placeholder is one more slot. This is the
        number BANK_MAX_UNIQUE_KEYS caps.
        """
        names = vault_layout.ordered_names(self.layout())

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


    # ─── The vault layout: tabs, slot order, placeholders ───────────────────

    def _present_names(self) -> dict:
        """Return stored slot name -> (display key, prototype key), in the
        order the vault room holds its objects. layout.reconcile takes this.

        The prototype tag is read here, not through the statefeed's
        serializer. The handler is the domain layer, and a placeholder needs
        the key only to draw its mesh after the item is gone.
        """
        from evennia.prototypes.prototypes import PROTOTYPE_TAG_CATEGORY

        room = self._get_bank_room()
        present = {}

        for obj in room.contents:
            name = obj.key.lower()

            if name in present:
                continue

            prototype = obj.tags.get(category=PROTOTYPE_TAG_CATEGORY) or ""
            present[name] = (obj.key, str(prototype))

        return present


    def layout(self) -> vault_layout.VaultLayout:
        """
        Purpose: Return the vault layout, fitted to what the vault holds.

        Entry:
            None.

        Exit/Returns:
            Returns a VaultLayout. A change to it writes nothing. Give it to
            _save_layout to keep it.

        Module Globals:
            BANK_LAYOUT_ATTR read.

        Methodology:
            1. Read the record, and fit it to the stored objects. A new name
               goes into the viewed tab, as in OSRS.
            2. Write the record back only if the fit changed it.

        Notes/References:
            Every reader comes through here: the slot count, the order of
            list_items, the pop-up, and each layout verb. Thus, an item that
            reached the vault by any route has a slot, and an item that left
            becomes a placeholder before anything reads the layout again.

        Author: Nick Hobar
        Creation date: 10/08/2026
        """
        from evennia.utils.dbserialize import deserialize

        # deserialize, because an Attribute gives back a _SaverDict of
        # _SaverLists. Those are not dict and list, and the layout model
        # takes plain Python only. Without this, every read started empty.
        stored = self.obj.attributes.get(BANK_LAYOUT_ATTR, default=None)
        record = deserialize(stored)
        current = vault_layout.from_record(record)
        before = vault_layout.to_record(current)

        vault_layout.reconcile(current, self._present_names(), current.viewed)

        if vault_layout.to_record(current) != before:
            self._save_layout(current)

        return current


    def _fit_layout(self) -> None:
        """
        Fit the layout to the vault now, at the end of a transfer.

        A read fits the layout too, but a read can come too late. A slot
        becomes a placeholder only if the layout saw its item before the item
        left. A deposit and a withdrawal in one turn, with no read between,
        would leave no trace. A new name also takes the tab that the player
        views at the deposit, not at some later read.
        """
        self.layout()


    def _save_layout(self, current) -> None:
        """Write one layout back to its Attribute."""
        record = vault_layout.to_record(current)
        self.obj.attributes.add(BANK_LAYOUT_ATTR, record)


    def _publish_layout(self) -> None:
        """
        Send the open bank pop-up again after a layout change.

        A layout change moves no item, so emit_inventory never marks the
        pop-up. crafting_facilities.cancel_craft has the same problem and the
        same answer. Imported inside the method for the reason _publish gives.
        """
        from evennia.utils import logger

        from systems.interface.popups import service

        try:
            service.publish_if_open(self.obj)
        except Exception:
            logger.log_trace()


    def _change_layout(self, change) -> str:
        """
        Read the layout and apply `change` to it. `change` takes the layout
        and returns "" on success, or the reason it failed. On success, keep
        the layout and send the open pop-up again. Returns the reason.

        One routine for every layout verb. Thus, no verb can forget to save,
        and no verb can send a pop-up for a change that it refused.
        """
        current = self.layout()
        refusal = change(current)

        if not refusal:
            self._save_layout(current)
            self._publish_layout()

        return refusal


    def view_tab(self, index: int) -> str:
        """Look at one tab. A new item name goes into the viewed tab. Returns
        "" on success, or the reason it failed."""
        def _view(current):
            shown = vault_layout.set_view(current, index)

            return "" if shown else NO_SUCH_TAB_ERROR

        return self._change_layout(_view)


    def move_to_tab(self, needle: str, target) -> str:
        """
        Purpose: Move one slot into a tab, into a new tab, or out of its tab.

        Entry:
            needle - an item name, whole or the start of one. It may name a
                     placeholder.
            target - a tab number, or bank_const.NEW_TAB_WORD for a new tab.
                     bank_const.MAIN_TAB takes the slot out of its tab.

        Exit/Returns:
            Returns "" on success, or the reason it failed.

        Module Globals:
            NO_SUCH_SLOT_ERROR, NO_SUCH_TAB_ERROR read.

        Methodology:
            Resolve the name to a slot, turn the new-tab word into the number
            after the last tab, and give both to layout.move.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 10/08/2026
        """
        def _move(current):
            name = vault_layout.resolve(current, needle)

            if not name:
                return NO_SUCH_SLOT_ERROR

            wanted = target

            if target == bank_const.NEW_TAB_WORD:
                wanted = len(current.tabs)

            moved = vault_layout.move(current, name, wanted)

            return "" if moved else NO_SUCH_TAB_ERROR

        return self._change_layout(_move)


    def swap_slots(self, first: str, second: str) -> str:
        """Swap the places of two slots. Each name may name a placeholder.
        Returns "" on success, or the reason it failed."""
        def _swap(current):
            first_name = vault_layout.resolve(current, first)
            second_name = vault_layout.resolve(current, second)

            if not first_name or not second_name:
                return NO_SUCH_SLOT_ERROR

            if first_name == second_name:
                return SAME_SLOT_ERROR

            vault_layout.swap(current, first_name, second_name)

            return ""

        return self._change_layout(_swap)


    def rename_tab(self, index: int, text: str) -> str:
        """Give one tab a text name, or "" to show its item icon again.
        Returns "" on success, or the reason it failed."""
        def _rename(current):
            renamed = vault_layout.rename(current, index, text)

            return "" if renamed else NO_SUCH_TAB_ERROR

        return self._change_layout(_rename)


    def set_keep_placeholders(self, keep: bool) -> None:
        """Turn "always set placeholders" on or off. The placeholders that
        exist stay. Release them with release_placeholders."""
        def _set(current):
            current.keep_placeholders = bool(keep)

            return ""

        self._change_layout(_set)


    def keeps_placeholders(self) -> bool:
        """Return True when the last unit to leave leaves a placeholder."""
        return self.layout().keep_placeholders


    def release_placeholder(self, needle: str) -> str:
        """Remove one placeholder and free its slot. Returns "" on success, or
        the reason it failed."""
        def _release(current):
            name = vault_layout.resolve(current, needle)

            if not name:
                return NO_SUCH_SLOT_ERROR

            released = vault_layout.release(current, name)

            return "" if released else NOT_A_PLACEHOLDER_ERROR

        return self._change_layout(_release)


    def release_placeholders(self) -> int:
        """Remove every placeholder. Returns how many slots it freed."""
        freed = []

        def _release_all(current):
            freed.append(vault_layout.release_all(current))

            return ""

        self._change_layout(_release_all)

        return freed[0]


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

        self.obj.attributes.remove(BANK_LAYOUT_ATTR)
