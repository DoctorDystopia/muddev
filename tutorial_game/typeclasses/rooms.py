"""
Room

Rooms are simple containers that has no location of their own.

"""

from evennia.objects.objects import DefaultRoom

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

    def at_object_creation(self):
        # super().at_object_creation()
        
        self.db.is_dark = False

    def get_room_stats(self):
        """
        Get the main stats of this room.
        """

        is_dark = self.db.is_dark

        return print(f"Is Dark: {is_dark}")

    pass
