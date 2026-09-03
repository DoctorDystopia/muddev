"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: BankNode typeclass and the banking commands attached to it.
"""

from evennia import Command, CmdSet

from commands.constants import HELP_CATEGORY_BANKING
from systems.banking import messages
from systems.banking.handler import BANK_MAX_UNIQUE_KEYS, NOT_STORED_ERROR
from systems.statefeed.constants import ASSET_KIND_STATION, COMMERCE_ROLE_BANK
from typeclasses.objects import ObjectParent, DefaultObject
from .spawners import register_spawner, spawn_once
from systems.menus.base_menu import QUANTITY_ALL_KEYWORD, start_blackout_menu
from systems.statefeed import constants as feed_const

# Every line this module sends a player is a shop or a bank, so the routing
# tag is bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_COMMERCE = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_COMMERCE}

# A banking command with no argument. Phrased as a question rather than as
# usage, which is what `deposit` has always asked.
NOTHING_NAMED_ERROR = "What do you want to deposit?"

# The verbs these commands answer to. Named because the bank menu's `_default`
# option has to recognise one of them by string -- see banking_menu
# ._parse_deposit_request on why the menu must parse a command at all -- and a
# literal there would be a second owner of a Command's key.
DEPOSIT_COMMAND_KEY = "deposit"
WITHDRAW_COMMAND_KEY = "withdraw"

# The quantity below which a slot-addressed deposit means the clicked slot
# alone rather than the whole group. Named so the rule reads the same here as
# shop_service._MIN_SELL_COUNT makes it read there.
_MIN_DEPOSIT_COUNT = 1


def _bankable_candidates(caller):
    """
    Purpose: List every object a deposit may reach, carried or worn.

    Entry:
        caller is the character.

    Exit/Returns:
        Returns a list of objects: the character's contents, followed by
        whatever is equipped.

    Module Globals:
        None

    Methodology:
        EquipmentHandler.equip holds an equipped object at location=None, so
        it is not in caller.contents and no search over contents can find it.
        That is why CmdDeposit's promise to unequip first was untrue for as
        long as it was written, and why banking_menu._equipped_marker
        decorated a list that could never contain an equipped item.

        Carried first, so a player holding a spare of something they are
        wearing banks the loose one before the worn one. Equipped items are
        appended rather than merged in slot order because the order here IS
        the order _release_for_deposit consumes them in.

    Notes/References:
        Selling deliberately does NOT widen this way. An unequipped deposit
        is undone by `withdraw`; a sale at the miser factor is not, and gear
        is what a misclick most wants back.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    candidates = list(caller.contents)

    equipment = getattr(caller, "equipment", None)

    if equipment is not None:
        candidates.extend(obj for obj in equipment.all() if obj is not None)

    return candidates


def _find_carried_group(caller, item_key):
    """
    Purpose: Find every object a player would call `item_key`, carried or
             worn, so a banking command can act on the whole run of them at
             once.

    Entry:
        caller is the character; item_key is a player-typed name.

    Exit/Returns:
        Returns a list of objects sharing one key, or an empty list. Messages
        nothing -- callers phrase their own not-found text.

    Module Globals:
        None

    Methodology:
        Search quietly, which yields every match rather than Evennia's usual
        "More than one result" refusal, then narrow to the first match's key
        so a partial name never mixes two item types.

        The candidate list is _bankable_candidates rather than
        caller.contents, which is what makes CmdDeposit's docstring true.

    Notes/References:
        Non-stackable items are separate objects, so eleven scrap plates are
        eleven matches. That ambiguity is exactly what the player means.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    matches = caller.search(
        item_key, candidates=_bankable_candidates(caller), quiet=True)

    if not matches:
        return []

    matched_key = matches[0].key.lower()

    return [obj for obj in matches if obj.key.lower() == matched_key]


def _release_for_deposit(caller, targets):
    """
    Purpose: Take anything equipped out of its slot before it is banked.

    Entry:
        caller is the character; targets is the list _find_carried_group or
        resolve_carried_item produced.

    Exit/Returns:
        Returns the same list. Never raises: an object that is not equipped
        is left exactly as it was.

    Module Globals:
        None

    Methodology:
        EquipmentHandler.remove, NOT unequip. unequip returns the object to
        the inventory and raises at 32/32 (handler.py), so `deposit sword`
        with a full bag would fail -- absurd, when the deposit is about to
        free a slot. remove clears the slot and leaves the object at
        location=None, which is where BankHandler wants it anyway.

        The round trip through inventory is the thing that manufactures the
        failure, so it is the thing that is skipped.

    Notes/References:
        This is what makes CmdDeposit's "If an item is currently equipped, it
        will be unequipped first" true. It was written before
        EquipmentHandler held equipped objects off-inventory and was never
        correct until 09/02/2026.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    equipment = getattr(caller, "equipment", None)

    if equipment is None:
        return targets

    for obj in targets:
        if equipment.is_equipped(obj):
            equipment.remove(obj)

    return targets


