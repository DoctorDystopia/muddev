"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: BankNode typeclass and the banking commands attached to it.
"""

from evennia import Command, CmdSet

from commands.constants import HELP_CATEGORY_BANKING
from systems.statefeed.constants import ASSET_KIND_STATION
from typeclasses.objects import ObjectParent, DefaultObject
from .spawners import register_spawner, spawn_once
from systems.menus.base_menu import start_blackout_menu


class CmdDeposit(Command):
    """
    Deposit an item from your inventory into the bank for safe keeping.

    Usage:
        deposit <item>
        deposit <item> <quantity>

    If the item is currently equipped, it will be unequipped first.
    """
    key = "deposit"
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_BANKING

    def func(self):
        caller = self.caller
        args = self.args.strip().split()

        if not args:
            caller.msg("What do you want to deposit?")
            return

        item_name = args[0]
        count = None
        if len(args) > 1 and args[1].isdigit():
            count = int(args[1])

        target = caller.search(item_name)
        if not target:
            return

        caller.bank.deposit(target, count)


class CmdWithdraw(Command):
    """
    Withdraw an item from the bank into your inventory.

    Usage:
        withdraw <item>
        withdraw <item> <quantity>
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
                caller.msg("Your bank account is empty. Nothing to withdraw.")
                return
            item_list = ", ".join(obj.key for obj in stored)
            caller.msg(f"Your bank contains: {item_list}")
            caller.msg("Use |ywithdraw <item>|n to retrieve something.")
            return

        # Trailing integer (if any) is the quantity; everything before it is
        # the name, so multi-word keys like "rusty scrap metal" survive.
        # No quantity given means the whole stack, matching deposit.
        parts = args.split()
        count = None
        if len(parts) > 1 and parts[-1].isdigit():
            count = int(parts[-1])
            parts = parts[:-1]

        item_key = " ".join(parts)

        # withdraw() matches on obj.id, so resolve the name here. Passing the
        # raw string made this command incapable of ever withdrawing anything.
        item = caller.bank.find_item_by_name(item_key)
        if item is None:
            caller.msg("You don't have that item stored in the bank.")
            return

        caller.bank.withdraw(item.id, count)


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
            caller.msg("Your bank account is empty.")
            return

        count = caller.bank.count_items()
        lines = [f"Your bank contains {count} item{'s' if count != 1 else ''}:"]
        for item in items:
            weight = getattr(item.db, "weight", None)
            value = getattr(item.db, "value", None)
            details = []
            if weight is not None:
                details.append(f"{weight}kg")
            if value is not None:
                details.append(f"{value}g")
            suffix = f" ({', '.join(details)})" if details else ""
            lines.append(f"  {item.key}{suffix}")
        caller.msg("\n".join(lines))


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
