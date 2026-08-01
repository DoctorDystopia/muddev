"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/05/2026
Description: Typeclasses for gatherable resource nodes in the world.
"""

from typeclasses.objects import DefaultObject
from commands.gathering_cmds import GatheringNodeCmdSet
from .spawners import register_spawner, spawn_once

    

# Public constant definitions
RUSTY_POLE_REQ_LEVEL = 0
RUSTY_POLE_XP_REWARD = 10



class RustyPole(DefaultObject):
    """
    Purpose: Represents a level 0 gathering node for the Cutting skill.
    
    Entry:
        No conditions
    
    Exit/Returns:
        No conditions
    
    Module variables:
        None
    
    Methodology:
        Initializes the database attributes required for gathering,
        sets the required level, and injects the generic GatheringNodeCmdSet 
        to expose interactions.
    
    Notes/References:
        None
    
    Author: Nick Hobar
    Creation date: 06/05/2026
    """
    
    def at_object_creation(self) -> None:
        parent_class = super()
        parent_class.at_object_creation()
        
        self.cmdset.add(GatheringNodeCmdSet, persistent=True)
        self.locks.add("get:false()")
        
        self.db.required_level = RUSTY_POLE_REQ_LEVEL
        self.db.xp_reward = RUSTY_POLE_XP_REWARD


    def is_cutting_node(self) -> bool:
        """
        Purpose: Identifies this object as a valid cutting target.
        
        Entry:
            No conditions
        
        Exit/Returns:
            Returns True unconditionally.
        
        Module variables:
            None
        
        Methodology:
            Standard identification hook.
        
        Notes/References:
            Replaces the legacy is_plant() check.
        
        Author: Nick Hobar
        Creation date: 06/05/2026
        """
        is_node = True
        
        return is_node


@register_spawner("Pole clearing")
def spawn_rusty_pole(room):
    spawn_once(
        room,
        "typeclasses.gathering_nodes.RustyPole",
        key="rusty pole",
    )