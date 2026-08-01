"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Custom commands for players to interact with the progression system.
"""



from commands.command import Command
from evennia import CmdSet
from evennia.utils.evmenu import EvMenu
from systems.progression.skills.registry import SKILL_REGISTRY
from systems.ui.meters import build_xp_meter



class CmdSkills(Command):
    """
    Purpose: Displays the player's current skill levels and XP progress.
    Can also target other players to view their skills.
    """
    key = "skills"
    aliases = ["skill", "sk"]
    locks = "cmd:all()"
    help_category = "Progression"


    SKILLS_MENU_PATH = "systems.menus.skills_menu"


    def func(self) -> None:
        """
        Purpose: Executes the skills command, launching the skills menu.

        Entry:
            self.caller is a valid Evennia Character object
            self.args is a string (potentially empty)

        Exit/Returns:
            No conditions

        Module Globals:
            SKILL_REGISTRY read
            SKILLS_MENU_PATH read

        Methodology:
            If arguments are provided, shows another player's skills
            as a text summary. Otherwise, opens the interactive
            skills panel menu for self-view.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        caller = self.caller
        raw_args = self.args
        clean_args = raw_args.strip()
        has_args = bool(clean_args)

        if has_args:
            # Show another player's skills as text
            target = caller.search(clean_args, global_search=True)
            target_not_found = target is None

            if target_not_found:
                return

            target_name = target.name
            output_lines = [f"|c--- {target_name}'s Skills ---|n"]

            skills_dict = target.db.skills

            if not skills_dict:
                caller.msg(f"{target_name} has not acquired any skills yet.")
                return

            for skill_key, skill_data in skills_dict.items():
                is_valid_skill = skill_key in SKILL_REGISTRY

                if is_valid_skill:
                    skill_class = SKILL_REGISTRY[skill_key]
                    skill_name = skill_class.name
                    current_lvl = skill_data["level"]

                    xp_tuple = target.skills.get_xp_level(skill_key)
                    current_xp = xp_tuple[0]
                    total_xp_needed = xp_tuple[1]

                    xp_meter = build_xp_meter(current_xp, total_xp_needed)
                    line_string = (
                        f"|w{skill_name}:|n Level {current_lvl} {xp_meter}"
                    )
                    output_lines.append(line_string)

            final_output = "\n".join(output_lines)
            caller.msg(final_output)
        else:
            # Open interactive skills panel menu for self
            EvMenu(
                caller,
                self.SKILLS_MENU_PATH,
                startnode="start",
            )



class CmdAddXP(Command):
    """
    Purpose: Administrative command to grant XP directly to a character's skill.
    """
    key = "addxp"
    aliases = ["grantxp"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"


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
            caller.msg("Usage: addxp <character> <skill_key> <amount>")
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
            caller.msg(f"Error: '{skill_key}' is not a valid skill in the registry.")
            return
            
        is_numeric = amount_str.lstrip('-').isdigit()
        
        if not is_numeric:
            caller.msg("Error: The XP amount must be a whole number.")
            return
            
        amount = int(amount_str)
        target_handler = target.skills
        
        target_handler.add_xp(skill_key, amount)
        
        success_msg = f"Successfully granted {amount} XP to {target.name}'s {skill_key} skill."
        caller.msg(success_msg)



class ProgressionCmdSet(CmdSet):

    def at_cmdset_creation(self):
        self.add(CmdSkills())
        self.add(CmdAddXP())