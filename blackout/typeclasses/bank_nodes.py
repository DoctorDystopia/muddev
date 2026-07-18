from evennia import Command, CmdSet
from evennia import create_object
from typeclasses.objects import ObjectParent, DefaultObject
from .spawners import register_spawner


class CmdDeposit(Command):
    """
    Deposit an item from your inventory into the bank for safe keeping.
    """
    key = "deposit"
    locks = "cmd:all()"
    help_category = "Banking"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        if not args:
            caller.msg("What do you want to deposit?")
            return

        target = caller.search(args)
        if not target:
            return

        caller.bank.deposit(target)


class CmdWithdraw(Command):
    """
    Withdraw an item from the bank into your inventory.
    """
    key = "withdraw"
    locks = "cmd:all()"
    help_category = "Banking"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        if not args:
            caller.msg("What do you want to withdraw?")
            return

        caller.bank.withdraw(args)


class CmdBalance(Command):
    """
    List all items stored in your bank account.
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

        item_list = ", ".join(items)
        caller.msg(f"Your bank contains: {item_list}")


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


class BankNode(ObjectParent, DefaultObject):
    """
    A bank terminal where players can securely store and retrieve items.
    """
    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()

        self.cmdset.add(BankCmdSet, persistent=True)
        self.locks.add("get:false()")

        self.db.desc = "A bank terminal for secure item storage. Try |ydeposit|n, |ywithdraw|n, or |ybalance|n."


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
