


from evennia import Command
from evennia import CmdSet
from evennia import InterruptCommand
from systems.statefeed import constants as feed_const

# Every line this module sends a player is about the room around you, so the
# routing tag is bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_ROOM = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_ROOM}



class CmdSit(Command):
    """
    Sit down on something.

    Usage:
      sit <target>

    """

    key = "sit"

    def func(self):
        self.obj.do_sit(self.caller)

        # args = self.args.strip()
        # if not args:
        #     self.caller.msg("Sit on what?")
        #     return
        
        # target = self.caller.search(args)
        # if not target:
        #     self.caller.msg("You don't see that here.")
        #     return
        
        # self.caller.msg(f"You sit down on {target.key}.")
        # target.msg(f"{self.caller.key} sits down on you.")



class CmdSit2(Command):
    """
    Sit down on something.

    Usage:
      sit <sittables>

    """

    key = "sit"

    def parse(self):
        self.args = self.args.strip()
        if not self.args:
            self.called.msg(("Sit on what?", _MSG_ROOM))
            raise InterruptCommand()

    def func(self):
        sittable = self.caller.search(self.args)
        if not sittable:
            self.caller.msg(("You don't see that here.", _MSG_ROOM))
            return
        try:
            sittable.do_sit(self.caller)
        except AttributeError:
            self.caller.msg(("You can't sit on that!", _MSG_ROOM))



class CmdStand(Command):
    """
    Stand up from something.

    Usage:
      stand <target>

    """

    key = "stand"
    locks = "cmd:sitsonthis()"

    def func(self):
        self.obj.do_stand(self.caller)

        # args = self.args.strip()
        # if not args:
        #     self.caller.msg("Stand up from what?")
        #     return
        
        # target = self.caller.search(args)
        # if not target:
        #     self.caller.msg("You don't see that here.")
        #     return
        
        # self.caller.msg(f"You stand up from {target.key}.")
        # target.msg(f"{self.caller.key} stands up from you.")



class CmdStand2(Command):
    """
    Stand up from something.

    Usage:
      stand <sittables>

    """

    key = "stand"

    def func(self):
        caller = self.caller
        sittable = caller.db.is_sitting
        if not sittable:
            caller.msg(("You are not sitting on anything!", _MSG_ROOM))
        else:
            sittable.do_stand(caller)



class CmdNoSitStand(Command):
    """
    Sit down or stand up
    """

    key = "sit"
    aliases = ["stand"]

    def func(self):
        if self.cmdname =="sit":
            self.msg(("You have nothing to sit on!", _MSG_ROOM))
        else:
            self.msg(("You are not sitting on anything!", _MSG_ROOM))



class CmdSetSit(CmdSet):
    """
    Command set for sitting and standing.
    """

    priority = 1

    def at_cmdset_creation(self):
        self.add(CmdSit())
        self.add(CmdStand())



class CmdSetSit2(CmdSet):
    """
    Command set for sitting and standing.
    """

    priority = 1

    def at_cmdset_creation(self):
        self.add(CmdSit2())
        self.add(CmdStand2())