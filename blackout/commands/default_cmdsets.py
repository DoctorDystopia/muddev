"""
Command sets

All commands in the game must be grouped in a cmdset.  A given command
can be part of any number of cmdsets and cmdsets can be added/removed
and merged onto entities at runtime.

To create new commands to populate the cmdset, see
`commands/command.py`.

This module wraps the default command sets of Evennia; overloads them
to add/remove commands from the default lineup. You can create your
own cmdsets by inheriting from them or directly from `evennia.CmdSet`.

"""

# from blackout.commands.sittables import CmdSetSit2
from evennia import default_cmds

from commands.build_cmds import BuildCmdSet
from commands.cleanup_cmds import CleanupCmdSet
from commands.comms_cmds import CmdPage
from commands.display_cmds import DisplayCmdSet
from commands.combat_cmds import CombatCmdSet
from commands.crafting_cmds import CraftingCmdSet
from commands.drop_cmds import DropCmdSet
from commands.equipment_cmds import EquipmentCmdSet
from commands.exterminator_cmds import ExterminatorCmdSet
from commands.gathering_cmds import GatheringCmdSet
from commands.graffiti_cmds import GraffitiCmdSet
from commands.get_cmds import GetCmdSet
from commands.consumable_cmds import ConsumableCmdSet
from commands.inventory_cmds import InventoryCmdSet
from commands.login_cmds import CmdForget, CmdRemember, CmdUnconnectedResume
from commands.movement_cmds import MovementCmdSet
from commands.progression_cmds import ProgressionCmdSet
from commands.quest_cmds import QuestCmdSet
from commands.read_cmds import ReadCmdSet
from commands.speech_cmds import SpeechCmdSet


class CharacterCmdSet(default_cmds.CharacterCmdSet):
    """
    The `CharacterCmdSet` contains general in-game commands like `look`,
    `get`, etc available on in-game Character objects. It is merged with
    the `AccountCmdSet` when an Account puppets a Character.
    """

    key = "DefaultCharacter"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #
        self.add(ProgressionCmdSet())
        self.add(QuestCmdSet())
        self.add(ExterminatorCmdSet())
        self.add(EquipmentCmdSet())
        self.add(InventoryCmdSet())
        self.add(ConsumableCmdSet())
        self.add(GetCmdSet())
        # On the CHARACTER, not on each node. A cmdset that hangs on a
        # corpse is deleted with the corpse the moment it is butchered,
        # so the verb could not survive its own first use.
        self.add(GatheringCmdSet())
        self.add(DropCmdSet())
        self.add(MovementCmdSet())
        self.add(CleanupCmdSet())
        self.add(BuildCmdSet())
        self.add(ReadCmdSet())
        # Replaces Evennia's say by key. Both speech commands reach past
        # the tile of the speaker (systems/gameplay/speech/).
        self.add(SpeechCmdSet())
        self.add(GraffitiCmdSet())
        self.add(DisplayCmdSet())
        # The confirm toggle, on the character so the Godot Options button
        # works anywhere, not only beside a workbench.
        self.add(CraftingCmdSet())

        self.add(CombatCmdSet())

        # self.add(CmdSetSit2())


class AccountCmdSet(default_cmds.AccountCmdSet):
    """
    This is the cmdset available to the Account at all times. It is
    combined with the `CharacterCmdSet` when the Account puppets a
    Character. It holds game-account-specific commands, channel
    commands, etc.
    """

    key = "DefaultAccount"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #
        # Replaces Evennia's page by key: the same command, with a routing
        # tag on every line and a /reply switch.
        self.add(CmdPage())
        # The saved login. On the account, so both work OOC and IC.
        self.add(CmdRemember())
        self.add(CmdForget())


class UnloggedinCmdSet(default_cmds.UnloggedinCmdSet):
    """
    Command set available to the Session before being logged in.  This
    holds commands like creating a new account, logging in, etc.
    """

    key = "DefaultUnloggedin"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #
        # The login of a saved login. The Godot client sends it by itself.
        self.add(CmdUnconnectedResume())


class SessionCmdSet(default_cmds.SessionCmdSet):
    """
    This cmdset is made available on Session level once logged in. It
    is empty by default.
    """

    key = "DefaultSession"

    def at_cmdset_creation(self):
        """
        This is the only method defined in a cmdset, called during
        its creation. It should populate the set with command instances.

        As and example we just add the empty base `Command` object.
        It prints some info.
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #
