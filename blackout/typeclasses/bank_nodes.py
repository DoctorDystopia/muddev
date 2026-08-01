from evennia import Command, CmdSet
from evennia import create_object
from typeclasses.objects import ObjectParent, DefaultObject
from .spawners import register_spawner
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
    help_category = "Banking"

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
    help_category = "Banking"

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
        # the name, so multi-word keys like "Rusty Scrap Metal" survive.
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
    help_category = "Banking"

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
    help_category = "Banking"

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
    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()

        self.cmdset.add(BankCmdSet, persistent=True)
        self.locks.add("get:false()")

        self.db.desc = "A bank terminal for secure item storage. Try |ybank|n for the menu, or |ydeposit|n, |ywithdraw|n, |ybalance|n."


@register_spawner("Bank")
def spawn_bank(room):
    if not any(
        obj.is_typeclass("typeclasses.bank_nodes.BankNode", exact=True)
        for obj in room.contents
    ):
        create_object(
            "typeclasses.bank_nodes.BankNode",
            key="bank terminal",
            location=room,
        )
