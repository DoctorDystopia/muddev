"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/05/2026
Description: Typeclasses for gatherable resource nodes in the world.
"""

from typeclasses.objects import DefaultObject
from commands.gathering_cmds import GatheringNodeCmdSet
from systems.progression.skills.gatherables import GATHERABLE_REGISTRY
from .spawners import register_spawner, spawn_once



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
        Initializes the database attributes required for gathering by
        reading its required level, XP reward, and gatherable_key from
        GATHERABLE_REGISTRY, and injects the generic GatheringNodeCmdSet
        to expose interactions.

    Notes/References:
        GATHERABLE_REGISTRY is this node's single owner for required level
        and XP reward -- see systems/progression/skills/gatherables.py.

    Author: Nick Hobar
    Creation date: 06/05/2026
    """
    # Key into GATHERABLE_REGISTRY. Every gathering node typeclass sets its
    # own gatherable_key the same way a skill def sets its own `key`.
    gatherable_key = "rusty_pole"

    # What a graphical client may send to work this node, read by
    # systems/statefeed/serializers.py through getattr. Bare, because
    # GatheringNodeCmdSet hangs on this object.
    #
    # This lives here rather than in the client precisely because every
    # gathering node in the game today is a CUTTING node, and the next one
    # will not be. A renderer holding its own verb table would keep sending
    # `cut` at a mining node until someone remembered to edit it.
    interact_verb = "cut"


    def at_object_creation(self) -> None:
        parent_class = super()
        parent_class.at_object_creation()

        self.cmdset.add(GatheringNodeCmdSet, persistent=True)
        self.locks.add("get:false()")

        gatherable_def = GATHERABLE_REGISTRY[self.gatherable_key]
        self.db.gatherable_key = self.gatherable_key
        self.db.required_level = gatherable_def.required_level
        self.db.xp_reward = gatherable_def.xp_reward


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
        
        Author: Nick Hobar
        Creation date: 06/05/2026
        """
        is_node = True
        
        return is_node



class MetalPole(DefaultObject):
    """
    Purpose: Represents a level 10 gathering node for the Cutting skill.

    Entry:
        No conditions

    Exit/Returns:
        No conditions

    Module variables:
        None

    Methodology:
        Initializes the database attributes required for gathering by
        reading its required level, XP reward, and gatherable_key from
        GATHERABLE_REGISTRY, and injects the generic GatheringNodeCmdSet
        to expose interactions.

    Notes/References:
        GATHERABLE_REGISTRY is this node's single owner for required level
        and XP reward -- see systems/progression/skills/gatherables.py.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    # Key into GATHERABLE_REGISTRY. Every gathering node typeclass sets its
    # own gatherable_key the same way a skill def sets its own `key`.
    gatherable_key = "metal_pole"

    # What a graphical client may send to work this node, read by
    # systems/statefeed/serializers.py through getattr. Bare, because
    # GatheringNodeCmdSet hangs on this object.
    
    # This lives here rather than in the client precisely because every
    # gathering node in the game today is a CUTTING node, and the next one
    # will not be. A renderer holding its own verb table would keep sending
    # `cut` at a mining node until someone remembered to edit it.
    interact_verb = "cut"


    def at_object_creation(self) -> None:
        parent_class = super()
        parent_class.at_object_creation()

        self.cmdset.add(GatheringNodeCmdSet, persistent=True)
        self.locks.add("get:false()")

        gatherable_def = GATHERABLE_REGISTRY[self.gatherable_key]
        self.db.gatherable_key = self.gatherable_key
        self.db.required_level = gatherable_def.required_level
        self.db.xp_reward = gatherable_def.xp_reward


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
        
        Author: Nick Hobar
        Creation date: 08/22/2026
        """
        is_node = True
        
        return is_node



@register_spawner("Rusty pole clearing")
def spawn_rusty_pole(room):
    spawn_once(
        room,
        "typeclasses.gathering_nodes.RustyPole",
        key="rusty pole",
    )



@register_spawner("Metal pole clearing")
def spawn_metal_pole(room):
    spawn_once(
        room,
        "typeclasses.gathering_nodes.MetalPole",
        key="metal pole",
    )