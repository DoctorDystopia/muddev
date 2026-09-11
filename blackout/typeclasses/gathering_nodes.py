"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/05/2026
Description: Typeclasses for gatherable resource nodes in the world.
"""

from typeclasses.objects import DefaultObject
from commands.gathering_cmds import gathering_verbs
from systems.gameplay.progression.skills.gatherables import GATHERABLE_REGISTRY
from .spawners import register_spawner, spawn_once



class GatheringNode(DefaultObject):
    """
    Purpose: Anything in the world that a gathering skill can be worked on.

    Entry:
        A subclass sets `gatherable_key` to a GATHERABLE_REGISTRY key.

    Exit/Returns:
        No conditions.

    Module variables:
        GATHERABLE_REGISTRY read, to fail loudly at creation on a key that
        does not exist.

    Methodology:
        Stamps db.gatherable_key, and that single attribute is the whole of
        what makes an object a node: the skills read the registry through it,
        the commands find it by it, and so does the statefeed.

        It hangs no cmdset of its own. The gathering verbs live on the
        CHARACTER (commands/gathering_cmds.py GatheringCmdSet), because a
        cmdset on the node cannot outlive a node that a harvest consumes --
        see that class for the bug this cost.

        It no longer stamps db.required_level or db.xp_reward. Those were
        scalars, and a node now carries a LIST of yields at different levels
        for different skills -- so the registry is the only place they can
        live without two copies of the same table disagreeing. Nothing ever
        used them as the per-spawn override they were added for.

        There is also no `is_cutting_node()` here any more. A predicate per
        gathering skill meant every node typeclass had to grow a method each
        time a skill was added, to answer a question the registry already
        answers -- see gatherables.get_gatherable_for_node.

    Notes/References:
        GATHERABLE_REGISTRY is the single owner of what a node yields, to
        which skill, at what level -- see
        systems/gameplay/progression/skills/gatherables.py.

    Author: Nick Hobar
    Creation date: 09/10/2026
    """
    gatherable_key = ""

    # What a graphical client may send to work this node. Read by
    # systems/interface/statefeed/serializers.py, which builds one action per
    # skill the registry says can work this node, so a node worked by two
    # skills offers two -- and no client holds a verb table of its own.
    interact_verb = ""


    def extra_actions(self) -> list:
        """
        Purpose: One clickable verb per skill that can work this node.

        Entry:
            No conditions.

        Exit/Returns:
            Returns a list of {"command", "label"} dicts, one per skill named
            on this node's yields. Empty for an unregistered node.

        Module variables:
            GATHERABLE_REGISTRY read, through gathering_verbs.

        Methodology:
            Read from the registry rather than declared here, which is the
            whole reason `interact_verb` was not enough. Every gathering node
            in the game was a CUTTING node when that attribute was written,
            and its own comment said the next one would not be. A corpse is
            worked by two skills; a node the registry gives a third to grows a
            third button with no edit here and none in the client.

            The commands name the node explicitly rather than relying on the
            cmdset's own object, because a client sends a string and the
            player it is sent on behalf of may be standing beside two of them.

        Notes/References:
            Consumed by systems/interface/statefeed/serializers.py
            interact_actions.

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        return gathering_verbs(self)


    def at_object_creation(self) -> None:
        parent_class = super()
        parent_class.at_object_creation()

        self.locks.add("get:false()")

        # Raises on an unregistered key rather than spawning a node nobody
        # can work, which is what the old code did by indexing the registry.
        GATHERABLE_REGISTRY[self.gatherable_key]

        self.db.gatherable_key = self.gatherable_key



class RustyPole(GatheringNode):
    """
    Purpose: The level 0 gathering node for the Cutting skill.

    Notes/References:
        Its GatherableDef carries bare_hands=True, which is what lets a
        brand-new character tear the first chunk of metal out of the world
        without the axe they cannot yet make.

    Author: Nick Hobar
    Creation date: 06/05/2026
    """
    gatherable_key = "rusty_pole"



class MetalPole(GatheringNode):
    """
    Purpose: The level 10 gathering node for the Cutting skill.

    Author: Nick Hobar
    Creation date: 08/22/2026
    """
    gatherable_key = "metal_pole"



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
