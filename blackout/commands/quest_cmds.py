"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: The `quest` command -- the player's view of what they have
             accepted, what they are doing now, and what they have finished.
"""

from evennia import CmdSet

from commands.command import Command
from commands.constants import HELP_CATEGORY_GENERAL
from systems.quests.loader import GLOBAL_QUEST_REGISTRY
from systems.ui.colors import (
    DIM_COLOR,
    RESET_COLOR,
    highlight as _hl,
    title as _title,
)



# Public constant definitions
QUEST_COMMAND_KEY = "quest"
QUEST_COMMAND_ALIASES = ["quests", "journal", "qu"]
QUEST_COMMAND_LOCKS = "cmd:all()"

QUEST_CMD_SET_KEY = "QuestCmdSet"
QUEST_CMD_SET_PRIORITY = 1

# Headings and stock lines.
HEADING_ACTIVE = "Active Quests"
HEADING_COMPLETED = "Completed Quests"

MSG_NO_QUESTS = (
    "You have no active quests. Talk to the people you meet in the wastes."
)
MSG_UNKNOWN_QUEST = "You know of no quest called '{name}'."
MSG_HINT = "Type |wquest <name>|n to see a quest's objectives."



def _resolve_quest_key(caller: object, name: str) -> str:
    """
    Purpose: Turn what a player typed into a quest key they actually hold.

    Entry:
        caller is a Character with a quests handler.
        name is the raw argument, already stripped and lowercased.

    Exit/Returns:
        Returns a quest key, or None if nothing matched.

    Module Globals:
        GLOBAL_QUEST_REGISTRY read.

    Methodology:
        Matches against the player's OWN quests only -- active first, then
        completed -- by key and by title prefix. Searching the whole registry
        would let `quest` confirm the existence of content the player has
        never encountered, which is a small spoiler and a large support
        question.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    candidates = caller.quests.active_keys() + caller.quests.completed_keys()

    for quest_key in candidates:
        if quest_key.lower() == name:
            return quest_key

    for quest_key in candidates:
        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)
        title = getattr(blueprint, "title", "") or ""

        if title.lower().startswith(name):
            return quest_key

    return None



class CmdQuest(Command):
    """
    Show your quest journal.

    Usage:
        quest
        quest <name>

    With no argument, lists every quest you have accepted and every one you
    have finished. Naming a quest shows its current objectives and how far
    along each one is.
    """
    key = QUEST_COMMAND_KEY
    aliases = QUEST_COMMAND_ALIASES
    locks = QUEST_COMMAND_LOCKS
    help_category = HELP_CATEGORY_GENERAL


    def func(self) -> None:
        """
        Purpose: Render either the journal overview or one quest's detail.

        Entry:
            self.caller is a Character with a quests handler.

        Exit/Returns:
            No conditions. Always messages the caller.

        Module Globals:
            None

        Methodology:
            Dispatches on whether an argument was given. Both branches read
            exclusively through the quests handler -- no db.active_quests
            access lives here, which is the whole reason the handler grew a
            read API.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        caller = self.caller
        name = self.args.strip().lower()

        if name:
            self._show_one(caller, name)
            return

        self._show_journal(caller)


    def _show_journal(self, caller: object) -> None:
        """
        Purpose: List every quest this character has touched.

        Entry:
            caller is a Character with a quests handler.

        Exit/Returns:
            No conditions.

        Module Globals:
            HEADING_ACTIVE, HEADING_COMPLETED, MSG_NO_QUESTS, MSG_HINT read.

        Methodology:
            An active quest shows its current step description inline, so the
            common question -- "what am I supposed to be doing" -- is answered
            without a second command. Completed quests are titles only.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        quests = caller.quests
        active = quests.active_keys()
        completed = quests.completed_keys()

        if not active and not completed:
            caller.msg(MSG_NO_QUESTS)
            return

        lines = []

        if active:
            lines.append(_title(HEADING_ACTIVE))

            for quest_key in active:
                lines.extend(self._journal_entry(quests, quest_key))

        if completed:
            if lines:
                lines.append("")

            lines.append(_title(HEADING_COMPLETED))

            for quest_key in completed:
                lines.append(f"  {DIM_COLOR}{self._title_of(quest_key)}{RESET_COLOR}")

        if active:
            lines.append("")
            lines.append(MSG_HINT)

        caller.msg("\n".join(lines))


    def _journal_entry(self, quests: object, quest_key: str) -> list:
        """
        Purpose: The two lines one active quest contributes to the journal.

        Entry:
            quests is the caller's QuestHandler. quest_key is active.

        Exit/Returns:
            Returns a list of display lines.

        Module Globals:
            None

        Methodology:
            A quest whose blueprint has gone missing -- content removed while
            a player held it -- still prints, under its raw key. Dropping it
            would leave a player unable to see, or abandon, a quest the game
            still believes they are on.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        entry = [f"  {_hl(self._title_of(quest_key))}"]
        step = quests.current_step(quest_key)

        if step is not None:
            entry.append(f"    {DIM_COLOR}{step.description}{RESET_COLOR}")

        return entry


    def _show_one(self, caller: object, name: str) -> None:
        """
        Purpose: Show one quest's description and live objective list.

        Entry:
            caller is a Character. name is the lowercased argument.

        Exit/Returns:
            No conditions.

        Module Globals:
            MSG_UNKNOWN_QUEST read.

        Methodology:
            Objective rendering belongs to the handler, not here: the tickbox
            and fraction formats are the same ones the android's progress
            dialogue needs, and a second copy would be a second thing to keep
            in step.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        quest_key = _resolve_quest_key(caller, name)

        if quest_key is None:
            caller.msg(MSG_UNKNOWN_QUEST.format(name=name))
            return

        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)
        lines = [_title(self._title_of(quest_key))]

        if blueprint is not None:
            lines.append(blueprint.description)

        lines.append("")

        if caller.quests.is_complete(quest_key):
            lines.append(f"{DIM_COLOR}Completed.{RESET_COLOR}")
            caller.msg("\n".join(lines))
            return

        step = caller.quests.current_step(quest_key)

        if step is not None:
            lines.append(_hl(step.description))

        for objective in caller.quests.objective_lines(quest_key):
            lines.append(f"  {objective}")

        caller.msg("\n".join(lines))


    @staticmethod
    def _title_of(quest_key: str) -> str:
        """The quest's display title, falling back to its raw key."""
        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)

        return getattr(blueprint, "title", None) or quest_key



class QuestCmdSet(CmdSet):
    """
    Purpose: Carries the quest journal command onto every character.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        QUEST_CMD_SET_KEY, QUEST_CMD_SET_PRIORITY read.

    Methodology:
        Added to CharacterCmdSet in commands/default_cmdsets.py alongside the
        other Blackout command sets.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    key = QUEST_CMD_SET_KEY
    priority = QUEST_CMD_SET_PRIORITY


    def at_cmdset_creation(self) -> None:
        """Populate the cmdset with the quest command."""
        self.add(CmdQuest())