def _units_wanted(count):
    """Map a parsed quantity onto what BankHandler's transfers understand.

    They are three-valued here and two-valued there: split_item_and_count
    distinguishes an explicit "all" from an omitted quantity, because the two
    reach different SETS of objects, but once the target list is chosen both
    mean "as many units as that list holds" -- which is what None has always
    meant to deposit_many and withdraw_many.
    """
    if count == QUANTITY_ALL_KEYWORD:
        return None

    return count


def _slot_targets(caller, item, count):
    """
    Purpose: Choose what a slot-addressed deposit acts on.

    Entry:
        item  - the object in the slot the player named.
        count - an int, QUANTITY_ALL_KEYWORD, or None for omitted.

    Exit/Returns:
        Returns a list of objects, slot-ascending when it is a group.

    Module Globals:
        None.

    Methodology:
        THE CLICKED SLOT WINS FOR ONE, THE GROUP WINS FOR MORE -- the same
        rule shop_service._entry_for_request encodes, and it has to be the
        same or Sell 1 and Deposit 1 would disagree about which of eight
        identical chunks they mean.

        An omitted quantity and an explicit 1 both mean "what is in that
        slot". Anything larger, and `all`, walk every carried copy from the
        lowest slot up, because a player asking for three of eight is not
        naming three slots and ascending order is the only one they can see.

    Notes/References:
        The group never contains an equipped object -- carried_group reads the
        inventory handler, and equipped items are held at location=None. Only
        the NAME form reaches worn gear, and that form takes all of it.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    from commands.inventory_cmds import carried_group

    single = count is None or count == _MIN_DEPOSIT_COUNT

    if single and count != QUANTITY_ALL_KEYWORD:
        return [item]

    return carried_group(caller, item)


def perform_deposit(caller, args):
    """
    Purpose: Parse, execute and report one slot- or name-addressed deposit.

    Entry:
        caller is the character; args is the raw argument, e.g. "7", "7 3",
        "7 all", "rusty scrap metal 5".

    Exit/Returns:
        Returns True when anything was banked. Messages the caller on every
        exit, so no caller needs a second refusal line.

    Module Globals:
        _MSG_COMMERCE read.

    Methodology:
        THERE ARE TWO WAYS IN, and this is why they cannot drift.
        EvMenuCmdSet is `mergetype="Replace"` with `no_objs=True`, so while
        the bank menu is open nothing reaches the command parser -- not even
        CmdDeposit on the terminal the menu was opened from. A graphical
        client that clicked the terminal and then right-clicked an item would
        have hit "Invalid choice". So this routine serves CmdDeposit and the
        deposit node's `_default` option both.

        A first token that parses as a slot number resolves through
        resolve_carried_item and acts on THAT OBJECT ALONE. The
        name-addressed behaviour -- every carried copy of that name -- is
        untouched. There was no ambiguity to trade away: `deposit 7` used to
        search for an item literally named "7" and find nothing, so the slot
        form takes a form that has never worked.

    Notes/References:
        systems/shop/shop_service.perform_sell is the same shape for the same
        reason, and the two are deliberately readable side by side.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    from commands.inventory_cmds import (
        parse_slot_number,
        resolve_carried_item,
        split_item_and_count,
    )

    item_key, count = split_item_and_count(args.strip())

    if not item_key:
        caller.msg((NOTHING_NAMED_ERROR, _MSG_COMMERCE))
        return False

    if parse_slot_number(item_key) >= 0:
        _index, item = resolve_carried_item(caller, item_key)

        if item is None:
            return False

        targets = _slot_targets(caller, item, count)
    else:
        targets = _find_carried_group(caller, item_key)

        if not targets:
            caller.msg((f"You aren't carrying '{item_key}'.", _MSG_COMMERCE))
            return False

    _release_for_deposit(caller, targets)

    result = caller.bank.deposit_many(targets, _units_wanted(count))
    line = messages.format_transfer(result, messages.VERB_DEPOSIT)

    if line:
        caller.msg((line, _MSG_COMMERCE))

    return bool(result.success)


class CmdDeposit(Command):
    """
    Deposit items from your inventory into the bank for safe keeping.

    Usage:
        deposit <slot>
        deposit <slot> <quantity>
        deposit <slot> all
        deposit <item name> [quantity|all]

    Slot numbers are the ones `inventory` prints, and name one stack. A name
    banks everything you are carrying that matches -- the whole stack for a
    stackable item, and every copy of it otherwise.

    If an item is currently equipped, it will be unequipped first.
    """
    key = DEPOSIT_COMMAND_KEY
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_BANKING

    def func(self):
        perform_deposit(self.caller, self.args)


