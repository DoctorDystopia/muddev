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
from systems.statefeed.constants import ASSET_KIND_STATION
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


def _split_name_and_count(args):
    """
    Purpose: Split a banking command's argument into an item name and an
             optional quantity, so multi-word keys survive.

    Entry:
        args is the raw argument string, already stripped and non-empty.

    Exit/Returns:
        Returns an (item_key, count) tuple. count is an int, or None meaning
        "as many as there are" -- the same thing None has always meant to
        BankHandler.deposit and .withdraw.

    Module Globals:
        None

    Methodology:
        A trailing integer is the quantity and everything before it is the
        name, so "rusty scrap metal 5" parses correctly. A trailing "all" is
        spelled out by players often enough to accept explicitly, and means
        the same as omitting it.

    Notes/References:
        deposit used to take args[0] as the whole name, so every multi-word
        item was searched for by its first word alone.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    parts = args.split()
    count = None

    if len(parts) > 1 and parts[-1].isdigit():
        count = int(parts[-1])
        parts = parts[:-1]
    elif len(parts) > 1 and parts[-1].lower() == QUANTITY_ALL_KEYWORD:
        parts = parts[:-1]

    item_key = " ".join(parts)

    return item_key, count


def _find_carried_group(caller, item_key):
    """
    Purpose: Find every carried object a player would call `item_key`, so a
             banking command can act on the whole run of them at once.

    Entry:
        caller is the character; item_key is a player-typed name.

    Exit/Returns:
        Returns a list of carried objects sharing one key, or an empty list.
        Messages nothing -- callers phrase their own not-found text.

    Module Globals:
        None

    Methodology:
        Search the inventory quietly, which yields every match rather than
        Evennia's usual "More than one result" refusal, then narrow to the
        first match's key so a partial name never mixes two item types.

    Notes/References:
        Non-stackable items are separate objects, so eleven scrap plates are
        eleven matches. That ambiguity is exactly what the player means.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    matches = caller.search(item_key, candidates=caller.contents, quiet=True)

    if not matches:
        return []

    matched_key = matches[0].key.lower()

    return [obj for obj in matches if obj.key.lower() == matched_key]


class CmdDeposit(Command):
    """
    Deposit items from your inventory into the bank for safe keeping.

    Usage:
        deposit <item>
        deposit <item> <quantity>
        deposit <item> all

    Without a quantity, everything you are carrying that matches goes in --
    the whole stack for a stackable item, and every copy of it otherwise.

    If an item is currently equipped, it will be unequipped first.
    """
    key = "deposit"
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_BANKING

    def func(self):
        caller = self.caller
        args = self.args.strip()

        if not args:
            caller.msg(("What do you want to deposit?", _MSG_COMMERCE))
            return

        item_key, count = _split_name_and_count(args)
        targets = _find_carried_group(caller, item_key)

        if not targets:
            caller.msg((f"You aren't carrying '{item_key}'.", _MSG_COMMERCE))
            return

        result = caller.bank.deposit_many(targets, count)
        line = messages.format_transfer(result, messages.VERB_DEPOSIT)

        if line:
            caller.msg((line, _MSG_COMMERCE))


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
    key = "withdraw"
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

        item_key, count = _split_name_and_count(args)

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
