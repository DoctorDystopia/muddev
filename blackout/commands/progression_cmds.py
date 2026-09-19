"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Custom commands for players to interact with the progression system.
"""



from commands.command import Command
from commands.constants import HELP_CATEGORY_ADMIN, HELP_CATEGORY_PROGRESSION
from evennia import CmdSet
from systems.interface.menus import constants as menu_const
from systems.interface.menus.base_menu import start_blackout_menu
from systems.gameplay.progression.skills.registry import SKILL_REGISTRY
from systems.interface.statefeed import constants as feed_const

# Every line this module sends a player is progression, so the routing tag is
# bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/interface/statefeed/constants.py.
_MSG_PROGRESSION = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_PROGRESSION}

# What `profile`, `skills` and `stats` say about a target that is not a
# character.
_NOT_A_CHARACTER_MSG = "You can only read a profile for a character."


def _find_character(caller, name: str):
    """
    Purpose: Find the character that `profile`, `skills` or `stats` names.

    Entry:
        caller - the character who searches.
        name   - what the player typed: a name, or a dbref such as `#42`.

    Exit/Returns:
        Returns the character, or None. On None the player was already told
        why.

    Module Globals:
        _NOT_A_CHARACTER_MSG read.

    Methodology:
        A global search, so a profile is readable from anywhere.

        `use_dbref=True`, because a click on a player sends that player's
        dbref. A name cannot do that job: `skills Guns` reads the Guns skill
        first, and two names can share a prefix. Evennia gives a dbref search
        to Builders only unless the caller asks for it.

        The target must have a `skills` handler, not a Character typeclass. A
        chair found by its dbref is refused, and an object that grows real
        skills later is readable with no edit here.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    target = caller.search(name, global_search=True, use_dbref=True)

    if target is None:
        return None

    has_skills = getattr(target, "skills", None) is not None

    if not has_skills:
        caller.msg((_NOT_A_CHARACTER_MSG, _MSG_PROGRESSION))
        return None

    return target


def _open_profile(caller, target, page: str) -> None:
    """Open the profile menu of `target` at one page.

    The import is deferred to keep the summary panel registry's package walk
    out of cmdset import time, as CmdProfile always did.
    """
    from systems.interface.menus.profile_menu import start_profile_menu

    start_profile_menu(caller, target, startnode=page)



class CmdSkills(Command):
    """
    Show your skills, one skill's full sheet, or another character's levels.

    Usage:
      skills                  open your skills panel
      skills <skill>          read one skill: XP, progress and what it unlocks
      skills <character>      another character's levels

    Examples:
      skills cutting
      skills brain            a unique prefix is enough
    """
    key = "skills"
    aliases = ["skill", "sk"]
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_PROGRESSION


    SKILLS_MENU_PATH = "systems.interface.menus.skills_menu"

    # The label of this command on the click menu of another player. See
    # Character.extra_actions.
    ENTITY_ACTION_LABEL = "Skills"


    def func(self) -> None:
        """
        Purpose: Executes the skills command.

        Entry:
            self.caller is a valid Evennia Character object
            self.args is a string (potentially empty)

        Exit/Returns:
            No conditions

        Module Globals:
            SKILLS_MENU_PATH read

        Methodology:
            Three readings of one argument, resolved in a fixed order.

            A SKILL NAME WINS OVER A CHARACTER NAME, and that ordering is
            deliberate rather than incidental. It takes nothing away: before
            this branch existed, `skills cutting` searched the room for a
            character called "cutting", failed, and printed "Could not find".
            Every string the skill branch now claims is one that used to be an
            error, so nothing that worked stopped working -- and a character
            standing there actually named Cutting is the only collision, which
            `look` and `profile` both still answer.

            The feed publish happens FIRST, before the branch, because all
            three readings answer the same question -- the player is asking
            about skills -- and a graphical client's grid should be current
            whichever one they meant. It pre-checks its subscription and costs
            nothing on a telnet-only server, like every other feed call.

        Notes/References:
            The per-skill sheet is rendered by
            systems/gameplay/progression/skills/detail.py, which is also what the menu
            node prints and what CHANNEL_CHAR_SKILLS ships as data.

        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        from systems.gameplay.progression.skills import detail as skill_detail
        from systems.interface.statefeed import events as feed

        caller = self.caller
        clean_args = self.args.strip()

        feed.emit_skills(caller)

        if not clean_args:
            start_blackout_menu(
                caller,
                self.SKILLS_MENU_PATH,
                startnode="start",
            )
            return

        skill_key = skill_detail.resolve_skill_key(clean_args)

        if skill_key:
            sheet = skill_detail.render_detail(caller, skill_key)
            caller.msg((sheet, _MSG_PROGRESSION))
            return

        self._show_other(clean_args)


    def _show_other(self, name: str) -> None:
        """
        Purpose: Open another character's profile at the skills page.

        Entry:
            name is what the player typed, already stripped and known not to
            name a skill.

        Exit/Returns:
            No conditions.

        Module Globals:
            None.

        Methodology:
            Until 09/18/2026 this printed the levels as one block of text. It
            now opens the profile menu at its skills page, so `skills
            <character>`, `profile <character>` and `stats <character>` are
            three doors into one screen. A Godot client shows that screen as
            a pop-up.

            A failed search reports itself -- caller.search already told the
            player -- so this returns silently rather than adding a second
            complaint about the same miss.

        Notes/References:
            systems/interface/menus/profile_menu.py renders the levels.

        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        target = _find_character(self.caller, name)

        if target is None:
            return

        _open_profile(self.caller, target, menu_const.PROFILE_NODE_SKILLS)



