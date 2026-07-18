"""
Room

Rooms are simple containers that has no location of their own.

"""

from evennia.objects.objects import DefaultRoom
from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom
from .objects import ObjectParent
from .spawners import SPAWNER_REGISTRY, load_all_spawners


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
        during xyzgrid building. Looks up the prototype's room key
        in SPAWNER_REGISTRY and dispatches to the matching spawner, if any.
        """
        if prototype is None:
            return
        load_all_spawners()
        key = prototype.get("key")
        spawner = SPAWNER_REGISTRY.get(key)
        if spawner:
            spawner(self)