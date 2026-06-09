"""
My Commands

Commands describe the input the account can do to the game.

"""


from commands.command import Command
from evennia import default_cmds
from evennia import CmdSet



class CommandEcho(Command):
    """
    Simple echo command

    Usage:
      echo <message>
    """

    key = "echo"

    def func(self):
        self.caller.msg(f"Echo: {self.args.strip()}")



class CommandHit(Command):
    """
    Hit a target.

    Usage:
      hit <target>
    """

    key = "hit"

    def parse(self):
        self.args = self.args.strip()
        target, *weapon = self.args.split(" with ", 1)

        if not weapon:
            target, *weapon = target.split(" ", 1)
            
        self.target = target.strip()

        if weapon:
            self.weapon = weapon[0].strip()
        else:
            self.weapon = None

    def func(self):
        args = self.args.strip()
        if not args:
            self.caller.msg("Hit what?")
            return
        
        target = self.caller.search(self.target)
        # target = self.caller.search(args)
        if not target:
            self.caller.msg("You don't see that here.")
            return
        
        weapon = None
        if self.weapon:
            weapon = self.caller.search(self.weapon)
            if weapon:
                weapon_str = f"{weapon.key}"
            else:
                weapon_str = "your bare hands"

        self.caller.msg(f"You hit {target.key} with {weapon_str}!")
        target.msg(f"{self.caller.key} hits you with {weapon_str}!")



class MyCommandGet(default_cmds.CmdGet):

    def func(self):
        super().func()
        self.caller.msg(str(self.caller.location.contents))



class CmdQuickFind(Command):
    """
    Find an item in your current location.

    Usage:
      quickfind <query>
    """

    key = "quickfind"

    def func(self):
        query = self.args.strip()

        result = self.caller.search(query)
        if not result:
            self.caller.msg("You don't see that here.")
            return
        self.caller.msg(f"Found match for {query}: {result}")



class MyCommandSet(CmdSet):

    def at_cmdset_creation(self):
        self.add(CommandEcho())
        self.add(CommandHit())
        self.add(CmdQuickFind())