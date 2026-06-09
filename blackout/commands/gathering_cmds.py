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

# Private constant definitions
_MIN_HARVEST_COOLDOWN = 3.0



class CmdCutNode(Command):
    """
    Purpose: Generic command to harvest materials from a cutting node.
    
    Entry:
        self.caller must be a valid Character.
        self.obj must be a valid cutting node object.
    
    Exit/Returns:
        No conditions
    
    Module variables:
        None
    
    Methodology:
        Validates the target name matches the node. Checks volatile 
        cooldowns to prevent macro spam. Verifies tool presence and 
        skill prerequisites, including the node's required level. 
        Executes the gather and awards flat XP.
    
    Notes/References:
        Attached dynamically to the node's CmdSet.
    
    Author: Nick Hobar
    Creation date: 06/05/2026
    """
    key = "cut"
    aliases = ["chop"]
    locks = "cmd:all()"

    def func(self) -> None:
        caller = self.caller
        node = self.obj
        args = self.args
        
        target_name = args.strip().lower()
        node_name = node.key.lower()
        node_aliases = [alias.lower() for alias in node.aliases.all()]
        
        is_match = (target_name == node_name) or (target_name in node_aliases)
        
        if not is_match:
            caller.msg("You cannot cut that.")
            return
            
        last_harvest = caller.ndb.last_harvest_time
        current_time = time.time()
        
        if last_harvest is not None:
            time_diff = current_time - last_harvest
            is_cooling_down = time_diff < _MIN_HARVEST_COOLDOWN
            
            if is_cooling_down:
                caller.msg("You are already busy gathering.")
                return
                
        contents = caller.contents
        has_axe = False
        
        for item in contents:
            item_name = item.key.lower()
            if item_name == "axe":
                has_axe = True
                
        if not has_axe:
            caller.msg("You need an axe to cut this.")
            return
            
        cutting_skill = Cutting()
        has_unlocked = cutting_skill.get_unlock_requirements(caller)
        
        if not has_unlocked:
            caller.msg("You do not know how to cut this material.")
            return
            
        handler = SkillHandler(caller)
        req_level = node.db.required_level
        meets_req = handler.meets_prerequisite(CUTTING_SKILL_KEY, req_level)
        
        if not meets_req:
            error_msg = f"You need a Cutting level of {req_level} to cut this."
            caller.msg(error_msg)
            return
            
        cutting_skill.execute(caller, node)
        
        caller.ndb.last_harvest_time = current_time
        
        xp_reward = node.db.xp_reward
        handler.add_xp(CUTTING_SKILL_KEY, xp_reward)



class NodeCmdSet(CmdSet):
    """
    Purpose: CmdSet to inject gathering commands to nearby players.
    
    Entry:
        No conditions
    
    Exit/Returns:
        No conditions
    
    Module variables:
        None
    
    Methodology:
        Instantiates and adds the generic CmdCutNode command to the set.
    
    Notes/References:
        None
    
    Author: Nick Hobar
    Creation date: 06/05/2026
    """
    key = "NodeCmdSet"
    priority = 10
    duplicates = True

    def at_cmdset_creation(self) -> None:
        cmd = CmdCutNode()
        self.add(cmd)