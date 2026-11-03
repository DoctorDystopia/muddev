"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The AugBot typeclass and the `amplify` command on it
             (DESIGN-0015, Phase 1). An AugBot restores Grit in full, at
             once and for nothing. It is the altar of OSRS Prayer. The
             Augmentation Locus, the place that trains, is Phase 4.

             The object kind `restore_point` (world/object_kinds.py) stands
             one up through the spawner below, as `bank` stands up a bank
             terminal. The shape is typeclasses/bank_nodes.py.
"""

from evennia import CmdSet

from commands.command import FacingCommand
from commands.constants import HELP_CATEGORY_AUGMENTATION
from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import pool as augmentation_pool
from systems.interface.statefeed.constants import ASSET_KIND_STATION
from typeclasses.objects import ObjectParent, DefaultObject
from .spawners import register_spawner, spawn_once


# The model of the AugBot. No model record exists yet, and the client draws
# the station family model for a key with no record.
AUGBOT_ASSET_KEY: str = "augbot"


class CmdAmplify(FacingCommand):
    """
    Restore your Grit in full at an Augmentation Bot.

    Usage:
        amplify

    Grit does not come back on its own. An AugBot refills it at once, and
    asks nothing for it.
    """
    key = aug_const.AMPLIFY_COMMAND_KEY
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_AUGMENTATION

    def func(self):
        """
        Purpose: Refill the Grit of the caller, or say that it is full.

        Entry:
            self.caller is the character that typed the line.
            self.obj is the AugBot whose cmdset holds this command.

        Exit/Returns:
            Returns nothing. The caller gets one line.

        Module Globals:
            aug_const.AMPLIFY_MESSAGE read.
            aug_const.AMPLIFY_FULL_MESSAGE read.

        Methodology:
            1. If the pool is full, say so and stop.
            2. Else, restore the pool in full and say the amplified line.

        Notes/References:
            The restore reaches the vitals bar through the pool module.
            Nothing here sends a snapshot.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        caller = self.caller
        held = augmentation_pool.current(caller)
        cap = augmentation_pool.maximum(caller)

        if held >= cap:
            caller.msg(aug_const.AMPLIFY_FULL_MESSAGE)
            return

        augmentation_pool.restore(caller)
        caller.msg(aug_const.AMPLIFY_MESSAGE)


class AugBotCmdSet(CmdSet):
    """
    CmdSet injected onto AugBot objects.
    """
    key = "AugBotCmdSet"
    priority = 10
    duplicates = True

    def at_cmdset_creation(self):
        self.add(CmdAmplify())


class AugBot(ObjectParent, DefaultObject):
    """
    An Augmentation Bot, the machine that restores Grit.
    """

    # How a graphical client draws this and what it may send to use it. Read
    # by systems/interface/statefeed/serializers.py through getattr, as the
    # bank terminal is. `amplify` is bare because AugBotCmdSet hangs on this
    # object: the owner of the cmdset is already the target.
    asset_kind = ASSET_KIND_STATION
    asset_key = AUGBOT_ASSET_KEY
    interact_verb = CmdAmplify.key

    def at_object_creation(self):
        parent_class = super()
        parent_class.at_object_creation()

        self.cmdset.add(AugBotCmdSet, persistent=True)
        self.locks.add("get:false()")

        self.db.desc = aug_const.AUGBOT_DESC


@register_spawner(aug_const.AUGBOT_SPAWNER_KEY)
def spawn_augbot(room):
    return spawn_once(
        room,
        "typeclasses.augbots.AugBot",
        key="augbot",
    )
