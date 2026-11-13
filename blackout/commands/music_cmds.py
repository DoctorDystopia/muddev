"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: The `music` command: the list of the tracks, with the state of
             each one for the player (DESIGN-0016).

             Telnet plays nothing, so the command lists and does nothing
             else. The rows come from systems/gameplay/music/detail.py,
             which the Music tab of the Godot client reads too. Thus, the
             listing and the tab cannot disagree on which track a player
             holds.
"""

from evennia import CmdSet

from commands.command import Command
from commands.constants import HELP_CATEGORY_GENERAL
from systems.gameplay.music import detail as music_detail
from systems.interface.statefeed import constants as feed_const
from systems.interface.ui.colors import (
    DIM_COLOR,
    ERROR_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
    title as _title,
)


# ─── Public constant definitions ─────────────────────────────────────────────

MUSIC_COMMAND_KEY: str = "music"
MUSIC_COMMAND_ALIASES: list = ["tracks"]
MUSIC_COMMAND_LOCKS: str = "cmd:all()"

MUSIC_CMD_SET_KEY: str = "MusicCmdSet"
MUSIC_CMD_SET_PRIORITY: int = 1

# The lines of the listing. Player-facing text, so the voice stays.
HEADING_TRACKS: str = "Music tracks ({unlocked}/{total} unlocked)"
MSG_NO_TRACKS: str = "The world has no music yet."
LINE_UNLOCKED: str = f"  {SUCCESS_COLOR}{{name}}{RESET_COLOR}"
LINE_LOCKED: str = f"  {ERROR_COLOR}{{name}}{RESET_COLOR}"
LINE_LOCKED_HINT: str = (
    f"  {ERROR_COLOR}{{name}}{RESET_COLOR} {DIM_COLOR}— {{hint}}{RESET_COLOR}"
)


# ─── Private constant definitions ────────────────────────────────────────────

# Every line this module sends a player is progression, so the routing tag
# is bound once here. The SERVER says what a line IS; the client decides
# which tab shows it.
_MSG_PROGRESSION: dict = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_PROGRESSION,
}


# ─── Private helper routines ─────────────────────────────────────────────────

def _row_line(row: dict) -> str:
    """The listing line of one track row."""
    name = row[feed_const.MUSIC_ROW_NAME]
    hint = row[feed_const.MUSIC_ROW_HINT]

    if row[feed_const.MUSIC_ROW_STATE] == feed_const.MUSIC_STATE_UNLOCKED:
        return LINE_UNLOCKED.format(name=name)

    if hint:
        return LINE_LOCKED_HINT.format(name=name, hint=hint)

    return LINE_LOCKED.format(name=name)


class CmdMusic(Command):
    """
    music - list the music tracks, and which ones you have unlocked.

    Usage:
        music

    A track unlocks when you first enter its area, or when you finish the
    content that it belongs to. A locked track shows a hint of where to
    find it.
    """

    key = MUSIC_COMMAND_KEY
    aliases = MUSIC_COMMAND_ALIASES
    locks = MUSIC_COMMAND_LOCKS
    help_category = HELP_CATEGORY_GENERAL

    def func(self) -> None:
        """
        Purpose: Print one line for each track, with its state.

        Entry:
            No argument. The caller is a Character with a music handler.

        Exit/Returns:
            Returns nothing.

        Module Globals:
            HEADING_TRACKS, MSG_NO_TRACKS read.

        Methodology:
            The rows come from music_detail.track_rows, the one owner. The
            count comes from the same rows, so the heading and the lines
            cannot disagree.

        Author: Nick Hobar
        Creation date: 11/08/2026
        """
        caller = self.caller
        rows = music_detail.track_rows(caller)

        if not rows:
            caller.msg((MSG_NO_TRACKS, _MSG_PROGRESSION))
            return

        heading = HEADING_TRACKS.format(
            unlocked=music_detail.unlocked_count(rows), total=len(rows))
        lines = [_title(heading)]

        for row in rows:
            lines.append(_row_line(row))

        caller.msg(("\n".join(lines), _MSG_PROGRESSION))


class MusicCmdSet(CmdSet):
    """
    Purpose: Carry the music listing onto every character.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        MUSIC_CMD_SET_KEY, MUSIC_CMD_SET_PRIORITY read.

    Methodology:
        Added to CharacterCmdSet in commands/default_cmdsets.py with the
        other Blackout command sets.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """

    key = MUSIC_CMD_SET_KEY
    priority = MUSIC_CMD_SET_PRIORITY

    def at_cmdset_creation(self) -> None:
        """Populate the cmdset with the music command."""
        self.add(CmdMusic())
