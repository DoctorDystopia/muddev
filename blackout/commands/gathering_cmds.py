"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/05/2026
Description: Generic gathering commands injected via node CmdSets.
"""

import time
from evennia import Command
from evennia import CmdSet

from systems.progression.skills.handler import SkillHandler
from systems.progression.skills.skill_defs.gathering.cutting import Cutting



# Public constant definitions
CUTTING_SKILL_KEY = "cutting"




class CmdCutGatheringNode(Command):
    """
    Purpose: Generic command to harvest materials from a cutting node.
    """
    key = "cut"
    aliases = ["chop"]
    locks = "cmd:all()"

    def func(self) -> None:
        caller = self.caller
        args = self.args.strip()
        
        # 1. Check if they typed a target at all
        if not args:
            caller.msg("What do you want to cut?")
            return

        # 2. Use Evennia's robust search to find the object in the room or inventory
        target = caller.search(args)
        
        # If search() doesn't find anything, it automatically prints a standard
        # "Could not find 'X'." error to the caller, so we can just return.
        if not target:
            return
            
        # 3. Hand off the found object to the Skill logic
        cutting_skill = Cutting()
        cutting_skill.execute(caller, target)



class GatheringNodeCmdSet(CmdSet):
    """
    Purpose: CmdSet to inject gathering commands to nearby players.
    """
    key = "GatheringNodeCmdSet"
    priority = 10
    duplicates = True

    def at_cmdset_creation(self) -> None:
        self.add(CmdCutGatheringNode())