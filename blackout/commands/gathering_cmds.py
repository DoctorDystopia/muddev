"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/05/2026
Description: Generic gathering commands injected via node CmdSets.
"""

from evennia import Command
from evennia import CmdSet
from evennia.utils import logger

from commands.constants import HELP_CATEGORY_GATHERING
from systems.progression.skills.registry import SKILL_REGISTRY



# Public constant definitions
CUTTING_SKILL_KEY = "cutting"




class CmdGatherFromNode(Command):
    """
    Purpose: Base command for harvesting a resource node with a skill.

    Subclasses supply `key`/`aliases` and a `skill_key` naming the skill to
    run. The skill class itself is resolved through SKILL_REGISTRY at call
    time, so adding a gathering skill means adding its skill module and a
    four-line subclass -- no edits here, and no import of the concrete skill
    class.
    """
    skill_key = None
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_GATHERING

    def func(self) -> None:
        """
        Purpose: Resolve the target and hand it to the configured skill.

        Entry:
            self.caller is a valid Evennia Character.
            self.args may name an object in the room or inventory.

        Exit/Returns:
            No conditions. Messages the caller on every failure path.

        Module Globals:
            SKILL_REGISTRY read.

        Methodology:
            1. Reject an empty argument.
            2. caller.search reports its own "Could not find" error.
            3. Look the skill up by key and execute it against the target.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 06/05/2026
        """
        caller = self.caller
        args = self.args.strip()

        if not args:
            caller.msg(f"What do you want to {self.cmdstring}?")
            return

        # Evennia's search prints its own standard failure message.
        target = caller.search(args)
        if not target:
            return

        skill_class = SKILL_REGISTRY.get(self.skill_key)
        if skill_class is None:
            logger.log_err(
                f"{type(self).__name__}: skill_key {self.skill_key!r} is not in "
                f"SKILL_REGISTRY."
            )
            caller.msg("You don't know how to do that.")
            return

        skill = skill_class()
        skill.execute(caller, target)



class CmdCutGatheringNode(CmdGatherFromNode):
    """
    Purpose: Harvest materials from a cutting node.
    """
    key = "cut"
    aliases = ["chop"]
    skill_key = CUTTING_SKILL_KEY



class GatheringNodeCmdSet(CmdSet):
    """
    Purpose: CmdSet to inject gathering commands to nearby players.
    """
    key = "GatheringNodeCmdSet"
    priority = 10
    duplicates = True

    def at_cmdset_creation(self) -> None:
        self.add(CmdCutGatheringNode())