class CmdScore(Command):
    """
    Show your dossier: combat level, hitpoints, readiness, holdings and
    progress on one screen, with jumps into the panel that owns each number.

    Skills are NOT on it. They were, until the roster outgrew a band: one line
    per category with a level beside each name says less than the `skills`
    screen already says, in more space, and a graphical client drawing a grid
    of them had to reach into the dossier payload and pull one panel out by
    name -- which is the one thing that payload's contract forbids. The
    aggregate figures stay here (combat level, total level, total XP) and
    `Skills panel` below is the jump into the roster.

    Usage:
      score
    """
    key = "score"
    aliases = ["sc", "dossier", "char"]
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_PROGRESSION


    def func(self) -> None:
        """
        Purpose: Opens the player summary screen.

        Entry:
            self.caller is a valid Evennia Character object.

        Exit/Returns:
            No conditions.

        Module Globals:
            None

        Methodology:
            Delegates straight to the menu module, which owns both the screen
            and its drill-down handoff. Nothing about the layout lives here --
            `score` is a launcher, and a second caller (a login greeting, a
            web-client panel) should be able to open the same screen without
            going through a command.

            Takes no target argument, because the drill-downs below the
            dossier open the CALLER's own screens. `profile <name>` shows the
            same dossier of any other character. Everything on it is public.

        Notes/References:
            The MUD convention for this command is `score`; `sc`, `dossier`
            and `char` are aliases for players arriving from elsewhere.

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        from systems.interface.menus.summary_menu import start_summary_menu

        start_summary_menu(self.caller)


class CmdStats(Command):
    """
    Show lifetime records: kills and deaths per hostile, harvests per node,
    credits spent.

    Your dossier (`score`) carries the short form of the same tallies; this
    names every entry. Name another character to read their records.

    Usage:
      stats
      stats <character>
    """
    key = "stats"
    aliases = ["records"]
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_PROGRESSION

    # The label of this command on the click menu of another player. See
    # Character.extra_actions.
    ENTITY_ACTION_LABEL = "Records"


    def func(self) -> None:
        """
        Purpose: Prints the caller's full records sheet, or opens another
                 character's profile at its records page.

        Entry:
            self.caller is a valid Evennia Character object.
            self.args optionally names a character.

        Exit/Returns:
            No conditions.

        Module Globals:
            _MSG_PROGRESSION read.

        Methodology:
            A launcher, like `score`: the sheet is built by RecordsPanel, the
            same module that draws the dossier band, so the two cannot describe
            a tally differently.

            With an argument, it opens the profile menu at its records page,
            the same screen `profile <character>` opens. Records are public.

        Notes/References:
            The panel is imported inside func, as CmdProfile imports the
            summary service, to keep the panel registry's package walk out of
            cmdset import time.

        Author: Nick Hobar
        Creation date: 09/13/2026
        """
        from systems.interface.summary.panel_defs.records import RecordsPanel

        clean_args = self.args.strip()

        if clean_args:
            target = _find_character(self.caller, clean_args)

            if target is not None:
                _open_profile(self.caller, target, menu_const.PROFILE_NODE_RECORDS)

            return

        screen = RecordsPanel.sheet(self.caller)
        self.caller.msg((screen, _MSG_PROGRESSION))


class CmdProfile(Command):
    """
    Show the profile of a character: their dossier, their skills and their
    records. With no argument, shows your own.

    Everything on a profile is public. Another player reads the same dossier
    that you read with `score`.

    Usage:
      profile
      profile <character>
    """
    key = "profile"
    aliases = ["whois", "honours"]
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_PROGRESSION

    # The label of this command on the click menu of another player. See
    # Character.extra_actions.
    ENTITY_ACTION_LABEL = "Profile"


    def func(self) -> None:
        """
        Purpose: Opens a character's profile at the dossier page.

        Entry:
            self.caller is a valid Evennia Character object.
            self.args optionally names the character to look up.

        Exit/Returns:
            No conditions.

        Module Globals:
            None

        Methodology:
            Empty argument targets the caller. That is the useful default here
            rather than an error.

            There was a narrower "public" dossier until 09/18/2026. It hid
            hitpoints, location, holdings, equipment and records. The game
            now treats all of it as public, so the profile renders the full
            dossier, and the panels carry no public flag.

        Notes/References:
            systems/interface/menus/profile_menu.py owns the pages.
            _find_character owns the search and the character check.

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        caller = self.caller
        clean_args = self.args.strip()
        target = caller

        if clean_args:
            target = _find_character(caller, clean_args)

        if target is None:
            return

        _open_profile(caller, target, menu_const.PROFILE_NODE_DOSSIER)


