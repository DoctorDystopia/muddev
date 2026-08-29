"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Custom commands for players to interact with the progression system.
"""



from commands.command import Command
from commands.constants import HELP_CATEGORY_ADMIN, HELP_CATEGORY_PROGRESSION
from evennia import CmdSet
from systems.menus.base_menu import start_blackout_menu
from systems.progression.skills.registry import SKILL_REGISTRY
from systems.ui.meters import build_xp_meter
from systems.statefeed import constants as feed_const

# Every line this module sends a player is progression, so the routing tag is
# bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_PROGRESSION = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_PROGRESSION}



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


    SKILLS_MENU_PATH = "systems.menus.skills_menu"

    OTHER_HEADER = "|c--- {name}'s Skills ---|n"
    NO_SKILLS_MSG = "{name} has not acquired any skills yet."


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
            systems/progression/skills/detail.py, which is also what the menu
            node prints and what CHANNEL_CHAR_SKILLS ships as data.

        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        from systems.progression.skills import detail as skill_detail
        from systems.statefeed import events as feed

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
        Purpose: Print another character's skill levels.

        Entry:
            name is what the player typed, already stripped and known not to
            name a skill.

        Exit/Returns:
            No conditions.

        Module Globals:
            SKILL_REGISTRY read.
            OTHER_HEADER, NO_SKILLS_MSG read.

        Methodology:
            Unchanged from the behaviour this command has always had, lifted
            out of func so the three readings of the argument read as three
            branches rather than as one branch and forty lines.

            A failed search reports itself -- caller.search already told the
            player -- so this returns silently rather than adding a second
            complaint about the same miss.

        Notes/References:
            The levels shown are read through the target's own handler, so a
            skill added since that character was created reports 0 rather than
            being absent.

        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        caller = self.caller
        target = caller.search(name, global_search=True)

        if target is None:
            return

        target_name = target.name
        skills_dict = target.db.skills

        if not skills_dict:
            caller.msg((self.NO_SKILLS_MSG.format(name=target_name),
                        _MSG_PROGRESSION))
            return

        output_lines = [self.OTHER_HEADER.format(name=target_name)]

        for skill_key, skill_data in skills_dict.items():
            if skill_key not in SKILL_REGISTRY:
                continue

            skill_class = SKILL_REGISTRY[skill_key]
            current_xp, total_xp_needed, _remaining = (
                target.skills.get_xp_level(skill_key))
            xp_meter = build_xp_meter(current_xp, total_xp_needed)

            output_lines.append(
                f"|w{skill_class.name}:|n Level {skill_data['level']} {xp_meter}")

        screen = "\n".join(output_lines)
        caller.msg((screen, _MSG_PROGRESSION))



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

            Deliberately takes no target argument. `skills <name>` already
            exposes another player's skills; a full dossier is private state
            (holdings, bank, quest progress), and the public subset belongs in
            its own command with its own per-panel filtering rather than as an
            argument here that would leak everything by default.

        Notes/References:
            The MUD convention for this command is `score`; `sc`, `dossier`
            and `char` are aliases for players arriving from elsewhere.

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        from systems.menus.summary_menu import start_summary_menu

        start_summary_menu(self.caller)


class CmdProfile(Command):
    """
    Show the public profile of another character -- what anyone may read about
    them. With no argument, shows your own, so you can see what others see.

    Usage:
      profile
      profile <character>
    """
    key = "profile"
    aliases = ["whois", "honours"]
    locks = "cmd:all()"
    help_category = HELP_CATEGORY_PROGRESSION


    NOT_A_CHARACTER_MSG = "You can only read a profile for a character."


    def func(self) -> None:
        """
        Purpose: Renders a character's public profile.

        Entry:
            self.caller is a valid Evennia Character object.
            self.args optionally names the character to look up.

        Exit/Returns:
            No conditions.

        Module Globals:
            None

        Methodology:
            Empty argument targets the caller. That is the useful default here
            rather than an error: the first question a player has about a
            public profile is what it says about them.

            A global search matches the behaviour `skills <name>` already has,
            so the two lookups behave the same way from the player's side.

            The target is checked for a `skills` handler rather than for a
            Character typeclass. Same reason CombatEntity gates on the optional
            API surface instead of isinstance: an NPC or a future typeclass
            that grows real skills should be readable, and a chair should not,
            and that is decided by what the object can answer, not by what it
            inherits from.

        Notes/References:
            Renders through service.render_public_summary, which walks only the
            panels flagged public and calls each through its narrowed public
            renderer. This command decides WHO is shown, never WHAT.

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        from systems.summary.service import render_public_summary

        caller = self.caller
        clean_args = self.args.strip()

        if not clean_args:
            target = caller
        else:
            target = caller.search(clean_args, global_search=True)

            if target is None:
                # caller.search already reported the failure.
                return

        has_skills = getattr(target, "skills", None) is not None

        if not has_skills:
            caller.msg((self.NOT_A_CHARACTER_MSG, _MSG_PROGRESSION))
            return

        screen = render_public_summary(target)
        caller.msg((screen, _MSG_PROGRESSION))


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
        self.add(CmdProfile())
        self.add(CmdAddXP())
