"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The Augmentation Locus typeclass (DESIGN-0015, Phase 4). A
             Locus is the place that trains: a graft on its tile pays
             AUG_LOCUS_XP_MULT times the XP of the sample. It is the gilded
             altar of OSRS Prayer. The AugBot (typeclasses/augbots.py) is a
             different machine: it restores Grit, and it trains nothing
             (Nick, 10/30/2026).

             The Locus holds no command. `graft` lives on the character
             (commands/augment_cmds.py), and it asks the room for a Locus
             through `locus_here`. Thus, one verb serves a graft anywhere
             and a graft here, and the two cannot pay differently by accident.

             The object kind `locus` (world/object_kinds.py) stands one up
             through the spawner below, as `restore_point` stands up an
             AugBot. The shape is typeclasses/augbots.py.
"""

from systems.gameplay.augmentation import constants as aug_const
from systems.interface.statefeed.constants import ASSET_KIND_STATION
from typeclasses.objects import ObjectParent, DefaultObject
from .spawners import register_spawner, spawn_once


# The model of the Locus. No model record exists yet, and the client draws
# the station family model for a key with no record.
LOCUS_ASSET_KEY: str = "augmentation_locus"


class AugmentationLocus(ObjectParent, DefaultObject):
    """
    An Augmentation Locus, the place where a graft pays more.
    """

    # How a graphical client draws this and what it may send to use it. Read
    # by systems/interface/statefeed/serializers.py through getattr. The
    # verb is `graft` with no argument: the command then lists the samples
    # that the player carries, so a click on the Locus is a prompt.
    asset_kind = ASSET_KIND_STATION
    asset_key = LOCUS_ASSET_KEY
    interact_verb = aug_const.GRAFT_COMMAND_KEY

    # The mark that `locus_here` reads. A class attribute, never a row, so
    # a renamed class reaches every Locus that already stands in the world.
    is_augmentation_locus = True

    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()

        self.locks.add("get:false()")

        self.db.desc = aug_const.AUG_LOCUS_DESC


def locus_here(character):
    """
    Purpose: Find an Augmentation Locus on the tile of a character.

    Entry:
        character is any object. It may have no location.

    Exit/Returns:
        Returns the first Locus in the room of the character, or None.

    Module Globals:
        None.

    Methodology:
        One walk of the room contents, on the class mark. A dbref row
        cannot go stale, because nothing here reads a stored path.

    Notes/References:
        `graft` is the one caller today.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    location = getattr(character, "location", None)

    if location is None:
        return None

    for obj in location.contents:
        is_locus = getattr(obj, "is_augmentation_locus", False)

        if is_locus:
            return obj

    return None


@register_spawner(aug_const.AUG_LOCUS_SPAWNER_KEY)
def spawn_locus(room):
    return spawn_once(
        room,
        "typeclasses.loci.AugmentationLocus",
        key="augmentation locus",
    )