class CmdAddXP(Command):
    """
    Purpose: Administrative command to grant XP directly to a character's skill.
    """
    key = "addxp"
    aliases = ["grantxp"]
    locks = "cmd:perm(Admin)"
    help_category = HELP_CATEGORY_ADMIN


    def func(self) -> None:
        """
        Purpose: Parses arguments to locate a target, validate a skill, and add XP.
        
        Entry:
            self.caller is a valid Evennia Character object
            self.args is a string containing target, skill, and amount
        
        Exit/Returns:
            No conditions
        
        Module Globals:
            SKILL_REGISTRY read
            
        Methodology:
            Splits the argument string. Validates the argument count. Searches 
            for the target character. Validates the skill key against the registry. 
            Converts the amount to an integer and invokes the skill handler to 
            process the XP addition.
            
        Notes/References:
            None
            
        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        caller = self.caller
        raw_args = self.args
        clean_args = raw_args.strip()
        split_args = clean_args.split()
        
        arg_count = len(split_args)
        has_correct_args = arg_count == 3
        
        if not has_correct_args:
            caller.msg(
                ("Usage: addxp <character> <skill_key> <amount>", _MSG_PROGRESSION))
            return
            
        target_name = split_args[0]
        skill_key = split_args[1]
        amount_str = split_args[2]
        
        target = caller.search(target_name, global_search=True)
        target_not_found = target is None
        
        if target_not_found:
            # caller.search handles the "Not Found" error message automatically
            return
            
        is_valid_skill = skill_key in SKILL_REGISTRY
        
        if not is_valid_skill:
            caller.msg(
                (f"Error: '{skill_key}' is not a valid skill in the registry.",
                 _MSG_PROGRESSION))
            return
            
        is_numeric = amount_str.lstrip('-').isdigit()
        
        if not is_numeric:
            caller.msg(
                ("Error: The XP amount must be a whole number.", _MSG_PROGRESSION))
            return
            
        amount = int(amount_str)
        target_handler = target.skills
        
        target_handler.add_xp(skill_key, amount)
        
        success_msg = f"Successfully granted {amount} XP to {target.name}'s {skill_key} skill."
        caller.msg((success_msg, _MSG_PROGRESSION))



class ProgressionCmdSet(CmdSet):

    def at_cmdset_creation(self):
        self.add(CmdSkills())
        self.add(CmdScore())
        self.add(CmdStats())
        self.add(CmdProfile())
        self.add(CmdAddXP())