class CmdWithdraw(Command):
    """
    Withdraw items from the bank into your inventory.

    Usage:
        withdraw <item>
        withdraw <item> <quantity>
        withdraw <item> all

    Without a quantity, everything stored under that name comes out, as far
    as your inventory has room for.
    """
    key = WITHDRAW_COMMAND_KEY
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_BANKING

    def func(self):
        caller = self.caller
        args = self.args.strip()

        if not args:
            stored = caller.bank.list_items()
            if not stored:
                caller.msg(
                    ("Your bank account is empty. Nothing to withdraw.", _MSG_COMMERCE))
                return
            # dict.fromkeys, not set(): one entry per key, listing order kept.
            item_list = ", ".join(dict.fromkeys(obj.key for obj in stored))
            caller.msg((f"Your bank contains: {item_list}", _MSG_COMMERCE))
            caller.msg(
                ("Use |ywithdraw <item>|n to retrieve something.", _MSG_COMMERCE))
            return

        from commands.inventory_cmds import split_item_and_count

        item_key, count = split_item_and_count(args)
        count = _units_wanted(count)

        # A slot number is meaningless here, deliberately: `withdraw` targets
        # the VAULT, which has no grid and no slot numbers. The graphical
        # client has nothing to click, which is why withdraw keeps the text
        # menu and gets no per-row action.

        # withdraw() matches on obj.id, so resolve the name here. Passing the
        # raw string made this command incapable of ever withdrawing anything.
        # Resolving to every match, not just the first, is what lets a run of
        # non-stackables come out in one command.
        items = caller.bank.find_items_by_name(item_key)
        if not items:
            caller.msg((NOT_STORED_ERROR, _MSG_COMMERCE))
            return

        result = caller.bank.withdraw_many(items, count)
        line = messages.format_transfer(result, messages.VERB_WITHDRAW)

        if line:
            caller.msg((line, _MSG_COMMERCE))


class CmdBalance(Command):
    """
    List all items stored in your bank account.

    Usage:
        balance
    """
    key = "balance"
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_BANKING

    def func(self):
        caller = self.caller
        items = caller.bank.list_items()

        if not items:
            caller.msg(("Your bank account is empty.", _MSG_COMMERCE))
            return

        count = caller.bank.count_items()
        used = caller.bank.used_slots()
        plural = "s" if count != 1 else ""
        lines = [
            f"Your bank contains {count} item{plural} "
            f"in {used}/{BANK_MAX_UNIQUE_KEYS} slots:"
        ]

        # Non-stackables are stored one object per item, so listing them raw
        # printed the same line eleven times. Total by key instead.
        totals = {}
        for item in items:
            weight = getattr(item.db, "weight", None)
            value = getattr(item.db, "value", None)
            details = []
            if weight is not None:
                details.append(f"{weight}kg")
            if value is not None:
                details.append(f"{value}g")
            suffix = f" ({', '.join(details)})" if details else ""
            label = f"{item.key}{suffix}"
            totals[label] = totals.get(label, 0) + getattr(item, "quantity", 1)

        for label, quantity in totals.items():
            amount = f" x{quantity}" if quantity > 1 else ""
            lines.append(f"  {label}{amount}")

        caller.msg(("\n".join(lines), _MSG_COMMERCE))


class CmdBank(Command):
    """
    Open the banking menu to deposit, withdraw, and browse items.

    Usage:
        bank
    """
    key = "bank"
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_BANKING

    def func(self):
        caller = self.caller
        start_blackout_menu(caller, "systems.menus.banking_menu", startnode="start")


class BankCmdSet(CmdSet):
    """
    CmdSet injected onto BankNode objects.
    """
    key = "BankCmdSet"
    priority = 10
    duplicates = True

    def at_cmdset_creation(self):
        self.add(CmdDeposit())
        self.add(CmdWithdraw())
        self.add(CmdBalance())
        self.add(CmdBank())


class BankNode(ObjectParent, DefaultObject):
    """
    A bank terminal where players can securely store and retrieve items.
    """

    # How a graphical client draws this and what it may send to use it. Read
    # by systems/statefeed/serializers.py through getattr. `bank` is bare
    # because BankCmdSet hangs on this object -- the cmdset's owner is already
    # the target. Without these the terminal is served as a generic item and a
    # client offers `get`, on a thing that carries `get:false()`.
    asset_kind = ASSET_KIND_STATION
    asset_key = "bank_terminal"
    interact_verb = CmdBank.key

    # What standing at this terminal lets you do with what you are carrying.
    # Read by systems/statefeed/commerce.py through getattr, the same route
    # the three attributes above take.
    commerce_role = COMMERCE_ROLE_BANK

    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()

        self.cmdset.add(BankCmdSet, persistent=True)
        self.locks.add("get:false()")

        self.db.desc = "A bank terminal for secure item storage. Try |ybank|n for the menu, or |ydeposit|n, |ywithdraw|n, |ybalance|n."


@register_spawner("Bank")
def spawn_bank(room):
    spawn_once(
        room,
        "typeclasses.bank_nodes.BankNode",
        key="bank terminal",
    )
