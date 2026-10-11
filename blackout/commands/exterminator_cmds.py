"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: The `task` command of the Exterminator skill.

             `task` shows the task. With a Task Writ in the bag, a client
             that draws pop-ups gets the task pop-up. Every other client
             gets text. `task new` takes a task from a Preceptor here.
             `task skip` drops the task for points. `task writ` gets a new
             Task Writ from a Preceptor here.

             The command only parses. ExterminatorHandler owns the task, and
             systems/gameplay/exterminator/service.py owns the work of a
             Preceptor. The Preceptor dialogue calls the same service.
             DESIGN-0012, Phase 2.
"""

from evennia import CmdSet, Command

from commands.constants import HELP_CATEGORY_PROGRESSION
from systems.gameplay.exterminator import constants as ext_const
from systems.gameplay.exterminator import service
from systems.gameplay.exterminator.cards import card_lines
from systems.interface.statefeed import constants as feed_const



_MSG_PROGRESSION = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_PROGRESSION}

# The menu that a session with no pop-up picks from.
_PICK_MENU_MODULE: str = "systems.interface.menus.exterminator_pick_menu"

_TASK_CMD_SET_KEY: str = "exterminator_cmdset"



class CmdTask(Command):
    """
    show or change your Exterminator task

    Usage:
      task
      task new [preceptor]
      task skip
      task writ [preceptor]
      task pick [n]

    A Preceptor gives you a task: kill a count of one kind of creature.
    Each kill on your task gives Exterminator XP. A finished task gives
    points. At the start of a task and at each third of it, you pick one
    buff from three cards. A buff works only against your task creatures,
    and it ends with the task.

    task              - show your task, your streak, and your points
    task new          - take a task from a Preceptor here
    task skip         - drop your task for points. Your streak ends.
    task writ         - get a new Task Writ from a Preceptor here
    task pick         - show the cards of a waiting pick
    task pick <n>     - pick card n
    """

    key = ext_const.TASK_COMMAND_KEY
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_PROGRESSION

    def func(self) -> None:
        """
        Purpose: Send the subcommand to its routine.

        Entry:
            self.caller is a Character. self.args is the rest of the line.

        Exit/Returns:
            No conditions.

        Module Globals:
            ext_const.TASK_ARG_* read.

        Methodology:
            The first word picks the subcommand from a table. The rest is
            the Preceptor name, for `new` and `writ`. No word shows the task.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        words = self.args.strip().split(None, 1)
        verb = words[0].lower() if words else ""
        rest = words[1] if len(words) > 1 else ""
        routes = {
            "": self._show,
            ext_const.TASK_ARG_NEW: self._new,
            ext_const.TASK_ARG_SKIP: self._skip,
            ext_const.TASK_ARG_WRIT: self._writ,
            ext_const.TASK_ARG_PICK: self._pick,
        }
        route = routes.get(verb)

        if route is None:
            self._say(ext_const.MSG_TASK_USAGE)
            return

        route(rest)


    def _say(self, text: str) -> None:
        """Send one line to the caller, with the progression type."""
        self.caller.msg((text, _MSG_PROGRESSION))


    def _show(self, _rest: str) -> None:
        """Open the task pop-up from a carried writ, or print the task."""
        from systems.interface.popups import service as popup_service
        from systems.interface.popups.popup_defs.exterminator import EXTERMINATOR_POPUP_KEY

        caller = self.caller
        writ = service.carried_writ(caller)
        wants = popup_service.wants_popup(caller)

        if writ is not None and wants:
            opened = popup_service.open_popup(caller, EXTERMINATOR_POPUP_KEY, writ)

            if opened:
                return

        lines = caller.exterminator.summary_lines() + card_lines(caller)
        self._say("\n".join(lines))


    def _pick(self, rest: str) -> None:
        """
        Purpose: Pick a card by number, or show the cards to pick from.

        Entry:
            rest is "" or the number of a card.

        Exit/Returns:
            No conditions.

        Module Globals:
            None.

        Methodology:
            1. With a number, pick that card.
            2. With no number and a client that draws pop-ups, show the task
               pop-up with its cards.
            3. Else, open the pick menu.

        Notes/References:
            The pop-up never opens beside an EvMenu (CLAUDE.md, "Pop-ups").

        Author: Nick Hobar
        Creation date: 10/06/2026
        """
        from systems.interface.menus.base_menu import start_blackout_menu
        from systems.interface.popups import service as popup_service

        caller = self.caller
        number_text = rest.strip()

        if number_text:
            number = int(number_text) if number_text.isdigit() else 0
            _picked, message = caller.exterminator.pick(number)
            self._say(message)
            return

        if caller.exterminator.banked_picks() <= 0:
            self._say(ext_const.MSG_NO_PICK)
            return

        wants = popup_service.wants_popup(caller)
        writ = service.carried_writ(caller)

        if wants and writ is not None:
            self._show("")
            return

        start_blackout_menu(caller, _PICK_MENU_MODULE, startnode="start")


    def _new(self, rest: str) -> None:
        """Take a task from a Preceptor here."""
        preceptor_npc = service.preceptor_here(self.caller, rest)

        if preceptor_npc is None:
            self._say(ext_const.MSG_NO_PRECEPTOR_HERE)
            return

        lines = service.take_task(self.caller, preceptor_npc)
        self._say("\n".join(lines))


    def _skip(self, _rest: str) -> None:
        """Drop the task for points."""
        _skipped, message = self.caller.exterminator.skip()
        self._say(message)


    def _writ(self, rest: str) -> None:
        """Get a new Task Writ from a Preceptor here."""
        preceptor_npc = service.preceptor_here(self.caller, rest)

        if preceptor_npc is None:
            self._say(ext_const.MSG_NO_PRECEPTOR_HERE)
            return

        writ_line = service.give_writ(self.caller, preceptor_npc)
        self._say(writ_line)



class ExterminatorCmdSet(CmdSet):
    """
    Purpose: Holds the `task` command on every character.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        _TASK_CMD_SET_KEY read.

    Methodology:
        On the character, not on the Preceptor. `task` and `task skip` work
        anywhere, and `task new` finds a Preceptor in the room itself. Thus,
        no Preceptor needs a persistent cmdset of its own.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """

    key = _TASK_CMD_SET_KEY

    def at_cmdset_creation(self) -> None:
        """Add the `task` command."""
        self.add(CmdTask())
