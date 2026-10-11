"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/05/2026
Description: The speech commands: `say` and `yell`.

             The commands only parse a line. `Character.at_say` finds the
             listeners through `systems/gameplay/speech/hearing.py`.

             `say` is the Evennia command with a new help text. The old text
             says that a say reaches the room, and each tile is one room.
             `yell` is a say with a larger reach and its own lines. The two
             lines have the `say` message type, so both go to the Local tab.
"""

from evennia import CmdSet
from evennia.commands.default.general import CmdSay as EvenniaCmdSay

from systems.gameplay.speech import constants as speech_const


class CmdSay(EvenniaCmdSay):
    """
    speak as your character

    Usage:
      say <message>

    Talk to everyone near you: each person that you can see on your
    floor. To reach your whole area, use yell.
    """


class CmdYell(EvenniaCmdSay):
    """
    yell to your whole area

    Usage:
      yell <message>

    Everyone in your area hears you, on every floor. To talk to the
    people near you, use say.
    """

    key = "yell"
    aliases = ["shout"]

    def func(self) -> None:
        """
        Purpose: Yell one line to the area of the caller.

        Entry:
            self.caller is a character. self.args is the line.

        Exit/Returns:
            No conditions. An empty line gets a prompt.

        Module Globals:
            speech_const.YELL_EMPTY, YELL_SELF, YELL_HEARD and REACH_YELL
            read.

        Methodology:
            The steps of the Evennia `say`: `at_pre_say` can change or stop
            the line, and `at_say` sends it.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 10/05/2026
        """
        caller = self.caller

        if not self.args:
            caller.msg(speech_const.YELL_EMPTY)
            return

        speech = caller.at_pre_say(self.args)

        if not speech:
            return

        caller.at_say(speech, msg_self=speech_const.YELL_SELF,
                      msg_location=speech_const.YELL_HEARD,
                      reach=speech_const.REACH_YELL)


class SpeechCmdSet(CmdSet):
    """The speech commands. This `say` replaces the Evennia `say` by key."""

    key = "speech_cmdset"

    def at_cmdset_creation(self) -> None:
        """Add the commands."""
        self.add(CmdSay())
        self.add(CmdYell())
