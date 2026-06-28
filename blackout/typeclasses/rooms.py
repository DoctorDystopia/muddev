"""
Room

Rooms are simple containers that has no location of their own.

"""

from evennia.objects.objects import DefaultRoom
from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom
from evennia.contrib.grid.xyzgrid.xyzgrid import get_xyzgrid
from evennia import create_object
from .objects import ObjectParent


class Room(ObjectParent, DefaultRoom):
    """
    Rooms are like any Object, except their location is None
    (which is default). They also use basetype_setup() to
    add locks so they cannot be puppeted or picked up.
    (to change that, use at_object_creation instead)

    See mygame/typeclasses/objects.py for a list of
    properties and methods available on all Objects.
    """

    pass


class GridTile(ObjectParent, XYZRoom):
    """
    The baseline 1x1 coordinate tile for the physical world of Blackout.
    """
    map_visual_range = 10  # None = full map; default is 2 tiles in each direction

    def at_object_post_spawn(self, prototype=None):
        """
        Called after this room is created/updated via a prototype
        during xyzgrid building. Spawns a RustyPole object inside
        rooms whose prototype key is "Pole clearing".
        """
        if prototype is None:
            return
        if prototype.get("key") != "Pole clearing":
            return

        from typeclasses.gathering_nodes import RustyPole

        if not any(
            obj.is_typeclass("typeclasses.gathering_nodes.RustyPole", exact=True)
            for obj in self.contents
        ):
            create_object(
                RustyPole,
                key="rusty pole",
                location=self,
            )